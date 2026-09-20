from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AuditEvent


class AuditRepository:
    def list_page(
        self,
        session: Session,
        organization_id: UUID,
        *,
        offset: int,
        limit: int,
        event_type: str | None = None,
        actor_user_id: UUID | None = None,
    ) -> tuple[Sequence[AuditEvent], int]:
        statement = select(AuditEvent).where(AuditEvent.organization_id == organization_id)
        count_statement = select(func.count()).select_from(AuditEvent).where(
            AuditEvent.organization_id == organization_id
        )
        if event_type:
            statement = statement.where(AuditEvent.event_type == event_type)
            count_statement = count_statement.where(AuditEvent.event_type == event_type)
        if actor_user_id:
            statement = statement.where(AuditEvent.actor_user_id == actor_user_id)
            count_statement = count_statement.where(AuditEvent.actor_user_id == actor_user_id)
        total = session.scalar(count_statement) or 0
        return (
            session.scalars(
                statement.order_by(AuditEvent.created_at.desc(), AuditEvent.id).offset(offset).limit(limit)
            ).all(),
            total,
        )
