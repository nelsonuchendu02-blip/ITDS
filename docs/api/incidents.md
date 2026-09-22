# Incident API

Incidents are organization-scoped. Use `POST /api/v1/incidents` to create,
`GET` for listing or retrieval, and `POST /{id}/assign` to assign an
organization user. Lifecycle transitions are explicit:

- `POST /{id}/start`
- `POST /{id}/resolve` with `{ "resolution_summary": "..." }`
- `POST /{id}/close` (the existing resolution summary is required)

Lifecycle endpoints reject invalid transitions and write audit events. The
generic patch endpoint is limited to non-lifecycle metadata.
