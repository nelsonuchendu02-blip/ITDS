from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RemediationPlan:
    """Represents a future remediation action plan.

    No destructive operations are permitted in Phase 0.
    """

    action_name: str = "noop"
    requires_admin: bool = False
    safe_mode: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        return self.safe_mode and not self.requires_admin
