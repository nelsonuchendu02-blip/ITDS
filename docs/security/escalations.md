# Escalation security

Escalations are organization-scoped children of incidents. The database
enforces the incident/organization composite relationship and prevents
duplicate levels for one incident. Creation, acknowledgement, and resolution
are permission-gated explicit operations and produce
`escalation_created`, `escalation_acknowledged`, and `escalation_resolved`
audit events. Closed incidents cannot be escalated.
