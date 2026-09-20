from __future__ import annotations

from typing import Any


class DiagnosticAnalyzer:
    """Diagnostics shell that will later reason over endpoint state."""

    def analyze(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "not_implemented",
            "input_summary": sorted(payload.keys()),
        }
