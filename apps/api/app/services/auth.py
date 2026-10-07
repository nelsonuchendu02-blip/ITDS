from datetime import datetime, timezone
from uuid import UUID, uuid4

from pwdlib.exceptions import PwdlibError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..exceptions import SecurityError
from ..models import User, UserSession, UserStatus
from ..repositories import UserRepository, UserSessionRepository
from ..security.passwords import hash_password, verify_dummy_password, verify_password
from ..security.tokens import (
    create_access_token,
    get_access_token_expiration,
)
from .audit import record_security_event


class AuthenticationService:
    def __init__(
        self,
        repository: UserRepository | None = None,
        session_repository: UserSessionRepository | None = None,
    ) -> None:
        self.repository = repository or UserRepository()
        self.session_repository = session_repository or UserSessionRepository()

    def authenticate(
        self,
        session: Session,
        *,
        email: str,
        password: str,
        settings: Settings | None = None,
    ) -> str:
        normalized_email = email.strip().lower()
        matching_users = self.repository.get_by_login(session, normalized_email)
        user = matching_users[0] if len(matching_users) == 1 else None

        try:
            valid_password = (
                verify_password(password, user.password_hash)
                if user is not None and user.password_hash
                else verify_dummy_password(password)
            )
        except (PwdlibError, TypeError, ValueError):
            valid_password = verify_dummy_password(password)

        if user is None or not valid_password or user.status is not UserStatus.ACTIVE:
            record_security_event(
                session,
                event_type="authentication",
                organization_id=user.organization_id if user else None,
                actor_user_id=user.id if user else None,
                action="login",
                result="failure",
                metadata={"reason": "invalid_credentials"},
            )
            self._commit_audit(session)
            raise SecurityError(
                "invalid_credentials",
                "Invalid email or password",
                401,
            )

        configured = settings or get_settings()
        token_id = uuid4()
        issued_at = datetime.now(timezone.utc)
        expires_at = get_access_token_expiration(
            issued_at=issued_at,
            settings=configured,
        )

        try:
            token = create_access_token(
                user.id,
                token_id=token_id,
                issued_at=issued_at,
                expires_at=expires_at,
                settings=configured,
            )

            user_session = UserSession(
                user_id=user.id,
                token_id=token_id,
                expires_at=expires_at,
            )
            self.session_repository.create(session, user_session)

            record_security_event(
                session,
                event_type="authentication",
                organization_id=user.organization_id,
                actor_user_id=user.id,
                action="login",
                result="success",
            )

            session.commit()
            return token

        except (ValueError, SQLAlchemyError) as exc:
            session.rollback()
            raise SecurityError(
                "authentication_unavailable",
                "Authentication is temporarily unavailable",
                503,
            ) from exc

    def change_password(
        self,
        session: Session,
        *,
        user: User,
        current_password: str,
        new_password: str,
    ) -> None:
        if not user.password_hash:
            raise SecurityError(
                "password_change_unavailable",
                "Password change is unavailable for this account",
                409,
            )

        try:
            current_password_valid = verify_password(
                current_password,
                user.password_hash,
            )
        except (PwdlibError, TypeError, ValueError):
            current_password_valid = False

        if not current_password_valid:
            record_security_event(
                session,
                event_type="authentication",
                organization_id=user.organization_id,
                actor_user_id=user.id,
                action="change_password",
                result="failure",
                metadata={"reason": "invalid_current_password"},
            )
            self._commit_audit(session)
            raise SecurityError(
                "invalid_current_password",
                "Current password is incorrect",
                401,
            )

        try:
            password_reused = verify_password(
                new_password,
                user.password_hash,
            )
        except (PwdlibError, TypeError, ValueError):
            password_reused = False

        if password_reused:
            record_security_event(
                session,
                event_type="authentication",
                organization_id=user.organization_id,
                actor_user_id=user.id,
                action="change_password",
                result="failure",
                metadata={"reason": "password_reuse"},
            )
            self._commit_audit(session)
            raise SecurityError(
                "password_reuse",
                "New password must be different from the current password",
                400,
            )

        now = datetime.now(timezone.utc)

        try:
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
                actor_user_id=user.id,
                action="change_password",
                result="success",
            )

            session.commit()

        except (PwdlibError, ValueError, SQLAlchemyError) as exc:
            session.rollback()
            raise SecurityError(
                "password_change_unavailable",
                "Password change is temporarily unavailable",
                503,
            ) from exc
    @staticmethod
    def _commit_audit(session: Session) -> None:
        try:
            session.commit()
        except SQLAlchemyError as exc:
            session.rollback()
            raise SecurityError(
                "authentication_unavailable",
                "Authentication is temporarily unavailable",
                503,
            ) from exc

    def create_user(
        self,
        session: Session,
        *,
        organization_id: UUID,
        email: str,
        display_name: str,
        password_hash: str,
    ) -> User:
        user = User(
            organization_id=organization_id,
            email=email.strip().lower(),
            display_name=display_name,
            password_hash=password_hash,
        )
        try:
            self.repository.create(session, user)
            session.commit()
            return user
        except IntegrityError as exc:
            session.rollback()
            raise SecurityError(
                "user_creation_failed",
                "User could not be created",
                409,
            ) from exc
