# Windows endpoint agent: operations guide (Phase 1O)

This document describes how the ITDS endpoint agent is packaged, installed,
configured, and operated as a Windows Service. It reflects the actual
implementation under `apps/agent/`, not aspirational behavior.

For the security model (credential protection, least privilege, logging
guarantees, security boundary), see
[docs/security/windows-agent-security.md](../security/windows-agent-security.md).

## Supported installation interface

**The supported installation interface is the Python installer modules under
`apps/agent/installer/`** (`install.py`, `uninstall.py`, `common.py`). There is
no PowerShell installer, and none is planned:

- Only one installation mechanism exists in this repository. The
  `automation/powershell/` scripts are unrelated, read-only diagnostic
  tooling and never perform Windows service installation, registration, or
  configuration changes; they are out of scope for agent deployment.
- Introducing a second (PowerShell) installer that duplicates
  `install.py`/`uninstall.py` would create two independently-maintained
  code paths that could drift out of sync (e.g. one applying the ACL
  policy, the other forgetting to), which is exactly the "overlapping
  mechanisms" outcome Phase 1O explicitly avoids. A future thin PowerShell
  wrapper that only *invokes* `python installer/install.py` could be added
  later without changing this contract, but does not exist today and is not
  required.
- Operators run `installer/install.py` and `installer/uninstall.py` directly
  (from an elevated shell) or via the frozen executables described below.

## Components produced by this phase

