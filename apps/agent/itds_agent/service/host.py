"""Windows Service Control Manager (SCM) integration for `ITDSAgent`.

This module is intentionally thin: all actual agent behavior (runtime
start/stop, heartbeat cycle, configuration, logging) lives in
`itds_agent.service.lifecycle.ServiceLifecycle` and the modules it wires
together, which are unit-testable without `pywin32`. This module only
translates SCM lifecycle calls (`SvcDoRun`/`SvcStop`) into
`ServiceLifecycle` calls and reports status back to the SCM, per the
requirement that service code stay separated from business/collection
logic.

Only importable on Windows (it imports `win32serviceutil`/`win32service`/
`win32event`/`servicemanager` from `pywin32`); Linux CI exercises
`ServiceLifecycle` directly instead.
"""
from __future__ import annotations

import functools
import sys

import servicemanager
import win32event
import win32service
import win32serviceutil

from ..core.bootstrap import build_runtime
from .lifecycle import ServiceLifecycle, ServiceLifecycleError

SERVICE_NAME = "ITDSAgent"
SERVICE_DISPLAY_NAME = "ITDS Endpoint Agent"
SERVICE_DESCRIPTION = (
    "Collects and reports read-only device telemetry (CPU, memory, disk, "
    "uptime) to the ITDS monitoring API. Telemetry-only: performs no "
    "remote command execution, remediation, or system changes."
)


class ITDSAgentService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = SERVICE_DISPLAY_NAME
    _svc_description_ = SERVICE_DESCRIPTION

    def __init__(self, args):
        super().__init__(args)
        # A manual-reset event is used purely to let SvcStop wake SvcDoRun's
        # wait immediately; the actual runtime shutdown is driven by
        # ServiceLifecycle.stop(), not by this event alone.
        self._stop_scm_event = win32event.CreateEvent(None, 1, 0, None)
        # Running as a Windows service: route logs additively through the
        # Windows Event Log as well as the bounded rotating file, so
        # operators can see agent status via Event Viewer / `services.msc`
        # without opening the log directory.
        self._lifecycle = ServiceLifecycle(
            runtime_factory=functools.partial(build_runtime, use_event_log=True)
        )

    def SvcStop(self) -> None:
        # Report STOP_PENDING immediately: shutdown must not block
        # indefinitely, and the SCM expects prompt acknowledgement of a stop
        # request even while the runtime finishes its bounded shutdown.
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        try:
            self._lifecycle.stop()
        finally:
            win32event.SetEvent(self._stop_scm_event)

    def SvcDoRun(self) -> None:
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )
        try:
            self._lifecycle.start()
        except ServiceLifecycleError as exc:
            # Configuration/credential problems are reported to the Windows
            # Event Log (visible via `services.msc` / Event Viewer) and the
            # service transitions to a controlled stop rather than crashing
            # or retrying indefinitely.
            servicemanager.LogErrorMsg(f"ITDSAgent failed to start: {exc}")
            self.ReportServiceStatus(win32service.SERVICE_STOPPED, win32ExitCode=1)
            return

        if self._lifecycle.failed:
            servicemanager.LogErrorMsg("ITDSAgent runtime failed during startup.")
            self.ReportServiceStatus(win32service.SERVICE_STOPPED, win32ExitCode=1)
            return

        self.ReportServiceStatus(win32service.SERVICE_RUNNING)
        while True:
            if self._lifecycle.wait(timeout=0.1):
                if self._lifecycle.failed:
                    servicemanager.LogErrorMsg("ITDSAgent runtime exited unexpectedly.")
                    self.ReportServiceStatus(win32service.SERVICE_STOPPED, win32ExitCode=1)
                else:
                    self.ReportServiceStatus(win32service.SERVICE_STOPPED)
                    servicemanager.LogMsg(
                        servicemanager.EVENTLOG_INFORMATION_TYPE,
                        servicemanager.PYS_SERVICE_STOPPED,
                        (self._svc_name_, ""),
                    )
                return
            if win32event.WaitForSingleObject(self._stop_scm_event, 0) == win32event.WAIT_OBJECT_0:
                if self._lifecycle.failed:
                    servicemanager.LogErrorMsg("ITDSAgent runtime failed while stopping.")
                    self.ReportServiceStatus(win32service.SERVICE_STOPPED, win32ExitCode=1)
                else:
                    self.ReportServiceStatus(win32service.SERVICE_STOPPED)
                    servicemanager.LogMsg(
                        servicemanager.EVENTLOG_INFORMATION_TYPE,
                        servicemanager.PYS_SERVICE_STOPPED,
                        (self._svc_name_, ""),
                    )
                return


def main() -> None:
    """Console entry used by `win32serviceutil.HandleCommandLine` for
    install/remove/start/stop/debug, e.g.:
    `ITDSAgentService.exe install|remove|start|stop|debug`.
    """
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(ITDSAgentService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(ITDSAgentService)


if __name__ == "__main__":
    main()
