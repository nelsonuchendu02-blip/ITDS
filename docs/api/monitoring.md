# Monitoring and health telemetry

Phase 1L provides organization-scoped monitoring target definitions and an
append-only health telemetry record API. It does not execute probes, schedule
jobs, or perform remediation.

- `POST/GET /api/v1/monitoring/targets` creates and lists targets.
- `GET/PATCH /api/v1/monitoring/targets/{id}` reads and updates a target.
- `POST /api/v1/monitoring/targets/{id}/enable` and `/disable` toggle targets.
- `POST /api/v1/monitoring/targets/{id}/telemetry` ingests telemetry.
- `GET /api/v1/monitoring/targets/{id}/telemetry` lists telemetry with bounded pagination.
- `GET /api/v1/monitoring/summary` returns organization health counts.

All routes require the monitoring permission and enforce organization scope.
Telemetry ingestion requires `monitoring:ingest`; timestamps must be timezone-aware,
non-future, and ordered. There is one target per organization/device.
Targets enforce a check interval of 10–86,400 seconds and an offline threshold
of 10–604,800 seconds that is never below the interval. Summary counts include
total, enabled, disabled, healthy, degraded, unhealthy, offline, and unknown.
