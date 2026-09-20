from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CommunicationChannel:
    """Shell for future channel-based communication with the support backend."""

    channel_name: str = "internal"
    endpoint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_configured(self) -> bool:
        return self.endpoint is not None and self.endpoint.strip() != ""
