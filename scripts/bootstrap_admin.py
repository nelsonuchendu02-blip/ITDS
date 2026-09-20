"""Explicit operator-run bootstrap for the first ITDS administrator."""

import argparse
import getpass
import sys
from pathlib import Path

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.config import get_settings
from app.db import get_session_factory
from app.models import BootstrapState, Organization, Role, User
from app.permissions import BASELINE_ROLES
from app.security.passwords import hash_password
from app.services.audit import record_security_event


def bootstrap(email: str, display_name: str, organization_name: str) -> None:
    password = getpass.getpass("Initial administrator password: ")
    confirmation = getpass.getpass("Confirm administrator password: ")
    if password != confirmation or not password:
        raise SystemExit("Passwords do not match or are empty.")
    session = get_session_factory(get_settings())()
    try:
        organization = Organization(name=organization_name)
        session.add(organization)
        session.flush()
        roles = {name: Role(name=name, organization=organization) for name in BASELINE_ROLES}
        session.add_all(roles.values())
        user = User(
            organization=organization,
            email=email.strip().lower(),
            display_name=display_name,
            password_hash=hash_password(password),
        )
        user.roles.append(roles["platform_admin"])
        session.add(user)
        session.flush()
        session.add(
            BootstrapState(
                id=1,
                completed_at=datetime.now(timezone.utc),
                organization_id=organization.id,
                user_id=user.id,
            )
        )
        record_security_event(
            session,
            event_type="bootstrap",
            organization_id=organization.id,
            actor_user_id=user.id,
            action="create_initial_administrator",
            result="success",
            metadata={"role": "platform_admin"},
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            raise SystemExit("Bootstrap has already been completed.") from None
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--organization", required=True)
    args = parser.parse_args()
    bootstrap(args.email, args.display_name, args.organization)
