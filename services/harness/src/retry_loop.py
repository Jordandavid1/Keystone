"""
KEYSTONE Bounded Retry & Replanning Engine (Bible §14, §15, §16).
Enforces hard bounds on execution attempts, cumulative runtime, and credit cost.
Prevents infinite loops and runaway GPU spend.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

from packages.contracts.src.models import (
    GenerationAttempt,
    HarnessResult,
    QualityScore,
    RetryPolicy
)


class RetryDecision:
    """Outcome of evaluating whether to retry or abort/replan."""

    def __init__(
        self,
        action: Literal["RETRY", "REPLAN", "ABORT", "PASS"],
        reason: str,
        attempt_number: int,
        cumulative_cost: float,
        cumulative_runtime_seconds: float,
        recommended_adjustments: Optional[Dict[str, Any]] = None
    ):
        self.action = action
        self.reason = reason
        self.attempt_number = attempt_number
        self.cumulative_cost = cumulative_cost
        self.cumulative_runtime_seconds = cumulative_runtime_seconds
        self.recommended_adjustments = recommended_adjustments or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "attempt_number": self.attempt_number,
            "cumulative_cost": self.cumulative_cost,
            "cumulative_runtime_seconds": self.cumulative_runtime_seconds,
            "recommended_adjustments": self.recommended_adjustments
        }


class BoundedRetryManager:
    """
    Evaluates attempts and enforces RetryPolicy boundaries.
    """

    def __init__(self, policy: Optional[RetryPolicy] = None):
        self.policy = policy or RetryPolicy()
        self.attempts: List[GenerationAttempt] = []
        self.cumulative_cost: float = 0.0
        self.start_time: float = time.time()

    def record_attempt(
        self,
        job_id: str,
        provider_id: str,
        capability_id: str,
        prompt_hash: str,
        success: bool,
        cost: float = 1.0,
        runtime_seconds: float = 15.0,
        failure_code: Optional[str] = None,
        output_asset_ids: Optional[List[str]] = None
    ) -> GenerationAttempt:
        attempt_id = f"att_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc)
        self.cumulative_cost += cost

        attempt = GenerationAttempt(
            attempt_id=attempt_id,
            job_id=job_id,
            provider_id=provider_id,
            capability_id=capability_id,
            prompt_hash=prompt_hash,
            workflow_version="1.0.0",
            started_at=now,
            completed_at=now,
            success=success,
            output_asset_ids=output_asset_ids or [],
            metrics={"runtime_seconds": runtime_seconds, "cost": cost},
            failure_code=failure_code
        )
        self.attempts.append(attempt)
        return attempt

    def evaluate_retry(
        self,
        latest_harness_result: Optional[HarnessResult] = None,
        latest_quality_score: Optional[QualityScore] = None
    ) -> RetryDecision:
        """
        Determines whether another generation attempt should be dispatched.
        """
        attempt_count = len(self.attempts)
        elapsed_time = time.time() - self.start_time

        # 1. Check if latest attempt passed cleanly
        if self.attempts and self.attempts[-1].success:
            if latest_harness_result and latest_harness_result.verdict == "fail":
                pass  # Quality failed despite worker execution success
            else:
                return RetryDecision(
                    action="PASS",
                    reason="GENERATION_SUCCEEDED",
                    attempt_number=attempt_count,
                    cumulative_cost=self.cumulative_cost,
                    cumulative_runtime_seconds=elapsed_time
                )

        # 2. Check maximum attempts bound
        if attempt_count >= self.policy.max_attempts:
            return RetryDecision(
                action="REPLAN" if attempt_count < 5 else "ABORT",
                reason=f"MAX_ATTEMPTS_EXCEEDED: Reached {attempt_count}/{self.policy.max_attempts} attempts",
                attempt_number=attempt_count,
                cumulative_cost=self.cumulative_cost,
                cumulative_runtime_seconds=elapsed_time
            )

        # 3. Check cumulative runtime bound
        if elapsed_time > self.policy.max_total_runtime_seconds:
            return RetryDecision(
                action="ABORT",
                reason=f"TIMEOUT_EXCEEDED: Elapsed {elapsed_time:.1f}s exceeds {self.policy.max_total_runtime_seconds}s limit",
                attempt_number=attempt_count,
                cumulative_cost=self.cumulative_cost,
                cumulative_runtime_seconds=elapsed_time
            )

        # 4. Check cost budget ceiling
        if self.cumulative_cost >= self.policy.max_estimated_cost:
            return RetryDecision(
                action="ABORT",
                reason=f"COST_CEILING_EXCEEDED: Cumulative cost {self.cumulative_cost} exceeds budget {self.policy.max_estimated_cost}",
                attempt_number=attempt_count,
                cumulative_cost=self.cumulative_cost,
                cumulative_runtime_seconds=elapsed_time
            )

        # 5. Determine recommended parameter adjustments for retry
        adjustments: Dict[str, Any] = {"seed": int(time.time() * 1000) % 100000}
        if latest_harness_result and "POOR_PROMPT_ADHERENCE" in latest_harness_result.reason_codes:
            adjustments["guidance_multiplier"] = 1.15
        if latest_harness_result and "HIGH_ARTIFACT_DENSITY" in latest_harness_result.reason_codes:
            adjustments["steps"] = 28
            adjustments["denoise"] = 0.65

        return RetryDecision(
            action="RETRY",
            reason=f"PERMITTED_RETRY: Attempt {attempt_count + 1} permitted within budget",
            attempt_number=attempt_count + 1,
            cumulative_cost=self.cumulative_cost,
            cumulative_runtime_seconds=elapsed_time,
            recommended_adjustments=adjustments
        )
