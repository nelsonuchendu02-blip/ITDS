# Windows agent foundation

Phase 1M provides a safe endpoint foundation: read-only collectors using `psutil`, an
HTTPS communication client using `httpx`, and a lifecycle runtime. It intentionally contains no subprocess,
shell, PowerShell, WMI, SSH, network scanning, repair, or service-installation behavior.
Credentials are supplied by the server enrollment flow and must not be logged.

## Current structure

- `core`: runtime and lifecycle shell
- `config`: configuration support for safe deployment
- `collectors`: safe read-only system and local-network telemetry collection
- `diagnostics`: future analysis logic
- `remediation`: planned safe remediation workflows only
- `communication`: HTTPS heartbeat client (`httpx`); future support-channel
  contracts beyond the heartbeat path remain unimplemented
- `logging`: logging facade for agent events

## Safety rules

- No repair commands are executed in this phase.
- No Windows configuration is modified.
- No destructive actions are implemented.
- Sensitive data collection is deliberately avoided.
- Communication uses `X-Agent-Credential`, bounded request sizes, timeouts, and bounded retries.
- Heartbeats are sent over HTTPS to the versioned API path `/api/v1/agents/heartbeat`,
  constructed from the configured `api_base_url` (e.g. `https://server.example.com`).
- The agent is telemetry-only; it performs no repair, shell, PowerShell, WMI, SSH, scanning, or OS changes.
