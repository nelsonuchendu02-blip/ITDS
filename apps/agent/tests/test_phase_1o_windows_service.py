"""Phase 1O tests: Windows service lifecycle, configuration loading,
credential protection, log redaction, shared bootstrap wiring, console
entry point, and the security boundaries introduced for the production
Windows endpoint service.

`security/credential_store.py` and `service/host.py` are the only
pywin32-dependent modules. This file exercises `credential_store.py`
against a fake `win32crypt` module (injected via `sys.modules`) so these
tests run on non-Windows CI too; `service/host.py` itself is intentionally
thin (SCM glue only) and is covered by the "no prohibited execution"
static scan below plus manual verification on Windows.
"""
from __future__ import annotations

import ast
import importlib.util
import logging
import re
import stat
import sys
import threading
import time
import types
from pathlib import Path

import pytest

from itds_agent.config.loader import (
    ConfigurationError,
    _read_config_file,
    load_settings,
)
from itds_agent.config.settings import AgentSettings
from itds_agent.core.bootstrap import build_runtime
from itds_agent.core.runtime import AgentRuntime, RuntimeState
from itds_agent.communication.client import AgentCommunicationError
from itds_agent.logging.redaction import RedactingFilter, redact
from itds_agent.security import CredentialStore, CredentialStoreError
from itds_agent.service.lifecycle import ServiceLifecycle, ServiceLifecycleError

AGENT_ROOT = Path(__file__).parents[1]


def _settings(**overrides) -> AgentSettings:
    values = dict(
        api_base_url="https://api.example.test",
        credential="cred-prefix.secret",
        agent_version="9.9.9",
        heartbeat_interval_seconds=10,
        request_timeout_seconds=7,
    )
    values.update(overrides)
    return AgentSettings(**values)


# ---------------------------------------------------------------------------
# config/loader.py
# ---------------------------------------------------------------------------


def test_read_config_file_rejects_forbidden_secret_keys(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"api_base_url": "https://x.test", "credential": "leaked"}')
    with pytest.raises(ConfigurationError, match="secret fields"):
        _read_config_file(config)


def test_read_config_file_rejects_unknown_keys(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"allow_destructive_actions": true}')
    with pytest.raises(ConfigurationError, match="unsupported fields"):
        _read_config_file(config)


def test_read_config_file_missing_file_returns_empty(tmp_path):
    assert _read_config_file(tmp_path / "missing.json") == {}


def test_load_settings_applies_env_overrides_and_credential(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"api_base_url": "https://from-file.test", "heartbeat_interval_seconds": 60}')

    class FakeStore:
        def load(self):
            return "prefix.secret"

    settings = load_settings(
        config_file=config,
        credential_store=FakeStore(),
        env={"ITDS_AGENT_API_BASE_URL": "https://from-env.test"},
    )
    assert settings.api_base_url == "https://from-env.test"
    assert settings.heartbeat_interval_seconds == 60
    assert settings.credential == "prefix.secret"


def test_load_settings_requires_an_enrolled_credential(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"api_base_url": "https://x.test"}')

    class EmptyStore:
        def load(self):
            return None

    with pytest.raises(ConfigurationError, match="no agent credential is enrolled"):
        load_settings(config_file=config, credential_store=EmptyStore(), env={})


def test_load_settings_wraps_credential_store_errors(tmp_path):
    config = tmp_path / "config.json"
    config.write_text('{"api_base_url": "https://x.test"}')

    class BrokenStore:
        def load(self):
            raise CredentialStoreError("boom")

    with pytest.raises(ConfigurationError, match="unable to load the protected agent credential"):
        load_settings(config_file=config, credential_store=BrokenStore(), env={})


# ---------------------------------------------------------------------------
# security/credential_store.py (mocked win32crypt so this runs off Windows)
# ---------------------------------------------------------------------------


class _FakeWin32Crypt:
    """Minimal stand-in for the pywin32 `win32crypt` DPAPI surface."""

    def CryptProtectData(self, data, description, entropy, reserved, prompt, flags):
        return b"PROTECTED:" + entropy + b":" + data

    def CryptUnprotectData(self, blob, entropy, reserved, prompt, flags):
        prefix = b"PROTECTED:" + entropy + b":"
        if not blob.startswith(prefix):
            raise ValueError("bad blob")
        return "ITDS agent credential", blob[len(prefix):]


@pytest.fixture
def credential_store(tmp_path, monkeypatch):
    fake_module = _FakeWin32Crypt()
    monkeypatch.setattr(
        CredentialStore, "_dpapi", lambda self: fake_module, raising=True
    )
    return CredentialStore(tmp_path / "credential.bin")


def test_credential_store_round_trips_via_dpapi(credential_store):
    credential_store.save("prefix.super-secret")
    assert credential_store.exists()
    assert credential_store.load() == "prefix.super-secret"


def test_credential_store_load_missing_file_returns_none(credential_store):
    assert credential_store.load() is None


def test_credential_store_rejects_empty_credential(credential_store):
    with pytest.raises(CredentialStoreError):
        credential_store.save("")


def test_credential_store_clear_removes_file(credential_store):
    credential_store.save("prefix.secret")
    credential_store.clear()
    assert not credential_store.exists()
    # clear() is safe to call again (e.g. during uninstall) even if already gone.
    credential_store.clear()


