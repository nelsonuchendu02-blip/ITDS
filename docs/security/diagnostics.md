# Secure diagnostics (Phase 1G)

Diagnostics are organization-scoped and require an authenticated user with
`diagnostics:read`, `diagnostics:run`, or `diagnostics:manage`. Every lifecycle
mutation emits an organization-scoped audit event. State changes use a
conditional `UPDATE` on the expected status, so completion cannot overwrite a
concurrent cancellation (and terminal states cannot be re-entered).

The Phase 1 provider is deterministic simulation only. It accepts structured
identifiers, never executes subprocesses, opens network connections, reads
credentials, or returns provider exceptions to API clients. Diagnostic result
observations are structured JSON and should not contain secrets.

`GET /api/v1/diagnostics/check-types` is the supported discovery endpoint for
the allow-listed check types (`connectivity`, `configuration`, `security`, and
`performance`) and requires `diagnostics:read`.

The Phase 1G migration uses PostgreSQL native enums and foreign keys. SQLite
uses SQLAlchemy's portable enum representation and Alembic batch table rebuilds
for foreign keys added to existing diagnostic tables; both backends retain the
same persisted enum names and referential constraints.
