from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Role


class RoleRepository:
    def get_by_name(self, session: Session, organization_id: UUID, name: str) -> Role | None:
        return session.scalar(
            select(Role).where(Role.organization_id == organization_id, Role.name == name)
        )

    def list_by_organization(self, session: Session, organization_id: UUID) -> Sequence[Role]:
        return session.scalars(
            select(Role).where(Role.organization_id == organization_id).order_by(Role.name)
        ).all()
