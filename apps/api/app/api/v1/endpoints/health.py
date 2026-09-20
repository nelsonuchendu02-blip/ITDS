from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ....db import get_db

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/database")
def database_health(session: Session = Depends(get_db)) -> dict[str, str]:
    """Check database connectivity without exposing connection details."""
    try:
        session.execute(text("SELECT 1"))
        dialect = session.get_bind().dialect.name
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ok", "database": dialect}
