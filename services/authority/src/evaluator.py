"""
KEYSTONE Authority Engine Component Evaluators (Bible §12, §13).
Implements SafetyPolicyEvaluator, CreditBalanceEvaluator, and ParameterBoundaryEvaluator.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from packages.contracts.src.models import ProposedAction
from services.authority.src.rules import (
    ACTION_TYPES,
    CAPABILITY_NAMESPACES,
    ASPECT_RATIO_WHITELIST,
    IMAGE_MAX_WIDTH,
    IMAGE_MAX_HEIGHT,
    IMAGE_MIN_DIMENSION,
    VIDEO_MAX_RESOLUTION,
    VIDEO_DEFAULT_RESOLUTION,
    VIDEO_RESOLUTIONS,
    VIDEO_MAX_DURATION_SECONDS,
    VIDEO_MIN_DURATION_SECONDS,
    VIDEO_FPS_RANGE,
    STEPS_RANGE,
    GUIDANCE_RANGE,
    DENOISE_RANGE,
    IDENTITY_WEIGHT_RANGE,
    UPSCALE_SCALE_FACTORS,
    FORBIDDEN_TERMS,
    DESTRUCTIVE_SQL_PATTERNS,
    DESTRUCTIVE_SYSTEM_PATTERNS,
    calculate_estimated_credits
)


class EvaluatorResult:
    def __init__(
        self,
        passed: bool,
        reason_codes: Optional[List[str]] = None,
        sanitized_arguments: Optional[Dict[str, Any]] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.passed = passed
        self.reason_codes = reason_codes or []
        self.sanitized_arguments = sanitized_arguments or {}
        self.details = details or {}


def _extract_text_fragments(val: Any) -> List[str]:
    """Recursively extracts string, int, and float representations from nested structures."""
    fragments: List[str] = []
    if isinstance(val, str):
        fragments.append(val)
    elif isinstance(val, (int, float)) and not isinstance(val, bool):
        fragments.append(str(val))
    elif isinstance(val, dict):
        for sub_val in val.values():
            fragments.extend(_extract_text_fragments(sub_val))
    elif isinstance(val, (list, tuple, set)):
        for item in val:
            fragments.extend(_extract_text_fragments(item))
    return fragments


class SafetyPolicyEvaluator:
    """
    Evaluates safety policies, forbidden terms, destructive commands,
    and Aikido delimiter quarantine integrity.
    """

    @classmethod
    def evaluate(cls, action: ProposedAction, untrusted_content: Optional[str] = None) -> EvaluatorResult:
        reason_codes: List[str] = []
        details: Dict[str, Any] = {}

        # Collect text fragments across action
        text_blobs: List[str] = []
        if action.rationale:
            text_blobs.append(str(action.rationale))
        if action.parameters:
            text_blobs.extend(_extract_text_fragments(action.parameters))
        full_text = " ".join(text_blobs).lower()

        # 1. Forbidden terms check
        for term in FORBIDDEN_TERMS:
            if term in full_text:
                reason_codes.append(f"SAFETY_POLICY_VIOLATION: FORBIDDEN_TERM_{term.upper().replace(' ', '_')}")
                details["violating_term"] = term

        # 2. Destructive SQL check
        for pattern in DESTRUCTIVE_SQL_PATTERNS:
            if pattern.search(full_text):
                reason_codes.append("SAFETY_POLICY_VIOLATION: DESTRUCTIVE_SQL_OPERATION")
                details["destructive_sql"] = True
                break

        # 3. Destructive system operations
        for pattern in DESTRUCTIVE_SYSTEM_PATTERNS:
            if pattern.search(full_text):
                reason_codes.append("SAFETY_POLICY_VIOLATION: DESTRUCTIVE_SYSTEM_OPERATION")
                details["destructive_system"] = True
                break

        # 4. Aikido quarantine check
        # Verify that untrusted input doesn't contain unescaped closing delimiters (case-insensitive)
        untrusted_str = str(untrusted_content).lower() if untrusted_content else ""
        combined_text = (full_text + " " + untrusted_str).strip()
        if (
            "</untrusted_content>" in combined_text
            or "</ untrusted_content>" in combined_text
            or bool(re.search(r"</\s*untrusted_content>", combined_text, re.IGNORECASE))
        ):
            reason_codes.append("SAFETY_POLICY_VIOLATION: AIKIDO_DELIMITER_BREAKOUT_ATTEMPT")
            details["delimiter_escape_detected"] = True

        passed = len(reason_codes) == 0
        return EvaluatorResult(passed=passed, reason_codes=reason_codes, details=details)


class CreditBalanceEvaluator:
    """
    Evaluates tenant credit balance and calculates available balance.
    Invariant: available_credits = balance - held_balance >= required_credits.
    """

    @classmethod
    def evaluate(
        cls,
        required_credits: int,
        balance: int,
        held_balance: int = 0
    ) -> EvaluatorResult:
        available_credits = balance - held_balance
        if available_credits < required_credits:
            return EvaluatorResult(
                passed=False,
                reason_codes=["INSUFFICIENT_CREDITS"],
                details={
                    "balance": balance,
                    "held_balance": held_balance,
                    "available_credits": available_credits,
                    "required_credits": required_credits,
                    "deficit": required_credits - available_credits
                }
            )
        return EvaluatorResult(
            passed=True,
            reason_codes=["CREDIT_BALANCE_SUFFICIENT"],
            details={
                "available_credits": available_credits,
                "required_credits": required_credits
            }
        )


class ParameterBoundaryEvaluator:
    """
    Enforces parameter ceilings, whitelists, ranges, and required assets.
    """

    @classmethod
    def evaluate(cls, action: ProposedAction) -> EvaluatorResult:
        reason_codes: List[str] = []
        raw_params = dict(action.parameters or {})
        sanitized = dict(raw_params)

        capability = action.capability
        action_type = action.action_type

        # 1. Action type & capability validation
        if action_type not in ACTION_TYPES:
            reason_codes.append(f"UNKNOWN_ACTION_TYPE: '{action_type}'")
        if capability not in CAPABILITY_NAMESPACES:
            reason_codes.append(f"UNKNOWN_CAPABILITY: '{capability}'")

        # 2. Aspect ratio
        if "aspect_ratio" in sanitized:
            ar = str(sanitized["aspect_ratio"]).strip()
            if ar not in ASPECT_RATIO_WHITELIST:
                reason_codes.append(f"OUT_OF_BOUNDS_PARAMETER: aspect_ratio '{ar}' not in whitelist")
                # Clamp to 16:9 or 1:1 default
                sanitized["aspect_ratio"] = "16:9"

        # 3. Resolution (width, height)
        if "width" in sanitized:
            try:
                w = int(sanitized["width"])
                if w > IMAGE_MAX_WIDTH or w < IMAGE_MIN_DIMENSION:
                    reason_codes.append(f"OUT_OF_BOUNDS_PARAMETER: width {w} outside [{IMAGE_MIN_DIMENSION}, {IMAGE_MAX_WIDTH}]")
                sanitized["width"] = max(IMAGE_MIN_DIMENSION, min(w, IMAGE_MAX_WIDTH))
            except (ValueError, TypeError):
                sanitized["width"] = 1024
                reason_codes.append("INVALID_PARAMETER: width must be integer")

        if "height" in sanitized:
            try:
                h = int(sanitized["height"])
                if h > IMAGE_MAX_HEIGHT or h < IMAGE_MIN_DIMENSION:
                    reason_codes.append(f"OUT_OF_BOUNDS_PARAMETER: height {h} outside [{IMAGE_MIN_DIMENSION}, {IMAGE_MAX_HEIGHT}]")
                sanitized["height"] = max(IMAGE_MIN_DIMENSION, min(h, IMAGE_MAX_HEIGHT))
            except (ValueError, TypeError):
                sanitized["height"] = 1024
                reason_codes.append("INVALID_PARAMETER: height must be integer")

        # 4. Video Parameters
        if capability in ("video.i2v", "video.t2v"):
            if "resolution" in sanitized:
                res = str(sanitized["resolution"]).lower()
                if res not in VIDEO_RESOLUTIONS:
                    reason_codes.append(f"OUT_OF_BOUNDS_PARAMETER: resolution '{res}' not in {VIDEO_RESOLUTIONS}")
                    sanitized["resolution"] = VIDEO_DEFAULT_RESOLUTION
            if "duration_seconds" in sanitized:
                try:
                    dur = int(sanitized["duration_seconds"])
                    if dur > VIDEO_MAX_DURATION_SECONDS or dur < VIDEO_MIN_DURATION_SECONDS:
                        reason_codes.append(
                            f"OUT_OF_BOUNDS_PARAMETER: duration_seconds {dur} outside "
                            f"[{VIDEO_MIN_DURATION_SECONDS}, {VIDEO_MAX_DURATION_SECONDS}]"
                        )
                    sanitized["duration_seconds"] = max(VIDEO_MIN_DURATION_SECONDS, min(dur, VIDEO_MAX_DURATION_SECONDS))
                except (ValueError, TypeError):
                    sanitized["duration_seconds"] = 5

            if "fps" in sanitized:
                try:
                    fps = int(sanitized["fps"])
                    sanitized["fps"] = max(VIDEO_FPS_RANGE[0], min(fps, VIDEO_FPS_RANGE[1]))
                except (ValueError, TypeError):
                    sanitized["fps"] = 24

        # 5. Steps & Guidance & Denoise
        if "steps" in sanitized:
            try:
                steps = int(sanitized["steps"])
                if steps < STEPS_RANGE[0] or steps > STEPS_RANGE[1]:
                    reason_codes.append(f"OUT_OF_BOUNDS_PARAMETER: steps {steps} clamped to {STEPS_RANGE}")
                sanitized["steps"] = max(STEPS_RANGE[0], min(steps, STEPS_RANGE[1]))
            except (ValueError, TypeError):
                sanitized["steps"] = 30

        if "guidance" in sanitized:
            try:
                g = float(sanitized["guidance"])
                if g < GUIDANCE_RANGE[0] or g > GUIDANCE_RANGE[1]:
                    reason_codes.append(f"OUT_OF_BOUNDS_PARAMETER: guidance {g} clamped to {GUIDANCE_RANGE}")
                sanitized["guidance"] = max(GUIDANCE_RANGE[0], min(g, GUIDANCE_RANGE[1]))
            except (ValueError, TypeError):
                sanitized["guidance"] = 7.5

        if "denoise" in sanitized:
            try:
                d = float(sanitized["denoise"])
                if d < DENOISE_RANGE[0] or d > DENOISE_RANGE[1]:
                    reason_codes.append(f"OUT_OF_BOUNDS_PARAMETER: denoise {d} clamped to {DENOISE_RANGE}")
                sanitized["denoise"] = max(DENOISE_RANGE[0], min(d, DENOISE_RANGE[1]))
            except (ValueError, TypeError):
                sanitized["denoise"] = 0.75

        # 6. Upscale Scale Factor
        if capability == "upscale.clarity" and "scale_factor" in sanitized:
            try:
                sf = int(sanitized["scale_factor"])
                if sf not in UPSCALE_SCALE_FACTORS:
                    reason_codes.append(f"OUT_OF_BOUNDS_PARAMETER: scale_factor {sf} not in {UPSCALE_SCALE_FACTORS}")
                    sanitized["scale_factor"] = 2
            except (ValueError, TypeError):
                sanitized["scale_factor"] = 2

        # 7. Asset ID requirements
        if capability in ("image.editing", "video.i2v", "upscale.clarity") and not sanitized.get("input_asset_id"):
            reason_codes.append(f"MISSING_REQUIRED_ASSET: input_asset_id required for {capability}")

        if capability == "identity.flux_pulid" and not sanitized.get("identity_asset_id"):
            reason_codes.append(f"MISSING_REQUIRED_ASSET: identity_asset_id required for {capability}")

        # Parameter checks can either clamp or fail if critical
        fatal_violations = [r for r in reason_codes if r.startswith("UNKNOWN_") or r.startswith("MISSING_REQUIRED_ASSET")]
        passed = len(fatal_violations) == 0

        return EvaluatorResult(
            passed=passed,
            reason_codes=reason_codes,
            sanitized_arguments=sanitized
        )
