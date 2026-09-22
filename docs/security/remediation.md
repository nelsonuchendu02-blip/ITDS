# Phase 1J secure remediation

Remediation plans are deterministic, organization/device scoped records composed
only from an accepted recommendation and the allowlisted structured action
catalog. Generation is deterministic and idempotent. Plans require explicit
approval before queueing, execution, and verification. Phase 1J execution is
always a dry run: the executor does not invoke a shell, process, network
command, or operating-system API. Command, shell, PowerShell, script,
executable, path, and unknown action fields are rejected.

The protected routes are list/get plans and actions (`remediation:read`),
create/generate and submit (`remediation:create`), approve/reject
(`remediation:approve`), queue/cancel (`remediation:manage`), dry-run execute
(`remediation:execute`), and verify/results (`remediation:verify` or read).
Every successful or failed operation emits a sanitized audit event and all
lookups enforce organization isolation.
