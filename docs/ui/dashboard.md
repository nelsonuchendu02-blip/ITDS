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

## Data modules

The dashboard includes permission-gated pages for:

- dashboard overview and KPIs
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

## Permission-aware navigation

- Sidebar entries are defined centrally in `src/utils/navigation.ts`.
- UI visibility is controlled with `usePermission` and `PermissionGate`.
- Backend authorization remains the source of truth.

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
