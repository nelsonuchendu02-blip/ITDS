from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..exceptions import PersistenceError, SecurityError
from ..models import (
    DiagnosticRunStatus, RootCauseAnalysis, RootCauseAnalysisStatus, RootCauseFinding, User,
)
from ..repositories import RootCauseRepository
from ..root_cause import evaluate_rules
from .audit import record_security_event


class RootCauseService:
    def __init__(self, repository: RootCauseRepository | None = None) -> None:
        self.repository = repository or RootCauseRepository()

    def create(self, session: Session, *, organization_id: UUID, diagnostic_run_id: UUID,
               actor: User) -> RootCauseAnalysis:
        self._actor_scope(actor, organization_id)
        run = self.repository.diagnostic_run(session, diagnostic_run_id, organization_id)
        if run is None:
            raise SecurityError("diagnostic_run_not_found", "Diagnostic run not found", 404)
        if run.status is not DiagnosticRunStatus.COMPLETED:
            raise SecurityError("diagnostic_run_not_completed", "Root-cause analysis requires a completed diagnostic run", 409)
        analysis = RootCauseAnalysis(
            organization_id=organization_id, device_id=run.device_id,
            diagnostic_run_id=run.id, initiated_by_user_id=actor.id,
        )
        try:
            self.repository.create(session, analysis)
            record_security_event(session, event_type="root_cause_analysis_created",
                                  organization_id=organization_id, actor_user_id=actor.id,
                                  action="create", result="success",
                                  resource_type="root_cause_analysis", resource_id=str(analysis.id))
            session.commit()
            session.refresh(analysis)
            return analysis
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Root-cause analysis could not be created") from exc

    def get(self, session: Session, analysis_id: UUID, organization_id: UUID):
        return self.repository.get(session, analysis_id, organization_id)

    def list(self, session: Session, organization_id: UUID, *, offset: int, limit: int):
        return self.repository.list_page(session, organization_id, offset=offset, limit=limit)

    def findings(self, session: Session, analysis: RootCauseAnalysis, organization_id: UUID):
        return self.repository.findings(session, analysis.id, organization_id)

    def run(self, session: Session, *, analysis: RootCauseAnalysis, actor: User) -> RootCauseAnalysis:
        self._assert_scope(analysis, actor)
        if analysis.status is not RootCauseAnalysisStatus.PENDING:
            raise SecurityError("invalid_transition", "Root-cause analysis cannot be started", 409)
        if not self.repository.transition(session, analysis.id, actor.organization_id,
                                          RootCauseAnalysisStatus.PENDING, RootCauseAnalysisStatus.RUNNING):
            session.rollback()
            raise SecurityError("invalid_transition", "Root-cause analysis cannot be started", 409)
        record_security_event(session, event_type="root_cause_analysis_started",
                              organization_id=analysis.organization_id, actor_user_id=actor.id,
                              action="start", result="success", resource_type="root_cause_analysis",
                              resource_id=str(analysis.id))
        session.commit()
        try:
            current = self.repository.get(session, analysis.id, actor.organization_id)
            if current is None:
                raise PersistenceError("Root-cause analysis could not be loaded")
            diagnostic_run = self.repository.diagnostic_run(
                session, current.diagnostic_run_id, actor.organization_id
            )
            if diagnostic_run is None or diagnostic_run.device_id != current.device_id:
                raise PersistenceError("Root-cause analysis diagnostic run could not be loaded")
            if diagnostic_run.status is not DiagnosticRunStatus.COMPLETED:
                raise PersistenceError("Root-cause analysis requires a completed diagnostic run")
            results = list(self.repository.results(session, current.diagnostic_run_id, actor.organization_id))
            for finding in evaluate_rules(results):
                fingerprint = f"{finding.rule_id}:{','.join(finding.evidence_result_ids)}"
                session.add(RootCauseFinding(
                    analysis_id=current.id, organization_id=current.organization_id,
                    device_id=current.device_id,
                    diagnostic_result_id=UUID(finding.evidence_result_ids[0]),
                    rule_id=finding.rule_id, category=finding.category, status=finding.status,
                    severity=finding.severity, confidence=finding.confidence,
                    title=finding.title, summary=finding.summary,
                    explanation=finding.explanation,
                    evidence={"diagnostic_result_ids": list(finding.evidence_result_ids),
                              "signals": [finding.summary]},
                    fingerprint=fingerprint,
                ))
            if not self.repository.transition(session, current.id, actor.organization_id,
                                              RootCauseAnalysisStatus.RUNNING, RootCauseAnalysisStatus.COMPLETED,
                                              completed_at=datetime.now(timezone.utc)):
                session.rollback()
                return self.repository.get(session, current.id, actor.organization_id) or current
            record_security_event(session, event_type="root_cause_analysis_completed",
                                  organization_id=current.organization_id, actor_user_id=actor.id,
                                  action="complete", result="success", resource_type="root_cause_analysis",
                                  resource_id=str(current.id))
            session.commit()
            return self.repository.get(session, current.id, actor.organization_id) or current
        except PersistenceError:
            session.rollback()
            self._mark_failed(session, analysis.id, actor, "root_cause_analysis_failed")
            raise
        except Exception as exc:
            session.rollback()
            self._mark_failed(session, analysis.id, actor, "root_cause_analysis_failed")
            raise PersistenceError("Root-cause analysis could not be completed", 500) from exc

    def cancel(self, session: Session, *, analysis: RootCauseAnalysis, actor: User) -> RootCauseAnalysis:
        self._assert_scope(analysis, actor)
        if analysis.status not in {RootCauseAnalysisStatus.PENDING, RootCauseAnalysisStatus.RUNNING}:
            raise SecurityError("invalid_transition", "Root-cause analysis cannot be cancelled", 409)
        if not self.repository.transition(session, analysis.id, actor.organization_id, analysis.status,
                                          RootCauseAnalysisStatus.CANCELLED,
                                          cancelled_at=datetime.now(timezone.utc)):
            session.rollback()
            raise SecurityError("invalid_transition", "Root-cause analysis cannot be cancelled", 409)
        record_security_event(session, event_type="root_cause_analysis_cancelled",
                              organization_id=analysis.organization_id, actor_user_id=actor.id,
                              action="cancel", result="success", resource_type="root_cause_analysis",
                              resource_id=str(analysis.id))
        session.commit()
        return self.repository.get(session, analysis.id, actor.organization_id)

    def _mark_failed(self, session: Session, analysis_id: UUID, actor: User, error_code: str) -> None:
        if self.repository.transition(session, analysis_id, actor.organization_id,
                                      RootCauseAnalysisStatus.RUNNING, RootCauseAnalysisStatus.FAILED,
                                      error_code=error_code, completed_at=datetime.now(timezone.utc)):
            record_security_event(session, event_type="root_cause_analysis_failed",
                                  organization_id=actor.organization_id, actor_user_id=actor.id,
                                  action="fail", result="failure", resource_type="root_cause_analysis",
                                  resource_id=str(analysis_id))
            session.commit()
        else:
            session.rollback()

    @staticmethod
    def _actor_scope(actor: User, organization_id: UUID) -> None:
        if actor.organization_id != organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)

    @staticmethod
    def _assert_scope(analysis: RootCauseAnalysis, actor: User) -> None:
        if analysis.organization_id != actor.organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)
