from dataclasses import dataclass
from uuid import UUID

from ..models import DiagnosticCheckType, DiagnosticResultSeverity, DiagnosticResultStatus


@dataclass(frozen=True)
class DiagnosticCheck:
    identifier: str
    check_type: DiagnosticCheckType
    status: DiagnosticResultStatus
    severity: DiagnosticResultSeverity
    observed: dict
    expected: dict
    message: str


class SimulatedDiagnosticProvider:
    name = "simulated"

    def run(self, *, device_id: UUID, diagnostic_type: str) -> list[DiagnosticCheck]:
        # Deliberately deterministic and side-effect free: no shell, network, or secrets.
        return [DiagnosticCheck(
            identifier=f"{diagnostic_type}.simulated",
            check_type=DiagnosticCheckType(diagnostic_type),
            status=DiagnosticResultStatus.PASS,
            severity=DiagnosticResultSeverity.INFO,
            observed={"device_id": str(device_id), "simulation": True},
            expected={"simulation": True},
            message="Simulated diagnostic check passed",
        )]
