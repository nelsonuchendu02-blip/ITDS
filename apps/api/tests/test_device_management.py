from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import AuditEvent, Base, Device, DeviceStatus, Organization, Role, User
from app.security.passwords import hash_password
from app.security.tokens import create_access_token
from app.schemas import DeviceManagementCreate, DeviceManagementUpdate


@dataclass
class DeviceTestContext:
    session_factory: sessionmaker
    admin_token: str
    viewer_token: str
    technician_token: str
    other_admin_token: str
    device_id: str
    other_device_id: str
    organization_id: str
    other_organization_id: str
    admin_id: str


def _authorization(token: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + token}


@pytest.fixture
def device_context(monkeypatch: pytest.MonkeyPatch) -> Iterator[DeviceTestContext]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
            organization=organization,
            email="admin@managed.test",
            display_name="Admin",
            password_hash=hash_password("secret-password"),
        )
        admin.roles.append(Role(name="organization_admin", organization=organization))
        viewer = User(
            organization=organization,
            email="viewer@managed.test",
            display_name="Viewer",
            password_hash=hash_password("secret-password"),
        )
        viewer.roles.append(Role(name="viewer", organization=organization))
        technician = User(
            organization=organization,
            email="technician@managed.test",
            display_name="Technician",
            password_hash=hash_password("secret-password"),
        )
        technician.roles.append(Role(name="technician", organization=organization))
        other_admin = User(
            organization=other_organization,
            email="admin@other.test",
            display_name="Other Admin",
            password_hash=hash_password("secret-password"),
        )
        other_admin.roles.append(Role(name="organization_admin", organization=other_organization))
        device = Device(
            organization=organization,
            hostname="managed-host",
            device_type="workstation",
            operating_system="Windows",
            ip_address="192.0.2.5",
        )
        other_device = Device(
            organization=other_organization,
            hostname="other-host",
            device_type="server",
            operating_system="Linux",
            ip_address="192.0.2.20",
        )
        session.add_all([
            organization,
            other_organization,
            admin,
            viewer,
            technician,
            other_admin,
            device,
            other_device,
        ])
        session.commit()
        context = DeviceTestContext(
            session_factory=session_factory,
            admin_token=create_access_token(admin.id),
            viewer_token=create_access_token(viewer.id),
            technician_token=create_access_token(technician.id),
            other_admin_token=create_access_token(other_admin.id),
            device_id=str(device.id),
            other_device_id=str(other_device.id),
            organization_id=str(organization.id),
            other_organization_id=str(other_organization.id),
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


def _client() -> TestClient:
    return TestClient(app)


def test_create_assigns_authenticated_organization_and_records_audit(
    device_context: DeviceTestContext,
) -> None:
    response = _client().post(
        "/api/v1/devices",
        headers=_authorization(device_context.admin_token),
        json={
            "organization_id": device_context.other_organization_id,
            "hostname": "created-host",
            "device_type": "server",
            "operating_system": "Linux",
            "ip_address": "198.51.100.10",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["organization_id"] == device_context.organization_id
    assert payload["hostname"] == "created-host"

    with device_context.session_factory() as session:
        device = session.get(Device, payload["id"])
        assert device is not None
        assert str(device.organization_id) == device_context.organization_id
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "device_created",
                AuditEvent.resource_id == payload["id"],
            )
        )
        assert event is not None
        _assert_device_audit(event, device_context, payload["id"], "create")


def test_create_rejects_invalid_ip_and_does_not_store_credentials(
    device_context: DeviceTestContext,
) -> None:
    response = _client().post(
        "/api/v1/devices",
        headers=_authorization(device_context.admin_token),
        json={
            "hostname": "invalid-ip",
            "device_type": "server",
            "operating_system": "Linux",
            "ip_address": "not-an-ip",
            "password": "must-not-be-stored",
            "token": "must-not-be-stored",
        },
    )

    assert response.status_code == 422
    with device_context.session_factory() as session:
        assert session.scalar(select(Device).where(Device.hostname == "invalid-ip")) is None
        assert session.scalar(
            select(AuditEvent).where(AuditEvent.resource_type == "device")
        ) is None


def test_read_allows_in_scope_viewer_and_hides_cross_organization_devices(
    device_context: DeviceTestContext,
) -> None:
    client = _client()
    in_scope = client.get(
        f"/api/v1/devices/{device_context.device_id}",
        headers=_authorization(device_context.viewer_token),
    )
    cross_scope = client.get(
        f"/api/v1/devices/{device_context.other_device_id}",
        headers=_authorization(device_context.viewer_token),
    )
    missing = client.get(
        "/api/v1/devices/00000000-0000-0000-0000-000000000000",
        headers=_authorization(device_context.viewer_token),
    )

    assert in_scope.status_code == 200
    assert in_scope.json()["id"] == device_context.device_id
    assert cross_scope.status_code == missing.status_code == 404
    assert cross_scope.json() == missing.json()


def test_list_is_isolated_paginated_and_filterable(device_context: DeviceTestContext) -> None:
    with device_context.session_factory() as session:
        organization_id = device_context.organization_id
        organization = session.get(Organization, organization_id)
        assert organization is not None
        session.add_all(
            [
                Device(
                    organization=organization,
                    hostname="linux-server",
                    device_type="server",
                    operating_system="Linux",
                ),
                Device(
                    organization=organization,
                    hostname="windows-laptop",
                    device_type="laptop",
                    operating_system="Windows",
                    status=DeviceStatus.INACTIVE,
                ),
                Device(
                    organization=organization,
                    hostname="mac-laptop",
                    device_type="laptop",
                    operating_system="macOS",
                ),
            ]
        )
        session.commit()

    client = _client()
    headers = _authorization(device_context.viewer_token)
    all_devices = client.get("/api/v1/devices?page=1&page_size=2", headers=headers)
    page_two = client.get("/api/v1/devices?page=2&page_size=2", headers=headers)
    too_large = client.get("/api/v1/devices?page_size=101", headers=headers)
    search = client.get("/api/v1/devices?search=linux", headers=headers)
    status = client.get("/api/v1/devices?status=inactive", headers=headers)
    device_type = client.get("/api/v1/devices?device_type=laptop", headers=headers)
    operating_system = client.get("/api/v1/devices?operating_system=macOS", headers=headers)

    assert all_devices.status_code == page_two.status_code == 200
    assert all_devices.json()["meta"] == {"page": 1, "page_size": 2, "total": 4}
    assert len(all_devices.json()["items"]) == 2
    assert page_two.json()["meta"]["page"] == 2
    assert len(page_two.json()["items"]) == 2
    assert too_large.status_code == 422
    assert [item["hostname"] for item in search.json()["items"]] == ["linux-server"]
    assert [item["hostname"] for item in status.json()["items"]] == ["windows-laptop"]
    assert {item["hostname"] for item in device_type.json()["items"]} == {
        "mac-laptop",
        "windows-laptop",
    }
    assert [item["hostname"] for item in operating_system.json()["items"]] == ["mac-laptop"]
    assert all(
        item["organization_id"] == device_context.organization_id
        for item in all_devices.json()["items"] + page_two.json()["items"]
    )


def test_update_is_authorized_scoped_and_protects_server_fields(
    device_context: DeviceTestContext,
) -> None:
    client = _client()
    update_payload = {
        "hostname": "updated-host",
        "device_type": "laptop",
        "operating_system": "Windows 11",
        "ip_address": "198.51.100.11",
        "organization_id": device_context.other_organization_id,
        "id": "00000000-0000-0000-0000-000000000000",
        "status": "retired",
        "last_seen_at": "2030-01-01T00:00:00Z",
    }
    updated = client.patch(
        f"/api/v1/devices/{device_context.device_id}",
        headers=_authorization(device_context.admin_token),
        json=update_payload,
    )
    unauthorized = client.patch(
        f"/api/v1/devices/{device_context.device_id}",
        headers=_authorization(device_context.viewer_token),
        json={"hostname": "not-allowed"},
    )
    cross_scope = client.patch(
        f"/api/v1/devices/{device_context.other_device_id}",
        headers=_authorization(device_context.admin_token),
        json={"hostname": "must-not-change"},
    )

    assert updated.status_code == 200
    assert updated.json()["id"] == device_context.device_id
    assert updated.json()["organization_id"] == device_context.organization_id
    assert updated.json()["status"] == "active"
    assert updated.json()["last_seen_at"] is None
    assert unauthorized.status_code == 403
    assert cross_scope.status_code == 404

    with device_context.session_factory() as session:
        device = session.get(Device, device_context.device_id)
        assert device is not None
        assert str(device.organization_id) == device_context.organization_id
        assert device.status is DeviceStatus.ACTIVE
        assert device.last_seen_at is None
        event = session.scalar(
            select(AuditEvent).where(
                AuditEvent.event_type == "device_updated",
                AuditEvent.resource_id == device_context.device_id,
            )
        )
        assert event is not None
        _assert_device_audit(event, device_context, device_context.device_id, "update")


def test_activation_and_deactivation_are_managed_scoped_and_audited(
    device_context: DeviceTestContext,
) -> None:
    client = _client()
    headers = _authorization(device_context.admin_token)
    activated = client.post(
        f"/api/v1/devices/{device_context.device_id}/activate",
        headers=headers,
    )
    deactivated = client.post(
        f"/api/v1/devices/{device_context.device_id}/deactivate",
        headers=headers,
    )
    viewer_attempt = client.post(
        f"/api/v1/devices/{device_context.device_id}/activate",
        headers=_authorization(device_context.viewer_token),
    )
    cross_scope = client.post(
        f"/api/v1/devices/{device_context.other_device_id}/activate",
        headers=headers,
    )

    assert activated.status_code == deactivated.status_code == 200
    assert activated.json()["status"] == "active"
    assert deactivated.json()["status"] == "inactive"
    assert viewer_attempt.status_code == 403
    assert cross_scope.status_code == 404

    with device_context.session_factory() as session:
        events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.resource_type == "device",
                AuditEvent.resource_id == device_context.device_id,
            )
        ).all()
        event_types = {event.event_type for event in events}
        assert {"device_activated", "device_deactivated"} <= event_types
        for event in events:
            _assert_device_audit(
                event,
                device_context,
                device_context.device_id,
                "status_change" if event.event_type.startswith("device_") else event.action,
            )
            serialized = repr(event.event_metadata)
            assert "secret-password" not in serialized
            assert "Bearer" not in serialized
            assert "token" not in serialized.lower()
            assert "password" not in serialized.lower()


