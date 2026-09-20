"""add password hashes to users

Revision ID: 2f5d7c8e9a10
Revises: 1a8fd5c3debf
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


revision: str = "2f5d7c8e9a10"
down_revision: Union[str, None] = "1a8fd5c3debf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.create_table(
        "bootstrap_state",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("organization_id", MigrationUUID(), nullable=False),
        sa.Column("user_id", MigrationUUID(), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_bootstrap_state_singleton"),
    )


def downgrade() -> None:
    op.drop_table("bootstrap_state")
    op.drop_column("users", "password_hash")
