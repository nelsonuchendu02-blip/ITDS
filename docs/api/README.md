# API documentation

The current backend exposes a minimal operational surface for the Phase 0 foundation.

## Health check

- Method: GET
- Route: `/api/health`
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

Future API work will add diagnostic, incident, and support workflow endpoints under versioned routes such as `/api/v1`.
