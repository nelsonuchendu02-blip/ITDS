from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models import PasswordResetToken


class PasswordResetTokenRepository:
    """Database operations for password-reset tokens."""

    def create(
        self,
        session: Session,
        token: PasswordResetToken,
    ) -> PasswordResetToken:
        session.add(token)
        session.flush()
        return token

    def get_by_prefix(
        self,
        session: Session,
        *,
        token_prefix: str,
    ) -> PasswordResetToken | None:
        return session.scalar(
            select(PasswordResetToken).where(
                PasswordResetToken.token_prefix == token_prefix,
            )
        )

    def revoke_active_for_user(
        self,
        session: Session,
        *,
        user_id: UUID,
        revoked_at: datetime,
    ) -> int:
        result = session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.user_id == user_id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.revoked_at.is_(None),
            )
            .values(revoked_at=revoked_at)
        )
        return result.rowcount or 0

    def mark_used(
        self,
        session: Session,
        *,
        token: PasswordResetToken,
        used_at: datetime,
    ) -> bool:
        result = session.execute(
            update(PasswordResetToken)
            .where(
                PasswordResetToken.id == token.id,
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.revoked_at.is_(None),
            )
            .values(used_at=used_at)
        )
        return result.rowcount == 1