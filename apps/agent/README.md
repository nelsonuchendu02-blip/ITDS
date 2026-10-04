# Windows endpoint agent

Phase 1M established a safe endpoint foundation: read-only collectors using `psutil`, an
HTTPS communication client using `httpx`, and a lifecycle runtime. Phase 1O adds a
production Windows Service host, a deterministic installer/uninstaller, DPAPI-protected
credential storage, and PyInstaller packaging around that same foundation. The agent
intentionally contains no subprocess, shell, PowerShell, WMI, SSH, network scanning,
repair, or destructive-action behavior anywhere in this package.

For full operational instructions (install/uninstall, configuration, packaging, directory
layout) see [docs/operations/windows-agent.md](../../docs/operations/windows-agent.md).
For the security model (credential protection, least privilege, logging guarantees,
security boundary) see
[docs/security/windows-agent-security.md](../../docs/security/windows-agent-security.md).

## Current structure

- `core`: runtime and lifecycle shell (`AgentRuntime`)
- `config`: configuration loading/validation and filesystem path policy
- `collectors`: safe read-only system and local-network telemetry collection
- `communication`: HTTPS heartbeat client (`httpx`), bounded retries/timeouts
- `security`: DPAPI-protected credential store (`CredentialStore`) and the
  `ITDSAgentEnroll` operator tool
- `service`: Windows Service Control Manager integration (`service/host.py`,
  Windows-only) and the Windows-agnostic `ServiceLifecycle` wrapper
  (`service/lifecycle.py`, unit-tested on every platform)
- `logging`: rotating, redacting logging configuration
- `diagnostics`: future analysis logic (unimplemented)
- `remediation`: planned safe remediation workflows only (unimplemented)
- `installer/` (sibling to `itds_agent/`): the deterministic Python installer
  (`install.py`, `uninstall.py`, `common.py`) - the sole supported installation
  mechanism; see the operations doc for why no PowerShell installer exists.
- `build/` (sibling to `itds_agent/`): the PyInstaller build script
  (`build_exe.py`) and its entry-point wrapper scripts (`entrypoints/`)

## Running the agent

- Console mode (development, no service installation):
  `python -m itds_agent`
- Production: install as the `ITDSAgent` Windows Service via
  `python installer/install.py` (see the operations doc for the full
  install/enroll/start sequence).

Console mode and the Windows service both call the same
`itds_agent.core.bootstrap.build_runtime()` function, so there is exactly one
configuration/logging/heartbeat code path regardless of how the process starts.

## Safety rules

- No repair commands are executed anywhere in this package.
- No Windows configuration is modified, other than the installer's own fixed,
  narrow actions (service registration, recovery policy, and ACLs on the
  agent's own data directory - never arbitrary system settings).
- No destructive actions are implemented.
- Sensitive data collection is deliberately avoided.
- Communication uses `X-Agent-Credential`, bounded request sizes, timeouts, and bounded retries.
- Heartbeats are sent over HTTPS to the versioned API path `/api/v1/agents/heartbeat`,
  constructed from the configured `api_base_url` (e.g. `https://server.example.com`).
- The agent is telemetry-only; it performs no repair, shell, PowerShell, WMI, SSH, scanning, or OS changes.
- The agent credential is protected at rest via Windows DPAPI plus a restrictive
  NTFS ACL on its storage directory (see the security doc for why both are
  required together, not either alone).
- The installer accepts no operator-supplied commands or arbitrary arguments
  beyond a fixed executable path; every Windows API call it makes uses fixed,
  hard-coded arguments.
