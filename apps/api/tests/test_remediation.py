from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_db
from app.exceptions import SecurityError
from app.main import app
from app.models import (
    AuditEvent, Base, Device, Organization, Recommendation, RecommendationStatus,
    RemediationAction, RemediationActionStatus, RemediationPlanStatus,
    RemediationVerificationStatus, Role, User,
)
from app.remediation.catalog import validate_action
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.services.remediation import RemediationService


@pytest.fixture
def remediation_db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session = Session(engine)
    org = Organization(name="Remediation Org")
    actor = User(organization=org, email="remediation@example.test", display_name="Operator")
    device = Device(organization=org, hostname="remediation-01", device_type="server", operating_system="Linux")
    session.add_all([org, actor, device])
    session.flush()
    recommendation = Recommendation(
        organization=org, device=device, title="Refresh configuration",
        summary="Evidence-backed refresh", description="safe", rule_id="safe-refresh",
        fingerprint="fingerprint", status=RecommendationStatus.ACCEPTED,
    )
    session.add(recommendation)
    session.commit()
    yield session, actor, recommendation
    session.close()
    engine.dispose()


def test_generation_is_deterministic_and_lifecycle_is_guarded(remediation_db):
    session, actor, recommendation = remediation_db
    service = RemediationService()
    plan = service.generate(session, recommendation.id, actor)
    assert plan.status is RemediationPlanStatus.DRAFT
    assert plan.dry_run is True
    assert plan.root_cause_finding_id is None
    assert service.generate(session, recommendation.id, actor).id == plan.id
    with pytest.raises(SecurityError):
        service.execute(session, plan, actor)
    service.transition(session, plan, actor, RemediationPlanStatus.PENDING_APPROVAL)
    service.transition(session, plan, actor, RemediationPlanStatus.APPROVED)
    service.transition(session, plan, actor, RemediationPlanStatus.QUEUED)
    executed = service.execute(session, plan, actor)
    assert executed.status is RemediationPlanStatus.VERIFICATION_REQUIRED
    verified = service.verify(session, executed, actor)
    assert verified.status is RemediationPlanStatus.VERIFIED
    from app.models import RemediationAction
    action = session.query(RemediationAction).filter_by(plan_id=plan.id).one()
    assert action.result["executed"] is False
    assert action.status is RemediationActionStatus.SUCCEEDED


def test_action_catalog_rejects_unsafe_and_missing_parameters():
    with pytest.raises(ValueError):
        validate_action("restart_managed_service", {"service_name": "nginx"})
    with pytest.raises(ValueError):
        validate_action("refresh_device_configuration", {"source": "x", "reason": "x", "command": "id"})
    with pytest.raises(ValueError):
        validate_action("refresh_device_configuration", {"source": "x", "reason": "x", "nested": {}})


def test_phase_1j_enums_are_exact_bounded_values():
    assert {item.value for item in RemediationPlanStatus} == {
        "draft", "pending_approval", "approved", "rejected", "queued",
        "executing", "succeeded", "failed", "cancelled", "verification_required", "verified",
    }
    assert {item.value for item in RemediationActionStatus} == {
        "pending", "ready", "executing", "succeeded", "failed", "skipped", "cancelled",
    }
    assert {item.value for item in RemediationVerificationStatus} == {
        "pending", "passed", "failed", "inconclusive",
    }


def test_recommendation_rule_mapping_and_cross_org_integrity(remediation_db):
    session, actor, recommendation = remediation_db
    recommendation.rule_id = "configuration-failure"
    recommendation.evidence = {}
    session.commit()
    plan = RemediationService().generate(session, recommendation.id, actor)
    assert plan.actions[0].action_key == "apply_safe_configuration"
    session.connection().exec_driver_sql("PRAGMA foreign_keys=ON")
    other = Organization(name="Other")
    other_device = Device(organization=other, hostname="other-01", device_type="server", operating_system="Linux")
    session.add_all([other, other_device])
    session.flush()
    invalid = Recommendation(
        organization_id=actor.organization_id, device_id=other_device.id,
        title="Cross org", rule_id="security-failure", fingerprint="cross",
        status=RecommendationStatus.ACCEPTED,
    )
    session.add(invalid)
    with pytest.raises(IntegrityError):
        session.commit()


