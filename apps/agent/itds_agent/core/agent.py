from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentCore:
    """Minimal runtime shell for future Windows agent behavior.

    Phase 0 intentionally prohibits remediation or system mutation.
    """

    agent_name: str = "itds-agent"
    version: str = "0.1.0"
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def register_capability(self, capability: str) -> None:
        if capability not in self.capabilities:
            self.capabilities.append(capability)

    def describe(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "version": self.version,
            "capabilities": list(self.capabilities),
            "metadata": dict(self.metadata),
        }
