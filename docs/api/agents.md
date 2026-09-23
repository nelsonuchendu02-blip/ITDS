# Phase 1M endpoint agents

All routes are under `/api/v1/agents`.

Organization administrators create a short-lived one-time enrollment token with
`POST /api/v1/agents/enrollment-tokens`. The raw token is returned once and is
never stored; only an Argon2 digest is persisted. An endpoint calls
`POST /api/v1/agents/enroll` with the token. A token may target a device, may
accept a caller-supplied device, or may leave the agent unbound.
The response contains a credential once; the server stores only its digest.

Agents authenticate with `X-Agent-Credential` and send
`POST /api/v1/agents/heartbeat`; organization and device are always derived
from the credential. Human management routes are `GET /agents`, `GET /agents/{id}`,
`PATCH /agents/{id}`, `POST /agents/{id}/revoke`, `POST /agents/{id}/retire`,
and `POST /agents/{id}/credentials/rotate`. All management routes require one
of `agents:read`, `agents:create`, `agents:manage`, or `agents:rotate`.

The agent package is deliberately read-only and stdlib-only: no shell,
PowerShell, WMI, SSH, scanning, repair, or service installation is implemented.
