from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...dependencies.auth import get_incident_service, require_permission
from ....db import get_db
from ....exceptions import SecurityError
from ....models import Escalation, EscalationStatus, User
from ....schemas import (
    IncidentAssignment, IncidentCreate, IncidentResolution, IncidentUpdate, IncidentRead,
    IncidentPage, EscalationCreate, EscalationRead,
)
from ....services.incident import IncidentService

router = APIRouter(prefix="/incidents", tags=["incidents"])
Service = Annotated[IncidentService, Depends(get_incident_service)]


def missing() -> SecurityError:
    return SecurityError("incident_not_found", "Incident not found", 404)


@router.post("", response_model=IncidentRead, status_code=201)
def create(payload: IncidentCreate, user: Annotated[User, Depends(require_permission("incidents:create"))],
           service: Service, session: Session = Depends(get_db)):
    return service.create(session, actor=user, **payload.model_dump())


@router.get("", response_model=IncidentPage)
def list_incidents(user: Annotated[User, Depends(require_permission("incidents:read"))],
                   service: Service, session: Session = Depends(get_db),
                   page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100)):
    items, total = service.list(session, user.organization_id, offset=(page - 1) * page_size, limit=page_size)
    return IncidentPage(items=items, total=total, page=page, page_size=page_size)


@router.get("/{incident_id}", response_model=IncidentRead)
def get(incident_id: UUID, user: Annotated[User, Depends(require_permission("incidents:read"))],
        service: Service, session: Session = Depends(get_db)):
    incident = service.get(session, incident_id, user.organization_id)
    if incident is None:
        raise missing()
    return incident


@router.patch("/{incident_id}", response_model=IncidentRead)
def update(incident_id: UUID, payload: IncidentUpdate,
           user: Annotated[User, Depends(require_permission("incidents:manage"))],
           service: Service, session: Session = Depends(get_db)):
    incident = service.get(session, incident_id, user.organization_id)
    if incident is None:
        raise missing()
    return service.update(session, incident, actor=user, **payload.model_dump(exclude_unset=True))


@router.post("/{incident_id}/start", response_model=IncidentRead)
def start(incident_id: UUID, user: Annotated[User, Depends(require_permission("incidents:manage"))],
          service: Service, session: Session = Depends(get_db)):
    incident = service.get(session, incident_id, user.organization_id)
    if incident is None:
        raise missing()
    return service.start(session, incident, actor=user)


@router.post("/{incident_id}/resolve", response_model=IncidentRead)
def resolve_incident(incident_id: UUID, payload: IncidentResolution,
                     user: Annotated[User, Depends(require_permission("incidents:resolve"))],
                     service: Service, session: Session = Depends(get_db)):
    incident = service.get(session, incident_id, user.organization_id)
    if incident is None:
        raise missing()
    return service.resolve(session, incident, actor=user, **payload.model_dump())


@router.post("/{incident_id}/close", response_model=IncidentRead)
def close_incident(incident_id: UUID,
                   user: Annotated[User, Depends(require_permission("incidents:close"))],
                   service: Service, session: Session = Depends(get_db),
                   payload: IncidentResolution | None = None):
    incident = service.get(session, incident_id, user.organization_id)
    if incident is None:
        raise missing()
    return service.close(session, incident, actor=user,
                         resolution_summary=payload.resolution_summary if payload else None)


@router.post("/{incident_id}/assign", response_model=IncidentRead)
def assign(incident_id: UUID, payload: IncidentAssignment,
           user: Annotated[User, Depends(require_permission("incidents:assign"))],
           service: Service, session: Session = Depends(get_db)):
    incident = service.get(session, incident_id, user.organization_id)
    if incident is None:
        raise missing()
    return service.assign(session, incident, actor=user, **payload.model_dump())


@router.post("/{incident_id}/escalations", response_model=EscalationRead, status_code=201)
def escalate(incident_id: UUID, payload: EscalationCreate,
             user: Annotated[User, Depends(require_permission("escalations:create"))],
             service: Service, session: Session = Depends(get_db)):
    incident = service.get(session, incident_id, user.organization_id)
    if incident is None:
        raise missing()
    return service.escalate(session, incident, actor=user, **payload.model_dump())


@router.get("/{incident_id}/escalations", response_model=list[EscalationRead])
def list_escalations(incident_id: UUID, user: Annotated[User, Depends(require_permission("escalations:read"))],
                     service: Service, session: Session = Depends(get_db)):
    incident = service.get(session, incident_id, user.organization_id)
    if incident is None:
        raise missing()
    return service.escalations(session, incident)


@router.post("/{incident_id}/escalations/{escalation_id}/acknowledge", response_model=EscalationRead)
def acknowledge(incident_id: UUID, escalation_id: UUID,
                user: Annotated[User, Depends(require_permission("escalations:manage"))],
                service: Service, session: Session = Depends(get_db)):
    return _transition(incident_id, escalation_id, user, service, session, EscalationStatus.ACKNOWLEDGED)


@router.post("/{incident_id}/escalations/{escalation_id}/resolve", response_model=EscalationRead)
def resolve(incident_id: UUID, escalation_id: UUID,
            user: Annotated[User, Depends(require_permission("escalations:resolve"))],
            service: Service, session: Session = Depends(get_db)):
    return _transition(incident_id, escalation_id, user, service, session, EscalationStatus.RESOLVED)


def _transition(incident_id, escalation_id, user, service, session, target):
    incident = service.get(session, incident_id, user.organization_id)
    escalation = session.scalar(select(Escalation).where(
        Escalation.id == escalation_id, Escalation.incident_id == incident_id,
        Escalation.organization_id == user.organization_id))
    if incident is None or escalation is None:
        raise SecurityError("escalation_not_found", "Escalation not found", 404)
    return service.transition_escalation(session, escalation, actor=user, target=target)