@pytest.fixture
def remediation_api(monkeypatch):
    """Build real records and use the same DB override pattern as API tests."""
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setenv("JWT_SECRET", "test-secret-" + "x" * 32)
    monkeypatch.setenv("JWT_ISSUER", "itds-test")
    monkeypatch.setenv("JWT_AUDIENCE", "itds-test-client")
    get_settings.cache_clear()

    with factory() as session:
        org = Organization(name="API Org")
        other_org = Organization(name="Other API Org")
        admin = User(organization=org, email="admin@api.test", display_name="Admin",
                     password_hash=hash_password("secret"))
        admin.roles.append(Role(name="organization_admin", organization=org))
        technician = User(organization=org, email="tech@api.test", display_name="Tech",
                          password_hash=hash_password("secret"))
        technician.roles.append(Role(name="technician", organization=org))
        viewer = User(organization=org, email="viewer@api.test", display_name="Viewer",
                      password_hash=hash_password("secret"))
        viewer.roles.append(Role(name="viewer", organization=org))
        other_admin = User(organization=other_org, email="admin@other-api.test",
                           display_name="Other Admin", password_hash=hash_password("secret"))
        other_admin.roles.append(Role(name="organization_admin", organization=other_org))
        device = Device(organization=org, hostname="api-device-a", device_type="server",
                        operating_system="Linux")
        second_device = Device(organization=org, hostname="api-device-b", device_type="server",
                               operating_system="Linux")
        other_device = Device(organization=other_org, hostname="other-api-device",
                              device_type="server", operating_system="Linux")
        session.add_all([org, other_org, admin, technician, viewer, other_admin,
                         device, second_device, other_device])
        session.flush()
        recommendations = []
        for item, target in (("A", device), ("B", second_device)):
            recommendations.append(Recommendation(
                organization=org, device=target, title=f"Refresh {item}", summary="Safe refresh",
                description="Evidence-backed", rule_id="safe-refresh", fingerprint=f"api-{item}",
                status=RecommendationStatus.ACCEPTED,
            ))
        other_recommendation = Recommendation(
            organization=other_org, device=other_device, title="Other refresh",
            summary="Other", description="Other", rule_id="safe-refresh", fingerprint="other-api",
            status=RecommendationStatus.ACCEPTED,
        )
        session.add_all(recommendations + [other_recommendation])
        session.commit()
        values = {
            "factory": factory,
            "admin_token": create_access_token(admin.id),
            "technician_token": create_access_token(technician.id),
            "viewer_token": create_access_token(viewer.id),
            "other_token": create_access_token(other_admin.id),
            "recommendation_id": str(recommendations[0].id),
            "second_recommendation_id": str(recommendations[1].id),
            "other_recommendation_id": str(other_recommendation.id),
            "organization_id": str(org.id),
            "device_id": str(device.id),
            "second_device_id": str(second_device.id),
        }

    def override_get_db():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield values
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
        engine.dispose()


