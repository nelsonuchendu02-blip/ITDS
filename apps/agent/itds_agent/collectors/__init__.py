"""Collector interfaces for future endpoint data gathering."""

from .base import Collector
from .system import SystemCollector, collect
from .network import NetworkCollector, collect as collect_network

__all__ = ["Collector", "SystemCollector", "NetworkCollector", "collect", "collect_network"]
