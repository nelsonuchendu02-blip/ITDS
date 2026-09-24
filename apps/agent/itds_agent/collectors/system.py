"""Safe local system telemetry without command or process execution."""
import platform
import time
from typing import Any

import psutil

from .base import Collector


class SystemCollector(Collector):
    def __init__(self, agent_version: str = "unknown") -> None:
        self.agent_version = agent_version[:100]

    def collect(self) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "hostname": platform.node()[:255] or None,
            "platform": platform.system()[:100] or None,
            "os_version": platform.version()[:256] or None,
            "agent_version": self.agent_version,
            "cpu_percent": self._safe_percent(self._cpu_percent),
            "memory_percent": self._safe_percent(self._memory_percent),
            "disk_percent": self._safe_percent(self._disk_percent),
            "uptime_seconds": self._safe_uptime(),
        }
        return metrics

    @staticmethod
    def _safe_percent(reader) -> float | None:
        try:
            value = float(reader())
        except (OSError, RuntimeError, ValueError):
            return None
        return max(0.0, min(100.0, value))

    @staticmethod
    def _cpu_percent() -> float:
        return psutil.cpu_percent(interval=None)

    @staticmethod
    def _memory_percent() -> float:
        return psutil.virtual_memory().percent

    @staticmethod
    def _disk_percent() -> float:
        return psutil.disk_usage(".").percent

    @staticmethod
    def _safe_uptime() -> float | None:
        try:
            return max(0.0, time.time() - psutil.boot_time())
        except (OSError, RuntimeError, ValueError):
            return None


def collect(agent_version: str = "unknown") -> dict[str, Any]:
    return SystemCollector(agent_version=agent_version).collect()
