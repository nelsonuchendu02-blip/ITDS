"""Secure one-time secret issuance and verification for agent tokens/credentials.

Secrets are generated as ``{prefix}.{secret}``. The prefix is stored in plain
text in an indexed column so authentication can look up a candidate row in
O(1) instead of scanning and verifying every stored hash. Only the Argon2
digest of the full secret is ever persisted.
"""
import secrets

from pwdlib import PasswordHash

_HASHER = PasswordHash.recommended()
PREFIX_LENGTH = 12


def issue_secret() -> tuple[str, str]:
    """Return ``(prefix, raw_secret)`` for a new one-time secret."""
    prefix = secrets.token_urlsafe(PREFIX_LENGTH)[:PREFIX_LENGTH]
    secret = secrets.token_urlsafe(32)
    return prefix, f"{prefix}.{secret}"


def extract_prefix(raw_secret: str) -> str | None:
    if not raw_secret or "." not in raw_secret:
        return None
    prefix, _, remainder = raw_secret.partition(".")
    if not prefix or not remainder:
        return None
    return prefix


def hash_secret(secret: str) -> str:
    return _HASHER.hash(secret)


def verify_secret(secret: str, digest: str) -> bool:
    try:
        return _HASHER.verify(secret, digest)
    except (TypeError, ValueError):
        return False
