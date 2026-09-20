from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from ..models import AuditEvent


def record_security_event(
    session: Session,
    *,
    event_type: str,
    organization_id: UUID | None,
    actor_user_id: UUID | None,
    action: str,
    result: str,
    metadata: dict | None = None,
) -> None:
    session.add(
        AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            event_type=event_type,
            resource_type="authentication",
            action=action,
            result=result,
            event_metadata=metadata,
            created_at=datetime.now(timezone.utc),
        )
    )
