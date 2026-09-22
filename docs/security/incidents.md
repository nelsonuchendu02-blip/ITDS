# Incident security

Incident reads and writes are permission-gated and filtered by organization.
Composite organization/device and organization/user foreign keys prevent
cross-tenant references at the database boundary. Resolution and closure
record the acting user, timestamps, and a non-empty resolution summary.
Unknown request fields are rejected by strict Pydantic schemas.