| Component | Source | Purpose |
| --- | --- | --- |
| `ITDSAgent.exe` | `itds_agent/service/host.py` (via `build/entrypoints/service_entry.py`) | The Windows Service binary; also supports `install/remove/start/stop/debug` via `win32serviceutil.HandleCommandLine` for direct SCM operations (distinct from the repository's own installer, which additionally sets directory ACLs and recovery policy - see below). |
| `ITDSAgentEnroll.exe` | `itds_agent/security/enroll.py` (via `build/entrypoints/enroll_entry.py`) | One-time operator tool: prompts for the agent credential (hidden input) and stores it DPAPI-protected. |
| `python installer/install.py` | `apps/agent/installer/install.py` | Installs the `ITDSAgent` service with the intended account, startup type, recovery policy, and directory ACLs. |
| `python installer/uninstall.py` | `apps/agent/installer/uninstall.py` | Stops and removes the service, clears the stored credential, optionally purges data. |

The installer copies the complete `ITDSAgent` onedir package, including
PyInstaller's `_internal/` runtime files, to `%ProgramFiles%\ITDS\Agent` and
registers the service from that installed location. Each install stages a
fresh package and replaces the destination directory, removing stale files
from earlier versions. Reparse points in source, staging, or destination
paths are rejected. Stop an already-running service before upgrading so
Windows does not keep package files locked. `--exe` selects the packaged
executable to copy; its containing directory is copied as the package.

Console mode (`python -m itds_agent`, useful for local development without
installing a service) and the Windows service both call the same
`itds_agent.core.bootstrap.build_runtime()` function, so there is exactly one
configuration/logging/heartbeat code path regardless of how the process is
started.

## Directory layout

| Path | Contents | Notes |
| --- | --- | --- |
| `%PROGRAMDATA%\ITDS\Agent\config.json` | Non-secret configuration (see below) | Created by the operator; loader rejects unknown/secret fields. |
| `%PROGRAMDATA%\ITDS\Agent\credential.bin` | DPAPI-protected agent credential | Written only by `ITDSAgentEnroll.exe` / `itds_agent.security.enroll`. |
| `%PROGRAMDATA%\ITDS\Agent\logs\itds-agent.log(.N)` | Rotating log files | Bounded size; see the security doc for redaction guarantees. |
| install directory (wherever `build/dist/ITDSAgent/` is copied to, e.g. `%ProgramFiles%\ITDS\Agent\`) | Frozen executable + PyInstaller `_internal/` support files | Read-only at runtime; the service does not need write access here (least privilege). |

`ProgramData` (not `Program Files`) holds mutable runtime state specifically
so the service account never needs write access to its own install
directory. `installer/common.py::secure_data_directories()` creates
`config`/`credential`/`logs` directories if missing and applies a DACL that
grants full control only to `SYSTEM`, `BUILTIN\Administrators`, and the
service account (`NT AUTHORITY\LocalService`) - no other local account can
read the protected credential file or configuration.

The override environment variable `ITDS_AGENT_DATA_DIR` exists purely for
tests; production deployments should not set it.

## Configuration

`config.json` is a plain JSON object. Allowed keys (see
`itds_agent/config/loader.py::_ALLOWED_FILE_KEYS`):

```json
{
  "agent_name": "device-01",
  "agent_version": "1.0.0",
  "api_base_url": "https://server.example.com",
  "device_id": "…",
  "heartbeat_interval_seconds": 60,
  "request_timeout_seconds": 10,
  "log_level": "INFO",
  "log_directory": "C:\\ProgramData\\ITDS\\Agent\\logs",
  "log_max_bytes": 1000000,
  "log_backup_count": 5
}
```

- `credential`, `password`, `secret`, `token`, and `api_key` are **forbidden**
  keys in this file; the loader raises `ConfigurationError` if present. The
  credential always comes from the protected credential store, never the
  config file.
- Any key not in the allow-list is rejected (`ConfigurationError`), so a
  config file can never silently smuggle in an unreviewed field.
- Every key can also be set via an `ITDS_AGENT_<KEY>` environment variable
  (e.g. `ITDS_AGENT_API_BASE_URL`), which overrides the file value; useful
  for scripted/ephemeral deployments.
- `api_base_url` must be `https://`; HTTP is rejected by
  `AgentSettings.validate()`.

## Credential enrollment

1. Enroll the device through the ITDS API (outside this agent) to obtain a
   one-time agent credential.
2. As an Administrator on the target machine, run `ITDSAgentEnroll.exe`
   (or `python -m itds_agent.security.enroll`). It prompts for the
   credential via hidden input (never accepted as a CLI argument, so it
   never appears in shell history or process listings) and stores it
   DPAPI-protected at `credential.bin`.
3. To rotate a credential, obtain a new one from the API and re-run the
   enrollment tool; this overwrites the previous protected blob.
4. To remove a stored credential without uninstalling, run
   `ITDSAgentEnroll.exe --clear`. `installer/uninstall.py` also clears it
   automatically.

See [docs/security/windows-agent-security.md](../security/windows-agent-security.md)
for exactly how the credential is protected and why it can be decrypted by
the `LocalService` account even though it is enrolled by an interactive
Administrator.

## Install

```powershell
# From an elevated PowerShell/Command Prompt, after building (see Packaging below):
cd apps\agent
python installer\install.py
# or, with an explicit exe path:
python installer\install.py --exe "C:\path\to\ITDSAgent.exe"
```

This performs exactly five fixed actions (no arbitrary commands are ever
accepted or executed):

1. Verifies the process is elevated (`require_admin()`); refuses to
   continue otherwise.
2. Copies the complete packaged `ITDSAgent` directory, including
   `_internal/` support files, into `%ProgramFiles%\ITDS\Agent` by default.
3. Creates `%PROGRAMDATA%\ITDS\Agent` and its `logs` subdirectory (if
   missing) and applies the restricted ACL described above. Safe to rerun:
   directory creation is idempotent (`mkdir(parents=True, exist_ok=True)`)
   and re-applying the same ACL has no adverse effect.
4. Registers the service (display name `ITDS Endpoint Agent`) to run the
   installed `ITDSAgent.exe` under `NT AUTHORITY\LocalService`, with
   automatic (delayed) startup. No account password is ever collected,
   stored, or passed (`password=None` is a fixed constant in
   `install.py`, verified by `tests/test_phase_1o_windows_service.py`).
5. Configures a bounded automatic-restart recovery policy: up to two
   60-second-delayed restarts, then no further action, resetting the
   failure counter after 24 hours with no failures. `SC_ACTION_RUN_COMMAND`
   is never configured, so a service crash can never be turned into
   arbitrary command execution.

After installing, run `ITDSAgentEnroll.exe` once to store the credential,
verify/create `config.json`, then start the service:

```powershell
sc start ITDSAgent
# or
Start-Service ITDSAgent
```

Re-running `installer/install.py` after the service is already installed is
safe: `win32serviceutil.InstallService` on an existing service updates its
configuration rather than creating a duplicate registration, and directory
creation/ACL application are both idempotent.

## Uninstall

```powershell
python installer\uninstall.py
# or, to also delete config/credential/logs:
python installer\uninstall.py --purge-data
```

This performs exactly three fixed actions:

1. Verifies elevation.
2. Stops (if running) and removes the `ITDSAgent` service registration.
   Both "already stopped" and "not installed" are treated as success (not
   errors), so uninstall is safe to run more than once or on a machine
   where install only partially completed.
3. Clears the DPAPI-protected credential file, so no protected secret is
   left behind for a possible future different service account to
   encounter. The uninstaller exits unsuccessfully if clearing the
   credential fails and does not proceed with a requested data purge.

`config.json` and the log directory are left in place by default (useful
for a reinstall or post-mortem review); pass `--purge-data` to delete
`%PROGRAMDATA%\ITDS\Agent` entirely.
Purge always targets the standard `%ProgramData%\ITDS\Agent` location (not
the test-only `ITDS_AGENT_DATA_DIR` override) and refuses to follow a
Windows reparse point in that path. Credential clearing also refuses a
reparse-point path rather than modifying a redirected file.

## Packaging (PyInstaller)

Build from a clean environment:

```powershell
cd apps\agent
pip install -r requirements.txt
pip install -r build\requirements-build.txt
python build\build_exe.py
```

This produces two `--onedir` (directory-based, not single-file) packages:

- `apps/agent/build/dist/ITDSAgent/ITDSAgent.exe` (+ `_internal/` support
  files) - the service binary.
- `apps/agent/build/dist/ITDSAgentEnroll/ITDSAgentEnroll.exe` (+
  `_internal/`) - the enrollment tool.

`--onedir` (rather than `--onefile`) was chosen because it starts faster, is
easier to inspect/verify (files aren't unpacked to a temp directory at
runtime), and lets an installer add/replace individual files without
repackaging.

The actual PyInstaller entry scripts are thin wrapper modules under
`apps/agent/build/entrypoints/` (`service_entry.py`, `enroll_entry.py`), not
`itds_agent/service/host.py` / `itds_agent/security/enroll.py` directly.
PyInstaller freezes whatever script it is given as the `__main__` module,
which breaks Python package-relative imports inside those two modules if
they are frozen directly; the wrapper scripts import them normally
(`from itds_agent.service.host import main`) so the package's internal
relative imports keep working exactly as under `python -m itds_agent`. This
was discovered and fixed during Phase 1O validation by actually running the
build and starting the resulting executables (see Verified in this
environment, below) - do not assume a `--onedir` PyInstaller build of a
package submodule works without this pattern.

Build outputs (`build/dist/`, `build/work/`, `build/*.spec`) are excluded
from source control by `.gitignore`; only the build *scripts*
(`build_exe.py`, `requirements-build.txt`, `entrypoints/*.py`) are tracked.

Nothing in the frozen executables embeds a credential, a production API URL,
or any other secret - both binaries read `config.json`/`credential.bin`
externally at runtime exactly like console mode.

### Verified in this environment

- `python build/build_exe.py` completed successfully on this Windows
  development machine and produced both executables.
- `ITDSAgentEnroll.exe --clear` ran to completion (exit code 0).
- `ITDSAgent.exe <unrecognized-argument>` reached
  `win32serviceutil.HandleCommandLine`'s usage output (proving the
  service module now imports and initializes correctly when frozen,
  rather than failing with the relative-import error described above).
- A text scan of the frozen binary/support files found no embedded
  production URLs, credentials, or other secrets (only the standard
  Windows application-manifest XML schema URL).

### Not verified in this environment

- A full `debug`-mode run of `ITDSAgent.exe` against a real enrolled
  device/API was not performed (no live ITDS server was available in this
  session); only import/startup-path correctness was verified.
- Installing the frozen `ITDSAgent.exe` as an actual Windows service via
  `installer/install.py` and observing it run under the SCM as
  `LocalService` end-to-end was not performed in this session (see
  docs/security/windows-agent-security.md for exactly what credential
  protection testing was and was not completed).

## Runtime behavior summary

- Exactly one `AgentRuntime` loop runs per process:
  `service/lifecycle.py::ServiceLifecycle.start()` is idempotent and is a
  no-op if already running, and `AgentRuntime.run()` itself refuses a
  second concurrent invocation via an internal lock, raising `RuntimeError`
  rather than silently starting a duplicate heartbeat loop.
- `AgentRuntime.tick()` distinguishes communication failures
  (`AgentCommunicationError`, e.g. a transient network/API outage) from
  unexpected defects: communication failures are logged and the runtime
  keeps running (self-heals on the next scheduled heartbeat), while any
  other unexpected exception transitions the runtime to `RuntimeState.ERROR`
  and the run loop exits (fail safe rather than looping on an unknown
  defect).
- `ServiceLifecycle.stop()` signals the runtime and joins its background
  thread with a bounded timeout (default 30s), so shutdown does not hang
  indefinitely and does not leave the thread running after the service
  reports `SERVICE_STOPPED`.
- If the runtime thread exits without a requested stop, the service host
  reports `SERVICE_STOPPED` with a non-zero exit code so the configured SCM
  failure-recovery actions can run. A requested graceful stop reports a
  successful stop instead.
- The HTTPS communication client (`itds_agent/communication/client.py`,
  reused unchanged from Phase 1M) already provides bounded timeouts,
  bounded retries with backoff for transient failures, and does not retry
  authentication failures.

## Windows Event Log

Setting `use_event_log=True` (done automatically when running as the
Windows service, not in console mode) additively registers an
`NTEventLogHandler`. If Event Log registration is unavailable (e.g. missing
registry source), the agent logs a warning and continues with file logging
only - Event Log is never the sole diagnostic channel.

## Known limitations of this developer-machine validation

- DPAPI credential decryption under the actual `LocalService` account (as
  opposed to the interactive Administrator account used for enrollment) was
  not directly tested by installing and running the Windows service in this
  session. See docs/security/windows-agent-security.md for the design
  change made to address this (`CRYPTPROTECT_LOCAL_MACHINE`) and what
  remains unverified.
- The full elevated install → enroll → start → stop → uninstall lifecycle
  was not executed end-to-end against a real Windows service in this
  session (installer `--help` invocations, ACL creation in a scratch
  directory, and AST-level verification of the exact `InstallService` call
  were performed instead - see the security document for details).
