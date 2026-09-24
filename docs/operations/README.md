# Operations guidance

ITDS now includes a role-aware operations dashboard that consumes live backend
data from `/api/v1/*`. The frontend does not invent mock operational data in
production mode.

## Current guidance

- Validate backend tests with `pytest`.
- Validate frontend with `npm run check`, `npm run test`, and `npm run build`.
- Keep environment-driven configuration (`VITE_API_BASE_URL`, backend settings).
- Preserve server-side permission enforcement; client gating is UX-only.
- Keep endpoint-agent operations read-only and telemetry-centric.

## Operational boundaries

- No frontend-triggered shell execution or OS-modifying actions.
- No secrets in repository files; environment variables only.
- Polling refresh is bounded and interval-driven, not unbounded loops.

## Deferred operations work

- deployment automation
- environment orchestration
- observability pipelines
- production runbooks and on-call escalation playbooks
