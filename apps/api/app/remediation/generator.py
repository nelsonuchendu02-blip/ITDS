import hashlib
import json
from typing import Any

from .catalog import validate_action

RULE_ACTION_MAP = {
    "configuration-failure": "apply_safe_configuration",
    "connectivity-failure": "refresh_device_configuration",
    "performance-failure": "refresh_device_configuration",
    "security-failure": "refresh_device_configuration",
}


def canonical_plan_hash(device_id: str, actions: list[dict[str, Any]]) -> str:
    payload = {"device_id": str(device_id), "actions": actions}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def generate_actions(recommendation) -> list[dict[str, Any]]:
    """Map recommendation metadata to a stable, allowlisted action list."""
    key = RULE_ACTION_MAP.get(recommendation.rule_id, "refresh_device_configuration")
    metadata = recommendation.evidence or {}
    candidate = metadata.get("action_key")
    if candidate in ("refresh_device_configuration", "restart_managed_service", "apply_safe_configuration"):
        key = candidate
    parameters = dict(metadata.get("action_parameters") or {})
    if key == "refresh_device_configuration":
        parameters.setdefault("source", recommendation.rule_id)
        parameters.setdefault("reason", recommendation.summary or recommendation.title)
    elif key == "apply_safe_configuration":
        parameters.setdefault("settings", {})
        parameters.setdefault("reason", recommendation.summary or recommendation.title)
    validate_action(key, parameters)
    return [{"sequence": 1, "action_key": key, "parameters": parameters}]
