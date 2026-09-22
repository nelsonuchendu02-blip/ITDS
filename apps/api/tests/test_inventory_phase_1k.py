from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import AssetType, AuditEvent, Base, Device, Organization, Role, Site, User
from app.security.tokens import create_access_token

# (kind, path) pairs covering every Phase 1K inventory route family.
RESOURCE_ROUTES = (
    ("asset", "/api/v1/assets"),
    ("site", "/api/v1/sites"),
    ("network", "/api/v1/networks"),
    ("subnet", "/api/v1/subnets"),
    ("vlan", "/api/v1/vlans"),
    ("ssid", "/api/v1/ssids"),
)

MINIMAL_PAYLOAD = {
    "asset": {"hostname": "route-asset", "device_type": "server", "operating_system": "Linux"},
    "site": {"name": "route-site"},
    "network": {"name": "route-network"},
    "subnet": {"cidr": "10.10.0.0/24"},
    "vlan": {"vlan_id": 10, "name": "route-vlan"},
    "ssid": {"ssid": "route-ssid"},
}


@dataclass
class InventoryContext:
    session_factory: sessionmaker
    admin_token: str
    viewer_token: str
    technician_token: str
    other_admin_token: str
    organization_id: str
    other_organization_id: str
    other_site_id: str


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def inventory_context(monkeypatch: pytest.MonkeyPatch) -> Iterator[InventoryContext]:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setenv("JWT_SECRET", "inventory-phase-1k-" + "x" * 32)
    monkeypatch.setenv("JWT_ISSUER", "itds-test")
    monkeypatch.setenv("JWT_AUDIENCE", "itds-test-client")
    get_settings.cache_clear()

    with factory() as session:
        org = Organization(name="Inventory org")
        other_org = Organization(name="Other inventory org")
        admin = User(organization=org, email="inventory-admin@test", display_name="Admin")
        admin.roles.append(Role(organization=org, name="organization_admin"))
        viewer = User(organization=org, email="inventory-viewer@test", display_name="Viewer")
        viewer.roles.append(Role(organization=org, name="viewer"))
        technician = User(organization=org, email="inventory-tech@test", display_name="Tech")
        technician.roles.append(Role(organization=org, name="technician"))
        other_admin = User(organization=other_org, email="other-admin@test", display_name="Other")
        other_admin.roles.append(Role(organization=other_org, name="organization_admin"))
        other_site = Site(organization=other_org, name="Other site")
        session.add_all([org, other_org, admin, viewer, technician, other_admin, other_site])
        session.commit()
        context = InventoryContext(
            factory,
            create_access_token(admin.id),
            create_access_token(viewer.id),
            create_access_token(technician.id),
            create_access_token(other_admin.id),
            str(org.id),
            str(other_org.id),
            str(other_site.id),
        )

    def override_get_db() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield context
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


def test_asset_type_validation_and_forbidden_extra(inventory_context: InventoryContext) -> None:
    client = TestClient(app)
    valid = client.post(
        "/api/v1/assets",
        headers=_auth(inventory_context.admin_token),
        json={
            "hostname": "asset-1",
            "device_type": "server",
            "operating_system": "Linux",
            "asset_type": "server",
            "operating_system_version": "22.04",
            "ipv6_address": "::1",
            "management_ip": "10.0.0.5",
            "bios_version": "F.42",
            "cpu": "2x Xeon",
            "memory": "64GB",
            "storage": "2TB NVMe",
            "criticality": "high",
            "discovery_source": "manual",
        },
    )
    assert valid.status_code == 201
    body = valid.json()
    assert body["asset_type"] == AssetType.SERVER.value
    assert body["criticality"] == "high"
    assert body["operating_system_version"] == "22.04"
    assert body["management_ip"] == "10.0.0.5"

    invalid = client.post(
        "/api/v1/assets",
        headers=_auth(inventory_context.admin_token),
        json={
            "hostname": "asset-invalid",
            "device_type": "server",
            "operating_system": "Linux",
            "asset_type": "not-a-type",
        },
    )
    extra = client.post(
        "/api/v1/assets",
        headers=_auth(inventory_context.admin_token),
        json={
            "hostname": "asset-extra",
            "device_type": "server",
            "operating_system": "Linux",
            "unexpected": True,
        },
    )
    assert invalid.status_code == extra.status_code == 422


