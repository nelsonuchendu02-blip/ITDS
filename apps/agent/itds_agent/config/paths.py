"""Default filesystem locations for the installed Windows agent.

Centralizing these paths keeps the installer, service host, and console
entry point in agreement about where configuration, protected credentials,
and logs live, and keeps that policy in one reviewable place.

`ProgramData` (not `Program Files`) is used for mutable runtime state
(config, credential, logs) because the service does not need write access
to its own install directory - this supports least-privilege operation.
"""
from __future__ import annotations

import os
from pathlib import Path

#: Overridable only for tests; production code should not need to set this.
_DATA_ROOT_ENV = "ITDS_AGENT_DATA_DIR"


def default_data_directory() -> Path:
    program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
    return Path(program_data) / "ITDS" / "Agent"


def data_directory() -> Path:
    override = os.environ.get(_DATA_ROOT_ENV)
    if override:
        return Path(override)
    return default_data_directory()


def config_path() -> Path:
    return data_directory() / "config.json"


def credential_path() -> Path:
    return data_directory() / "credential.bin"


def log_directory() -> Path:
    return data_directory() / "logs"
