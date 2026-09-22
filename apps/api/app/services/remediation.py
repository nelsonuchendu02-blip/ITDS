from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from ..exceptions import SecurityError
from ..models import (
    AuditEvent, Recommendation, RecommendationStatus, RemediationAction,
    RemediationActionStatus, RemediationPlan, RemediationPlanStatus,
    RemediationVerification, RemediationVerificationStatus, User,
)
from ..remediation.executor import DryRunExecutor
from ..remediation.generator import canonical_plan_hash, generate_actions


class RemediationService:
    def get(self, session: Session, plan_id: UUID, organization_id: UUID):
        plan = session.scalar(select(RemediationPlan).execution_options(populate_existing=True).options(
            selectinload(RemediationPlan.actions), selectinload(RemediationPlan.verifications)
        ).where(RemediationPlan.id == plan_id, RemediationPlan.organization_id == organization_id))
        if plan is not None:
            plan.actions[:] = list(session.scalars(select(RemediationAction).where(
                RemediationAction.plan_id == plan.id,
                RemediationAction.organization_id == organization_id,
            )))
        return plan

    def list(self, session: Session, organization_id: UUID, *, limit: int = 100, offset: int = 0):
        return list(session.scalars(select(RemediationPlan).options(
            selectinload(RemediationPlan.actions), selectinload(RemediationPlan.verifications)
        ).where(RemediationPlan.organization_id == organization_id)
          .order_by(RemediationPlan.created_at.desc()).offset(offset).limit(limit)))

    def actions(self, session: Session, plan_id: UUID, organization_id: UUID):
        plan = self.get(session, plan_id, organization_id)
        return None if plan is None else plan.actions

    def generate(self, session: Session, recommendation_id: UUID, actor: User) -> RemediationPlan:
        recommendation = session.scalar(select(Recommendation).where(
            Recommendation.id == recommendation_id,
            Recommendation.organization_id == actor.organization_id,
            Recommendation.status == RecommendationStatus.ACCEPTED,
            Recommendation.device_id.is_not(None),
        ))
        if recommendation is None:
            raise SecurityError("recommendation_not_eligible", "Recommendation is not eligible for remediation", 409)
        existing = session.scalar(select(RemediationPlan).where(
            RemediationPlan.recommendation_id == recommendation.id,
            RemediationPlan.device_id == recommendation.device_id,
            RemediationPlan.organization_id == actor.organization_id,
        ))
        if existing is not None:
            return self.get(session, existing.id, actor.organization_id)
        try:
            actions = generate_actions(recommendation)
        except ValueError:
            raise SecurityError("invalid_remediation_action", "Recommendation cannot produce a safe remediation plan", 422) from None
        plan = RemediationPlan(
            organization_id=actor.organization_id, device_id=recommendation.device_id,
            recommendation_id=recommendation.id,
            root_cause_finding_id=recommendation.root_cause_finding_id,
            created_by_user_id=actor.id,
            title=f"Remediation for {recommendation.title}", rationale=recommendation.summary or "",
            plan_hash=canonical_plan_hash(recommendation.device_id, actions),
            status=RemediationPlanStatus.DRAFT, dry_run=True,
        )
        session.add(plan)
        try:
            session.flush()
            for action in actions:
                session.add(RemediationAction(plan_id=plan.id, organization_id=actor.organization_id,
                                              device_id=plan.device_id, **action))
            self._audit(session, actor, "plan_created", plan)
            session.commit()
        except IntegrityError:
            session.rollback()
            existing = session.scalar(select(RemediationPlan).where(
                RemediationPlan.recommendation_id == recommendation.id,
                RemediationPlan.device_id == recommendation.device_id,
                RemediationPlan.organization_id == actor.organization_id,
            ))
            if existing is None:
                raise SecurityError("remediation_create_failed", "Unable to create remediation plan", 409) from None
            return self.get(session, existing.id, actor.organization_id)
        return self.get(session, plan.id, actor.organization_id)

    def transition(self, session: Session, plan: RemediationPlan, actor: User, target: RemediationPlanStatus):
        allowed = {
            RemediationPlanStatus.PENDING_APPROVAL: {
                RemediationPlanStatus.DRAFT,
            },
            RemediationPlanStatus.APPROVED: {
                RemediationPlanStatus.PENDING_APPROVAL,
            },
            RemediationPlanStatus.REJECTED: {RemediationPlanStatus.PENDING_APPROVAL},
            RemediationPlanStatus.QUEUED: {RemediationPlanStatus.APPROVED},
            RemediationPlanStatus.EXECUTING: {RemediationPlanStatus.QUEUED},
            RemediationPlanStatus.SUCCEEDED: {RemediationPlanStatus.EXECUTING},
            RemediationPlanStatus.CANCELLED: {
                RemediationPlanStatus.DRAFT,
                RemediationPlanStatus.PENDING_APPROVAL, RemediationPlanStatus.APPROVED,
                RemediationPlanStatus.QUEUED,
            },
            RemediationPlanStatus.VERIFIED: {RemediationPlanStatus.VERIFICATION_REQUIRED},
        }
        if plan.status not in allowed.get(target, set()):
            self._audit(session, actor, f"plan_{target.value}", plan, result="failure")
            session.commit()
            raise SecurityError("invalid_remediation_transition", "Invalid remediation lifecycle transition", 409)
        now = datetime.now(timezone.utc)
        if target is RemediationPlanStatus.APPROVED:
            plan.approved_by_user_id, plan.approved_at = actor.id, now
        plan.status = target
        if target is RemediationPlanStatus.VERIFIED:
            plan.verification_status = RemediationVerificationStatus.PASSED
        self._audit(session, actor, f"plan_{target.value}", plan)
        session.commit()
        return self.get(session, plan.id, plan.organization_id)

    def execute(self, session: Session, plan: RemediationPlan, actor: User):
        if not plan.dry_run:
            raise SecurityError("dry_run_required", "Only dry-run remediation execution is permitted", 409)
        self.transition(session, plan, actor, RemediationPlanStatus.EXECUTING)
        try:
            executor = DryRunExecutor()
            actions = list(session.scalars(select(RemediationAction).where(
                RemediationAction.plan_id == plan.id,
                RemediationAction.organization_id == plan.organization_id,
            )))
            for action in sorted(actions, key=lambda item: item.sequence):
                action.status = RemediationActionStatus.EXECUTING
                result = executor.execute(action.action_key, action.parameters)
                action.result = {"success": result.success, "message": result.message, **result.observed}
                action.status = RemediationActionStatus.SUCCEEDED
            self.transition(session, plan, actor, RemediationPlanStatus.SUCCEEDED)
            plan = self.get(session, plan.id, plan.organization_id)
            plan.status = RemediationPlanStatus.VERIFICATION_REQUIRED
            plan.verification_status = RemediationVerificationStatus.PENDING
            plan.executed_at = datetime.now(timezone.utc)
            self._audit(session, actor, "plan_executed_dry_run", plan)
            session.commit()
        except Exception:
            session.rollback()
            plan = self.get(session, plan.id, plan.organization_id)
            plan.status = RemediationPlanStatus.FAILED
            self._audit(session, actor, "plan_execution_failed", plan, result="failure")
            session.commit()
            raise SecurityError("remediation_execution_failed", "Remediation dry-run failed", 422) from None
        return self.get(session, plan.id, plan.organization_id)

    def verify(self, session: Session, plan: RemediationPlan, actor: User):
        if plan.status is not RemediationPlanStatus.VERIFICATION_REQUIRED:
            raise SecurityError("invalid_remediation_transition", "Plan is not awaiting verification", 409)
        verification = RemediationVerification(
            plan_id=plan.id, organization_id=plan.organization_id, device_id=plan.device_id,
            check_key="dry_run_completed",
            status=RemediationVerificationStatus.PASSED, observed={"executed": False},
            details="Dry-run verification only; no OS execution occurred", verified_at=datetime.now(timezone.utc),
        )
        session.add(verification)
        plan.status = RemediationPlanStatus.VERIFIED
        plan.verification_status = RemediationVerificationStatus.PASSED
        self._audit(session, actor, "plan_verified", plan)
        session.commit()
        return self.get(session, plan.id, plan.organization_id)

    @staticmethod
    def _audit(session, actor, action, plan, *, result="success"):
        session.add(AuditEvent(organization_id=plan.organization_id, actor_user_id=actor.id,
                               event_type="remediation", resource_type="remediation_plan",
                               resource_id=str(plan.id), action=action, result=result,
                               event_metadata={"dry_run": plan.dry_run},
                               created_at=datetime.now(timezone.utc)))
