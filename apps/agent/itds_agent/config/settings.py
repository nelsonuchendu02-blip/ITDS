from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class AgentSettings:
    """Safe runtime settings for future agent deployment.

    Values are intentionally limited to configuration metadata for Phase 0.
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

    def validate(self) -> None:
        endpoint = self.api_base_url or self.endpoint_url
        if not endpoint:
            raise ValueError("api_base_url is required")
        parsed = urlparse(endpoint)
        if parsed.scheme != "https" or not parsed.netloc:
            raise ValueError("api_base_url must be an HTTPS URL")
        if not 10 <= self.heartbeat_interval_seconds <= 86400:
            raise ValueError("heartbeat_interval_seconds must be between 10 and 86400")
        if not 1 <= self.request_timeout_seconds <= 120:
            raise ValueError("request_timeout_seconds must be between 1 and 120")
        if not self.credential or "." not in self.credential:
            raise ValueError("credential is required")
        if not self.agent_version or len(self.agent_version) > 100:
            raise ValueError("agent_version is required and must be at most 100 characters")

    def is_safe_mode(self) -> bool:
        return not self.allow_destructive_actions and not self.required_admin
