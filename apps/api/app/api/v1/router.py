from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["v1"])


@router.get("/status")
def api_status() -> dict[str, str]:
    """Return a basic versioned status payload for the API."""
    return {"status": "ok", "api_version": "v1"}
