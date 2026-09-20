from __future__ import annotations

import logging


class AgentLogger:
    """Thin logging facade for future Windows endpoint instrumentation."""

    def __init__(self, name: str = "itds-agent") -> None:
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)
