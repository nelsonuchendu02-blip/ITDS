from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import (
    DiscoveryJob,
    DiscoveryJobStatus,
    DiscoveryResult,
    DiscoveryResultStatus,
    ReconciliationStatus,
)


class DiscoveryJobRepository:
    def create(self, session: Session, job: DiscoveryJob) -> DiscoveryJob:
        session.add(job)
        session.flush()
        return job

    def get_by_id(self, session: Session, job_id: UUID, organization_id: UUID) -> DiscoveryJob | None:
        return session.scalar(
            select(DiscoveryJob).where(
                DiscoveryJob.id == job_id,
                DiscoveryJob.organization_id == organization_id,
            )
        )

    def active_for_target(
        self, session: Session, organization_id: UUID, provider: str, target_definition: str
    ) -> DiscoveryJob | None:
        return session.scalar(
            select(DiscoveryJob).where(
                DiscoveryJob.organization_id == organization_id,
                DiscoveryJob.provider == provider,
                DiscoveryJob.target_definition == target_definition,
                DiscoveryJob.status.in_([DiscoveryJobStatus.PENDING, DiscoveryJobStatus.RUNNING]),
            )
        )

    def transition(
        self,
        session: Session,
        job_id: UUID,
        organization_id: UUID,
        *,
        expected_status: DiscoveryJobStatus,
        status: DiscoveryJobStatus,
        started_at=None,
        completed_at=None,
        cancelled_at=None,
        error_code: str | None = None,
    ) -> bool:
        values = {"status": status}
        if started_at is not None:
            values["started_at"] = started_at
        if completed_at is not None:
            values["completed_at"] = completed_at
        if cancelled_at is not None:
            values["cancelled_at"] = cancelled_at
        if error_code is not None:
            values["error_code"] = error_code
        result = session.execute(
            update(DiscoveryJob)
            .where(
                DiscoveryJob.id == job_id,
                DiscoveryJob.organization_id == organization_id,
                DiscoveryJob.status == expected_status,
            )
            .values(**values)
        )
        return result.rowcount == 1

    def list_page(
        self, session: Session, organization_id: UUID, *, offset: int, limit: int,
        status: DiscoveryJobStatus | None = None, provider: str | None = None,
    ) -> tuple[list[DiscoveryJob], int]:
        filters = [DiscoveryJob.organization_id == organization_id]
        if status:
            filters.append(DiscoveryJob.status == status)
        if provider:
            filters.append(DiscoveryJob.provider == provider)
        statement = select(DiscoveryJob).where(*filters)
        count_statement = select(func.count()).select_from(DiscoveryJob).where(*filters)
        return (
            session.scalars(
                statement.order_by(DiscoveryJob.created_at.desc(), DiscoveryJob.id).offset(offset).limit(limit)
            ).all(),
            session.scalar(count_statement) or 0,
        )


class DiscoveryResultRepository:
    def create(self, session: Session, result: DiscoveryResult) -> DiscoveryResult:
        session.add(result)
        session.flush()
        return result

    def list_page(
        self, session: Session, job_id: UUID, organization_id: UUID, *, offset: int, limit: int,
        status: DiscoveryResultStatus | None = None,
        reconciliation_status: ReconciliationStatus | None = None,
        ip: str | None = None, hostname: str | None = None,
    ) -> tuple[Sequence[DiscoveryResult], int]:
        filters = [
            DiscoveryResult.discovery_job_id == job_id,
            DiscoveryResult.organization_id == organization_id,
        ]
        if status:
            filters.append(DiscoveryResult.status == status)
        if reconciliation_status:
            filters.append(DiscoveryResult.reconciliation_status == reconciliation_status)
        if ip:
            filters.append(DiscoveryResult.target_ip == ip)
        if hostname:
            filters.append(func.lower(DiscoveryResult.discovered_hostname) == hostname.lower())
        statement = select(DiscoveryResult).where(*filters)
        count_statement = select(func.count()).select_from(DiscoveryResult).where(*filters)
        return (
            session.scalars(
                statement.order_by(DiscoveryResult.discovered_at.desc(), DiscoveryResult.id)
                .offset(offset).limit(limit)
            ).all(),
            session.scalar(count_statement) or 0,
        )
