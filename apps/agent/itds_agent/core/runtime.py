from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable
from enum import StrEnum
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

    @property
    def running(self) -> bool:
        return self.state is RuntimeState.RUNNING

    def tick(self):
        if not self.running:
            return None
        try:
            system = SystemCollector().collect()
            network = NetworkCollector().collect()
            return self.heartbeat({
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "hostname": network.get("hostname") or system.get("hostname"),
                "platform": system.get("platform"),
                "local_ip": network.get("local_ip"),
                "metrics": system,
            })
        except Exception:
            self.state = RuntimeState.ERROR
            raise

    def start(self) -> None:
        if self.state in (RuntimeState.RUNNING, RuntimeState.STARTING):
            return
        self.state = RuntimeState.STARTING
        self.settings.validate()
        self.state = RuntimeState.RUNNING

    def stop(self) -> None:
        if self.state is RuntimeState.STOPPED:
            return
        self.state = RuntimeState.STOPPING
        self.state = RuntimeState.STOPPED
