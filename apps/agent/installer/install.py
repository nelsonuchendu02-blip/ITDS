"""Installs the ITDS endpoint agent as a Windows service.

This script performs exactly five fixed, deterministic actions - it does
not accept or execute arbitrary commands:

1. Verify it is running elevated (Administrator).
2. Copy the complete service package to `%ProgramFiles%\\ITDS\\Agent`.
3. Create `%PROGRAMDATA%\\ITDS\\Agent` (config/credential) and its `logs`
   subdirectory, restricted to SYSTEM, Administrators, and the agent's own
   LocalService account.
4. Register the service from that installed location, under the
   least-privilege `LocalService` account, set to start automatically
   (delayed) at boot.
5. Configure a bounded automatic-restart recovery policy for transient
   service failures (no `SC_ACTION_RUN_COMMAND` action is ever configured -
   only "restart the service" or "take no action").

It does NOT provision a credential: run `ITDSAgentEnroll.exe` separately
(as an Administrator, once) to store the agent's HTTPS credential via
DPAPI before starting the service. See docs/operations/windows-agent.md.

Usage (from an elevated prompt, after `build/build_exe.py` has produced
`build/dist/ITDSAgent/ITDSAgent.exe`):
    python installer/install.py [--exe PATH_TO_ITDSAgent.exe]
"""
from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # apps/agent on sys.path

from installer.common import (  # noqa: E402 - path setup must precede this import
    SERVICE_ACCOUNT,
    SERVICE_DESCRIPTION,
    SERVICE_DISPLAY_NAME,
    SERVICE_NAME,
    require_admin,
    secure_data_directories,
)

DEFAULT_EXE = (
    Path(__file__).resolve().parent.parent
    / "build"
    / "dist"
    / "ITDSAgent"
    / "ITDSAgent.exe"
)
DEFAULT_INSTALL_DIR = (
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "ITDS" / "Agent"
)

# Reset the failure counter after 24h with no failures, then allow up to
# three bounded, delayed automatic restarts before giving up and leaving
# the service stopped for an operator to investigate - this avoids a
# crash-restart busy loop while still recovering from transient faults.
_FAILURE_RESET_PERIOD_SECONDS = 24 * 60 * 60
_RESTART_DELAY_MS = 60_000


def _register_service(exe_path: Path) -> None:
    import win32service
    import win32serviceutil

    win32serviceutil.InstallService(
        None,
        SERVICE_NAME,
        SERVICE_DISPLAY_NAME,
        startType=win32service.SERVICE_AUTO_START,
        userName=SERVICE_ACCOUNT,
        password=None,
        exeName=str(exe_path),
        description=SERVICE_DESCRIPTION,
    )
    _configure_delayed_start_and_recovery()


def _install_package(exe_path: Path, install_dir: Path) -> Path:
    _ensure_service_stopped()
    source_dir = Path(os.path.abspath(exe_path)).parent
    install_dir = Path(os.path.abspath(install_dir))
    _ensure_no_reparse_points(source_dir, inspect_tree=True)
    _ensure_no_reparse_points(install_dir)
    if source_dir != install_dir:
        if source_dir.is_relative_to(install_dir) or install_dir.is_relative_to(source_dir):
            raise ValueError("The source package and installation directory must not contain each other.")
        install_dir.parent.mkdir(parents=True, exist_ok=True)
        _ensure_no_reparse_points(install_dir.parent)

        staging_dir = Path(tempfile.mkdtemp(
            prefix=f".{install_dir.name}.staging-", dir=install_dir.parent
        ))
        backup_dir: Path | None = None
        try:
            shutil.copytree(source_dir, staging_dir, dirs_exist_ok=True, symlinks=True)
            _ensure_no_reparse_points(staging_dir, inspect_tree=True)

            if install_dir.exists():
                _ensure_no_reparse_points(install_dir, inspect_tree=True)
                backup_dir = install_dir.with_name(
                    f".{install_dir.name}.backup-{uuid.uuid4().hex}"
                )
                install_dir.rename(backup_dir)
            try:
                staging_dir.rename(install_dir)
            except OSError:
                if backup_dir is not None:
                    backup_dir.rename(install_dir)
                    backup_dir = None
                raise
            if backup_dir is not None:
                _ensure_no_reparse_points(backup_dir, inspect_tree=True)
                shutil.rmtree(backup_dir)
                backup_dir = None
        finally:
            if staging_dir.exists():
                _ensure_no_reparse_points(staging_dir, inspect_tree=True)
                shutil.rmtree(staging_dir)
    installed_exe = install_dir / exe_path.name
    if not installed_exe.is_file():
        raise FileNotFoundError(f"Packaged service executable not found after installation: {installed_exe}")
    return installed_exe