@pytest.mark.parametrize("value", ["laptop", "desktop", "mobile_phone", "tablet", "server",
                                   "access_point", "switch", "firewall", "router", "printer",
                                   "network_device", "iot", "other"])
def test_asset_type_accepts_every_required_category(
    inventory_context: InventoryContext, value: str
) -> None:
    client = TestClient(app)
    response = client.post(
        "/api/v1/assets",
        headers=_auth(inventory_context.admin_token),
        json={
            "hostname": f"asset-{value}",
            "device_type": "generic",
            "operating_system": "Linux",
            "asset_type": value,
        },
    )
    assert response.status_code == 201
    assert response.json()["asset_type"] == value


@pytest.mark.parametrize("value", ["unknown", "workstation", "mobile", "virtual_machine"])
def test_asset_type_rejects_removed_legacy_categories(
    inventory_context: InventoryContext, value: str
) -> None:
    response = TestClient(app).post(
        "/api/v1/assets",
        headers=_auth(inventory_context.admin_token),
        json={
            "hostname": f"asset-legacy-{value}",
            "device_type": "generic",
            "operating_system": "Linux",
            "asset_type": value,
        },
    )
    assert response.status_code == 422


@pytest.mark.parametrize("kind,path", RESOURCE_ROUTES)
def test_route_requires_authentication(
    inventory_context: InventoryContext, kind: str, path: str
) -> None:
    client = TestClient(app)
    assert client.get(path).status_code == 401
    assert client.post(path, json=MINIMAL_PAYLOAD[kind]).status_code == 401


@pytest.mark.parametrize("kind,path", RESOURCE_ROUTES)
def test_route_permissions_by_role(
    inventory_context: InventoryContext, kind: str, path: str
) -> None:
    client = TestClient(app)

    viewer_read = client.get(path, headers=_auth(inventory_context.viewer_token))
    viewer_create = client.post(
        path, headers=_auth(inventory_context.viewer_token), json=MINIMAL_PAYLOAD[kind]
    )
    assert viewer_read.status_code == 200
    assert viewer_create.status_code == 403

    tech_create = client.post(
        path, headers=_auth(inventory_context.technician_token), json=MINIMAL_PAYLOAD[kind]
    )
    assert tech_create.status_code == 201
    resource_id = tech_create.json()["id"]

    tech_manage = client.patch(
        f"{path}/{resource_id}", headers=_auth(inventory_context.technician_token), json={}
    )
    assert tech_manage.status_code == 403

    admin_manage = client.patch(
        f"{path}/{resource_id}", headers=_auth(inventory_context.admin_token), json={}
    )
    assert admin_manage.status_code == 200

    admin_delete = client.delete(
        f"{path}/{resource_id}", headers=_auth(inventory_context.admin_token)
    )
    assert admin_delete.status_code == 204


