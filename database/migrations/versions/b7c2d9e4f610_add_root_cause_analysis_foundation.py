"""add Phase 1H secure root-cause analysis foundation.

Revision ID: b7c2d9e4f610
Revises: 9e4f7a1c2b30
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


revision: str = "b7c2d9e4f610"
down_revision: Union[str, None] = "9e4f7a1c2b30"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(
            "PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED",
            name="root_cause_analysis_status",
        ).create(bind, checkfirst=True)
        sa.Enum(
            "LOW", "MEDIUM", "HIGH", "CRITICAL",
            name="root_cause_finding_severity",
        ).create(bind, checkfirst=True)
        sa.Enum(
            "IDENTIFIED", "LIKELY", "INSUFFICIENT_EVIDENCE",
            name="root_cause_finding_status",
        ).create(bind, checkfirst=True)
        sa.Enum(
            "HIGH", "MEDIUM", "LOW",
            name="root_cause_finding_confidence",
        ).create(bind, checkfirst=True)

    parent_constraints = (
        (
            "diagnostic_runs", "uq_diagnostic_runs_id_device_organization",
            ["id", "device_id", "organization_id"],
        ),
        (
            "diagnostic_results", "uq_diagnostic_results_id_device_organization",
            ["id", "device_id", "organization_id"],
        ),
        ("devices", "uq_devices_id_organization", ["id", "organization_id"]),
    )
    if bind.dialect.name == "sqlite":
        for table_name, constraint_name, columns in parent_constraints:
            with op.batch_alter_table(table_name) as batch:
                batch.create_unique_constraint(constraint_name, columns)
    else:
        for table_name, constraint_name, columns in parent_constraints:
            op.create_unique_constraint(constraint_name, table_name, columns)

    analysis_status = sa.Enum(
        "PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED",
        name="root_cause_analysis_status",
    )
    finding_severity = sa.Enum(
        "LOW", "MEDIUM", "HIGH", "CRITICAL",
        name="root_cause_finding_severity",
    )
    op.create_table(
        "root_cause_analyses",
        sa.Column("id", MigrationUUID(), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("device_id", MigrationUUID(), nullable=False),
        sa.Column("diagnostic_run_id", MigrationUUID(), nullable=False),
        sa.Column("initiated_by_user_id", MigrationUUID(), nullable=True),
        sa.Column("provider", sa.String(length=50), server_default="deterministic", nullable=False),
        sa.Column("status", analysis_status, nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["device_id", "organization_id"], ["devices.id", "devices.organization_id"],
            name="fk_root_cause_analyses_device_organization", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["diagnostic_run_id", "device_id", "organization_id"],
            [
                "diagnostic_runs.id", "diagnostic_runs.device_id",
                "diagnostic_runs.organization_id",
            ],
            name="fk_root_cause_analyses_run_organization", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["initiated_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "device_id", "organization_id",
            name="uq_root_cause_analyses_id_device_organization",
        ),
    )
    op.create_table(
        "root_cause_findings",
        sa.Column("id", MigrationUUID(), nullable=False),
        sa.Column("analysis_id", MigrationUUID(), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("device_id", MigrationUUID(), nullable=False),
        sa.Column("diagnostic_result_id", MigrationUUID(), nullable=False),
        sa.Column("rule_id", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("status", sa.Enum(
            "IDENTIFIED", "LIKELY", "INSUFFICIENT_EVIDENCE",
            name="root_cause_finding_status",
        ), nullable=False),
        sa.Column("severity", finding_severity, nullable=False),
        sa.Column("confidence", sa.Enum(
            "HIGH", "MEDIUM", "LOW",
            name="root_cause_finding_confidence",
        ), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("fingerprint", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["analysis_id", "device_id", "organization_id"],
            [
                "root_cause_analyses.id", "root_cause_analyses.device_id",
                "root_cause_analyses.organization_id",
            ],
            name="fk_root_cause_findings_analysis_organization", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["device_id", "organization_id"], ["devices.id", "devices.organization_id"],
            name="fk_root_cause_findings_device_organization", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["diagnostic_result_id", "device_id", "organization_id"],
            [
                "diagnostic_results.id", "diagnostic_results.device_id",
                "diagnostic_results.organization_id",
            ],
            name="fk_root_cause_findings_result_organization", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "id", "device_id", "organization_id",
            name="uq_root_cause_findings_id_device_organization",
        ),
        sa.UniqueConstraint("analysis_id", "fingerprint", name="uq_root_cause_findings_analysis_fingerprint"),
    )
    op.create_index("ix_root_cause_analyses_organization_id", "root_cause_analyses", ["organization_id"])
    op.create_index("ix_root_cause_analyses_status", "root_cause_analyses", ["status"])
    op.create_index("ix_root_cause_analyses_org_status", "root_cause_analyses", ["organization_id", "status"])
    op.create_index("ix_root_cause_analyses_run", "root_cause_analyses", ["diagnostic_run_id"])
    op.create_index("ix_root_cause_analyses_initiated_by_user_id", "root_cause_analyses", ["initiated_by_user_id"])
    op.create_index("ix_root_cause_findings_analysis", "root_cause_findings", ["analysis_id"])
    op.create_index("ix_root_cause_findings_organization_id", "root_cause_findings", ["organization_id"])
    op.create_index("ix_root_cause_findings_device_id", "root_cause_findings", ["device_id"])
    op.create_index("ix_root_cause_findings_diagnostic_result_id", "root_cause_findings", ["diagnostic_result_id"])


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("ix_root_cause_findings_analysis", table_name="root_cause_findings")
    op.drop_index("ix_root_cause_findings_diagnostic_result_id", table_name="root_cause_findings")
    op.drop_index("ix_root_cause_findings_device_id", table_name="root_cause_findings")
    op.drop_index("ix_root_cause_findings_organization_id", table_name="root_cause_findings")
    op.drop_table("root_cause_findings")
    for name in (
        "ix_root_cause_analyses_initiated_by_user_id",
        "ix_root_cause_analyses_run",
        "ix_root_cause_analyses_org_status",
        "ix_root_cause_analyses_status",
        "ix_root_cause_analyses_organization_id",
    ):
        op.drop_index(name, table_name="root_cause_analyses")
    op.drop_table("root_cause_analyses")
    parent_constraints = (
        ("diagnostic_runs", "uq_diagnostic_runs_id_device_organization"),
        ("diagnostic_results", "uq_diagnostic_results_id_device_organization"),
        ("devices", "uq_devices_id_organization"),
    )
    if bind.dialect.name == "sqlite":
        for table_name, constraint_name in parent_constraints:
            with op.batch_alter_table(table_name) as batch:
                batch.drop_constraint(constraint_name, type_="unique")
    else:
        for table_name, constraint_name in parent_constraints:
            op.drop_constraint(constraint_name, table_name, type_="unique")
    if bind.dialect.name == "postgresql":
        sa.Enum(name="root_cause_finding_confidence").drop(bind, checkfirst=True)
        sa.Enum(name="root_cause_finding_status").drop(bind, checkfirst=True)
        sa.Enum(name="root_cause_finding_severity").drop(bind, checkfirst=True)
        sa.Enum(name="root_cause_analysis_status").drop(bind, checkfirst=True)
