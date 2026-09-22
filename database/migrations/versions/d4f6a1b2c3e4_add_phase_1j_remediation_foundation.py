"""add Phase 1J secure remediation foundation.

Revision ID: d4f6a1b2c3e4
Revises: c8d3e5f7a901
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

revision: str = "d4f6a1b2c3e4"
down_revision: Union[str, None] = "c8d3e5f7a901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class MigrationUUID(sa.TypeDecorator):
    impl = sa.String
    cache_ok = True
    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(PostgreSQLUUID(as_uuid=True) if dialect.name == "postgresql" else sa.String(36))


def _enum(name, values):
    return sa.Enum(*values, name=name, native_enum=True)


_PARENT_UNIQUENESS = (
    (
        "recommendations",
        "uq_recommendations_id_org",
        ["id", "organization_id"],
    ),
    (
        "recommendations",
        "uq_recommendations_id_device_org",
        ["id", "device_id", "organization_id"],
    ),
    (
        "root_cause_analyses",
        "uq_root_cause_analyses_id_organization",
        ["id", "organization_id"],
    ),
    (
        "root_cause_findings",
        "uq_root_cause_findings_id_organization",
        ["id", "organization_id"],
    ),
)


def _create_parent_uniqueness(bind) -> None:
    """Create parent keys before Phase 1J composite foreign keys."""
    if bind.dialect.name == "sqlite":
        for table_name, constraint_name, columns in _PARENT_UNIQUENESS:
            with op.batch_alter_table(table_name) as batch:
                batch.create_unique_constraint(constraint_name, columns)
        return
    for table_name, constraint_name, columns in _PARENT_UNIQUENESS:
        op.create_unique_constraint(constraint_name, table_name, columns)


def _drop_parent_uniqueness(bind) -> None:
    if bind.dialect.name == "sqlite":
        for table_name, constraint_name, _columns in reversed(_PARENT_UNIQUENESS):
            with op.batch_alter_table(table_name) as batch:
                batch.drop_constraint(constraint_name, type_="unique")
        return
    for table_name, constraint_name, _columns in reversed(_PARENT_UNIQUENESS):
        op.drop_constraint(constraint_name, table_name, type_="unique")


def upgrade() -> None:
    bind = op.get_bind()
    _create_parent_uniqueness(bind)
    uid = MigrationUUID()
    plan_status = _enum("remediation_plan_status", ["draft", "pending_approval", "approved", "rejected", "queued", "executing", "succeeded", "failed", "cancelled", "verification_required", "verified"])
    action_status = _enum("remediation_action_status", ["pending", "ready", "executing", "succeeded", "failed", "skipped", "cancelled"])
    verification_status = _enum("remediation_verification_status", ["pending", "passed", "failed", "inconclusive"])
    op.create_table(
        "remediation_plans",
        sa.Column("id", uid, primary_key=True),
        sa.Column("organization_id", uid, nullable=False),
        sa.Column("device_id", uid, nullable=False),
        sa.Column("recommendation_id", uid),
        sa.Column("root_cause_finding_id", uid),
        sa.Column("created_by_user_id", uid),
        sa.Column("approved_by_user_id", uid),
        sa.Column("status", plan_status, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("plan_hash", sa.String(64), nullable=False),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("executed_at", sa.DateTime(timezone=True)),
        sa.Column("verification_status", verification_status, nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id", "organization_id"], ["devices.id", "devices.organization_id"], name="fk_remediation_plans_device_org"),
        sa.ForeignKeyConstraint(["recommendation_id", "device_id", "organization_id"], ["recommendations.id", "recommendations.device_id", "recommendations.organization_id"], name="fk_remediation_plans_recommendation_org", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["root_cause_finding_id", "device_id", "organization_id"], ["root_cause_findings.id", "root_cause_findings.device_id", "root_cause_findings.organization_id"], name="fk_remediation_plans_finding_org", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("id", "organization_id", name="uq_remediation_plans_id_org"),
        sa.UniqueConstraint("id", "device_id", "organization_id", name="uq_remediation_plans_id_device_org"),
        sa.UniqueConstraint("organization_id", "recommendation_id", name="uq_remediation_plans_org_recommendation"),
    )
    op.create_index("ix_remediation_plans_org_status", "remediation_plans", ["organization_id", "status"])
    op.create_index("ix_remediation_plans_plan_hash", "remediation_plans", ["plan_hash"])
    op.create_table(
        "remediation_actions",
        sa.Column("id", uid, primary_key=True),
        sa.Column("plan_id", uid, nullable=False),
        sa.Column("organization_id", uid, nullable=False),
        sa.Column("device_id", uid, nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("action_key", sa.String(100), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("status", action_status, nullable=False, server_default="pending"),
        sa.Column("result", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id", "device_id", "organization_id"], ["remediation_plans.id", "remediation_plans.device_id", "remediation_plans.organization_id"], name="fk_remediation_actions_plan_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id", "organization_id"], ["devices.id", "devices.organization_id"]),
        sa.UniqueConstraint("plan_id", "sequence", name="uq_remediation_actions_plan_sequence"),
    )
    op.create_index("ix_remediation_actions_plan_id", "remediation_actions", ["plan_id"])
    op.create_table(
        "remediation_verifications",
        sa.Column("id", uid, primary_key=True),
        sa.Column("plan_id", uid, nullable=False),
        sa.Column("organization_id", uid, nullable=False),
        sa.Column("device_id", uid, nullable=False),
        sa.Column("check_key", sa.String(100), nullable=False),
        sa.Column("status", verification_status, nullable=False, server_default="pending"),
        sa.Column("observed", sa.JSON()),
        sa.Column("details", sa.Text()),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["plan_id", "device_id", "organization_id"], ["remediation_plans.id", "remediation_plans.device_id", "remediation_plans.organization_id"], name="fk_remediation_verifications_plan_org", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["device_id", "organization_id"], ["devices.id", "devices.organization_id"]),
    )
    op.create_index("ix_remediation_verifications_plan_id", "remediation_verifications", ["plan_id"])


def downgrade() -> None:
    op.drop_table("remediation_verifications")
    op.drop_table("remediation_actions")
    op.drop_table("remediation_plans")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for name in ("remediation_action_status", "remediation_plan_status", "remediation_verification_status"):
            sa.Enum(name=name).drop(bind, checkfirst=True)
    _drop_parent_uniqueness(bind)
