from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ..models import Recommendation, RecommendationStatus, RootCauseFinding


class RecommendationRepository:
    def create(self, session: Session, recommendation: Recommendation) -> Recommendation:
        session.add(recommendation)
        session.flush()
        return recommendation

    def get(self, session: Session, recommendation_id: UUID, organization_id: UUID) -> Recommendation | None:
        return session.scalar(select(Recommendation).where(
            Recommendation.id == recommendation_id,
            Recommendation.organization_id == organization_id,
        ))

    def list_page(self, session: Session, organization_id: UUID, *, offset: int, limit: int,
                  status: RecommendationStatus | None = None):
        filters = [Recommendation.organization_id == organization_id]
        if status is not None:
            filters.append(Recommendation.status == status)
        query = select(Recommendation).where(*filters).order_by(
            Recommendation.created_at.desc(), Recommendation.id).offset(offset).limit(limit)
        return session.scalars(query).all(), session.scalar(
            select(func.count()).select_from(Recommendation).where(*filters)) or 0

    def finding(self, session: Session, finding_id: UUID, organization_id: UUID) -> RootCauseFinding | None:
        return session.scalar(select(RootCauseFinding).where(
            RootCauseFinding.id == finding_id,
            RootCauseFinding.organization_id == organization_id,
        ))

    def findings_for_analysis(self, session: Session, analysis_id: UUID, organization_id: UUID) -> Sequence[RootCauseFinding]:
        return session.scalars(select(RootCauseFinding).where(
            RootCauseFinding.analysis_id == analysis_id,
            RootCauseFinding.organization_id == organization_id,
        ).order_by(RootCauseFinding.id)).all()

    def for_identity(
        self, session: Session, *, organization_id: UUID, device_id: UUID,
        finding_id: UUID, rule_id: str, fingerprint: str,
    ) -> Recommendation | None:
        return session.scalar(select(Recommendation).where(
            Recommendation.organization_id == organization_id,
            Recommendation.device_id == device_id,
            Recommendation.root_cause_finding_id == finding_id,
            Recommendation.rule_id == rule_id,
            Recommendation.fingerprint == fingerprint,
        ))

    def transition(self, session: Session, recommendation_id: UUID, organization_id: UUID,
                   expected: RecommendationStatus, status: RecommendationStatus, **values) -> bool:
        result = session.execute(update(Recommendation).where(
            Recommendation.id == recommendation_id,
            Recommendation.organization_id == organization_id,
            Recommendation.status == expected,
        ).values(status=status, **values))
        return result.rowcount == 1
