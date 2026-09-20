from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_db
from app.api.dependencies.auth import get_discovery_service
from app.exceptions import PersistenceError
from app.main import app
from app.models import (
    AuditEvent,
    Base,
    Device,
    DiscoveryJob,
    DiscoveryJobStatus,
    Organization,
    Role,
    User,
)
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.schemas import DiscoveryJobCreate, DiscoveryJobRead, DiscoveryResultRead
from app.services.discovery import DiscoveryService


@dataclass
class DiscoveryContext:
    session_factory: sessionmaker
    admin_token: str
    support_token: str
    viewer_token: str
    other_admin_token: str
    job_id: str
    other_job_id: str
    result_device_id: str
    organization_id: str
    admin_id: str


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


class ExplodingProvider:
    name = "simulated"

    def discover(self, target):
        raise RuntimeError("provider secret and stack trace must not escape")


class CancellingProvider:
    name = "simulated"

    def __init__(self, session_factory: sessionmaker) -> None:
        self.session_factory = session_factory

    def discover(self, target):
        with self.session_factory() as session:
            job = session.scalar(select(DiscoveryJob).where(DiscoveryJob.target_definition == target.definition))
            assert job is not None
            job.status = DiscoveryJobStatus.CANCELLED
            session.commit()
        return []


@pytest.fixture
def discovery_context(monkeypatch: pytest.MonkeyPatch) -> Iterator[DiscoveryContext]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setenv("JWT_SECRET", "test-secret-" + "x" * 32)
    monkeypatch.setenv("JWT_ISSUER", "itds-test")
    monkeypatch.setenv("JWT_AUDIENCE", "itds-test-client")
    get_settings.cache_clear()

    with session_factory() as session:
        organization = Organization(name="Managed")
        other_organization = Organization(name="Other")
        admin = User(
            organization=organization, email="admin@managed.test",
            display_name="Admin", password_hash=hash_password("secret-password"),
        )
        admin.roles.append(Role(name="organization_admin", organization=organization))
        support = User(
            organization=organization, email="support@managed.test",
            display_name="Support", password_hash=hash_password("secret-password"),
        )
        support.roles.append(Role(name="it_support", organization=organization))
        viewer = User(
            organization=organization, email="viewer@managed.test",
            display_name="Viewer", password_hash=hash_password("secret-password"),
        )
        viewer.roles.append(Role(name="viewer", organization=organization))
        other_admin = User(
            organization=other_organization, email="admin@other.test",
            display_name="Other Admin", password_hash=hash_password("secret-password"),
        )
        other_admin.roles.append(Role(name="organization_admin", organization=other_organization))
        matched_device = Device(
            organization=organization, hostname="known-host",
            device_type="server", operating_system="Linux", ip_address="192.0.2.50",
        )
        job = DiscoveryJob(
            organization=organization, created_by_user_id=admin.id,
            provider="simulated", target_type="address",
            target_definition="192.0.2.50", target_count=1,
        )
        other_job = DiscoveryJob(
            organization=other_organization, created_by_user_id=other_admin.id,
            provider="simulated", target_type="address",
            target_definition="192.0.2.60", target_count=1,
        )
        session.add_all([
            organization, other_organization, admin, support, viewer, other_admin,
            matched_device, job, other_job,
        ])
        session.commit()
        context = DiscoveryContext(
            session_factory=session_factory,
            admin_token=create_access_token(admin.id),
            support_token=create_access_token(support.id),
            viewer_token=create_access_token(viewer.id),
            other_admin_token=create_access_token(other_admin.id),
            job_id=str(job.id),
            other_job_id=str(other_job.id),
            result_device_id=str(matched_device.id),
            organization_id=str(organization.id),
            admin_id=str(admin.id),
        )

    def override_get_db() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield context
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_create_normalizes_target_and_records_audit(discovery_context: DiscoveryContext) -> None:
    response = TestClient(app).post(
        "/api/v1/discovery/jobs",
        headers=_headers(discovery_context.admin_token),
        json={"provider": "simulated", "target": "192.0.2.1/24"},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["organization_id"] == discovery_context.organization_id
    assert payload["target_type"] == "cidr"
    assert payload["target_definition"] == "192.0.2.0/24"
    assert payload["target_count"] == 256
    with discovery_context.session_factory() as session:
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "discovery_job_created",
                AuditEvent.resource_id == payload["id"],
            )
        )
        assert event is not None
        assert str(event.organization_id) == discovery_context.organization_id
        assert str(event.actor_user_id) == discovery_context.admin_id
        assert event.action == "create"
        assert event.result == "success"
        assert event.resource_type == "discovery_job"
        assert event.event_metadata == {
            "provider": "simulated",
            "target_type": "cidr",
            "target_count": 256,
        }


@pytest.mark.parametrize("target", ["not-an-ip", "10.0.0.0/16", "2001:db8::1"])
def test_invalid_or_oversized_targets_are_rejected(
    discovery_context: DiscoveryContext, target: str
) -> None:
    response = TestClient(app).post(
        "/api/v1/discovery/jobs",
        headers=_headers(discovery_context.admin_token),
        json={"target": target},
    )
    assert response.status_code == 422


