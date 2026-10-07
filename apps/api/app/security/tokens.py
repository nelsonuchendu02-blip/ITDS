from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt

from ..config import SUPPORTED_JWT_ALGORITHMS, Settings, get_settings


@dataclass(frozen=True)
class AccessTokenClaims:
    subject: UUID
    token_id: UUID


def _settings(settings: Settings | None = None) -> Settings:
    configured = settings or get_settings()
    if not configured.jwt_secret:
        raise ValueError("JWT_SECRET must be configured before issuing or validating tokens")
    if configured.jwt_algorithm not in SUPPORTED_JWT_ALGORITHMS:
        raise ValueError("JWT_ALGORITHM is not supported")
    return configured


def get_access_token_expiration(
    *,
    issued_at: datetime,
    settings: Settings | None = None,
) -> datetime:
    configured = _settings(settings)
    return issued_at + timedelta(minutes=configured.jwt_access_token_minutes)


def create_access_token(
    subject: UUID,
    *,
    token_id: UUID | None = None,
    issued_at: datetime | None = None,
    expires_at: datetime | None = None,
    settings: Settings | None = None,
) -> str:
    configured = _settings(settings)
    effective_issued_at = issued_at or datetime.now(timezone.utc)
    effective_token_id = token_id or uuid4()
    effective_expires_at = expires_at or get_access_token_expiration(
        issued_at=effective_issued_at,
        settings=configured,
    )

    claims: dict[str, object] = {
        "sub": str(subject),
        "exp": effective_expires_at,
        "iat": effective_issued_at,
        "jti": str(effective_token_id),
        "typ": "access",
    }

    if configured.jwt_issuer:
        claims["iss"] = configured.jwt_issuer
    if configured.jwt_audience:
        claims["aud"] = configured.jwt_audience

    return jwt.encode(
        claims,
        configured.jwt_secret,
        algorithm=configured.jwt_algorithm,
    )


def decode_access_token(
    token: str,
    settings: Settings | None = None,
) -> AccessTokenClaims:
    configured = _settings(settings)
    options = {"require": ["sub", "exp", "iat", "jti", "typ"]}
    decode_kwargs: dict[str, object] = {
        "algorithms": [configured.jwt_algorithm],
        "options": options,
    }

    if configured.jwt_issuer:
        decode_kwargs["issuer"] = configured.jwt_issuer
    if configured.jwt_audience:
        decode_kwargs["audience"] = configured.jwt_audience

    claims = jwt.decode(
        token,
        configured.jwt_secret,
        **decode_kwargs,
    )

    if claims.get("typ") != "access":
        raise jwt.InvalidTokenError("invalid token type")

    try:
        subject = UUID(str(claims["sub"]))
        token_id = UUID(str(claims["jti"]))
    except (KeyError, ValueError) as exc:
        raise jwt.InvalidTokenError("invalid token claims") from exc

    return AccessTokenClaims(
        subject=subject,
        token_id=token_id,
    )
