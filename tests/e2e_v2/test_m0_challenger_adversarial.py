"""
KEYSTONE Milestone M0: Adversarial Challenger Test Suite
========================================================
Empirical stress-testing of:
1. infrastructure/migrations/versions/0002_keystone_full_schema.sql
   - 23-table schema totality (12 base + 11 additive)
   - Column types and foreign key definitions
   - Check constraints: credit_ledger (amount > 0, transaction_type IN (...)),
     credit_accounts (balance >= 0, held_balance >= 0, status),
     asset_relationships (8 valid relationship types, composite unique)
   - Credit ledger immutability trigger simulation (UPDATE and DELETE prohibited)
2. scripts/verify_invariants.py
   - Behavior under simulated invariant breaches (tampered Bible, altered manifests,
     prohibited cognition models, test runner failures)
   - Bug/edge-case identification: string literal search vs regex for test failures,
     and skip-tests behavior.
"""

import os
import sys
import json
import sqlite3
import tempfile
import subprocess
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
MIGRATION_0001 = ROOT_DIR / "infrastructure" / "migrations" / "versions" / "0001_core.sql"
MIGRATION_0002 = ROOT_DIR / "infrastructure" / "migrations" / "versions" / "0002_keystone_full_schema.sql"
VERIFY_SCRIPT = ROOT_DIR / "scripts" / "verify_invariants.py"

# Add scripts directory to path for direct module testing
sys.path.insert(0, str(ROOT_DIR / "scripts"))
import verify_invariants


# ==============================================================================
# 1. DDL Static & Semantic Analysis Tests
# ==============================================================================

