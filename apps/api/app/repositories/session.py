from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import UserSession


class UserSessionRepository:
    def create(self, session: Session, user_session: UserSession) -> UserSession:
        session.add(user_session)
        session.flush()
        return user_session

    def get_active_by_token_id(
        self,
        session: Session,
        *,
        token_id: UUID,
        now: datetime,
    ) -> UserSession | None:
        return session.scalar(
            select(UserSession).where(
                UserSession.token_id == token_id,
                UserSession.revoked_at.is_(None),
                UserSession.expires_at > now,
            )
        )

    def revoke_by_token_id(
        self,
        session: Session,
        *,
        token_id: UUID,
        revoked_at: datetime,
    ) -> bool:
        user_session = session.scalar(
            select(UserSession).where(UserSession.token_id == token_id)
        )
        if user_session is None:
            return False

        if user_session.revoked_at is None:
            user_session.revoked_at = revoked_at

        return True

    def revoke_all_by_user_id(
        self,
        session: Session,
        *,
        user_id: UUID,
        revoked_at: datetime,
    ) -> int:
        user_sessions = session.scalars(
            select(UserSession).where(
                UserSession.user_id == user_id,
                UserSession.revoked_at.is_(None),
            )
        ).all()

        for user_session in user_sessions:
            user_session.revoked_at = revoked_at

        return len(user_sessions)
