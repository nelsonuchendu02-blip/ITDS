"""extend diagnostic persistence for Phase 1G.

Revision ID: 9e4f7a1c2b30
Revises: 8d2e4f6a1b90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID


class MigrationUUID(sa.TypeDecorator):
    impl = sa.String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PostgreSQLUUID(as_uuid=True))
        return dialect.type_descriptor(sa.String(36))


revision: str = "9e4f7a1c2b30"
down_revision: Union[str, None] = "8d2e4f6a1b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE diagnostic_run_status ADD VALUE IF NOT EXISTS 'CANCELLED'")
        sa.Enum(
            "CONNECTIVITY", "CONFIGURATION", "SECURITY", "PERFORMANCE",
            name="diagnostic_check_type",
        ).create(bind, checkfirst=True)
    op.add_column("diagnostic_runs", sa.Column("provider", sa.String(50), server_default="simulated", nullable=False))
    op.add_column("diagnostic_runs", sa.Column("created_by_user_id", MigrationUUID(), nullable=True))
    if bind.dialect.name == "postgresql":
        op.create_foreign_key(
            "fk_diagnostic_runs_created_by_user_id", "diagnostic_runs", "users",
            ["created_by_user_id"], ["id"], ondelete="SET NULL",
        )
    elif bind.dialect.name == "sqlite":
        with op.batch_alter_table("diagnostic_runs") as batch:
            batch.create_foreign_key(
                "fk_diagnostic_runs_created_by_user_id", "users",
                ["created_by_user_id"], ["id"], ondelete="SET NULL",
            )
    op.add_column("diagnostic_runs", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("diagnostic_runs", sa.Column("error_code", sa.String(100), nullable=True))
    op.add_column(
        "diagnostic_results",
        sa.Column(
            "check_type",
            sa.Enum("CONNECTIVITY", "CONFIGURATION", "SECURITY", "PERFORMANCE", name="diagnostic_check_type"),
            server_default="CONNECTIVITY",
            nullable=False,
        ),
    )
    # Explicit denormalized scope makes result reads safe even when callers do
    # not load the parent run. Backfill before enforcing NOT NULL.
    op.add_column("diagnostic_results", sa.Column("organization_id", MigrationUUID(), nullable=True))
    op.add_column("diagnostic_results", sa.Column("device_id", MigrationUUID(), nullable=True))
    op.add_column("diagnostic_results", sa.Column("title", sa.String(255), nullable=True))
    op.add_column("diagnostic_results", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("diagnostic_results", sa.Column("recommendation", sa.Text(), nullable=True))
    op.add_column("diagnostic_results", sa.Column("result_metadata", sa.JSON(), nullable=True))
    op.add_column(
        "diagnostic_results",
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    backfill_sql = (
        "UPDATE diagnostic_results SET organization_id = diagnostic_runs.organization_id, "
        "device_id = diagnostic_runs.device_id, "
        "title = COALESCE(NULLIF(check_identifier, ''), 'Diagnostic result'), "
        "checked_at = COALESCE(created_at, CURRENT_TIMESTAMP) "
        "FROM diagnostic_runs WHERE diagnostic_results.diagnostic_run_id = diagnostic_runs.id"
        if bind.dialect.name == "postgresql"
        else (
            "UPDATE diagnostic_results SET organization_id = (SELECT organization_id FROM diagnostic_runs WHERE diagnostic_runs.id = diagnostic_results.diagnostic_run_id), "
        "device_id = (SELECT device_id FROM diagnostic_runs WHERE diagnostic_runs.id = diagnostic_results.diagnostic_run_id), "
            "title = COALESCE(NULLIF(check_identifier, ''), 'Diagnostic result'), "
            "checked_at = COALESCE(created_at, CURRENT_TIMESTAMP)"
        )
    )
    op.execute(backfill_sql)
    missing_values = bind.execute(sa.text(
        "SELECT COUNT(*) FROM diagnostic_results "
        "WHERE organization_id IS NULL OR device_id IS NULL "
        "OR title IS NULL OR checked_at IS NULL"
    )).scalar_one()
    if missing_values:
        raise RuntimeError(
            "Phase 1G diagnostic result backfill could not populate required fields"
        )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("diagnostic_results") as batch:
            for column in ("organization_id", "device_id", "title", "checked_at"):
                batch.alter_column(column, nullable=False)
            batch.create_foreign_key(
                "fk_diagnostic_results_organization_id", "organizations",
                ["organization_id"], ["id"], ondelete="CASCADE",
            )
            batch.create_foreign_key(
                "fk_diagnostic_results_device_id", "devices",
                ["device_id"], ["id"], ondelete="CASCADE",
            )
    else:
        for column in ("organization_id", "device_id", "title", "checked_at"):
            op.alter_column("diagnostic_results", column, nullable=False)
    if bind.dialect.name == "postgresql":
        op.create_foreign_key(
            "fk_diagnostic_results_organization_id", "diagnostic_results", "organizations",
            ["organization_id"], ["id"], ondelete="CASCADE",
        )
        op.create_foreign_key(
            "fk_diagnostic_results_device_id", "diagnostic_results", "devices",
            ["device_id"], ["id"], ondelete="CASCADE",
        )
    op.create_index("ix_diagnostic_results_organization_id", "diagnostic_results", ["organization_id"])
    op.create_index("ix_diagnostic_results_device_id", "diagnostic_results", ["device_id"])
    op.create_index("ix_diagnostic_runs_created_by_user_id", "diagnostic_runs", ["created_by_user_id"])
    if bind.dialect.name == "postgresql":
        op.create_check_constraint(
            "ck_diagnostic_runs_terminal_timestamps",
            "diagnostic_runs",
            "(status NOT IN ('COMPLETED', 'FAILED', 'CANCELLED')) OR completed_at IS NOT NULL OR cancelled_at IS NOT NULL",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.drop_constraint("ck_diagnostic_runs_terminal_timestamps", "diagnostic_runs", type_="check")
        op.drop_constraint("fk_diagnostic_runs_created_by_user_id", "diagnostic_runs", type_="foreignkey")
    elif bind.dialect.name == "sqlite":
        with op.batch_alter_table("diagnostic_runs") as batch:
            batch.drop_constraint("fk_diagnostic_runs_created_by_user_id", type_="foreignkey")
    op.drop_index("ix_diagnostic_runs_created_by_user_id", table_name="diagnostic_runs")
    op.drop_index("ix_diagnostic_results_device_id", table_name="diagnostic_results")
    op.drop_index("ix_diagnostic_results_organization_id", table_name="diagnostic_results")
    if bind.dialect.name == "postgresql":
        op.drop_constraint("fk_diagnostic_results_device_id", "diagnostic_results", type_="foreignkey")
        op.drop_constraint("fk_diagnostic_results_organization_id", "diagnostic_results", type_="foreignkey")
    elif bind.dialect.name == "sqlite":
        with op.batch_alter_table("diagnostic_results") as batch:
            batch.drop_constraint("fk_diagnostic_results_device_id", type_="foreignkey")
            batch.drop_constraint("fk_diagnostic_results_organization_id", type_="foreignkey")
    for column in ("checked_at", "result_metadata", "recommendation", "summary", "title", "device_id", "organization_id"):
        op.drop_column("diagnostic_results", column)
    op.drop_column("diagnostic_results", "check_type")
    op.drop_column("diagnostic_runs", "error_code")
    op.drop_column("diagnostic_runs", "cancelled_at")
    op.drop_column("diagnostic_runs", "created_by_user_id")
    op.drop_column("diagnostic_runs", "provider")
    if bind.dialect.name == "postgresql":
        sa.Enum(name="diagnostic_check_type").drop(bind, checkfirst=True)
