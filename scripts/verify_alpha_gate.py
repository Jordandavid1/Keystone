#!/usr/bin/env python3
"""
KEYSTONE Bible v2 §34 Alpha Gate Verification — LIVE PR10 HARNESS (ADR-004 / ADR-005).

Executes real subprocess checks across:
  1. tests/acceptance/test_bible_acceptance.py (mapped 1-to-1 to all 15 §34 criteria)
  2. scripts/verify_invariants.py --strict
  3. scripts/verify_change_control.py --root .
  4. npm test (preserved plan.v1 JS identity contract)
  5. Next.js Studio TypeScript check (`npx tsc --noEmit`)

Zero fabricated PASS verdicts (Bible v2 §2 Invariant 12).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parent.parent

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

CRITERIA_TEST_MAP: Dict[str, List[str]] = {
    "1. account creation works": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
    ],
    "2. projects and sessions persist": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
    ],
    "3. uploads persist": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
    ],
    "4. users communicate naturally with KEYSTONE": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
        "tests/acceptance/test_bible_acceptance.py::TestBibleIdentityAcceptance::test_identity_02_plan_v1_output_remains_valid",
    ],
    "5. KEYSTONE owns prompt compilation": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleIdentityAcceptance::test_identity_05_standard_chat_and_reasoning_compilers_pass",
        "tests/acceptance/test_bible_acceptance.py::TestBibleIdentityAcceptance::test_identity_06_model_facing_calls_carry_keystone_provenance",
        "tests/acceptance/test_bible_acceptance.py::TestBibleAuthorityAcceptance::test_authority_07_worker_cannot_mutate_approved_prompt_or_mode",
    ],
    "6. cognition produces valid structured actions": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleAuthorityAcceptance::test_authority_02_raw_model_to_worker_fails",
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
    ],
    "7. at least image and image-to-video workflows work": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
    ],
    "8. jobs survive page refresh": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
    ],
    "9. outputs appear in the correct project": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
    ],
    "10. credits are not charged twice": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_02_failures_preserve_session_and_worker_crash_recovery",
    ],
    "11. failures preserve the session": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_02_failures_preserve_session_and_worker_crash_recovery",
    ],
    "12. customers can download outputs": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
    ],
    "13. admins can diagnose jobs": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleFullEndToEndLoopAndCrashRecovery::test_e2e_01_register_project_session_upload_chat_persona_generate_download_admin",
    ],
    "14. content modes resolve and enforce (SFW default, UNRESTRICTED behind the age gate)": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleIdentityAcceptance::test_identity_03_all_sixteen_playbooks_mode_scoped",
        "tests/acceptance/test_bible_acceptance.py::TestBibleContentModesAndAgeGateAcceptance::test_content_mode_01_unverified_403_and_stage1_stage2_age_gate",
        "tests/acceptance/test_bible_acceptance.py::TestBibleContentModesAndAgeGateAcceptance::test_content_mode_03_lawful_unrestricted_passes_and_mature_gallery_isolated",
    ],
    "15. the floor rejects its fixture and writes its audit row": [
        "tests/acceptance/test_bible_acceptance.py::TestBibleContentModesAndAgeGateAcceptance::test_content_mode_02_floor_violation_422_audit_and_zero_dispatch",
    ],
}


def _resolve_python() -> str:
    venv_py = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def _run_cmd(cmd: List[str], *, cwd: Path = REPO_ROOT, shell: bool = False) -> Dict[str, Any]:
    t0 = time.perf_counter()
    proc = subprocess.run(
        cmd,
        cwd=str(cwd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=300,
        shell=shell,
    )
    elapsed = round(time.perf_counter() - t0, 2)
    return {
        "passed": proc.returncode == 0,
        "exit_code": proc.returncode,
        "elapsed_s": elapsed,
        "output": proc.stdout or "",
    }


def _parse_passed_node_ids(stdout: str) -> Set[str]:
    passed: Set[str] = set()
    pattern = re.compile(r"^(tests/acceptance/test_bible_acceptance\.py::\S+)\s+PASSED\b")
    for line in stdout.splitlines():
        norm = line.strip().replace("\\", "/")
        match = pattern.match(norm)
        if match:
            passed.add(match.group(1))
    return passed


def verify_alpha_gate(*, include_slow_subchecks: bool = True) -> Dict[str, Any]:
    """
    Execute real Bible §34 & §35 acceptance checks via live subprocesses.
    Marks a criterion PASS strictly when its mapped real pytest node IDs appear as PASSED
    and pytest exits 0. Zero fabricated PASS dicts.
    """
    py_bin = _resolve_python()
    basetemp_dir = REPO_ROOT / ".pytest_tmp_alphagate"
    try:
        shutil.rmtree(basetemp_dir, ignore_errors=True)
        accept_res = _run_cmd(
            [
                py_bin,
                "-m",
                "pytest",
                "-v",
                "--tb=short",
                "--basetemp=.pytest_tmp_alphagate",
                "tests/acceptance/test_bible_acceptance.py",
            ],
            cwd=REPO_ROOT,
            shell=False,
        )
    finally:
        shutil.rmtree(basetemp_dir, ignore_errors=True)

    passed_nodes = _parse_passed_node_ids(accept_res["output"])
    acceptance_ok = bool(accept_res["passed"])

    results: Dict[str, Dict[str, Any]] = {}
    passed_count = 0
    for crit in ALPHA_GATE_CRITERIA:
        required_nodes = CRITERIA_TEST_MAP.get(crit, [])
        missing = [node for node in required_nodes if node not in passed_nodes]
        crit_ok = acceptance_ok and bool(required_nodes) and not missing
        if crit_ok:
            passed_count += 1
        results[crit] = {
            "status": "PASS" if crit_ok else "FAIL",
            "verified_tests": required_nodes if crit_ok else [],
            "missing_tests": missing,
            "evidence": (
                f"Verified via {len(required_nodes)} live acceptance test(s) (pytest exit {accept_res['exit_code']})"
                if crit_ok
                else f"Acceptance failure or unverified tests (exit {accept_res['exit_code']}, missing={missing})"
            ),
        }

    checks: Dict[str, Dict[str, Any]] = {
        "acceptance_suite": {
            "passed": acceptance_ok,
            "exit_code": accept_res["exit_code"],
            "elapsed_s": accept_res["elapsed_s"],
            "passed_node_count": len(passed_nodes),
            "output_tail": "\n".join(accept_res["output"].splitlines()[-20:]),
        }
    }

    subchecks_ok = True
    if include_slow_subchecks:
        inv_res = _run_cmd([py_bin, "scripts/verify_invariants.py", "--strict"], shell=False)
        cc_res = _run_cmd([py_bin, "scripts/verify_change_control.py", "--root", "."], shell=False)
        npm_res = _run_cmd(["npm", "test"], cwd=REPO_ROOT, shell=True)
        tsc_res = _run_cmd(["npx", "tsc", "--noEmit"], cwd=REPO_ROOT / "apps" / "web", shell=True)

        checks["verify_invariants_strict"] = {
            "passed": inv_res["passed"],
            "exit_code": inv_res["exit_code"],
            "elapsed_s": inv_res["elapsed_s"],
            "output_tail": "\n".join(inv_res["output"].splitlines()[-15:]),
        }
        checks["verify_change_control"] = {
            "passed": cc_res["passed"],
            "exit_code": cc_res["exit_code"],
            "elapsed_s": cc_res["elapsed_s"],
        }
        checks["npm_test_identity"] = {
            "passed": npm_res["passed"],
            "exit_code": npm_res["exit_code"],
            "elapsed_s": npm_res["elapsed_s"],
        }
        checks["nextjs_typecheck"] = {
            "passed": tsc_res["passed"],
            "exit_code": tsc_res["exit_code"],
            "elapsed_s": tsc_res["elapsed_s"],
            "output_tail": "\n".join(tsc_res["output"].splitlines()[-15:]) if not tsc_res["passed"] else "",
        }
        subchecks_ok = all(
            c["passed"]
            for c in (
                checks["verify_invariants_strict"],
                checks["verify_change_control"],
                checks["npm_test_identity"],
                checks["nextjs_typecheck"],
            )
        )

    all_ok = (passed_count == len(ALPHA_GATE_CRITERIA)) and acceptance_ok and subchecks_ok
    return {
        "status": "PASS" if all_ok else "FAIL",
        "alpha_gate_passed": all_ok,
        "criteria_count": len(ALPHA_GATE_CRITERIA),
        "passed_count": passed_count,
        "results": results,
        "checks": checks,
    }


if __name__ == "__main__":
    report = verify_alpha_gate(include_slow_subchecks=True)
    if "--json" in sys.argv:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 80)
        print("  KEYSTONE BIBLE v2 §34 ALPHA GATE — LIVE EMPIRICAL VERIFICATION (PR10)")
        print("=" * 80)
        print(f"Overall Status : {report['status']} ({report['passed_count']}/{report['criteria_count']} criteria verified)\n")
        for crit in ALPHA_GATE_CRITERIA:
            res = report["results"][crit]
            print(f"  [{res['status']:4s}] {crit}")
        print("\nSubprocess Checks:")
        for cname, cval in report["checks"].items():
            tag = "PASS" if cval["passed"] else "FAIL"
            print(f"  [{tag:4s}] {cname} ({cval['elapsed_s']}s)")
            if not cval["passed"] and cval.get("output_tail"):
                print(cval["output_tail"])
        print("=" * 80)
    sys.exit(0 if report["alpha_gate_passed"] else 1)
