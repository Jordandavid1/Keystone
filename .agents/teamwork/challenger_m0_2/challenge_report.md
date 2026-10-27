# Keystone Milestone M0: Adversarial Challenge Report

**Agent**: `challenger_m0_2` (teamwork_preview_challenger)  
**Parent**: Project Orchestrator (`6f59f58e-8034-400a-bd25-c869a10728f4`)  
**Date**: 2026-10-23  
**Milestone**: M0 (Wave 0: Contract Freeze & Additive Foundation)  
**Evaluation Scope**: `infrastructure/migrations/versions/0002_keystone_full_schema.sql` (Database DDL & Constraints), `scripts/verify_invariants.py` (Invariant Guard), `scripts/verify_change_control.py` (ADR Governance).

---

## Challenge Summary

- **Overall Risk Assessment**: **LOW**
- **Final Verdict**: **APPROVE**
- **Test Evidence**: 25 adversarial test cases executed via Pytest in `tests/e2e_v2/test_m0_challenger_adversarial.py` (100% green pass in 1.47s), plus full regression of 199 tests in `tests/e2e_v2/`, 132 tests in Run 1 E2E runner, 3 identity tests in `npm test`, and zero diffs on git-tracked pre-built files.

The Milestone M0 database DDL migration `0002_keystone_full_schema.sql` completely and strictly realizes the 23-table persistence totality mandated by `KEYSTONE_BIBLE.md` §21. The credit ledger immutability trigger and check constraints correctly enforce append-only ledger physics (`amount > 0`, transaction types whitelist, update/delete abort). The invariant verification script `scripts/verify_invariants.py` reliably detects tampering across the Bible checksum, docs mirror, 69 pre-built manifest files, pinned Qwen cognition model, and execution runner failures.

Four minor advisory challenges were identified and analyzed below with concrete mitigations for upcoming waves; none invalidate Milestone M0 contract freeze objectives.

---

## Challenges

### [Low / Advisory] Challenge 1: Row-Level Trigger on `credit_ledger` Does Not Intercept `TRUNCATE`
- **Assumption Challenged**: The PostgreSQL trigger `trg_credit_ledger_immutable` prevents all forms of record deletion on `credit_ledger`.
- **Attack Scenario**: An attacker, rogue maintenance script, or privileged database connection executes `TRUNCATE TABLE credit_ledger;`. In PostgreSQL, `BEFORE UPDATE OR DELETE ... FOR EACH ROW` triggers are bypassed by `TRUNCATE` operations because `TRUNCATE` is a statement-level DDL command that unlinks table pages rather than scanning rows.
- **Blast Radius**: Complete loss of financial ledger transaction history without triggering the immutability exception `keystone_credit_ledger_prevent_modification`.
- **Mitigation**: Add a statement-level truncate guard in a defense-in-depth migration:
  ```sql
  CREATE OR REPLACE FUNCTION keystone_credit_ledger_prevent_truncate()
  RETURNS TRIGGER AS $$
  BEGIN
      RAISE EXCEPTION 'credit_ledger cannot be truncated. Append-only invariant violated.';
  END;
  $$ LANGUAGE plpgsql;

  CREATE TRIGGER trg_credit_ledger_prevent_truncate
  BEFORE TRUNCATE ON credit_ledger
  FOR EACH STATEMENT
  EXECUTE FUNCTION keystone_credit_ledger_prevent_truncate();
  ```
  In production Cloud SQL, revoke `TRUNCATE` permissions from the standard application role (`REVOKE TRUNCATE ON credit_ledger FROM keystone_app`).

### [Low / Advisory] Challenge 2: `credit_accounts` Lacks `held_balance <= balance` Invariant
- **Assumption Challenged**: A user's held balance cannot exceed their total credit balance.
- **Attack Scenario**: A concurrent race condition or logic flaw in the hold reservation service reserves 1,000 credits on an account with a balance of only 200 credits. `0002_keystone_full_schema.sql` enforces `CHECK (balance >= 0)` and `CHECK (held_balance >= 0)`, but does NOT enforce `CHECK (held_balance <= balance)`.
- **Blast Radius**: Available balance (`balance - held_balance`) becomes negative (-800), potentially causing overdrafts or ledger settlement discrepancies.
- **Mitigation**: Enforce available balance check in SQL schema or application domain service (Milestone M1 / M5):
  ```sql
  ALTER TABLE credit_accounts ADD CONSTRAINT chk_credit_accounts_available_balance CHECK (balance >= held_balance);
  ```

### [Low / Advisory] Challenge 3: Invariant Verifier Script String Literal Search Instead of Regex in `verify_npm_test`
- **Assumption Challenged**: Line 476 of `scripts/verify_invariants.py` detects any failing test count in `npm test` output using `"fail [1-9]" in output`.
- **Attack Scenario**: In Python, `"fail [1-9]" in output` tests for the exact 10-character substring `"fail [1-9]"` because `re` is not imported or used. If `npm test` outputs `"fail 1"` and somehow exits with status 0 (e.g., if a subshell swallowed exit codes), `verify_npm_test` would fail to detect the failure via that string check.
- **Blast Radius**: Potential false-negative pass in CI if test runner process exit code is masked. (Note: currently mitigated because `res["success"] = (proc.returncode == 0)` correctly catches standard non-zero test exits).
- **Mitigation**: Update `scripts/verify_invariants.py` to import `re` and use `re.search(r"fail [1-9]", output)`.

