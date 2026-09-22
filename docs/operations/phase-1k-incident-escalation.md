# Phase 1K incident and escalation foundation

Phase 1K provides organization-scoped incident and escalation workflows. Every
device, assignee, and escalation parent is protected by composite
organization-aware foreign keys. API payloads reject unknown fields and enforce
bounded strings and escalation levels.

Incident transitions are open → in progress → resolved → closed (an incident
must be resolved before it is closed). Escalations are open → acknowledged or
resolved. All creates and lifecycle changes write audit events. This phase is
data/workflow-only: it performs no subprocess, shell, PowerShell, eval, exec,
or other dynamic execution.