def test_job_scope_lifecycle_results_and_reconciliation(discovery_context: DiscoveryContext) -> None:
    client = TestClient(app)
    headers = _headers(discovery_context.admin_token)
    job = client.get(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}", headers=headers
    )
    assert job.status_code == 200
    assert job.json()["status"] == "pending"

    run = client.post(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/run", headers=headers
    )
    assert run.status_code == 200
    assert run.json()["status"] == "completed"
    assert client.post(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/run", headers=headers
    ).status_code == 409

    results = client.get(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/results", headers=headers
    )
    assert results.status_code == 200
    assert results.json()["meta"]["total"] == 1
    result = results.json()["items"][0]
    assert result["organization_id"] == discovery_context.organization_id
    assert result["matched_device_id"] == discovery_context.result_device_id
    assert result["reconciliation_status"] == "matched"

    with discovery_context.session_factory() as session:
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.resource_id == discovery_context.job_id)
        ).all()
        assert {"discovery_started", "discovery_completed"} <= {
            event.event_type for event in events
        }
        result_event = session.scalar(
            select(AuditEvent).where(AuditEvent.event_type == "discovery_result_recorded")
        )
        assert result_event is not None
        assert result_event.resource_type == "discovery_result"
        assert result_event.action == "record"
        assert result_event.result == "success"


def test_cross_organization_and_nonexistent_jobs_are_not_disclosed(
    discovery_context: DiscoveryContext,
) -> None:
    client = TestClient(app)
    other_view = client.get(
        f"/api/v1/discovery/jobs/{discovery_context.other_job_id}",
        headers=_headers(discovery_context.admin_token),
    )
    missing = client.get(
        "/api/v1/discovery/jobs/00000000-0000-0000-0000-000000000000",
        headers=_headers(discovery_context.admin_token),
    )
    assert other_view.status_code == missing.status_code == 404
    assert other_view.json() == missing.json()
    assert client.get(
        f"/api/v1/discovery/jobs/{discovery_context.other_job_id}/results",
        headers=_headers(discovery_context.admin_token),
    ).status_code == 404


def test_cancel_and_authorization_policy(discovery_context: DiscoveryContext) -> None:
    client = TestClient(app)
    support_headers = _headers(discovery_context.support_token)
    viewer_headers = _headers(discovery_context.viewer_token)
    created = client.post(
        "/api/v1/discovery/jobs",
        headers=support_headers,
        json={"target": "192.0.2.70"},
    )
    assert created.status_code == 403
    assert client.get("/api/v1/discovery/jobs", headers=support_headers).status_code == 200
    assert client.get("/api/v1/discovery/jobs", headers=viewer_headers).status_code == 403
    assert client.post(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/cancel",
        headers=viewer_headers,
    ).status_code == 403

    cancelled = client.post(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/cancel",
        headers=_headers(discovery_context.admin_token),
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.post(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/run",
        headers=_headers(discovery_context.admin_token),
    ).status_code == 409


def test_provider_failure_is_safe_and_audited(discovery_context: DiscoveryContext) -> None:
    service = DiscoveryService(providers={"simulated": ExplodingProvider()})
    app.dependency_overrides[get_discovery_service] = lambda: service
    try:
        response = TestClient(app).post(
            f"/api/v1/discovery/jobs/{discovery_context.job_id}/run",
            headers=_headers(discovery_context.admin_token),
        )
    finally:
        app.dependency_overrides.pop(get_discovery_service, None)

    assert response.status_code == 500
    assert "provider secret" not in response.text
    assert "RuntimeError" not in response.text
    with discovery_context.session_factory() as session:
        job = session.get(DiscoveryJob, discovery_context.job_id)
        assert job is not None
        assert job.status is DiscoveryJobStatus.FAILED
        assert job.error_code == "discovery_execution_failed"
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "discovery_failed",
                AuditEvent.resource_id == discovery_context.job_id,
            )
        )
        assert event is not None
        assert event.event_metadata == {"error_code": "discovery_execution_failed"}


def test_cancelled_job_cannot_be_finalized_completed(
    discovery_context: DiscoveryContext,
) -> None:
    with discovery_context.session_factory() as session:
        job = session.get(DiscoveryJob, discovery_context.job_id)
        assert job is not None
        service = DiscoveryService(
            providers={"simulated": CancellingProvider(discovery_context.session_factory)}
        )
        result = service.start_job(
            session,
            job=job,
            actor=session.get(User, discovery_context.admin_id),
        )
        assert result.status is DiscoveryJobStatus.CANCELLED

    with discovery_context.session_factory() as session:
        job = session.get(DiscoveryJob, discovery_context.job_id)
        assert job is not None
        assert job.status is DiscoveryJobStatus.CANCELLED


def test_lifecycle_operations_remain_organization_scoped(
    discovery_context: DiscoveryContext,
) -> None:
    client = TestClient(app)
    other_headers = _headers(discovery_context.other_admin_token)
    assert client.post(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/run",
        headers=other_headers,
    ).status_code == 404
    assert client.post(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/cancel",
        headers=other_headers,
    ).status_code == 404


def test_result_filters_and_pagination_are_bounded(discovery_context: DiscoveryContext) -> None:
    client = TestClient(app)
    headers = _headers(discovery_context.admin_token)
    assert client.post(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/run", headers=headers
    ).status_code == 200
    page = client.get(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/results?page_size=1&ip=192.0.2.50",
        headers=headers,
    )
    too_large = client.get(
        f"/api/v1/discovery/jobs/{discovery_context.job_id}/results?page_size=101",
        headers=headers,
    )
    assert page.status_code == 200
    assert page.json()["meta"] == {"page": 1, "page_size": 1, "total": 1}
    assert too_large.status_code == 422


def test_discovery_schemas_exclude_server_controlled_fields() -> None:
    assert set(DiscoveryJobCreate.model_fields) == {"provider", "target"}
    assert set(DiscoveryJobRead.model_fields) >= {"status", "organization_id", "created_by_user_id"}
    assert set(DiscoveryResultRead.model_fields) >= {"organization_id", "discovery_job_id"}
