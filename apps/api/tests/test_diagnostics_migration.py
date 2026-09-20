import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from app.config import get_settings


def _alembic_config() -> Config:
    return Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))


def test_phase_1g_migration_backfills_existing_diagnostic_rows(
    tmp_path, monkeypatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config()

    try:
        command.upgrade(config, "8d2e4f6a1b90")
        engine = create_engine(database_url)
        organization_id = "00000000-0000-0000-0000-000000000001"
        device_id = "00000000-0000-0000-0000-000000000002"
        run_id = "00000000-0000-0000-0000-000000000003"
        result_id = "00000000-0000-0000-0000-000000000004"
        with engine.begin() as connection:
            connection.execute(text(
                "INSERT INTO organizations (id, name, status) "
                "VALUES (:id, 'Migration test', 'ACTIVE')"
            ), {"id": organization_id})
            connection.execute(text(
                "INSERT INTO devices "
                "(id, organization_id, hostname, device_type, operating_system, status) "
                "VALUES (:id, :organization_id, 'migration-device', 'server', 'Linux', 'ACTIVE')"
            ), {"id": device_id, "organization_id": organization_id})
            connection.execute(text(
                "INSERT INTO diagnostic_runs "
                "(id, organization_id, device_id, diagnostic_type, status) "
                "VALUES (:id, :organization_id, :device_id, 'connectivity', 'PENDING')"
            ), {
                "id": run_id,
                "organization_id": organization_id,
                "device_id": device_id,
            })
            connection.execute(text(
                "INSERT INTO diagnostic_results "
                "(id, diagnostic_run_id, check_identifier, status, severity) "
                "VALUES (:id, :run_id, '', 'PASS', 'INFO')"
            ), {"id": result_id, "run_id": run_id})

        command.upgrade(config, "head")
        inspector = inspect(engine)
        run_fks = {
            tuple(foreign_key["constrained_columns"])
            for foreign_key in inspector.get_foreign_keys("diagnostic_runs")
        }
        result_fks = {
            tuple(foreign_key["constrained_columns"])
            for foreign_key in inspector.get_foreign_keys("diagnostic_results")
        }
        with engine.connect() as connection:
            result = connection.execute(text(
                "SELECT organization_id, device_id, title, checked_at, check_type "
                "FROM diagnostic_results WHERE id = :id"
            ), {"id": result_id}).one()
        assert ("created_by_user_id",) in run_fks
        assert ("organization_id",) in result_fks
        assert ("device_id",) in result_fks
        assert result.organization_id == organization_id
        assert result.device_id == device_id
        assert result.title == "Diagnostic result"
        assert result.checked_at is not None
        assert result.check_type == "CONNECTIVITY"

        command.downgrade(config, "8d2e4f6a1b90")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            assert connection.execute(text(
                "SELECT COUNT(*) FROM diagnostic_results WHERE id = :id"
            ), {"id": result_id}).scalar_one() == 1
        engine.dispose()
    finally:
        get_settings.cache_clear()


def test_phase_1g_migration_backfill_qualifies_result_timestamp() -> None:
    migration = Path(__file__).resolve().parents[3] / (
        "database/migrations/versions/"
        "9e4f7a1c2b30_add_diagnostics_foundation.py"
    )
    source = migration.read_text(encoding="utf-8")
    assert "COALESCE(diagnostic_results.created_at, CURRENT_TIMESTAMP)" in source


@pytest.mark.postgresql
def test_phase_1g_postgresql_enum_upgrade_and_downgrade(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url or not database_url.lower().startswith("postgresql"):
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config()
    engine = create_engine(database_url)
    expected_original = ["PENDING", "RUNNING", "COMPLETED", "FAILED"]
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "8d2e4f6a1b90")
        command.upgrade(config, "head")
        with engine.connect() as connection:
            values = connection.execute(text(
                "SELECT enumlabel FROM pg_enum "
                "WHERE enumtypid = 'diagnostic_run_status'::regtype "
                "ORDER BY enumsortorder"
            )).scalars().all()
            constraints = {
                row[0] for row in connection.execute(text(
                    "SELECT conname FROM pg_constraint "
                    "WHERE conrelid = 'diagnostic_runs'::regclass"
                )).all()
            }
        assert values == expected_original + ["CANCELLED"]
        assert "ck_diagnostic_runs_terminal_timestamps" in constraints

        command.downgrade(config, "8d2e4f6a1b90")
        with engine.connect() as connection:
            values = connection.execute(text(
                "SELECT enumlabel FROM pg_enum "
                "WHERE enumtypid = 'diagnostic_run_status'::regtype "
                "ORDER BY enumsortorder"
            )).scalars().all()
        assert values == expected_original
        command.upgrade(config, "head")
    finally:
        engine.dispose()
        get_settings.cache_clear()
