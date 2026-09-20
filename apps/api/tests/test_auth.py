from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.config import Settings, validate_authentication_configuration
from app.db import get_db
from app.exceptions import SecurityError
from app.main import app
from app.models import AuditEvent, Base, BootstrapState, Organization, Role, User, UserStatus
from app.permissions import ROLE_PERMISSIONS
from app.api.dependencies.auth import ensure_organization_scope
from app.security.passwords import hash_password, verify_password
from app.security.tokens import create_access_token, decode_access_token
from app.services.auth import AuthenticationService


@pytest.fixture
def auth_session(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setenv("JWT_SECRET", "test-secret-" + "x" * 32)
    monkeypatch.setenv("JWT_ISSUER", "itds-test")
    monkeypatch.setenv("JWT_AUDIENCE", "itds-test-client")
    get_settings.cache_clear()
    with Session() as session:
        yield session
    get_settings.cache_clear()


def test_passwords_are_hashed_and_verified() -> None:
    password = "correct horse battery staple"
    password_hash = hash_password(password)
    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("wrong password", password_hash)


def test_authentication_token_and_current_user(auth_session, monkeypatch: pytest.MonkeyPatch) -> None:
    organization = Organization(name="Example")
    role = Role(name="viewer", organization=organization)
    user = User(
        organization=organization,
        email="admin@example.test",
        display_name="Admin",
        password_hash=hash_password("secret-password"),
    )
    user.roles.append(role)
    auth_session.add_all([organization, role, user])
    auth_session.commit()

    def override_get_db():
        yield auth_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/auth/token",
            data={"username": "ADMIN@example.test", "password": "secret-password"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]
        assert response.json()["token_type"] == "bearer"

        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        payload = me.json()
        assert payload["email"] == "admin@example.test"
        assert payload["roles"] == ["viewer"]
        assert "password_hash" not in payload
        assert "devices:read" in payload["permissions"]
    finally:
        app.dependency_overrides.clear()

    event = auth_session.scalar(
        select(AuditEvent).where(AuditEvent.event_type == "authentication")
    )
    assert event is not None
    assert event.event_metadata is None


def test_authentication_failures_are_generic(auth_session) -> None:
    organization = Organization(name="Example")
    user = User(
        organization=organization,
        email="admin@example.test",
        display_name="Admin",
        password_hash=hash_password("secret-password"),
    )
    auth_session.add(user)
    auth_session.commit()
    service = AuthenticationService()

    with pytest.raises(SecurityError) as known:
        service.authenticate(auth_session, email="admin@example.test", password="wrong")
    with pytest.raises(SecurityError) as unknown:
        service.authenticate(auth_session, email="missing@example.test", password="wrong")
    assert str(known.value) == str(unknown.value) == "Invalid email or password"
    assert known.value.code == unknown.value.code == "invalid_credentials"


def test_ambiguous_cross_organization_login_is_rejected(auth_session) -> None:
    first = Organization(name="First")
    second = Organization(name="Second")
    auth_session.add_all(
        [
            User(
                organization=first,
                email="shared@example.test",
                display_name="First User",
                password_hash=hash_password("secret-password"),
            ),
            User(
                organization=second,
                email="shared@example.test",
                display_name="Second User",
                password_hash=hash_password("secret-password"),
            ),
        ]
    )
    auth_session.commit()
    with pytest.raises(SecurityError, match="Invalid email or password"):
        AuthenticationService().authenticate(
            auth_session, email="shared@example.test", password="secret-password"
        )


def test_malformed_password_hash_follows_generic_failure(auth_session) -> None:
    organization = Organization(name="Example")
    user = User(
        organization=organization,
        email="malformed@example.test",
        display_name="Malformed",
        password_hash="not-a-valid-pwdlib-hash",
    )
    auth_session.add(user)
    auth_session.commit()
    with pytest.raises(SecurityError, match="Invalid email or password"):
        AuthenticationService().authenticate(
            auth_session, email=user.email, password="secret-password"
        )


def test_inactive_user_is_rejected(auth_session) -> None:
    organization = Organization(name="Example")
    user = User(
        organization=organization,
        email="inactive@example.test",
        display_name="Inactive",
        password_hash=hash_password("secret-password"),
        status=UserStatus.INACTIVE,
    )
    auth_session.add(user)
    auth_session.commit()
    with pytest.raises(SecurityError, match="Invalid email or password"):
        AuthenticationService().authenticate(
            auth_session, email=user.email, password="secret-password"
        )


def test_jwt_claims_and_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", "test-secret-" + "x" * 32)
    monkeypatch.setenv("JWT_ISSUER", "itds-test")
    monkeypatch.setenv("JWT_AUDIENCE", "itds-test-client")
    get_settings.cache_clear()
    subject = uuid4()
    token = create_access_token(subject)
    assert decode_access_token(token) == subject
    claims = jwt.decode(
        token,
        "test-secret-" + "x" * 32,
        algorithms=["HS256"],
        audience="itds-test-client",
        issuer="itds-test",
    )
    assert set(claims) >= {"sub", "exp", "iat", "jti", "typ"}

    expired = jwt.encode(
        {
            "sub": str(subject),
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
            "iat": datetime.now(timezone.utc) - timedelta(minutes=2),
            "jti": str(uuid4()),
            "typ": "access",
            "iss": "itds-test",
            "aud": "itds-test-client",
        },
        "test-secret-" + "x" * 32,
        algorithm="HS256",
    )
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(expired)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(
            token,
            settings=get_settings().model_copy(update={"jwt_secret": "wrong-" + "x" * 40}),
        )
    wrong_algorithm = jwt.encode(
        {
            "sub": str(subject),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
            "typ": "access",
            "iss": "itds-test",
            "aud": "itds-test-client",
        },
        "test-secret-" + "x" * 48,
        algorithm="HS384",
    )
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(wrong_algorithm)
    get_settings.cache_clear()


def test_auth_endpoint_requires_authentication() -> None:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_get_db():
        with Session() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = TestClient(app).get("/api/v1/auth/me")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "authentication_required"


def test_baseline_roles_have_controlled_permissions() -> None:
    assert set(ROLE_PERMISSIONS) == {
        "platform_admin",
        "organization_admin",
        "it_support",
        "technician",
        "viewer",
    }
    assert ROLE_PERMISSIONS["platform_admin"] == {"*"}


def test_platform_admin_cannot_cross_organization_without_explicit_scope(auth_session) -> None:
    organization_a = Organization(name="A")
    organization_b = Organization(name="B")
    role = Role(name="platform_admin", organization=organization_a)
    user = User(
        organization=organization_a,
        email="admin@example.test",
        display_name="Admin",
        password_hash=hash_password("secret-password"),
    )
    user.roles.append(role)
    auth_session.add_all([organization_a, organization_b, user])
    auth_session.commit()
    with pytest.raises(SecurityError, match="Permission denied"):
        ensure_organization_scope(user, organization_b.id)
    ensure_organization_scope(user, organization_a.id)


def test_production_configuration_requires_jwt_secret() -> None:
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        validate_authentication_configuration(Settings(environment="production"))
    with pytest.raises(RuntimeError, match="JWT_ALGORITHM"):
        validate_authentication_configuration(
            Settings(environment="development", jwt_algorithm="HS384")
        )


def test_bootstrap_is_atomic_and_single_use(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.bootstrap_admin as bootstrap_module

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    monkeypatch.setattr(bootstrap_module, "get_session_factory", lambda _: Session)
    monkeypatch.setattr(
        bootstrap_module.getpass,
        "getpass",
        lambda _: "secret-password",
    )
    bootstrap_module.bootstrap("admin@example.test", "Admin", "Example")
    with Session() as session:
        assert session.scalar(select(BootstrapState).where(BootstrapState.id == 1)) is not None
    with pytest.raises(SystemExit, match="already been completed"):
        bootstrap_module.bootstrap("second@example.test", "Second", "Other")

    with Session() as session:
        session.query(User).delete()
        session.query(BootstrapState).delete()
        session.commit()
    monkeypatch.setattr(
        bootstrap_module,
        "record_security_event",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("audit failure")),
    )
    with pytest.raises(RuntimeError, match="audit failure"):
        bootstrap_module.bootstrap("failed@example.test", "Failed", "Failed")
    with Session() as session:
        assert session.scalar(select(User.id)) is None
        assert session.scalar(select(BootstrapState.id)) is None
