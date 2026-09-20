"""add discovery job foundation

Revision ID: 7c1e4f6a2b90
Revises: 2f5d7c8e9a10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID


class MigrationUUID(sa.TypeDecorator):
    impl = sa.String
    cache_ok = True

    def load_dialect_impl(self, dialect: sa.engine.Dialect) -> sa.types.TypeEngine:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQLUUID(as_uuid=True))
        return dialect.type_descriptor(sa.String(36))


revision: str = "7c1e4f6a2b90"
down_revision: Union[str, None] = "2f5d7c8e9a10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "discovery_jobs",
        sa.Column("id", MigrationUUID(), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("created_by_user_id", MigrationUUID(), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=20), nullable=False),
        sa.Column("target_definition", sa.String(length=255), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="discovery_job_status"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_jobs_organization_id", "discovery_jobs", ["organization_id"], unique=False)
    op.create_index("ix_discovery_jobs_created_by_user_id", "discovery_jobs", ["created_by_user_id"], unique=False)
    op.create_index("ix_discovery_jobs_org_status", "discovery_jobs", ["organization_id", "status"], unique=False)
    op.create_index("ix_discovery_jobs_status", "discovery_jobs", ["status"], unique=False)
    op.create_index("ix_discovery_jobs_created_at", "discovery_jobs", ["created_at"], unique=False)

    op.create_table(
        "discovery_results",
        sa.Column("id", MigrationUUID(), nullable=False),
        sa.Column("discovery_job_id", MigrationUUID(), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("target_ip", sa.String(length=45), nullable=False),
        sa.Column("discovered_hostname", sa.String(length=255), nullable=True),
        sa.Column("discovered_device_type", sa.String(length=100), nullable=True),
        sa.Column("discovered_operating_system", sa.String(length=200), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DISCOVERED", "NOT_REACHABLE", "FAILED", name="discovery_result_status"),
            nullable=False,
        ),
        sa.Column(
            "reconciliation_status",
            sa.Enum("UNMATCHED", "MATCHED", "CONFLICT", name="reconciliation_status"),
            nullable=False,
        ),
        sa.Column("matched_device_id", MigrationUUID(), nullable=True),
        sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["discovery_job_id"], ["discovery_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["matched_device_id"], ["devices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_discovery_results_discovery_job_id", "discovery_results", ["discovery_job_id"], unique=False)
    op.create_index("ix_discovery_results_organization_id", "discovery_results", ["organization_id"], unique=False)
    op.create_index("ix_discovery_results_org_ip", "discovery_results", ["organization_id", "target_ip"], unique=False)
    op.create_index("ix_discovery_results_reconciliation", "discovery_results", ["organization_id", "reconciliation_status"], unique=False)
    op.create_index("ix_discovery_results_matched_device_id", "discovery_results", ["matched_device_id"], unique=False)


def downgrade() -> None:
    op.drop_table("discovery_results")
    op.drop_table("discovery_jobs")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for enum_name in ("reconciliation_status", "discovery_result_status", "discovery_job_status"):
            sa.Enum(name=enum_name).drop(bind, checkfirst=True)
