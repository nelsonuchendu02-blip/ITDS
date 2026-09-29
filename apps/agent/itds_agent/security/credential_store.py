"""Windows-native credential protection for the agent's server credential.

The agent credential (returned once by `POST /api/v1/agents/enroll` or
`.../credentials/rotate`) must never be stored as plaintext where avoidable.
This module wraps Windows DPAPI (`CryptProtectData`/`CryptUnprotectData` via
`pywin32`) so the credential is encrypted at rest using a key tied to the
Windows account running the agent - no key material is stored by ITDS
itself, and nothing here calls a shell, PowerShell, or any subprocess.

Design notes:
- By default, DPAPI ties the ciphertext to the *specific Windows account*
  that encrypted it. That default is unusable here: the credential is
  enrolled interactively (as an Administrator, via `security/enroll.py`)
  but must later be decrypted by the `ITDSAgent` Windows service, which
  runs continuously as a *different* account (`NT AUTHORITY\\LocalService`
  - see `installer/common.py::SERVICE_ACCOUNT`). A per-user-protected blob
  would never be readable by that service account.
- To make the protected blob readable by any local account on the same
  machine (while still being unreadable off that machine, and still
  unreadable without the matching entropy), this module protects data with
  the `CRYPTPROTECT_LOCAL_MACHINE` flag. Per Microsoft's documented
  behavior, "any user on the computer where the encryption was done can
  decrypt the data" once this flag is set - no administrator rights are
  required for either the protect or unprotect call. This trades "only
  this exact Windows account can decrypt it" for "only this machine can
  decrypt it" - the correct tradeoff for a machine-wide Windows service
  whose account is fixed and known (`LocalService`), not for a per-user
  secret. This is the "which Windows account can access it" contract
  documented in `docs/security/windows-agent-security.md`. The tradeoff:
  any local account on this machine (including other services or locally
  logged-in users, subject to normal file permissions on
  `credential.bin`) could invoke DPAPI to decrypt the blob if they could
  also read the file and supply the same entropy - this is why the data
  directory's ACL (`installer/common.py::secure_data_directories`)
  additionally restricts the file itself to SYSTEM, Administrators, and
  `LocalService` only. DPAPI's local-machine scoping and the filesystem
  ACL are complementary controls, not substitutes for each other.
- An additional "entropy" value scopes the protected blob to this
  application, so even another process on the same machine cannot
  trivially unprotect it without also supplying the same entropy.
- This module never logs the plaintext credential; failures redact the
  credential and only report the generic operation that failed.
"""
from __future__ import annotations

from pathlib import Path

#: Additional entropy binds the protected blob to this application so that
#: DPAPI-protected data cannot be casually unprotected by unrelated
#: processes on the same machine.
_ENTROPY = b"itds-agent-credential-v1"

#: CRYPTPROTECT_LOCAL_MACHINE (win32cryptcon.CRYPTPROTECT_LOCAL_MACHINE = 0x4).
#: Protects the blob so any local account on this machine can decrypt it
#: (rather than only the exact account that encrypted it), which is what
#: lets the `LocalService` service account read a credential that was
#: enrolled interactively as an Administrator. The literal value is used
#: directly (rather than importing win32cryptcon) so this module's only
#: Windows-specific import remains the lazily-loaded `win32crypt`.
_CRYPTPROTECT_LOCAL_MACHINE = 0x4


class CredentialStoreError(RuntimeError):
    """A credential could not be stored or retrieved. Never includes the
    credential value itself."""


class CredentialStore:
    """Persists the agent credential using Windows DPAPI, scoped to a file.

    The encrypted blob is written to `credential_path` (by default under the
    agent's protected data directory). DPAPI protects the *content*
    (machine-scoped via `CRYPTPROTECT_LOCAL_MACHINE`, see the module
    docstring for why): even if `credential.bin` is copied elsewhere, it
    cannot be decrypted without both the same machine and the same entropy.
    DPAPI alone does not restrict *who on this machine* can read the file -
    that is what the NTFS ACL applied by
    `installer/common.py::secure_data_directories()` is for. Treat DPAPI
    machine-scoping and the directory ACL as two complementary controls:
    DPAPI scoping is necessary but not sufficient, and the ACL is necessary
    but not sufficient, for this credential to be readable only by
    `LocalService`/SYSTEM/Administrators on this one machine.
    """

    def __init__(self, credential_path: Path):
        self.credential_path = credential_path

    def _dpapi(self):
        try:
            import win32crypt  # noqa: PLC0415 - Windows-only, imported lazily
        except ImportError as exc:  # pragma: no cover - exercised only off Windows
            raise CredentialStoreError(
                "DPAPI credential protection requires pywin32 and is only available on Windows"
            ) from exc
        return win32crypt

    def save(self, credential: str) -> None:
        if not credential:
            raise CredentialStoreError("cannot store an empty credential")
        win32crypt = self._dpapi()
        try:
            protected = win32crypt.CryptProtectData(
                credential.encode("utf-8"),
                "ITDS agent credential",
                _ENTROPY,
                None,
                None,
                _CRYPTPROTECT_LOCAL_MACHINE,
            )
        except Exception as exc:  # noqa: BLE001 - never leak the credential in the message
            raise CredentialStoreError("failed to protect agent credential") from exc
        self.credential_path.parent.mkdir(parents=True, exist_ok=True)
        self.credential_path.write_bytes(protected)

    def load(self) -> str | None:
        if not self.credential_path.exists():
            return None
        win32crypt = self._dpapi()
        blob = self.credential_path.read_bytes()
        try:
            _description, plaintext = win32crypt.CryptUnprotectData(
                blob, _ENTROPY, None, None, _CRYPTPROTECT_LOCAL_MACHINE
            )
        except Exception as exc:  # noqa: BLE001 - never leak the credential in the message
            raise CredentialStoreError("failed to unprotect agent credential") from exc
        return plaintext.decode("utf-8")

    def clear(self) -> None:
        """Removes the protected credential file, e.g. during uninstall."""
        self.credential_path.unlink(missing_ok=True)

    def exists(self) -> bool:
        return self.credential_path.exists()
