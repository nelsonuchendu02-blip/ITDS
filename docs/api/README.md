# API documentation

The ITDS backend exposes:

- an unauthenticated platform liveness endpoint at `/api/health`
- authenticated, organization-scoped operational APIs under `/api/v1/*`

## Health check

- Method: `GET`
- Route: `/api/health`
- Purpose: backend reachability/liveness probe
- Response: `200 OK`

Example payload:

```json
{
  "status": "ok",
  "service": "itds-api",
  "version": "0.1.0",
  "environment": "development"
}
```

## Versioned API surface (`/api/v1`)

The dashboard integrates directly with existing endpoints (no separate
dashboard-only aggregation endpoint). Current functional groups include:

- authentication: `/auth/token`, `/auth/me`
- device management: `/devices`
- monitoring and telemetry: `/monitoring/*`
- agents: `/agents`
- incidents and escalations: `/incidents/*`
- discovery: `/discovery/*`
- diagnostics: `/diagnostics/*`
- root-cause analysis: `/root-cause/*`
- recommendations: `/recommendations`
- remediation plans: `/remediation/*`
- inventory topology resources: `/sites`, `/networks`, `/subnets`, `/vlans`, `/ssids`
- audit events: `/audit-events`

All authorization is server-enforced by role-derived permissions. UI permission
gating in the dashboard is usability-oriented and does not replace API access
control.
