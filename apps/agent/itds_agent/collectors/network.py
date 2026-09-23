"""Read-only local network metadata collector."""
import socket
from typing import Any

from .base import Collector


class NetworkCollector(Collector):
    def collect(self) -> dict[str, Any]:
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except OSError:
            local_ip = None
        return {"hostname": hostname[:255], "local_ip": local_ip}


def collect() -> dict[str, Any]:
    return NetworkCollector().collect()
