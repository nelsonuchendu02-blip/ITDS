"""Server-side business logic for Phase 1M secure endpoint agents.

Enrollment tokens and agent credentials are single-use, high-entropy secrets.
Only Argon2 digests are ever persisted; raw values are returned exactly once
at issuance. All lifecycle transitions are audit logged and organization
scoped.
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..exceptions import SecurityError
from ..models import (
    Agent, AgentCredential, AgentEnrollmentToken, AgentStatus, Device, MonitoringTarget, User,
)
from ..schemas.monitoring import TelemetryCreate
from ..security.agent_credentials import extract_prefix, hash_secret, issue_secret, verify_secret
from .audit import record_security_event
from .monitoring import MonitoringService

_ACTIVE_AGENT_STATUSES = (AgentStatus.PENDING, AgentStatus.ACTIVE, AgentStatus.OFFLINE)


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


class AgentService:
    def __init__(self, monitoring: MonitoringService | None = None):
        self.monitoring = monitoring or MonitoringService()

    # ------------------------------------------------------------------
    # Enrollment tokens (human, JWT-authenticated)
    # ------------------------------------------------------------------
    def create_token(self, session: Session, actor: User, expires_in_seconds: int,
                      target_device_id=None):
        if target_device_id is not None:
            device = session.scalar(select(Device).where(
                Device.id == target_device_id, Device.organization_id == actor.organization_id))
            if device is None:
                raise SecurityError("device_not_found", "Device not found", 404)
        prefix, raw = issue_secret()
        token = AgentEnrollmentToken(
            organization_id=actor.organization_id, token_prefix=prefix, token_hash=hash_secret(raw),
            created_by_user_id=actor.id, target_device_id=target_device_id,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
        )
        session.add(token)
        record_security_event(
            session, event_type="agent_enrollment_token_created", organization_id=actor.organization_id,
            actor_user_id=actor.id, action="create", result="success",
            resource_type="agent_enrollment_token", resource_id=str(token.id),
        )
        session.commit()
        session.refresh(token)
        return token, raw

    # ------------------------------------------------------------------
    # Enrollment (unauthenticated aside from the one-time token)
    # ------------------------------------------------------------------
    def enroll(self, session: Session, values: dict):
        now = datetime.now(timezone.utc)
        raw_token = values["token"]
        prefix = extract_prefix(raw_token)
        token = None
        if prefix is not None:
            token = session.scalar(select(AgentEnrollmentToken).where(
                AgentEnrollmentToken.token_prefix == prefix))
        if (
            token is None
            or token.consumed_at is not None
            or token.revoked_at is not None
            or _as_utc(token.expires_at) <= now
            or not verify_secret(raw_token, token.token_hash)
        ):
            raise SecurityError("invalid_enrollment_token", "Invalid or expired enrollment token", 401)

        requested_device_id = values.get("device_id")
        if token.target_device_id is not None:
            if requested_device_id is not None and requested_device_id != token.target_device_id:
                raise SecurityError("device_mismatch", "Device does not match the enrollment token", 409)
            device_id = token.target_device_id
        else:
            device_id = requested_device_id

        device = None if device_id is None else session.scalar(select(Device).where(
            Device.id == device_id, Device.organization_id == token.organization_id))
        if device_id is not None and device is None:
            raise SecurityError("device_not_found", "Device not found", 404)
        if device_id is not None and session.scalar(select(Agent).where(
            Agent.organization_id == token.organization_id, Agent.device_id == device.id
        )) is not None:
            raise SecurityError("agent_exists", "An agent is already enrolled for this device", 409)

        agent = Agent(
            organization_id=token.organization_id, device_id=device.id if device is not None else None,
            agent_name=values["agent_name"],
            agent_version=values.get("agent_version"), platform=values.get("platform", "windows"),
            status=AgentStatus.PENDING,
        )
        credential_prefix, raw_credential = issue_secret()
        credential = AgentCredential(
            agent=agent, organization_id=token.organization_id,
            credential_prefix=credential_prefix, credential_hash=hash_secret(raw_credential),
        )
        # Claim the token atomically after all validation. Only one concurrent
        # enrollment can transition an unconsumed token.
        claimed = session.execute(
            update(AgentEnrollmentToken)
            .where(AgentEnrollmentToken.id == token.id,
                   AgentEnrollmentToken.consumed_at.is_(None),
                   AgentEnrollmentToken.revoked_at.is_(None),
                   AgentEnrollmentToken.expires_at > now)
            .values(consumed_at=now)
            .execution_options(synchronize_session=False)
        ).rowcount
        if claimed != 1:
            session.rollback()
            raise SecurityError("invalid_enrollment_token", "Invalid or expired enrollment token", 401)
        session.add_all([agent, credential])
        record_security_event(
            session, event_type="agent_enrolled", organization_id=token.organization_id, actor_user_id=None,
            action="enroll", result="success", resource_type="agent", resource_id=str(agent.id),
        )
        session.commit()
        session.refresh(agent)
        return agent, raw_credential

    # ------------------------------------------------------------------
    # Heartbeat (agent-credential authenticated; no client-supplied IDs)
    # ------------------------------------------------------------------
    def heartbeat(self, session: Session, agent: Agent, request_ip: str | None, values: dict):
        now = datetime.now(timezone.utc)
        observed = values["observed_at"]
        if observed.tzinfo is None or observed > now:
            raise SecurityError("invalid_timestamp", "Heartbeat timestamp is invalid", 422)
        if agent.status not in _ACTIVE_AGENT_STATUSES:
            raise SecurityError("agent_not_active", "Agent is not eligible to send heartbeats", 409)

        if values.get("agent_version"):
            agent.agent_version = values["agent_version"]
        agent.last_seen_at = observed
        agent.last_ip_address = request_ip
        if agent.status in (AgentStatus.PENDING, AgentStatus.OFFLINE):
            agent.status = AgentStatus.ACTIVE

        device = None
        if agent.device_id is not None:
            device = session.scalar(select(Device).where(
                Device.id == agent.device_id, Device.organization_id == agent.organization_id))
            if device is not None:
                if values.get("hostname"):
                    device.hostname = values["hostname"]
                if values.get("platform"):
                    device.operating_system = values["platform"]
                if values.get("local_ip"):
                    device.ip_address = values["local_ip"]
                device.last_seen_at = observed

        target = session.scalar(select(MonitoringTarget).where(
            MonitoringTarget.organization_id == agent.organization_id,
            MonitoringTarget.device_id == agent.device_id,
        )) if agent.device_id is not None else None
        telemetry = None
        if target is not None and target.enabled:
            telemetry_payload = TelemetryCreate(
                observed_at=observed,
                health_status=values.get("health_status"),
                source="agent",
                details={
                    "agent_id": str(agent.id),
                    "hostname": values.get("hostname"),
                    "platform": values.get("platform"),
                    "local_ip": values.get("local_ip"),
                    "metrics": values.get("metrics", {}),
                },
            ).model_dump()
            telemetry = self.monitoring.ingest_for_agent(
                session, target, agent.organization_id, telemetry_payload)

        session.commit()
        session.refresh(agent)
        return agent, telemetry

    # ------------------------------------------------------------------
    # Management (human, JWT-authenticated)
    # ------------------------------------------------------------------
    @staticmethod
    def _scope(agent: Agent, actor: User):
        if agent.organization_id != actor.organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)

    def update(self, session: Session, agent: Agent, actor: User, values: dict):
        self._scope(agent, actor)
        for key, value in values.items():
            setattr(agent, key, value)
        record_security_event(
            session, event_type="agent_updated", organization_id=actor.organization_id, actor_user_id=actor.id,
            action="update", result="success", resource_type="agent", resource_id=str(agent.id),
        )
        session.commit()
        session.refresh(agent)
        return agent

    def revoke(self, session: Session, agent: Agent, actor: User):
        self._scope(agent, actor)
        now = datetime.now(timezone.utc)
        agent.status = AgentStatus.REVOKED
        for credential in agent.credentials:
            if credential.revoked_at is None:
                credential.revoked_at = now
        record_security_event(
            session, event_type="agent_revoked", organization_id=actor.organization_id, actor_user_id=actor.id,
            action="revoke", result="success", resource_type="agent", resource_id=str(agent.id),
        )
        session.commit()
        session.refresh(agent)
        return agent

    def retire(self, session: Session, agent: Agent, actor: User):
        self._scope(agent, actor)
        now = datetime.now(timezone.utc)
        agent.status = AgentStatus.RETIRED
        for credential in agent.credentials:
            if credential.revoked_at is None:
                credential.revoked_at = now
        record_security_event(
            session, event_type="agent_retired", organization_id=actor.organization_id, actor_user_id=actor.id,
            action="retire", result="success", resource_type="agent", resource_id=str(agent.id),
        )
        session.commit()
        session.refresh(agent)
        return agent

    def rotate_credential(self, session: Session, agent: Agent, actor: User):
        self._scope(agent, actor)
        if agent.status in (AgentStatus.REVOKED, AgentStatus.RETIRED):
            raise SecurityError("agent_not_active", "Agent is not eligible for credential rotation", 409)
        now = datetime.now(timezone.utc)
        for credential in agent.credentials:
            if credential.revoked_at is None:
                credential.revoked_at = now
        prefix, raw = issue_secret()
        session.add(AgentCredential(
            agent_id=agent.id, organization_id=agent.organization_id,
            credential_prefix=prefix, credential_hash=hash_secret(raw),
        ))
        record_security_event(
            session, event_type="agent_credential_rotated", organization_id=actor.organization_id,
            actor_user_id=actor.id, action="rotate", result="success",
            resource_type="agent", resource_id=str(agent.id),
        )
        session.commit()
        return raw