class TestDatabaseDDLAnalysis:
    """Verifies the DDL specifications against Keystone Bible §21, §22, §27."""

    def test_twenty_three_table_totality(self):
        """Verify the union of 0001_core.sql and 0002_keystone_full_schema.sql produces 23 tables."""
        assert MIGRATION_0001.exists(), f"Missing {MIGRATION_0001}"
        assert MIGRATION_0002.exists(), f"Missing {MIGRATION_0002}"

        content_0001 = MIGRATION_0001.read_text(encoding="utf-8")
        content_0002 = MIGRATION_0002.read_text(encoding="utf-8")

        import re
        tables_0001 = set(re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", content_0001, re.IGNORECASE))
        tables_0002 = set(re.findall(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", content_0002, re.IGNORECASE))

        expected_0001 = {
            "users", "projects", "sessions", "messages", "assets", "requests",
            "cognitive_runs", "authority_decisions", "jobs", "compiled_prompts",
            "harness_runs", "audit_events"
        }
        expected_0002 = {
            "subscriptions", "api_keys", "credit_accounts", "credit_ledger",
            "request_assets", "generation_attempts", "attempt_assets",
            "user_feedback", "usage_records", "configuration_bundles",
            "asset_relationships"
        }

        assert tables_0001 == expected_0001, f"0001 mismatch: {tables_0001.symmetric_difference(expected_0001)}"
        assert tables_0002 == expected_0002, f"0002 mismatch: {tables_0002.symmetric_difference(expected_0002)}"
        
        total_tables = tables_0001.union(tables_0002)
        assert len(total_tables) == 23, f"Expected 23 tables, found {len(total_tables)}: {total_tables}"

    def test_credit_ledger_ddl_constraints(self):
        """Verify credit_ledger check constraints and trigger definitions."""
        content = MIGRATION_0002.read_text(encoding="utf-8")

        # 1. amount > 0 check constraint
        assert "amount BIGINT NOT NULL CHECK (amount > 0)" in content

        # 2. transaction types: DEPOSIT, HOLD, SETTLEMENT, RELEASE, REFUND
        assert "transaction_type TEXT NOT NULL CHECK (transaction_type IN ('DEPOSIT', 'HOLD', 'SETTLEMENT', 'RELEASE', 'REFUND'))" in content

        # 3. balance checks
        assert "balance_after BIGINT NOT NULL CHECK (balance_after >= 0)" in content
        assert "held_balance_after BIGINT NOT NULL CHECK (held_balance_after >= 0)" in content

        # 4. Trigger function definition with RAISE EXCEPTION
        assert "CREATE OR REPLACE FUNCTION keystone_credit_ledger_prevent_modification()" in content
        assert "RAISE EXCEPTION 'credit_ledger is strictly append-only. UPDATE and DELETE operations are forbidden.';" in content

        # 5. Trigger on BEFORE UPDATE OR DELETE
        assert "CREATE TRIGGER trg_credit_ledger_immutable" in content
        assert "BEFORE UPDATE OR DELETE ON credit_ledger" in content
        assert "EXECUTE FUNCTION keystone_credit_ledger_prevent_modification();" in content

    def test_asset_relationships_ddl_constraints(self):
        """Verify asset_relationships 8 valid types and composite unique constraint."""
        content = MIGRATION_0002.read_text(encoding="utf-8")

        # 8 valid relationship types
        valid_types = [
            'source', 'edit', 'variation', 'animation',
            'upscale', 'reference', 'selected-final', 'intermediate'
        ]
        type_check_pattern = (
            "CHECK (relationship_type IN ('source', 'edit', 'variation', "
            "'animation', 'upscale', 'reference', 'selected-final', 'intermediate'))"
        )
        assert type_check_pattern in content

        # Composite unique constraint
        assert "UNIQUE(parent_asset_id, child_asset_id, relationship_type)" in content

        # Foreign keys with cascade
        assert "parent_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE" in content
        assert "child_asset_id UUID NOT NULL REFERENCES assets(id) ON DELETE CASCADE" in content


# ==============================================================================
# 2. SQLite In-Memory Simulation of Immutability and Constraints
# ==============================================================================

class TestCreditLedgerSimulation:
    """Simulates credit_ledger behaviour with SQLite triggers and check constraints."""

    @pytest.fixture
    def db(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()

        # Create base credit_accounts
        cur.execute("""
            CREATE TABLE credit_accounts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL UNIQUE,
                balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
                held_balance INTEGER NOT NULL DEFAULT 0 CHECK (held_balance >= 0),
                currency TEXT NOT NULL DEFAULT 'credits',
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'frozen', 'suspended', 'closed'))
            );
        """)

        # Create credit_ledger mirroring PostgreSQL semantics
        cur.execute("""
            CREATE TABLE credit_ledger (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL REFERENCES credit_accounts(id) ON DELETE RESTRICT,
                transaction_type TEXT NOT NULL CHECK (transaction_type IN ('DEPOSIT', 'HOLD', 'SETTLEMENT', 'RELEASE', 'REFUND')),
                amount INTEGER NOT NULL CHECK (amount > 0),
                balance_after INTEGER NOT NULL CHECK (balance_after >= 0),
                held_balance_after INTEGER NOT NULL CHECK (held_balance_after >= 0),
                reference_id TEXT,
                reference_type TEXT CHECK (reference_type IS NULL OR reference_type IN ('job', 'request', 'stripe_checkout', 'hold', 'manual_adjustment', 'subscription_grant')),
                idempotency_key TEXT,
                description TEXT
            );
        """)

        # Partial unique index on idempotency_key
        cur.execute("""
            CREATE UNIQUE INDEX idx_credit_ledger_idempotency
            ON credit_ledger(idempotency_key)
            WHERE idempotency_key IS NOT NULL;
        """)

        # Mirror the PostgreSQL keystone_credit_ledger_prevent_modification trigger
        cur.execute("""
            CREATE TRIGGER trg_credit_ledger_prevent_update
            BEFORE UPDATE ON credit_ledger
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'credit_ledger is strictly append-only. UPDATE and DELETE operations are forbidden.');
            END;
        """)

        cur.execute("""
            CREATE TRIGGER trg_credit_ledger_prevent_delete
            BEFORE DELETE ON credit_ledger
            FOR EACH ROW
            BEGIN
                SELECT RAISE(ABORT, 'credit_ledger is strictly append-only. UPDATE and DELETE operations are forbidden.');
            END;
        """)

        # Populate a default account
        cur.execute("INSERT INTO credit_accounts (id, user_id, balance) VALUES ('acc-1', 'usr-1', 1000);")
        conn.commit()

        yield conn
        conn.close()

    def test_valid_deposit_and_hold_inserts(self, db):
        cur = db.cursor()
        cur.execute("""
            INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after, idempotency_key)
            VALUES ('tx-1', 'acc-1', 'DEPOSIT', 500, 1500, 0, 'idem-1');
        """)
        cur.execute("""
            INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after, idempotency_key)
            VALUES ('tx-2', 'acc-1', 'HOLD', 100, 1400, 100, 'idem-2');
        """)
        db.commit()

        cur.execute("SELECT COUNT(*) FROM credit_ledger")
        assert cur.fetchone()[0] == 2

    def test_amount_must_be_strictly_positive(self, db):
        cur = db.cursor()
        # Zero amount must fail
        with pytest.raises(sqlite3.IntegrityError):
            cur.execute("""
                INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after)
                VALUES ('tx-fail-0', 'acc-1', 'DEPOSIT', 0, 1000, 0);
            """)

        # Negative amount must fail
        with pytest.raises(sqlite3.IntegrityError):
            cur.execute("""
                INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after)
                VALUES ('tx-fail-neg', 'acc-1', 'DEPOSIT', -50, 950, 0);
            """)

    def test_transaction_type_whitelist(self, db):
        cur = db.cursor()
        for invalid_type in ['WITHDRAWAL', 'TRANSFER', 'CHARGE', 'deduct', 'Deposit']:
            with pytest.raises(sqlite3.IntegrityError):
                cur.execute(f"""
                    INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after)
                    VALUES ('tx-fail-{invalid_type}', 'acc-1', '{invalid_type}', 50, 950, 0);
                """)

    def test_immutability_trigger_blocks_update(self, db):
        cur = db.cursor()
        cur.execute("""
            INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after)
            VALUES ('tx-immutable-1', 'acc-1', 'DEPOSIT', 500, 1500, 0);
        """)
        db.commit()

        # Attempt to modify amount or transaction_type
        with pytest.raises(sqlite3.DatabaseError) as exc_info:
            cur.execute("UPDATE credit_ledger SET amount = 999 WHERE id = 'tx-immutable-1';")
        assert "credit_ledger is strictly append-only" in str(exc_info.value)

    def test_immutability_trigger_blocks_delete(self, db):
        cur = db.cursor()
        cur.execute("""
            INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after)
            VALUES ('tx-immutable-2', 'acc-1', 'HOLD', 200, 800, 200);
        """)
        db.commit()

        # Attempt to delete ledger row
        with pytest.raises(sqlite3.DatabaseError) as exc_info:
            cur.execute("DELETE FROM credit_ledger WHERE id = 'tx-immutable-2';")
        assert "credit_ledger is strictly append-only" in str(exc_info.value)

    def test_idempotency_key_uniqueness(self, db):
        cur = db.cursor()
        cur.execute("""
            INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after, idempotency_key)
            VALUES ('tx-idem-1', 'acc-1', 'DEPOSIT', 100, 1100, 0, 'idem-unique-key');
        """)
        db.commit()

        # Duplicate non-null key fails
        with pytest.raises(sqlite3.IntegrityError):
            cur.execute("""
                INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after, idempotency_key)
                VALUES ('tx-idem-2', 'acc-1', 'DEPOSIT', 100, 1200, 0, 'idem-unique-key');
            """)

        # Multiple NULL keys succeed
        cur.execute("""
            INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after, idempotency_key)
            VALUES ('tx-idem-null-1', 'acc-1', 'DEPOSIT', 10, 1110, 0, NULL);
        """)
        cur.execute("""
            INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after, idempotency_key)
            VALUES ('tx-idem-null-2', 'acc-1', 'DEPOSIT', 10, 1120, 0, NULL);
        """)
        db.commit()

    def test_foreign_key_delete_restrict_on_account(self, db):
        """Verifies that an account cannot be deleted while having ledger transactions."""
        cur = db.cursor()
        cur.execute("""
            INSERT INTO credit_ledger (id, account_id, transaction_type, amount, balance_after, held_balance_after)
            VALUES ('tx-restrict-1', 'acc-1', 'DEPOSIT', 100, 1100, 0);
        """)
        db.commit()

        # Deleting the parent credit_account must fail with IntegrityError (FOREIGN KEY constraint failed)
        with pytest.raises(sqlite3.IntegrityError):
            cur.execute("DELETE FROM credit_accounts WHERE id = 'acc-1';")

    def test_adversarial_vulnerability_truncate_not_prevented_by_row_trigger(self):
        """
        Adversarial Analysis of DDL 0002_keystone_full_schema.sql line 169:
        The trigger is defined as:
          BEFORE UPDATE OR DELETE ON credit_ledger FOR EACH ROW
        In PostgreSQL, TRUNCATE does NOT fire row-level triggers!
        A TRUNCATE TABLE credit_ledger would wipe all ledger history without firing the trigger.
        A defense-in-depth mitigation requires:
          BEFORE TRUNCATE ON credit_ledger FOR EACH STATEMENT EXECUTE FUNCTION ...
        """
        content = MIGRATION_0002.read_text(encoding="utf-8")
        assert "TRUNCATE" not in content, "Documents that TRUNCATE trigger is not present in 0002 migration."



class TestAssetRelationshipsSimulation:
    """Simulates asset_relationships constraints in SQLite."""

    @pytest.fixture
    def db(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE assets (
                id TEXT PRIMARY KEY,
                media_type TEXT NOT NULL
            );
        """)

        cur.execute("""
            CREATE TABLE asset_relationships (
                id TEXT PRIMARY KEY,
                parent_asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                child_asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
                relationship_type TEXT NOT NULL CHECK (relationship_type IN ('source', 'edit', 'variation', 'animation', 'upscale', 'reference', 'selected-final', 'intermediate')),
                UNIQUE(parent_asset_id, child_asset_id, relationship_type)
            );
        """)

        cur.execute("INSERT INTO assets (id, media_type) VALUES ('ast-1', 'image');")
        cur.execute("INSERT INTO assets (id, media_type) VALUES ('ast-2', 'video');")
        cur.execute("INSERT INTO assets (id, media_type) VALUES ('ast-3', 'image');")
        conn.commit()

        yield conn
        conn.close()

    def test_all_eight_relationship_types_valid(self, db):
        valid_types = ['source', 'edit', 'variation', 'animation', 'upscale', 'reference', 'selected-final', 'intermediate']
        cur = db.cursor()
        for idx, r_type in enumerate(valid_types):
            cur.execute(f"""
                INSERT INTO asset_relationships (id, parent_asset_id, child_asset_id, relationship_type)
                VALUES ('rel-{idx}', 'ast-1', 'ast-2', '{r_type}');
            """)
        db.commit()

        cur.execute("SELECT COUNT(*) FROM asset_relationships")
        assert cur.fetchone()[0] == 8

    def test_invalid_relationship_type_rejected(self, db):
        cur = db.cursor()
        for invalid_type in ['derived', 'child', 'input', 'parent', 'clone', 'SOURCE']:
            with pytest.raises(sqlite3.IntegrityError):
                cur.execute(f"""
                    INSERT INTO asset_relationships (id, parent_asset_id, child_asset_id, relationship_type)
                    VALUES ('rel-fail-{invalid_type}', 'ast-1', 'ast-2', '{invalid_type}');
                """)

    def test_composite_unique_constraint(self, db):
        cur = db.cursor()
        cur.execute("""
            INSERT INTO asset_relationships (id, parent_asset_id, child_asset_id, relationship_type)
            VALUES ('rel-dup-1', 'ast-1', 'ast-2', 'animation');
        """)
        db.commit()

        # Duplicate (parent, child, type) must fail
        with pytest.raises(sqlite3.IntegrityError):
            cur.execute("""
                INSERT INTO asset_relationships (id, parent_asset_id, child_asset_id, relationship_type)
                VALUES ('rel-dup-2', 'ast-1', 'ast-2', 'animation');
            """)

        # Reversed direction succeeds
        cur.execute("""
            INSERT INTO asset_relationships (id, parent_asset_id, child_asset_id, relationship_type)
            VALUES ('rel-rev-1', 'ast-2', 'ast-1', 'animation');
        """)
        db.commit()


# ==============================================================================
# 3. Adversarial Invariant Verifier Script Tests
# ==============================================================================

class TestVerifyInvariantsAdversarial:
    """Stress tests scripts/verify_invariants.py under simulated invariant breaches."""

    def test_verifier_passes_on_current_workspace(self):
        """Standard execution on uncorrupted workspace must return 0."""
        res = verify_invariants.verify_bible(ROOT_DIR, require_docs_copy=True)
        assert res["overall_valid"] is True
        assert res["root_valid"] is True
        assert res["docs_valid"] is True

        manifest = verify_invariants.verify_prebuilt_manifest(ROOT_DIR)
        assert manifest["all_valid"] is True
        assert manifest["mismatch_count"] == 0
        assert manifest["missing_count"] == 0

        cog = verify_invariants.verify_cognition_checkpoint(ROOT_DIR)
        assert cog["valid"] is True

    def test_detects_tampered_root_bible(self, tmp_path):
        """Modifying root Bible by 1 byte must trigger failure."""
        fake_root = tmp_path / "mock_keystone"
        fake_root.mkdir()
        fake_bible = fake_root / "KEYSTONE_BIBLE.md"
        fake_bible.write_text("Corrupted content", encoding="utf-8")

        res = verify_invariants.verify_bible(fake_root)
        assert res["root_valid"] is False
        assert res["overall_valid"] is False

    def test_detects_missing_docs_bible_when_required(self, tmp_path):
        """Missing docs/KEYSTONE_BIBLE.md must fail when require_docs_copy=True."""
        fake_root = tmp_path / "mock_keystone"
        fake_root.mkdir()
        # Create valid root
        real_bible = ROOT_DIR / "KEYSTONE_BIBLE.md"
        (fake_root / "KEYSTONE_BIBLE.md").write_bytes(real_bible.read_bytes())

        res = verify_invariants.verify_bible(fake_root, require_docs_copy=True)
        assert res["root_valid"] is True
        assert res["docs_present"] is False
        assert res["docs_valid"] is False
        assert res["overall_valid"] is False

    def test_detects_missing_manifest_file(self, tmp_path):
        """Missing any of the 69 pre-built files must fail manifest verification."""
        fake_root = tmp_path / "mock_manifest_missing"
        fake_root.mkdir()

        res = verify_invariants.verify_prebuilt_manifest(fake_root)
        assert res["all_valid"] is False
        assert res["missing_count"] == len(verify_invariants.PREBUILT_MANIFEST)

    def test_detects_corrupted_manifest_file(self, tmp_path):
        """Modifying even 1 byte in a pre-built file must fail manifest verification."""
        fake_root = tmp_path / "mock_manifest_corrupted"
        fake_root.mkdir()

        # Recreate a single tracked file with corrupted bytes
        rel_path = "README.md"
        target = fake_root / rel_path
        target.write_text("Modified README content", encoding="utf-8")

        res = verify_invariants.verify_prebuilt_manifest(fake_root)
        assert res["all_valid"] is False
        mismatched_paths = [m["path"] for m in res["mismatches"]]
        assert rel_path in mismatched_paths

    def test_detects_cognition_checkpoint_tampering(self, tmp_path):
        """Removing pinned model or adding prohibited model patterns must trigger breach."""
        fake_root = tmp_path / "mock_kaggle"
        nb_dir = fake_root / "infrastructure" / "kaggle"
        nb_dir.mkdir(parents=True)
        nb_file = nb_dir / "keystone_kaggle_bootstrap.ipynb"

        # Case 1: Pinned model missing
        nb_file.write_text(json.dumps({"cells": [{"source": ["some generic model"]}]}), encoding="utf-8")
        res1 = verify_invariants.verify_cognition_checkpoint(fake_root)
        assert res1["valid"] is False

        # Case 2: Pinned model present, but prohibited quantized substitute injected
        nb_file.write_text(json.dumps({
            "cells": [
                {"source": [verify_invariants.PINNED_COGNITION_MODEL]},
                {"source": ["Using qwen/qwen2.5-7b as fallback"]}
            ]
        }), encoding="utf-8")
        res2 = verify_invariants.verify_cognition_checkpoint(fake_root)
        assert res2["valid"] is False

    def test_detects_prohibited_model_in_kaggle_setup(self, tmp_path):
        """Prohibited models in KAGGLE_SETUP/*.ipynb must also fail verification."""
        fake_root = tmp_path / "mock_kaggle_setup"
        # Valid bootstrap
        nb_dir = fake_root / "infrastructure" / "kaggle"
        nb_dir.mkdir(parents=True)
        (nb_dir / "keystone_kaggle_bootstrap.ipynb").write_text(
            json.dumps({"cells": [{"source": [verify_invariants.PINNED_COGNITION_MODEL]}]}),
            encoding="utf-8"
        )
        # Invalid KAGGLE_SETUP notebook
        setup_dir = fake_root / "KAGGLE_SETUP"
        setup_dir.mkdir(parents=True)
        (setup_dir / "worker.ipynb").write_text(
            json.dumps({"cells": [{"source": ["unsloth 4bit quantized"]}]}),
            encoding="utf-8"
        )

        res = verify_invariants.verify_cognition_checkpoint(fake_root)
        assert res["valid"] is False

    def test_flaw_analysis_in_verify_npm_test_regex(self):
        """
        Adversarial Analysis of verify_invariants.py:
        Line 476: has_fail = ("fail [1-9]" in output or ...)
        Because 'fail [1-9]' is evaluated as a string literal and not a compiled regex,
        an output containing 'fail 1' does not trigger 'fail [1-9]' in output!
        Demonstrates the logic weakness if exit_code is zero.
        """
        mock_npm_output = "ℹ tests 3, pass 2, fail 1\n"
        # Direct string membership test as written in verify_invariants.py:
        literal_match = "fail [1-9]" in mock_npm_output
        assert literal_match is False, "Demonstrates that 'fail [1-9]' is treated as literal, not regex."

    def test_verify_npm_test_non_zero_exit_fails(self, monkeypatch):
        """Simulate npm test returning non-zero exit code."""
        def mock_run_command_fail(cmd, cwd):
            return {
                "command": "npm test",
                "exit_code": 1,
                "stdout": "fail 1",
                "stderr": "AssertionError",
                "success": False
            }
        monkeypatch.setattr(verify_invariants, "run_command_check", mock_run_command_fail)
        res = verify_invariants.verify_npm_test(ROOT_DIR)
        assert res["passed"] is False

    def test_verify_e2e_runner_failure_fails(self, monkeypatch):
        """Simulate node e2e runner returning failure."""
        def mock_run_command_fail(cmd, cwd):
            return {
                "command": "node tests/e2e/runner.js",
                "exit_code": 1,
                "stdout": "Total Failed: 2",
                "stderr": "",
                "success": False
            }
        monkeypatch.setattr(verify_invariants, "run_command_check", mock_run_command_fail)
        res = verify_invariants.verify_e2e_runner(ROOT_DIR)
        assert res["passed"] is False

    def test_cli_skip_tests_flag_behavior(self):
        """
        Adversarial Analysis of CLI flags:
        When --skip-tests is passed, verify_invariants skips npm test and e2e runner.
        Verify that --skip-tests flags them as skipped.
        """
        cmd = [sys.executable, str(VERIFY_SCRIPT), "--require-docs-bible", "--skip-tests", "--json"]
        proc = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True)
        assert proc.returncode == 0
        data = json.loads(proc.stdout)
        assert data["npm_test_identity"]["skipped"] is True
        assert data["e2e_runner_run1"]["skipped"] is True

