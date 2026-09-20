from typing import Any

from fastapi import Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class PersistenceError(Exception):
    """Safe application-level representation of an expected persistence failure."""

    def __init__(self, message: str, status_code: int = 409) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DatabaseUnavailableError(Exception):
    """Raised when a request cannot establish the configured database session."""


class SecurityError(Exception):
    """Controlled authentication or authorization failure."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Return a structured error payload for client errors."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": "http_error",
                "message": exc.detail,
            }
        },
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    """Avoid leaking debug internals in production responses."""
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_server_error",
                "message": "An unexpected internal error occurred.",
            }
        },
    )


async def database_unavailable_handler(_: Request, __: DatabaseUnavailableError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"error": {"code": "database_unavailable", "message": "Database is unavailable"}},
    )


async def security_error_handler(_: Request, exc: SecurityError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
        headers={"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None,
    )


async def persistence_error_handler(_: Request, exc: PersistenceError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": "persistence_error", "message": exc.message}},
    )


def register_exception_handlers(app: Any) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(FastAPIHTTPException, http_exception_handler)
    app.add_exception_handler(DatabaseUnavailableError, database_unavailable_handler)
    app.add_exception_handler(SecurityError, security_error_handler)
    app.add_exception_handler(PersistenceError, persistence_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
