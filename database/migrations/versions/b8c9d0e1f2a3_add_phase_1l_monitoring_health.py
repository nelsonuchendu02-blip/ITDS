"""add Phase 1L secure monitoring and health telemetry foundation.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.dialects.postgresql import ENUM as PostgreSQLEnum

revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class MigrationUUID(sa.TypeDecorator):
    impl = sa.String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(
            PostgreSQLUUID(as_uuid=True) if dialect.name == "postgresql" else sa.String(36))


def _enum(name, *values):
    return sa.Enum(*values, name=name)


def _health_enum(bind):
    values = ("HEALTHY", "DEGRADED", "UNHEALTHY", "OFFLINE", "UNKNOWN")
    if bind.dialect.name == "postgresql":
        return PostgreSQLEnum(*values, name="health_status", create_type=False)
    return _enum("health_status", *values)


def upgrade() -> None:
    bind = op.get_bind()
    health = _health_enum(bind)
    if bind.dialect.name == "postgresql":
        PostgreSQLEnum("HEALTHY", "DEGRADED", "UNHEALTHY", "OFFLINE", "UNKNOWN",
                      name="health_status").create(bind, checkfirst=True)
    op.create_table(
        "monitoring_targets",
        sa.Column("id", MigrationUUID(), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("device_id", MigrationUUID(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("check_interval_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("offline_after_seconds", sa.Integer(), nullable=False, server_default="900"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_status_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(100)),
        sa.Column("health_status", health, nullable=False, server_default="UNKNOWN"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_monitoring_targets_id_organization"),
        sa.UniqueConstraint("organization_id", "device_id", name="uq_monitoring_targets_org_device"),
        sa.CheckConstraint("check_interval_seconds >= 10", name="ck_monitoring_targets_interval_min"),
        sa.CheckConstraint("check_interval_seconds <= 86400", name="ck_monitoring_targets_interval_max"),
        sa.CheckConstraint("offline_after_seconds >= 10", name="ck_monitoring_targets_offline_min"),
        sa.CheckConstraint("offline_after_seconds <= 604800", name="ck_monitoring_targets_offline_max"),
        sa.CheckConstraint("offline_after_seconds >= check_interval_seconds",
                           name="ck_monitoring_targets_offline_after_interval"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id", "organization_id"], ["devices.id", "devices.organization_id"],
                                name="fk_monitoring_targets_device_org"),
    )
    for name, columns in (
        ("ix_monitoring_targets_organization_id", ["organization_id"]),
        ("ix_monitoring_targets_device_id", ["device_id"]),
        ("ix_monitoring_targets_enabled", ["enabled"]),
        ("ix_monitoring_targets_health_status", ["health_status"]),
        ("ix_monitoring_targets_last_seen_at", ["last_seen_at"]),
    ):
        op.create_index(name, "monitoring_targets", columns)
    op.create_table(
        "health_telemetry",
        sa.Column("id", MigrationUUID(), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("target_id", MigrationUUID(), nullable=False),
        sa.Column("device_id", MigrationUUID(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("health_status", health, nullable=False),
        sa.Column("latency_ms", sa.Integer()),
        sa.Column("packet_loss_percent", sa.Float()),
        sa.Column("cpu_percent", sa.Float()),
        sa.Column("memory_percent", sa.Float()),
        sa.Column("disk_percent", sa.Float()),
        sa.Column("uptime_seconds", sa.Integer()),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("details", sa.JSON()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_health_telemetry_id_organization"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_id", "organization_id"],
                                ["monitoring_targets.id", "monitoring_targets.organization_id"],
                                name="fk_health_telemetry_target_org"),
        sa.ForeignKeyConstraint(["device_id", "organization_id"], ["devices.id", "devices.organization_id"],
                                name="fk_health_telemetry_device_org"),
    )
    for name, columns in (
        ("ix_health_telemetry_organization_id", ["organization_id"]),
        ("ix_health_telemetry_target_id", ["target_id"]),
        ("ix_health_telemetry_device_id", ["device_id"]),
        ("ix_health_telemetry_observed_at", ["observed_at"]),
        ("ix_health_telemetry_received_at", ["received_at"]),
        ("ix_health_telemetry_org_health_status", ["organization_id", "health_status"]),
        ("ix_health_telemetry_org_device_observed", ["organization_id", "device_id", "observed_at"]),
    ):
        op.create_index(name, "health_telemetry", columns)


def downgrade() -> None:
    for name in ("ix_health_telemetry_org_device_observed", "ix_health_telemetry_org_health_status",
                 "ix_health_telemetry_received_at", "ix_health_telemetry_observed_at",
                 "ix_health_telemetry_device_id", "ix_health_telemetry_target_id",
                 "ix_health_telemetry_organization_id"):
        op.drop_index(name, table_name="health_telemetry")
    op.drop_table("health_telemetry")
    for name in ("ix_monitoring_targets_last_seen_at", "ix_monitoring_targets_health_status",
                 "ix_monitoring_targets_enabled", "ix_monitoring_targets_device_id",
                 "ix_monitoring_targets_organization_id"):
        op.drop_index(name, table_name="monitoring_targets")
    op.drop_table("monitoring_targets")
    # health_status is shared with ORM metadata and other migrations; do not
    # drop it when removing the Phase 1L tables.
