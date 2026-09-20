from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Collector(ABC):
    """Base class for endpoint collectors.

    Phase 0 deliberately does not collect sensitive operational data.
    """

    @abstractmethod
    def collect(self) -> dict[str, Any]:
        raise NotImplementedError
