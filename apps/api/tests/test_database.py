import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.models import Base, Device, DeviceStatus, Organization, Role, User, UserStatus


def test_sqlite_schema_and_relationships() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        org = Organization(name="Example")
        user = User(email="admin@example.test", display_name="Admin", organization=org, status=UserStatus.ACTIVE)
        role = Role(name="operator", organization=org)
        user.roles.append(role)
        device = Device(
            hostname="pc-01",
            device_type="workstation",
            operating_system="Windows",
            organization=org,
            last_seen_at=datetime.now(timezone.utc),
        )
        session.add_all([org, user, role, device])
        session.commit()
        assert user.organization.name == "Example"
        assert user.roles[0].name == "operator"
        assert device.status is DeviceStatus.ACTIVE
        assert isinstance(device.id, uuid.UUID)
        assert org.created_at is not None
        assert org.updated_at is not None
    assert "audit_events" in inspect(engine).get_table_names()


def test_constraints_are_declared() -> None:
    constraints = {constraint.name for constraint in User.__table__.constraints}
    assert "uq_users_org_email" in constraints
    assert "uq_roles_org_name" in {c.name for c in Role.__table__.constraints}


def test_scoped_unique_constraints_are_enforced() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    with Session() as session:
        org = Organization(name="Example")
        session.add_all(
            [
                org,
                User(email="same@example.test", display_name="First", organization=org),
                User(email="same@example.test", display_name="Second", organization=org),
            ]
        )
        with pytest.raises(IntegrityError):
            session.commit()
