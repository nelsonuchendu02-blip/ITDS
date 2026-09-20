import logging
from logging.config import dictConfig

from .config import get_settings


def configure_logging() -> None:
    """Configure structured application logging."""
    settings = get_settings()
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "standard",
                    "level": settings.log_level.upper(),
                }
            },
            "loggers": {
                "itds": {
                    "handlers": ["default"],
                    "level": settings.log_level.upper(),
                    "propagate": False,
                }
            },
        }
    )


logger = logging.getLogger("itds")
