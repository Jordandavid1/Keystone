#!/usr/bin/env python3
"""
KEYSTONE Bible §34 Alpha Gate Verification — RETIRED v1 STUB (ADR-004 / ADR-005).

The previous v1 implementation hardcoded "PASS" dictionaries for 10 of 13 criteria
without exercising the API, database, storage, or workers. Per Bible v2 §2 Invariant 12
("Real Tests Only") and ADR-005, all fabricated PASS dictionaries have been permanently
deleted in O0.5.

This gate fails closed until PR10 delivers real HTTP + PostgreSQL + worker integration
tests verifying all 15 Bible v2 §34 Alpha Gate criteria.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List

ALPHA_GATE_CRITERIA: List[str] = [
    "1. account creation works",
    "2. projects and sessions persist",
    "3. uploads persist",
    "4. users communicate naturally with KEYSTONE",
    "5. KEYSTONE owns prompt compilation",
    "6. cognition produces valid structured actions",
    "7. at least image and image-to-video workflows work",
    "8. jobs survive page refresh",
    "9. outputs appear in the correct project",
    "10. credits are not charged twice",
    "11. failures preserve the session",
    "12. customers can download outputs",
    "13. admins can diagnose jobs",
    "14. content modes resolve and enforce (SFW default, UNRESTRICTED behind the age gate)",
    "15. the floor rejects its fixture and writes its audit row",
]


def verify_alpha_gate() -> Dict[str, Any]:
    """
    Fail-closed placeholder until PR10 wires real HTTP/DB integration checks.
    Never fabricates PASS verdicts.
    """
    results = {
        criterion: {
            "status": "NOT_RUN",
            "evidence": "Retired v1 fabricated PASS stub (ADR-004/ADR-005 O0.5); real HTTP/DB check scheduled for PR10.",
        }
        for criterion in ALPHA_GATE_CRITERIA
    }
    return {
        "status": "RETIRED_PENDING_PR10",
        "alpha_gate_passed": False,
        "criteria_count": len(ALPHA_GATE_CRITERIA),
        "passed_count": 0,
        "results": results,
    }


if __name__ == "__main__":
    report = verify_alpha_gate()
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 72)
        print("  KEYSTONE BIBLE §34 ALPHA GATE — v1 FAKE-PASS STUB RETIRED (O0.5)")
        print("=" * 72)
        print("Status: RETIRED_PENDING_PR10 (fail-closed; 0/15 real checks wired yet)")
        print("See ADR-004 / ADR-005 and Bible v2 §2 Invariant 12 (Real Tests Only).")
        print("=" * 72)
    sys.exit(2)
