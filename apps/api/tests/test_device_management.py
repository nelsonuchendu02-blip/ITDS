from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import Base, Device, Organization, Role, User
from app.security.passwords import hash_password
from app.security.tokens import create_access_token


def test_device_management_enforces_permissions_and_organization_scope(monkeypatch) -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setenv("JWT_SECRET", "test-secret-" + "x" * 32)
    monkeypatch.setenv("JWT_ISSUER", "itds-test")
    monkeypatch.setenv("JWT_AUDIENCE", "itds-test-client")
    get_settings.cache_clear()

    with Session() as session:
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
        other_device = Device(
            organization=other_organization,
            hostname="other-host",
            device_type="server",
            operating_system="Linux",
        )
        session.add_all([organization, other_organization, admin, viewer, other_device])
        session.commit()
        admin_token = create_access_token(admin.id)
        viewer_token = create_access_token(viewer.id)
        other_device_id = str(other_device.id)

    def override_get_db():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        created_response = client.post(
            "/api/v1/devices",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "hostname": "managed-host",
                "device_type": "workstation",
                "operating_system": "Windows",
                "ip_address": "192.0.2.5",
            },
        )
        assert created_response.status_code == 201
        created_id = created_response.json()["id"]
        assert "organization_id" in created_response.json()

        assert client.get(
            f"/api/v1/devices/{other_device_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).status_code == 404
        assert client.post(
            "/api/v1/devices",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={
                "hostname": "not-allowed",
                "device_type": "server",
                "operating_system": "Linux",
            },
        ).status_code == 403
        updated = client.patch(
            f"/api/v1/devices/{created_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"hostname": "renamed-host"},
        )
        assert updated.status_code == 200
        assert updated.json()["hostname"] == "renamed-host"
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
