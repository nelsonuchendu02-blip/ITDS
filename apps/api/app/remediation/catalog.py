from dataclasses import dataclass
from typing import Any

FORBIDDEN_PARAMETER_KEYS = {
    "command", "shell", "powershell", "script", "executable", "path",
    "arguments", "cmd", "bash", "sh", "pwsh",
}


@dataclass(frozen=True)
class ActionDefinition:
    key: str
    description: str
    parameter_keys: frozenset[str]
    requires_admin: bool = False
    required_parameter_keys: frozenset[str] = frozenset()


ACTION_CATALOG = {
    "refresh_device_configuration": ActionDefinition(
        "refresh_device_configuration",
        "Refresh configuration metadata without making system changes.",
        frozenset({"source", "reason"}), required_parameter_keys=frozenset({"source", "reason"}),
    ),
    "restart_managed_service": ActionDefinition(
        "restart_managed_service",
        "Queue a managed service restart simulation for review.",
        frozenset({"service_name", "reason"}),
        requires_admin=True, required_parameter_keys=frozenset({"service_name", "reason"}),
    ),
    "apply_safe_configuration": ActionDefinition(
        "apply_safe_configuration",
        "Apply a validated safe configuration patch in simulation mode.",
        frozenset({"settings", "reason"}),
        requires_admin=True, required_parameter_keys=frozenset({"settings", "reason"}),
    ),
}


def validate_action(action_key: str, parameters: dict[str, Any]) -> ActionDefinition:
    definition = ACTION_CATALOG.get(action_key)
    if definition is None:
        raise ValueError("action_key is not allowlisted")
    if not isinstance(parameters, dict):
        raise ValueError("action parameters must be an object")
    keys = {str(key).lower() for key in parameters}
    forbidden = {key for key in keys if key in FORBIDDEN_PARAMETER_KEYS or
                 any(token in key for token in ("command", "shell", "powershell", "script", "executable", "path"))}
    if forbidden:
        raise ValueError(f"unsafe remediation keys are forbidden: {sorted(forbidden)}")
    if set(parameters) - definition.parameter_keys:
        raise ValueError("action parameters contain unsupported fields")
    missing = definition.required_parameter_keys - set(parameters)
    if missing:
        raise ValueError("required action parameters are missing")
    def reject_nested(value: Any) -> None:
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                lowered = str(nested_key).lower()
                if lowered in FORBIDDEN_PARAMETER_KEYS or any(
                    token in lowered for token in ("command", "shell", "powershell", "script", "executable", "path")
                ):
                    raise ValueError("unsafe remediation keys are forbidden")
                reject_nested(nested_value)
        elif isinstance(value, list):
            for item in value:
                reject_nested(item)
    for value in parameters.values():
        reject_nested(value)
    return definition
