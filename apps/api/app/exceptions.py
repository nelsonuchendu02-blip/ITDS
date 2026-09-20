from typing import Any

from fastapi import Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class PersistenceError(Exception):
    """Safe application-level representation of an expected persistence failure."""


class DatabaseUnavailableError(Exception):
    """Raised when a request cannot establish the configured database session."""


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


def register_exception_handlers(app: Any) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(FastAPIHTTPException, http_exception_handler)
    app.add_exception_handler(DatabaseUnavailableError, database_unavailable_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
