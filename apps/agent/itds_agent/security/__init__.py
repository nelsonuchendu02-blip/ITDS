"""Windows-native security primitives for the endpoint agent.

Nothing in this package executes shell commands, PowerShell, WMI, or any
subprocess. It only wraps DPAPI-based credential-at-rest protection.
"""

from .credential_store import CredentialStore, CredentialStoreError

__all__ = ["CredentialStore", "CredentialStoreError"]