def test_credential_store_unprotect_failure_does_not_leak_credential(tmp_path, monkeypatch):
    class ExplodingWin32Crypt:
        def CryptUnprotectData(self, *args, **kwargs):
            raise OSError("corrupt blob")

    monkeypatch.setattr(
        CredentialStore, "_dpapi", lambda self: ExplodingWin32Crypt(), raising=True
    )
    store = CredentialStore(tmp_path / "credential.bin")
    store.credential_path.write_bytes(b"garbage")
    with pytest.raises(CredentialStoreError) as error:
        store.load()
    assert "garbage" not in str(error.value)


def test_credential_store_uses_local_machine_scope_not_per_user(tmp_path, monkeypatch):
    """The service runs as LocalService but credentials are enrolled by an
    interactive Administrator; only CRYPTPROTECT_LOCAL_MACHINE (flag 0x4)
    lets the service account decrypt what the enrolling account protected.
    Per-user (flag 0) protection would be unreadable by the service."""

    seen_flags = []

    class RecordingWin32Crypt:
        def CryptProtectData(self, data, description, entropy, reserved, prompt, flags):
            seen_flags.append(flags)
            return b"PROTECTED:" + data

        def CryptUnprotectData(self, blob, entropy, reserved, prompt, flags):
            seen_flags.append(flags)
            return "ITDS agent credential", blob[len(b"PROTECTED:"):]

    monkeypatch.setattr(
        CredentialStore, "_dpapi", lambda self: RecordingWin32Crypt(), raising=True
    )
    store = CredentialStore(tmp_path / "credential.bin")
    store.save("prefix.secret")
    store.load()

    CRYPTPROTECT_LOCAL_MACHINE = 0x4
    assert seen_flags == [CRYPTPROTECT_LOCAL_MACHINE, CRYPTPROTECT_LOCAL_MACHINE]


def test_credential_store_raises_off_windows_without_pywin32(tmp_path, monkeypatch):
    monkeypatch.setattr(
        CredentialStore,
        "_dpapi",
        lambda self: (_ for _ in ()).throw(
            CredentialStoreError("DPAPI credential protection requires pywin32")
        ),
    )
    store = CredentialStore(tmp_path / "credential.bin")
    with pytest.raises(CredentialStoreError):
        store.save("prefix.secret")


# ---------------------------------------------------------------------------
# logging/redaction.py
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "secret"),
    [
        ("X-Agent-Credential: prefix.super-secret-value", "super-secret-value"),
        ("Authorization=Bearer-abc123", "abc123"),
        ("credential: prefix.super-secret-value", "super-secret-value"),
        ("password=hunter2", "hunter2"),
        ("secret: abc-123", "abc-123"),
        ("token=xyz-789", "xyz-789"),
    ],
)
def test_redact_hides_credential_shaped_values(message, secret):
    result = redact(message)
    assert "[redacted]" in result
    assert secret not in result


def test_redacting_filter_scrubs_log_records_and_args():
    filter_ = RedactingFilter()
    record = logging.LogRecord(
        name="itds-agent",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="request headers: %s",
        args=("X-Agent-Credential: prefix.super-secret",),
        exc_info=None,
    )
    assert filter_.filter(record) is True
    assert "super-secret" not in record.args[0]


def test_redacting_filter_scrubs_non_string_args_such_as_exceptions():
    """Regression: a non-string arg (e.g. an exception passed to
    `logger.warning("...: %s", exc)`) must be redacted by the filter, not
    left untouched until `%`-formatting stringifies it later (which would
    bypass redaction entirely)."""

    class _FakeError(Exception):
        def __str__(self):
            return "token=super-secret-value failure detail"

    filter_ = RedactingFilter()
    record = logging.LogRecord(
        name="itds-agent",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="heartbeat failed: %s",
        args=(_FakeError(),),
        exc_info=None,
    )
    assert filter_.filter(record) is True
    assert "super-secret-value" not in record.getMessage()


# ---------------------------------------------------------------------------
# core/runtime.py error differentiation (Phase 1O behavior change)
# ---------------------------------------------------------------------------


def test_communication_errors_do_not_transition_to_error_state():
    def failing_heartbeat(_payload):
        raise AgentCommunicationError("network unreachable")

    runtime = AgentRuntime(_settings(), failing_heartbeat)
    assert runtime.run(max_cycles=2) == 2
    assert runtime.state is RuntimeState.STOPPED


def test_unexpected_errors_still_transition_to_error_state():
    def failing_heartbeat(_payload):
        raise RuntimeError("unexpected defect")

    runtime = AgentRuntime(_settings(), failing_heartbeat)
    assert runtime.run(max_cycles=1) == 1
    assert runtime.state is RuntimeState.ERROR


def test_run_rejects_a_second_concurrent_call():
    runtime = AgentRuntime(_settings(), lambda payload: payload)
    runtime._run_lock.acquire()
    try:
        with pytest.raises(RuntimeError, match="already active"):
            runtime.run(max_cycles=1)
    finally:
        runtime._run_lock.release()


# ---------------------------------------------------------------------------
# core/bootstrap.py
# ---------------------------------------------------------------------------


def test_build_runtime_wires_settings_logging_and_client(tmp_path, monkeypatch):
    monkeypatch.setenv("ITDS_AGENT_DATA_DIR", str(tmp_path))
    runtime = build_runtime(settings=_settings(log_directory=str(tmp_path / "logs")))
    assert isinstance(runtime, AgentRuntime)
    assert runtime.logger.name == "itds-agent"
    assert runtime.settings.agent_version == "9.9.9"


