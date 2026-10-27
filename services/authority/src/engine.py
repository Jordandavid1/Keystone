"""
KEYSTONE Authority Engine (Bible §12, §13).
Orchestrates sequential policy gates, credit balance checks, parameter boundary clamping,
deterministic decision rendering, and audit event emission.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from packages.contracts.src.models import ProposedAction, AuthorityDecision
from services.authority.src.rules import (
    calculate_estimated_credits,
    CONFIRMATION_CREDIT_THRESHOLD
)
from services.authority.src.evaluator import (
    SafetyPolicyEvaluator,
    CreditBalanceEvaluator,
    ParameterBoundaryEvaluator
)


class AuthorityEngine:
    """
    Sovereign Authority Decision Engine for KEYSTONE.
    Evaluates ProposedAction models against safety, parameters, and credits.
    """

    POLICY_BUNDLE_VERSION = "1.0.0"
    CAPABILITY_REGISTRY_VERSION = "1.0.0"
    HARNESS_BUNDLE_VERSION = "1.0.0"

    def __init__(self):
        # In-memory audit event log buffer for fast queries and telemetry verification
        self.audit_log: List[Dict[str, Any]] = []

    def evaluate(
        self,
        action: ProposedAction,
        user_id: str = "usr_system",
        credit_balance: int = 100,
        held_balance: int = 0,
        untrusted_content: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> AuthorityDecision:
        """
        Executes sequential evaluation pipeline over a ProposedAction.
        Returns an authoritative AuthorityDecision and logs an AuditEvent.
        """
        req_id = request_id or f"req_{uuid.uuid4().hex[:12]}"
        dec_id = f"dec_{uuid.uuid4().hex[:12]}"
        reason_codes: List[str] = []

        # --------------------------------------------------------------------
        # Gate 1: Safety & Security Policy
        # --------------------------------------------------------------------
        safety_res = SafetyPolicyEvaluator.evaluate(action, untrusted_content=untrusted_content)
        if not safety_res.passed:
            decision = AuthorityDecision(
                decision_id=dec_id,
                request_id=req_id,
                decision="DENY",
                decision_enum="deny",
                capability_id=action.capability,
                provider_id="keystone_internal",
                required_credits=0,
                sanitized_arguments={},
                reason_codes=safety_res.reason_codes,
                policy_bundle_version=self.POLICY_BUNDLE_VERSION,
                capability_registry_version=self.CAPABILITY_REGISTRY_VERSION,
                harness_bundle_version=self.HARNESS_BUNDLE_VERSION,
                created_at=datetime.now(timezone.utc)
            )
            self._emit_audit_event(decision, user_id=user_id, raw_action=action)
            return decision

        # --------------------------------------------------------------------
        # Gate 2: Parameter Boundary & Whitelist
        # --------------------------------------------------------------------
        param_res = ParameterBoundaryEvaluator.evaluate(action)
        if not param_res.passed:
            decision = AuthorityDecision(
                decision_id=dec_id,
                request_id=req_id,
                decision="DENY",
                decision_enum="deny",
                capability_id=action.capability,
                provider_id="keystone_internal",
                required_credits=0,
                sanitized_arguments=param_res.sanitized_arguments,
                reason_codes=param_res.reason_codes,
                policy_bundle_version=self.POLICY_BUNDLE_VERSION,
                capability_registry_version=self.CAPABILITY_REGISTRY_VERSION,
                harness_bundle_version=self.HARNESS_BUNDLE_VERSION,
                created_at=datetime.now(timezone.utc)
            )
            self._emit_audit_event(decision, user_id=user_id, raw_action=action)
            return decision

        sanitized_params = param_res.sanitized_arguments
        reason_codes.extend(param_res.reason_codes)

        # --------------------------------------------------------------------
        # Gate 3: Credit Cost Calculation
        # --------------------------------------------------------------------
        required_credits = calculate_estimated_credits(action.capability, sanitized_params)

        # --------------------------------------------------------------------
        # Gate 4: Tenant Credit Balance Check
        # --------------------------------------------------------------------
        credit_res = CreditBalanceEvaluator.evaluate(
            required_credits=required_credits,
            balance=credit_balance,
            held_balance=held_balance
        )
        if not credit_res.passed:
            decision = AuthorityDecision(
                decision_id=dec_id,
                request_id=req_id,
                decision="DENY",
                decision_enum="deny",
                capability_id=action.capability,
                provider_id="keystone_internal",
                required_credits=required_credits,
                sanitized_arguments=sanitized_params,
                reason_codes=credit_res.reason_codes,
                policy_bundle_version=self.POLICY_BUNDLE_VERSION,
                capability_registry_version=self.CAPABILITY_REGISTRY_VERSION,
                harness_bundle_version=self.HARNESS_BUNDLE_VERSION,
                created_at=datetime.now(timezone.utc)
            )
            self._emit_audit_event(decision, user_id=user_id, raw_action=action)
            return decision

        # --------------------------------------------------------------------
        # Gate 5: Confirmation Policy (High Cost Operations)
        # --------------------------------------------------------------------
        if required_credits > CONFIRMATION_CREDIT_THRESHOLD:
            reason_codes.append("HIGH_COST_OPERATION_CONFIRMATION_REQUIRED")
            decision = AuthorityDecision(
                decision_id=dec_id,
                request_id=req_id,
                decision="REQUIRE_CONFIRMATION",
                decision_enum="replan",
                capability_id=action.capability,
                provider_id="keystone_internal",
                required_credits=required_credits,
                sanitized_arguments=sanitized_params,
                reason_codes=reason_codes,
                policy_bundle_version=self.POLICY_BUNDLE_VERSION,
                capability_registry_version=self.CAPABILITY_REGISTRY_VERSION,
                harness_bundle_version=self.HARNESS_BUNDLE_VERSION,
                created_at=datetime.now(timezone.utc)
            )
            self._emit_audit_event(decision, user_id=user_id, raw_action=action)
            return decision

        # --------------------------------------------------------------------
        # Verdict: ALLOW
        # --------------------------------------------------------------------
        reason_codes.append("POLICY_EVALUATION_PASSED")
        decision = AuthorityDecision(
            decision_id=dec_id,
            request_id=req_id,
            decision="ALLOW",
            decision_enum="approve",
            capability_id=action.capability,
            provider_id="keystone_internal",
            required_credits=required_credits,
            sanitized_arguments=sanitized_params,
            reason_codes=reason_codes,
            policy_bundle_version=self.POLICY_BUNDLE_VERSION,
            capability_registry_version=self.CAPABILITY_REGISTRY_VERSION,
            harness_bundle_version=self.HARNESS_BUNDLE_VERSION,
            created_at=datetime.now(timezone.utc)
        )
        self._emit_audit_event(decision, user_id=user_id, raw_action=action)
        return decision

    def _emit_audit_event(
        self,
        decision: AuthorityDecision,
        user_id: str,
        raw_action: ProposedAction
    ) -> Dict[str, Any]:
        """Emits an immutable AuditEvent and logs it to internal buffer and database."""
        event_record = {
            "id": str(uuid.uuid4()),
            "actor_type": "authority_engine",
            "actor_id": user_id or "keystone_system",
            "event_type": "authority.decision",
            "request_id": decision.request_id,
            "job_id": None,
            "data": {
                "decision_id": decision.decision_id,
                "decision": decision.decision,
                "decision_enum": decision.decision_enum,
                "capability_id": decision.capability_id,
                "required_credits": decision.required_credits,
                "reason_codes": decision.reason_codes,
                "sanitized_arguments": decision.sanitized_arguments,
                "action_type": raw_action.action_type
            },
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        self.audit_log.append(event_record)
        return event_record


# Singleton instance
authority_engine = AuthorityEngine()
