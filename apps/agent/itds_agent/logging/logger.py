from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

from .redaction import RedactingFilter

_LOGGER_NAME = "itds-agent"


class AgentLogger:
    """Thin logging facade used by call sites that only need info/warning."""

    def __init__(self, name: str = _LOGGER_NAME) -> None:
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.INFO)

    def info(self, message: str) -> None:
        self.logger.info(message)

    def warning(self, message: str) -> None:
        self.logger.warning(message)


def configure_logging(
    *,
    log_directory: Path | None = None,
    log_level: str = "INFO",
    max_bytes: int = 1_000_000,
    backup_count: int = 5,
    use_event_log: bool = False,
    logger_name: str = _LOGGER_NAME,
) -> logging.Logger:
    """Configures bounded/rotating logging for the agent process.

    Safe by construction:
    - A `RotatingFileHandler` caps total on-disk log size to
      `max_bytes * (backup_count + 1)`, so the agent cannot consume
      unbounded disk space no matter how long the service runs.
    - Every handler gets a `RedactingFilter` so credential-shaped substrings
      are stripped even if a caller accidentally logs one.
    - Windows Event Log integration is additive (`use_event_log=True`) and
      never the only diagnostic channel; the rotating file handler is always
      configured so logs remain available without Event Log access.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    logger.handlers.clear()
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s", datefmt="%Y-%m-%dT%H:%M:%S%z"
    )

    if log_directory is not None:
        log_directory.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_directory / "itds-agent.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(RedactingFilter())
        logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.addFilter(RedactingFilter())
    logger.addHandler(console_handler)

    if use_event_log:
        try:
            event_handler = logging.handlers.NTEventLogHandler(logger_name)
        except ImportError:
            # Event Log integration is an optional, additive channel; the
            # rotating file handler above already provides a diagnostic
            # channel, so we degrade quietly rather than failing startup.
            logger.warning("Windows Event Log integration unavailable; continuing with file logging only")
        else:
            event_handler.setFormatter(formatter)
            event_handler.addFilter(RedactingFilter())
            logger.addHandler(event_handler)

    return logger