def test_build_runtime_propagates_configuration_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("ITDS_AGENT_DATA_DIR", str(tmp_path))

    class BrokenStore:
        def load(self):
            return None

    monkeypatch.setattr(
        "itds_agent.core.bootstrap.load_settings",
        lambda: (_ for _ in ()).throw(ConfigurationError("no agent credential is enrolled")),
    )
    with pytest.raises(ConfigurationError):
        build_runtime()


# ---------------------------------------------------------------------------
# service/lifecycle.py (pywin32-free, unit-testable)
# ---------------------------------------------------------------------------


def _fake_runtime_factory(calls):
    def factory():
        runtime = AgentRuntime(_settings(heartbeat_interval_seconds=10), lambda payload: calls.append(payload))
        runtime._stop_event.wait = lambda interval: False  # run until stop() is called
        return runtime

    return factory


def test_service_lifecycle_start_stop_runs_and_terminates_cleanly():
    calls = []
    lifecycle = ServiceLifecycle(runtime_factory=_fake_runtime_factory(calls))
    lifecycle.start()
    try:
        assert lifecycle.is_running()
        for _ in range(50):
            if calls:
                break
            time.sleep(0.05)
        assert calls, "expected at least one heartbeat before stop"
    finally:
        lifecycle.stop(join_timeout=5.0)
    assert not lifecycle.is_running()
    assert lifecycle.wait(timeout=0)
    assert not lifecycle.failed


def test_service_lifecycle_start_is_idempotent():
    calls = []
    factory_calls = []

    def factory():
        factory_calls.append(None)
        return _fake_runtime_factory(calls)()

    lifecycle = ServiceLifecycle(runtime_factory=factory)
    lifecycle.start()
    first_runtime = lifecycle.runtime
    lifecycle.start()  # second call must be a no-op, not a second thread/runtime
    try:
        assert lifecycle.runtime is first_runtime
        assert len(factory_calls) == 1
    finally:
        lifecycle.stop(join_timeout=5.0)
    assert len(factory_calls) == 1


def test_service_lifecycle_reports_unexpected_runtime_exit_as_failure():
    def broken_heartbeat(_payload):
        raise RuntimeError("unexpected runtime defect")

    runtime = AgentRuntime(_settings(), broken_heartbeat)
    lifecycle = ServiceLifecycle(runtime_factory=lambda: runtime)

    lifecycle.start()

    assert lifecycle.wait(timeout=5.0)
    assert runtime.state is RuntimeState.ERROR
    assert lifecycle.failed
    assert not lifecycle.is_running()


def test_service_lifecycle_graceful_stop_is_not_a_runtime_failure():
    lifecycle = ServiceLifecycle(runtime_factory=_fake_runtime_factory([]))
    lifecycle.start()

    lifecycle.stop(join_timeout=5.0)

    assert lifecycle.wait(timeout=0)
    assert not lifecycle.failed
    assert not lifecycle.is_running()


def test_service_lifecycle_stop_during_startup_does_not_launch_runtime_loop():
    start_entered = threading.Event()
    allow_start = threading.Event()
    heartbeat_calls = []

    class GatedRuntime(AgentRuntime):
        def start(self):
            start_entered.set()
            assert allow_start.wait(timeout=5.0)
            super().start()

    runtime = GatedRuntime(
        _settings(),
        lambda payload: heartbeat_calls.append(payload),
    )
    lifecycle = ServiceLifecycle(runtime_factory=lambda: runtime)
    start_thread = threading.Thread(target=lifecycle.start)
    start_thread.start()
    assert start_entered.wait(timeout=5.0)

    lifecycle.stop(join_timeout=0.01)
    allow_start.set()
    start_thread.join(timeout=5.0)

    assert not start_thread.is_alive()
    assert lifecycle.wait(timeout=5.0)
    assert not lifecycle.failed
    assert heartbeat_calls == []


def test_service_lifecycle_start_raises_service_error_on_bad_configuration():
    def bad_factory():
        raise ConfigurationError("no agent credential is enrolled")

    lifecycle = ServiceLifecycle(runtime_factory=bad_factory)
    with pytest.raises(ServiceLifecycleError):
        lifecycle.start()
    assert not lifecycle.is_running()


def test_service_lifecycle_stop_before_start_is_safe():
    lifecycle = ServiceLifecycle(runtime_factory=_fake_runtime_factory([]))
    lifecycle.stop(join_timeout=1.0)  # must not raise


