"""Phase 1N dashboard aggregation endpoint tests.

Covers organization-scoped aggregate accuracy, permission-aware section
visibility, and cross-organization isolation for GET /api/v1/dashboard/overview.
"""
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import (
    Agent,
    AgentStatus,
    Base,
    Device,
    DiscoveryJob,
    DiscoveryJobStatus,
    Incident,
    IncidentStatus,
    Organization,
    Recommendation,
    RecommendationStatus,
    Role,
    User,
)
from app.security.tokens import create_access_token


@dataclass
class DashboardContext:
    session_factory: object
    admin_token: str
    viewer_only_devices_token: str
    other_org_token: str


@pytest.fixture
def dashboard_context(monkeypatch: pytest.MonkeyPatch) -> Iterator[DashboardContext]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setenv("JWT_SECRET", "dashboard-test-" + "x" * 32)
    get_settings.cache_clear()

    with session_factory() as session:
        org = Organization(name="Dashboard org")
        other_org = Organization(name="Other dashboard org")

        admin = User(organization=org, email="dash-admin@test", display_name="Admin")
        admin.roles.append(Role(organization=org, name="organization_admin"))

        # "viewer" role only grants devices:read, monitoring:read, agents:read -
        # used to prove that incidents/discovery/recommendations sections are
        # omitted (not zeroed) when the caller lacks those permissions.
        limited = User(organization=org, email="dash-viewer@test", display_name="Viewer")
        limited.roles.append(Role(organization=org, name="viewer"))

        other_admin = User(organization=other_org, email="other-admin@test", display_name="Other admin")
        other_admin.roles.append(Role(organization=other_org, name="organization_admin"))

        # Two devices in-scope, one out-of-scope.
        device_a = Device(organization=org, hostname="dash-device-a", device_type="server", operating_system="Linux")
        device_b = Device(organization=org, hostname="dash-device-b", device_type="server", operating_system="Linux")
        other_device = Device(organization=other_org, hostname="other-device", device_type="server", operating_system="Linux")

        agent_active = Agent(organization=org, agent_name="agent-active", status=AgentStatus.ACTIVE, device_id=None)
        agent_pending = Agent(organization=org, agent_name="agent-pending", status=AgentStatus.PENDING, device_id=None)
        other_agent = Agent(organization=other_org, agent_name="other-agent", status=AgentStatus.ACTIVE, device_id=None)

        incident_open = Incident(organization=org, title="Open incident", status=IncidentStatus.OPEN, opened_at=datetime.now(timezone.utc))
        incident_in_progress = Incident(organization=org, title="In progress incident", status=IncidentStatus.IN_PROGRESS, opened_at=datetime.now(timezone.utc))
        incident_closed = Incident(organization=org, title="Closed incident", status=IncidentStatus.CLOSED, opened_at=datetime.now(timezone.utc))
        other_incident = Incident(organization=other_org, title="Other open incident", status=IncidentStatus.OPEN, opened_at=datetime.now(timezone.utc))

        job_running = DiscoveryJob(
            organization=org, provider="simulated", target_type="address",
            target_definition="192.0.2.1", target_count=1, status=DiscoveryJobStatus.RUNNING,
        )
        job_completed = DiscoveryJob(
            organization=org, provider="simulated", target_type="address",
            target_definition="192.0.2.2", target_count=1, status=DiscoveryJobStatus.COMPLETED,
        )
        other_job = DiscoveryJob(
            organization=other_org, provider="simulated", target_type="address",
            target_definition="192.0.2.3", target_count=1, status=DiscoveryJobStatus.RUNNING,
        )

        recommendation_pending = Recommendation(organization=org, title="Pending rec", status=RecommendationStatus.PENDING)
        recommendation_accepted = Recommendation(organization=org, title="Accepted rec", status=RecommendationStatus.ACCEPTED)
        other_recommendation = Recommendation(organization=other_org, title="Other rec", status=RecommendationStatus.PENDING)

        session.add_all([
            org, other_org, admin, limited, other_admin,
            device_a, device_b, other_device,
            agent_active, agent_pending, other_agent,
            incident_open, incident_in_progress, incident_closed, other_incident,
            job_running, job_completed, other_job,
            recommendation_pending, recommendation_accepted, other_recommendation,
        ])
        session.commit()

        context = DashboardContext(
            session_factory=session_factory,
            admin_token=create_access_token(admin.id),
            viewer_only_devices_token=create_access_token(limited.id),
            other_org_token=create_access_token(other_admin.id),
        )

    def override_get_db():
        with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield context
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_overview_returns_accurate_organization_scoped_aggregates(dashboard_context):
    client = TestClient(app)
    response = client.get(
        "/api/v1/dashboard/overview",
        headers={"Authorization": f"Bearer {dashboard_context.admin_token}"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["devices"]["total"] == 2
    assert body["agents"] == {"total": 2, "active": 1}
    assert body["incidents"] == {"open": 1, "in_progress": 1}
    assert body["discovery"] == {"total": 2, "running": 1, "pending": 0, "completed": 1, "failed": 0}
    assert body["recommendations"] == {"total": 2, "pending": 1}
    assert "monitoring" in body
    assert "generated_at" in body


def test_overview_omits_sections_without_permission(dashboard_context):
    client = TestClient(app)
    response = client.get(
        "/api/v1/dashboard/overview",
        headers={"Authorization": f"Bearer {dashboard_context.viewer_only_devices_token}"},
    )
    assert response.status_code == 200
    body = response.json()

    # "viewer" role grants devices/monitoring/agents read, but not
    # incidents/discovery/recommendations.
    assert body["devices"]["total"] == 2
    assert body["agents"] == {"total": 2, "active": 1}
    assert body["incidents"] is None
    assert body["discovery"] is None
    assert body["recommendations"] is None


def test_overview_is_organization_isolated(dashboard_context):
    client = TestClient(app)
    response = client.get(
        "/api/v1/dashboard/overview",
        headers={"Authorization": f"Bearer {dashboard_context.other_org_token}"},
    )
    assert response.status_code == 200
    body = response.json()

    assert body["devices"]["total"] == 1
    assert body["agents"] == {"total": 1, "active": 1}
    assert body["incidents"] == {"open": 1, "in_progress": 0}
    assert body["discovery"]["total"] == 1
    assert body["recommendations"]["total"] == 1


def test_overview_requires_authentication(dashboard_context):
    client = TestClient(app)
    response = client.get("/api/v1/dashboard/overview")
    assert response.status_code == 401
