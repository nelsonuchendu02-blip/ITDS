"""add Phase 1K incident lifecycle fields.

Revision ID: f6a1b2c3d4e5
Revises: e5f7a9b1c3d5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

revision: str = "f6a1b2c3d4e5"
down_revision: Union[str, None] = "e5f7a9b1c3d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


class MigrationUUID(sa.TypeDecorator):
    impl = sa.String
    cache_ok = True

    def load_dialect_impl(self, dialect):
        return dialect.type_descriptor(
            PostgreSQLUUID(as_uuid=True) if dialect.name == "postgresql" else sa.String(36)
        )


def upgrade() -> None:
    uid = MigrationUUID()
    columns = [
        sa.Column("created_by_user_id", uid, nullable=True),
        sa.Column("resolved_by_user_id", uid, nullable=True),
        sa.Column("closed_by_user_id", uid, nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_summary", sa.Text(), nullable=True),
        sa.Column("last_escalated_at", sa.DateTime(timezone=True), nullable=True),
    ]
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("incidents") as batch:
            for column in columns:
                batch.add_column(column)
            batch.create_foreign_key("fk_incidents_created_by_user_org", "users",
                                     ["created_by_user_id", "organization_id"], ["id", "organization_id"])
            batch.create_foreign_key("fk_incidents_resolved_by_user_org", "users",
                                     ["resolved_by_user_id", "organization_id"], ["id", "organization_id"])
            batch.create_foreign_key("fk_incidents_closed_by_user_org", "users",
                                     ["closed_by_user_id", "organization_id"], ["id", "organization_id"])
        return
    for column in columns:
        op.add_column("incidents", column)
    op.create_foreign_key("fk_incidents_created_by_user_org", "incidents", "users",
                          ["created_by_user_id", "organization_id"], ["id", "organization_id"])
    op.create_foreign_key("fk_incidents_resolved_by_user_org", "incidents", "users",
                          ["resolved_by_user_id", "organization_id"], ["id", "organization_id"])
    op.create_foreign_key("fk_incidents_closed_by_user_org", "incidents", "users",
                          ["closed_by_user_id", "organization_id"], ["id", "organization_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("incidents") as batch:
            batch.drop_constraint("fk_incidents_closed_by_user_org", type_="foreignkey")
            batch.drop_constraint("fk_incidents_resolved_by_user_org", type_="foreignkey")
            batch.drop_constraint("fk_incidents_created_by_user_org", type_="foreignkey")
            for name in (
                "last_escalated_at", "resolution_summary", "closed_at",
                "closed_by_user_id", "resolved_by_user_id", "created_by_user_id",
            ):
                batch.drop_column(name)
        return
    op.drop_constraint("fk_incidents_closed_by_user_org", "incidents", type_="foreignkey")
    op.drop_constraint("fk_incidents_resolved_by_user_org", "incidents", type_="foreignkey")
    op.drop_constraint("fk_incidents_created_by_user_org", "incidents", type_="foreignkey")
    for name in (
        "last_escalated_at", "resolution_summary", "closed_at",
        "closed_by_user_id", "resolved_by_user_id", "created_by_user_id",
    ):
        op.drop_column("incidents", name)
