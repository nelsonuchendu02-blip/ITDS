from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..exceptions import SecurityError
from ..models import Escalation, EscalationStatus, Incident, IncidentStatus, User
from .audit import record_security_event


class IncidentService:
    @staticmethod
    def _ensure_actor(session: Session, actor: User) -> None:
        if session.scalar(select(User).where(
            User.id == actor.id, User.organization_id == actor.organization_id
        )) is None:
            raise SecurityError("permission_denied", "Actor is not in this organization", 403)

    @staticmethod
    def _ensure_scope(incident: Incident, actor: User) -> None:
        if incident.organization_id != actor.organization_id:
            raise SecurityError("incident_not_found", "Incident not found", 404)

    def get(self, session: Session, incident_id: UUID, organization_id: UUID) -> Incident | None:
        return session.scalar(select(Incident).where(
            Incident.id == incident_id, Incident.organization_id == organization_id))

    def list(self, session: Session, organization_id: UUID, *, offset: int, limit: int):
        statement = select(Incident).where(Incident.organization_id == organization_id).order_by(
            Incident.opened_at.desc(), Incident.id).offset(offset).limit(limit)
        items = list(session.scalars(statement))
        total = session.scalar(select(func.count()).select_from(Incident).where(
            Incident.organization_id == organization_id)) or 0
        return items, total

    def _user(self, session, user_id, organization_id):
        if user_id is None:
            return None
        user = session.scalar(select(User).where(User.id == user_id, User.organization_id == organization_id))
        if user is None:
            raise SecurityError("invalid_assignee", "Assigned user is not in this organization", 422)
        return user

    def create(self, session: Session, *, actor: User, title: str, description=None,
               severity=None, priority=None, device_id=None, assigned_user_id=None) -> Incident:
        from ..models import Device
        self._ensure_actor(session, actor)
        if device_id is not None and session.scalar(select(Device).where(
                Device.id == device_id, Device.organization_id == actor.organization_id)) is None:
            raise SecurityError("invalid_device", "Device is not in this organization", 422)
        self._user(session, assigned_user_id, actor.organization_id)
        incident = Incident(organization_id=actor.organization_id, title=title, description=description,
                            severity=severity, priority=priority, device_id=device_id,
                            assigned_user_id=assigned_user_id, created_by_user_id=actor.id,
                            opened_at=datetime.now(timezone.utc))
        session.add(incident)
        try:
            session.flush()
            record_security_event(session, event_type="incident_created", organization_id=actor.organization_id,
                                  actor_user_id=actor.id, action="create", result="success",
                                  resource_type="incident", resource_id=str(incident.id))
            session.commit()
        except IntegrityError:
            session.rollback()
            raise SecurityError("incident_create_failed", "Incident could not be created", 409) from None
        session.refresh(incident)
        return incident

    def start(self, session, incident: Incident, *, actor: User) -> Incident:
        self._ensure_actor(session, actor)
        self._ensure_scope(incident, actor)
        if incident.status is not IncidentStatus.OPEN:
            raise SecurityError("invalid_incident_transition", "Only open incidents can be started", 409)
        incident.status = IncidentStatus.IN_PROGRESS
        self._audit_incident(session, incident, actor, "incident_started")
        session.commit()
        session.refresh(incident)
        return incident

    def resolve(self, session, incident: Incident, *, actor: User, resolution_summary: str) -> Incident:
        self._ensure_actor(session, actor)
        self._ensure_scope(incident, actor)
        if incident.status is not IncidentStatus.IN_PROGRESS:
            raise SecurityError("invalid_incident_transition", "Only in-progress incidents can be resolved", 409)
        incident.status = IncidentStatus.RESOLVED
        incident.resolved_at = datetime.now(timezone.utc)
        incident.resolved_by_user_id = actor.id
        incident.resolution_summary = resolution_summary
        self._audit_incident(session, incident, actor, "incident_resolved")
        session.commit()
        session.refresh(incident)
        return incident

    def close(self, session, incident: Incident, *, actor: User, resolution_summary: str | None = None) -> Incident:
        self._ensure_actor(session, actor)
        self._ensure_scope(incident, actor)
        if incident.status is not IncidentStatus.RESOLVED:
            raise SecurityError("invalid_incident_transition", "Only resolved incidents can be closed", 409)
        if resolution_summary is not None:
            incident.resolution_summary = resolution_summary
        if not incident.resolution_summary:
            raise SecurityError("resolution_summary_required", "A resolution summary is required", 422)
        incident.status = IncidentStatus.CLOSED
        incident.closed_at = datetime.now(timezone.utc)
        incident.closed_by_user_id = actor.id
        self._audit_incident(session, incident, actor, "incident_closed")
        session.commit()
        session.refresh(incident)
        return incident

    def assign(self, session, incident: Incident, *, actor: User, assigned_user_id: UUID) -> Incident:
        self._ensure_actor(session, actor)
        self._ensure_scope(incident, actor)
        self._user(session, assigned_user_id, actor.organization_id)
        incident.assigned_user_id = assigned_user_id
        self._audit_incident(session, incident, actor, "incident_assigned")
        session.commit()
        session.refresh(incident)
        return incident

    @staticmethod
    def _audit_incident(session, incident, actor, event_type):
        record_security_event(session, event_type=event_type, organization_id=actor.organization_id,
                              actor_user_id=actor.id, action=event_type.removeprefix("incident_"),
                              result="success", resource_type="incident", resource_id=str(incident.id))

    def update(self, session: Session, incident: Incident, *, actor: User, **changes) -> Incident:
        self._ensure_actor(session, actor)
        self._ensure_scope(incident, actor)
        if changes.get("assigned_user_id") is not None:
            self._user(session, changes["assigned_user_id"], actor.organization_id)
        target = changes.get("status")
        if target is not None:
            raise SecurityError("explicit_transition_required", "Use the incident lifecycle endpoint", 422)
        if target is IncidentStatus.RESOLVED and incident.status not in (
                IncidentStatus.OPEN, IncidentStatus.IN_PROGRESS):
            raise SecurityError("invalid_incident_transition", "Incident cannot be resolved from its current state", 409)
        if target is IncidentStatus.CLOSED and incident.status is not IncidentStatus.RESOLVED:
            raise SecurityError("invalid_incident_transition", "Incident must be resolved before closing", 409)
        for key, value in changes.items():
            if value is not None:
                setattr(incident, key, value)
        if target is IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.now(timezone.utc)
        if target is IncidentStatus.CLOSED and incident.resolved_at is None:
            incident.resolved_at = datetime.now(timezone.utc)
        record_security_event(session, event_type="incident_updated", organization_id=actor.organization_id,
                              actor_user_id=actor.id, action="update", result="success",
                              resource_type="incident", resource_id=str(incident.id),
                              metadata={"status": target.value if target else None})
        session.commit()
        session.refresh(incident)
        return incident

    def escalations(self, session, incident):
        return list(session.scalars(select(Escalation).where(
            Escalation.incident_id == incident.id, Escalation.organization_id == incident.organization_id
        ).order_by(Escalation.escalation_level)))

    def escalate(self, session, incident: Incident, *, actor: User, escalation_level: int,
                 reason: str, assigned_to: str | None = None) -> Escalation:
        self._ensure_actor(session, actor)
        self._ensure_scope(incident, actor)
        if incident.status is IncidentStatus.CLOSED:
            raise SecurityError("incident_closed", "Closed incidents cannot be escalated", 409)
        escalation = Escalation(organization_id=actor.organization_id, incident_id=incident.id,
                                escalation_level=escalation_level, reason=reason, assigned_to=assigned_to,
                                escalated_at=datetime.now(timezone.utc))
        session.add(escalation)
        incident.last_escalated_at = escalation.escalated_at
        try:
            session.flush()
            record_security_event(session, event_type="escalation_created", organization_id=actor.organization_id,
                                  actor_user_id=actor.id, action="escalate", result="success",
                                  resource_type="escalation", resource_id=str(escalation.id))
            session.commit()
        except IntegrityError:
            session.rollback()
            raise SecurityError("duplicate_escalation", "Escalation level already exists for this incident", 409) from None
        session.refresh(escalation)
        return escalation

    def transition_escalation(self, session, escalation: Escalation, *, actor: User,
                               target: EscalationStatus) -> Escalation:
        self._ensure_actor(session, actor)
        if escalation.organization_id != actor.organization_id:
            raise SecurityError("escalation_not_found", "Escalation not found", 404)
        if session.scalar(select(Incident).where(
            Incident.id == escalation.incident_id,
            Incident.organization_id == actor.organization_id,
        )) is None:
            raise SecurityError("escalation_not_found", "Escalation not found", 404)
        allowed = {
            EscalationStatus.ACKNOWLEDGED: {EscalationStatus.OPEN},
            EscalationStatus.RESOLVED: {EscalationStatus.ACKNOWLEDGED},
        }
        if escalation.status not in allowed.get(target, set()):
            raise SecurityError("invalid_escalation_transition", "Invalid escalation lifecycle transition", 409)
        escalation.status = target
        if target is EscalationStatus.RESOLVED:
            escalation.resolved_at = datetime.now(timezone.utc)
        record_security_event(session, event_type=f"escalation_{target.value}",
                              organization_id=actor.organization_id, actor_user_id=actor.id,
                              action=target.value, result="success", resource_type="escalation",
                              resource_id=str(escalation.id))
        session.commit()
        session.refresh(escalation)
        return escalation
