from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AgentSettings:
    """Safe runtime settings for future agent deployment.

    Values are intentionally limited to configuration metadata for Phase 0.
    """

    agent_name: str = "itds-agent"
    log_level: str = "INFO"
    endpoint_url: str | None = None
    allow_destructive_actions: bool = False
    required_admin: bool = False
    extra_settings: dict[str, str] = field(default_factory=dict)

    def is_safe_mode(self) -> bool:
        return not self.allow_destructive_actions and not self.required_admin
