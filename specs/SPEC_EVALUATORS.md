# SPEC A: Evaluator Tank (`services/harness/src/evaluators/`)

**Authority:** KEYSTONE Bible v2 (§2 Invariant 8, §13, §14, §41.4) & ADR-005  
**Target Implementation:** PR3 (Tier-A deterministic/floor) & PR7 (Tier-B neural/OCR/temporal/identity evaluators)

---

## 1. Service Modules (`services/harness/src/evaluators/`)

- `deterministic.py` — File integrity, dimensions, duration, format validity, actual upscale delta (rejects bicubic / zero-delta fakes). Runs on **every asset** (Tier A).
- `ocr.py` — Rendered text fidelity vs. requested string (Tesseract / PaddleOCR-class). Runs on text-bearing images.
- `vlm_critique.py` — Output alignment vs. compiled intent, persona sheet, and mode-aware rubric (Qwen-VL via `CognitiveProvider`). Runs on sampled jobs + all retries + all persona assets.
- `temporal.py` — Frame-to-frame consistency, flicker detection, and drift across `extend` video segments (sampled-frame SSIM + optical-flow drift). Runs on video outputs.
- `identity.py` — Persona identity embedding cosine similarity vs. persona reference asset set (§41.4). Runs on **all persona-bearing assets**.

---

## 2. Execution Pipeline

```text
Worker post-execution hook
  -> Tier A: deterministic.py (always)
  -> Conditional Tier B per §13.3 budget (OCR / VLM / temporal / identity)
  -> Verdict object { family, score, defects[] }
  -> Persist `harness_runs` row in PostgreSQL (never process RAM)
  -> Retry decision via `retry_loop.py` (bounded attempts/runtime/cost; escalation flag)
  -> Acceptance -> §42 promotion candidate (or operator-review flag if budget exhausted)
```

No evaluator may rely solely on numbers supplied by the thing being evaluated. Un-evaluated output may never enter lineage as final, and budget exhaustion flags the asset for operator review (never silent accept, never silent drop).

---

## 3. Mode-Aware Critique Rubrics (§13.4)

`vlm_critique.py` builds its evaluation prompt through the critique-compiler (`H3PromptCompiler.critique_rubric(mode)` / canonical `PromptCompiler`) under the same authority and mode discipline as generation:
- An `UNRESTRICTED` rubric never penalizes explicitness or graphic genre elements requested by the compiled intent.
- An `SFW` rubric holds the mainstream register.

---

## 4. Configuration Keys

- `KEYSTONE_EVAL_BUDGET_VLM_PCT` — Sample percentage for non-retry, non-persona VLM evaluation
- `KEYSTONE_EVAL_VIDEO_SAMPLE_FRAMES` — Number of frames sampled for temporal consistency
- `KEYSTONE_EVAL_RETRY_MAX` — Maximum automatic quality retries
- Service tier mapping: `draft | quality` mapped to operator-configured evaluator budget profiles

---

## 5. Real Acceptance Tests (ADR-005)

1. Corrupted binary / truncated file fails `deterministic.py`.
2. Synthetic text-image fixture with misspelled rendered text fails `ocr.py`.
3. Persona-drift fixture (two labeled mismatched-identity images) scores below threshold in `identity.py`.
4. Explicit fixture passes the `UNRESTRICTED` VLM rubric while being flagged by the `SFW` rubric.
5. Exhausting retry budget marks the asset for operator review rather than silently accepting or dropping it, and writes durable `harness_runs` rows.
