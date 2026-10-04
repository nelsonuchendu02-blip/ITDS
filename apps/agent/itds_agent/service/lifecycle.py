"""Windows-agnostic service lifecycle management.

Wraps the shared `AgentRuntime` lifecycle (start in a background thread,
stop on request) so this logic can be unit-tested without importing
`pywin32`, keeping the Windows-specific glue in `service/host.py` thin and
allowing this module's tests to run on Linux CI.
"""
from __future__ import annotations

import threading
from typing import Callable

from ..config.loader import ConfigurationError
from ..core.bootstrap import build_runtime
from ..core.runtime import AgentRuntime


class ServiceLifecycleError(RuntimeError):
    """Raised when the service cannot start, e.g. invalid configuration."""


class ServiceLifecycle:
    """Owns exactly one `AgentRuntime` and the background thread driving it.

    `start()` is idempotent: calling it while already running is a no-op,
    which is the guard against a duplicate runtime loop if the service
    control manager (or a caller) invokes start more than once.
    """

    def __init__(self, runtime_factory: Callable[[], AgentRuntime] = build_runtime):
        self._runtime_factory = runtime_factory
        self._runtime: AgentRuntime | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._ready = threading.Event()
        self._finished = threading.Event()
        self._stop_requested = threading.Event()
        self._started = False
        self._failed = False
        self._startup_error: Exception | None = None

    @property
    def runtime(self) -> AgentRuntime | None:
        return self._runtime

    @property
    def failed(self) -> bool:
        return self._failed

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            try:
                self._runtime = self._runtime_factory()
            except ConfigurationError as exc:
                self._failed = True
                self._finished.set()
                raise ServiceLifecycleError(str(exc)) from exc
            except Exception as exc:
                self._failed = True
                self._finished.set()
                raise ServiceLifecycleError("unable to initialize agent runtime") from exc
            thread = threading.Thread(
                target=self._run_runtime, name="itds-agent-runtime", daemon=True
            )
            self._thread = thread
            try:
                thread.start()
            except Exception as exc:
                self._failed = True
                self._ready.set()
                self._finished.set()
                raise ServiceLifecycleError("unable to start agent runtime thread") from exc
        self._ready.wait()
        if self._startup_error is not None:
            if isinstance(self._startup_error, ConfigurationError):
                raise ServiceLifecycleError(str(self._startup_error)) from self._startup_error
            raise ServiceLifecycleError("unable to start agent runtime") from self._startup_error

    def _run_runtime(self) -> None:
        runtime = self._runtime
        try:
            if runtime is None:
                raise RuntimeError("agent runtime was not initialized")
            runtime.start()
        except Exception as exc:
            self._startup_error = exc
            self._failed = True
            self._ready.set()
            self._finished.set()
            return
        self._ready.set()
        try:
            if self._stop_requested.is_set():
                runtime.stop()
            else:
                runtime.run()
        except Exception:
            self._failed = True
        finally:
            if not self._stop_requested.is_set() or (
                runtime is not None and runtime.state.value == "error"
            ):
                self._failed = True
            self._finished.set()

    def stop(self, join_timeout: float = 30.0) -> None:
        """Signals the runtime to stop and waits (bounded) for its thread to
        exit, so shutdown cleanly terminates the runtime's timer and network
        client before the process/service exits."""
        with self._lock:
            runtime = self._runtime
            thread = self._thread
            self._stop_requested.set()
        if runtime is not None:
            runtime.stop()
        if thread is not None:
            thread.join(timeout=join_timeout)

    def wait(self, timeout: float | None = None) -> bool:
        """Wait until the runtime thread has actually exited."""
        if not self._started:
            return False
        if not self._finished.wait(timeout=timeout):
            return False
        thread = self._thread
        if thread is not None:
            thread.join()
        return True