def _load_windows_service_host_with_fakes(monkeypatch):
    statuses = []

    class FakeServiceFramework:
        def __init__(self, _args):
            pass

        def ReportServiceStatus(self, status, **kwargs):
            statuses.append((status, kwargs))

    win32service = types.ModuleType("win32service")
    win32service.SERVICE_STOP_PENDING = 3
    win32service.SERVICE_STOPPED = 1
    win32service.SERVICE_RUNNING = 4

    win32event = types.ModuleType("win32event")
    win32event.INFINITE = -1
    win32event.WAIT_OBJECT_0 = 0
    win32event.WAIT_TIMEOUT = 258
    win32event.CreateEvent = lambda *_args: threading.Event()
    win32event.SetEvent = lambda event: event.set()

    def wait_for_single_object(event, timeout):
        wait_timeout = None if timeout == win32event.INFINITE else timeout / 1000
        return (
            win32event.WAIT_OBJECT_0
            if event.wait(wait_timeout)
            else win32event.WAIT_TIMEOUT
        )

    win32event.WaitForSingleObject = wait_for_single_object

    win32serviceutil = types.ModuleType("win32serviceutil")
    win32serviceutil.ServiceFramework = FakeServiceFramework
    win32serviceutil.HandleCommandLine = lambda _service: None

    servicemanager = types.ModuleType("servicemanager")
    servicemanager.EVENTLOG_INFORMATION_TYPE = 4
    servicemanager.PYS_SERVICE_STARTED = 100
    servicemanager.PYS_SERVICE_STOPPED = 101
    servicemanager.LogMsg = lambda *_args: None
    servicemanager.LogErrorMsg = lambda *_args: None
    servicemanager.Initialize = lambda: None
    servicemanager.PrepareToHostSingle = lambda *_args: None
    servicemanager.StartServiceCtrlDispatcher = lambda: None

    for name, module in (
        ("servicemanager", servicemanager),
        ("win32event", win32event),
        ("win32service", win32service),
        ("win32serviceutil", win32serviceutil),
    ):
        monkeypatch.setitem(sys.modules, name, module)

    host_path = AGENT_ROOT / "itds_agent" / "service" / "host.py"
    spec = importlib.util.spec_from_file_location(
        "itds_agent.service._host_test", host_path
    )
    assert spec is not None and spec.loader is not None
    host_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(host_module)
    return host_module, statuses, win32service


def test_windows_service_reports_failed_runtime_as_stopped_nonzero(monkeypatch):
    host_module, statuses, win32service = _load_windows_service_host_with_fakes(monkeypatch)

    def broken_heartbeat(_payload):
        raise RuntimeError("unexpected runtime defect")

    runtime = AgentRuntime(_settings(), broken_heartbeat)
    service = host_module.ITDSAgentService([])
    service._lifecycle = ServiceLifecycle(runtime_factory=lambda: runtime)

    service_thread = threading.Thread(target=service.SvcDoRun)
    service_thread.start()
    service_thread.join(timeout=5.0)

    assert not service_thread.is_alive(), "Failed service host did not return to its dispatcher."
    assert (win32service.SERVICE_RUNNING, {}) in statuses
    assert statuses[-1] == (
        win32service.SERVICE_STOPPED,
        {"win32ExitCode": 1},
    )
    assert service._lifecycle.wait(timeout=0)
    assert not service._lifecycle.is_running(), "Runtime worker survived service failure."


def test_windows_service_graceful_stop_reports_stopped_zero(monkeypatch):
    host_module, statuses, win32service = _load_windows_service_host_with_fakes(monkeypatch)
    service = host_module.ITDSAgentService([])
    service._lifecycle = ServiceLifecycle(runtime_factory=_fake_runtime_factory([]))

    service_thread = threading.Thread(target=service.SvcDoRun)
    service_thread.start()
    for _ in range(100):
        if (win32service.SERVICE_RUNNING, {}) in statuses:
            break
        time.sleep(0.01)
    assert (win32service.SERVICE_RUNNING, {}) in statuses

    service.SvcStop()
    service_thread.join(timeout=5.0)

    assert not service_thread.is_alive()
    assert statuses[-1] == (win32service.SERVICE_STOPPED, {})


def test_windows_service_stop_event_preserves_runtime_failure_exit_code(monkeypatch):
    host_module, statuses, win32service = _load_windows_service_host_with_fakes(monkeypatch)
    service = host_module.ITDSAgentService([])

    class FailingDuringStopLifecycle:
        failed = False

        def start(self):
            pass

        def wait(self, timeout=None):
            return False

        def stop(self):
            self.failed = True

    service._lifecycle = FailingDuringStopLifecycle()
    service_thread = threading.Thread(target=service.SvcDoRun)
    service_thread.start()
    for _ in range(100):
        if (win32service.SERVICE_RUNNING, {}) in statuses:
            break
        time.sleep(0.01)
    assert (win32service.SERVICE_RUNNING, {}) in statuses

    service.SvcStop()
    service_thread.join(timeout=5.0)

    assert not service_thread.is_alive()
    assert statuses[-1] == (
        win32service.SERVICE_STOPPED,
        {"win32ExitCode": 1},
    )


# ---------------------------------------------------------------------------
# Security boundary: prohibited execution / secret-literal static scan
# ---------------------------------------------------------------------------

_PROHIBITED_PATTERNS = [
    re.compile(r"\bimport subprocess\b"),
    re.compile(r"\bsubprocess\.\w"),
    re.compile(r"\bos\.system\b"),
    re.compile(r"\bos\.popen\b"),
    re.compile(r"\bshell\s*=\s*True\b"),
    re.compile(r"\bwmic\b", re.IGNORECASE),
    re.compile(r"\bwin32com\.client\b"),
    re.compile(r"\bparamiko\b"),
    re.compile(r"\bssh\b", re.IGNORECASE),
]

#: The build script legitimately shells out to PyInstaller with a fixed,
#: non-shell argv (no user input, `shell=` never set) - it is packaging
#: tooling, not part of the shipped agent, and is explicitly reviewed here
#: rather than excluded silently.
_ALLOWED_SUBPROCESS_FILES = {AGENT_ROOT / "build" / "build_exe.py"}

