from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import (
    DiagnosticResult, DiagnosticRun, RootCauseAnalysis, RootCauseAnalysisStatus, RootCauseFinding,
)


class RootCauseRepository:
    def create(self, session: Session, analysis: RootCauseAnalysis) -> RootCauseAnalysis:
        session.add(analysis)
        session.flush()
        return analysis

    def get(self, session: Session, analysis_id: UUID, organization_id: UUID) -> RootCauseAnalysis | None:
        return session.scalar(select(RootCauseAnalysis).where(
            RootCauseAnalysis.id == analysis_id,
            RootCauseAnalysis.organization_id == organization_id,
        ))

    def list_page(self, session: Session, organization_id: UUID, *, offset: int, limit: int):
        filters = [RootCauseAnalysis.organization_id == organization_id]
        return (
            session.scalars(select(RootCauseAnalysis).where(*filters).order_by(
                RootCauseAnalysis.created_at.desc(), RootCauseAnalysis.id
            ).offset(offset).limit(limit)).all(),
            session.scalar(select(func.count()).select_from(RootCauseAnalysis).where(*filters)) or 0,
        )

    def diagnostic_run(self, session: Session, run_id: UUID, organization_id: UUID) -> DiagnosticRun | None:
        return session.scalar(select(DiagnosticRun).where(
            DiagnosticRun.id == run_id, DiagnosticRun.organization_id == organization_id
        ))

    def results(self, session: Session, run_id: UUID, organization_id: UUID) -> Sequence[DiagnosticResult]:
        return session.scalars(select(DiagnosticResult).join(
            DiagnosticRun, DiagnosticRun.id == DiagnosticResult.diagnostic_run_id
        ).where(
            DiagnosticResult.diagnostic_run_id == run_id,
            DiagnosticResult.organization_id == organization_id,
            DiagnosticRun.organization_id == organization_id,
            DiagnosticResult.device_id == DiagnosticRun.device_id,
        ).order_by(DiagnosticResult.created_at, DiagnosticResult.id)).all()

    def transition(self, session: Session, analysis_id: UUID, organization_id: UUID,
                   expected: RootCauseAnalysisStatus, status: RootCauseAnalysisStatus, **values) -> bool:
        result = session.execute(update(RootCauseAnalysis).where(
            RootCauseAnalysis.id == analysis_id,
            RootCauseAnalysis.organization_id == organization_id,
            RootCauseAnalysis.status == expected,
        ).values(status=status, **values))
        return result.rowcount == 1

    def findings(self, session: Session, analysis_id: UUID, organization_id: UUID) -> Sequence[RootCauseFinding]:
        return session.scalars(select(RootCauseFinding).join(RootCauseAnalysis).where(
            RootCauseFinding.analysis_id == analysis_id,
            RootCauseAnalysis.organization_id == organization_id,
            RootCauseFinding.organization_id == organization_id,
        ).order_by(RootCauseFinding.severity.desc(), RootCauseFinding.rule_id, RootCauseFinding.id)).all()
