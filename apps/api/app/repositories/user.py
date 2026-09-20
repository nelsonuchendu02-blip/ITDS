from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..models import User


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
