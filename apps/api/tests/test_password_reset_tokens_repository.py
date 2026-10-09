from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models import Base, PasswordResetToken
from app.repositories.password_reset_tokens import PasswordResetTokenRepository


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def setup_function() -> None:
    Base.metadata.create_all(engine)


def teardown_function() -> None:
    Base.metadata.drop_all(engine)


def create_token(
    *,
    user_id=None,
    prefix: str = "test-prefix",
    used_at=None,
    revoked_at=None,
) -> PasswordResetToken:
    return PasswordResetToken(
        id=uuid4(),
        user_id=user_id or uuid4(),
        token_prefix=prefix,
        token_hash="test-hash",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        used_at=used_at,
        revoked_at=revoked_at,
    )


def assert_same_instant(
    actual: datetime | None,
    expected: datetime,
) -> None:
    assert actual is not None

    if actual.tzinfo is None:
        actual = actual.replace(tzinfo=timezone.utc)

    assert actual == expected

def test_create_and_get_by_prefix() -> None:
    repository = PasswordResetTokenRepository()

    with TestingSessionLocal() as session:
        token = create_token(prefix="lookup-prefix")

        repository.create(session, token)
        session.commit()

        found = repository.get_by_prefix(
            session,
            token_prefix="lookup-prefix",
        )

        assert found is not None
        assert found.id == token.id
        assert found.token_prefix == "lookup-prefix"


def test_get_by_prefix_returns_none_for_unknown_prefix() -> None:
    repository = PasswordResetTokenRepository()

    with TestingSessionLocal() as session:
        found = repository.get_by_prefix(
            session,
            token_prefix="does-not-exist",
        )

        assert found is None


def test_revoke_active_for_user() -> None:
    repository = PasswordResetTokenRepository()
    user_id = uuid4()
    revoked_at = datetime.now(timezone.utc)

    with TestingSessionLocal() as session:
        first = create_token(
            user_id=user_id,
            prefix="first-prefix",
        )
        second = create_token(
            user_id=user_id,
            prefix="second-prefix",
        )

        repository.create(session, first)
        repository.create(session, second)
        session.commit()

        count = repository.revoke_active_for_user(
            session,
            user_id=user_id,
            revoked_at=revoked_at,
        )
        session.commit()

        assert count == 2
        assert_same_instant(first.revoked_at, revoked_at)
        assert_same_instant(second.revoked_at, revoked_at)


def test_revoke_active_for_user_does_not_revoke_used_tokens() -> None:
    repository = PasswordResetTokenRepository()
    user_id = uuid4()
    used_at = datetime.now(timezone.utc)
    revoked_at = datetime.now(timezone.utc)

    with TestingSessionLocal() as session:
        active = create_token(
            user_id=user_id,
            prefix="active-prefix",
        )
        used = create_token(
            user_id=user_id,
            prefix="used-prefix",
            used_at=used_at,
        )

        repository.create(session, active)
        repository.create(session, used)
        session.commit()

        count = repository.revoke_active_for_user(
            session,
            user_id=user_id,
            revoked_at=revoked_at,
        )
        session.commit()

        assert count == 1
        assert_same_instant(active.revoked_at, revoked_at)
        assert used.revoked_at is None
        assert_same_instant(used.used_at, used_at)


def test_revoke_active_for_user_does_not_revoke_already_revoked_tokens() -> None:
    repository = PasswordResetTokenRepository()
    user_id = uuid4()
    previous_revocation = datetime.now(timezone.utc)
    revoked_at = previous_revocation + timedelta(seconds=1)

    with TestingSessionLocal() as session:
        active = create_token(
            user_id=user_id,
            prefix="active-prefix",
        )
        already_revoked = create_token(
            user_id=user_id,
            prefix="revoked-prefix",
            revoked_at=previous_revocation,
        )

        repository.create(session, active)
        repository.create(session, already_revoked)
        session.commit()

        count = repository.revoke_active_for_user(
            session,
            user_id=user_id,
            revoked_at=revoked_at,
        )
        session.commit()

        assert count == 1
        assert_same_instant(active.revoked_at, revoked_at)
        assert_same_instant(already_revoked.revoked_at, previous_revocation)


def test_mark_used() -> None:
    repository = PasswordResetTokenRepository()
    used_at = datetime.now(timezone.utc)

    with TestingSessionLocal() as session:
        token = create_token(prefix="use-prefix")

        repository.create(session, token)
        session.commit()

        repository.mark_used(
            session,
            token=token,
            used_at=used_at,
        )
        session.commit()

        assert_same_instant(token.used_at, used_at)