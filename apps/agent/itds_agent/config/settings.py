from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


class ConfigurationError(ValueError):
    """Configuration is missing or invalid; safe to surface to an operator."""


@dataclass
class AgentSettings:
    """Safe runtime settings for the Windows endpoint agent.

    The `credential` field is intentionally not populated by the file/
    environment configuration loader (see `config/loader.py`): it is
    retrieved separately from the platform credential store so it never
    lives in a config file, template, or the frozen executable.
    """

    agent_name: str = "itds-agent"
    agent_version: str = "0.1.0"
    log_level: str = "INFO"
    endpoint_url: str | None = None
    api_base_url: str | None = None
    device_id: str | None = None
    allow_destructive_actions: bool = False
    required_admin: bool = False
    extra_settings: dict[str, str] = field(default_factory=dict)
    heartbeat_interval_seconds: int = 300
    request_timeout_seconds: int = 15
    credential: str | None = None
    log_directory: str | None = None
    log_max_bytes: int = 1_000_000
    log_backup_count: int = 5

    def validate(self) -> None:
        endpoint = self.api_base_url or self.endpoint_url
        if not endpoint:
            raise ConfigurationError("api_base_url is required")
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ConfigurationError("api_base_url must be an HTTPS URL")
        if not 10 <= self.heartbeat_interval_seconds <= 86400:
            raise ConfigurationError("heartbeat_interval_seconds must be between 10 and 86400")
        if not 1 <= self.request_timeout_seconds <= 120:
            raise ConfigurationError("request_timeout_seconds must be between 1 and 120")
        if not self.credential or "." not in self.credential:
            raise ConfigurationError("credential is required")
        if not self.agent_version or len(self.agent_version) > 100:
            raise ConfigurationError("agent_version is required and must be at most 100 characters")
        if self.log_level.upper() not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("log_level must be one of DEBUG, INFO, WARNING, ERROR, CRITICAL")
        if self.log_max_bytes < 10_000:
            raise ConfigurationError("log_max_bytes must be at least 10000 to avoid excessive log rotation")
        if self.log_backup_count < 1:
            raise ConfigurationError("log_backup_count must be at least 1")

    def is_safe_mode(self) -> bool:
        return not self.allow_destructive_actions and not self.required_admin
