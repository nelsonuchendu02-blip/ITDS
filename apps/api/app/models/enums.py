from enum import StrEnum


class DeviceStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    RETIRED = "retired"


class DiscoveryJobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DiscoveryResultStatus(StrEnum):
    DISCOVERED = "discovered"
    NOT_REACHABLE = "not_reachable"
    FAILED = "failed"


class ReconciliationStatus(StrEnum):
    UNMATCHED = "unmatched"
    MATCHED = "matched"
    CONFLICT = "conflict"


class OrganizationStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class UserStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class IncidentPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class IncidentStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DiagnosticRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DiagnosticCheckType(StrEnum):
    CONNECTIVITY = "connectivity"
    CONFIGURATION = "configuration"
    SECURITY = "security"
    PERFORMANCE = "performance"


class DiagnosticResultStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


class DiagnosticResultSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RootCauseAnalysisStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class RootCauseFindingSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RootCauseFindingStatus(StrEnum):
    IDENTIFIED = "identified"
    LIKELY = "likely"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class RootCauseFindingConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RecommendationConfidence(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecommendationRemediationType(StrEnum):
    GUIDANCE = "guidance"
    CONFIGURATION = "configuration"
    INVESTIGATION = "investigation"
    ESCALATION = "escalation"


class RecommendationStatus(StrEnum):
    PENDING = "pending"
    REVIEWED = "reviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    IMPLEMENTED = "implemented"
    # Compatibility aliases for Phase 1A/1I callers; they do not add values.
    PROPOSED = "pending"
    COMPLETED = "implemented"


class RepairActionStatus(StrEnum):
    REQUESTED = "requested"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EscalationStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