def _api_client():
    return TestClient(app)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_remediation_sensitive_endpoints_require_authentication(remediation_api):
    client = _api_client()
    plan_id = "00000000-0000-0000-0000-000000000001"
    endpoints = (
        ("get", "/api/v1/remediation/plans"),
        ("get", f"/api/v1/remediation/plans/{plan_id}"),
        ("post", "/api/v1/remediation/plans", {"recommendation_id": remediation_api["recommendation_id"]}),
        ("post", f"/api/v1/remediation/plans/{plan_id}/submit"),
        ("post", f"/api/v1/remediation/plans/{plan_id}/approve"),
        ("post", f"/api/v1/remediation/plans/{plan_id}/reject"),
        ("post", f"/api/v1/remediation/plans/{plan_id}/queue"),
        ("post", f"/api/v1/remediation/plans/{plan_id}/cancel"),
        ("post", f"/api/v1/remediation/plans/{plan_id}/execute"),
        ("post", f"/api/v1/remediation/plans/{plan_id}/verify"),
        ("get", f"/api/v1/remediation/plans/{plan_id}/actions"),
        ("get", f"/api/v1/remediation/plans/{plan_id}/verification-results"),
    )
    for method, path, *body in endpoints:
        if method == "get":
            response = client.get(path)
        else:
            response = client.post(path, json=body[0] if body else None)
        assert response.status_code == 401, (method, path, response.text)


def test_remediation_permissions_are_explicitly_separated(remediation_api):
    client = _api_client()
    viewer = _bearer(remediation_api["viewer_token"])
    technician = _bearer(remediation_api["technician_token"])
    assert client.get("/api/v1/remediation/plans", headers=viewer).status_code == 403
    created = client.post("/api/v1/remediation/plans", headers=technician, json={
        "recommendation_id": remediation_api["recommendation_id"],
    })
    assert created.status_code == 201
    plan_id = created.json()["id"]
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/approve",
                       headers=technician).status_code == 403
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/execute",
                       headers=technician).status_code == 403


def test_remediation_permission_matrix_covers_all_sensitive_routes(remediation_api):
    client = _api_client()
    admin = _bearer(remediation_api["admin_token"])
    technician = _bearer(remediation_api["technician_token"])
    viewer = _bearer(remediation_api["viewer_token"])
    created = client.post(
        "/api/v1/remediation/plans",
        headers=admin,
        json={"recommendation_id": remediation_api["recommendation_id"]},
    )
    assert created.status_code == 201
    plan_id = created.json()["id"]

    for path in (
        f"/api/v1/remediation/plans/{plan_id}/actions",
        f"/api/v1/remediation/plans/{plan_id}/verification-results",
    ):
        assert client.get(path, headers=viewer).status_code == 403
        assert client.get(path, headers=admin).status_code == 200

    assert client.post(f"/api/v1/remediation/plans/{plan_id}/submit",
                       headers=viewer).status_code == 403
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/approve",
                       headers=technician).status_code == 403
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/queue",
                       headers=technician).status_code == 403
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/cancel",
                       headers=technician).status_code == 403
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/execute",
                       headers=technician).status_code == 403
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/verify",
                       headers=technician).status_code == 409


def test_remediation_api_isolates_cross_organization_records(remediation_api):
    client = _api_client()
    other_created = client.post(
        "/api/v1/remediation/plans",
        headers=_bearer(remediation_api["other_token"]),
        json={"recommendation_id": remediation_api["other_recommendation_id"]},
    )
    assert other_created.status_code == 201
    foreign_plan_id = other_created.json()["id"]
    headers = _bearer(remediation_api["admin_token"])
    endpoints = (
        f"/api/v1/remediation/plans/{foreign_plan_id}",
        f"/api/v1/remediation/plans/{foreign_plan_id}/actions",
        f"/api/v1/remediation/plans/{foreign_plan_id}/verification-results",
    )
    for path in endpoints:
        response = client.get(path, headers=headers)
        assert response.status_code == 404
    for action in ("submit", "approve", "reject", "queue", "cancel", "execute", "verify"):
        response = client.post(
            f"/api/v1/remediation/plans/{foreign_plan_id}/{action}",
            headers=headers,
        )
        assert response.status_code == 404


