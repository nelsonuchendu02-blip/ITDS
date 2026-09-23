# Agent security model

- Enrollment tokens and agent credentials are high-entropy one-time secrets.
- Only password hashes are stored; raw values are returned exactly once.
- Enrollment validates both device and organization ownership.
- Enrollment tokens are claimed with an atomic single-use transition; target
  devices are optional and may remain unbound until later convergence.
- Agent credentials are checked for active status, expiry, revocation, and agent status.
- Every enrollment, token creation, heartbeat, and rotation emits an audit event.
- Agent telemetry is bounded to strict schemas and cannot contain executable fields.
- Heartbeats never accept organization or device identifiers; those values come
  from the authenticated credential.
