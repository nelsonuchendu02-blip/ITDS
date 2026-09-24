# Dashboard API integration map

The Phase 1N dashboard consumes existing API resources directly instead of a
custom aggregation endpoint.

## Authentication

- `POST /api/v1/auth/token`
- `GET /api/v1/auth/me`

## Module-to-endpoint mapping

- dashboard summary:
  - `GET /api/v1/monitoring/summary`
  - `GET /api/v1/devices`
  - `GET /api/v1/agents`
  - `GET /api/v1/incidents`
  - `GET /api/v1/discovery/jobs`
  - `GET /api/v1/recommendations`
- devices: `GET /api/v1/devices`
- monitoring:
  - `GET /api/v1/monitoring/targets`
  - `GET /api/v1/monitoring/targets/{target_id}/telemetry`
- agents: `GET /api/v1/agents`
- incidents:
  - `GET /api/v1/incidents`
  - `GET /api/v1/incidents/{incident_id}/escalations`
- discovery:
  - `GET /api/v1/discovery/jobs`
  - `GET /api/v1/discovery/jobs/{job_id}/results`
- diagnostics:
  - `GET /api/v1/diagnostics/runs`
  - `GET /api/v1/diagnostics/runs/{run_id}/results`
- root cause:
  - `GET /api/v1/root-cause/analyses`
  - `GET /api/v1/root-cause/analyses/{analysis_id}/findings`
- recommendations: `GET /api/v1/recommendations`
- remediation: `GET /api/v1/remediation/plans`
- networks:
  - `GET /api/v1/sites`
  - `GET /api/v1/networks`
  - `GET /api/v1/subnets`
  - `GET /api/v1/vlans`
  - `GET /api/v1/ssids`
- audit: `GET /api/v1/audit-events`

## Why no `/api/v1/dashboard/overview` endpoint

Current backend resources already expose the data needed for each module with
appropriate pagination and permission checks. The frontend composes these calls
while preserving server-side authorization boundaries and avoiding redundant API
surface area.
