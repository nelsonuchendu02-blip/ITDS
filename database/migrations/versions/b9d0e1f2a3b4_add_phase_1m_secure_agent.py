"""add Phase 1M secure endpoint agent foundation.

Revision ID: b9d0e1f2a3b4
Revises: b8c9d0e1f2a3
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PGUUID, ENUM as PGEnum

revision = "b9d0e1f2a3b4"
down_revision: Union[str, None] = "b8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on = None

AGENT_STATUS_VALUES = ("pending", "active", "offline", "revoked", "retired")


class MigrationUUID(sa.TypeDecorator):
    impl = sa.String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(
            PGUUID(as_uuid=True) if dialect.name == "postgresql" else sa.String(36))


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        PGEnum(*AGENT_STATUS_VALUES, name="agent_status").create(bind, checkfirst=True)
        status = PGEnum(*AGENT_STATUS_VALUES, name="agent_status", create_type=False)
    else:
        status = sa.Enum(*AGENT_STATUS_VALUES, name="agent_status")

    op.create_table(
        "agents",
        sa.Column("id", MigrationUUID(), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("device_id", MigrationUUID(), nullable=True),
        sa.Column("agent_name", sa.String(200), nullable=False),
        sa.Column("status", status, nullable=False, server_default="pending"),
        sa.Column("agent_version", sa.String(100)),
        sa.Column("platform", sa.String(100), nullable=False, server_default="windows"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("last_ip_address", sa.String(45)),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_error_code", sa.String(100)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_agents_id_organization"),
        sa.UniqueConstraint("organization_id", "device_id", name="uq_agents_org_device"),
        sa.UniqueConstraint("organization_id", "agent_name", name="uq_agents_org_name"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id", "organization_id"], ["devices.id", "devices.organization_id"],
                                name="fk_agents_device_org"),
    )
    op.create_index("ix_agents_organization_id", "agents", ["organization_id"])
    op.create_index("ix_agents_device_id", "agents", ["device_id"])
    op.create_index("ix_agents_status", "agents", ["status"])
    op.create_index("ix_agents_last_seen_at", "agents", ["last_seen_at"])

    op.create_table(
        "agent_enrollment_tokens",
        sa.Column("id", MigrationUUID(), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("token_prefix", sa.String(32), nullable=False),
        sa.Column("token_hash", sa.String(255), nullable=False),
        sa.Column("created_by_user_id", MigrationUUID()),
        sa.Column("target_device_id", MigrationUUID(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_uses", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_agent_enrollment_tokens_hash"),
        sa.UniqueConstraint("token_prefix", name="uq_agent_enrollment_tokens_prefix"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_device_id", "organization_id"], ["devices.id", "devices.organization_id"],
                                name="fk_agent_enrollment_tokens_device_org"),
    )
    op.create_index("ix_agent_enrollment_tokens_org", "agent_enrollment_tokens", ["organization_id"])
    op.create_index("ix_agent_enrollment_tokens_prefix", "agent_enrollment_tokens", ["token_prefix"])
    op.create_index("ix_agent_enrollment_tokens_target_device", "agent_enrollment_tokens", ["target_device_id"])
    op.create_index("ix_agent_enrollment_tokens_org_expires", "agent_enrollment_tokens",
                    ["organization_id", "expires_at"])

    op.create_table(
        "agent_credentials",
        sa.Column("id", MigrationUUID(), nullable=False),
        sa.Column("agent_id", MigrationUUID(), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("credential_prefix", sa.String(32), nullable=False),
        sa.Column("credential_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_ip", sa.String(45)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "organization_id", name="uq_agent_credentials_id_organization"),
        sa.UniqueConstraint("credential_hash", name="uq_agent_credentials_hash"),
        sa.UniqueConstraint("credential_prefix", name="uq_agent_credentials_prefix"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id", "organization_id"], ["agents.id", "agents.organization_id"],
                                name="fk_agent_credentials_agent_org"),
    )
    op.create_index("ix_agent_credentials_agent_id", "agent_credentials", ["agent_id"])
    op.create_index("ix_agent_credentials_organization_id", "agent_credentials", ["organization_id"])
    op.create_index("ix_agent_credentials_prefix", "agent_credentials", ["credential_prefix"])


def downgrade() -> None:
    for name, table in (
        ("ix_agent_credentials_prefix", "agent_credentials"),
        ("ix_agent_credentials_organization_id", "agent_credentials"),
        ("ix_agent_credentials_agent_id", "agent_credentials"),
        ("ix_agent_enrollment_tokens_org_expires", "agent_enrollment_tokens"),
        ("ix_agent_enrollment_tokens_target_device", "agent_enrollment_tokens"),
        ("ix_agent_enrollment_tokens_prefix", "agent_enrollment_tokens"),
        ("ix_agent_enrollment_tokens_org", "agent_enrollment_tokens"),
        ("ix_agents_last_seen_at", "agents"),
        ("ix_agents_status", "agents"),
        ("ix_agents_device_id", "agents"),
        ("ix_agents_organization_id", "agents"),
    ):
        op.drop_index(name, table_name=table)
    op.drop_table("agent_credentials")
    op.drop_table("agent_enrollment_tokens")
    op.drop_table("agents")
    if op.get_bind().dialect.name == "postgresql":
        PGEnum(name="agent_status").drop(op.get_bind(), checkfirst=True)
