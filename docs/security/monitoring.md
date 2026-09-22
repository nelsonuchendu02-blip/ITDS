# Monitoring security

Monitoring checks and health telemetry are organization-owned records. The
database uses composite `(id, organization_id)` foreign keys for device and
check references, while the service and API apply organization predicates to
every read and write. Cross-organization identifiers therefore return a
not-found or permission error without disclosing their existence.

Telemetry is data only: Phase 1L has no probe execution, scheduler, command
execution, or remediation behavior. Inputs are strictly validated, pagination
is bounded to 100 records, future timestamps are rejected, and successful
creates are written to the security audit stream.
