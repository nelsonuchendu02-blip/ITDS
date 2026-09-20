from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


client = TestClient(app)


def test_app_starts() -> None:
    assert app is not None


def test_health_endpoint() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "itds-api"


def test_versioned_status_route() -> None:
    response = client.get("/api/v1/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["api_version"] == "v1"


def test_config_loading() -> None:
    settings = get_settings()
    assert settings.app_name == "ITDS API"
    assert settings.api_prefix == "/api"


def test_not_found_is_structured() -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    payload = response.json()
    assert "error" in payload
    assert payload["error"]["code"] == "http_error"
