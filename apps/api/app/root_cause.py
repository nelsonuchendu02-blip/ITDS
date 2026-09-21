"""Deterministic, allow-listed root-cause rules.

Rules intentionally receive only persisted DiagnosticResult fields. They do not
accept client-provided predicates, expressions, commands, or provider data.
"""
from dataclasses import dataclass
from typing import Callable

from .models import (
    DiagnosticResult, RootCauseFindingConfidence, RootCauseFindingSeverity,
    RootCauseFindingStatus,
)


@dataclass(frozen=True)
class RuleFinding:
    rule_id: str
    category: str
    status: RootCauseFindingStatus
    severity: RootCauseFindingSeverity
    confidence: RootCauseFindingConfidence
    title: str
    summary: str
    explanation: str
    evidence_result_ids: tuple[str, ...]


Rule = Callable[[list[DiagnosticResult]], RuleFinding | None]


def _failed_check(results: list[DiagnosticResult], check_type: str, rule_id: str,
                  severity: RootCauseFindingSeverity, title: str, summary: str) -> RuleFinding | None:
    matches = [result for result in results if result.check_type.value == check_type and result.status.value == "fail"]
    if not matches:
        return None
    evidence_ids = tuple(str(result.id) for result in matches)
    return RuleFinding(
        rule_id=rule_id,
        category=check_type.upper(),
        status=RootCauseFindingStatus.IDENTIFIED,
        severity=severity,
        confidence=RootCauseFindingConfidence.HIGH,
        title=title,
        summary=summary,
        explanation=f"Deterministic rule {rule_id} matched failed {check_type} evidence.",
        evidence_result_ids=evidence_ids,
    )


def _connectivity(results: list[DiagnosticResult]) -> RuleFinding | None:
    return _failed_check(results, "connectivity", "connectivity-failure",
                         RootCauseFindingSeverity.HIGH, "Connectivity failure",
                         "One or more connectivity checks failed.")


def _configuration(results: list[DiagnosticResult]) -> RuleFinding | None:
    return _failed_check(results, "configuration", "configuration-failure",
                         RootCauseFindingSeverity.MEDIUM, "Configuration failure",
                         "One or more configuration checks failed.")


def _security(results: list[DiagnosticResult]) -> RuleFinding | None:
    return _failed_check(results, "security", "security-failure",
                         RootCauseFindingSeverity.CRITICAL, "Security failure",
                         "One or more security checks failed.")


def _performance(results: list[DiagnosticResult]) -> RuleFinding | None:
    return _failed_check(results, "performance", "performance-failure",
                         RootCauseFindingSeverity.MEDIUM, "Performance failure",
                         "One or more performance checks failed.")


RULE_REGISTRY: tuple[Rule, ...] = (_connectivity, _configuration, _security, _performance)


def evaluate_rules(results: list[DiagnosticResult]) -> list[RuleFinding]:
    """Evaluate rules in stable registry order and deduplicate by fingerprint."""
    findings: list[RuleFinding] = []
    seen: set[tuple[str, tuple[str, ...]]] = set()
    for rule in RULE_REGISTRY:
        finding = rule(results)
        if finding is not None and (finding.rule_id, finding.evidence_result_ids) not in seen:
            seen.add((finding.rule_id, finding.evidence_result_ids))
            findings.append(finding)
    return findings
