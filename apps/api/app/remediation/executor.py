from dataclasses import dataclass
from typing import Any

from .catalog import validate_action


@dataclass(frozen=True)
class DryRunResult:
    success: bool
    action_key: str
    message: str
    observed: dict[str, Any]


class DryRunExecutor:
    """Executor intentionally incapable of invoking a shell, process, or OS API."""

    def execute(self, action_key: str, parameters: dict[str, Any]) -> DryRunResult:
        validate_action(action_key, parameters)
        return DryRunResult(
            True, action_key, "dry-run: no operating-system action was executed",
            {"parameters": parameters, "executed": False},
        )