def test_remediation_same_org_plans_keep_real_device_scope(remediation_api):
    client = _api_client()
    headers = _bearer(remediation_api["admin_token"])
    first = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": remediation_api["recommendation_id"],
    }).json()
    second = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": remediation_api["second_recommendation_id"],
    }).json()
    assert first["device_id"] == remediation_api["device_id"]
    assert second["device_id"] == remediation_api["second_device_id"]
    assert {action["parameters"]["source"] for action in first["actions"]} == {"safe-refresh"}
    with remediation_api["factory"]() as session:
        action = session.scalar(select(RemediationAction).where(
            RemediationAction.plan_id == UUID(first["id"])))
        assert str(action.device_id) == remediation_api["device_id"]


def test_generate_rejects_server_owned_and_unsafe_input_fields(remediation_api):
    response = _api_client().post("/api/v1/remediation/plans",
        headers=_bearer(remediation_api["admin_token"]), json={
            "recommendation_id": remediation_api["recommendation_id"],
            "organization_id": remediation_api["organization_id"],
            "status": "approved",
            "actions": [{"action_key": "shell", "parameters": {"command": "id"}}],
        })
    assert response.status_code == 422
    assert "organization_id" in str(response.json())


@pytest.mark.parametrize("field", (
    "organization_id", "device_id", "actor_user_id", "approved_by_user_id",
    "status", "risk_level", "approval", "verification_status",
    "execution_result", "command", "shell", "powershell", "script",
    "executable", "path", "actions", "parameters", "result",
))
def test_generate_rejects_authoritative_and_execution_injection_fields(remediation_api, field):
    response = _api_client().post(
        "/api/v1/remediation/plans",
        headers=_bearer(remediation_api["admin_token"]),
        json={
            "recommendation_id": remediation_api["recommendation_id"],
            field: {"command": "id"} if field in {"actions", "parameters", "result"} else "injected",
        },
    )
    assert response.status_code == 422
    assert field in str(response.json())


def test_execute_requires_submit_approval_and_queue_via_endpoints(remediation_api):
    client = _api_client()
    headers = _bearer(remediation_api["admin_token"])
    plan_id = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": remediation_api["recommendation_id"],
    }).json()["id"]
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/execute", headers=headers).status_code == 409
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/submit", headers=headers).status_code == 200
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/approve", headers=headers).status_code == 200
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/queue", headers=headers).status_code == 200
    executed = client.post(f"/api/v1/remediation/plans/{plan_id}/execute", headers=headers)
    assert executed.status_code == 200
    assert executed.json()["status"] == "verification_required"
    assert all(action["result"]["executed"] is False for action in executed.json()["actions"])


def test_execute_rejects_every_unapproved_lifecycle_state(remediation_api):
    client = _api_client()
    headers = _bearer(remediation_api["admin_token"])
    with remediation_api["factory"]() as session:
        device_id = UUID(remediation_api["device_id"])
        org_id = UUID(remediation_api["organization_id"])
        extra = [
            Recommendation(
                organization_id=org_id, device_id=device_id,
                title=f"Additional refresh {index}", summary="Safe refresh",
                description="Evidence-backed", rule_id="safe-refresh",
                fingerprint=f"additional-{index}", status=RecommendationStatus.ACCEPTED,
            )
            for index in range(2)
        ]
        session.add_all(extra)
        session.commit()
        extra_ids = [str(item.id) for item in extra]

    draft = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": remediation_api["recommendation_id"],
    }).json()["id"]
    assert client.post(f"/api/v1/remediation/plans/{draft}/execute", headers=headers).status_code == 409

    pending = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": extra_ids[0],
    }).json()["id"]
    assert client.post(f"/api/v1/remediation/plans/{pending}/submit", headers=headers).status_code == 200
    assert client.post(f"/api/v1/remediation/plans/{pending}/execute", headers=headers).status_code == 409

    rejected = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": remediation_api["second_recommendation_id"],
    }).json()["id"]
    assert client.post(f"/api/v1/remediation/plans/{rejected}/submit", headers=headers).status_code == 200
    assert client.post(f"/api/v1/remediation/plans/{rejected}/reject", headers=headers).status_code == 200
    assert client.post(f"/api/v1/remediation/plans/{rejected}/execute", headers=headers).status_code == 409

    cancelled = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": extra_ids[1],
    }).json()["id"]
    assert client.post(f"/api/v1/remediation/plans/{cancelled}/cancel", headers=headers).status_code == 200
    assert client.post(f"/api/v1/remediation/plans/{cancelled}/execute", headers=headers).status_code == 409


