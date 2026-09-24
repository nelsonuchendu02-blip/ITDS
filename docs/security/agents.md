# Agent security model

- Enrollment tokens and agent credentials are high-entropy one-time secrets.
- Only password hashes are stored; raw values are returned exactly once.
- Enrollment validates both device and organization ownership.
- Enrollment tokens are claimed with an atomic single-use transition; target
  devices are optional and may remain unbound until later convergence.
- Agent credentials are checked for active status, expiry, revocation, and agent status.
- Enrollment, token creation/revocation, credential rotation/revocation, agent
  lifecycle transitions, and relevant authentication failures are audited.
- Normal high-frequency heartbeat telemetry is not emitted as a security-audit
  event on every cycle.
- Agent telemetry is bounded to strict schemas and cannot contain executable fields.
- Heartbeats never accept organization or device identifiers; those values come
  from the authenticated credential.
