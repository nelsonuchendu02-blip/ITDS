# PowerShell standards

This directory establishes the rules for PowerShell automation in future project phases. No live remediation scripts are included in Phase 0.

## Required conventions

- Validate all parameters before use.
- Prefer explicit return codes over implicit success assumptions.
- Log actions and failures to a structured output channel.
- Check for administrator privileges before any privileged operation.
- Require a safety gate for any operation that could change system state.
- Do not implement destructive actions in Phase 0.

## Safety checks

- Verify the execution context before running privileged commands.
- Require explicit approval for actions beyond read-only diagnostics.
- Guard against accidental changes to system configuration.
- Use exit codes that clearly distinguish success, validation failure, and privilege issues.

## Error handling

- Catch exceptions and log contextual details.
- Return actionable error messages rather than raw stack traces.
- Ensure command output is readable and auditable.

## Destructive-operation protection

The foundation forbids destructive operations until later phases define the required safeguards, approval flow, and rollback plan.
