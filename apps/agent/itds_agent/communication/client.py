from dataclasses import dataclass
from typing import Any, Protocol
import json
import time

class Transport(Protocol):
    def send(self, path: str, payload: dict[str, Any]) -> dict[str, Any]: ...

class AgentCommunicationError(RuntimeError):
    """A bounded communication failure without exposing credential values."""

@dataclass
class AgentClient:
    transport: Transport
    credential: str
    max_attempts: int = 3
    retry_delay_seconds: float = 0.25

    def heartbeat(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.credential or "." not in self.credential:
            raise ValueError("credential is required")
        if len(payload) > 32 or len(json.dumps(payload, default=str)) > 64_000:
            raise ValueError("heartbeat payload exceeds bounds")
        attempts = max(1, min(self.max_attempts, 3))
        for attempt in range(attempts):
            try:
                return self.transport.send("/agents/heartbeat", payload)
            except (TimeoutError, ConnectionError) as exc:
                if attempt + 1 == attempts:
                    raise AgentCommunicationError("heartbeat delivery failed") from exc
                time.sleep(min(self.retry_delay_seconds * (2 ** attempt), 2.0))
        raise AgentCommunicationError("heartbeat delivery failed")
