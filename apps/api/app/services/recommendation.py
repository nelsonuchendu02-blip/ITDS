from datetime import datetime, timezone
import hashlib
import json
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..exceptions import PersistenceError, SecurityError
from ..models import Recommendation, RecommendationStatus, RootCauseFinding, User
from ..recommendations import recommendation_for_finding
from ..repositories.recommendation import RecommendationRepository
from .audit import record_security_event


class RecommendationService:
    def __init__(self, repository: RecommendationRepository | None = None) -> None:
        self.repository = repository or RecommendationRepository()

    def create(self, session: Session, *, organization_id: UUID, actor: User,
               finding_id: UUID, title: str | None = None, description: str | None = None,
               priority=None, rationale: str | None = None) -> Recommendation:
        self._scope(actor, organization_id)
        finding = self.repository.finding(session, finding_id, organization_id)
        if finding is None:
            raise SecurityError("root_cause_finding_not_found", "Root-cause finding not found", 404)
        template = recommendation_for_finding(finding)
        if template is None:
            raise SecurityError("unsupported_recommendation_rule", "No approved recommendation rule matches finding", 422)
        evidence = {"finding_id": str(finding.id), "fingerprint": finding.fingerprint}
        identity = self._fingerprint(
            organization_id=organization_id, device_id=finding.device_id,
            finding_id=finding.id, rule_id=template.rule_id, evidence=evidence,
        )
        recommendation = Recommendation(
            organization_id=organization_id, device_id=finding.device_id,
            diagnostic_result_id=finding.diagnostic_result_id,
            root_cause_finding_id=finding.id, root_cause_analysis_id=finding.analysis_id,
            created_by_user_id=actor.id,
            title=template.title, description=template.description,
            priority=template.priority, rationale=finding.explanation,
            rule_id=template.rule_id,
            evidence=evidence, fingerprint=identity,
            category=template.category, severity=template.severity, summary=template.summary,
            expected_effect=template.expected_effect, confidence=template.confidence,
            remediation_type=template.remediation_type,
            requires_human_approval=template.requires_human_approval,
        )
        try:
            self.repository.create(session, recommendation)
            record_security_event(session, event_type="recommendation_created",
                organization_id=organization_id, actor_user_id=actor.id, action="create",
                result="success", resource_type="recommendation", resource_id=str(recommendation.id))
            session.commit()
            session.refresh(recommendation)
            return recommendation
        except IntegrityError as exc:
            session.rollback()
            raise PersistenceError("Recommendation could not be created") from exc

    def generate(self, session: Session, *, organization_id: UUID, actor: User,
                 analysis_id: UUID) -> list[Recommendation]:
        self._scope(actor, organization_id)
        findings = self.repository.findings_for_analysis(session, analysis_id, organization_id)
        if not findings:
            raise SecurityError("root_cause_analysis_not_found", "Root-cause analysis or findings not found", 404)
        generated: list[Recommendation] = []
        try:
            for finding in findings:
                template = recommendation_for_finding(finding)
                evidence = {"finding_id": str(finding.id), "fingerprint": finding.fingerprint}
                identity = self._fingerprint(
                    organization_id=organization_id, device_id=finding.device_id,
                    finding_id=finding.id, rule_id=template.rule_id, evidence=evidence,
                ) if template is not None else ""
                if template is None or self.repository.for_identity(
                    session, organization_id=organization_id, device_id=finding.device_id,
                    finding_id=finding.id, rule_id=template.rule_id, fingerprint=identity,
                ):
                    continue
                recommendation = Recommendation(
                    organization_id=organization_id, device_id=finding.device_id,
                    diagnostic_result_id=finding.diagnostic_result_id,
                    root_cause_finding_id=finding.id, root_cause_analysis_id=finding.analysis_id,
                    created_by_user_id=actor.id,
                    title=template.title, description=template.description,
                    priority=template.priority, rationale=finding.explanation,
                    rule_id=template.rule_id,
                    evidence=evidence, fingerprint=identity,
                    category=template.category, severity=template.severity, summary=template.summary,
                    expected_effect=template.expected_effect, confidence=template.confidence,
                    remediation_type=template.remediation_type,
                    requires_human_approval=template.requires_human_approval,
                )
                self.repository.create(session, recommendation)
                generated.append(recommendation)
            record_security_event(session, event_type="recommendations_generated",
                organization_id=organization_id, actor_user_id=actor.id, action="generate",
                result="success", resource_type="root_cause_analysis", resource_id=str(analysis_id),
                metadata={"count": len(generated)})
            session.commit()
            return generated
        except IntegrityError as exc:
            session.rollback()
            self._record_generation_failure(session, organization_id, actor, analysis_id)
            raise PersistenceError("Recommendations could not be generated") from exc
        except Exception as exc:
            session.rollback()
            self._record_generation_failure(session, organization_id, actor, analysis_id)
            raise PersistenceError("Recommendations could not be generated") from exc

    def get(self, session, recommendation_id, organization_id):
        return self.repository.get(session, recommendation_id, organization_id)

    def list(self, session, organization_id, *, offset, limit, status=None):
        return self.repository.list_page(session, organization_id, offset=offset, limit=limit, status=status)

    def transition(self, session: Session, *, recommendation: Recommendation, actor: User,
                   target: RecommendationStatus, rejection_reason: str | None = None,
                   implementation_notes: str | None = None) -> Recommendation:
        self._scope(actor, recommendation.organization_id)
        allowed = {
            RecommendationStatus.PENDING: {RecommendationStatus.REVIEWED},
            RecommendationStatus.REVIEWED: {RecommendationStatus.ACCEPTED, RecommendationStatus.REJECTED},
            RecommendationStatus.ACCEPTED: {RecommendationStatus.IMPLEMENTED},
        }
        if target not in allowed.get(recommendation.status, set()):
            raise SecurityError("invalid_transition", "Recommendation cannot make that transition", 409)
        values = {}
        now = datetime.now(timezone.utc)
        if target in {RecommendationStatus.REVIEWED, RecommendationStatus.ACCEPTED, RecommendationStatus.REJECTED}:
            values.update(reviewed_by_user_id=actor.id, reviewed_at=now)
        if target is RecommendationStatus.REJECTED:
            values["rejection_reason"] = rejection_reason
        if target is RecommendationStatus.IMPLEMENTED:
            values.update(implemented_at=now, implementation_notes=implementation_notes)
        if not self.repository.transition(session, recommendation.id, actor.organization_id,
                                          recommendation.status, target, **values):
            session.rollback()
            raise SecurityError("invalid_transition", "Recommendation cannot make that transition", 409)
        record_security_event(session, event_type=f"recommendation_{target.value}",
            organization_id=recommendation.organization_id, actor_user_id=actor.id,
            action=target.value, result="success", resource_type="recommendation",
            resource_id=str(recommendation.id))
        session.commit()
        return self.repository.get(session, recommendation.id, actor.organization_id)

    @staticmethod
    def _fingerprint(*, organization_id: UUID, device_id: UUID, finding_id: UUID,
                     rule_id: str, evidence: dict) -> str:
        normalized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        source = "|".join((str(organization_id), str(device_id), str(finding_id), rule_id, normalized))
        return hashlib.sha256(source.encode("utf-8")).hexdigest()

    @staticmethod
    def _scope(actor: User, organization_id: UUID) -> None:
        if actor.organization_id != organization_id:
            raise SecurityError("permission_denied", "Permission denied", 403)

    @staticmethod
    def _record_generation_failure(session: Session, organization_id: UUID,
                                   actor: User, analysis_id: UUID) -> None:
        record_security_event(
            session, event_type="recommendations_generation_failed",
            organization_id=organization_id, actor_user_id=actor.id,
            action="generate", result="failure",
            resource_type="root_cause_analysis", resource_id=str(analysis_id),
            metadata={"error_code": "recommendation_generation_failed"},
        )
        session.commit()
