"""Operator CLI to store or clear the agent's protected credential.

Run as ``python -m itds_agent.security.enroll`` (or the packaged
``ITDSAgentEnroll.exe``) once per device, after the device has been
enrolled through the ITDS API and a credential has been issued.

The credential is never accepted as a command-line argument (which would
leak into shell history and process listings); it is always read via
``getpass`` from an interactive, non-echoing prompt. This module performs
no network calls and no shell/PowerShell/WMI/subprocess execution - it only
writes the DPAPI-protected credential file via `CredentialStore`.
"""
from __future__ import annotations

import argparse
import getpass
import sys

from .credential_store import CredentialStore, CredentialStoreError
from ..config.paths import credential_path


def _prompt_for_credential() -> str:
    credential = getpass.getpass("Agent credential (input hidden): ")
    if not credential:
        raise SystemExit("itds-agent-enroll: no credential entered; aborting")
    return credential


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="itds-agent-enroll",
        description="Store or clear the ITDS agent's protected credential (DPAPI, Windows only).",
    )
    parser.add_argument(
        "--clear",
        action="store_true",
        help="remove the currently stored credential instead of setting one",
    )
    args = parser.parse_args(argv)

    store = CredentialStore(credential_path())

    if args.clear:
        store.clear()
        print("itds-agent-enroll: stored credential removed")
        return 0

    credential = _prompt_for_credential()
    try:
        store.save(credential)
    except CredentialStoreError as exc:
        print(f"itds-agent-enroll: failed to store credential: {exc}", file=sys.stderr)
        return 1
    finally:
        # Best-effort: drop the local reference promptly; Python cannot
        # guarantee secure memory wiping, but this avoids holding it longer
        # than necessary in this short-lived process.
        del credential

    print(f"itds-agent-enroll: credential stored at {credential_path()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
