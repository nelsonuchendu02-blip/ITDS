"""Loads `AgentSettings` from an external JSON config file plus environment
variable overrides, then attaches the credential from the protected
credential store. The two are combined here, not earlier, so the on-disk
config file and any packaged config template can never legitimately contain
a plaintext credential field.
"""
from __future__ import annotations

import json
from pathlib import Path

from .paths import config_path, credential_path
from .settings import AgentSettings, ConfigurationError
from ..security.credential_store import CredentialStore, CredentialStoreError

#: Config keys the file loader will accept. Anything else is rejected so a
#: config file cannot silently smuggle in unexpected/unsafe fields such as
#: `allow_destructive_actions: true` without deliberate operator review of
#: this list.
_ALLOWED_FILE_KEYS = {
    "agent_name",
    "agent_version",
    "api_base_url",
    "device_id",
    "heartbeat_interval_seconds",
    "request_timeout_seconds",
    "log_level",
    "log_directory",
    "log_max_bytes",
    "log_backup_count",
}

#: A config file must never carry these secrets; presence is a hard error
#: rather than something silently ignored, since it signals a template or
#: deployment mistake that could otherwise leak a credential into source
#: control or a packaged executable.
_FORBIDDEN_FILE_KEYS = {"credential", "password", "secret", "token", "api_key"}

_ENV_PREFIX = "ITDS_AGENT_"
_ENV_KEYS = {
    "agent_name": str,
    "agent_version": str,
    "api_base_url": str,
    "device_id": str,
    "heartbeat_interval_seconds": int,
    "request_timeout_seconds": int,
    "log_level": str,
    "log_directory": str,
}


def _read_config_file(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ConfigurationError(f"unable to read configuration file: {path}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError(f"configuration file must contain a JSON object: {path}")
    forbidden = _FORBIDDEN_FILE_KEYS & raw.keys()
    if forbidden:
        raise ConfigurationError(
            "configuration file must not contain secret fields: " + ", ".join(sorted(forbidden))
        )
    unknown = set(raw.keys()) - _ALLOWED_FILE_KEYS
    if unknown:
        raise ConfigurationError(
            "configuration file contains unsupported fields: " + ", ".join(sorted(unknown))
        )
    return raw


def _apply_env_overrides(values: dict, env: dict) -> dict:
    result = dict(values)
    for key, caster in _ENV_KEYS.items():
        env_name = f"{_ENV_PREFIX}{key.upper()}"
        if env_name in env:
            raw_value = env[env_name]
            try:
                result[key] = caster(raw_value)
            except ValueError as exc:
                raise ConfigurationError(f"invalid value for {env_name}") from exc
    return result


def load_settings(
    *,
    config_file: Path | None = None,
    credential_store: CredentialStore | None = None,
    env: dict | None = None,
    require_credential: bool = True,
) -> AgentSettings:
    """Builds a validated `AgentSettings` from file + environment + credential store.

    Raises `ConfigurationError` (a `ValueError` subclass) with an operator-safe
    message on any missing/invalid configuration; never includes credential
    material in the error.
    """
    import os as _os

    config_file = config_file or config_path()
    file_values = _read_config_file(Path(config_file))
    merged = _apply_env_overrides(file_values, env if env is not None else dict(_os.environ))

    settings = AgentSettings(**{k: v for k, v in merged.items() if v is not None})

    if require_credential:
        store = credential_store or CredentialStore(credential_path())
        try:
            settings.credential = store.load()
        except CredentialStoreError as exc:
            raise ConfigurationError("unable to load the protected agent credential") from exc
        if not settings.credential:
            raise ConfigurationError(
                "no agent credential is enrolled; run enrollment before starting the service"
            )

    settings.validate()
    return settings