@pytest.mark.parametrize("kind,path", RESOURCE_ROUTES)
def test_route_get_and_delete_isolate_by_organization(
    inventory_context: InventoryContext, kind: str, path: str
) -> None:
    client = TestClient(app)
    created = client.post(
        path, headers=_auth(inventory_context.admin_token), json=MINIMAL_PAYLOAD[kind]
    )
    assert created.status_code == 201
    resource_id = created.json()["id"]

    cross_org_get = client.get(
        f"{path}/{resource_id}", headers=_auth(inventory_context.other_admin_token)
    )
    assert cross_org_get.status_code == 404

    cross_org_update = client.patch(
        f"{path}/{resource_id}", headers=_auth(inventory_context.other_admin_token), json={}
    )
    assert cross_org_update.status_code == 404

    cross_org_delete = client.delete(
        f"{path}/{resource_id}", headers=_auth(inventory_context.other_admin_token)
    )
    assert cross_org_delete.status_code == 404

    same_org_list = client.get(path, headers=_auth(inventory_context.admin_token))
    assert any(item["id"] == resource_id for item in same_org_list.json())
    other_org_list = client.get(path, headers=_auth(inventory_context.other_admin_token))
    assert all(item["id"] != resource_id for item in other_org_list.json())


def test_inventory_authentication_permissions_and_isolation(
    inventory_context: InventoryContext,
) -> None:
    client = TestClient(app)
    assert client.get("/api/v1/sites").status_code == 401
    viewer_read = client.get("/api/v1/sites", headers=_auth(inventory_context.viewer_token))
    viewer_create = client.post(
        "/api/v1/sites",
        headers=_auth(inventory_context.viewer_token),
        json={"name": "viewer-site"},
    )
    assert viewer_read.status_code == 200
    assert viewer_create.status_code == 403

    cross_org = client.get(
        f"/api/v1/sites/{inventory_context.other_site_id}",
        headers=_auth(inventory_context.admin_token),
    )
    assert cross_org.status_code == 404


def test_asset_site_network_crud_and_audit(inventory_context: InventoryContext) -> None:
    client = TestClient(app)
    headers = _auth(inventory_context.admin_token)
    site = client.post("/api/v1/sites", headers=headers, json={"name": "HQ"})
    assert site.status_code == 201
    site_id = site.json()["id"]
    assert client.patch(
        f"/api/v1/sites/{site_id}", headers=headers, json={"description": "Updated"}
    ).status_code == 200

    network = client.post(
        "/api/v1/networks", headers=headers, json={"name": "Production", "site_id": site_id}
    )
    assert network.status_code == 201
    network_id = network.json()["id"]
    assert client.patch(
        f"/api/v1/networks/{network_id}", headers=headers, json={"description": "Core"}
    ).status_code == 200

    subnet = client.post(
        "/api/v1/subnets", headers=headers, json={"network_id": network_id, "cidr": "10.1.0.0/24"}
    )
    assert subnet.status_code == 201
    vlan = client.post(
        "/api/v1/vlans", headers=headers, json={"network_id": network_id, "vlan_id": 42, "name": "core"}
    )
    assert vlan.status_code == 201
    ssid = client.post(
        "/api/v1/ssids", headers=headers, json={"network_id": network_id, "ssid": "corp-wifi"}
    )
    assert ssid.status_code == 201

    asset = client.post(
        "/api/v1/assets",
        headers=headers,
        json={
            "hostname": "crud-asset",
            "device_type": "server",
            "operating_system": "Linux",
            "location": "Rack 4, Row B",
            "site_id": site_id,
            "network_id": network_id,
            "subnet_id": subnet.json()["id"],
            "vlan_id": vlan.json()["id"],
            "wlan_id": ssid.json()["id"],
        },
    )
    assert asset.status_code == 201
    assert asset.json()["network_id"] == network_id
    assert asset.json()["location"] == "Rack 4, Row B"
    asset_id = asset.json()["id"]
    assert client.get(f"/api/v1/assets/{asset_id}", headers=headers).status_code == 200
    assert client.patch(
        f"/api/v1/assets/{asset_id}", headers=headers, json={"hostname": "renamed-asset"}
    ).status_code == 200

    with inventory_context.session_factory() as session:
        events = session.scalars(select(AuditEvent)).all()
        assert {event.event_type for event in events} >= {
            "site_created", "site_updated",
            "network_created", "network_updated",
            "subnet_created", "vlan_created", "ssid_created",
            "asset_created", "asset_updated",
        }


