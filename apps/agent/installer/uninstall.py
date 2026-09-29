"""Uninstalls the ITDS endpoint agent Windows service.

Performs exactly three fixed, deterministic actions:

1. Verify it is running elevated (Administrator).
2. Stop and remove the `ITDSAgent` Windows service registration.
3. Clear the DPAPI-protected credential (so no protected secret is left
   behind for the removed service account to decrypt).

Configuration and log files under `%PROGRAMDATA%\\ITDS\\Agent` are left in
place by default (useful for a reinstall or post-mortem review); pass
`--purge-data` to also delete that directory tree.

Usage (from an elevated prompt):
    python installer/uninstall.py [--purge-data]
"""
from __future__ import annotations

import argparse
import shutil
import stat
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # apps/agent on sys.path

from installer.common import SERVICE_NAME, require_admin  # noqa: E402 - path setup must precede this import
from itds_agent.config.paths import default_data_directory  # noqa: E402
from itds_agent.security import CredentialStore, CredentialStoreError  # noqa: E402


def _stop_and_remove_service() -> None:
    import pywintypes
    import win32service
    import win32serviceutil

    try:
        win32serviceutil.StopService(SERVICE_NAME)
    except pywintypes.error as exc:
        # Already stopped or not installed - both are fine for an
        # uninstall; anything else is unexpected and worth surfacing.
        if exc.winerror not in (
            1060,  # ERROR_SERVICE_DOES_NOT_EXIST
            1062,  # ERROR_SERVICE_NOT_ACTIVE
        ):
            raise

    try:
        win32serviceutil.RemoveService(SERVICE_NAME)
    except pywintypes.error as exc:
        if exc.winerror != 1060:  # ERROR_SERVICE_DOES_NOT_EXIST
            raise
        print(f"Service '{SERVICE_NAME}' was not installed; nothing to remove.")
        return

    print(f"Service '{SERVICE_NAME}' stopped and removed.")


def _clear_credential() -> bool:
    try:
        credential_file = default_data_directory() / "credential.bin"
        if _contains_reparse_point(credential_file):
            print(
                f"Error: refusing to clear credential through a reparse point: {credential_file}",
                file=sys.stderr,
            )
            return False
        store = CredentialStore(credential_file)
        if store.exists():
            store.clear()
            print("Stored agent credential cleared.")
        return True
    except (CredentialStoreError, OSError) as exc:
        print(f"Error: could not clear stored credential: {exc}", file=sys.stderr)
        return False


def _contains_reparse_point(path: Path) -> bool:
    current = path
    while True:
        try:
            attributes = current.lstat().st_file_attributes
        except FileNotFoundError:
            if current.parent == current:
                return False
            current = current.parent
            continue
        if attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            return True
        if current.parent == current:
            return False
        current = current.parent


def _purge_data_directory() -> bool:
    directory = default_data_directory()
    try:
        contains_reparse_point = _contains_reparse_point(directory)
    except OSError as exc:
        print(f"Error: could not validate agent data path {directory}: {exc}", file=sys.stderr)
        return False
    if contains_reparse_point:
        print(
            f"Error: refusing to purge data through a reparse point: {directory}",
            file=sys.stderr,
        )
        return False
    if not directory.exists():
        return True
    try:
        shutil.rmtree(directory)
    except OSError as exc:
        print(f"Error: could not purge agent data directory {directory}: {exc}", file=sys.stderr)
        return False
    print(f"Removed {directory}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--purge-data",
        action="store_true",
        help="Also delete %%PROGRAMDATA%%\\ITDS\\Agent (config.json and logs).",
    )
    args = parser.parse_args(argv)

    require_admin()

    _stop_and_remove_service()
    if not _clear_credential():
        return 1

    if args.purge_data and not _purge_data_directory():
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
