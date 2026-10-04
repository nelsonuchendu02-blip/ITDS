import json
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import (
    Agent,
    AgentCredential,
    AgentEnrollmentToken,
    AuditEvent,
    Base,
    Device,
    Organization,
    Role,
    User,
)
from app.schemas.agent import AgentEnrollmentResponse, EnrollmentTokenRead
from app.security.passwords import hash_password


@pytest.fixture
def enrollment_api(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[sessionmaker, str]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setenv("JWT_SECRET", "phase1o-enrollment-test-secret-" + "x" * 32)
    monkeypatch.setenv("JWT_ISSUER", "phase1o-enrollment-test")
    monkeypatch.setenv("JWT_AUDIENCE", "phase1o-enrollment-test-client")
    get_settings.cache_clear()

    with session_factory() as session:
        organization = Organization(name="Phase 1O enrollment test")
        administrator = User(
            organization=organization,
            email="phase1o-admin@example.test",
            display_name="Phase 1O test administrator",
            password_hash=hash_password("phase1o-test-password-never-log"),
        )
        administrator.roles.append(
            Role(name="organization_admin", organization=organization)
        )
        device = Device(
            organization=organization,
            hostname="phase1o-enrollment-device",
            device_type="workstation",
            operating_system="Windows",
        )
        session.add_all([organization, administrator, device])
        session.commit()
        device_id = str(device.id)

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield session_factory, device_id
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        get_settings.cache_clear()
        engine.dispose()


def test_enrollment_api_persists_agent_and_audit_without_logging_secrets(
    enrollment_api: tuple[sessionmaker, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    session_factory, device_id = enrollment_api
    test_password = "phase1o-test-password-never-log"
    client = TestClient(app, raise_server_exceptions=False)

    login_response = client.post(
        "/api/v1/auth/token",
        data={
            "username": "phase1o-admin@example.test",
            "password": test_password,
        },
    )
    assert login_response.status_code == 200, "Test administrator authentication failed."
    access_token = login_response.json()["access_token"]
    authorization = {"Authorization": f"Bearer {access_token}"}

    token_response = client.post(
        "/api/v1/agents/enrollment-tokens",
        headers=authorization,
        json={"target_device_id": device_id},
    )
    assert token_response.status_code == 201, "Enrollment token issuance failed."
    token_data = EnrollmentTokenRead.model_validate(token_response.json())
    enrollment_token = token_data.token

    enrollment_response = client.post(
        "/api/v1/agents/enroll",
        json={
            "token": enrollment_token,
            "agent_name": "phase1o-api-enrollment-test",
            "agent_version": "1.0.0-test",
            "platform": "windows",
        },
    )
    assert enrollment_response.status_code == 201, "Agent enrollment did not return HTTP 201."

    response_data = enrollment_response.json()
    assert set(response_data) == {"agent", "credential"}, (
        "Enrollment response did not contain exactly the documented fields."
    )
    enrollment = AgentEnrollmentResponse.model_validate(response_data)
    agent_data = response_data["agent"]
    assert enrollment.credential, "Enrollment response omitted the issued credential."
    assert agent_data["id"], "Enrollment response omitted the agent ID."
    assert agent_data["created_at"], "Enrollment response omitted created_at."
    assert agent_data["updated_at"], "Enrollment response omitted updated_at."
    assert agent_data["enrolled_at"], "Enrollment response omitted enrolled_at."
    credential_occurrences = json.dumps(response_data).count(enrollment.credential)
    assert credential_occurrences == 1, (
        "Enrollment response did not return the credential exactly once."
    )

    with session_factory() as session:
        agent_id = agent_data["id"]
        agent = session.get(Agent, agent_id)
        assert agent is not None, "Enrolled agent row was not persisted."
        assert agent.created_at is not None
        assert agent.updated_at is not None
        assert agent.enrolled_at is not None

        stored_credential = session.scalar(
            select(AgentCredential).where(AgentCredential.agent_id == agent.id)
        )
        assert stored_credential is not None, "Agent credential row was not persisted."
        credential_hash = stored_credential.credential_hash
        credential_is_hashed = stored_credential.credential_hash != enrollment.credential
        assert credential_is_hashed, (
            "Agent credential was not persisted as a hash."
        )

        consumed_token = session.scalar(
            select(AgentEnrollmentToken).where(AgentEnrollmentToken.id == token_data.id)
        )
        assert consumed_token is not None and consumed_token.consumed_at is not None, (
            "Enrollment token was not consumed."
        )
        enrollment_token_hash = consumed_token.token_hash

        audit_events = session.scalars(
            select(AuditEvent).where(AuditEvent.event_type == "agent_enrolled")
        ).all()
        assert len(audit_events) == 1, "Expected exactly one agent enrollment audit event."
        assert audit_events[0].resource_id == str(agent.id), (
            "Enrollment audit resource_id does not match the persisted agent UUID."
        )

        agent_count_before_rejections = len(session.scalars(select(Agent)).all())
        credential_count_before_rejections = len(
            session.scalars(select(AgentCredential)).all()
        )

    repeated_response = client.post(
        "/api/v1/agents/enroll",
        json={
            "token": enrollment_token,
            "agent_name": "phase1o-replayed-token-test",
            "platform": "windows",
        },
    )
    assert repeated_response.status_code == 401, (
        "Reusing the consumed enrollment token was not rejected."
    )

    duplicate_token_response = client.post(
        "/api/v1/agents/enrollment-tokens",
        headers=authorization,
        json={"target_device_id": device_id},
    )
    assert duplicate_token_response.status_code == 201, (
        "Could not issue a token for the duplicate-device rejection check."
    )
    duplicate_token = EnrollmentTokenRead.model_validate(
        duplicate_token_response.json()
    ).token
    duplicate_device_response = client.post(
        "/api/v1/agents/enroll",
        json={
            "token": duplicate_token,
            "agent_name": "phase1o-duplicate-device-test",
            "platform": "windows",
        },
    )
    assert duplicate_device_response.status_code == 409, (
        "Duplicate device enrollment was not rejected."
    )

    with session_factory() as session:
        assert len(session.scalars(select(Agent)).all()) == agent_count_before_rejections, (
            "Rejected enrollment unexpectedly persisted an agent."
        )
        assert len(session.scalars(select(AgentCredential)).all()) == (
            credential_count_before_rejections
        ), "Rejected enrollment unexpectedly persisted a credential."
        enrollment_token_hashes = session.scalars(
            select(AgentEnrollmentToken.token_hash)
        ).all()

    with session_factory() as session:
        user = session.scalar(
            select(User).where(User.email == "phase1o-admin@example.test")
        )
        user_password_hash = user.password_hash if user else ""
        raw_secret_values = (
            test_password,
            user_password_hash,
            access_token,
            enrollment_token,
            enrollment.credential,
            token_data.token,
            credential_hash,
            enrollment_token_hash,
            duplicate_token,
            *enrollment_token_hashes,
        )
    captured_logs = caplog.text
    secrets_absent_from_logs = all(
        not secret or secret not in captured_logs for secret in raw_secret_values
    )
    assert secrets_absent_from_logs, "Sensitive enrollment data appeared in captured logs."
