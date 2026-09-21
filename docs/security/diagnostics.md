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

## Secure root-cause analysis (Phase 1H)

Root-cause analysis is organization-scoped and requires `root_cause:read`,
`root_cause:run`, or `root_cause:manage`. An analysis may be created only for a
diagnostic run whose status is `COMPLETED`; pending, running, failed, and
cancelled runs are intentionally rejected because their evidence is incomplete
or not trustworthy. Analysis execution has guarded pending/running/terminal
transitions, so cancellation cannot be overwritten by a concurrent completion.

The rule registry is deterministic and allow-listed. Rules consume only the
persisted `DiagnosticResult` fields (`check_type` and `status` for Phase 1H),
never client-supplied rule definitions, expressions, commands, credentials, or
provider internals. Findings retain explicit organization, device, and diagnostic-result ownership,
along with a category, severity, status (`identified`, `likely`, or
`insufficient_evidence`), confidence classification, explanation, and
structured evidence. A unique analysis/rule/evidence fingerprint prevents
duplicate findings within an analysis. Failures expose only a stable safe error
code and write an organization-scoped audit event.

The protected API surface is:

- `POST /api/v1/root-cause/analyses`
- `GET /api/v1/root-cause/analyses`
- `GET /api/v1/root-cause/analyses/{analysis_id}`
- `POST /api/v1/root-cause/analyses/{analysis_id}/run`
- `POST /api/v1/root-cause/analyses/{analysis_id}/cancel`
- `GET /api/v1/root-cause/analyses/{analysis_id}/findings`

The Phase 1H migration uses PostgreSQL native enums and portable JSON/UUID
types. It also adds composite organization/device foreign keys so analyses and
findings cannot combine an organization with a device, diagnostic run, or
diagnostic result owned by another organization. SQLite remains supported for
unit tests; its foreign-key enforcement is enabled by the migration tests.
