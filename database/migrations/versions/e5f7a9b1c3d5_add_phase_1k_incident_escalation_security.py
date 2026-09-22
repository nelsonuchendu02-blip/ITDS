"""add Phase 1K secure incident and escalation foundation.

Revision ID: e5f7a9b1c3d5
Revises: d4f6a1b2c3e4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID

revision: str = "e5f7a9b1c3d5"
down_revision: Union[str, None] = "d4f6a1b2c3e4"
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
    bind = op.get_bind()
    uid = MigrationUUID()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("users") as batch:
            batch.create_unique_constraint("uq_users_id_organization", ["id", "organization_id"])
        with op.batch_alter_table("incidents") as batch:
            batch.create_unique_constraint("uq_incidents_id_organization", ["id", "organization_id"])
            batch.create_foreign_key("fk_incidents_device_org", "devices",
                                     ["device_id", "organization_id"], ["id", "organization_id"])
            batch.create_foreign_key("fk_incidents_assigned_user_org", "users",
                                     ["assigned_user_id", "organization_id"], ["id", "organization_id"])
        with op.batch_alter_table("escalations") as batch:
            batch.create_foreign_key("fk_escalations_incident_org", "incidents",
                                     ["incident_id", "organization_id"], ["id", "organization_id"],
                                     ondelete="CASCADE")
            batch.create_unique_constraint("uq_escalations_incident_level",
                                           ["organization_id", "incident_id", "escalation_level"])
        return
    op.create_unique_constraint("uq_users_id_organization", "users", ["id", "organization_id"])
    op.create_unique_constraint("uq_incidents_id_organization", "incidents", ["id", "organization_id"])
    op.create_foreign_key("fk_incidents_device_org", "incidents", "devices",
                          ["device_id", "organization_id"], ["id", "organization_id"])
    op.create_foreign_key("fk_incidents_assigned_user_org", "incidents", "users",
                          ["assigned_user_id", "organization_id"], ["id", "organization_id"])
    op.create_foreign_key("fk_escalations_incident_org", "escalations", "incidents",
                          ["incident_id", "organization_id"], ["id", "organization_id"], ondelete="CASCADE")
    op.create_unique_constraint("uq_escalations_incident_level", "escalations",
                                ["organization_id", "incident_id", "escalation_level"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("escalations") as batch:
            batch.drop_constraint("uq_escalations_incident_level", type_="unique")
            batch.drop_constraint("fk_escalations_incident_org", type_="foreignkey")
        with op.batch_alter_table("incidents") as batch:
            batch.drop_constraint("fk_incidents_assigned_user_org", type_="foreignkey")
            batch.drop_constraint("fk_incidents_device_org", type_="foreignkey")
            batch.drop_constraint("uq_incidents_id_organization", type_="unique")
        with op.batch_alter_table("users") as batch:
            batch.drop_constraint("uq_users_id_organization", type_="unique")
        return
    op.drop_constraint("uq_escalations_incident_level", "escalations", type_="unique")
    op.drop_constraint("fk_escalations_incident_org", "escalations", type_="foreignkey")
    op.drop_constraint("fk_incidents_assigned_user_org", "incidents", type_="foreignkey")
    op.drop_constraint("fk_incidents_device_org", "incidents", type_="foreignkey")
    op.drop_constraint("uq_incidents_id_organization", "incidents", type_="unique")
    op.drop_constraint("uq_users_id_organization", "users", type_="unique")
