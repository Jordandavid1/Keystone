"""
KEYSTONE Authority Engine Rules & Policies (Bible §12, §13).
Defines parameter boundary ceilings, aspect ratio whitelists, credit calculation formulas,
and safety evaluation rules.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Set, Tuple

# ============================================================================
# Action Types & Capability Namespaces (Bible §12)
# ============================================================================

ACTION_TYPES: Set[str] = {
    "generate",
    "edit",
    "variate",
    "animate",
    "upscale",
    "analyze"
}

CAPABILITY_NAMESPACES: Set[str] = {
    "image.generation",
    "image.editing",
    "video.i2v",
    "video.t2v",
    "identity.flux_pulid",
    "upscale.clarity",
    "analysis.inspect",
    "creative.generation"  # Backward compatibility
}

# ============================================================================
# Parameter Boundaries & Ceilings (Bible §12, §13)
# ============================================================================

ASPECT_RATIO_WHITELIST: Set[str] = {"1:1", "16:9", "9:16", "4:3", "3:4", "21:9"}
IMAGE_MAX_WIDTH: int = 2048
IMAGE_MAX_HEIGHT: int = 2048
IMAGE_MIN_DIMENSION: int = 256

VIDEO_MAX_RESOLUTION: str = "1080p"
VIDEO_DEFAULT_RESOLUTION: str = "720p"
VIDEO_RESOLUTIONS: Set[str] = {"480p", "720p", "1080p"}
VIDEO_MAX_DURATION_SECONDS: int = 10
VIDEO_MIN_DURATION_SECONDS: int = 1
VIDEO_FPS_RANGE: Tuple[int, int] = (8, 30)

STEPS_RANGE: Tuple[int, int] = (1, 50)
GUIDANCE_RANGE: Tuple[float, float] = (1.0, 20.0)
DENOISE_RANGE: Tuple[float, float] = (0.05, 1.0)
IDENTITY_WEIGHT_RANGE: Tuple[float, float] = (0.1, 1.0)
UPSCALE_SCALE_FACTORS: Set[int] = {2, 4}

CONFIRMATION_CREDIT_THRESHOLD: int = 10

# ============================================================================
# Base Credit Costs & Estimation Formula (Bible §13, §27)
# ============================================================================

BASE_CREDIT_TABLE: Dict[str, int] = {
    "image.generation": 1,
    "image.editing": 2,
    "video.i2v": 5,
    "video.t2v": 5,
    "identity.flux_pulid": 3,
    "upscale.clarity": 2,
    "analysis.inspect": 1,
    "creative.generation": 1,
}

def calculate_estimated_credits(capability: str, params: Optional[Dict[str, Any]] = None) -> int:
    """
    Computes deterministic credit cost: Base Credits + Modifiers.
    """
    params = params or {}
    base = BASE_CREDIT_TABLE.get(capability, 1)
    modifiers = 0

    if capability in ("video.i2v", "video.t2v"):
        resolution = params.get("resolution", "720p")
        if resolution == "1080p":
            modifiers += 5
        duration = params.get("duration_seconds", 5)
        if isinstance(duration, (int, float)) and duration > 5:
            modifiers += int(duration - 5)

    elif capability in ("image.generation", "image.editing", "identity.flux_pulid", "creative.generation"):
        w = params.get("width", 1024)
        h = params.get("height", 1024)
        if isinstance(w, (int, float)) and isinstance(h, (int, float)):
            if (w * h) > (1024 * 1024):
                modifiers += 1
        steps = params.get("steps", 30)
        if isinstance(steps, (int, float)) and steps > 35:
            modifiers += 1

    elif capability == "upscale.clarity":
        scale = params.get("scale_factor", 2)
        if scale == 4:
            modifiers += 2

    return base + modifiers

# ============================================================================
# Safety Patterns & Forbidden Terms (Bible §13, §28)
# ============================================================================

FORBIDDEN_TERMS: List[str] = [
    "csam",
    "child sexual",
    "child pornography",
    "pedophil",
    "underage sexual",
    "child exploitation",
    "weapon of mass destruction",
    "biological weapon",
    "chemical weapon",
    "nuclear weapon",
    "dirty bomb",
    "synthesize ricin",
    "weaponized anthrax",
    "ransomware",
    "credential harvesting",
    "keylogger",
    "botnet c2",
    "zero-day exploit payload",
    "terrorist attack instructions",
    "bomb making tutorial"
]

DESTRUCTIVE_SQL_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bDROP\s+TABLE\b", re.IGNORECASE),
    re.compile(r"\bDROP\s+DATABASE\b", re.IGNORECASE),
    re.compile(r"\bTRUNCATE(\s+TABLE)?\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
    re.compile(r"\bALTER\s+TABLE\b.*DROP", re.IGNORECASE),
]

DESTRUCTIVE_SYSTEM_PATTERNS: List[re.Pattern] = [
    re.compile(r"\brm\s+-rf\b", re.IGNORECASE),
    re.compile(r"\bchmod\s+-R\s+(777|a\+rwx)\b", re.IGNORECASE),
    re.compile(r"\bmkfs(\.\w+)?\b", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\bshutdown\s+(-h|-r|now)\b", re.IGNORECASE),
    re.compile(r"\bsystem\s+override\b", re.IGNORECASE),
]
