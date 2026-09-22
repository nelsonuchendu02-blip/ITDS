from fastapi import APIRouter

from .endpoints.health import router as health_router
from .endpoints.auth import router as auth_router
from .endpoints.management import router as management_router
from .endpoints.devices import router as devices_router
from .endpoints.discovery import router as discovery_router
from .endpoints.diagnostics import router as diagnostics_router
from .endpoints.root_cause import router as root_cause_router
from .endpoints.recommendations import router as recommendations_router
from .endpoints.remediation import router as remediation_router

router = APIRouter(prefix="/api/v1", tags=["v1"])
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(management_router)
router.include_router(devices_router)
router.include_router(discovery_router)
router.include_router(diagnostics_router)
router.include_router(root_cause_router)
router.include_router(recommendations_router)
router.include_router(remediation_router)


@router.get("/status")
def api_status() -> dict[str, str]:
    """Return a basic versioned status payload for the API."""
    return {"status": "ok", "api_version": "v1"}
