from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import DiagnosticResult, DiagnosticRun, DiagnosticRunStatus


class DiagnosticRepository:
    def create(self, session: Session, run: DiagnosticRun) -> DiagnosticRun:
        session.add(run)
        session.flush()
        return run

    def get(self, session: Session, run_id: UUID, organization_id: UUID) -> DiagnosticRun | None:
        return session.scalar(select(DiagnosticRun).where(
            DiagnosticRun.id == run_id, DiagnosticRun.organization_id == organization_id,
        ))

    def list_page(self, session: Session, organization_id: UUID, *, offset: int, limit: int,
                  status: DiagnosticRunStatus | None = None) -> tuple[Sequence[DiagnosticRun], int]:
        filters = [DiagnosticRun.organization_id == organization_id]
        if status:
            filters.append(DiagnosticRun.status == status)
        return (
            session.scalars(select(DiagnosticRun).where(*filters).order_by(
                DiagnosticRun.created_at.desc(), DiagnosticRun.id).offset(offset).limit(limit)
            ).all(),
            session.scalar(select(func.count()).select_from(DiagnosticRun).where(*filters)) or 0,
        )

    def transition(self, session: Session, run_id: UUID, organization_id: UUID,
                   expected: DiagnosticRunStatus, status: DiagnosticRunStatus, **values) -> bool:
        result = session.execute(update(DiagnosticRun).where(
            DiagnosticRun.id == run_id, DiagnosticRun.organization_id == organization_id,
            DiagnosticRun.status == expected,
        ).values(status=status, **values))
        return result.rowcount == 1

    def results(self, session: Session, run_id: UUID, organization_id: UUID) -> Sequence[DiagnosticResult]:
        return session.scalars(select(DiagnosticResult).join(DiagnosticRun).where(
            DiagnosticResult.diagnostic_run_id == run_id,
            DiagnosticRun.organization_id == organization_id,
            DiagnosticResult.organization_id == organization_id,
        ).order_by(DiagnosticResult.created_at, DiagnosticResult.id)).all()