_SOURCE_DIRS = ["itds_agent", "installer", "build"]
_PROHIBITED_MODULES = {
    "subprocess",
    "win32com.client",
    "paramiko",
    "wmi",
}
_PROHIBITED_CALLS = {
    "os.system",
    "os.popen",
    "os.startfile",
    "os.execv",
    "os.execve",
    "os.execl",
    "os.execlp",
    "os.execlpe",
    "os.execle",
    "os.execvp",
    "os.execvpe",
    "os.spawnl",
    "os.spawnle",
    "os.spawnlp",
    "os.spawnlpe",
    "os.spawnv",
    "os.spawnve",
    "os.spawnvp",
    "os.spawnvpe",
    "win32api.ShellExecute",
    "win32api.ShellExecuteEx",
    "win32process.CreateProcess",
    "win32process.CreateProcessAsUser",
    "ctypes.windll.shell32.ShellExecuteA",
    "ctypes.windll.shell32.ShellExecuteW",
    "ctypes.windll.shell32.ShellExecuteExA",
    "ctypes.windll.shell32.ShellExecuteExW",
    "ctypes.windll.kernel32.WinExec",
    "ctypes.windll.kernel32.CreateProcessA",
    "ctypes.windll.kernel32.CreateProcessW",
    "exec",
    "eval",
    "builtins.exec",
    "builtins.eval",
    "__import__",
    "builtins.__import__",
    "importlib.import_module",
}
_PROHIBITED_SUBPROCESS_CALLS = {
    "call",
    "check_call",
    "check_output",
    "getoutput",
    "getstatusoutput",
    "Popen",
    "run",
}


def _dotted_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _dotted_name(node.value)
        return f"{parent}.{node.attr}" if parent else None
    return None


def _find_prohibited_execution(source: str) -> list[str]:
    tree = ast.parse(source)
    module_aliases = {}
    function_aliases = {}
    offenders = []

    def resolve_name(node):
        name = _dotted_name(node)
        if name in function_aliases:
            return function_aliases[name]
        if name:
            root, separator, suffix = name.partition(".")
            if root in module_aliases:
                return module_aliases[root] + (f".{suffix}" if separator else "")
        return name

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                if any(
                    module == prohibited or module.startswith(f"{prohibited}.")
                    for prohibited in _PROHIBITED_MODULES
                ):
                    offenders.append(f"line {node.lineno}: import {module}")
                module_aliases[alias.asname or module.split(".")[0]] = (
                    module if alias.asname else module.split(".")[0]
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imported = f"{module}.{alias.name}" if module else alias.name
                if any(
                    imported == prohibited or imported.startswith(f"{prohibited}.")
                    for prohibited in _PROHIBITED_MODULES
                ):
                    offenders.append(f"line {node.lineno}: import {imported}")
                if alias.name == "*":
                    if module == "os":
                        offenders.append(f"line {node.lineno}: wildcard import from os")
                    continue
                local_name = alias.asname or alias.name
                if alias.name in _PROHIBITED_SUBPROCESS_CALLS and module == "subprocess":
                    function_aliases[local_name] = imported
                elif module in {"os", "win32api", "win32process"}:
                    function_aliases[local_name] = imported
                elif module:
                    module_aliases[local_name] = imported

    assignments = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
    ]
    while assignments:
        remaining = []
        for node in assignments:
            value = node.value
            resolved = resolve_name(value)
            if resolved not in _PROHIBITED_CALLS and not any(
                resolved == "subprocess." + call
                for call in _PROHIBITED_SUBPROCESS_CALLS
            ):
                remaining.append(node)
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    function_aliases[target.id] = resolved
        if len(remaining) == len(assignments):
            break
        assignments = remaining

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = resolve_name(node.func)
        if (
            name in _PROHIBITED_CALLS
            or name in {"subprocess." + call for call in _PROHIBITED_SUBPROCESS_CALLS}
        ):
            offenders.append(f"line {node.lineno}: call {name}")
        if any(
            keyword.arg == "shell"
            and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is False)
            for keyword in node.keywords
        ):
            offenders.append(f"line {node.lineno}: shell execution enabled")

    return offenders


def _iter_source_files():
    for directory in _SOURCE_DIRS:
        yield from (AGENT_ROOT / directory).rglob("*.py")


def test_no_prohibited_execution_patterns_in_agent_source():
    offenders = []
    for path in _iter_source_files():
        if path in _ALLOWED_SUBPROCESS_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        offenders.extend(
            f"{path}: {offender}" for offender in _find_prohibited_execution(text)
        )
        for pattern in _PROHIBITED_PATTERNS:
            if pattern.search(text):
                offenders.append(f"{path}: {pattern.pattern}")
    assert not offenders, f"prohibited execution patterns found: {offenders}"


@pytest.mark.parametrize(
    "source",
    [
        "import subprocess as process\nprocess.run(['cmd'])",
        "from subprocess import run as launch\nlaunch(['cmd'])",
        "import os as operating_system\noperating_system.system('cmd')",
        "from os import popen as launch\nlaunch('cmd')",
        "from win32com import client as automation\nautomation.Dispatch('WScript.Shell')",
        "import subprocess\nsubprocess.run(['cmd'], shell=True)",
        "eval('print(1)')",
        "import builtins\nbuiltins.eval('print(1)')",
        "import os\nlaunch = os.system\nlaunch('cmd')",
        "__import__('subprocess')",
        "import importlib\nimportlib.import_module('subprocess')",
    ],
)
def test_security_scan_detects_aliased_execution(source):
    assert _find_prohibited_execution(source)


