"""Configuration support for the Windows endpoint agent."""

from .loader import load_settings
from .paths import config_path, credential_path, data_directory, log_directory
from .settings import AgentSettings, ConfigurationError

__all__ = [
    "AgentSettings",
    "ConfigurationError",
    "load_settings",
    "config_path",
    "credential_path",
    "data_directory",
    "log_directory",
]