def test_http_lifecycle_creates_audits_and_safe_dry_run_result(remediation_api):
    client = _api_client()
    headers = _bearer(remediation_api["admin_token"])
    with remediation_api["factory"]() as session:
        device_id = UUID(remediation_api["device_id"])
        org_id = UUID(remediation_api["organization_id"])
        extra = Recommendation(
            organization_id=org_id, device_id=device_id,
            title="Audit cancellation refresh", summary="Safe refresh",
            description="Evidence-backed", rule_id="safe-refresh",
            fingerprint="audit-cancellation", status=RecommendationStatus.ACCEPTED,
        )
        session.add(extra)
        session.commit()
        extra_id = str(extra.id)
    plan = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": remediation_api["recommendation_id"],
    }).json()
    plan_id = plan["id"]
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/submit", headers=headers).status_code == 200
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/approve", headers=headers).status_code == 200
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/queue", headers=headers).status_code == 200
    executed = client.post(f"/api/v1/remediation/plans/{plan_id}/execute", headers=headers)
    assert executed.status_code == 200
    assert all(action["result"]["executed"] is False for action in executed.json()["actions"])
    assert client.post(f"/api/v1/remediation/plans/{plan_id}/verify", headers=headers).status_code == 200

    rejected = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": remediation_api["second_recommendation_id"],
    }).json()["id"]
    assert client.post(f"/api/v1/remediation/plans/{rejected}/submit", headers=headers).status_code == 200
    assert client.post(f"/api/v1/remediation/plans/{rejected}/reject", headers=headers).status_code == 200

    cancelled = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": extra_id,
    }).json()["id"]
    assert client.post(f"/api/v1/remediation/plans/{cancelled}/cancel", headers=headers).status_code == 200

    with remediation_api["factory"]() as session:
        events = session.scalars(select(AuditEvent).where(
            AuditEvent.resource_type == "remediation_plan"
        )).all()
        actions = {event.action for event in events}
        assert {
            "plan_created", "plan_pending_approval", "plan_approved",
            "plan_queued", "plan_executed_dry_run", "plan_verified",
            "plan_rejected", "plan_cancelled",
        } <= actions
        for event in events:
            assert event.event_metadata == {"dry_run": True}
            assert "command" not in str(event.event_metadata).lower()
            assert "sql" not in str(event.event_metadata).lower()


def test_invalid_action_parameters_fail_safely_and_are_audited(remediation_api):
    client = _api_client()
    headers = _bearer(remediation_api["admin_token"])
    plan = client.post("/api/v1/remediation/plans", headers=headers, json={
        "recommendation_id": remediation_api["recommendation_id"],
    }).json()
    with remediation_api["factory"]() as session:
        action = session.scalar(select(RemediationAction).where(
            RemediationAction.plan_id == UUID(plan["id"])))
        action.parameters = {"source": "api", "reason": "test", "command": "id"}
        session.commit()
    for endpoint in ("submit", "approve", "queue"):
        assert client.post(f"/api/v1/remediation/plans/{plan['id']}/{endpoint}",
                           headers=headers).status_code == 200
    response = client.post(f"/api/v1/remediation/plans/{plan['id']}/execute", headers=headers)
    assert response.status_code == 422
    assert response.json()["error"]["message"] == "Remediation dry-run failed"
    assert "command" not in str(response.json()).lower()
    with remediation_api["factory"]() as session:
        event = session.scalar(select(AuditEvent).where(
            AuditEvent.resource_id == plan["id"], AuditEvent.action == "plan_execution_failed"))
        assert event is not None
        assert event.result == "failure"
