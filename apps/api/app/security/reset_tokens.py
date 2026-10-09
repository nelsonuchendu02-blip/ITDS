"""Secure password-reset token issuance and verification."""

import secrets

from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

_HASHER = PasswordHash.recommended()
PREFIX_LENGTH = 12
SECRET_LENGTH = 32


def issue_reset_token() -> tuple[str, str]:
    """Return ``(prefix, raw_token)`` for a new password-reset token."""
    prefix = secrets.token_urlsafe(PREFIX_LENGTH)[:PREFIX_LENGTH]
    secret = secrets.token_urlsafe(SECRET_LENGTH)
    return prefix, f"{prefix}.{secret}"


def extract_prefix(raw_token: str) -> str | None:
    """Extract the lookup prefix from a raw reset token."""
    if not raw_token or "." not in raw_token:
        return None

    prefix, _, remainder = raw_token.partition(".")

    if not prefix or not remainder:
        return None

    return prefix


def hash_reset_token(secret: str) -> str:
    """Hash a reset-token secret for persistent storage."""
    return _HASHER.hash(secret)


def verify_reset_token(secret: str, digest: str) -> bool:
    """Verify a reset-token secret against its stored digest."""
    try:
        return _HASHER.verify(secret, digest)
    except (TypeError, ValueError, UnknownHashError):
        return False
