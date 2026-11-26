#!/usr/bin/env python3
"""
KEYSTONE v2 Structural Lint & Invariant Guard (ADR-004 / ADR-005, Bible v2 §2 & §37).

Replaces the retired v1 69-file SHA-256 byte-freeze and Bible content checksum lock.
Checks run in either BLOCKING or ADVISORY (warn-only) mode and flip to blocking
explicitly as their target milestones land:

  - bible_sync           : advisory at O0.5 -> BLOCKING from O2 (Bible v2 landing)
  - license_policy       : advisory at O0.5 -> BLOCKING from O17 (housekeeping)
  - no_duplicate_engines : advisory until PR6 -> BLOCKING from PR6 (1 compiler, 1 Comfy client, 1 web UI)
  - manifest_accounting  : advisory until PR8 (quantization sanctioned; flips blocking once local Qwen-embedding registers in CapabilityManifest)
  - banned_strings       : BLOCKING (zero placeholders / sample inputs / silent fallbacks)
  - change_control       : BLOCKING (§37 ADR traceability)
  - npm_test_identity    : BLOCKING (preserved plan.v1 / PromptAnatomy identity tests)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Checks enforced as blocking right now (O17 + PR6 + PR8: all checks blocking).
# Checks not in this set run in advisory (warn-only) mode unless --strict is passed.
BLOCKING_CHECKS: Set[str] = {
    "bible_sync",
    "license_policy",
    "no_duplicate_engines",
    "manifest_accounting",
    "banned_strings",
    "change_control",
    "npm_test_identity",
}


def compute_sha256(filepath: Path) -> Tuple[int, str]:
    data = filepath.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest().upper()


def verify_bible_sync(root_dir: Path) -> Dict[str, Any]:
    """
    Bible v2 §37 sync check (replaces v1 SHA-256 content freeze).
    Ensures root KEYSTONE_BIBLE.md and docs/KEYSTONE_BIBLE.md both exist and are byte-identical.
    """
    root_bible = root_dir / "KEYSTONE_BIBLE.md"
    docs_bible = root_dir / "docs" / "KEYSTONE_BIBLE.md"

    root_present = root_bible.exists()
    docs_present = docs_bible.exists()
    root_size, root_sha = compute_sha256(root_bible) if root_present else (None, None)
    docs_size, docs_sha = compute_sha256(docs_bible) if docs_present else (None, None)
    in_sync = bool(root_present and docs_present and root_sha == docs_sha and root_size == docs_size)

    return {
        "valid": in_sync,
        "root_present": root_present,
        "docs_present": docs_present,
        "root_size": root_size,
        "docs_size": docs_size,
        "root_sha256": root_sha,
        "docs_sha256": docs_sha,
        "in_sync": in_sync,
    }


def verify_no_duplicate_engines(root_dir: Path) -> Dict[str, Any]:
    """
    ADR-005 structural lint: one file/engine per concept.
    Flags parallel prompt engines, ComfyUI clients, and web UIs until consolidation PRs complete.
    """
    findings: List[Dict[str, Any]] = []

    prompt_engines = [
        p
        for p in (
            "packages/prompt-engine/src/engine.js",
            "packages/prompt_engine/compiler.py",
            "apps/api/src/keystone/prompting.py",
        )
        if (root_dir / p).exists()
    ]
    if len(prompt_engines) > 2:  # JS compatibility engine + 1 unified Python compiler is the target ceiling
        findings.append(
            {
                "category": "duplicate_prompt_engines",
                "paths": prompt_engines,
                "detail": "Multiple Python prompt compilers present; consolidate to one authoritative Python compiler.",
            }
        )

    comfy_clients = [
        p
        for p in (
            "services/comfy/src/client.py",
            "apps/api/src/creative/h3.py",
            "services/comfy/src/adapters.py",
        )
        if (root_dir / p).exists()
    ]
    if len(comfy_clients) > 1:
        findings.append(
            {
                "category": "duplicate_comfy_clients",
                "paths": comfy_clients,
                "detail": "Multiple ComfyUI/H3 clients present; consolidate behind one fabric adapter.",
            }
        )

    legacy_web_uis = [
        p
        for p in (
            "apps/web/index.html",
            "apps/web/app.js",
            "apps/web/styles.css",
            "apps/web/legacy",
        )
        if (root_dir / p).exists()
    ]
    if legacy_web_uis:
        active_web_uis = [
            p for p in ("apps/web/app/page.tsx",) if (root_dir / p).exists()
        ] + legacy_web_uis
        findings.append(
            {
                "category": "duplicate_web_uis",
                "paths": active_web_uis,
                "detail": "Legacy HTML SPA / apps/web/legacy still present alongside Next.js Studio (retired in PR6).",
            }
        )

    return {
        "valid": len(findings) == 0,
        "finding_count": len(findings),
        "findings": findings,
    }


def verify_manifest_accounting(root_dir: Path) -> Dict[str, Any]:
    """
    Bible v2 §2 Invariants 2, 5–7 & ADR-005: replaces the retired quantization ban
    with capability-manifest accounting (GGUF/int8/fp8 quantization is sanctioned
    when disclosed in operator config / capability manifests) and verifies that
    `cognition.local_embeddings` is registered in `CapabilityManifest` with
    model_id, quantization, dimension=1024, and license.
    """
    issues: List[str] = []
    manifest_candidates = [
        root_dir / "apps" / "api" / "src" / "creative" / "h3_manifest.py",
        root_dir / "services" / "comfy" / "src" / "client.py",
        root_dir / "services" / "cognition" / "src" / "embeddings.py",
    ]
    present_manifests = [str(p.relative_to(root_dir)).replace("\\", "/") for p in manifest_candidates if p.exists()]
    if not present_manifests:
        issues.append("No capability manifest modules found.")

    embeddings_file = root_dir / "services" / "cognition" / "src" / "embeddings.py"
    comfy_client_file = root_dir / "services" / "comfy" / "src" / "client.py"
    local_embeddings_registered = False
    local_embeddings_metadata: Dict[str, Any] = {}

    if not embeddings_file.exists():
        issues.append("Missing services/cognition/src/embeddings.py for cognition.local_embeddings CapabilityManifest.")
    else:
        emb_text = embeddings_file.read_text(encoding="utf-8", errors="replace")
        if "cognition.local_embeddings" not in emb_text or "CapabilityManifest" not in emb_text:
            issues.append("services/cognition/src/embeddings.py does not declare cognition.local_embeddings inside CapabilityManifest.")
        elif comfy_client_file.exists() and "cognition.local_embeddings" not in comfy_client_file.read_text(encoding="utf-8", errors="replace"):
            issues.append("services/comfy/src/client.py does not register cognition.local_embeddings in ADAPTER_REGISTRY / CapabilityManifest.")
        else:
            try:
                if str(root_dir) not in sys.path:
                    sys.path.insert(0, str(root_dir))
                from services.cognition.src.embeddings import KEYSTONE_EMBEDDING_DIM, get_embedding_manifest
                from services.comfy.src.client import list_capabilities

                emb_manifest = get_embedding_manifest()
                meta = dict(emb_manifest.metadata or {})
                local_embeddings_metadata = meta
                registered_ids = {m.capability_id for m in list_capabilities()}

                if emb_manifest.capability_id != "cognition.local_embeddings":
                    issues.append(f"Expected capability_id 'cognition.local_embeddings', got '{emb_manifest.capability_id}'.")
                if "cognition.local_embeddings" not in registered_ids:
                    issues.append("cognition.local_embeddings is not registered in services.comfy.src.client.list_capabilities().")
                if int(KEYSTONE_EMBEDDING_DIM) != 1024 or int(meta.get("dimension", 0)) != 1024:
                    issues.append(f"cognition.local_embeddings dimension must be 1024, got {meta.get('dimension')}.")
                for required_meta_key in ("model_id", "quantization", "dimension", "license"):
                    if not meta.get(required_meta_key):
                        issues.append(f"cognition.local_embeddings CapabilityManifest missing metadata '{required_meta_key}'.")

                local_embeddings_registered = (
                    emb_manifest.capability_id == "cognition.local_embeddings"
                    and "cognition.local_embeddings" in registered_ids
                    and int(meta.get("dimension", 0)) == 1024
                    and bool(meta.get("model_id"))
                    and bool(meta.get("quantization"))
                    and bool(meta.get("license"))
                )
            except Exception as exc:
                issues.append(f"Failed to verify cognition.local_embeddings CapabilityManifest: {exc}")

    # Ensure closed-source aligned vendor models are not invoked in active Python runtime paths.
    closed_vendor_pattern = re.compile(r"\b(gemini-2\.5-flash|gpt-4o|claude-3|text-embedding-005)\b", re.IGNORECASE)
    for rel_dir in ("apps/api/src", "services/cognition", "services/authority", "services/harness", "services/comfy"):
        base = root_dir / rel_dir
        if not base.exists():
            continue
        for py_file in sorted(base.rglob("*.py")):
            if "__pycache__" in py_file.parts:
                continue
            text = py_file.read_text(encoding="utf-8", errors="replace")
            if closed_vendor_pattern.search(text):
                issues.append(f"Closed aligned vendor model reference in {py_file.relative_to(root_dir)}")

    # Flag retired BigQuery/intelligence research track until archived per ADR-004 D13.
    for retired_dir in ("services/intelligence", "infrastructure/bigquery"):
        if (root_dir / retired_dir).exists():
            issues.append(f"Retired research track still present in core monorepo: {retired_dir} (ADR-004 D13).")

    return {
        "valid": len(issues) == 0,
        "present_manifests": present_manifests,
        "local_embeddings_registered": local_embeddings_registered,
        "local_embeddings_manifest": local_embeddings_metadata,
        "quantization_sanctioned": True,
        "issues": issues,
    }


def verify_license_policy(root_dir: Path) -> Dict[str, Any]:
    """
    Bible v2 §29 & ADR-004 R4: repository must declare proprietary closed-source license,
    with no Apache-2.0 or MIT license twins.
    """
    issues: List[str] = []
    license_file = root_dir / "LICENSE"
    if not license_file.exists():
        issues.append("Root LICENSE file missing.")
    else:
        txt = license_file.read_text(encoding="utf-8", errors="replace")
        if "Apache License" in txt or "MIT License" in txt:
            issues.append("Root LICENSE still contains a permissive OSS license instead of Bible §29 proprietary notice.")
        if "Proprietary" not in txt and "proprietary" not in txt:
            issues.append("Root LICENSE missing proprietary copyright notice (Bible §29).")

    for pkg_rel in ("package.json", "services/intelligence/package.json"):
        pkg_path = root_dir / pkg_rel
        if not pkg_path.exists():
            continue
        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
            lic = str(data.get("license", "")).strip()
            if lic.upper() in {"MIT", "APACHE-2.0", "ISC", "BSD-3-CLAUSE"}:
                issues.append(f"{pkg_rel} declares permissive license '{lic}' (must be UNLICENSED / PROPRIETARY).")
        except Exception as exc:
            issues.append(f"Failed to parse {pkg_rel}: {exc}")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
    }


def verify_banned_strings(root_dir: Path, run_behavioral_suite: bool = True) -> Dict[str, Any]:
    """Enforces zero-placeholder, zero-sample-input, live-only output invariants."""
    if str(root_dir) not in sys.path:
        sys.path.insert(0, str(root_dir))
    from tests.test_no_placeholders_invariants import scan_zero_placeholder_invariants

    static_res = scan_zero_placeholder_invariants(root_dir)
    behavioral_passed = True
    behavioral_summary = "skipped"

    if run_behavioral_suite:
        import shutil as _shutil

        inv_tmp = root_dir / ".pytest_tmp_inv"
        _shutil.rmtree(inv_tmp, ignore_errors=True)
        try:
            proc = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "pytest",
                    "--basetemp=.pytest_tmp_inv",
                    str(root_dir / "tests" / "test_no_placeholders_invariants.py"),
                    "-v",
                ],
                cwd=str(root_dir),
                capture_output=True,
                text=True,
                timeout=120,
            )
        finally:
            _shutil.rmtree(inv_tmp, ignore_errors=True)
        behavioral_passed = proc.returncode == 0
        out = proc.stdout + proc.stderr
        behavioral_summary = "\n".join(out.splitlines()[-8:])

    return {
        "valid": bool(static_res["valid"]) and behavioral_passed,
        "static_scan": static_res,
        "behavioral_passed": behavioral_passed,
        "behavioral_summary": behavioral_summary,
    }


def verify_change_control_audit(root_dir: Path) -> Dict[str, Any]:
    """Runs verify_change_control.py to enforce §37 ADR traceability."""
    proc = subprocess.run(
        [sys.executable, str(root_dir / "scripts" / "verify_change_control.py"), "--root", str(root_dir)],
        cwd=str(root_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )
    return {
        "valid": proc.returncode == 0,
        "exit_code": proc.returncode,
        "output": (proc.stdout + proc.stderr).strip(),
    }


def run_command_check(cmd: List[str], cwd: Path) -> Dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True,
            timeout=120,
        )
        return {
            "command": " ".join(cmd),
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "success": (proc.returncode == 0),
        }
    except Exception as exc:
        return {
            "command": " ".join(cmd),
            "exit_code": -1,
            "stdout": "",
            "stderr": str(exc),
            "success": False,
        }


def verify_npm_test(root_dir: Path) -> Dict[str, Any]:
    res = run_command_check(["npm", "test"], root_dir)
    output = res["stdout"] + res["stderr"]
    has_pass = ("pass 3" in output or "3 Pass" in output or "✔" in output)
    has_fail = bool(re.search(r"\bfail\s+[1-9]\d*", output, re.IGNORECASE)) or (res["exit_code"] != 0)
    passed = res["success"] and has_pass and not has_fail
    return {
        "valid": passed,
        "passed": passed,
        "command": "npm test",
        "exit_code": res["exit_code"],
        "output_summary": "\n".join(
            [line for line in output.splitlines() if "pass" in line.lower() or "tests" in line.lower() or "✔" in line][:5]
        ),
    }


def run_lint(root_dir: Path, skip_tests: bool = False, strict: bool = False) -> Dict[str, Any]:
    checks: Dict[str, Dict[str, Any]] = {
        "bible_sync": verify_bible_sync(root_dir),
        "no_duplicate_engines": verify_no_duplicate_engines(root_dir),
        "manifest_accounting": verify_manifest_accounting(root_dir),
        "license_policy": verify_license_policy(root_dir),
        "banned_strings": verify_banned_strings(root_dir, run_behavioral_suite=not skip_tests),
        "change_control": verify_change_control_audit(root_dir),
        "npm_test_identity": (
            {"valid": True, "passed": True, "skipped": True}
            if skip_tests
            else verify_npm_test(root_dir)
        ),
    }

    blocking_failures: List[str] = []
    advisory_warnings: List[str] = []

    for name, res in checks.items():
        is_blocking = strict or (name in BLOCKING_CHECKS)
        res["mode"] = "blocking" if is_blocking else "advisory"
        if not res["valid"]:
            if is_blocking:
                blocking_failures.append(name)
            else:
                advisory_warnings.append(name)

    all_passed = len(blocking_failures) == 0
    return {
        "lint_version": "2.0",
        "status": "PASS" if all_passed else "FAIL",
        "all_passed": all_passed,
        "strict": strict,
        "blocking_checks": sorted(BLOCKING_CHECKS),
        "blocking_failures": blocking_failures,
        "advisory_warnings": advisory_warnings,
        "checks": checks,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="KEYSTONE v2 Structural Lint & Invariant Guard")
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running npm test and behavioral pytest checks")
    parser.add_argument("--strict", action="store_true", help="Treat advisory checks as blocking")
    args = parser.parse_args()

    root_dir = Path(args.root).resolve()
    result = run_lint(root_dir, skip_tests=args.skip_tests, strict=args.strict)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 80)
        print("  KEYSTONE v2 STRUCTURAL LINT & INVARIANT GUARD (ADR-004 / ADR-005)")
        print("=" * 80)
        print(f"Overall Status   : {'[PASS]' if result['all_passed'] else '[FAIL]'} (blocking failures: {len(result['blocking_failures'])}, advisory warnings: {len(result['advisory_warnings'])})\n")
        for name, res in result["checks"].items():
            tag = "PASS" if res["valid"] else ("FAIL" if res["mode"] == "blocking" else "WARN")
            print(f"  [{tag:4s}] ({res['mode']:8s}) {name}")
        if result["advisory_warnings"]:
            print(f"\nAdvisory warnings (not yet blocking): {', '.join(result['advisory_warnings'])}")
        if result["blocking_failures"]:
            print(f"\nBlocking failures: {', '.join(result['blocking_failures'])}")
        print("=" * 80)

    sys.exit(0 if result["all_passed"] else 1)


if __name__ == "__main__":
    main()
