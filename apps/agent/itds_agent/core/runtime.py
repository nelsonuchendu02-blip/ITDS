import logging
from enum import StrEnum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event, Lock
from typing import Callable

from ..collectors import NetworkCollector, SystemCollector
from ..communication.client import AgentCommunicationError
from ..config.settings import AgentSettings

class RuntimeState(StrEnum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

@dataclass
class AgentRuntime:
    settings: AgentSettings
    heartbeat: Callable[[dict], object]
    state: RuntimeState = RuntimeState.STOPPED
    system_collector: SystemCollector = field(default_factory=SystemCollector)
    network_collector: NetworkCollector = field(default_factory=NetworkCollector)
    logger: logging.Logger = field(default_factory=lambda: logging.getLogger("itds-agent"))
    _stop_event: Event = field(default_factory=Event, init=False, repr=False)
    #: Guards against a second `run()` loop starting concurrently on the same
    #: instance (e.g. an accidental duplicate service-start call); this is a
    #: belt-and-braces check alongside the service host's own start guard.
    _run_lock: Lock = field(default_factory=Lock, init=False, repr=False)

    def __post_init__(self) -> None:
        self.system_collector.agent_version = self.settings.agent_version

    @property
    def running(self) -> bool:
        return self.state is RuntimeState.RUNNING

    def tick(self):
        if not self.running:
            return None
        try:
            system = self.system_collector.collect()
            network = self.network_collector.collect()
            result = self.heartbeat({
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "agent_version": self.settings.agent_version,
                "hostname": network.get("hostname") or system.get("hostname"),
                "platform": system.get("platform"),
                "local_ip": network.get("local_ip"),
                "metrics": system,
            })
            self.logger.info("heartbeat succeeded")
            return result
        except AgentCommunicationError as exc:
            # A communication failure (including an authentication failure,
            # which the client already refuses to retry) is a transient,
            # expected condition for a long-running service - e.g. a
            # temporary network outage. Logging and continuing keeps the
            # service stable and lets it self-heal on the next scheduled
            # heartbeat, instead of requiring an operator to restart it.
            self.logger.warning("heartbeat failed: %s", exc)
            return None
        except Exception as exc:  # noqa: BLE001 - unexpected defects fail safe
            self.logger.warning("heartbeat cycle raised an unexpected error: %s", exc)
            self.state = RuntimeState.ERROR
            return None

    def start(self) -> None:
        if self.state in (RuntimeState.RUNNING, RuntimeState.STARTING):
            return
        self.state = RuntimeState.STARTING
        try:
            self.settings.validate()
        except Exception:
            self.state = RuntimeState.ERROR
            raise
        self.state = RuntimeState.RUNNING

    def stop(self) -> None:
        if self.state is RuntimeState.STOPPED:
            return
        self.state = RuntimeState.STOPPING
        self._stop_event.set()
        self.state = RuntimeState.STOPPED

    def run(self, max_cycles: int | None = None) -> int:
        if not self._run_lock.acquire(blocking=False):
            raise RuntimeError("AgentRuntime.run() is already active on this instance")
        try:
            self.start()
            cycles = 0
            try:
                while self.running and not self._stop_event.is_set():
                    self.tick()
                    cycles += 1
                    if self.state is RuntimeState.ERROR or (
                        max_cycles is not None and cycles >= max_cycles
                    ):
                        break
                    self._stop_event.wait(self.settings.heartbeat_interval_seconds)
            finally:
                if self.state is RuntimeState.RUNNING:
                    self.stop()
            return cycles
        finally:
            self._run_lock.release()
