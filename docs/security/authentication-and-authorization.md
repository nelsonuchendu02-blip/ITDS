# Authentication and Authorization

Phase 1C establishes the backend identity and authorization foundation.

## Authentication

Passwords are hashed with Argon2 through `pwdlib`. Password hashes are stored
only in the `users.password_hash` column and are never returned by API schemas.
Login is available through `POST /api/v1/auth/token` using OAuth2-compatible
form-equivalent fields (`username` contains the normalized email and `password`).

Access tokens are signed JWTs with `sub`, `exp`, `iat`, `jti`, and `typ=access`.
The signing secret, algorithm, lifetime, issuer, and audience are configured
through environment settings. `JWT_SECRET` is mandatory when issuing or
validating tokens and must never be committed.

The migration permits a null hash for pre-existing Phase 1A users so the
schema upgrade remains safe for existing data. Such users cannot authenticate
until an operator provisions a password through a controlled administrative
process.

## Organization context and roles

The current user is loaded from the token subject and database. Organization
context comes from `User.organization_id`; client-supplied organization IDs are
not used as authorization proof.

Ordinary authorization checks remain organization-scoped. The
`platform_admin` wildcard covers defined in-organization permissions only; it
does not grant cross-organization access. Cross-organization authority would
require the separate explicit `organizations:cross_scope` permission, which no
baseline role receives.

The baseline role names are:

- `platform_admin`: all permissions
- `organization_admin`: organization, user, role, and audit administration
- `it_support`: user read, device read/write, and audit read
- `technician`: device read/write and diagnostics execution
- `viewer`: user and device read

Reusable `require_role` and `require_permission` dependencies enforce access
before protected service operations. No domain CRUD endpoints are exposed in
this phase.

## Phase 1D management API

The protected management routes provide organization-scoped administration:

- `GET /api/v1/organizations/me` and scoped organization read/update
- paginated user list, read, create, update, activate, and deactivate operations
- role listing, assignment, and removal for users in the current organization
- paginated audit-event read access

There is no public registration route. Administrative user creation hashes the
password in the service layer and never returns the hash. User, role, and audit
queries include the authenticated organization predicate. Organization paths
may only cross that boundary when a caller has the explicit
`organizations:cross_scope` permission; the `platform_admin` wildcard does not
implicitly provide it. Assignment of the `platform_admin` role is not exposed
through the organization-scoped management API.

## Phase 1E device inventory

Authenticated users with `devices:read` can list and retrieve devices in their
authenticated organization. Users with `devices:write` can update approved
device metadata; users with `devices:manage` can register devices and activate
or deactivate them. The organization is assigned from the authenticated user
and is not accepted from the request body.

Device list requests use bounded pagination with a maximum page size of 100 and
support search, status, device type, and operating-system filters. Device
lookups and mutations include the organization predicate, so identifiers from
another organization return the same not-found response rather than revealing
whether a device exists. Device IDs, organization IDs, audit ownership, status
timestamps, and last-seen values are server-controlled.

Device creation, metadata updates, activation, and deactivation create
organization-scoped audit events containing only safe actor, target, operation,
result, and status metadata. Discovery, monitoring, telemetry, diagnostics, and
remediation are outside Phase 1E.

## Bootstrap and audit

Run `scripts/bootstrap_admin.py` explicitly with `DATABASE_URL` and
`JWT_SECRET` configured. The command prompts for the password without printing
it, creates the first organization and baseline roles, assigns
`platform_admin`, and refuses to run after any user exists.

The singleton bootstrap-state record is written in the same transaction as the
organization, roles, user, role assignment, and bootstrap audit event. A
duplicate singleton insert causes the transaction to roll back.

Successful and failed login attempts create `AuditEvent` records without
passwords, hashes, tokens, or authorization headers.

MFA, SSO, LDAP, password reset email, refresh-token storage, and browser
session handling are future security work.