def test_security_scan_allows_non_execution_os_helpers():
    assert not _find_prohibited_execution("import os\nos.getenv('ITDS_AGENT_API_BASE_URL')")
    assert not _find_prohibited_execution("launch(['tool'], shell=False)")


def test_build_script_subprocess_call_uses_fixed_argv_never_shell():
    tree = ast.parse((AGENT_ROOT / "build" / "build_exe.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "run":
            for keyword in node.keywords:
                if keyword.arg == "shell":
                    assert keyword.value.value is False


def test_no_plausible_secret_literals_in_agent_source():
    # Looks for high-entropy-looking assigned string literals next to
    # credential-shaped variable names; real code only ever loads
    # credentials from the protected store or environment, never a literal.
    suspect = re.compile(
        r"(?i)(password|secret|api_key|access_token)\s*=\s*[\"'][^\"']{8,}[\"']"
    )
    offenders = []
    for path in _iter_source_files():
        text = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if suspect.search(line) and "os.environ" not in line and "getenv" not in line:
                offenders.append(f"{path}:{line_no}")
    assert not offenders, f"possible secret literal(s) found: {offenders}"


# ---------------------------------------------------------------------------
# installer/ - Windows-only; skipped (not failed) off Windows.
# ---------------------------------------------------------------------------

pytestmark_installer = pytest.mark.skipif(
    sys.platform != "win32", reason="installer/ only imports on Windows (pywin32-backed)"
)


@pytestmark_installer
def test_installer_service_identity_is_least_privilege():
    import installer.common as installer_common

    assert installer_common.SERVICE_ACCOUNT == r"NT AUTHORITY\LocalService"
    assert installer_common.SERVICE_NAME == "ITDSAgent"
    assert installer_common.SERVICE_DISPLAY_NAME == "ITDS Endpoint Agent"


@pytestmark_installer
def test_install_service_call_never_passes_a_real_password():
    """AST-level (not text/grep) proof that `InstallService(...)` always
    passes the literal `password=None` - no account password is ever
    collected, stored, or forwarded by the installer."""
    tree = ast.parse((AGENT_ROOT / "installer" / "install.py").read_text(encoding="utf-8"))
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "InstallService"
    )
    keywords = {kw.arg: kw.value for kw in call.keywords}
    assert set(keywords) >= {"startType", "userName", "password", "exeName", "description"}
    assert isinstance(keywords["password"], ast.Constant)
    assert keywords["password"].value is None


@pytestmark_installer
def test_install_package_copies_the_full_bundle_to_the_install_directory(tmp_path, monkeypatch):
    import installer.install as install_module

    monkeypatch.setattr(install_module, "_ensure_service_stopped", lambda: None)
    source_dir = tmp_path / "build" / "ITDSAgent"
    install_dir = tmp_path / "Program Files" / "ITDS" / "Agent"
    (source_dir / "_internal").mkdir(parents=True)
    executable = source_dir / "ITDSAgent.exe"
    executable.write_bytes(b"service")
    (source_dir / "_internal" / "python312.dll").write_bytes(b"runtime")

    installed_exe = install_module._install_package(executable, install_dir)

    assert installed_exe == install_dir / "ITDSAgent.exe"
    assert installed_exe.read_bytes() == b"service"
    assert (install_dir / "_internal" / "python312.dll").read_bytes() == b"runtime"


@pytestmark_installer
def test_install_package_replacement_removes_stale_files(tmp_path, monkeypatch):
    import installer.install as install_module

    monkeypatch.setattr(install_module, "_ensure_service_stopped", lambda: None)
    source_dir = tmp_path / "build" / "ITDSAgent"
    install_dir = tmp_path / "Program Files" / "ITDS" / "Agent"
    source_dir.mkdir(parents=True)
    install_dir.mkdir(parents=True)
    (source_dir / "ITDSAgent.exe").write_bytes(b"new service")
    (source_dir / "_internal").mkdir()
    (source_dir / "_internal" / "runtime.dll").write_bytes(b"runtime")
    (install_dir / "ITDSAgent.exe").write_bytes(b"old service")
    (install_dir / "stale-old-module.dll").write_bytes(b"stale")

    installed_exe = install_module._install_package(
        source_dir / "ITDSAgent.exe", install_dir
    )

    assert installed_exe.read_bytes() == b"new service"
    assert (install_dir / "_internal" / "runtime.dll").is_file()
    assert not (install_dir / "stale-old-module.dll").exists()


@pytestmark_installer
def test_install_package_refuses_destination_reparse_point(tmp_path, monkeypatch):
    import installer.install as install_module

    monkeypatch.setattr(install_module, "_ensure_service_stopped", lambda: None)
    source_dir = tmp_path / "build" / "ITDSAgent"
    install_dir = tmp_path / "Program Files" / "ITDS" / "Agent"
    source_dir.mkdir(parents=True)
    install_dir.mkdir(parents=True)
    (source_dir / "ITDSAgent.exe").write_bytes(b"service")
    original_lstat = Path.lstat
    reparse_attributes = types.SimpleNamespace(
        st_mode=stat.S_IFDIR,
        st_file_attributes=0x400,
    )

    def fake_lstat(path):
        if path == install_dir:
            return reparse_attributes
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)

    with pytest.raises(ValueError, match="reparse point"):
        install_module._install_package(source_dir / "ITDSAgent.exe", install_dir)