def _ensure_no_reparse_points(path: Path, *, inspect_tree: bool = False) -> None:
    current = path
    while True:
        try:
            entry_stat = current.lstat()
        except FileNotFoundError:
            if current.parent == current:
                break
            current = current.parent
            continue
        if (
            stat.S_ISLNK(entry_stat.st_mode)
            or getattr(entry_stat, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError(f"Refusing to use a reparse point in package path: {current}")
        if current.parent == current:
            break
        current = current.parent

    if inspect_tree:
        if not path.is_dir():
            raise NotADirectoryError(f"Agent package directory does not exist: {path}")
        pending = [path]
        while pending:
            directory = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    entry_stat = entry.stat(follow_symlinks=False)
                    entry_path = Path(entry.path)
                    if (
                        stat.S_ISLNK(entry_stat.st_mode)
                        or getattr(entry_stat, "st_file_attributes", 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                    ):
                        raise ValueError(f"Refusing to copy a package containing a reparse point: {entry_path}")
                    if stat.S_ISDIR(entry_stat.st_mode):
                        pending.append(entry_path)


def _ensure_service_stopped() -> None:
    """Refuse package replacement while the registered service may hold files open."""
    import win32service

    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CONNECT)
    try:
        try:
            handle = win32service.OpenService(
                scm, SERVICE_NAME, win32service.SERVICE_QUERY_STATUS
            )
        except Exception as exc:
            error_code = getattr(exc, "winerror", None)
            if error_code is None and exc.args:
                error_code = exc.args[0]
            if error_code == 1060:
                return
            raise
        try:
            status = win32service.QueryServiceStatusEx(handle)
            current_state = status["CurrentState"]
            process_id = status["ProcessId"]
            if current_state != win32service.SERVICE_STOPPED or process_id:
                raise RuntimeError(
                    f"Cannot replace the agent package while {SERVICE_NAME} "
                    f"has not fully stopped (SCM state={current_state}, "
                    f"process_id={process_id}). Stop the service and retry."
                )
        finally:
            win32service.CloseServiceHandle(handle)
    finally:
        win32service.CloseServiceHandle(scm)


def _configure_delayed_start_and_recovery() -> None:
    import win32service

    scm = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
    try:
        handle = win32service.OpenService(scm, SERVICE_NAME, win32service.SERVICE_ALL_ACCESS)
        try:
            win32service.ChangeServiceConfig2(
                handle, win32service.SERVICE_CONFIG_DELAYED_AUTO_START_INFO, True
            )
            actions = [
                (win32service.SC_ACTION_RESTART, _RESTART_DELAY_MS),
                (win32service.SC_ACTION_RESTART, _RESTART_DELAY_MS),
                (win32service.SC_ACTION_NONE, 0),
            ]
            win32service.ChangeServiceConfig2(
                handle,
                win32service.SERVICE_CONFIG_FAILURE_ACTIONS,
                (_FAILURE_RESET_PERIOD_SECONDS, None, None, actions),
            )
            win32service.ChangeServiceConfig2(
                handle,
                win32service.SERVICE_CONFIG_FAILURE_ACTIONS_FLAG,
                True,
            )
        finally:
            win32service.CloseServiceHandle(handle)
    finally:
        win32service.CloseServiceHandle(scm)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--exe",
        type=Path,
        default=DEFAULT_EXE,
        help="Path to the packaged ITDSAgent.exe (default: build/dist/ITDSAgent/ITDSAgent.exe)",
    )
    args = parser.parse_args(argv)

    require_admin()

    if args.exe.name.casefold() != "ITDSAgent.exe".casefold():
        print(f"Expected the ITDSAgent.exe service binary, not {args.exe.name}.")
        return 1
    if not args.exe.is_file():
        print(f"ITDSAgent.exe not found at {args.exe}. Run build/build_exe.py first, or pass --exe.")
        return 1

    installed_exe = _install_package(args.exe, DEFAULT_INSTALL_DIR)
    secure_data_directories()
    _register_service(installed_exe)

    print(f"Service '{SERVICE_NAME}' installed (account={SERVICE_ACCOUNT}, start=automatic-delayed).")
    print(f"Service package installed at {DEFAULT_INSTALL_DIR}.")
    print("Next steps:")
    print("  1. Run ITDSAgentEnroll.exe (as Administrator) to store the agent credential.")
    print("  2. Create/verify %PROGRAMDATA%\\ITDS\\Agent\\config.json (see docs/operations/windows-agent.md).")
    print(f"  3. Start the service: sc start {SERVICE_NAME}  (or) Start-Service {SERVICE_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
