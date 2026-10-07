from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.models import UserSession
from app.security.tokens import create_access_token, get_access_token_expiration


def create_test_access_token(session: Session, user_id: UUID) -> str:
    """Create an access token and matching active server-side test session."""
    token_id = uuid4()
    issued_at = datetime.now(timezone.utc)
    expires_at = get_access_token_expiration(issued_at=issued_at)

    token = create_access_token(
        user_id,
        token_id=token_id,
        issued_at=issued_at,
        expires_at=expires_at,
    )

    session.add(
        UserSession(
            user_id=user_id,
            token_id=token_id,
            expires_at=expires_at,
        )
    )
    session.commit()

    return token


