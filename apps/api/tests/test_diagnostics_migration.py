import os
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Device, DiagnosticCheckType, DiagnosticResult, DiagnosticResultSeverity,
    DiagnosticResultStatus, DiagnosticRun, DiagnosticRunStatus, Organization,
    RootCauseAnalysis, RootCauseAnalysisStatus, RootCauseFinding,
    RootCauseFindingConfidence, RootCauseFindingSeverity, RootCauseFindingStatus,
)


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


def test_phase_1h_sqlite_migration_lifecycle_and_schema(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'root-cause.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config()
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        columns = {column["name"] for column in inspect(engine).get_columns("root_cause_findings")}
        assert {
            "organization_id", "device_id", "diagnostic_result_id", "category",
            "status", "severity", "confidence", "explanation", "evidence",
        } <= columns
        command.downgrade(config, "9e4f7a1c2b30")
        assert "root_cause_findings" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
        assert "root_cause_analyses" in inspect(engine).get_table_names()
    finally:
        engine.dispose()
        get_settings.cache_clear()


def test_phase_1h_sqlite_rejects_cross_organization_combinations(tmp_path, monkeypatch) -> None:
    database_url = f"sqlite:///{tmp_path / 'root-cause-integrity.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config()
    engine = create_engine(database_url)
    try:
        command.upgrade(config, "head")
        org_a, org_b = str(uuid4()), str(uuid4())
        device_a, device_b = str(uuid4()), str(uuid4())
        run_a, run_b = str(uuid4()), str(uuid4())
        result_a, result_b = str(uuid4()), str(uuid4())
        analysis_a = str(uuid4())
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            for organization_id, name in ((org_a, "A"), (org_b, "B")):
                connection.execute(text(
                    "INSERT INTO organizations (id, name, status) VALUES (:id, :name, 'ACTIVE')"
                ), {"id": organization_id, "name": name})
            for device_id, organization_id, hostname in (
                (device_a, org_a, "a-device"), (device_b, org_b, "b-device")
            ):
                connection.execute(text(
                    "INSERT INTO devices "
                    "(id, organization_id, hostname, device_type, operating_system, status) "
                    "VALUES (:id, :organization_id, :hostname, 'server', 'Linux', 'ACTIVE')"
                ), {"id": device_id, "organization_id": organization_id, "hostname": hostname})
            for run_id, organization_id, device_id in (
                (run_a, org_a, device_a), (run_b, org_b, device_b)
            ):
                connection.execute(text(
                    "INSERT INTO diagnostic_runs "
                    "(id, organization_id, device_id, diagnostic_type, status) "
                    "VALUES (:id, :organization_id, :device_id, 'connectivity', 'COMPLETED')"
                ), {
                    "id": run_id, "organization_id": organization_id, "device_id": device_id,
                })
            for result_id, run_id, organization_id, device_id in (
                (result_a, run_a, org_a, device_a), (result_b, run_b, org_b, device_b)
            ):
                connection.execute(text(
                    "INSERT INTO diagnostic_results "
                    "(id, diagnostic_run_id, organization_id, device_id, check_identifier, "
                    "check_type, status, severity, title, checked_at) "
                    "VALUES (:id, :run_id, :organization_id, :device_id, 'check', "
                    "'CONNECTIVITY', 'FAIL', 'HIGH', 'Check', CURRENT_TIMESTAMP)"
                ), {
                    "id": result_id, "run_id": run_id, "organization_id": organization_id,
                    "device_id": device_id,
                })
            connection.execute(text(
                "INSERT INTO root_cause_analyses "
                "(id, organization_id, device_id, diagnostic_run_id, provider, status) "
                "VALUES (:id, :organization_id, :device_id, :run_id, 'deterministic', 'PENDING')"
            ), {
                "id": analysis_a, "organization_id": org_a, "device_id": device_a, "run_id": run_a,
            })

        invalid_analysis_values = (
            {"device_id": device_b, "diagnostic_run_id": run_a},
            {"device_id": device_a, "diagnostic_run_id": run_b},
        )
        for values in invalid_analysis_values:
            with pytest.raises(IntegrityError):
                with engine.begin() as connection:
                    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                    connection.execute(text(
                        "INSERT INTO root_cause_analyses "
                        "(id, organization_id, device_id, diagnostic_run_id, provider, status) "
                        "VALUES (:id, :organization_id, :device_id, :run_id, "
                        "'deterministic', 'PENDING')"
                    ), {
                        "id": str(uuid4()), "organization_id": org_a,
                        "device_id": values["device_id"], "run_id": values["diagnostic_run_id"],
                    })

        invalid_finding_values = (
            {"diagnostic_result_id": result_b, "device_id": device_a},
            {"diagnostic_result_id": result_a, "device_id": device_b},
        )
        for values in invalid_finding_values:
            with pytest.raises(IntegrityError):
                with engine.begin() as connection:
                    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                    connection.execute(text(
                        "INSERT INTO root_cause_findings "
                        "(id, analysis_id, organization_id, device_id, diagnostic_result_id, "
                        "rule_id, category, status, severity, confidence, title, summary, "
                        "explanation, evidence, fingerprint) "
                        "VALUES (:id, :analysis_id, :organization_id, :device_id, "
                        ":result_id, 'rule', 'CONNECTIVITY', 'IDENTIFIED', 'HIGH', 'HIGH', "
                        "'Finding', 'Summary', 'Explanation', '{}', :fingerprint)"
                    ), {
                        "id": str(uuid4()), "analysis_id": analysis_a, "organization_id": org_a,
                        "device_id": values["device_id"], "result_id": values["diagnostic_result_id"],
                        "fingerprint": str(uuid4()),
                    })
    finally:
        engine.dispose()
        get_settings.cache_clear()


@pytest.mark.postgresql
def test_phase_1h_postgresql_enum_and_schema_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    database_url = os.getenv("TEST_DATABASE_URL")
    if not database_url or not database_url.lower().startswith("postgresql"):
        pytest.skip("Set TEST_DATABASE_URL to an isolated PostgreSQL database")
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    config = _alembic_config()
    engine = create_engine(database_url)
    try:
        command.downgrade(config, "9e4f7a1c2b30")
        command.upgrade(config, "head")
        inspector = inspect(engine)
        finding_columns = {column["name"] for column in inspector.get_columns("root_cause_findings")}
        finding_fks = {
            tuple(foreign_key["constrained_columns"])
            for foreign_key in inspector.get_foreign_keys("root_cause_findings")
        }
        with engine.connect() as connection:
            status_values = connection.execute(text(
                "SELECT enumlabel FROM pg_enum "
                "WHERE enumtypid = 'root_cause_analysis_status'::regtype "
                "ORDER BY enumsortorder"
            )).scalars().all()
            finding_status_values = connection.execute(text(
                "SELECT enumlabel FROM pg_enum "
                "WHERE enumtypid = 'root_cause_finding_status'::regtype "
                "ORDER BY enumsortorder"
            )).scalars().all()
        assert {
            "organization_id", "device_id", "diagnostic_result_id", "category",
            "status", "severity", "confidence", "explanation", "evidence",
        } <= finding_columns
        assert {("organization_id",), ("device_id",), ("diagnostic_result_id",)} <= finding_fks
        assert status_values == ["PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED"]
        assert finding_status_values == ["IDENTIFIED", "LIKELY", "INSUFFICIENT_EVIDENCE"]

        organization = Organization(name="Phase 1H PostgreSQL")
        other_organization = Organization(name="Other Phase 1H PostgreSQL")
        device = Device(
            organization=organization, hostname="phase1h-device",
            device_type="server", operating_system="Linux",
        )
        other_device = Device(
            organization=other_organization, hostname="other-phase1h-device",
            device_type="server", operating_system="Linux",
        )
        with Session(engine) as session:
            session.add_all([organization, other_organization, device, other_device])
            session.flush()
            run = DiagnosticRun(
                organization_id=organization.id, device_id=device.id,
                diagnostic_type="connectivity", provider="simulated",
                status=DiagnosticRunStatus.COMPLETED,
                completed_at=datetime.now(timezone.utc),
            )
            other_run = DiagnosticRun(
                organization_id=other_organization.id, device_id=other_device.id,
                diagnostic_type="connectivity", provider="simulated",
                status=DiagnosticRunStatus.COMPLETED,
                completed_at=datetime.now(timezone.utc),
            )
            session.add_all([run, other_run])
            session.flush()
            result = DiagnosticResult(
                diagnostic_run_id=run.id, organization_id=organization.id,
                device_id=device.id, check_identifier="connectivity-check",
                check_type=DiagnosticCheckType.CONNECTIVITY,
                status=DiagnosticResultStatus.FAIL,
                severity=DiagnosticResultSeverity.HIGH, title="Connectivity failure",
                checked_at=datetime.now(timezone.utc),
            )
            other_result = DiagnosticResult(
                diagnostic_run_id=other_run.id, organization_id=other_organization.id,
                device_id=other_device.id, check_identifier="other-check",
                check_type=DiagnosticCheckType.CONNECTIVITY,
                status=DiagnosticResultStatus.FAIL,
                severity=DiagnosticResultSeverity.HIGH, title="Other failure",
                checked_at=datetime.now(timezone.utc),
            )
            session.add_all([result, other_result])
            session.flush()
            analysis = RootCauseAnalysis(
                organization_id=organization.id, device_id=device.id,
                diagnostic_run_id=run.id, initiated_by_user_id=None,
                provider="deterministic", status=RootCauseAnalysisStatus.PENDING,
            )
            session.add(analysis)
            session.flush()
            finding = RootCauseFinding(
                analysis_id=analysis.id, organization_id=organization.id,
                device_id=device.id, diagnostic_result_id=result.id,
                rule_id="connectivity-failure", category="CONNECTIVITY",
                status=RootCauseFindingStatus.IDENTIFIED,
                severity=RootCauseFindingSeverity.HIGH,
                confidence=RootCauseFindingConfidence.HIGH,
                title="Connectivity failure", summary="Failure",
                explanation="Deterministic evidence", evidence={"diagnostic_result_ids": [str(result.id)]},
                fingerprint="connectivity-failure:" + str(result.id),
            )
            session.add(finding)
            session.commit()
            assert session.get(RootCauseFinding, finding.id) is not None

            with pytest.raises(IntegrityError):
                session.add(RootCauseAnalysis(
                    organization_id=organization.id, device_id=other_device.id,
                    diagnostic_run_id=run.id, provider="deterministic",
                    status=RootCauseAnalysisStatus.PENDING,
                ))
                session.commit()
            session.rollback()

            with pytest.raises(IntegrityError):
                session.add(RootCauseFinding(
                    analysis_id=analysis.id, organization_id=organization.id,
                    device_id=device.id, diagnostic_result_id=other_result.id,
                    rule_id="foreign-result", category="CONNECTIVITY",
                    status=RootCauseFindingStatus.IDENTIFIED,
                    severity=RootCauseFindingSeverity.HIGH,
                    confidence=RootCauseFindingConfidence.HIGH,
                    title="Invalid", summary="Invalid", explanation="Invalid",
                    evidence={"diagnostic_result_ids": [str(other_result.id)]},
                    fingerprint="foreign-result:" + str(other_result.id),
                ))
                session.commit()
            session.rollback()

        command.downgrade(config, "9e4f7a1c2b30")
        assert "root_cause_findings" not in inspect(engine).get_table_names()
        command.upgrade(config, "head")
    finally:
        engine.dispose()
        get_settings.cache_clear()


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
