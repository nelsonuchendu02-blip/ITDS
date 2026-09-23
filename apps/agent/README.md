# Windows agent foundation

Phase 1M provides a safe endpoint foundation: read-only stdlib collectors, an injectable
communication transport, and a lifecycle runtime. It intentionally contains no subprocess,
shell, PowerShell, WMI, SSH, network scanning, repair, or service-installation behavior.
Credentials are supplied by the server enrollment flow and must not be logged.

## Current structure

- `core`: runtime and lifecycle shell
- `config`: configuration support for safe deployment
- `collectors`: future endpoint data collection
- `diagnostics`: future analysis logic
- `remediation`: planned safe remediation workflows only
- `communication`: future support-channel contracts
- `logging`: logging facade for agent events

## Safety rules

- No repair commands are executed in this phase.
- No Windows configuration is modified.
- No destructive actions are implemented.
- Sensitive data collection is deliberately avoided.
