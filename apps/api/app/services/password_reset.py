from datetime import datetime, timedelta, timezone

from pwdlib.exceptions import PwdlibError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..exceptions import SecurityError
from ..models import PasswordResetToken
from ..repositories import (
    PasswordResetTokenRepository,
    UserRepository,
    UserSessionRepository,
)
from ..security.passwords import hash_password
from ..security.reset_tokens import (
    extract_prefix,
    hash_reset_token,
    issue_reset_token,
    verify_reset_token,
)
from .audit import record_security_event
from .password_reset_delivery import PasswordResetDelivery


class PasswordResetService:
    """Application service for secure password-reset workflows."""

    def __init__(
        self,
        repository: UserRepository | None = None,
        token_repository: PasswordResetTokenRepository | None = None,
        session_repository: UserSessionRepository | None = None,
        delivery: PasswordResetDelivery | None = None,
    ) -> None:
        self.repository = repository or UserRepository()
        self.token_repository = (
            token_repository or PasswordResetTokenRepository()
        )
        self.session_repository = (
            session_repository or UserSessionRepository()
        )
        self.delivery = delivery

    def request_reset(
        self,
        session: Session,
        *,
        email: str,
        settings: Settings | None = None,
    ) -> None:
        """Create and deliver a password-reset token for an existing account.

        The caller should return the same generic response regardless of
        whether the account exists.
        """
        normalized_email = email.strip().lower()
        matching_users = self.repository.get_by_login(
            session,
            normalized_email,
        )
        user = matching_users[0] if len(matching_users) == 1 else None

        if user is None:
            return None

        now = datetime.now(timezone.utc)

        configured = settings or get_settings()
        ttl_minutes = configured.password_reset_token_ttl_minutes
        expires_at = now + timedelta(minutes=ttl_minutes)

        prefix, raw_token = issue_reset_token()
        token_secret = raw_token.split(".", 1)[1]
        token_hash = hash_reset_token(token_secret)

        try:
            self.token_repository.revoke_active_for_user(
                session,
                user_id=user.id,
                revoked_at=now,
            )

            reset_token = PasswordResetToken(
                user_id=user.id,
                token_prefix=prefix,
                token_hash=token_hash,
                expires_at=expires_at,
            )

            self.token_repository.create(session, reset_token)

            record_security_event(
                session,
                event_type="authentication",
                organization_id=user.organization_id,
                actor_user_id=None,
                action="request_password_reset",
                result="success",
            )

            if self.delivery is not None:
                self.delivery.deliver(
                    email=user.email,
                    reset_token=raw_token,
                )

            session.commit()

        except (PwdlibError, ValueError, SQLAlchemyError) as exc:
            session.rollback()
            raise SecurityError(
                "password_reset_unavailable",
                "Password reset is temporarily unavailable",
                503,
            ) from exc

    def reset_password(
        self,
        session: Session,
        *,
        token: str,
        new_password: str,
    ) -> None:
        """Consume a valid reset token and set a new password."""
        invalid_error = SecurityError(
            "invalid_password_reset",
            "The password reset request is invalid or has expired",
            400,
        )

        prefix = extract_prefix(token)
        if prefix is None:
            raise invalid_error

        token_secret = token.split(".", 1)[1]

        reset_token = self.token_repository.get_by_prefix(
            session,
            token_prefix=prefix,
        )

        if reset_token is None:
            raise invalid_error

        now = datetime.now(timezone.utc)

        expires_at = reset_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if (
            reset_token.used_at is not None
            or reset_token.revoked_at is not None
            or expires_at <= now
        ):
            raise invalid_error

        try:
            valid_token = verify_reset_token(
                token_secret,
                reset_token.token_hash,
            )
        except (PwdlibError, TypeError, ValueError):
            valid_token = False

        if not valid_token:
            raise invalid_error

        user = self.repository.get_by_id(
            session,
            reset_token.user_id,
        )

        if user is None:
            raise invalid_error

        try:
            consumed = self.token_repository.mark_used(
                session,
                token=reset_token,
                used_at=now,
            )

            if not consumed:
                session.rollback()
                raise invalid_error

            user.password_hash = hash_password(new_password)

            self.session_repository.revoke_all_by_user_id(
                session,
                user_id=user.id,
                revoked_at=now,
            )

            record_security_event(
                session,
                event_type="authentication",
                organization_id=user.organization_id,
                actor_user_id=None,
                action="reset_password",
                result="success",
            )

            session.commit()

        except SecurityError:
            raise
        except (PwdlibError, ValueError, SQLAlchemyError) as exc:
            session.rollback()
            raise SecurityError(
                "password_reset_unavailable",
                "Password reset is temporarily unavailable",
                503,
            ) from exc