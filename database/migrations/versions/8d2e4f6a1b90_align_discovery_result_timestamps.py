"""align discovery result timestamps

Revision ID: 8d2e4f6a1b90
Revises: 7c1e4f6a2b90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8d2e4f6a1b90"
down_revision: Union[str, None] = "7c1e4f6a2b90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "discovery_results",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )
    op.add_column(
        "discovery_results",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("discovery_results", "updated_at")
    op.drop_column("discovery_results", "created_at")
