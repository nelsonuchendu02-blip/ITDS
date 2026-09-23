import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx


class AgentCommunicationError(RuntimeError):
    """A communication failure that is safe to expose to callers."""


class AgentAuthenticationError(AgentCommunicationError):
    """The API rejected the agent credential."""


class AgentRetryableError(AgentCommunicationError):
    """A bounded, potentially transient transport failure."""

class Transport(Protocol):
    def send(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, Any]: ...


@dataclass
class HttpxTransport:
    base_url: str
    max_response_bytes: int = 64_000

    def __post_init__(self) -> None:
        if not self.base_url.startswith("https://"):
            raise ValueError("API base URL must use HTTPS")
        self.base_url = self.base_url.rstrip("/")

    def send(
        self,
        path: str,
        payload: dict[str, Any],
        *,
        headers: dict[str, str],
        timeout: float,
    ) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.base_url}{path}",
                json=payload,
                headers=headers,
                timeout=timeout,
                follow_redirects=False,
            )
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise AgentRetryableError("agent API request failed") from exc
        if response.status_code in (401, 403):
            raise AgentAuthenticationError("agent API authentication failed")
        if response.status_code == 408 or response.status_code == 429 or response.status_code >= 500:
            raise AgentRetryableError("agent API temporarily unavailable")
        if response.status_code >= 400:
            raise AgentCommunicationError("agent API rejected the request")
        if len(response.content) > self.max_response_bytes:
            raise AgentCommunicationError("agent API response exceeds bounds")
        try:
            result = response.json()
        except ValueError as exc:
            raise AgentCommunicationError("agent API returned invalid JSON") from exc
        if not isinstance(result, dict):
            raise AgentCommunicationError("agent API returned an invalid response")
        return result

@dataclass
class AgentClient:
    transport: Transport
    credential: str
    max_attempts: int = 3
    retry_delay_seconds: float = 0.25
    request_timeout_seconds: float = 15
    max_payload_bytes: int = 64_000

    @classmethod
    def from_settings(cls, settings) -> "AgentClient":
        settings.validate()
        return cls(
            transport=HttpxTransport(settings.api_base_url or settings.endpoint_url),
            credential=settings.credential,
            request_timeout_seconds=settings.request_timeout_seconds,
        )

    def heartbeat(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.credential or "." not in self.credential:
            raise ValueError("credential is required")
        serialized = json.dumps(payload, default=str)
        if len(payload) > 32 or len(serialized.encode("utf-8")) > self.max_payload_bytes:
            raise ValueError("heartbeat payload exceeds bounds")
        attempts = max(1, min(self.max_attempts, 3))
        for attempt in range(attempts):
            try:
                return self.transport.send(
                    "/agents/heartbeat",
                    payload,
                    headers={"X-Agent-Credential": self.credential},
                    timeout=self.request_timeout_seconds,
                )
            except AgentAuthenticationError:
                raise
            except (AgentRetryableError, TimeoutError, ConnectionError) as exc:
                if attempt + 1 == attempts:
                    raise AgentRetryableError("heartbeat delivery failed") from exc
                time.sleep(min(self.retry_delay_seconds * (2 ** attempt), 2.0))
        raise AgentRetryableError("heartbeat delivery failed")
