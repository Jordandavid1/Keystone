"""
KEYSTONE Bounded Retry & Replanning Engine (Bible v2 §13.5, §14, §15, §16; ADR-005 PR7).

Enforces hard bounds on execution attempts (`KEYSTONE_EVAL_RETRY_MAX`, default 3),
cumulative runtime, and credit cost. On budget exhaustion, escalates generated assets
to operator review (`Asset.metadata_["review_required"] = True`, `Asset.status = "needs_review"`)
— never silently accepting and never silently dropping failed outputs.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from packages.contracts.src.models import (
    GenerationAttempt,
    HarnessResult,
    QualityScore,
    RetryPolicy,
)

DEFAULT_EVAL_RETRY_MAX = 3
DEFAULT_PASS_THRESHOLD = 0.70


def get_eval_retry_max(override: Optional[int] = None) -> int:
    """Resolve maximum quality evaluation retry attempts from override or KEYSTONE_EVAL_RETRY_MAX (default 3)."""
    if override is not None:
        return max(1, int(override))
    raw = os.getenv("KEYSTONE_EVAL_RETRY_MAX", str(DEFAULT_EVAL_RETRY_MAX)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_EVAL_RETRY_MAX


def flag_asset_for_operator_review(
    asset: Any,
    *,
    reason: Optional[str] = None,
    reason_codes: Optional[List[str]] = None,
    attempt_count: Optional[int] = None,
) -> Any:
    """
    Escalate an asset to operator review upon retry budget exhaustion (Bible v2 §13.5):
      - `Asset.metadata_["review_required"] = True`
      - `Asset.status = "needs_review"`
    Never silently accepts (`status != "ready"`) and never silently drops (`deleted_at` untouched).
    """
    if asset is None:
        return None

    if isinstance(asset, dict):
        meta = dict(asset.get("metadata_") or asset.get("metadata") or {})
        meta["review_required"] = True
        if reason:
            meta["review_reason"] = reason
        if reason_codes:
            meta["review_reason_codes"] = list(reason_codes)
        if attempt_count is not None:
            meta["eval_attempts"] = int(attempt_count)
        asset["metadata_"] = meta
        asset["metadata"] = meta
        asset["status"] = "needs_review"
        asset["review_required"] = True
        return asset

    existing_meta = getattr(asset, "metadata_", None)
    meta_dict: Dict[str, Any] = dict(existing_meta) if isinstance(existing_meta, dict) else {}
    meta_dict["review_required"] = True
    if reason:
        meta_dict["review_reason"] = reason
    if reason_codes:
        meta_dict["review_reason_codes"] = list(reason_codes)
    if attempt_count is not None:
        meta_dict["eval_attempts"] = int(attempt_count)

    # Re-assign dictionary AND mutate in-place so SQLAlchemy tracks changes regardless of column wrapper
    try:
        asset.metadata_ = meta_dict
        if isinstance(getattr(asset, "metadata_", None), dict):
            asset.metadata_["review_required"] = True
    except Exception:
        pass

    try:
        asset.status = "needs_review"
    except Exception:
        pass

    return asset


class RetryDecision:
    """Outcome of evaluating whether to pass, retry, replan, or abort/escalate."""

    def __init__(
        self,
        action: Literal["RETRY", "REPLAN", "ABORT", "PASS"],
        reason: str,
        attempt_number: int,
        cumulative_cost: float,
        cumulative_runtime_seconds: float,
        recommended_adjustments: Optional[Dict[str, Any]] = None,
        *,
        review_required: bool = False,
        asset_status: Optional[str] = None,
    ):
        self.action = action
        self.reason = reason
        self.attempt_number = attempt_number
        self.cumulative_cost = cumulative_cost
        self.cumulative_runtime_seconds = cumulative_runtime_seconds
        self.recommended_adjustments = recommended_adjustments or {}
        self.review_required = bool(review_required)
        self.asset_status = asset_status or ("needs_review" if self.review_required else ("ready" if action == "PASS" else None))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action,
            "reason": self.reason,
            "attempt_number": self.attempt_number,
            "cumulative_cost": self.cumulative_cost,
            "cumulative_runtime_seconds": self.cumulative_runtime_seconds,
            "recommended_adjustments": self.recommended_adjustments,
            "review_required": self.review_required,
            "asset_status": self.asset_status,
        }


class BoundedRetryManager:
    """
    Evaluates generation attempts against KHF verdicts and enforces RetryPolicy boundaries.
    """

    def __init__(
        self,
        policy: Optional[RetryPolicy] = None,
        *,
        max_attempts: Optional[int] = None,
        max_total_runtime_seconds: Optional[int] = None,
        max_estimated_cost: Optional[float] = None,
        pass_threshold: float = DEFAULT_PASS_THRESHOLD,
    ):
        if policy is None:
            resolved_max = get_eval_retry_max(max_attempts)
            policy = RetryPolicy(
                max_attempts=min(10, max(1, resolved_max)),
                max_total_runtime_seconds=int(max_total_runtime_seconds or 300),
                max_estimated_cost=float(max_estimated_cost if max_estimated_cost is not None else 10.0),
            )
        elif max_attempts is not None:
            policy = policy.model_copy(update={"max_attempts": min(10, max(1, int(max_attempts)))})

        self.policy = policy
        self.pass_threshold = float(pass_threshold)
        self.attempts: List[GenerationAttempt] = []
        self.harness_results: List[HarnessResult] = []
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
        output_asset_ids: Optional[List[str]] = None,
        attempt_id: Optional[str] = None,
        workflow_version: str = "1.0.0",
    ) -> GenerationAttempt:
        resolved_attempt_id = str(attempt_id or uuid.uuid4())
        now = datetime.now(timezone.utc)
        self.cumulative_cost += float(cost)

        attempt = GenerationAttempt(
            attempt_id=resolved_attempt_id,
            job_id=job_id,
            provider_id=provider_id,
            capability_id=capability_id,
            prompt_hash=prompt_hash,
            workflow_version=workflow_version,
            started_at=now,
            completed_at=now,
            success=bool(success),
            output_asset_ids=output_asset_ids or [],
            metrics={"runtime_seconds": float(runtime_seconds), "cost": float(cost)},
            resource_cost={"credits": float(cost), "runtime_seconds": float(runtime_seconds)},
            failure_code=failure_code,
        )
        self.attempts.append(attempt)
        return attempt

    def evaluate_retry(
        self,
        latest_harness_result: Optional[HarnessResult] = None,
        latest_quality_score: Optional[QualityScore] = None,
        *,
        pass_threshold: Optional[float] = None,
        asset: Optional[Any] = None,
    ) -> RetryDecision:
        """
        Determine whether the latest attempt passed, should be retried within budget,
        or exhausted its retry/runtime/cost budget (flagging `asset` for operator review).
        """
        if latest_harness_result is not None:
            self.harness_results.append(latest_harness_result)

        attempt_count = len(self.attempts)
        elapsed_time = max(0.0, time.time() - self.start_time)
        eff_threshold = float(pass_threshold if pass_threshold is not None else self.pass_threshold)

        # Determine whether quality evaluation failed or scored below threshold
        harness_failed = False
        if latest_harness_result is not None:
            if latest_harness_result.verdict == "fail":
                harness_failed = True
            elif latest_harness_result.score is not None and float(latest_harness_result.score) < eff_threshold:
                harness_failed = True

        quality_failed = False
        if latest_quality_score is not None and float(latest_quality_score.overall) < eff_threshold:
            quality_failed = True

        # 1. Check if latest attempt passed cleanly
        if self.attempts and self.attempts[-1].success and not harness_failed and not quality_failed:
            return RetryDecision(
                action="PASS",
                reason="GENERATION_SUCCEEDED",
                attempt_number=attempt_count,
                cumulative_cost=self.cumulative_cost,
                cumulative_runtime_seconds=elapsed_time,
                review_required=False,
                asset_status="ready",
            )

        reason_codes = list(latest_harness_result.reason_codes) if latest_harness_result else []

        # 2. Check maximum attempts bound
        if attempt_count >= self.policy.max_attempts:
            reason_msg = f"MAX_ATTEMPTS_EXCEEDED: Reached {attempt_count}/{self.policy.max_attempts} attempts"
            if asset is not None:
                flag_asset_for_operator_review(
                    asset,
                    reason=reason_msg,
                    reason_codes=reason_codes,
                    attempt_count=attempt_count,
                )
            return RetryDecision(
                action="REPLAN" if attempt_count < 5 else "ABORT",
                reason=reason_msg,
                attempt_number=attempt_count,
                cumulative_cost=self.cumulative_cost,
                cumulative_runtime_seconds=elapsed_time,
                review_required=True,
                asset_status="needs_review",
            )

        # 3. Check cumulative runtime bound
        if elapsed_time > self.policy.max_total_runtime_seconds:
            reason_msg = (
                f"TIMEOUT_EXCEEDED: Elapsed {elapsed_time:.1f}s exceeds "
                f"{self.policy.max_total_runtime_seconds}s limit"
            )
            if asset is not None:
                flag_asset_for_operator_review(
                    asset,
                    reason=reason_msg,
                    reason_codes=reason_codes,
                    attempt_count=attempt_count,
                )
            return RetryDecision(
                action="ABORT",
                reason=reason_msg,
                attempt_number=attempt_count,
                cumulative_cost=self.cumulative_cost,
                cumulative_runtime_seconds=elapsed_time,
                review_required=True,
                asset_status="needs_review",
            )

        # 4. Check cost budget ceiling
        if self.cumulative_cost >= self.policy.max_estimated_cost:
            reason_msg = (
                f"COST_CEILING_EXCEEDED: Cumulative cost {self.cumulative_cost} exceeds "
                f"budget {self.policy.max_estimated_cost}"
            )
            if asset is not None:
                flag_asset_for_operator_review(
                    asset,
                    reason=reason_msg,
                    reason_codes=reason_codes,
                    attempt_count=attempt_count,
                )
            return RetryDecision(
                action="ABORT",
                reason=reason_msg,
                attempt_number=attempt_count,
                cumulative_cost=self.cumulative_cost,
                cumulative_runtime_seconds=elapsed_time,
                review_required=True,
                asset_status="needs_review",
            )

        # 5. Determine recommended parameter adjustments for bounded retry
        next_attempt = attempt_count + 1
        adjustments: Dict[str, Any] = {
            "seed": (int(time.time() * 1000) + next_attempt * 7919) % 100000,
            "is_retry": True,
            "attempt_number": next_attempt,
        }
        if any(c in reason_codes for c in ("POOR_PROMPT_ADHERENCE", "VLM_CRITIQUE_BELOW_THRESHOLD")):
            adjustments["guidance_multiplier"] = 1.15
        if "OCR_TEXT_MISMATCH" in reason_codes:
            adjustments["guidance_multiplier"] = 1.20
            adjustments["ocr_emphasis"] = True
        if "PERSONA_IDENTITY_DRIFT" in reason_codes:
            adjustments["identity_weight"] = 1.25
        if any(
            c in reason_codes
            for c in (
                "TEMPORAL_FLICKER_DETECTED",
                "TEMPORAL_CONSISTENCY_BELOW_THRESHOLD",
                "EXTEND_BOUNDARY_DRIFT",
            )
        ):
            adjustments["motion_scale"] = 0.85
            adjustments["denoise"] = 0.55
        if "HIGH_ARTIFACT_DENSITY" in reason_codes:
            adjustments["steps"] = 28
            adjustments["denoise"] = 0.65

        return RetryDecision(
            action="RETRY",
            reason=f"PERMITTED_RETRY: Attempt {next_attempt} permitted within budget",
            attempt_number=next_attempt,
            cumulative_cost=self.cumulative_cost,
            cumulative_runtime_seconds=elapsed_time,
            recommended_adjustments=adjustments,
            review_required=False,
        )

    @staticmethod
    def escalate_asset_for_review(
        asset: Any,
        *,
        reason: Optional[str] = None,
        reason_codes: Optional[List[str]] = None,
        attempt_count: Optional[int] = None,
    ) -> Any:
        return flag_asset_for_operator_review(
            asset,
            reason=reason,
            reason_codes=reason_codes,
            attempt_count=attempt_count,
        )


__all__ = [
    "DEFAULT_EVAL_RETRY_MAX",
    "DEFAULT_PASS_THRESHOLD",
    "BoundedRetryManager",
    "RetryDecision",
    "flag_asset_for_operator_review",
    "get_eval_retry_max",
]
