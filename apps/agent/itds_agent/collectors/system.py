"""Safe local system telemetry without command or process execution."""
import os
import platform
import time
from typing import Any

from .base import Collector


class SystemCollector(Collector):
    def collect(self) -> dict[str, Any]:
        return {
            "hostname": platform.node()[:255],
            "platform": platform.system(),
            "platform_version": platform.version()[:256],
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count() or 1,
            "uptime_seconds": int(time.monotonic()),
        }


def collect() -> dict[str, Any]:
    return SystemCollector().collect()