def test_role_permissions_match_phase_1e_policy(device_context: DeviceTestContext) -> None:
    client = _client()
    technician_headers = _authorization(device_context.technician_token)
    viewer_headers = _authorization(device_context.viewer_token)

    technician_read = client.get("/api/v1/devices", headers=technician_headers)
    technician_update = client.patch(
        f"/api/v1/devices/{device_context.device_id}",
        headers=technician_headers,
        json={"hostname": "technician-update"},
    )
    technician_create = client.post(
        "/api/v1/devices",
        headers=technician_headers,
        json={
            "hostname": "technician-create",
            "device_type": "server",
            "operating_system": "Linux",
        },
    )
    viewer_read = client.get("/api/v1/devices", headers=viewer_headers)
    viewer_manage = client.post(
        f"/api/v1/devices/{device_context.device_id}/deactivate",
        headers=viewer_headers,
    )

    assert technician_read.status_code == technician_update.status_code == 200
    assert technician_create.status_code == 403
    assert viewer_read.status_code == 200
    assert viewer_manage.status_code == 403


def test_management_schemas_exclude_server_controlled_fields() -> None:
    assert set(DeviceManagementCreate.model_fields) == {
        "hostname",
        "device_type",
        "operating_system",
        "ip_address",
    }
    assert set(DeviceManagementUpdate.model_fields) == {
        "hostname",
        "device_type",
        "operating_system",
        "ip_address",
    }


def _assert_device_audit(
    event: AuditEvent,
    context: DeviceTestContext,
    device_id: str,
    action: str,
) -> None:
    assert str(event.organization_id) == context.organization_id
    assert str(event.actor_user_id) == context.admin_id
    assert event.resource_id == device_id
    assert event.action == action
    assert event.result == "success"
    assert event.resource_type == "device"
    assert event.event_metadata["target_device_id"] == device_id
