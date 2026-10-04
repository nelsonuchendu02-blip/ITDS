"""Shared, narrowly-scoped helpers for the ITDS agent installer scripts.

Both `install.py` and `uninstall.py` import from here so the service name,
display name, description, and data-directory ACL policy are defined in
exactly one place. Nothing in this module executes arbitrary/operator-
supplied commands: every Windows API call below takes fixed, hard-coded
arguments (service name, account, directory path) - never a shell string
built from user input - so this stays a narrow, deterministic installer,
not a general-purpose execution facility.
"""
from __future__ import annotations

import sys

if sys.platform != "win32":  # pragma: no cover - guard, not exercised off Windows
    raise ImportError("The ITDS agent installer only runs on Windows.")

import ntsecuritycon as ncon
import win32security

from itds_agent.config.paths import data_directory, log_directory
from itds_agent.service.host import SERVICE_DESCRIPTION, SERVICE_DISPLAY_NAME, SERVICE_NAME

# Least-privilege service account: LocalService has minimal local
# privileges and no network credentials, which is sufficient for the
# agent's telemetry-only, outbound-HTTPS-only workload.
SERVICE_ACCOUNT = r"NT AUTHORITY\LocalService"

__all__ = [
    "SERVICE_ACCOUNT",
    "SERVICE_DESCRIPTION",
    "SERVICE_DISPLAY_NAME",
    "SERVICE_NAME",
    "require_admin",
    "secure_data_directories",
]


def require_admin() -> None:
    """Refuse to continue unless running with administrative rights.

    Installing a service and writing an ACL both require admin privileges;
    failing fast with a clear message is safer than a partial install.
    """
    import ctypes

    if not ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError(
            "The ITDS agent installer must be run from an elevated "
            "(Administrator) PowerShell/Command Prompt."
        )


def _restricted_dacl():
    """Build a DACL granting full control only to SYSTEM, Administrators,
    and the LocalService account that runs the agent - no other accounts.
    """
    dacl = win32security.ACL()
    for sid in (
        win32security.CreateWellKnownSid(win32security.WinLocalSystemSid),
        win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid),
        win32security.CreateWellKnownSid(win32security.WinLocalServiceSid),
    ):
        dacl.AddAccessAllowedAceEx(
            win32security.ACL_REVISION,
            ncon.OBJECT_INHERIT_ACE | ncon.CONTAINER_INHERIT_ACE,
            ncon.FILE_ALL_ACCESS,
            sid,
        )
    return dacl


def secure_data_directories() -> None:
    """Create `ProgramData\\ITDS\\Agent` (config/credential) and its `logs`
    subdirectory if missing, and apply a restricted ACL so only SYSTEM,
    Administrators, and the agent's own LocalService account can read the
    protected credential file or the config/log contents.
    """
    dacl = _restricted_dacl()
    security_descriptor = win32security.SECURITY_DESCRIPTOR()
    security_descriptor.SetSecurityDescriptorDacl(1, dacl, 0)

    for directory in (data_directory(), log_directory()):
        directory.mkdir(parents=True, exist_ok=True)
        win32security.SetFileSecurity(
            str(directory), win32security.DACL_SECURITY_INFORMATION, security_descriptor
        )
