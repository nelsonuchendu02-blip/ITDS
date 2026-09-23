from dataclasses import dataclass
from pathlib import Path

import pytest

from itds_agent.collectors.system import SystemCollector
from itds_agent.communication.client import (
    AgentAuthenticationError,
    AgentClient,
    AgentRetryableError,
    HEARTBEAT_PATH,
    HttpxTransport,
)
from itds_agent.config.settings import AgentSettings
from itds_agent.core.runtime import AgentRuntime, RuntimeState


@dataclass
class FakeTransport:
    calls: list[tuple[str, dict, dict, float]]
    error: Exception | None = None

    def send(self, path, payload, *, headers, timeout):
        self.calls.append((path, payload, headers, timeout))
        if self.error:
            raise self.error
        return {"accepted": True}


def settings() -> AgentSettings:
    return AgentSettings(
        api_base_url="https://api.example.test",
        credential="cred-prefix.secret",
        agent_version="9.9.9",
        heartbeat_interval_seconds=10,
        request_timeout_seconds=7,
    )


def test_standalone_dependency_definition_is_complete():
    requirements = (Path(__file__).parents[1] / "requirements.txt").read_text()
    assert "httpx==0.27.0" in requirements
    assert "psutil==6.1.1" in requirements


def test_client_sends_credential_header_and_bounds_timeout():
    transport = FakeTransport([])
    result = AgentClient(transport, settings().credential, request_timeout_seconds=7).heartbeat(
        {"observed_at": "now"}
    )
    assert result == {"accepted": True}
    path, _, headers, timeout = transport.calls[0]
    assert path == "/api/v1/agents/heartbeat"
    assert path == HEARTBEAT_PATH
    assert headers == {"X-Agent-Credential": "cred-prefix.secret"}
    assert timeout == 7


def test_heartbeat_path_uses_the_versioned_api_prefix():
    """Fails against a bare '/agents/heartbeat' path; passes only with '/api/v1'."""
    transport = FakeTransport([])
    AgentClient(transport, "prefix.secret").heartbeat({})
    path = transport.calls[0][0]
    assert path == "/api/v1/agents/heartbeat"


def test_client_retries_transient_failures_with_a_bound(monkeypatch):
    transport = FakeTransport([], ConnectionError("network down"))
    sleeps = []
    monkeypatch.setattr("itds_agent.communication.client.time.sleep", sleeps.append)
    with pytest.raises(AgentRetryableError) as error:
        AgentClient(transport, "prefix.secret", max_attempts=3).heartbeat({})
    assert len(transport.calls) == 3
    assert len(sleeps) == 2
    assert "prefix.secret" not in str(error.value)


def test_client_does_not_retry_authentication_failures():
    transport = FakeTransport([], AgentAuthenticationError("authentication failed"))
    with pytest.raises(AgentAuthenticationError):
        AgentClient(transport, "prefix.secret", max_attempts=3).heartbeat({})
    assert len(transport.calls) == 1


def test_https_transport_rejects_insecure_urls():
    with pytest.raises(ValueError):
        HttpxTransport("http://api.example.test")


def test_https_transport_constructs_the_heartbeat_url(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout, follow_redirects):
        captured["url"] = url

        class Response:
            status_code = 200
            content = b'{"accepted": true}'

            def json(self):
                return {"accepted": True}

        return Response()

    monkeypatch.setattr("itds_agent.communication.client.httpx.post", fake_post)
    transport = HttpxTransport("https://server.example.com")
    transport.send(HEARTBEAT_PATH, {}, headers={}, timeout=5)
    assert captured["url"] == "https://server.example.com/api/v1/agents/heartbeat"


def test_https_transport_normalizes_a_trailing_slash_base_url(monkeypatch):
    captured = {}

    def fake_post(url, *, json, headers, timeout, follow_redirects):
        captured["url"] = url

        class Response:
            status_code = 200
            content = b'{"accepted": true}'

            def json(self):
                return {"accepted": True}

        return Response()

    monkeypatch.setattr("itds_agent.communication.client.httpx.post", fake_post)
    transport = HttpxTransport("https://server.example.com/")
    transport.send(HEARTBEAT_PATH, {}, headers={}, timeout=5)
    assert captured["url"] == "https://server.example.com/api/v1/agents/heartbeat"
    assert "//api/v1" not in captured["url"]


def test_system_collector_returns_safe_bounded_metrics(monkeypatch):
    monkeypatch.setattr("itds_agent.collectors.system.psutil.cpu_percent", lambda interval=None: 120)
    result = SystemCollector("1.2.3").collect()
    assert result["agent_version"] == "1.2.3"
    assert result["hostname"] is not None
    assert result["platform"] is not None
    assert result["cpu_percent"] == 100.0
    assert 0 <= result["memory_percent"] <= 100
    assert 0 <= result["disk_percent"] <= 100
    assert result["uptime_seconds"] >= 0


def test_system_collector_handles_unavailable_metrics(monkeypatch):
    def unavailable():
        raise OSError("unavailable")

    monkeypatch.setattr(SystemCollector, "_memory_percent", staticmethod(unavailable))
    monkeypatch.setattr("itds_agent.collectors.system.psutil.boot_time", unavailable)
    result = SystemCollector().collect()
    assert result["memory_percent"] is None
    assert result["uptime_seconds"] is None


def test_runtime_runs_bounded_cycles_and_stops():
    calls = []
    runtime = AgentRuntime(settings(), calls.append)
    waits = []
    runtime._stop_event.wait = lambda interval: waits.append(interval) or False
    assert runtime.run(max_cycles=2) == 2
    assert runtime.state is RuntimeState.STOPPED
    assert len(calls) == 2
    assert waits == [10]
    assert all(call["agent_version"] == "9.9.9" for call in calls)


def test_runtime_enters_error_without_hanging_on_heartbeat_failure():
    runtime = AgentRuntime(settings(), lambda payload: (_ for _ in ()).throw(RuntimeError("failed")))
    assert runtime.run(max_cycles=1) == 1
    assert runtime.state is RuntimeState.ERROR
