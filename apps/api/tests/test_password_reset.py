from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.exceptions import SecurityError
from app.models import (
    AuditEvent,
    Base,
    Organization,
    PasswordResetToken,
    User,
    UserSession,
)
from app.security.passwords import hash_password, verify_password
from app.services.password_reset import PasswordResetService


class FakePasswordResetDelivery:
    def __init__(self) -> None:
        self.email: str | None = None
        self.reset_token: str | None = None

    def deliver(self, *, email: str, reset_token: str) -> None:
        self.email = email
        self.reset_token = reset_token


@pytest.fixture
def reset_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        yield session

    Base.metadata.drop_all(engine)
    engine.dispose()


def create_user(
    session,
    *,
    email: str = "user@example.test",
    password: str = "old-secret-password",
) -> User:
    organization = Organization(name="Example")
    user = User(
        organization=organization,
        email=email,
        display_name="Test User",
        password_hash=hash_password(password),
    )
    session.add_all([organization, user])
    session.commit()
    return user


def test_request_reset_creates_token_and_revokes_previous_tokens(
    reset_session,
) -> None:
    user = create_user(reset_session)
    delivery = FakePasswordResetDelivery()
    service = PasswordResetService(delivery=delivery)

    service.request_reset(reset_session, email=user.email)
    first_token = delivery.reset_token
    assert first_token is not None
    assert "." in first_token

    first_record = reset_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id
        )
    )
    assert first_record is not None
    assert first_record.used_at is None
    assert first_record.revoked_at is None
    assert first_record.token_hash != first_token

    service.request_reset(reset_session, email=user.email)
    second_token = delivery.reset_token
    assert second_token is not None
    assert second_token != first_token

    records = reset_session.scalars(
        select(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id)
        .order_by(PasswordResetToken.created_at)
    ).all()

    assert len(records) == 2
    assert records[0].revoked_at is not None
    assert records[1].revoked_at is None


def test_request_reset_is_generic_for_unknown_email(reset_session) -> None:
    service = PasswordResetService()

    result = service.request_reset(
        reset_session,
        email="missing@example.test",
    )

    assert result is None
    assert reset_session.scalar(select(PasswordResetToken.id)) is None


def test_request_reset_normalizes_email(reset_session) -> None:
    user = create_user(reset_session)
    delivery = FakePasswordResetDelivery()
    service = PasswordResetService(delivery=delivery)

    service.request_reset(
        reset_session,
        email="  USER@EXAMPLE.TEST  ",
    )

    assert delivery.reset_token is not None
    assert delivery.email == user.email

    record = reset_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id
        )
    )
    assert record is not None


def test_reset_password_changes_password_and_revokes_sessions(
    reset_session,
) -> None:
    user = create_user(reset_session)

    first_session = UserSession(
        user_id=user.id,
        token_id=uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    second_session = UserSession(
        user_id=user.id,
        token_id=uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    reset_session.add_all([first_session, second_session])
    reset_session.commit()

    delivery = FakePasswordResetDelivery()
    service = PasswordResetService(delivery=delivery)
    service.request_reset(reset_session, email=user.email)

    reset_token = delivery.reset_token
    assert reset_token is not None

    service.reset_password(
        reset_session,
        token=reset_token,
        new_password="new-secret-password",
    )

    reset_session.refresh(user)
    assert verify_password("new-secret-password", user.password_hash)
    assert not verify_password("old-secret-password", user.password_hash)

    sessions = reset_session.scalars(
        select(UserSession).where(UserSession.user_id == user.id)
    ).all()
    assert len(sessions) == 2
    assert all(item.revoked_at is not None for item in sessions)

    token_record = reset_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id
        )
    )
    assert token_record is not None
    assert token_record.used_at is not None

    event = reset_session.scalar(
        select(AuditEvent)
        .where(
            AuditEvent.actor_user_id.is_(None),
            AuditEvent.action == "reset_password",
            AuditEvent.result == "success",
        )
        .order_by(AuditEvent.created_at.desc())
    )
    assert event is not None


def test_reset_password_rejects_token_reuse(reset_session) -> None:
    user = create_user(reset_session)
    delivery = FakePasswordResetDelivery()
    service = PasswordResetService(delivery=delivery)
    service.request_reset(reset_session, email=user.email)

    reset_token = delivery.reset_token
    assert reset_token is not None

    service.reset_password(
        reset_session,
        token=reset_token,
        new_password="new-secret-password",
    )

    with pytest.raises(
        SecurityError,
        match="The password reset request is invalid or has expired",
    ):
        service.reset_password(
            reset_session,
            token=reset_token,
            new_password="another-secret-password",
        )


def test_reset_password_rejects_invalid_token(reset_session) -> None:
    service = PasswordResetService()

    with pytest.raises(
        SecurityError,
        match="The password reset request is invalid or has expired",
    ):
        service.reset_password(
            reset_session,
            token="invalid-token",
            new_password="new-secret-password",
        )


def test_reset_password_rejects_expired_token(reset_session) -> None:
    user = create_user(reset_session)
    delivery = FakePasswordResetDelivery()
    service = PasswordResetService(delivery=delivery)

    service.request_reset(
        reset_session,
        email=user.email,
        settings=Settings(password_reset_token_ttl_minutes=1),
    )

    reset_token = delivery.reset_token
    assert reset_token is not None

    record = reset_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id
        )
    )
    assert record is not None
    record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    reset_session.commit()

    with pytest.raises(
        SecurityError,
        match="The password reset request is invalid or has expired",
    ):
        service.reset_password(
            reset_session,
            token=reset_token,
            new_password="new-secret-password",
        )

    reset_session.refresh(user)
    assert verify_password("old-secret-password", user.password_hash)


def test_reset_password_rejects_revoked_token(reset_session) -> None:
    user = create_user(reset_session)
    delivery = FakePasswordResetDelivery()
    service = PasswordResetService(delivery=delivery)
    service.request_reset(reset_session, email=user.email)

    reset_token = delivery.reset_token
    assert reset_token is not None

    record = reset_session.scalar(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id
        )
    )
    assert record is not None
    record.revoked_at = datetime.now(timezone.utc)
    reset_session.commit()

    with pytest.raises(
        SecurityError,
        match="The password reset request is invalid or has expired",
    ):
        service.reset_password(
            reset_session,
            token=reset_token,
            new_password="new-secret-password",
        )

    reset_session.refresh(user)
    assert verify_password("old-secret-password", user.password_hash)


def test_reset_password_rejects_tampered_token(reset_session) -> None:
    user = create_user(reset_session)
    delivery = FakePasswordResetDelivery()
    service = PasswordResetService(delivery=delivery)
    service.request_reset(reset_session, email=user.email)

    reset_token = delivery.reset_token
    assert reset_token is not None

    prefix, secret = reset_token.split(".", 1)
    tampered_token = f"{prefix}.{secret}tampered"

    with pytest.raises(
        SecurityError,
        match="The password reset request is invalid or has expired",
    ):
        service.reset_password(
            reset_session,
            token=tampered_token,
            new_password="new-secret-password",
        )

    reset_session.refresh(user)
    assert verify_password("old-secret-password", user.password_hash)