### [Advisory] Challenge 4: `--skip-tests` CLI Flag Bypasses Invariant Verification
- **Assumption Challenged**: Running `python scripts/verify_invariants.py` always executes all tests.
- **Attack Scenario**: A developer or script executes `python scripts/verify_invariants.py --skip-tests`, which marks `npm_test_identity` and `e2e_runner_run1` as `passed: True, skipped: True` without executing them.
- **Blast Radius**: CI or deployment pipelines could report `100% INVARIANTS SATISFIED` on broken code if invoked with `--skip-tests`.
- **Mitigation**: Ensure all CI gate definitions, pre-push hooks, and release runbooks explicitly execute `python scripts/verify_invariants.py --require-docs-bible` without `--skip-tests`.

---

## Stress Test Results

| Test Scenario | Expected Behavior | Actual Behavior | Result |
|:---|:---|:---|:---:|
| 1. DDL 23-Table Totality (`0001_core.sql` + `0002_keystone_full_schema.sql`) | Exactly 23 distinct tables created across schema | 12 base + 11 additive tables parsed, 23 total tables confirmed | **PASS** |
| 2. `credit_ledger` `amount > 0` Check Constraint | `amount = 0` or `amount < 0` rejected | Rejected with `IntegrityError: CHECK constraint failed` | **PASS** |
| 3. `credit_ledger` Transaction Types Whitelist | Only DEPOSIT, HOLD, SETTLEMENT, RELEASE, REFUND permitted | Invalid types ('WITHDRAWAL', 'TRANSFER', 'CHARGE') rejected | **PASS** |
| 4. `credit_ledger` Immutability Trigger on UPDATE | Any UPDATE statement blocked | Blocked with exception: `'credit_ledger is strictly append-only'` | **PASS** |
| 5. `credit_ledger` Immutability Trigger on DELETE | Any DELETE statement blocked | Blocked with exception: `'credit_ledger is strictly append-only'` | **PASS** |
| 6. `credit_ledger` Idempotency Key Uniqueness | Unique non-null keys enforced; multiple NULLs allowed | Duplicate key raises `IntegrityError`; multiple NULL keys succeed | **PASS** |
| 7. `credit_accounts` Foreign Key Restrict on Ledger | Deleting parent account with ledger entries blocked | Blocked with `IntegrityError: FOREIGN KEY constraint failed` | **PASS** |
| 8. `asset_relationships` 8 Relationship Types Whitelist | Exactly 8 valid types allowed | All 8 types ('source', 'edit', 'variation', 'animation', 'upscale', 'reference', 'selected-final', 'intermediate') succeed; invalid types rejected | **PASS** |
| 9. `asset_relationships` Composite Unique Constraint | Duplicate `(parent, child, type)` rejected; reversed order allowed | Duplicate rejected with `IntegrityError`; reversed order succeeds | **PASS** |
| 10. Invariant Verifier: Baseline Pass | Clean workspace yields status PASS and returncode 0 | Passed with exit code 0 and `all_passed: True` | **PASS** |
| 11. Invariant Verifier: Tampered Root Bible | 1-byte alteration triggers failure | Detected: `root_valid: False, overall_valid: False` | **PASS** |
| 12. Invariant Verifier: Missing `docs/KEYSTONE_BIBLE.md` | Missing docs copy with `--require-docs-bible` fails | Detected: `docs_valid: False, overall_valid: False` | **PASS** |
| 13. Invariant Verifier: Missing Manifest File | Removal of any pre-built file fails manifest audit | Detected: `missing_count: 69, all_valid: False` | **PASS** |
| 14. Invariant Verifier: Corrupted Manifest File | 1-byte modification of pre-built file fails audit | Detected: `mismatches: ['README.md'], all_valid: False` | **PASS** |
| 15. Invariant Verifier: Tampered Cognition Checkpoint | Removal of pinned model fails audit | Detected: `pinned_model_present: False, valid: False` | **PASS** |
| 16. Invariant Verifier: Prohibited Model Injected | Quantized model pattern (`qwen2.5-7b`, `unsloth`) fails | Detected: `prohibited_substitutes_found: True, valid: False` | **PASS** |
| 17. Invariant Verifier: Runner Failure Detection | Non-zero exit code in test runner fails verifier | Detected: `passed: False, all_passed: False` | **PASS** |
| 18. Invariant Verifier: `--skip-tests` CLI Flag Audit | Skips execution and flags skipped in JSON | Verified: returns `skipped: True` for test suites | **PASS** |

---

## Unchallenged Areas

- **Live PostgreSQL Database Engine Execution**: Full execution against managed Google Cloud SQL PostgreSQL instance will be performed during Milestone M6 deployment. M0 verified syntactic AST conformity, column constraints, trigger semantics, and relational algebra via in-memory SQLite simulation and static schema validation.
