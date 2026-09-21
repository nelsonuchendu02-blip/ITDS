"""Allow-listed deterministic recommendation generation rules."""
from dataclasses import dataclass
from typing import Callable

from .models import (
    RecommendationConfidence, RecommendationPriority, RecommendationRemediationType,
    RecommendationSeverity, RootCauseFinding,
)


@dataclass(frozen=True)
class RecommendationTemplate:
    rule_id: str
    title: str
    description: str
    priority: RecommendationPriority
    category: str
    severity: RecommendationSeverity
    summary: str
    expected_effect: str
    confidence: RecommendationConfidence
    remediation_type: RecommendationRemediationType
    requires_human_approval: bool


RecommendationRule = Callable[[RootCauseFinding], RecommendationTemplate | None]


def _rule(rule_id: str, title: str, description: str, remediation_type: str):
    def evaluate(finding: RootCauseFinding) -> RecommendationTemplate | None:
        if finding.rule_id != rule_id:
            return None
        severity = RecommendationSeverity(finding.severity.value)
        priority = (RecommendationPriority.HIGH if severity in {RecommendationSeverity.HIGH, RecommendationSeverity.CRITICAL}
                    else RecommendationPriority.LOW if severity is RecommendationSeverity.LOW
                    else RecommendationPriority.MEDIUM)
        confidence = RecommendationConfidence(finding.confidence.value)
        remediation = RecommendationRemediationType.ESCALATION if severity is RecommendationSeverity.CRITICAL else (
            RecommendationRemediationType.CONFIGURATION if rule_id == "configuration-failure"
            else RecommendationRemediationType.INVESTIGATION if rule_id == "performance-failure"
            else RecommendationRemediationType.GUIDANCE
        )
        return RecommendationTemplate(
            rule_id, title, description, priority, finding.category, severity,
            finding.summary, f"Addressing {finding.category.lower()} should improve endpoint health.",
            confidence, remediation,
            severity is RecommendationSeverity.CRITICAL or rule_id == "security-failure",
        )
    return evaluate


RULE_REGISTRY: tuple[RecommendationRule, ...] = (
    _rule("connectivity-failure", "Restore endpoint connectivity",
          "Verify network reachability, adapter state, and required support connectivity.", "investigation"),
    _rule("configuration-failure", "Correct endpoint configuration",
          "Review the failed configuration signal and apply the approved configuration baseline.", "configuration"),
    _rule("security-failure", "Remediate security control failure",
          "Review the failed security control and apply the approved security remediation.", "escalation"),
    _rule("performance-failure", "Investigate endpoint performance",
          "Review resource pressure and apply the approved performance remediation.", "investigation"),
)


def recommendation_for_finding(finding: RootCauseFinding) -> RecommendationTemplate | None:
    for rule in RULE_REGISTRY:
        template = rule(finding)
        if template:
            return template
    return None
