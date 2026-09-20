"""Database engine and session lifecycle helpers."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings
from .exceptions import DatabaseUnavailableError


@lru_cache(maxsize=1)
def get_engine(database_url: str | None = None) -> Engine:
    """Create an engine lazily; creating it never opens a database connection."""
    url = database_url or get_settings().database_url
    if not url:
        raise ValueError("DATABASE_URL must be configured before creating a database engine")
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update({"pool_size": 5, "max_overflow": 10, "pool_timeout": 30})
    return create_engine(url, **kwargs)


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    configured = settings or get_settings()
    return sessionmaker(bind=get_engine(configured.database_url), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that always closes the session."""
    try:
        session = get_session_factory()()
    except ValueError as exc:
        raise DatabaseUnavailableError from exc
    try:
        yield session
    finally:
        session.close()
