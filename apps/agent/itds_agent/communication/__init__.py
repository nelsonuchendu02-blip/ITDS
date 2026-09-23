"""Communication channels for the future endpoint agent."""

from .channel import CommunicationChannel
from .client import AgentClient, AgentCommunicationError, Transport

__all__ = ["CommunicationChannel", "AgentClient", "AgentCommunicationError", "Transport"]
