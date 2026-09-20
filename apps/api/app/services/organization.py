from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..exceptions import PersistenceError
from ..models import Organization
from ..repositories import OrganizationRepository


class OrganizationService:
    """Coordinate organization persistence and transaction boundaries."""

    def __init__(self, repository: OrganizationRepository | None = None) -> None:
        self.repository = repository or OrganizationRepository()

    def create_organization(self, session: Session, *, name: str) -> Organization:
        try:
            organization = self.repository.create(session, Organization(name=name))
            session.commit()
            return organization
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Organization could not be created") from exc

    def get_organization(self, session: Session, organization_id: UUID) -> Organization | None:
        return self.repository.get_by_id(session, organization_id)

    def list_organizations(self, session: Session) -> Sequence[Organization]:
        return self.repository.list(session)
