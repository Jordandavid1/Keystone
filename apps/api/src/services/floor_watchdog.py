"""
Non-configurable lawful-content floor watchdog (Bible v2 §40.5).

Enforces the hard legal floor upstream of dispatch. Never flags lawful adult
sexual content, consensual erotica, dark fiction, or graphic violence under
`unrestricted` mode.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import List, Literal, Optional, Tuple


RULE_VERSION = "1.0.0"


@dataclass
class FloorVerdict:
    verdict: Literal["pass", "fail", "uncertain"]
    reason_codes: List[str] = field(default_factory=list)
    rule_version: str = RULE_VERSION


# Hard non-configurable lawful-content floor patterns
_HARD_FLOOR_RULES: List[Tuple[str, re.Pattern[str]]] = [
    (
        "FLOOR_CSAM_MINORS",
        re.compile(
            r"\b(csam|child\s*porn|child\s*sexual|minor\s*sexual|underage\s*(?:sex|nude|nsfw|erotica|porn)|loli|shota)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "FLOOR_NCII",
        re.compile(
            r"\b(non-?consensual\s*(?:intimate|nude|porn)|revenge\s*porn|deepfake\s*(?:nude|porn)\s*of\s*real)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "FLOOR_CBRN_TERRORISM_SELFHARM",
        re.compile(
            r"\b(how\s*to\s*(?:make|build|synthesize)\s*(?:sarin|ricin|anthrax|nerve\s*agent|dirty\s*bomb|pipe\s*bomb|explosive)|"
            r"step-?by-?step\s*(?:suicide|self-?harm)\s*instructions)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "FLOOR_CRITICAL_INFRA_CYBER",
        re.compile(
            r"\b(exploit\s*(?:power\s*grid|water\s*treatment|hospital\s*network|nuclear\s*plant)\s*scada|"
            r"ransomware\s*payload\s*for\s*critical\s*infrastructure)\b",
            re.IGNORECASE,
        ),
    ),
]


def _load_extra_rules() -> List[Tuple[str, re.Pattern[str]]]:
    raw = os.environ.get("KEYSTONE_EXTRA_FLOOR_RULES", "").strip()
    if not raw:
        return []
    rules: List[Tuple[str, re.Pattern[str]]] = []
    for idx, token in enumerate(raw.split(",")):
        pattern = token.strip()
        if not pattern:
            continue
        try:
            rules.append((f"FLOOR_EXTRA_{idx}", re.compile(pattern, re.IGNORECASE)))
        except re.error:
            rules.append((f"FLOOR_EXTRA_{idx}", re.compile(re.escape(pattern), re.IGNORECASE)))
    return rules


class FloorWatchdog:
    """Deterministic + upward-only configurable lawful-content floor."""

    def evaluate(
        self,
        prompt_text: str,
        compiled_prompt: Optional[str] = None,
        content_mode: str = "sfw",
    ) -> FloorVerdict:
        # Evaluate only the user/prompt text (and compiled_prompt if distinct);
        # never flag lawful adult erotica, dark fiction, or graphic violence.
        text_to_scan = prompt_text or ""
        if compiled_prompt and compiled_prompt not in text_to_scan:
            text_to_scan = f"{text_to_scan}\n{compiled_prompt}"

        reason_codes: List[str] = []
        for code, pattern in _HARD_FLOOR_RULES:
            if pattern.search(text_to_scan):
                reason_codes.append(code)

        for code, pattern in _load_extra_rules():
            if pattern.search(text_to_scan):
                reason_codes.append(code)

        if reason_codes:
            return FloorVerdict(
                verdict="fail",
                reason_codes=reason_codes,
                rule_version=RULE_VERSION,
            )

        return FloorVerdict(
            verdict="pass",
            reason_codes=[],
            rule_version=RULE_VERSION,
        )


floor_watchdog = FloorWatchdog()


def evaluate(
    prompt_text: str,
    compiled_prompt: Optional[str] = None,
    content_mode: str = "sfw",
) -> FloorVerdict:
    return floor_watchdog.evaluate(
        prompt_text=prompt_text,
        compiled_prompt=compiled_prompt,
        content_mode=content_mode,
    )
