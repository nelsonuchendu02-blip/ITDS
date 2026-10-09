import pytest
from fastapi.testclient import TestClient

from app.api.v1.endpoints import auth as auth_endpoints
from app.db import get_db
from app.main import app


@pytest.fixture
def client():
    def override_get_db():
        yield None

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class FakePasswordResetService:
    def __init__(self):
        self.requested_email = None
        self.confirmed_token = None
        self.confirmed_password = None

    def request_reset(self, session, *, email, settings=None):
        self.requested_email = email

    def reset_password(self, session, *, token, new_password):
        self.confirmed_token = token
        self.confirmed_password = new_password


def test_password_reset_request_returns_generic_accepted_response(
    client, monkeypatch
):
    fake_service = FakePasswordResetService()
    monkeypatch.setattr(
        auth_endpoints,
        "PasswordResetService",
        lambda: fake_service,
    )

    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "  USER@example.test  "},
    )

    assert response.status_code == 202
    assert "If an account exists" in response.json()["message"]
    assert fake_service.requested_email == "USER@example.test"


def test_password_reset_confirm_passes_token_and_password_to_service(
    client, monkeypatch
):
    fake_service = FakePasswordResetService()
    monkeypatch.setattr(
        auth_endpoints,
        "PasswordResetService",
        lambda: fake_service,
    )

    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={
            "token": "test-prefix.test-secret",
            "new_password": "a-new-password-long-enough",
        },
    )

    assert response.status_code == 204
    assert fake_service.confirmed_token == "test-prefix.test-secret"
    assert fake_service.confirmed_password == "a-new-password-long-enough"


def test_password_reset_request_rejects_malformed_email(client):
    response = client.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "not-an-email"},
    )

    assert response.status_code == 422


def test_password_reset_confirm_rejects_short_password(client):
    response = client.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": "test-prefix.test-secret", "new_password": "short"},
    )

    assert response.status_code == 422
