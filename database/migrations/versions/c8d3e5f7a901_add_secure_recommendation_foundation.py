"""add Phase 1I secure recommendation foundation.

Revision ID: c8d3e5f7a901
Revises: b7c2d9e4f610
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.dialects.postgresql import ENUM as PostgreSQLEnum

revision: str = "c8d3e5f7a901"
down_revision: Union[str, None] = "b7c2d9e4f610"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class MigrationUUID(sa.TypeDecorator):
    impl = sa.String
    cache_ok = True
    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(PostgreSQLUUID(as_uuid=True) if dialect.name == "postgresql" else sa.String(36))


def _columns(bind):
    enum_types = {}
    if bind.dialect.name == "postgresql":
        enum_types = {
            "severity": PostgreSQLEnum("low", "medium", "high", "critical",
                                      name="recommendation_severity", create_type=False),
            "confidence": PostgreSQLEnum("low", "medium", "high",
                                        name="recommendation_confidence", create_type=False),
            "remediation_type": PostgreSQLEnum(
                "guidance", "configuration", "investigation", "escalation",
                name="recommendation_remediation_type", create_type=False,
            ),
        }
    else:
        enum_types = {
            "severity": sa.Enum("low", "medium", "high", "critical", name="recommendation_severity"),
            "confidence": sa.Enum("low", "medium", "high", name="recommendation_confidence"),
            "remediation_type": sa.Enum(
                "guidance", "configuration", "investigation", "escalation",
                name="recommendation_remediation_type",
            ),
        }
    return [
        sa.Column("root_cause_finding_id", MigrationUUID(), nullable=True),
        sa.Column("root_cause_analysis_id", MigrationUUID(), nullable=True),
        sa.Column("created_by_user_id", MigrationUUID(), nullable=True),
        sa.Column("decided_by_user_id", MigrationUUID(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("rule_id", sa.String(100), nullable=False, server_default="manual"),
        sa.Column("fingerprint", sa.String(64), nullable=False, server_default=""),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("reviewed_by_user_id", MigrationUUID(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("implemented_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("implementation_notes", sa.Text(), nullable=True),
        sa.Column("category", sa.String(100), nullable=False, server_default="GENERAL"),
        sa.Column("severity", enum_types["severity"], nullable=False, server_default="medium"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("expected_effect", sa.Text(), nullable=False, server_default=""),
        sa.Column("confidence", enum_types["confidence"], nullable=False, server_default="medium"),
        sa.Column("remediation_type", enum_types["remediation_type"], nullable=False, server_default="guidance"),
        sa.Column("requires_human_approval", sa.Boolean(), nullable=False, server_default=sa.true()),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for enum_type in (
            PostgreSQLEnum("low", "medium", "high", "critical", name="recommendation_severity"),
            PostgreSQLEnum("low", "medium", "high", name="recommendation_confidence"),
            PostgreSQLEnum("guidance", "configuration", "investigation", "escalation",
                           name="recommendation_remediation_type"),
        ):
            enum_type.create(bind, checkfirst=True)
        # Replace the Phase 1A enum safely, mapping legacy values.
        op.execute("ALTER TYPE recommendation_status RENAME TO recommendation_status_legacy")
        op.execute("CREATE TYPE recommendation_status AS ENUM ('pending','reviewed','accepted','rejected','implemented')")
        op.execute("""
            ALTER TABLE recommendations ALTER COLUMN status TYPE recommendation_status
            USING (CASE status::text WHEN 'PROPOSED' THEN 'pending'
                WHEN 'COMPLETED' THEN 'implemented' ELSE lower(status::text) END)::recommendation_status
        """)
        op.execute("DROP TYPE recommendation_status_legacy")
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("recommendations") as batch:
            for column in _columns(bind):
                batch.add_column(column)
            batch.create_index("ix_recommendations_root_cause_finding_id", ["root_cause_finding_id"])
            batch.create_index("ix_recommendations_root_cause_analysis_id", ["root_cause_analysis_id"])
            batch.create_index("ix_recommendations_created_by_user_id", ["created_by_user_id"])
            batch.create_index("ix_recommendations_decided_by_user_id", ["decided_by_user_id"])
            batch.create_foreign_key("fk_recommendations_finding_scope", "root_cause_findings",
                                     ["root_cause_finding_id", "device_id", "organization_id"],
                                     ["id", "device_id", "organization_id"], ondelete="CASCADE")
            batch.create_foreign_key("fk_recommendations_analysis_scope", "root_cause_analyses",
                                     ["root_cause_analysis_id", "device_id", "organization_id"],
                                     ["id", "device_id", "organization_id"], ondelete="CASCADE")
            batch.create_foreign_key("fk_recommendations_result_scope", "diagnostic_results",
                                     ["diagnostic_result_id", "device_id", "organization_id"],
                                     ["id", "device_id", "organization_id"], ondelete="CASCADE")
            batch.create_foreign_key("fk_recommendations_device_scope", "devices",
                                     ["device_id", "organization_id"],
                                     ["id", "organization_id"], ondelete="CASCADE")
            batch.create_foreign_key("fk_recommendations_created_by_user", "users",
                                     ["created_by_user_id"], ["id"], ondelete="SET NULL")
            batch.create_foreign_key("fk_recommendations_decided_by_user", "users",
                                     ["decided_by_user_id"], ["id"], ondelete="SET NULL")
            batch.create_unique_constraint(
                "uq_recommendations_deterministic_identity",
                ["organization_id", "device_id", "root_cause_finding_id", "rule_id", "fingerprint"],
            )
        return
    for column in _columns(bind):
        op.add_column("recommendations", column)
    op.create_index("ix_recommendations_root_cause_finding_id", "recommendations", ["root_cause_finding_id"])
    op.create_index("ix_recommendations_root_cause_analysis_id", "recommendations", ["root_cause_analysis_id"])
    op.create_index("ix_recommendations_created_by_user_id", "recommendations", ["created_by_user_id"])
    op.create_index("ix_recommendations_decided_by_user_id", "recommendations", ["decided_by_user_id"])
    op.create_foreign_key("fk_recommendations_finding_scope", "recommendations", "root_cause_findings",
                          ["root_cause_finding_id", "device_id", "organization_id"],
                          ["id", "device_id", "organization_id"], ondelete="CASCADE")
    op.create_foreign_key("fk_recommendations_analysis_scope", "recommendations", "root_cause_analyses",
                          ["root_cause_analysis_id", "device_id", "organization_id"],
                          ["id", "device_id", "organization_id"], ondelete="CASCADE")
    op.create_foreign_key("fk_recommendations_result_scope", "recommendations", "diagnostic_results",
                              ["diagnostic_result_id", "device_id", "organization_id"],
                              ["id", "device_id", "organization_id"], ondelete="CASCADE")
    op.create_foreign_key("fk_recommendations_device_scope", "recommendations", "devices",
                              ["device_id", "organization_id"], ["id", "organization_id"], ondelete="CASCADE")
    op.create_foreign_key("fk_recommendations_created_by_user", "recommendations", "users",
                          ["created_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_recommendations_decided_by_user", "recommendations", "users",
                          ["decided_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint(
        "uq_recommendations_deterministic_identity", "recommendations",
        ["organization_id", "device_id", "root_cause_finding_id", "rule_id", "fingerprint"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("recommendations") as batch:
            for name in ("fk_recommendations_result_scope", "fk_recommendations_finding_scope",
                         "fk_recommendations_analysis_scope",
                         "fk_recommendations_device_scope"):
                batch.drop_constraint(name, type_="foreignkey")
            batch.drop_constraint("uq_recommendations_deterministic_identity", type_="unique")
            for name in ("ix_recommendations_decided_by_user_id", "ix_recommendations_created_by_user_id",
                         "ix_recommendations_root_cause_analysis_id", "ix_recommendations_root_cause_finding_id"):
                batch.drop_index(name)
            for name in ("implementation_notes", "implemented_at", "rejection_reason", "reviewed_at",
                         "reviewed_by_user_id", "evidence", "fingerprint", "rule_id", "rationale", "decided_at",
                         "decided_by_user_id", "created_by_user_id", "root_cause_finding_id",
                         "requires_human_approval", "remediation_type", "confidence",
                         "expected_effect", "summary", "severity", "category"):
                batch.drop_column(name)
    else:
        op.drop_constraint("uq_recommendations_deterministic_identity", "recommendations", type_="unique")
        for name in ("fk_recommendations_decided_by_user", "fk_recommendations_created_by_user",
                     "fk_recommendations_result_scope", "fk_recommendations_finding_scope",
                     "fk_recommendations_analysis_scope",
                     "fk_recommendations_device_scope"):
            op.drop_constraint(name, "recommendations", type_="foreignkey")
        for name in ("ix_recommendations_decided_by_user_id", "ix_recommendations_created_by_user_id",
                     "ix_recommendations_root_cause_analysis_id", "ix_recommendations_root_cause_finding_id"):
            op.drop_index(name, table_name="recommendations")
        for name in ("implementation_notes", "implemented_at", "rejection_reason", "reviewed_at",
                     "reviewed_by_user_id", "evidence", "fingerprint", "rule_id", "rationale", "decided_at",
                     "decided_by_user_id", "created_by_user_id", "root_cause_finding_id",
                     "requires_human_approval", "remediation_type", "confidence",
                     "expected_effect", "summary", "severity", "category"):
            op.drop_column("recommendations", name)
        op.execute("ALTER TYPE recommendation_status RENAME TO recommendation_status_phase1i")
        op.execute("CREATE TYPE recommendation_status AS ENUM ('PROPOSED','ACCEPTED','REJECTED','COMPLETED')")
        op.execute("""
            ALTER TABLE recommendations ALTER COLUMN status TYPE recommendation_status
            USING (CASE status::text WHEN 'pending' THEN 'PROPOSED'
                WHEN 'reviewed' THEN 'PROPOSED' WHEN 'implemented' THEN 'COMPLETED'
                ELSE upper(status::text) END)::recommendation_status
        """)
        op.execute("DROP TYPE recommendation_status_phase1i")
        for name in ("recommendation_remediation_type", "recommendation_confidence",
                     "recommendation_severity"):
            op.execute(f"DROP TYPE {name}")


class _nullcontext:
    def __enter__(self): return self
    def __exit__(self, *_): return False