@pytestmark_installer
def test_installer_registers_service_from_program_files_package(tmp_path, monkeypatch):
    import installer.install as install_module

    source_dir = tmp_path / "build" / "ITDSAgent"
    install_dir = tmp_path / "Program Files" / "ITDS" / "Agent"
    source_dir.mkdir(parents=True)
    executable = source_dir / "ITDSAgent.exe"
    executable.write_bytes(b"service")
    registered_paths = []
    monkeypatch.setattr(install_module, "DEFAULT_INSTALL_DIR", install_dir)
    monkeypatch.setattr(install_module, "require_admin", lambda: None)
    monkeypatch.setattr(install_module, "_ensure_service_stopped", lambda: None)
    monkeypatch.setattr(install_module, "secure_data_directories", lambda: None)
    monkeypatch.setattr(install_module, "_register_service", registered_paths.append)

    assert install_module.main(["--exe", str(executable)]) == 0
    assert registered_paths == [install_dir / "ITDSAgent.exe"]


@pytestmark_installer
def test_installer_refuses_package_replacement_when_service_is_not_stopped(tmp_path, monkeypatch):
    import installer.install as install_module

    source_dir = tmp_path / "source"
    install_dir = tmp_path / "installation"
    source_dir.mkdir()
    install_dir.mkdir()
    (source_dir / "ITDSAgent.exe").write_bytes(b"new service")
    (install_dir / "ITDSAgent.exe").write_bytes(b"existing package")

    service = types.ModuleType("win32service")
    service.SC_MANAGER_CONNECT = 1
    service.SERVICE_QUERY_STATUS = 2
    service.SERVICE_STOPPED = 1
    service.SC_STATUS_PROCESS_INFO = 0
    service.OpenSCManager = lambda *_args: "scm"
    service.OpenService = lambda *_args: "service"
    service.QueryServiceStatusEx = lambda *_args: {
        "CurrentState": 4,
        "ProcessId": 1234,
    }
    service.CloseServiceHandle = lambda _handle: None
    monkeypatch.setitem(sys.modules, "win32service", service)

    with pytest.raises(RuntimeError, match="has not fully stopped"):
        install_module._install_package(source_dir / "ITDSAgent.exe", install_dir)
    assert (install_dir / "ITDSAgent.exe").read_bytes() == b"existing package"


@pytestmark_installer
def test_installer_rejects_stopped_service_with_live_process_id(monkeypatch):
    import installer.install as install_module

    service = types.ModuleType("win32service")
    service.SC_MANAGER_CONNECT = 1
    service.SERVICE_QUERY_STATUS = 2
    service.SERVICE_STOPPED = 1
    service.OpenSCManager = lambda *_args: "scm"
    service.OpenService = lambda *_args: "service"
    service.QueryServiceStatusEx = lambda *_args: {
        "CurrentState": service.SERVICE_STOPPED,
        "ProcessId": 1234,
    }
    service.CloseServiceHandle = lambda _handle: None
    monkeypatch.setitem(sys.modules, "win32service", service)

    with pytest.raises(RuntimeError, match="process_id=1234"):
        install_module._ensure_service_stopped()


@pytestmark_installer
def test_installer_allows_replacement_when_service_and_process_are_stopped(monkeypatch):
    import installer.install as install_module

    service = types.ModuleType("win32service")
    service.SC_MANAGER_CONNECT = 1
    service.SERVICE_QUERY_STATUS = 2
    service.SERVICE_STOPPED = 1
    service.OpenSCManager = lambda *_args: "scm"
    service.OpenService = lambda *_args: "service"
    service.QueryServiceStatusEx = lambda *_args: {
        "CurrentState": service.SERVICE_STOPPED,
        "ProcessId": 0,
    }
    service.CloseServiceHandle = lambda _handle: None
    monkeypatch.setitem(sys.modules, "win32service", service)

    install_module._ensure_service_stopped()


@pytestmark_installer
def test_recovery_actions_restart_after_non_crash_service_failure(monkeypatch):
    import installer.install as install_module

    service = types.ModuleType("win32service")
    service.SC_MANAGER_ALL_ACCESS = 1
    service.SERVICE_ALL_ACCESS = 2
    service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO = 3
    service.SERVICE_CONFIG_FAILURE_ACTIONS = 4
    service.SERVICE_CONFIG_FAILURE_ACTIONS_FLAG = 5
    service.SC_ACTION_RESTART = 1
    service.SC_ACTION_NONE = 0
    calls = []
    service.OpenSCManager = lambda *_args: "scm"
    service.OpenService = lambda *_args: "service"
    service.ChangeServiceConfig2 = lambda *args: calls.append(args)
    service.CloseServiceHandle = lambda _handle: None
    monkeypatch.setitem(sys.modules, "win32service", service)

    install_module._configure_delayed_start_and_recovery()

    assert calls[-1] == ("service", service.SERVICE_CONFIG_FAILURE_ACTIONS_FLAG, True)


@pytestmark_installer
def test_install_help_shows_package_override(capsys):
    import installer.install as install_module

    with pytest.raises(SystemExit) as exit_info:
        install_module.main(["--help"])

    assert exit_info.value.code == 0
    assert "--exe EXE" in capsys.readouterr().out


