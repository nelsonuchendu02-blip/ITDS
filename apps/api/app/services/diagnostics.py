from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..diagnostics.provider import SimulatedDiagnosticProvider
from ..exceptions import PersistenceError, SecurityError
from ..models import DiagnosticCheckType, DiagnosticResult, DiagnosticRun, DiagnosticRunStatus, Device, User
from ..repositories import DiagnosticRepository
from .audit import record_security_event


class DiagnosticService:
    def __init__(self, repository: DiagnosticRepository | None = None, provider=None):
        self.repository = repository or DiagnosticRepository()
        self.provider = provider or SimulatedDiagnosticProvider()

    def create(self, session: Session, *, organization_id: UUID, actor: User,
               device_id: UUID, diagnostic_type: str, provider: str = "simulated") -> DiagnosticRun:
        if actor.organization_id != organization_id or provider != "simulated":
            raise SecurityError("invalid_provider", "Unsupported diagnostic provider", 422)
        if diagnostic_type not in {check.value for check in DiagnosticCheckType}:
            raise SecurityError("invalid_check_type", "Unsupported diagnostic check type", 422)
        if session.scalar(select(Device.id).where(
            Device.id == device_id, Device.organization_id == organization_id,
        )) is None:
            raise SecurityError("device_not_found", "Device not found", 404)
        run = DiagnosticRun(
            organization_id=organization_id, device_id=device_id, created_by_user_id=actor.id,
            diagnostic_type=diagnostic_type, provider=provider,
        )
        try:
            self.repository.create(session, run)
            record_security_event(session, event_type="diagnostic_created",
                organization_id=organization_id, actor_user_id=actor.id, action="create",
                result="success", resource_type="diagnostic_run", resource_id=str(run.id))
            session.commit()
            session.refresh(run)
            return run
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Diagnostic run could not be created") from exc

    def get(self, session, run_id, organization_id):
        return self.repository.get(session, run_id, organization_id)

    def list(self, session, organization_id, *, offset, limit, status=None):
        return self.repository.list_page(session, organization_id, offset=offset, limit=limit, status=status)

    def results(self, session, run, organization_id):
        return self.repository.results(session, run.id, organization_id)

    def run(self, session: Session, *, run: DiagnosticRun, actor: User) -> DiagnosticRun:
        self._scope(run, actor)
        now = datetime.now(timezone.utc)
        if not self.repository.transition(session, run.id, actor.organization_id,
                DiagnosticRunStatus.PENDING, DiagnosticRunStatus.RUNNING, started_at=now):
            session.rollback()
            raise SecurityError("invalid_transition", "Diagnostic run cannot be started", 409)
        record_security_event(session, event_type="diagnostic_started",
            organization_id=run.organization_id, actor_user_id=actor.id, action="start",
            result="success", resource_type="diagnostic_run", resource_id=str(run.id))
        session.commit()
        try:
            checks = self.provider.run(device_id=run.device_id, diagnostic_type=run.diagnostic_type)
            current = self.repository.get(session, run.id, actor.organization_id)
            if current is None:
                raise PersistenceError("Diagnostic run not found")
            for check in checks:
                session.add(DiagnosticResult(
                    diagnostic_run_id=current.id, check_identifier=check.identifier,
                    organization_id=current.organization_id, device_id=current.device_id,
                    check_type=check.check_type, status=check.status, severity=check.severity,
                    observed_value=check.observed, expected_value=check.expected, message=check.message,
                    title=check.identifier.replace(".", " ").title(),
                    summary=check.message,
                    recommendation=None,
                    result_metadata={"provider": current.provider, "simulation": True},
                    checked_at=datetime.now(timezone.utc),
                ))
            if not self.repository.transition(session, run.id, actor.organization_id,
                    DiagnosticRunStatus.RUNNING, DiagnosticRunStatus.COMPLETED,
                    completed_at=datetime.now(timezone.utc)):
                session.rollback()
                return self.repository.get(session, run.id, actor.organization_id) or current
            record_security_event(session, event_type="diagnostic_completed",
                organization_id=run.organization_id, actor_user_id=actor.id, action="complete",
                result="success", resource_type="diagnostic_run", resource_id=str(run.id))
            session.commit()
            return self.repository.get(session, run.id, actor.organization_id) or current
        except Exception as exc:
            session.rollback()
            if self.repository.transition(session, run.id, actor.organization_id,
                    DiagnosticRunStatus.RUNNING, DiagnosticRunStatus.FAILED,
                    completed_at=datetime.now(timezone.utc), error_code="diagnostic_execution_failed"):
                record_security_event(session, event_type="diagnostic_failed",
                    organization_id=run.organization_id, actor_user_id=actor.id, action="fail",
                    result="failure", resource_type="diagnostic_run", resource_id=str(run.id))
                session.commit()
            raise PersistenceError("Diagnostic run could not be completed", 500) from exc

    def cancel(self, session, *, run, actor):
        self._scope(run, actor)
        if run.status not in {DiagnosticRunStatus.PENDING, DiagnosticRunStatus.RUNNING}:
            raise SecurityError("invalid_transition", "Diagnostic run cannot be cancelled", 409)
        if not self.repository.transition(session, run.id, actor.organization_id,
                run.status, DiagnosticRunStatus.CANCELLED,
                cancelled_at=datetime.now(timezone.utc)):
            session.rollback()
            raise SecurityError("invalid_transition", "Diagnostic run cannot be cancelled", 409)
        record_security_event(session, event_type="diagnostic_cancelled",
            organization_id=run.organization_id, actor_user_id=actor.id, action="cancel",
            result="success", resource_type="diagnostic_run", resource_id=str(run.id))
        session.commit()
        return self.repository.get(session, run.id, actor.organization_id)

    @staticmethod
    def _scope(run, actor):
        if run.organization_id != actor.organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)
