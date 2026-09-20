# Operations guidance

This repository intentionally avoids deployment infrastructure and operational monitoring in Phase 0. The project is designed to establish a stable foundation before automation and lifecycle management are added.

## Current guidance

- Validate backend tests with pytest.
- Validate frontend build with Vite.
- Use environment variables for runtime settings.
- Keep a minimal, explicit configuration surface.

## Deferred operations work

- deployment automation
- environment orchestration
- observability pipelines
- configuration management
- incident runbooks
- support escalation workflows
