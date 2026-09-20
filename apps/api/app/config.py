from functools import lru_cache
from typing import Final

from pydantic_settings import BaseSettings, SettingsConfigDict

SUPPORTED_JWT_ALGORITHMS: Final[frozenset[str]] = frozenset({"HS256"})


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables and `.env`."""

    app_name: str = "ITDS API"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    api_prefix: str = "/api"
    cors_allowed_origins: str = "http://localhost:5173"
    database_url: str | None = None
    jwt_secret: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_access_token_minutes: int = 15
    jwt_issuer: str | None = None
    jwt_audience: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def cors_origins(self) -> list[str]:
        return [item.strip() for item in self.cors_allowed_origins.split(",") if item.strip()]


def validate_authentication_configuration(settings: Settings | None = None) -> None:
    configured = settings or get_settings()
    if configured.jwt_algorithm not in SUPPORTED_JWT_ALGORITHMS:
        raise RuntimeError("JWT_ALGORITHM is not supported")
    if configured.environment.lower() == "production":
        if not configured.jwt_secret or len(configured.jwt_secret) < 32:
            raise RuntimeError("JWT_SECRET must be configured with at least 32 characters in production")
        if configured.jwt_access_token_minutes <= 0:
            raise RuntimeError("JWT_ACCESS_TOKEN_MINUTES must be positive")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
