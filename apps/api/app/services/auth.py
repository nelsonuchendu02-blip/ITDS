from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from pwdlib.exceptions import PwdlibError

from ..config import Settings
from ..exceptions import SecurityError
from ..models import User, UserStatus
from ..repositories import UserRepository
from ..security.passwords import verify_dummy_password, verify_password
from ..security.tokens import create_access_token
from .audit import record_security_event


class AuthenticationService:
    def __init__(self, repository: UserRepository | None = None) -> None:
        self.repository = repository or UserRepository()

    def authenticate(self, session: Session, *, email: str, password: str, settings: Settings | None = None) -> str:
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
            raise SecurityError("invalid_credentials", "Invalid email or password", 401)
        try:
            token = create_access_token(user.id, settings)
        except ValueError as exc:
            raise SecurityError(
                "authentication_unavailable",
                "Authentication is temporarily unavailable",
                503,
            ) from exc
        record_security_event(
            session,
            event_type="authentication",
            organization_id=user.organization_id,
            actor_user_id=user.id,
            action="login",
            result="success",
        )
        self._commit_audit(session)
        return token

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
            raise SecurityError("user_creation_failed", "User could not be created", 409) from exc
