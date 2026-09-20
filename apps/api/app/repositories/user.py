from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from ..models import Role, User


class UserRepository:
    def get_by_id(self, session: Session, user_id: UUID) -> User | None:
        return session.execute(
            select(User).options(joinedload(User.roles)).where(User.id == user_id)
        ).unique().scalar_one_or_none()

    def get_by_email(self, session: Session, organization_id: UUID, email: str) -> User | None:
        return session.execute(
            select(User)
            .options(joinedload(User.roles))
            .where(User.organization_id == organization_id, User.email == email)
        ).unique().scalar_one_or_none()

    def get_by_login(self, session: Session, email: str) -> list[User]:
        return session.execute(
            select(User).options(joinedload(User.roles)).where(User.email == email)
        ).unique().scalars().all()

    def create(self, session: Session, user: User) -> User:
        session.add(user)
        session.flush()
        return user

    def list_by_organization(self, session: Session, organization_id: UUID) -> Sequence[User]:
        return session.scalars(
            select(User).where(User.organization_id == organization_id).order_by(User.email)
        ).all()

    def list_page(
        self,
        session: Session,
        organization_id: UUID,
        *,
        offset: int,
        limit: int,
        search: str | None = None,
        status: str | None = None,
        role_name: str | None = None,
    ) -> tuple[list[User], int]:
        statement = select(User).where(User.organization_id == organization_id)
        count_statement = select(func.count()).select_from(User).where(User.organization_id == organization_id)
        if search:
            pattern = f"%{search.strip().lower()}%"
            statement = statement.where(
                func.lower(User.email).like(pattern) | func.lower(User.display_name).like(pattern)
            )
            count_statement = count_statement.where(
                func.lower(User.email).like(pattern) | func.lower(User.display_name).like(pattern)
            )
        if status:
            statement = statement.where(User.status == status)
            count_statement = count_statement.where(User.status == status)
        if role_name:
            statement = statement.join(User.roles).where(Role.name == role_name)
            count_statement = count_statement.join(User.roles).where(Role.name == role_name)
        total = session.scalar(count_statement) or 0
        users = session.scalars(
            statement.order_by(User.email, User.id).offset(offset).limit(limit)
        ).all()
        return users, total
