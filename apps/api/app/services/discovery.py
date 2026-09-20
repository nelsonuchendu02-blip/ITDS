from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..discovery.provider import (
    DiscoveryProvider,
    NormalizedTarget,
    ProviderResult,
    SimulatedDiscoveryProvider,
    normalize_target,
)
from ..exceptions import PersistenceError, SecurityError
from ..models import (
    Device,
    DiscoveryJob,
    DiscoveryJobStatus,
    DiscoveryResult,
    DiscoveryResultStatus,
    ReconciliationStatus,
    User,
)
from ..repositories import DiscoveryJobRepository, DiscoveryResultRepository
from .audit import record_security_event

ALLOWED_PROVIDERS = frozenset({"simulated"})


class DiscoveryService:
    def __init__(
        self,
        jobs: DiscoveryJobRepository | None = None,
        results: DiscoveryResultRepository | None = None,
        providers: dict[str, DiscoveryProvider] | None = None,
    ) -> None:
        self.jobs = jobs or DiscoveryJobRepository()
        self.results = results or DiscoveryResultRepository()
        self.providers = providers or {"simulated": SimulatedDiscoveryProvider()}

    def create_job(
        self, session: Session, *, organization_id: UUID, actor: User,
        provider: str, target: str,
    ) -> DiscoveryJob:
        if actor.organization_id != organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)
        if provider not in ALLOWED_PROVIDERS or provider not in self.providers:
            raise SecurityError("invalid_provider", "Unsupported discovery provider", 422)
        try:
            normalized = normalize_target(target)
        except ValueError as exc:
            raise SecurityError("invalid_target", str(exc), 422) from exc
        if self.jobs.active_for_target(
            session, organization_id, provider, normalized.definition
        ):
            raise PersistenceError("An active discovery job already exists for this target")
        job = DiscoveryJob(
            organization_id=organization_id,
            created_by_user_id=actor.id,
            provider=provider,
            target_type=normalized.target_type,
            target_definition=normalized.definition,
            target_count=normalized.count,
        )
        try:
            self.jobs.create(session, job)
            record_security_event(
                session,
                event_type="discovery_job_created",
                organization_id=organization_id,
                actor_user_id=actor.id,
                action="create",
                result="success",
                metadata={
                    "provider": provider,
                    "target_type": normalized.target_type,
                    "target_count": normalized.count,
                },
                resource_type="discovery_job",
                resource_id=str(job.id),
            )
            self._commit(session)
            return job
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Discovery job could not be created") from exc

    def get_job(self, session: Session, job_id: UUID, organization_id: UUID) -> DiscoveryJob | None:
        return self.jobs.get_by_id(session, job_id, organization_id)

    def list_jobs(
        self, session: Session, organization_id: UUID, *, offset: int, limit: int,
        status: DiscoveryJobStatus | None = None, provider: str | None = None,
    ):
        return self.jobs.list_page(
            session, organization_id, offset=offset, limit=limit,
            status=status, provider=provider,
        )

    def start_job(self, session: Session, *, job: DiscoveryJob, actor: User) -> DiscoveryJob:
        self._assert_scope(job, actor)
        if job.status is not DiscoveryJobStatus.PENDING:
            raise SecurityError("invalid_transition", "Discovery job cannot be started", 409)
        started_at = datetime.now(timezone.utc)
        if not self.jobs.transition(
            session,
            job.id,
            actor.organization_id,
            expected_status=DiscoveryJobStatus.PENDING,
            status=DiscoveryJobStatus.RUNNING,
            started_at=started_at,
        ):
            session.rollback()
            raise SecurityError("invalid_transition", "Discovery job cannot be started", 409)
        record_security_event(
            session, event_type="discovery_started", organization_id=job.organization_id,
            actor_user_id=actor.id, action="start", result="success",
            metadata={"provider": job.provider}, resource_type="discovery_job",
            resource_id=str(job.id),
        )
        self._commit(session)
        job = self.jobs.get_by_id(session, job.id, actor.organization_id)
        if job is None:
            raise PersistenceError("Discovery job could not be started")
        provider = self.providers[job.provider]
        try:
            provider_results = provider.discover(
                NormalizedTarget(job.target_type, job.target_definition, job.target_count)
            )
            for provider_result in provider_results:
                self._persist_result(session, job, actor, provider_result)
            completed_at = datetime.now(timezone.utc)
            if not self.jobs.transition(
                session,
                job.id,
                actor.organization_id,
                expected_status=DiscoveryJobStatus.RUNNING,
                status=DiscoveryJobStatus.COMPLETED,
                completed_at=completed_at,
            ):
                session.rollback()
                current = self.jobs.get_by_id(session, job.id, actor.organization_id)
                if current is None:
                    raise PersistenceError("Discovery job could not be completed")
                return current
            record_security_event(
                session, event_type="discovery_completed", organization_id=job.organization_id,
                actor_user_id=actor.id, action="complete", result="success",
                metadata={"result_count": len(provider_results)}, resource_type="discovery_job",
                resource_id=str(job.id),
            )
            self._commit(session)
            return self.jobs.get_by_id(session, job.id, actor.organization_id) or job
        except IntegrityError as exc:
            self._mark_failed(
                session, job.id, actor,
                error_code="persistence_failure",
            )
            raise PersistenceError("Discovery job could not be completed") from exc
        except Exception as exc:
            self._mark_failed(
                session, job.id, actor,
                error_code="discovery_execution_failed",
            )
            raise PersistenceError("Discovery job could not be completed", 500) from exc

    def cancel_job(self, session: Session, *, job: DiscoveryJob, actor: User) -> DiscoveryJob:
        self._assert_scope(job, actor)
        if job.status not in {DiscoveryJobStatus.PENDING, DiscoveryJobStatus.RUNNING}:
            raise SecurityError("invalid_transition", "Discovery job cannot be cancelled", 409)
        if not self.jobs.transition(
            session,
            job.id,
            actor.organization_id,
            expected_status=job.status,
            status=DiscoveryJobStatus.CANCELLED,
            cancelled_at=datetime.now(timezone.utc),
        ):
            session.rollback()
            current = self.jobs.get_by_id(session, job.id, actor.organization_id)
            if current is None or current.status not in {
                DiscoveryJobStatus.PENDING, DiscoveryJobStatus.RUNNING
            }:
                raise SecurityError("invalid_transition", "Discovery job cannot be cancelled", 409)
            raise PersistenceError("Discovery job could not be cancelled")
        record_security_event(
            session, event_type="discovery_cancelled", organization_id=job.organization_id,
            actor_user_id=actor.id, action="cancel", result="success",
            metadata=None, resource_type="discovery_job", resource_id=str(job.id),
        )
        self._commit(session)
        return self.jobs.get_by_id(session, job.id, actor.organization_id) or job

    def _mark_failed(
        self, session: Session, job_id: UUID, actor: User, *, error_code: str
    ) -> None:
        session.rollback()
        if not self.jobs.transition(
            session,
            job_id,
            actor.organization_id,
            expected_status=DiscoveryJobStatus.RUNNING,
            status=DiscoveryJobStatus.FAILED,
            completed_at=datetime.now(timezone.utc),
            error_code=error_code,
        ):
            session.rollback()
            current = self.jobs.get_by_id(session, job_id, actor.organization_id)
            if current is not None and current.status is DiscoveryJobStatus.CANCELLED:
                return
            raise PersistenceError("Discovery job could not be completed")
        record_security_event(
            session,
            event_type="discovery_failed",
            organization_id=actor.organization_id,
            actor_user_id=actor.id,
            action="complete",
            result="failure",
            metadata={"error_code": error_code},
            resource_type="discovery_job",
            resource_id=str(job_id),
        )
        self._commit(session)

    def list_results(
        self, session: Session, *, job: DiscoveryJob, organization_id: UUID,
        offset: int, limit: int,         status: DiscoveryResultStatus | None = None,
        reconciliation_status: ReconciliationStatus | None = None, ip: str | None = None,
        hostname: str | None = None,
    ):
        return self.results.list_page(
            session, job.id, organization_id, offset=offset, limit=limit,
            status=status, reconciliation_status=reconciliation_status,
            ip=ip, hostname=hostname,
        )

    def _persist_result(
        self, session: Session, job: DiscoveryJob, actor: User, value: ProviderResult
    ) -> DiscoveryResult:
        device_matches = session.scalars(
            select(Device).where(
                Device.organization_id == job.organization_id,
                Device.ip_address == value.target_ip,
            )
        ).all()
        if not device_matches and value.hostname:
            device_matches = session.scalars(
                select(Device).where(
                    Device.organization_id == job.organization_id,
                    Device.hostname.ilike(value.hostname),
                )
            ).all()
        reconciliation = (
            ReconciliationStatus.MATCHED if len(device_matches) == 1
            else ReconciliationStatus.CONFLICT if len(device_matches) > 1
            else ReconciliationStatus.UNMATCHED
        )
        result = DiscoveryResult(
            discovery_job_id=job.id,
            organization_id=job.organization_id,
            target_ip=value.target_ip,
            discovered_hostname=value.hostname,
            discovered_device_type=value.device_type,
            discovered_operating_system=value.operating_system,
            provider=job.provider,
            status=DiscoveryResultStatus.DISCOVERED,
            reconciliation_status=reconciliation,
            matched_device_id=device_matches[0].id if len(device_matches) == 1 else None,
            discovered_at=datetime.now(timezone.utc),
            result_metadata=value.metadata,
        )
        self.results.create(session, result)
        record_security_event(
            session, event_type="discovery_result_recorded",
            organization_id=job.organization_id, actor_user_id=actor.id,
            action="record", result="success",
            metadata={"target_ip": value.target_ip, "reconciliation": reconciliation.value},
            resource_type="discovery_result", resource_id=str(result.id),
        )
        return result

    @staticmethod
    def _assert_scope(job: DiscoveryJob, actor: User) -> None:
        if job.organization_id != actor.organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)

    @staticmethod
    def _commit(session: Session) -> None:
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Discovery operation could not be completed") from exc
