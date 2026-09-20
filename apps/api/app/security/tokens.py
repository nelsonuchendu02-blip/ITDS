from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt

from ..config import SUPPORTED_JWT_ALGORITHMS, Settings, get_settings


def _settings(settings: Settings | None = None) -> Settings:
    configured = settings or get_settings()
    if not configured.jwt_secret:
        raise ValueError("JWT_SECRET must be configured before issuing or validating tokens")
    if configured.jwt_algorithm not in SUPPORTED_JWT_ALGORITHMS:
        raise ValueError("JWT_ALGORITHM is not supported")
    return configured


def create_access_token(subject: UUID, settings: Settings | None = None) -> str:
    configured = _settings(settings)
    now = datetime.now(timezone.utc)
    claims: dict[str, object] = {
        "sub": str(subject),
        "exp": now + timedelta(minutes=configured.jwt_access_token_minutes),
        "iat": now,
        "jti": str(uuid4()),
        "typ": "access",
    }
    if configured.jwt_issuer:
        claims["iss"] = configured.jwt_issuer
    if configured.jwt_audience:
        claims["aud"] = configured.jwt_audience
    return jwt.encode(claims, configured.jwt_secret, algorithm=configured.jwt_algorithm)


def decode_access_token(token: str, settings: Settings | None = None) -> UUID:
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
    claims = jwt.decode(token, configured.jwt_secret, **decode_kwargs)
    if claims.get("typ") != "access":
        raise jwt.InvalidTokenError("invalid token type")
    try:
        subject = UUID(str(claims["sub"]))
        token_id = UUID(str(claims["jti"]))
    except (KeyError, ValueError) as exc:
        raise jwt.InvalidTokenError("invalid token claims") from exc
    return subject
