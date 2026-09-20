from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Organization


class OrganizationRepository:
    """Persistence operations for organizations."""

    def create(self, session: Session, organization: Organization) -> Organization:
        session.add(organization)
        session.flush()
        return organization

    def get_by_id(self, session: Session, organization_id: UUID) -> Organization | None:
        return session.get(Organization, organization_id)

    def list(self, session: Session) -> Sequence[Organization]:
        return session.scalars(select(Organization).order_by(Organization.name)).all()
