"""Phase 1M contract tests that also run without a live PostgreSQL instance."""
from datetime import datetime, timezone

import pytest

from app.models import AgentStatus
from app.schemas.agent import AgentHeartbeat


def test_agent_status_values_are_exact():
    assert {item.value for item in AgentStatus} == {
        "pending", "active", "offline", "revoked", "retired",
    }


def test_heartbeat_rejects_unbounded_or_sensitive_metrics():
    with pytest.raises(ValueError):
        AgentHeartbeat(
            observed_at=datetime.now(timezone.utc),
            metrics={f"metric_{n}": n for n in range(33)},
        )
    with pytest.raises(ValueError):
        AgentHeartbeat(
            observed_at=datetime.now(timezone.utc),
            metrics={"shell_output": "not allowed"},
        )


def test_heartbeat_accepts_bounded_safe_metrics():
    payload = AgentHeartbeat(
        observed_at=datetime.now(timezone.utc),
        metrics={"cpu_percent": 42.5, "healthy": True},
    )
    assert payload.metrics["cpu_percent"] == 42.5


def test_heartbeat_requires_timezone():
    with pytest.raises(ValueError):
        AgentHeartbeat(observed_at=datetime(2026, 1, 1))
