from enum import StrEnum
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Event
from typing import Callable

from ..collectors import NetworkCollector, SystemCollector
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
    _stop_event: Event = field(default_factory=Event, init=False, repr=False)

    @property
    def running(self) -> bool:
        return self.state is RuntimeState.RUNNING

    def tick(self):
        if not self.running:
            return None
        try:
            system = self.system_collector.collect()
            network = self.network_collector.collect()
            return self.heartbeat({
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "hostname": network.get("hostname") or system.get("hostname"),
                "platform": system.get("platform"),
                "local_ip": network.get("local_ip"),
                "metrics": system,
            })
        except Exception:
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
