from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..exceptions import PersistenceError, SecurityError
from ..models import Organization, Role, User, UserStatus
from ..repositories import AuditRepository, OrganizationRepository, RoleRepository, UserRepository
from ..security.passwords import hash_password
from .audit import record_security_event


class ManagementService:
    def __init__(
        self,
        organization_repository: OrganizationRepository | None = None,
        user_repository: UserRepository | None = None,
        role_repository: RoleRepository | None = None,
        audit_repository: AuditRepository | None = None,
    ) -> None:
        self.organizations = organization_repository or OrganizationRepository()
        self.users = user_repository or UserRepository()
        self.roles = role_repository or RoleRepository()
        self.audit = audit_repository or AuditRepository()

    def get_organization(self, session: Session, organization_id: UUID) -> Organization | None:
        return self.organizations.get_by_id(session, organization_id)

    def update_organization(
        self, session: Session, *, organization: Organization, name: str, actor: User
    ) -> Organization:
        self.organizations.update_name(organization, name.strip())
        record_security_event(
            session,
            event_type="organization_updated",
            organization_id=organization.id,
            actor_user_id=actor.id,
            action="update",
            result="success",
            metadata={"target_organization_id": str(organization.id)},
            resource_type="organization",
            resource_id=str(organization.id),
        )
        self._commit(session)
        return organization

    def list_users(
        self, session: Session, organization_id: UUID, *, offset: int, limit: int,
        search: str | None = None, status: str | None = None, role: str | None = None
    ) -> tuple[list[User], int]:
        return self.users.list_page(
            session, organization_id, offset=offset, limit=limit,
            search=search, status=status, role_name=role,
        )

    def get_user(self, session: Session, organization_id: UUID, user_id: UUID) -> User | None:
        user = self.users.get_by_id(session, user_id)
        return user if user and user.organization_id == organization_id else None

    def create_user(
        self, session: Session, *, organization_id: UUID, email: str, display_name: str,
        password: str, actor: User
    ) -> User:
        user = User(
            organization_id=organization_id,
            email=email.strip().lower(),
            display_name=display_name,
            password_hash=hash_password(password),
        )
        try:
            session.add(user)
            session.flush()
            record_security_event(
                session, event_type="user_created", organization_id=organization_id,
                actor_user_id=actor.id, action="create", result="success",
                metadata={"target_user_id": str(user.id)}, resource_type="user",
                resource_id=str(user.id),
            )
            self._commit(session)
            return user
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("User could not be created") from exc

    def update_user(
        self, session: Session, *, user: User, actor: User, email: str | None = None,
        display_name: str | None = None
    ) -> User:
        if email is not None:
            user.email = email.strip().lower()
        if display_name is not None:
            user.display_name = display_name
        record_security_event(
            session, event_type="user_updated", organization_id=user.organization_id,
            actor_user_id=actor.id, action="update", result="success",
            metadata={"target_user_id": str(user.id)}, resource_type="user",
            resource_id=str(user.id),
        )
        self._commit(session)
        return user

    def set_user_status(self, session: Session, *, user: User, actor: User, status: UserStatus) -> User:
        user.status = status
        record_security_event(
            session,
            event_type="user_activated" if status is UserStatus.ACTIVE else "user_deactivated",
            organization_id=user.organization_id,
            actor_user_id=actor.id,
            action="status_change",
            result="success",
            metadata={"target_user_id": str(user.id), "status": status.value},
            resource_type="user",
            resource_id=str(user.id),
        )
        self._commit(session)
        return user

    def list_roles(self, session: Session, organization_id: UUID) -> Sequence[Role]:
        return self.roles.list_by_organization(session, organization_id)

    def assign_role(self, session: Session, *, user: User, role: Role, actor: User) -> User:
        if role.name == "platform_admin":
            raise SecurityError("permission_denied", "Permission denied", 403)
        if role not in user.roles:
            user.roles.append(role)
        record_security_event(
            session, event_type="role_assigned", organization_id=user.organization_id,
            actor_user_id=actor.id, action="assign", result="success",
            metadata={"target_user_id": str(user.id), "role": role.name},
            resource_type="role", resource_id=str(role.id),
        )
        self._commit(session)
        return user

    def remove_role(self, session: Session, *, user: User, role: Role, actor: User) -> User:
        if role not in user.roles:
            raise PersistenceError("Role is not assigned", status_code=404)
        if role.name == "platform_admin" and user.id == actor.id:
            raise SecurityError("permission_denied", "Permission denied", 403)
        user.roles.remove(role)
        record_security_event(
            session, event_type="role_removed", organization_id=user.organization_id,
            actor_user_id=actor.id, action="remove", result="success",
            metadata={"target_user_id": str(user.id), "role": role.name},
            resource_type="role", resource_id=str(role.id),
        )
        self._commit(session)
        return user

    def list_audit_events(
        self, session: Session, organization_id: UUID, *, offset: int, limit: int,
        event_type: str | None = None, actor_user_id: UUID | None = None
    ):
        return self.audit.list_page(
            session, organization_id, offset=offset, limit=limit,
            event_type=event_type, actor_user_id=actor_user_id,
        )

    @staticmethod
    def _commit(session: Session) -> None:
        try:
            session.commit()
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Management operation could not be completed") from exc