def test_composite_parent_integrity_rejects_cross_org_site(
    inventory_context: InventoryContext,
) -> None:
    response = TestClient(app).post(
        "/api/v1/networks",
        headers=_auth(inventory_context.admin_token),
        json={"name": "invalid-parent", "site_id": inventory_context.other_site_id},
    )
    assert response.status_code == 404


def test_composite_parent_integrity_rejects_cross_org_network_children(
    inventory_context: InventoryContext,
) -> None:
    client = TestClient(app)
    headers = _auth(inventory_context.admin_token)
    other_headers = _auth(inventory_context.other_admin_token)
    other_network = client.post(
        "/api/v1/networks", headers=other_headers, json={"name": "other-network"}
    )
    assert other_network.status_code == 201
    other_network_id = other_network.json()["id"]

    for path, payload in (
        ("/api/v1/subnets", {"network_id": other_network_id, "cidr": "10.2.0.0/24"}),
        ("/api/v1/vlans", {"network_id": other_network_id, "vlan_id": 99, "name": "bad"}),
        ("/api/v1/ssids", {"network_id": other_network_id, "ssid": "bad-ssid"}),
    ):
        response = client.post(path, headers=headers, json=payload)
        assert response.status_code == 404


def test_asset_rejects_cross_org_network(
    inventory_context: InventoryContext,
) -> None:
    client = TestClient(app)
    other_network = client.post(
        "/api/v1/networks",
        headers=_auth(inventory_context.other_admin_token),
        json={"name": "other-org-network"},
    )
    assert other_network.status_code == 201

    response = client.post(
        "/api/v1/assets",
        headers=_auth(inventory_context.admin_token),
        json={
            "hostname": "cross-org-network-asset",
            "device_type": "server",
            "operating_system": "Linux",
            "network_id": other_network.json()["id"],
        },
    )
    assert response.status_code == 404


def test_asset_rejects_cross_org_assigned_user_and_related_resources(
    inventory_context: InventoryContext,
) -> None:
    client = TestClient(app)
    headers = _auth(inventory_context.admin_token)
    other_headers = _auth(inventory_context.other_admin_token)

    other_network = client.post("/api/v1/networks", headers=other_headers, json={"name": "n2"})
    other_subnet = client.post(
        "/api/v1/subnets",
        headers=other_headers,
        json={"network_id": other_network.json()["id"], "cidr": "10.3.0.0/24"},
    )
    assert other_subnet.status_code == 201

    response = client.post(
        "/api/v1/assets",
        headers=headers,
        json={
            "hostname": "cross-org-asset",
            "device_type": "server",
            "operating_system": "Linux",
            "subnet_id": other_subnet.json()["id"],
        },
    )
    assert response.status_code == 404


def test_inventory_migration_head_and_downgrade_upgrade_lifecycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'inventory-phase-1k.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        tables = set(inspect(engine).get_table_names())
        assert {"sites", "networks", "subnets", "vlans", "wlans"} <= tables
        device_columns = {column["name"] for column in inspect(engine).get_columns("devices")}
        assert {
            "asset_type", "criticality", "operating_system_version", "ipv6_address",
            "management_ip", "bios_version", "cpu", "memory", "storage",
            "discovery_source", "assigned_user_id", "network_id", "location",
        } <= device_columns
        device_fks = {fk["name"] for fk in inspect(engine).get_foreign_keys("devices")}
        assert "fk_devices_network_org" in device_fks
        command.downgrade(config, "f6a1b2c3d4e5")
        assert "sites" not in inspect(engine).get_table_names()
        remaining_device_columns = {
            column["name"] for column in inspect(engine).get_columns("devices")
        }
        assert "asset_type" not in remaining_device_columns
        assert "network_id" not in remaining_device_columns
        assert "location" not in remaining_device_columns
        command.upgrade(config, "head")
        assert "sites" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
        get_settings.cache_clear()
