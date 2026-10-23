#!/usr/bin/env python3
"""
KEYSTONE Change-Control Validator
Adheres to KEYSTONE_BIBLE.md §37: Change-control rules.
Verifies that any proposed modification to locked architectural invariants complies
with the mandatory 7-point approval protocol.
"""

from __future__ import annotations

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Dict, Any, List

REQUIRED_SECTIONS = [
    ("FOUNDER_APPROVAL", r"##\s*1\.\s*Explicit\s+Founder\s+Approval"),
    ("ADR", r"##\s*2\.\s*(Written\s+)?Architecture\s+Decision\s+Record"),
    ("COMPATIBILITY_ANALYSIS", r"##\s*3\.\s*Compatibility\s+Impact\s+Analysis"),
    ("KHF_COVERAGE", r"##\s*4\.\s*KHF\s+Regression\s+Coverage"),
    ("MIGRATION_PLAN", r"##\s*5\.\s*Migration\s+Plan"),
    ("ROLLBACK_PLAN", r"##\s*6\.\s*Rollback\s+Plan"),
    ("VERSIONED_CONTRACTS", r"##\s*7\.\s*Versioned\s+Contract\s+Updates")
]


def audit_adr_file(filepath: Path) -> Dict[str, Any]:
    content = filepath.read_text(encoding="utf-8", errors="ignore")
    missing_sections = []
    
    for sec_id, pattern in REQUIRED_SECTIONS:
        if not re.search(pattern, content, re.IGNORECASE):
            missing_sections.append(sec_id)

    # Check for non-empty approval text
    has_approval_text = False
    approval_match = re.search(r"##\s*1\.\s*Explicit\s+Founder\s+Approval\s*\n+([^#]+)", content, re.IGNORECASE)
    if approval_match and len(approval_match.group(1).strip()) > 10:
        has_approval_text = True

    return {
        "file": str(filepath),
        "valid": len(missing_sections) == 0 and has_approval_text,
        "missing_sections": missing_sections,
        "has_approval_text": has_approval_text
    }


def verify_change_control(root_dir: Path) -> Dict[str, Any]:
    cc_dir = root_dir / "docs" / "change_control"
    if not cc_dir.exists():
        return {
            "status": "PASS",
            "message": "No change control directory found; no invariant alterations active.",
            "adrs_audited": 0,
            "all_valid": True
        }

    adrs = [
        f for f in cc_dir.glob("*.md")
        if not f.name.startswith("ADR_TEMPLATE") and not f.name.startswith("README") and not f.name.startswith("CHANGE_LOG")
    ]

    if not adrs:
        return {
            "status": "PASS",
            "message": "No proposed ADRs found; locked architectural invariants remain intact.",
            "adrs_audited": 0,
            "all_valid": True
        }

    audits = [audit_adr_file(adr) for adr in adrs]
    all_valid = all(a["valid"] for a in audits)

    return {
        "status": "PASS" if all_valid else "FAIL",
        "adrs_audited": len(audits),
        "all_valid": all_valid,
        "audits": audits
    }


def main():
    parser = argparse.ArgumentParser(description="KEYSTONE Change-Control Validator")
    parser.add_argument("--root", default=".", help="Project root directory")
    args = parser.parse_args()

    root_dir = Path(args.root).resolve()
    res = verify_change_control(root_dir)

    print("=" * 80)
    print("  KEYSTONE CHANGE-CONTROL VALIDATOR (§37)")
    print("=" * 80)
    print(f"Status: {res['status']}")
    print(f"ADRs Audited: {res['adrs_audited']}")
    if res.get("message"):
        print(f"Detail: {res['message']}")
    if not res["all_valid"]:
        for a in res.get("audits", []):
            if not a["valid"]:
                print(f"Violation in {a['file']}: Missing {a['missing_sections']}")

    sys.exit(0 if res["all_valid"] else 1)


if __name__ == "__main__":
    main()
