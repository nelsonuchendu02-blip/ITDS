from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import get_db
from app.exceptions import DatabaseUnavailableError
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


def test_database_readiness_endpoint_with_isolated_sqlite() -> None:
    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)

    def override_get_db():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = client.get("/api/v1/health/database")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "sqlite"}


def test_database_readiness_endpoint_failure_is_structured() -> None:
    def unavailable_database():
        raise DatabaseUnavailableError
        yield

    app.dependency_overrides[get_db] = unavailable_database
    try:
        response = client.get("/api/v1/health/database")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "database_unavailable", "message": "Database is unavailable"}
    }


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
