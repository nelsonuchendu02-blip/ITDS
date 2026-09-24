"""Phase 1M secure endpoint agent management, enrollment, and heartbeat API.

Human endpoints (enrollment-token issuance, listing, updates, revoke, retire,
and human-triggered credential rotation) require a JWT-authenticated user with
the relevant ``agents:*`` permission and never accept agent credentials.
Agent endpoints (``/enroll`` and ``/heartbeat``) never accept human JWTs;
``/enroll`` is authenticated solely by a one-time enrollment token and
``/heartbeat`` is authenticated solely by the agent's own credential, deriving
its organization and device entirely from that credential.
"""
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ....db import get_db
from ....exceptions import SecurityError
from ....models import Agent, User
from ....schemas import (
    AgentEnroll, AgentEnrollmentResponse, AgentHeartbeat, AgentRead, AgentRotateResponse,
    AgentUpdate, EnrollmentTokenCreate, EnrollmentTokenRead,
)
from ....services.agent import AgentService
from ...dependencies.agent_auth import CurrentAgent
from ...dependencies.auth import require_permission

router = APIRouter(prefix="/agents", tags=["agents"])


def _service() -> AgentService:
    return AgentService()


def _get_agent(session: Session, organization_id: UUID, agent_id: UUID) -> Agent:
    agent = session.scalar(select(Agent).where(Agent.id == agent_id, Agent.organization_id == organization_id))
    if agent is None:
        raise SecurityError("agent_not_found", "Agent not found", 404)
    return agent


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# ----------------------------------------------------------------------
# Human-authenticated management endpoints. Static paths are registered
# before the "/{agent_id}" routes so they cannot be shadowed.
# ----------------------------------------------------------------------
@router.post("/enrollment-tokens", response_model=EnrollmentTokenRead, status_code=201)
def create_enrollment_token(
    payload: EnrollmentTokenCreate,
    user: Annotated[User, Depends(require_permission("agents:create"))],
    session: Session = Depends(get_db),
):
    token, raw = _service().create_token(session, user, payload.expires_in_seconds, payload.target_device_id)
    return {
        "id": token.id, "organization_id": token.organization_id, "token": raw,
        "token_prefix": token.token_prefix, "target_device_id": token.target_device_id,
        "expires_at": token.expires_at,
    }


@router.get("", response_model=list[AgentRead])
def list_agents(
    user: Annotated[User, Depends(require_permission("agents:read"))],
    session: Session = Depends(get_db),
):
    return session.scalars(
        select(Agent).where(Agent.organization_id == user.organization_id).order_by(Agent.created_at.desc())
    ).all()


@router.get("/{agent_id}", response_model=AgentRead)
def get_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(require_permission("agents:read"))],
    session: Session = Depends(get_db),
):
    return _get_agent(session, user.organization_id, agent_id)


@router.patch("/{agent_id}", response_model=AgentRead)
def update_agent(
    agent_id: UUID,
    payload: AgentUpdate,
    user: Annotated[User, Depends(require_permission("agents:manage"))],
    session: Session = Depends(get_db),
):
    agent = _get_agent(session, user.organization_id, agent_id)
    return _service().update(session, agent, user, payload.model_dump(exclude_unset=True))


@router.post("/{agent_id}/revoke", response_model=AgentRead)
def revoke_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(require_permission("agents:manage"))],
    session: Session = Depends(get_db),
):
    agent = _get_agent(session, user.organization_id, agent_id)
    return _service().revoke(session, agent, user)


@router.post("/{agent_id}/retire", response_model=AgentRead)
def retire_agent(
    agent_id: UUID,
    user: Annotated[User, Depends(require_permission("agents:manage"))],
    session: Session = Depends(get_db),
):
    agent = _get_agent(session, user.organization_id, agent_id)
    return _service().retire(session, agent, user)


@router.post("/{agent_id}/credentials/rotate", response_model=AgentRotateResponse)
def rotate_agent_credential(
    agent_id: UUID,
    user: Annotated[User, Depends(require_permission("agents:rotate"))],
    session: Session = Depends(get_db),
):
    agent = _get_agent(session, user.organization_id, agent_id)
    credential = _service().rotate_credential(session, agent, user)
    return {"credential": credential, "expires_at": None}


# ----------------------------------------------------------------------
# Agent-authenticated (or one-time-token authenticated) endpoints.
# ----------------------------------------------------------------------
@router.post("/enroll", response_model=AgentEnrollmentResponse, status_code=201)
def enroll(payload: AgentEnroll, session: Session = Depends(get_db)):
    agent, credential = _service().enroll(session, payload.model_dump())
    return {"agent": agent, "credential": credential}


@router.post("/heartbeat", response_model=AgentRead)
def heartbeat(
    payload: AgentHeartbeat,
    request: Request,
    agent: CurrentAgent,
    session: Session = Depends(get_db),
):
    agent, _telemetry = _service().heartbeat(session, agent, _client_ip(request), payload.model_dump())
    return agent
