"""Dedicated authentication for the Windows endpoint agent, separate from
human JWT authentication. Agents authenticate with a bearer-style secret
delivered via the ``X-Agent-Credential`` header; the credential is never
accepted by human-facing endpoints and human tokens are never accepted here.
"""
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...db import get_db
from ...exceptions import SecurityError
from ...models import Agent, AgentCredential, AgentStatus
from ...security.agent_credentials import extract_prefix, verify_secret

_AUTHENTICATABLE_STATUSES = (AgentStatus.PENDING, AgentStatus.ACTIVE, AgentStatus.OFFLINE)


def get_current_agent(
    request: Request,
    credential: Annotated[str | None, Header(alias="X-Agent-Credential")] = None,
    session: Session = Depends(get_db),
) -> Agent:
    if not credential:
        raise SecurityError("agent_authentication_required", "Agent credential is required", 401)
    prefix = extract_prefix(credential)
    if prefix is None:
        raise SecurityError("invalid_agent_credential", "Invalid agent credential", 401)
    row = session.scalar(select(AgentCredential).where(AgentCredential.credential_prefix == prefix))
    now = datetime.now(timezone.utc)
    if (
        row is None
        or row.revoked_at is not None
        or (
            row.expires_at is not None
            and (row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)) <= now
        )
        or not verify_secret(credential, row.credential_hash)
    ):
        raise SecurityError("invalid_agent_credential", "Invalid agent credential", 401)
    agent = session.get(Agent, row.agent_id)
    if agent is None or agent.status not in _AUTHENTICATABLE_STATUSES:
        raise SecurityError("invalid_agent_credential", "Invalid agent credential", 401)
    row.last_used_at = now
    row.last_used_ip = request.client.host if request.client else None
    session.commit()
    return agent


CurrentAgent = Annotated[Agent, Depends(get_current_agent)]
