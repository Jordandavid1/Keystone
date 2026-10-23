#!/usr/bin/env python3
"""
KEYSTONE Milestone M1 Adversarial Stress Test Suite
Empirical validation of:
  - F07 Storage key sanitization, path traversal defense, and signed URL verification
  - F08 Lineage DAG cycle detection, diamond graphs, self-references, relationship types
  - F09 Job State Machine illegal jumps, terminal breakouts, transition matrix, idempotency
"""

import os
import sys
import time
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple

# Reconfigure stdout to UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Add repo root to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.api.src.storage.service import (
    generate_storage_key,
    generate_signed_url,
    validate_signed_url,
    LocalStorageProvider,
    MAX_EXPIRY_SECONDS,
    DEFAULT_EXPIRY_SECONDS,
)
from apps.api.src.lineage.dag import (
    LineageDAG,
    VALID_RELATIONSHIPS,
)
from apps.api.src.jobs.state_machine import (
    JobState,
    JobStateMachine,
    STATES,
    TERMINAL_STATES,
    ALLOWED_TRANSITIONS,
    transition,
    normalize_state,
)

results: List[Dict[str, Any]] = []

def record(test_id: str, area: str, description: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {test_id}: {description} {f'({details})' if details else ''}")
    results.append({
        "test_id": test_id,
        "area": area,
        "description": description,
        "passed": passed,
        "details": details
    })


# ============================================================================
# AREA 1: Storage Key Sanitization & Path Traversal Attacks
# ============================================================================

def run_storage_path_traversal_tests():
    print("\n--- Running Area 1: Storage Key Sanitization & Path Traversal Attacks ---")

    # 1.1 Classic POSIX path traversal
    key = generate_storage_key("usr_1", "ast_1", "../../../etc/passwd.png")
    is_safe = (".." not in key) and key.endswith("passwd.png")
    record("ST-01", "Storage", "POSIX path traversal in filename sanitized", is_safe, f"key={key}")

    # 1.2 Windows backslash traversal
    key = generate_storage_key("usr_1", "ast_1", r"..\..\..\windows\system32\cmd.exe")
    is_safe = (".." not in key) and ("cmd.exe" in key or "exe" in key)
    record("ST-02", "Storage", "Windows backslash path traversal in filename sanitized", is_safe, f"key={key}")

    # 1.3 Null byte injection
    key = generate_storage_key("usr_1", "ast_1", "malicious.png\x00.exe")
    is_safe = ("\x00" not in key)
    record("ST-03", "Storage", "Null byte stripped from filename", is_safe, f"key={key}")

    # 1.4 URL-encoded path traversal
    key = generate_storage_key("usr_1", "ast_1", "%2e%2e%2f%2e%2e%2fetc%2fpasswd")
    is_safe = ("/" not in key.split("/")[-1]) and (".." not in key)
    record("ST-04", "Storage", "URL-encoded traversal characters sanitized", is_safe, f"key={key}")

    # 1.5 Mixed slash traversal
    key = generate_storage_key("usr_1", "ast_1", r"../../..\windows/system32\drivers/etc/hosts")
    is_safe = (".." not in key)
    record("ST-05", "Storage", "Mixed forward and backward slash traversal sanitized", is_safe, f"key={key}")

    # 1.6 Filename consisting solely of dots: '....'
    key = generate_storage_key("usr_1", "ast_1", "....")
    # Does '....' resolve to parent directory or asset folder?
    provider = LocalStorageProvider()
    resolved = provider._resolve_path(key)
    # Target should be inside base_dir/tenants/usr_1/assets/ast_1
    expected_parent = (provider.base_dir / "tenants/usr_1/assets/ast_1").resolve()
    # In Windows, '....' normalizes to '.' or empty, meaning resolved path IS the directory itself
    dots_flaw = (resolved == expected_parent)
    record("ST-06", "Storage", "Filename of all dots '....' path resolution check", not dots_flaw,
           f"Key '{key}' resolved to folder '{resolved}' rather than a file" if dots_flaw else f"Resolved: {resolved}")

    # 1.7 Filename of '..' directly
    key_dotdot = generate_storage_key("usr_1", "ast_1", "..")
    resolved_dotdot = provider._resolve_path(key_dotdot)
    expected_assets_dir = (provider.base_dir / "tenants/usr_1/assets").resolve()
    dotdot_escaped = (resolved_dotdot == expected_assets_dir)
    record("ST-07", "Storage", "Filename '..' escapes asset_id directory to parent assets folder", not dotdot_escaped,
           f"Key '{key_dotdot}' escaped asset dir and resolved to '{resolved_dotdot}'" if dotdot_escaped else "Did not escape")

    # 1.8 User ID path traversal injection
    key_user_traversal = generate_storage_key("../../admin", "ast_1", "avatar.png")
    user_traversal_present = (".." in key_user_traversal)
    record("ST-08", "Storage", "User ID parameter traversal injection check", not user_traversal_present,
           f"generate_storage_key does not sanitize user_id: '{key_user_traversal}'" if user_traversal_present else "Sanitized")

    # 1.9 LocalStorageProvider Sibling Prefix Traversal (CWE-22)
    # Tests if key '../storage_evil/file.txt' escapes base_dir via prefix startswith flaw
    try:
        resolved_sibling = provider._resolve_path("../storage_evil/file.txt")
        # Check if resolved_sibling is actually inside base_dir
        base_dir_resolved = provider.base_dir.resolve()
        is_inside = False
        try:
            resolved_sibling.relative_to(base_dir_resolved)
            is_inside = True
        except ValueError:
            is_inside = False
        prefix_vulnerability = not is_inside
    except ValueError as e:
        prefix_vulnerability = False
        resolved_sibling = str(e)

    record("ST-09", "Storage", "LocalStorageProvider sibling directory prefix traversal vulnerability (CWE-22)",
           not prefix_vulnerability,
           f"VULNERABILITY CONFIRMED: '../storage_evil/file.txt' resolved outside base_dir to '{resolved_sibling}' without rejection"
           if prefix_vulnerability else "Properly rejected traversal outside base_dir")

    # 1.10 LocalStorageProvider Absolute Path / Root Traversal rejection
    try:
        provider._resolve_path("/etc/passwd")
        # If no error, check where it went
        resolved_root = provider._resolve_path("/etc/passwd")
        is_safe_root = resolved_root.is_relative_to(provider.base_dir.resolve())
    except ValueError:
        is_safe_root = True
    record("ST-10", "Storage", "LocalStorageProvider absolute root path /etc/passwd contained", is_safe_root)

    # 1.11 Deep parent traversal ../../../../../../../../../etc/shadow rejection
    try:
        provider._resolve_path("../../../../../../../../../etc/shadow")
        escaped_shadow = True
    except ValueError:
        escaped_shadow = False
    record("ST-11", "Storage", "LocalStorageProvider deep parent traversal ../../etc/shadow rejected", not escaped_shadow)


# ============================================================================
# AREA 2: Signed URL Forgery & Expiration Stress Tests
# ============================================================================

def run_signed_url_stress_tests():
    print("\n--- Running Area 2: Signed URL Forgery & Expiration Stress Tests ---")

    test_key = "tenants/usr_test/assets/ast_test/hero.png"

    # 2.1 Legitimate signed URL generation
    url = generate_signed_url(test_key, expiry_seconds=900)
    val = validate_signed_url(url)
    record("SU-01", "Signed URL", "Legitimate 900s signed URL generation and validation", val["valid"] and val["storage_key"] == test_key)

    # 2.2 Maximum expiry ceiling boundary test (3600s allowed, 3601s rejected)
    url_3600 = generate_signed_url(test_key, expiry_seconds=3600)
    val_3600 = validate_signed_url(url_3600)
    record("SU-02", "Signed URL", "Exact 3600s maximum expiry accepted", val_3600["valid"])

    expiry_exceeded = False
    try:
        generate_signed_url(test_key, expiry_seconds=3601)
    except ValueError as e:
        if "EXPIRY_EXCEEDED" in str(e):
            expiry_exceeded = True
    record("SU-03", "Signed URL", "Expiry 3601s strictly rejected with EXPIRY_EXCEEDED", expiry_exceeded)

    # 2.3 Non-positive expiry (0, -100)
    zero_rejected = False
    try:
        generate_signed_url(test_key, expiry_seconds=0)
    except ValueError as e:
        if "INVALID_EXPIRY" in str(e):
            zero_rejected = True
    record("SU-04", "Signed URL", "Expiry 0s rejected with INVALID_EXPIRY", zero_rejected)

    neg_rejected = False
    try:
        generate_signed_url(test_key, expiry_seconds=-100)
    except ValueError as e:
        if "INVALID_EXPIRY" in str(e):
            neg_rejected = True
    record("SU-05", "Signed URL", "Negative expiry -100s rejected with INVALID_EXPIRY", neg_rejected)

    # 2.4 Altered signature detection (single character tamper)
    tampered_sig_url = url[:-1] + ("0" if url[-1] != "0" else "1")
    tampered_caught = False
    try:
        validate_signed_url(tampered_sig_url)
    except ValueError as e:
        if "INVALID_SIGNATURE" in str(e):
            tampered_caught = True
    record("SU-06", "Signed URL", "Single character tampered signature rejected with INVALID_SIGNATURE", tampered_caught)

    # 2.5 Truncated signature
    truncated_url = url[:-10]
    trunc_caught = False
    try:
        validate_signed_url(truncated_url)
    except ValueError as e:
        if "INVALID_SIGNATURE" in str(e):
            trunc_caught = True
    record("SU-07", "Signed URL", "Truncated signature rejected with INVALID_SIGNATURE", trunc_caught)

    # 2.6 Forged signature with random hex
    forged_sig = "a" * 64
    forged_url = f"https://storage.keystone.internal/{test_key}?expires={int(time.time())+500}&signature={forged_sig}"
    forged_caught = False
    try:
        validate_signed_url(forged_url)
    except ValueError as e:
        if "INVALID_SIGNATURE" in str(e):
            forged_caught = True
    record("SU-08", "Signed URL", "Completely forged 64-hex signature rejected with INVALID_SIGNATURE", forged_caught)

    # 2.7 Expired URL replay attack (short expiry replay)
    short_url = generate_signed_url(test_key, expiry_seconds=1)
    time.sleep(1.2)  # Wait for expiry
    expired_caught = False
    try:
        validate_signed_url(short_url)
    except ValueError as e:
        if "URL_EXPIRED" in str(e):
            expired_caught = True
    record("SU-09", "Signed URL", "Expired URL replay rejected with URL_EXPIRED", expired_caught)

    # 2.8 Negative expiry timestamp in query parameter
    url_neg_ts = f"https://storage.keystone.internal/{test_key}?expires=-500&signature=abcdef"
    neg_ts_caught = False
    try:
        validate_signed_url(url_neg_ts)
    except ValueError as e:
        if "URL_EXPIRED" in str(e) or "INVALID_EXPIRY" in str(e):
            neg_ts_caught = True
    record("SU-10", "Signed URL", "Negative expiration timestamp in query string rejected", neg_ts_caught)

    # 2.9 Non-numeric expiration parameter
    url_bad_num = f"https://storage.keystone.internal/{test_key}?expires=notanumber&signature=abcdef"
    bad_num_caught = False
    try:
        validate_signed_url(url_bad_num)
    except ValueError as e:
        if "INVALID_EXPIRY" in str(e):
            bad_num_caught = True
    record("SU-11", "Signed URL", "Non-numeric expiration parameter rejected with INVALID_EXPIRY", bad_num_caught)

    # 2.10 Storage key swapping attack (replay signature against different asset)
    diff_key = "tenants/usr_other/assets/ast_secret/confidential.png"
    swapped_url = url.replace(test_key, diff_key)
    swap_caught = False
    try:
        validate_signed_url(swapped_url)
    except ValueError as e:
        if "INVALID_SIGNATURE" in str(e):
            swap_caught = True
    record("SU-12", "Signed URL", "Signature replay across different storage key rejected", swap_caught)


# ============================================================================
# AREA 3: Lineage DAG Cycle Stress Tests & Complex Topologies
# ============================================================================

def run_lineage_dag_stress_tests():
    print("\n--- Running Area 3: Lineage DAG Cycle Stress Tests & Complex Topologies ---")

    # 3.1 Self-referential edge prevention
    dag = LineageDAG()
    self_ref_caught = False
    try:
        dag.add_relationship("node_A", "node_A", "source")
    except ValueError as e:
        if "SELF_REFERENTIAL_LINEAGE" in str(e):
            self_ref_caught = True
    record("DAG-01", "Lineage DAG", "Self-referential edge (A -> A) rejected with SELF_REFERENTIAL_LINEAGE", self_ref_caught)

    # 3.2 Invalid relationship types
    for bad_type in ["parent", "CHILD", "SOURCE", "", "invalid_rel", "1234"]:
        dag_bad = LineageDAG()
        bad_type_caught = False
        try:
            dag_bad.add_relationship("node_A", "node_B", bad_type)
        except ValueError as e:
            if "INVALID_RELATIONSHIP_TYPE" in str(e):
                bad_type_caught = True
        record(f"DAG-02-{bad_type}", "Lineage DAG", f"Invalid relationship type '{bad_type}' rejected with INVALID_RELATIONSHIP_TYPE", bad_type_caught)

    # 3.3 All 8 valid relationship types accepted
    dag_valid = LineageDAG()
    all_valid_pass = True
    for idx, rtype in enumerate(VALID_RELATIONSHIPS):
        edge = dag_valid.add_relationship(f"parent_{idx}", f"child_{idx}", rtype)
        if edge["relationship_type"] != rtype:
            all_valid_pass = False
    record("DAG-03", "Lineage DAG", "All 8 canonical relationship types successfully accepted", all_valid_pass)

    # 3.4 Direct 2-node cycle (A -> B -> A)
    dag_2 = LineageDAG()
    dag_2.add_relationship("A", "B", "source")
    cycle_2_caught = False
    try:
        dag_2.add_relationship("B", "A", "edit")
    except ValueError as e:
        if "CYCLE_DETECTED" in str(e):
            cycle_2_caught = True
    record("DAG-04", "Lineage DAG", "Direct 2-node cycle (A -> B -> A) rejected with CYCLE_DETECTED", cycle_2_caught)

    # 3.5 Deep cycle: A -> B -> C -> D -> E -> A
    dag_deep = LineageDAG()
    dag_deep.add_relationship("A", "B", "source")
    dag_deep.add_relationship("B", "C", "edit")
    dag_deep.add_relationship("C", "D", "variation")
    dag_deep.add_relationship("D", "E", "animation")
    deep_cycle_caught = False
    try:
        dag_deep.add_relationship("E", "A", "upscale")
    except ValueError as e:
        if "CYCLE_DETECTED" in str(e):
            deep_cycle_caught = True
    record("DAG-05", "Lineage DAG", "Deep 5-node cycle (A->B->C->D->E->A) rejected with CYCLE_DETECTED", deep_cycle_caught)

    # 3.6 Deep cycle to intermediate node (E -> C)
    inter_cycle_caught = False
    try:
        dag_deep.add_relationship("E", "C", "reference")
    except ValueError as e:
        if "CYCLE_DETECTED" in str(e):
            inter_cycle_caught = True
    record("DAG-06", "Lineage DAG", "Deep cycle to intermediate node (E -> C) rejected with CYCLE_DETECTED", inter_cycle_caught)

    # 3.7 Ultra-deep 50-node chain cycle stress test
    dag_50 = LineageDAG()
    for i in range(49):
        dag_50.add_relationship(f"node_{i}", f"node_{i+1}", "intermediate")
    ultra_cycle_caught = False
    try:
        dag_50.add_relationship("node_49", "node_0", "selected-final")
    except ValueError as e:
        if "CYCLE_DETECTED" in str(e):
            ultra_cycle_caught = True
    record("DAG-07", "Lineage DAG", "Ultra-deep 50-node chain cycle (node_49 -> node_0) rejected with CYCLE_DETECTED", ultra_cycle_caught)

    # 3.8 Diamond DAG topology (A -> B, A -> C, B -> D, C -> D)
    # Diamond is a VALID DAG (no directed cycles)
    dag_diamond = LineageDAG()
    dag_diamond.add_relationship("A", "B", "source")
    dag_diamond.add_relationship("A", "C", "source")
    dag_diamond.add_relationship("B", "D", "edit")
    dag_diamond.add_relationship("C", "D", "variation")
    diamond_accepted = len(dag_diamond.edges) == 4
    record("DAG-08", "Lineage DAG", "Diamond DAG topology successfully accepted without false cycle alarms", diamond_accepted)

    # 3.9 Diamond cycle attempt (D -> A, D -> B, D -> C)
    for target in ["A", "B", "C"]:
        diamond_cycle_caught = False
        try:
            dag_diamond.add_relationship("D", target, "upscale")
        except ValueError as e:
            if "CYCLE_DETECTED" in str(e):
                diamond_cycle_caught = True
        record(f"DAG-09-{target}", "Lineage DAG", f"Diamond closing edge (D -> {target}) rejected with CYCLE_DETECTED", diamond_cycle_caught)

    # 3.10 Disconnected graphs bridged and cycled
    dag_bridge = LineageDAG()
    # Graph 1: X1 -> X2 -> X3
    dag_bridge.add_relationship("X1", "X2", "source")
    dag_bridge.add_relationship("X2", "X3", "edit")
    # Graph 2: Y1 -> Y2 -> Y3
    dag_bridge.add_relationship("Y1", "Y2", "source")
    dag_bridge.add_relationship("Y2", "Y3", "edit")
    # Bridge X3 -> Y1
    dag_bridge.add_relationship("X3", "Y1", "reference")
    # Now path is X1 -> X2 -> X3 -> Y1 -> Y2 -> Y3. Adding Y3 -> X1 must be caught!
    bridge_cycle_caught = False
    try:
        dag_bridge.add_relationship("Y3", "X1", "animation")
    except ValueError as e:
        if "CYCLE_DETECTED" in str(e):
            bridge_cycle_caught = True
    record("DAG-10", "Lineage DAG", "Cross-component bridge cycle (Y3 -> X1) rejected with CYCLE_DETECTED", bridge_cycle_caught)

    # 3.11 Traversal correctness (Ancestors & Descendants on Diamond)
    ancestors_D = set(dag_diamond.get_ancestors("D"))
    descendants_A = set(dag_diamond.get_descendants("A"))
    record("DAG-11", "Lineage DAG", "Diamond DAG ancestors of D correctly resolves {'A', 'B', 'C'}", ancestors_D == {"A", "B", "C"}, f"got {ancestors_D}")
    record("DAG-12", "Lineage DAG", "Diamond DAG descendants of A correctly resolves {'B', 'C', 'D'}", descendants_A == {"B", "C", "D"}, f"got {descendants_A}")

    # 3.13 Boundary traversals (root has no ancestors, leaf has no descendants)
    record("DAG-13", "Lineage DAG", "Root node ancestors empty list", dag_diamond.get_ancestors("A") == [])
    record("DAG-14", "Lineage DAG", "Leaf node descendants empty list", dag_diamond.get_descendants("D") == [])
    record("DAG-15", "Lineage DAG", "Non-existent node ancestors empty list", dag_diamond.get_ancestors("ghost_node") == [])


# ============================================================================
# AREA 4: Job State Machine Illegal Jumps & Terminal State Locks
# ============================================================================

def run_job_state_machine_stress_tests():
    print("\n--- Running Area 4: Job State Machine Illegal Jumps & Terminal State Locks ---")

    # 4.1 Prompt-mandated illegal jumps
    # CREATED -> COMPLETED
    jump1_caught = False
    try:
        transition("CREATED", "COMPLETED")
    except ValueError as e:
        if "ILLEGAL_TRANSITION" in str(e):
            jump1_caught = True
    record("SM-01", "State Machine", "Illegal jump CREATED -> COMPLETED rejected with ILLEGAL_TRANSITION", jump1_caught)

    # Terminal breakout COMPLETED -> RUNNING
    breakout1_caught = False
    try:
        transition("COMPLETED", "RUNNING")
    except ValueError as e:
        if "ILLEGAL_TRANSITION" in str(e) and "terminal state" in str(e):
            breakout1_caught = True
    record("SM-02", "State Machine", "Terminal breakout COMPLETED -> RUNNING rejected with ILLEGAL_TRANSITION", breakout1_caught)

    # Terminal breakout CANCELLED -> VALIDATING
    breakout2_caught = False
    try:
        transition("CANCELLED", "VALIDATING")
    except ValueError as e:
        if "ILLEGAL_TRANSITION" in str(e) and "terminal state" in str(e):
            breakout2_caught = True
    record("SM-03", "State Machine", "Terminal breakout CANCELLED -> VALIDATING rejected with ILLEGAL_TRANSITION", breakout2_caught)

    # 4.2 Terminal state breakout tests for ALL terminal states
    all_terminals_locked = True
    for term in TERMINAL_STATES:
        for non_term in [s for s in STATES if s != term]:
            try:
                transition(term, non_term)
                all_terminals_locked = False
                print(f"FAILED: Allowed breakout from {term} to {non_term}")
            except ValueError as e:
                if "ILLEGAL_TRANSITION" not in str(e):
                    all_terminals_locked = False
    record("SM-04", "State Machine", "All 4 terminal states strictly lock all exit transitions (48/48 blocked)", all_terminals_locked)

    # 4.3 Full 13x13 transition matrix verification (169 combinations)
    matrix_verified = True
    for s1 in STATES:
        allowed_list = ALLOWED_TRANSITIONS.get(s1, [])
        for s2 in STATES:
            if s1 == s2:
                # Idempotent no-op
                try:
                    res = transition(s1, s2)
                    if res != s1:
                        matrix_verified = False
                except Exception:
                    matrix_verified = False
            elif s2 in allowed_list:
                # Must succeed
                try:
                    res = transition(s1, s2)
                    if res != s2:
                        matrix_verified = False
                except Exception:
                    matrix_verified = False
            else:
                # Must raise ILLEGAL_TRANSITION
                try:
                    transition(s1, s2)
                    matrix_verified = False
                    print(f"FAILED: Should have blocked transition {s1} -> {s2}")
                except ValueError as e:
                    if "ILLEGAL_TRANSITION" not in str(e):
                        matrix_verified = False
                except Exception:
                    matrix_verified = False
    record("SM-05", "State Machine", "Exhaustive 13x13 matrix verification (169 state pairs strictly verified)", matrix_verified)

    # 4.4 Unknown current state & unknown next state
    unknown_curr_caught = False
    try:
        transition("NON_EXISTENT_STATE", "RUNNING")
    except ValueError as e:
        if "UNKNOWN_CURRENT_STATE" in str(e):
            unknown_curr_caught = True
    record("SM-06", "State Machine", "Unknown current state rejected with UNKNOWN_CURRENT_STATE", unknown_curr_caught)

    unknown_next_caught = False
    try:
        transition("CREATED", "NON_EXISTENT_STATE")
    except ValueError as e:
        if "UNKNOWN_NEXT_STATE" in str(e):
            unknown_next_caught = True
    record("SM-07", "State Machine", "Unknown next state rejected with UNKNOWN_NEXT_STATE", unknown_next_caught)

    # 4.5 Worker lifecycle alias normalization
    aliases_tested = True
    alias_map = {
        "COMPILING_PROMPT": "VALIDATING",
        "PROPOSED_ACTION_PENDING": "PLANNING",
        "AWAITING_AUTHORIZATION": "AUTHORIZING",
        "ENVELOPE_ISSUED": "QUEUED",
        "DISPATCHED_TO_WORKER": "RUNNING",
        "WORKER_RUNNING": "RUNNING",
        "EVALUATING_OUTPUT": "VALIDATING_OUTPUT",
        "compiling_prompt": "VALIDATING",
        " worker_running ": "RUNNING",
    }
    for alias, canonical in alias_map.items():
        if normalize_state(alias) != canonical:
            aliases_tested = False
    record("SM-08", "State Machine", "Worker lifecycle aliases normalized to canonical states", aliases_tested)

    # 4.6 JobStateMachine instance lifecycle & retry limit
    sm = JobStateMachine("job_test_123", initial_state="CREATED", max_attempts=3)
    record("SM-09", "State Machine", "Initial state CREATED and not terminal", (sm.current_state == "CREATED" and not sm.is_terminal))

    # Happy path transition via instance
    sm.transition("VALIDATING")
    sm.transition("PLANNING")
    sm.transition("AUTHORIZING")
    sm.transition("QUEUED")
    sm.transition("RUNNING")
    sm.transition("VALIDATING_OUTPUT")
    record("SM-10", "State Machine", "Instance traversed happy path to VALIDATING_OUTPUT", sm.current_state == "VALIDATING_OUTPUT")

    # Retry loop: VALIDATING_OUTPUT -> RETRY_PENDING -> QUEUED
    sm.transition("RETRY_PENDING")
    sm.increment_attempt()
    sm.transition("QUEUED")
    record("SM-11", "State Machine", "Instance traversed retry loop back to QUEUED", sm.current_state == "QUEUED" and sm.current_attempt == 2)

    # Replan loop: RUNNING -> VALIDATING_OUTPUT -> REPLAN_REQUIRED -> PLANNING
    sm.transition("RUNNING")
    sm.transition("VALIDATING_OUTPUT")
    sm.transition("REPLAN_REQUIRED")
    sm.transition("PLANNING")
    record("SM-12", "State Machine", "Instance traversed replan loop back to PLANNING", sm.current_state == "PLANNING")

    # Completion to terminal state
    sm.transition("AUTHORIZING")
    sm.transition("QUEUED")
    sm.transition("RUNNING")
    sm.transition("VALIDATING_OUTPUT")
    sm.transition("COMPLETED")
    record("SM-13", "State Machine", "Job completed and is_terminal is True", sm.current_state == "COMPLETED" and sm.is_terminal)

    # Terminal state transition rejection on instance
    inst_term_blocked = False
    try:
        sm.transition("RUNNING")
    except ValueError as e:
        if "ILLEGAL_TRANSITION" in str(e):
            inst_term_blocked = True
    record("SM-14", "State Machine", "Instance transition out of terminal COMPLETED rejected", inst_term_blocked)


def main():
    print("================================================================================")
    print("  KEYSTONE MILESTONE M1 EMPIRICAL ADVERSARIAL STRESS TEST HARNESS")
    print("================================================================================")

    run_storage_path_traversal_tests()
    run_signed_url_stress_tests()
    run_lineage_dag_stress_tests()
    run_job_state_machine_stress_tests()

    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print("\n================================================================================")
    print(f"  ADVERSARIAL STRESS TEST SUMMARY: {passed}/{total} PASSED ({failed} FAILED)")
    print("================================================================================")

    if failed > 0:
        print("\nFAILED TESTS / VULNERABILITIES DETECTED:")
        for r in results:
            if not r["passed"]:
                print(f"  - [{r['test_id']}] {r['area']}: {r['description']}")
                if r['details']:
                    print(f"      Details: {r['details']}")
    else:
        print("\nALL ADVERSARIAL TESTS PASSED — NO ATTACK SURFACE VULNERABILITIES DETECTED")

    return failed

if __name__ == "__main__":
    sys.exit(main())
