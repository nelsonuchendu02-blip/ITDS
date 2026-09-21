# Secure recommendations

Recommendations are organization-scoped, server-created records derived from a
root-cause finding. Clients submit only the finding reference and explanatory
content; organization, device, diagnostic evidence, creator, timestamps, and
workflow state are assigned by the API.

The API exposes `recommendations:read` for listing and reading, and
`recommendations:run` for creating or deterministically generating
recommendations. Reviewing, accepting, rejecting, or implementing a
recommendation requires `recommendations:manage`. Every lifecycle
transition is recorded in the audit log and transitions are guarded with
compare-and-set updates to prevent stale clients from changing state.

`POST /api/v1/recommendations/generate` accepts a completed root-cause
`analysis_id`. The server evaluates the immutable allow-listed
`RULE_REGISTRY`, creates at most one recommendation per finding, and stores the
rule identifier and evidence fingerprint. Client predicates, expressions, and
commands are never evaluated.

All finding lookups include the authenticated user's organization. A finding
from another organization is returned as not found rather than disclosed.
Recommendation status values are `pending`, `reviewed`, `accepted`, `rejected`,
and `implemented`. The only valid lifecycle paths are
`pending -> reviewed -> accepted -> implemented` or
`reviewed -> rejected`.
