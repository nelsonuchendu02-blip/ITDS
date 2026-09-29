"""Single shared lifecycle entry point for both console mode and the Windows
service host.

`build_runtime()` is the one place that wires configuration, logging, the
HTTPS communication client, and the `AgentRuntime` together. Both
`itds_agent.__main__` (console mode) and `itds_agent.service.host` (the
Windows service wrapper) call this function so there is exactly one agent
lifecycle implementation, per the Phase 1O requirement that console mode and
the service use the same runtime/configuration/heartbeat path.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .runtime import AgentRuntime
from ..communication.client import AgentClient
from ..config.loader import load_settings
from ..config.paths import log_directory as default_log_directory
from ..config.settings import AgentSettings
from ..logging.logger import configure_logging

LOGGER_NAME = "itds-agent"


def build_runtime(
    *,
    settings: AgentSettings | None = None,
    use_event_log: bool = False,
) -> AgentRuntime:
    """Loads settings (if not supplied), configures logging, and returns a
    ready-to-run `AgentRuntime` wired to the real HTTPS heartbeat client.
    """
    if settings is None:
        settings = load_settings()
    else:
        settings.validate()

    log_dir = Path(settings.log_directory) if settings.log_directory else default_log_directory()
    logger = configure_logging(
        log_directory=log_dir,
        log_level=settings.log_level,
        max_bytes=settings.log_max_bytes,
        backup_count=settings.log_backup_count,
        use_event_log=use_event_log,
        logger_name=LOGGER_NAME,
    )

    client = AgentClient.from_settings(settings)

    return AgentRuntime(settings=settings, heartbeat=client.heartbeat, logger=logger)


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)
