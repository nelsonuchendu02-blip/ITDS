# Dashboard API integration map

The Phase 1N dashboard combines one aggregation endpoint for organization-wide
KPIs with the existing per-module resources for detailed tables and activity.

## Authentication

- `POST /api/v1/auth/token`
- `GET /api/v1/auth/me`

## `GET /api/v1/dashboard/overview`

Returns organization-scoped, permission-aware aggregate KPIs that the
paginated module APIs cannot answer accurately or efficiently from a single
page of results (for example: total open incidents across the whole
organization, not just the first page).

- **Auth:** required (`get_current_user`); any authenticated user may call
  this endpoint.
- **Scope:** results are always scoped to the caller's `organization_id`.
  Other organizations' data is never included.
- **Permissions:** the endpoint does not require one dedicated permission.
  Instead, each section of the response is included only when the caller
  holds the corresponding module's read permission (`devices:read`,
  `monitoring:read`, `agents:read`, `incidents:read`, `discovery:read`,
  `recommendations:read`). This mirrors the authorization boundary already
  enforced by the underlying module endpoints; the aggregation layer never
  exposes data a user could not already see through those endpoints.
- **Missing vs. zero:** when the caller lacks permission for a module, that
  section is `null` (omitted), not a fabricated `0`. A `null` section means
  "you cannot view this data", not "there is no data".
- **Read-only:** performs `SELECT`/`COUNT` queries only; no writes.

### Response shape

```json
{
  "generated_at": "2025-01-01T00:00:00Z",
  "devices": { "total": 42 },
  "monitoring": {
    "total_targets": 40, "enabled_targets": 38, "disabled_targets": 2,
    "healthy": 30, "degraded": 5, "unhealthy": 2, "offline": 1, "unknown": 2
  },
  "agents": { "total": 12, "active": 10 },
  "incidents": { "open": 3, "in_progress": 1 },
  "discovery": { "total": 6, "running": 1, "pending": 2, "completed": 2, "failed": 1 },
  "recommendations": { "total": 9, "pending": 4 }
}
```

Any of `devices`, `monitoring`, `agents`, `incidents`, `discovery`, or
`recommendations` may be `null` when the caller lacks the corresponding read
permission. `monitoring` reuses the same shape as `GET /api/v1/monitoring/summary`.

### Implementation notes

- Backed by `apps/api/app/services/dashboard.py::DashboardService`, which
  computes each aggregate with a scoped `COUNT`/`GROUP BY` query
  (`select(func.count())...`) rather than loading full result sets.
- Covered by `apps/api/tests/test_dashboard.py`: accurate aggregates,
  permission-based section omission, organization isolation, and
  authentication enforcement.

## Module-to-endpoint mapping

Detailed tables, drill-downs, and activity feeds still use the per-module
endpoints below; only aggregate dashboard KPIs come from
`/api/v1/dashboard/overview`.

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

## Why an aggregation endpoint was added

Earlier revisions of this document argued that per-module endpoints were
sufficient. Review found that was not accurate for organization-wide KPIs:
paginated endpoints such as `GET /api/v1/incidents` only return one page of
results, so a frontend computing "open incidents" from `items` undercounts
whenever an organization has more open incidents than fit on the first page.
`GET /api/v1/dashboard/overview` was added specifically to answer these
whole-organization aggregate questions with accurate, permission-scoped
`COUNT` queries, without duplicating authorization logic in the frontend.
