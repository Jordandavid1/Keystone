# Architecture Decision Record (ADR) 003: Promote OBLITERATUS/Qwen3.8-27B-OBLITERATED (V3 Deep Liberation) as Pinned Cognition Checkpoint

- **Date:** 2026-11-15
- **Target Invariant:** KEYSTONE_BIBLE.md §2, §10, §11, §24, §37
- **Status:** FOUNDER_APPROVED (Founder Explicit Directive: 2026-11-14)

## 1. Explicit Founder Approval
- **Approval Timestamp:** 2026-11-14 (UTC, Founder Explicit Directive)
- **Verbatim Founder Directive:** `"obliteratus v3 qwen 3.8 abliterated"` / `"replace with obliteratus v3 qwen3.8 abliterated invariant hardcode"` / `"replace with obliteratus v3"`
- **Sign-off Identification:** Founder Explicit Directive (Workspace Session ADR-003)

## 2. Architecture Decision Record
- **Context:** Per `KEYSTONE_BIBLE.md` §2, §10, §11, and §24, KEYSTONE's unaligned/abliterated cognition engine previously pinned `huihui-ai/Huihui-Qwen3.8-27B-abliterated`. On 2026-11-14, the Founder explicitly directed migrating and locking the entire mutable cognition runtime, Modal A100 vLLM worker, Kaggle Dual-T4 bootstrap notebooks (`KAGGLE_SETUP/`), Cloud Run deployment manifest, Web Studio UI, and automated invariant/adversarial suites to `OBLITERATUS/Qwen3.8-27B-OBLITERATED` (`Qwen3.8-27B — OBLITERATED`, V3: Deep Liberation), while simultaneously resolving Next.js `http-proxy` `[DEP0060]` (`util._extend`) deprecation warnings and Direct Cognition Console HTTP `401` handling.
- **Decision:**
  1. **Invariant Checkpoint Promotion:** Pin `OBLITERATUS/Qwen3.8-27B-OBLITERATED` across all mutable Python/TypeScript/JS services, Modal A100 workers (`keystone_a100_worker.py`, `keystone_a100_worker_v2.py`), Cloud Run (`infrastructure/cloudrun/service.yaml`), Kaggle setup notebooks/configs (`KAGGLE_SETUP/`), `.env` / `.env.modal`, frontend surfaces, and `scripts/verify_invariants.py`.
  2. **Pre-Built Manifest & Bible Preservation:** Preserve all 69 files listed in `docs/FILE_MANIFEST.txt` byte-for-byte intact—including `KEYSTONE_BIBLE.md`, `docs/KEYSTONE_BIBLE.md`, `TEST_READY.md`, `services/cognition/README.md`, and `infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb`—while updating `scripts/verify_invariants.py` (`verify_cognition_checkpoint`) to enforce `OBLITERATUS/Qwen3.8-27B-OBLITERATED` across active runtime and `KAGGLE_SETUP` deployment targets and disallow unauthorized model substitutions.
  3. **Direct Cognition Console & Proxy Hardening:** Eliminate `[DEP0060] util._extend` by replacing Next.js `http-proxy` rewrites with native `fetch` App Router Route Handlers (`apps/web/lib/backendProxy.ts` and `/v1`, `/internal`, `/admin` handlers), remove hardcoded `'local_dev_token'` / `'tenant-keystone-local'` / `'operator@keystone.internal'` fallbacks, and enforce clean auth gating and live `/v1/cognition/status` reporting in `AgentChatModal`.
- **Alternatives Considered & Rejected:** Keeping `huihui-ai/Huihui-Qwen3.8-27B-abliterated` violates the explicit Founder Directive. Modifying the frozen pre-built `KEYSTONE_BIBLE.md` or `infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb` without preserving `docs/FILE_MANIFEST.txt` would break §37 pre-built file immutability guarantees.

## 3. Compatibility Impact Analysis
- **API Impact:** Backwards-compatible `/v1/plan`, `/v1/health`, `/v1/cognition/status`, `/v1/cognition/chat`, and `/v1/cognition/agent-task` schemas; cognition model identifier updated to `OBLITERATUS/Qwen3.8-27B-OBLITERATED` (accepting `:fastest` / served alias normalization where configured on vLLM).
- **Client Impact:** `AgentChatModal` and `/workspace` reflect `OBLITERATUS/Qwen3.8-27B-OBLITERATED`, gate cleanly when unauthenticated (`401` / signed-out state), and remove synthetic fallback tokens.
- **State & Storage Impact:** Additive Modal volume staging directory (`models/obliteratus_qwen3_8_27b_v3`) excluding redundant GGUF and `*-of-00018.safetensors` shards; zero database schema breakage.
- **Pre-Built File Immutability:** All 69 files in `docs/FILE_MANIFEST.txt` remain 100% unmodified (`sha256` matches manifest).

## 4. KHF Regression Coverage
- **Regression Suite:** `scripts/verify_invariants.py`, `scripts/verify_change_control.py`, `scripts/verify_alpha_gate.py`, `tests/test_no_placeholders_invariants.py`, `tests/e2e_v2/`, and `tests/adversarial_security_suite.js`.
- **Test Scenarios:** Checkpoint pinning (`OBLITERATUS/Qwen3.8-27B-OBLITERATED`), rejection of deprecated `huihui` / closed-API / quantized checkpoints, 69-file `FILE_MANIFEST.txt` integrity, zero-placeholder static/runtime assertions, zero `[DEP0060]` proxy warnings, and fail-closed `COGNITION_NOT_CONFIGURED` / `COGNITION_UNREACHABLE` semantics.
- **Pre-Change vs Post-Change Verification:** Executed full `pytest`, JS test suites, and invariant gate scripts post-edit.

## 5. Migration Plan
- **Step 1:** Record ADR-003 under `docs/change_control/` per `KEYSTONE_BIBLE.md` §37.
- **Step 2:** Update all mutable runtime code, Modal workers, Kaggle `KAGGLE_SETUP/` artifacts, UI labels, `scripts/verify_invariants.py`, and test assertions to `OBLITERATUS/Qwen3.8-27B-OBLITERATED`.
- **Step 3:** Rebuild Next.js frontend with native `fetch` proxy handlers, restart local API (`KEYSTONE_DEV_AUTH_BYPASS=1`) and Web Studio, and run all automated verification gates.

## 6. Rollback Plan
- **Trigger Conditions:** Failure of `scripts/verify_invariants.py`, `scripts/verify_change_control.py`, or failure of vLLM serving `OBLITERATUS/Qwen3.8-27B-OBLITERATED` on A100/T4 runtime.
- **Immediate Reversion Steps:** Revert commits modifying `PINNED_COGNITION_MODEL`, `keystone_a100_worker*.py`, `KAGGLE_SETUP/`, and Next.js proxy handlers, and redeploy prior container revision.
- **State Recovery:** No destructive database migrations occur; `docs/FILE_MANIFEST.txt` artifacts were never altered.

## 7. Versioned Contract Updates
- **Pinned Cognition Checkpoint:** Promoted from `huihui-ai/Huihui-Qwen3.8-27B-abliterated` to `OBLITERATUS/Qwen3.8-27B-OBLITERATED`.
- **Pre-Built Bible SHA-256 (Unmodified per Manifest):** `1DA5FFE9D1467B7A4CF31F27F8B9D4CDE0B4096F1A922C6A3C214450FCC13A99` (`41919` bytes).
- **Proxy Transport:** Replaced Next.js `http-proxy` rewrites with native Undici/`fetch` handlers (`apps/web/lib/backendProxy.ts`) eliminating Node `[DEP0060]`.