@pytestmark_installer
def test_install_service_recovery_actions_never_run_a_command():
    """The failure-recovery policy may only restart the service or do
    nothing - `SC_ACTION_RUN_COMMAND` must never be configured, or a
    service failure could be turned into arbitrary command execution.
    Checked at the AST level (actual code), not the docstring prose that
    explains this policy."""
    import win32service

    tree = ast.parse((AGENT_ROOT / "installer" / "install.py").read_text(encoding="utf-8"))
    action_attrs = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and getattr(node.value, "id", None) == "win32service"
        and node.attr.startswith("SC_ACTION_")
    }
    assert action_attrs, "expected at least one SC_ACTION_* recovery constant to be referenced"
    assert "SC_ACTION_RUN_COMMAND" not in action_attrs
    assert action_attrs <= {"SC_ACTION_RESTART", "SC_ACTION_NONE", "SC_ACTION_REBOOT"}
    assert win32service.SC_ACTION_RUN_COMMAND not in (
        win32service.SC_ACTION_RESTART,
        win32service.SC_ACTION_NONE,
    )


@pytestmark_installer
def test_uninstall_clear_credential_uses_the_production_path_not_test_override(
    tmp_path, monkeypatch
):
    """Regression test: `_clear_credential()` previously constructed
    `CredentialStore()` with no arguments, which raises `TypeError`
    (`credential_path` is required) and would abort the entire uninstall
    before the service could even be removed."""
    import installer.uninstall as uninstall_module

    program_data = tmp_path / "ProgramData"
    monkeypatch.setenv("PROGRAMDATA", str(program_data))
    monkeypatch.setenv("ITDS_AGENT_DATA_DIR", str(tmp_path / "test-data"))
    captured = {}

    class SpyStore:
        def __init__(self, path):
            captured["path"] = path

        def exists(self):
            return False

    monkeypatch.setattr(uninstall_module, "CredentialStore", SpyStore)
    assert uninstall_module._clear_credential() is True

    assert captured["path"] == program_data / "ITDS" / "Agent" / "credential.bin"


@pytestmark_installer
@pytest.mark.parametrize("failure", [CredentialStoreError("DPAPI failure"), OSError("access denied")])
def test_uninstall_credential_clear_failure_is_reported_and_fails(monkeypatch, capsys, failure):
    import installer.uninstall as uninstall_module

    class BrokenStore:
        def __init__(self, path):
            pass

        def exists(self):
            raise failure

    monkeypatch.setattr(uninstall_module, "CredentialStore", BrokenStore)

    assert uninstall_module._clear_credential() is False
    assert "could not clear stored credential" in capsys.readouterr().err


@pytestmark_installer
def test_uninstall_refuses_to_clear_credential_through_a_reparse_point(
    monkeypatch, capsys
):
    import installer.uninstall as uninstall_module

    monkeypatch.setattr(uninstall_module, "_contains_reparse_point", lambda path: True)

    assert uninstall_module._clear_credential() is False
    assert "reparse point" in capsys.readouterr().err


@pytestmark_installer
def test_uninstall_does_not_purge_data_if_credential_clear_fails(monkeypatch):
    import installer.uninstall as uninstall_module

    monkeypatch.setattr(uninstall_module, "require_admin", lambda: None)
    monkeypatch.setattr(uninstall_module, "_stop_and_remove_service", lambda: None)
    monkeypatch.setattr(uninstall_module, "_clear_credential", lambda: False)
    monkeypatch.setattr(
        uninstall_module,
        "_purge_data_directory",
        lambda: (_ for _ in ()).throw(AssertionError("must not purge data")),
    )

    assert uninstall_module.main(["--purge-data"]) == 1


@pytestmark_installer
def test_uninstall_purge_uses_default_programdata_not_test_override(
    tmp_path, monkeypatch
):
    import installer.uninstall as uninstall_module

    program_data = tmp_path / "ProgramData"
    test_override = tmp_path / "test-data"
    monkeypatch.setenv("PROGRAMDATA", str(program_data))
    monkeypatch.setenv("ITDS_AGENT_DATA_DIR", str(test_override))
    captured = []
    monkeypatch.setattr(uninstall_module, "_contains_reparse_point", lambda path: False)
    monkeypatch.setattr(uninstall_module.shutil, "rmtree", lambda path: captured.append(path))
    (program_data / "ITDS" / "Agent").mkdir(parents=True)
    test_override.mkdir()

    assert uninstall_module._purge_data_directory() is True
    assert captured == [program_data / "ITDS" / "Agent"]


@pytestmark_installer
def test_uninstall_reparse_check_checks_existing_ancestors(tmp_path, monkeypatch):
    import types
    import installer.uninstall as uninstall_module

    target = tmp_path / "ProgramData" / "ITDS" / "Agent"
    reparse_parent = target.parents[1]
    original_lstat = Path.lstat

    def fake_lstat(path):
        if path == target:
            raise FileNotFoundError
        if path == reparse_parent:
            return types.SimpleNamespace(st_file_attributes=0x400)
        if path == target.parent:
            return types.SimpleNamespace(st_file_attributes=0)
        return original_lstat(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)

    assert uninstall_module._contains_reparse_point(target) is True


@pytestmark_installer
def test_uninstall_refuses_to_purge_through_a_reparse_point(tmp_path, monkeypatch, capsys):
    import installer.uninstall as uninstall_module

    monkeypatch.setenv("PROGRAMDATA", str(tmp_path))
    monkeypatch.setattr(uninstall_module, "_contains_reparse_point", lambda path: True)
    monkeypatch.setattr(
        uninstall_module.shutil,
        "rmtree",
        lambda path: (_ for _ in ()).throw(AssertionError("must not purge through reparse point")),
    )

    assert uninstall_module._purge_data_directory() is False
    assert "reparse point" in capsys.readouterr().err
