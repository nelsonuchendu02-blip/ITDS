"""add Phase 1K inventory persistence models.

Revision ID: a7b8c9d0e1f2
Revises: f6a1b2c3d4e5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f6a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class MigrationUUID(sa.TypeDecorator):
    impl = sa.String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(
            PostgreSQLUUID(as_uuid=True) if dialect.name == "postgresql" else sa.String(36)
        )


ASSET_TYPE_VALUES = (
    "LAPTOP", "DESKTOP", "MOBILE_PHONE", "TABLET", "SERVER", "ACCESS_POINT",
    "SWITCH", "FIREWALL", "ROUTER", "PRINTER", "NETWORK_DEVICE", "IOT", "OTHER",
)
DEVICE_CRITICALITY_VALUES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def _table(name):
    cols = [
        sa.Column("id", MigrationUUID(), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]
    if name == "sites":
        cols += [sa.Column("name", sa.String(200), nullable=False),
                 sa.Column("description", sa.Text()), sa.Column("address", sa.String(500))]
        constraints = [sa.UniqueConstraint("id", "organization_id", name="uq_sites_id_organization"),
                       sa.UniqueConstraint("organization_id", "name", name="uq_sites_org_name")]
    elif name == "networks":
        cols += [sa.Column("site_id", MigrationUUID()), sa.Column("name", sa.String(200), nullable=False),
                 sa.Column("description", sa.Text())]
        constraints = [sa.UniqueConstraint("id", "organization_id", name="uq_networks_id_organization"),
                       sa.UniqueConstraint("organization_id", "name", name="uq_networks_org_name"),
                       sa.ForeignKeyConstraint(["site_id", "organization_id"],
                                               ["sites.id", "sites.organization_id"],
                                               name="fk_networks_site_org")]
    elif name == "subnets":
        cols += [sa.Column("network_id", MigrationUUID()), sa.Column("cidr", sa.String(64), nullable=False),
                 sa.Column("gateway", sa.String(45))]
        constraints = [sa.UniqueConstraint("id", "organization_id", name="uq_subnets_id_organization"),
                       sa.UniqueConstraint("organization_id", "cidr", name="uq_subnets_org_cidr"),
                       sa.ForeignKeyConstraint(["network_id", "organization_id"],
                                               ["networks.id", "networks.organization_id"],
                                               name="fk_subnets_network_org")]
    elif name == "vlans":
        cols += [sa.Column("network_id", MigrationUUID()), sa.Column("vlan_id", sa.Integer(), nullable=False),
                 sa.Column("name", sa.String(200), nullable=False)]
        constraints = [sa.UniqueConstraint("id", "organization_id", name="uq_vlans_id_organization"),
                       sa.UniqueConstraint("organization_id", "vlan_id", name="uq_vlans_org_vlan_id"),
                       sa.ForeignKeyConstraint(["network_id", "organization_id"],
                                               ["networks.id", "networks.organization_id"],
                                               name="fk_vlans_network_org")]
    else:
        cols += [sa.Column("network_id", MigrationUUID()), sa.Column("ssid", sa.String(32), nullable=False),
                 sa.Column("security", sa.String(100))]
        constraints = [sa.UniqueConstraint("id", "organization_id", name="uq_wlans_id_organization"),
                       sa.UniqueConstraint("organization_id", "ssid", name="uq_wlans_org_ssid"),
                       sa.ForeignKeyConstraint(["network_id", "organization_id"],
                                               ["networks.id", "networks.organization_id"],
                                               name="fk_wlans_network_org")]
    constraints.append(sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"))
    op.create_table(name, *cols, *constraints, sa.PrimaryKeyConstraint("id"))
    op.create_index("ix_%s_organization_id" % name, name, ["organization_id"])


def upgrade() -> None:
    _table("sites")
    _table("networks")
    _table("subnets")
    _table("vlans")
    _table("wlans")
    asset_enum = sa.Enum(*ASSET_TYPE_VALUES, name="asset_type")
    criticality_enum = sa.Enum(*DEVICE_CRITICALITY_VALUES, name="device_criticality")
    columns = [
        sa.Column("asset_type", asset_enum, nullable=True),
        sa.Column("operating_system_version", sa.String(100)),
        sa.Column("ipv6_address", sa.String(45)),
        sa.Column("management_ip", sa.String(45)),
        sa.Column("asset_tag", sa.String(100)),
        sa.Column("serial_number", sa.String(255)),
        sa.Column("manufacturer", sa.String(200)),
        sa.Column("model", sa.String(200)),
        sa.Column("firmware_version", sa.String(100)),
        sa.Column("bios_version", sa.String(100)),
        sa.Column("mac_address", sa.String(17)),
        sa.Column("cpu", sa.String(200)),
        sa.Column("memory", sa.String(100)),
        sa.Column("storage", sa.String(200)),
        sa.Column("criticality", criticality_enum, nullable=True),
        sa.Column("discovery_source", sa.String(100)),
        sa.Column("location", sa.String(500)),
        sa.Column("purchase_date", sa.DateTime(timezone=True)),
        sa.Column("warranty_expiration", sa.DateTime(timezone=True)),
        sa.Column("site_id", MigrationUUID()),
        sa.Column("network_id", MigrationUUID()),
        sa.Column("subnet_id", MigrationUUID()),
        sa.Column("vlan_id", MigrationUUID()),
        sa.Column("wlan_id", MigrationUUID()),
        sa.Column("assigned_user_id", MigrationUUID()),
    ]
    fks = [
        ("fk_devices_site_org", "sites", "site_id"),
        ("fk_devices_network_org", "networks", "network_id"),
        ("fk_devices_subnet_org", "subnets", "subnet_id"),
        ("fk_devices_vlan_org", "vlans", "vlan_id"),
        ("fk_devices_wlan_org", "wlans", "wlan_id"),
        ("fk_devices_assigned_user_org", "users", "assigned_user_id"),
    ]
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("devices") as batch:
            for column in columns:
                batch.add_column(column)
            for name, table, column in fks:
                batch.create_foreign_key(name, table, [column, "organization_id"], ["id", "organization_id"])
    else:
        asset_enum.create(bind, checkfirst=True)
        criticality_enum.create(bind, checkfirst=True)
        for column in columns:
            op.add_column("devices", column)
        for name, table, column in fks:
            op.create_foreign_key(name, "devices", table, [column, "organization_id"], ["id", "organization_id"])


def downgrade() -> None:
    bind = op.get_bind()
    fks = [
        "fk_devices_assigned_user_org", "fk_devices_wlan_org", "fk_devices_vlan_org",
        "fk_devices_subnet_org", "fk_devices_network_org", "fk_devices_site_org",
    ]
    columns = [
        "assigned_user_id", "wlan_id", "vlan_id", "subnet_id", "network_id", "site_id",
        "warranty_expiration", "purchase_date", "location", "discovery_source", "criticality",
        "storage", "memory", "cpu", "mac_address", "bios_version", "firmware_version",
        "model", "manufacturer", "serial_number", "asset_tag", "management_ip",
        "ipv6_address", "operating_system_version", "asset_type",
    ]
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("devices") as batch:
            for name in fks:
                batch.drop_constraint(name, type_="foreignkey")
            for column in columns:
                batch.drop_column(column)
    else:
        for name in fks:
            op.drop_constraint(name, "devices", type_="foreignkey")
        for column in columns:
            op.drop_column("devices", column)
        sa.Enum(name="device_criticality").drop(bind, checkfirst=True)
        sa.Enum(name="asset_type").drop(bind, checkfirst=True)
    for name in ("wlans", "vlans", "subnets", "networks", "sites"):
        op.drop_index("ix_%s_organization_id" % name, table_name=name)
        op.drop_table(name)
