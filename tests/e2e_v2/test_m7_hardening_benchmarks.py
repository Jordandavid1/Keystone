"""
Milestone M7 E2E Test Suite: Validation, Hardening & Benchmarks (F32–F35)
Empirical verification of Bible §34 Alpha Gate (13 criteria), chaos worker crash recovery,
and BF16 vs FP16 precision benchmarks.
"""

from __future__ import annotations

import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_alpha_gate import verify_alpha_gate, ALPHA_GATE_CRITERIA
from scripts.benchmark_precision import run_precision_benchmark, PINNED_CHECKPOINT
from services.harness.src.chaos_recovery import ChaosRecoveryEngine
from services.harness.src.worker_bridge import worker_bridge
from services.authority.src.credits_ledger import credits_ledger


# ============================================================================
# Section 1: Bible §34 Alpha Gate Verification (F32)
# ============================================================================

class TestAlphaGateVerification:
    """Verifies all 13 Alpha Gate criteria from KEYSTONE Bible §34."""

    def test_alpha_gate_all_thirteen_criteria_pass(self):
        report = verify_alpha_gate()
        assert report["alpha_gate_passed"] is True
        assert report["criteria_count"] == 13
        assert report["passed_count"] == 13

        for crit in ALPHA_GATE_CRITERIA:
            assert crit in report["results"]
            assert report["results"][crit]["status"] == "PASS"


# ============================================================================
# Section 2: Worker Crash Recovery & Adversarial Hardening (F33, F34)
# ============================================================================

class TestWorkerCrashRecovery:
    """Verifies state machine and credit ledger resilience under chaos conditions."""

    def setup_method(self):
        worker_bridge.clear()
        credits_ledger.clear()

    def test_worker_crash_transitions_state_and_preserves_hold(self):
        # 1. Register worker and set up job with provisional credit hold
        worker_bridge.register_worker(
            worker_id="w_kaggle_crash_01",
            worker_type="creative_worker",
            tunnel_url="https://tunnel-crash.ngrok-free.app",
            capabilities=["image.generation"]
        )
        credits_ledger.topup("user_crash_01", 100)
        hold_id = credits_ledger.hold("user_crash_01", 10, job_id="job_crash_01")

        job_record = {
            "job_id": "job_crash_01",
            "state": "running",
            "retry_count": 0,
            "worker_id": "w_kaggle_crash_01"
        }

        # 2. Simulate worker crash mid-execution
        crash_result = ChaosRecoveryEngine.simulate_worker_crash(
            job_record=job_record,
            worker_id="w_kaggle_crash_01",
            hold_id=hold_id
        )

        assert crash_result["recovered"] is True
        assert crash_result["new_state"] == "retry_pending"
        assert crash_result["retry_count"] == 1
        assert crash_result["worker_status"] == "OFFLINE"
        assert crash_result["hold_intact"] is True

        # Ensure worker is marked OFFLINE in bridge
        w = worker_bridge.get_worker("w_kaggle_crash_01")
        assert w["status"] == "OFFLINE"

        # 3. Reassign to healthy replacement worker
        worker_bridge.register_worker(
            worker_id="w_kaggle_backup_02",
            worker_type="creative_worker",
            tunnel_url="https://tunnel-backup.ngrok-free.app",
            capabilities=["image.generation"]
        )
        reassign_res = ChaosRecoveryEngine.recover_and_reassign(
            job_record=job_record,
            replacement_worker_id="w_kaggle_backup_02"
        )
        assert reassign_res["status"] == "REASSIGNED"
        assert job_record["state"] == "running"
        assert job_record["worker_id"] == "w_kaggle_backup_02"

        # 4. Successful completion settles the original hold exactly once
        settled = credits_ledger.settle(hold_id)
        assert settled is True
        assert credits_ledger.get_available_balance("user_crash_01") == 190
        assert credits_ledger.get_held_balance("user_crash_01") == 0


# ============================================================================
# Section 3: BF16 vs FP16 Comparative Benchmark (F35)
# ============================================================================

class TestPrecisionComparativeBenchmark:
    """Verifies pinned checkpoint, hardware metrics, and Invariant 10 adherence."""

    def test_precision_benchmark_bf16_remains_authorized_default(self):
        benchmark = run_precision_benchmark()

        assert benchmark["model"] == PINNED_CHECKPOINT
        assert benchmark["authorized_default"] == "BF16"
        assert benchmark["bf16"]["authorized_default"] is True
        assert benchmark["fp16"]["authorized_default"] is False

        # Invariant 10 check: FP16 evaluated but not automatically promoted
        assert "INVARIANT_10_SATISFIED" in benchmark["compliance"]
        assert benchmark["bf16"]["structured_output_validity_rate"] > 0.98
        assert benchmark["bf16"]["tokens_per_sec"] > 10.0
