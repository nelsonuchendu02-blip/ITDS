# Architecture overview

## Major components

- API layer: FastAPI service that exposes versioned endpoints and health checks.
- Web client: React application responsible for displaying backend status and operational state.
- Agent layer: Python-based endpoint architecture reserved for future Windows collectors and diagnostics.
- Database layer: PostgreSQL-oriented migration and seed structure for future domain modeling.
- Automation layer: PowerShell guidance for future safe automation under explicit admin checks.

## Responsibilities

### API

The API layer manages configuration, logging, request validation, CORS, and error handling. It exposes the health endpoint and will grow to host diagnostic endpoints and support workflows without compromising the initial boundary.

### Web application

The frontend consumes real API data only, renders a minimal shell, and shows loading or error states from the backend.

### Windows agent

The agent foundation intentionally contains module boundaries only. No repair action or destructive operation is implemented in Phase 0. All modules exist to define a safe, extensible path for future device collectors and diagnostics.

### Database

The database foundation plans for PostgreSQL support and keeps migration/seed directories ready for future schema work without creating production tables yet.

### PowerShell automation

PowerShell guidance is intentionally limited to conventions, parameter validation, and safety policy. Real remediation logic is out of scope for this phase.

## Communication boundaries

- Web client calls API over HTTP.
- API reads configuration from environment variables.
- Windows agent modules rely on explicit interfaces and future communication channels.
- Database access remains intentionally out of scope for Phase 0.

## Future endpoint-agent architecture

The future agent will likely be organized as:

- core runtime
- configuration management
- collectors
- diagnostics
- remediation
- communication
- logging

Phase 0 defines the package boundaries but not any live operational behavior.

## Future real-time architecture

Real-time monitoring will be added in a future phase with explicit event streams, message brokers, and UI synchronization contracts. This phase avoids implementing real-time telemetry or stateful dashboards.

## Security boundaries

- Secrets live in environment variables only.
- CORS is explicitly configured and not wildcarded.
- Input validation and structured error responses are applied.
- Sensitive information collection is intentionally deferred.

## Scalability considerations

The Phase 0 design intentionally favors clean separation and maintainability over scaling assumptions. The architecture is structured to scale by adding services, collectors, and schemas without forcing early coupling between domain layers.
