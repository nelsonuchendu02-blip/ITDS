# ITDS operations dashboard (Phase 1N)

## Overview

The Phase 1N frontend replaces the previous Phase 0 health-only shell with a
full React + TypeScript operations dashboard. It is backed by live backend
endpoints under `/api/v1`.

## Authentication model

- Login uses `POST /api/v1/auth/token` (form-encoded credentials).
- Current user profile uses `GET /api/v1/auth/me`.
- Access token is kept **in memory only** (not persisted to local/session
  storage) because no refresh-token contract exists yet.
- If the backend returns `401`, the client clears the in-memory session and
  redirects to sign-in.

## API client and error handling

- Centralized in `apps/web/src/services/api.ts`.
- Automatically prefixes versioned routes with `/api/v1`.
- Preserves unauthenticated `/api/health` checks separately.
- Uses bounded request timeout and request payload-size limits.
- Parses backend structured errors (`{ error: { code, message } }`) with safe
  status-based fallbacks.

### Timeout and cancellation semantics

Every request is driven by a single internal `AbortController`, not by the
caller's `AbortSignal` directly:

- A timer (`timeoutMs`, default 15s) aborts the internal controller if the
  request has not completed in time, producing an `ApiError` with
  `code: 'timeout'`.
- If the caller passes its own `AbortSignal` (for example a React effect's
  unmount/cleanup signal via `usePolledResource`), an abort listener on that
  signal also aborts the same internal controller, but first records that
  the abort was caller-initiated. That path produces `code: 'cancelled'`
  instead of `'timeout'`.
- This distinction means an intentional cancellation (component unmount,
  a new poll superseding an in-flight one) is never surfaced to the user as
  a false "the request timed out" error, while a genuine timeout is never
  misreported as a routine cancellation.
- The timer and the caller-signal listener are always cleaned up in a
  `finally` block (and on the early payload-too-large rejection path), so no
  timer or listener outlives a completed/aborted request.

### Polling behavior

- `usePolledResource` (`apps/web/src/hooks/usePolledResource.ts`) fetches once
  on mount, then re-fetches on a fixed interval (default 30s) while enabled.
- Only one request is in flight per resource at a time; a manual `refresh()`
  is a no-op if a fetch is already running.
- On unmount, the interval timer is cleared and the resource's in-flight
  request is aborted via its internal `AbortController`, which is passed to
  the fetcher as its cancellation signal - this is the caller signal the
  `ApiClient` distinguishes from its own timeout, per above.
- A failed background refresh sets `error` but preserves the previously
  loaded `data`, so the UI does not flash to empty on a transient failure.

## Data modules

The dashboard includes permission-gated pages for:

- dashboard overview and KPIs (aggregate counts from `GET /api/v1/dashboard/overview`)
- devices
- monitoring + telemetry
- agents
- incidents + escalations
- discovery
- diagnostics
- root-cause analyses
- recommendations
- remediation plans
- networks inventory
- audit log

All modules render loading, error, and empty states and support bounded polling
refresh via `usePolledResource`.

## Dashboard aggregation strategy

The Dashboard page (`apps/web/src/pages/Dashboard.tsx`) draws its KPI cards and
health-distribution chart from a single `GET /api/v1/dashboard/overview` call
instead of computing organization-wide totals from paginated module responses.
This is necessary because paginated endpoints (for example `GET
/api/v1/incidents`) return only one page at a time; deriving an "open
incidents" count from `items.length` on the first page undercounts once an
organization has more open incidents than fit on a page. See
`docs/api/dashboard.md` for the endpoint contract.

Detailed tables and the recent-activity feed continue to use the per-module
endpoints (`listAgents`, `listIncidents`, `listDiscoveryJobs`,
`listRecommendations`) directly, since those views need item-level data the
aggregate endpoint intentionally does not return.

The dashboard's loading state (`anyLoading`) includes every resource that
contributes visible content - the overview call plus agents, incidents,
discovery jobs, and recommendations - so the page never shows "no recent
activity" merely because one of those resources is still loading in the
background.

## Permission-aware navigation

- Sidebar entries are defined centrally in `src/utils/navigation.ts`.
- UI visibility is controlled with `usePermission`/`useAnyPermission` and
  `PermissionGate`.
- Backend authorization remains the source of truth: the frontend rule below
  only controls whether a nav link/page renders; the aggregation endpoint and
  every module endpoint independently enforce their own permission checks
  server-side.
- **Dashboard nav entry decision:** the backend has no dedicated
  `dashboard:read` permission, since the dashboard is a composite view over
  several modules rather than its own resource. Gating the Dashboard link on
  a single module permission (previously `devices:read`) incorrectly hid it
  from users who could read other contributing modules (for example an
  incident responder with only `incidents:read`). The Dashboard nav entry is
  therefore visible to a user who holds **any** of `devices:read`,
  `monitoring:read`, `agents:read`, `incidents:read`, `discovery:read`, or
  `recommendations:read` (`useAnyPermission`), matching which KPI sections
  `GET /api/v1/dashboard/overview` will actually populate for that user. The
  Dashboard page itself further hides each KPI card/section individually
  based on the same per-module permissions, and shows an explicit "no
  dashboard data" empty state if none apply.

## Design system

The UI extends the existing dark theme and adds reusable components:

- layout shell (sidebar, topbar, footer)
- status badges
- KPI cards
- reusable data table and pagination
- feedback components (loading/empty/error/access denied)
- responsive layout rules for desktop/tablet/mobile

## Security and behavior constraints

- No fake production metrics/devices/incidents data.
- No frontend command execution paths.
- No credential/token logging.
- No destructive operations added in the dashboard layer.
