"""
KEYSTONE Proprietary Policy & Secret Scanner (Bible §29, §38, Invariant 17).
Enforces closed-source security, proprietary rights, and pre-push secret scanning.
Prevents accidental leakage of live credentials, API keys, and private keys.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple


COPYRIGHT_STATEMENT = "Copyright 2026 Jordan Maxwell. All rights reserved."

SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("STRIPE_LIVE_KEY", re.compile(r"sk_live_[a-zA-Z0-9_-]{16,}")),
    ("GITHUB_TOKEN", re.compile(r"ghp_[a-zA-Z0-9_-]{16,}")),
    ("AWS_ACCESS_KEY", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("GOOGLE_API_KEY", re.compile(r"AIzaSy[a-zA-Z0-9_-]{33}")),
    ("RSA_PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----")),
    ("GENERIC_SECRET_TOKEN", re.compile(r"(?:api_secret|master_secret|bearer_token)\s*=\s*['\"][a-zA-Z0-9_=-]{24,}['\"]", re.IGNORECASE))
]


class ProprietaryPolicyService:
    """
    Scans content for credentials, proprietary statements, and closed-source compliance.
    """

    @classmethod
    def get_copyright_statement(cls) -> str:
        return COPYRIGHT_STATEMENT

    @classmethod
    def scan_content_for_secrets(cls, content: str) -> Dict[str, Any]:
        """
        Scans a text string for high-entropy secret patterns.
        """
        if not content:
            return {"hasSecrets": False, "violations": []}

        violations = []
        for name, pattern in SECRET_PATTERNS:
            match = pattern.search(content)
            if match:
                violations.append({
                    "rule": name,
                    "matched": pattern.pattern,
                    "snippet": match.group(0)[:8] + "..."  # Redacted snippet
                })

        return {
            "hasSecrets": len(violations) > 0,
            "violations": violations,
            "matched": violations[0]["matched"] if violations else None
        }

    @classmethod
    def verify_closed_source_compliance(
        cls,
        remote_url: str,
        is_private: bool = True
    ) -> Dict[str, Any]:
        """
        Enforces Invariant 17: Keystone is closed-source; public repositories are strictly prohibited.
        """
        if not is_private:
            return {
                "compliant": False,
                "reason": "PUBLIC_REPOSITORY_PROHIBITED: KEYSTONE must only be hosted on private repositories."
            }

        return {
            "compliant": True,
            "remote_url": remote_url,
            "is_private": True,
            "copyright": COPYRIGHT_STATEMENT
        }


# Global proprietary policy service instance
proprietary_service = ProprietaryPolicyService()
