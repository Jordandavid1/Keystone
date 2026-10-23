"""
KEYSTONE Aikido Prompt-Injection Defense (Python Implementation)
Implements Precedence 7 untrusted data isolation (<untrusted_content>), closing tag escaping,
script/comment scrubbing, threat classification, and post-generation tag sanitization
per Bible §5 Precedence 7 and ORIGINAL_REQUEST R2.
"""

from __future__ import annotations
import re
from typing import Literal, Optional, List, Dict, Any


class AikidoDefenseService:
    """
    Aikido Prompt-Injection Defense Service.
    Isolates untrusted inputs (user requests, scraped benchmarks, OCR, tool responses)
    inside structural delimiters, neutralizes escaping probes, and sanitizes model outputs.
    """

    MALICIOUS_PATTERNS = [
        re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
        re.compile(r"you\s+are\s+(now\s+)?(in\s+developer\s+mode|unrestricted|\bDAN\b)", re.IGNORECASE),
        re.compile(r"\bDAN\s+(mode|capable)\b", re.IGNORECASE),
        re.compile(r"reveal\s+(all\s+)?(system\s+prompts?|passwords?|keys?)", re.IGNORECASE),
        re.compile(r"bypass\s+authority\s+engine", re.IGNORECASE),
        re.compile(r"delete\s+all\s+tables", re.IGNORECASE),
        re.compile(r"disregard\s+(all\s+)?(prior|previous)\s+constraints", re.IGNORECASE),
        re.compile(r"system\s+override", re.IGNORECASE)
    ]

    SUSPICIOUS_PATTERNS = [
        re.compile(r"system\s*:", re.IGNORECASE),
        re.compile(r"<\/?\w+>", re.IGNORECASE)
    ]

    @classmethod
    def quarantine(cls, content: str | None) -> str:
        """
        Encloses untrusted text inside <untrusted_content> delimiters.
        Returns empty string for null or empty input.
        Neutralizes closing tag breakout attempts and scrubs scripts/comments.
        """
        if content is None or content == "":
            return ""

        text = str(content)
        # 1. Scrub script tags
        text = re.sub(r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>", "", text, flags=re.IGNORECASE)
        # 2. Scrub HTML comments
        text = re.sub(r"<!--[\s\S]*?-->", "", text)
        # 3. Escape closing delimiters (case-insensitive and whitespace-tolerant)
        text = re.sub(r"<\/\s*untrusted_content\s*>", "&lt;/untrusted_content&gt;", text, flags=re.IGNORECASE)
        # 4. Escape opening delimiters
        text = re.sub(r"<\s*untrusted_content\s*>", "&lt;untrusted_content&gt;", text, flags=re.IGNORECASE)

        return f"<untrusted_content>\n{text}\n</untrusted_content>"

    @classmethod
    def classify_threat(cls, text: str | None) -> Literal["SAFE", "SUSPICIOUS", "MALICIOUS"]:
        """
        Evaluates input text against known prompt injection and jailbreak signatures.
        """
        if not text or not isinstance(text, str):
            return "SAFE"

        for pat in cls.MALICIOUS_PATTERNS:
            if pat.search(text):
                return "MALICIOUS"

        for pat in cls.SUSPICIOUS_PATTERNS:
            if pat.search(text):
                return "SUSPICIOUS"

        return "SAFE"

    @classmethod
    def post_sanitize(cls, output: str | None) -> str:
        """
        Strips internal delimiter tags that may have leaked into model generation output.
        """
        if not output or not isinstance(output, str):
            return ""
        sanitized = re.sub(r"<\/?\s*untrusted_content\s*>", "", output, flags=re.IGNORECASE)
        sanitized = re.sub(r"&lt;\/?\s*untrusted_content\s*&gt;", "", sanitized, flags=re.IGNORECASE)
        return sanitized.strip()


# Top-level functional convenience wrappers
def quarantine(content: str | None) -> str:
    return AikidoDefenseService.quarantine(content)


def classify_threat(text: str | None) -> Literal["SAFE", "SUSPICIOUS", "MALICIOUS"]:
    return AikidoDefenseService.classify_threat(text)


def post_sanitize(output: str | None) -> str:
    return AikidoDefenseService.post_sanitize(output)
