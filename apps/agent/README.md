# Windows agent foundation

This package establishes the module boundaries for the future Windows endpoint agent without implementing operational automation.

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
