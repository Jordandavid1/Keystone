# Original User Request

## 2026-10-22T14:02:02Z

# Teamwork Project Prompt — Final

> Status: Launched
> Goal: Execute build preserving all pre-built work → run full validation suite
> Requested team: Full Team

Build an additive architectural and UX intelligence pipeline for KEYSTONE by leveraging Firecrawl to scrape and deconstruct leading benchmark applications (such as Hugging Face), feeding extracted structural patterns and intent signals into a BigQuery AI/ML query & embeddings layer, protected by an enterprise PII Vault compliance and Aikido prompt-injection defense barrier.

Working directory: c:\Users\Lesia Eden\Downloads\keystone-cowork
Integrity mode: development

CRITICAL INVARIANT: DO NOT MODIFY OR OVERWRITE ANY PRE-BUILT CODE. Build strictly additively. All existing files, playbooks, and contracts must remain intact. Existing tests (`npm test`) must remain 100% green at all times.

## Requirements

### R1. Firecrawl Benchmark App & UX Extraction Service
- Build an additive service/module (e.g., under `services/intelligence` or `packages/signal-scraper`) utilizing Firecrawl skills (`firecrawl-scrape`, `firecrawl-build`, `firecrawl-website-design-clone`) to extract frontend component trees, design systems, API contracts, and workflow patterns from benchmark applications (such as Hugging Face Spaces/Hub).
- Enforce edge-level PII scrubbing (`redactPII: true`) and SHA-256 signal deduplication.

### R2. Enterprise PII Vault & Aikido Prompt Injection Defense
- Implement boundary encryption using AES-256-GCM for any extracted contact or personal references, passing only tokenized references.
- Implement Aikido prompt-injection defense: structural delimiter containment (`<untrusted_content>`), tag escaping, and post-generation sanitization so untrusted scraped markup never hijacks downstream LLM generation.
- Implement GDPR Article 17 cascading erasure logic with idempotency.

### R3. BigQuery AI/ML SQL Intelligence & Embeddings Layer
- Author SQL schemas, views, and analytical procedures using BigQuery AI/ML primitives (`AI.GENERATE`, `AI.GENERATE_EMBEDDING`, `AI.SIMILARITY`, `AI.CLASSIFY`) for semantic categorization and similarity search over scraped architectures.
- Ensure strict compliance with BigQuery AI/ML syntax constraints and mandatory resource attribution labeling.

### R4. Additive Keystone Integration & Clean Dependency Management
- Wire the new capability manifests into Keystone's architecture cleanly without modifying existing core contracts.
- Strictly adhere to Python dependency management guidelines (virtual environment, detection of package managers, bundled checks).
- Follow sysadmin guardrails (non-interactive execution, idempotent scripts, verification evidence).

## Acceptance Criteria

### Preservation & Non-Regression
- [ ] Baseline tests (`npm test`) continue to pass 100% without modification to existing test or source files.
- [ ] Pre-built directory structure and identity invariants are completely preserved.

### Extraction & Scraping
- [ ] Automated verification script/tests verify Firecrawl extraction, design pattern parsing, and SHA-256 deduplication.
- [ ] Edge PII redaction is enabled and verified.

### Security & Compliance
- [ ] Untrusted scraped HTML/markdown is validated to be properly quarantined inside Aikido delimiters.
- [ ] PII Vault compliance audit passes with zero plain PII reaching model contexts.

### Analytics & Verification
- [ ] BigQuery AI/ML SQL definitions validate cleanly against standard GCP schemas.
- [ ] Full end-to-end test and compliance verification suite passes with logged evidence.


## 2026-10-22T14:17:50Z

CRITICAL USER UPDATE / TARGET EXPANSION:
The user has locked in Option A (Full-Pipeline Integration) and explicitly mandated expanding the benchmark target catalog beyond Hugging Face to include the following 6 leading benchmark applications:
1. Hugging Face Spaces/Hub
2. Higgsfield (video/motion AI)
3. ZenCreator Pro (creator studio workflows)
4. Venice AI (privacy-first generative AI)
5. Adobe Creative Cloud / Firefly (creative tooling pipelines)
6. Grok (multimodal reasoning UX)

Please propagate this target list into:
- Phase 1 mock fixtures and E2E test suites
- Phase 2 Firecrawl scraper configurations and target schemas
- Phase 3 BigQuery AI/ML semantic categorization and embedding indexes
- All pre-built code remains strictly untouched.


## 2026-10-22T14:26:32Z

CRITICAL USER DIRECTIVE:
"use firecrawl when coding use the skills"

Ensure all active and upcoming implementation workers (Milestone 2 and beyond) actively read and utilize the newly installed Firecrawl skills (specifically firecrawl-build, firecrawl-build-scrape, firecrawl-website-design-clone, firecrawl-scrape, and firecrawl-developer-index located in C:\Users\Lesia Eden\.gemini\config\skills) to guide their code architecture, client transport, prompt structures, and extraction routines.


## 2026-10-22T16:11:35Z

Phase 1: build the complete KEYSTONE application exactly as specified in `KEYSTONE_BIBLE.md`, wire real GPU cognition and creative generation on Kaggle, deploy it live on Google Cloud, and give it a premium creative-workspace UX that makes anyone fall in love with it. Use a full team, fast paced but thorough. Phase 1 has no customers and no 24/7 uptime requirement: completeness and a working live system matter, availability SLAs don't.

Founder's words, verbatim: "I want to see a finished product today .. in a sense" / "just follow my instructions" / "do not change a single thing" / "DO NOT CHANGE ANY of the pre built work i put together just build" / "this keystone bible is the be all and end all. Nothing changes in this document. not unless I approve."

Working directory: c:\Users\Lesia Eden\Downloads\keystone-cowork
Integrity mode: development
Canonical spec: `KEYSTONE_BIBLE.md` (repo root) — the be-all and end-all. Read it in full before planning.

## Absolute constraints (founder directives)

1. **`KEYSTONE_BIBLE.md` is read-only.** Nothing in it changes without founder approval. Its SHA-256 must remain `1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788` for the entire run. Where §38 calls for `docs/KEYSTONE_BIBLE.md`, provide a byte-identical copy.
2. **Do not modify any pre-built work.** The founder's original scaffold and all Run 1 deliverables (`services/intelligence/`, `infrastructure/bigquery/`, `apps/api/src/intelligence_router.py`, `tests/e2e/`, `scripts/`, etc.) stay byte-identical. Build additively. If a Bible requirement cannot be met without editing an existing file, stop and ask the founder. Do not work around this.
3. All 18 locked invariants in Bible §2 and the §37 change-control rules apply. No agent may reinterpret them.
4. **Cognition checkpoint is pinned:** `huihui-ai/Huihui-Qwen3.8-27B-abliterated`, as already set in `infrastructure/kaggle/keystone_kaggle_bootstrap.ipynb`. No quantized, aligned or substitute checkpoint, ever (Bible §11, §24). Memory pressure is handled only through the §24 controlled retry profiles. Any change to weight precision or dtype (for example, if the T4 hardware can't run BF16) needs explicit founder approval first. If every approved profile is exhausted, stop and report evidence.
5. Closed source (§29): private repositories only, no public mirrors or publishing, and a secret scan before any push.
6. Secrets (§28): no real credentials in source, example env files, notebooks, logs, screenshots, prompts or Git history. The founder supplies Kaggle, Hugging Face, Firecrawl, Stripe test and Google Cloud credentials when asked. Agents request them; they never invent or hard-code them.

## Requirements

### R1. The full application per the Bible
Implement Epics A–I (§32) following the Wave 0–6 build order (§33). Every structure, contract, table, endpoint, state, harness and boundary the Bible names must exist and work:
- contracts and OpenAPI (§6–§19);
- PostgreSQL schema with Alembic migrations (§21);
- assets and lineage (§22);
- the creative tool fabric, covering image generation, image editing, Wan image-to-video and text-to-video, identity workflow, and upscale (§23);
- `KAGGLE_SETUP/` with all three notebooks (§24);
- the premium workspace (§25) and admin workspace (§26);
- auth, billing and credits (§27);
- security controls (§28);
- proprietary policy files and guarded private-GitHub publication tooling (§29, §38);
- legal documents drafted from the actual data flows (§30), marked as drafts pending qualified legal review.

### R2. Go live: Google Cloud plus Kaggle GPUs (Bible Tier 0)
- **Hosting:** the API, web workspace and admin workspace run on Google Cloud Run. Cloud SQL (PostgreSQL) is the durable store, Cloud Storage holds asset binaries behind signed short-expiry URLs, and Secret Manager holds secrets.
- **Founder steps:** the founder installs the gcloud CLI and authenticates when prompted. Every command that creates a billable resource is shown to the founder for confirmation first (sysadmin-guardrails).
- **GPUs:** the abliterated Qwen cognition (vLLM) and the ComfyUI/Wan creative workers run on Kaggle T4×2 via the `KAGGLE_SETUP` notebooks. The founder runs the notebooks; give clear step-by-step instructions and checklists.
- **Connecting Kaggle to the app:** Kaggle endpoints are ephemeral, so the platform must securely discover or re-register them each session without a redeploy. Workers verify signed envelopes.
- **Uptime:** sessions ending and restarting is acceptable in Phase 1.

### R3. Billing and credits
Stripe in test mode, plus the full credits ledger (§27): holds, settlement, refunds and reversals through ledger entries, idempotent webhooks, no double charges, and no balance change without a ledger event.

### R4. A killer UX informed by real benchmark research
- **Research:** use the Firecrawl skills (`firecrawl-website-design-clone`, `firecrawl-scrape`, `firecrawl-build*`, `firecrawl-signal-scraper`, installed under C:\Users\Lesia Eden\.gemini\config\skills) and the Run 1 intelligence service to scrape **live** public pages of Hugging Face, Higgsfield, ZenCreator Pro, Venice AI, Adobe Creative Cloud / Firefly and Grok. Run 1 only used mock fixtures. Capture their layout systems, navigation, composer and canvas patterns, progress and feedback UX, onboarding, motion, typography and color.
- **Synthesis:** produce a written UX research synthesis that says which patterns KEYSTONE adopts, improves on or rejects, and why.
- **Build:** build the §25 premium workspace from that synthesis, distinctly KEYSTONE. Learn patterns but never copy logos, trademarks, proprietary assets or copy text.
- **Bar:** the workspace should feel premium and delightful: fast, fluid, canvas-first, with polished motion, empty states, loading and progress states using the §25 language, compare mode, lineage, and a mobile review experience.

### R5. Required skills
- SQL work follows `bigquery-ai-ml` and `bigquery-sql`.
- Python dependencies follow `managing-python-dependencies` (isolated virtual environments, no global installs).
- System and deploy actions follow `sysadmin-guardrails`.
- Google platform documentation comes from `retrieving-developer-knowledge`.
- Scraping and web-data code follows the Firecrawl skills.

### R6. Compliance audit at completion
After go-live, run a `pii-vault-compliance` audit of the live system:
- zero plain PII in model-facing context;
- GDPR Art. 17 cascading erasure that is idempotent;
- Aikido `<untrusted_content>` defense on uploaded and retrieved content (Bible §5 precedence item 7);
- client response masking.

Produce a written audit report with findings and fixes.

## Acceptance Criteria

### Bible integrity and non-regression
- [ ] The Bible SHA-256 is unchanged at the end of the run, and every pre-existing file is byte-identical to a manifest captured at run start.
- [ ] `npm test` (3 identity tests) and `node --test tests/e2e/` (194 Run 1 tests) still pass.

### Bible §35 acceptance tests (automated, runnable by the founder)
- [ ] Identity tests: all six bullets.
- [ ] Authority tests: all seven bullets.
- [ ] The §35 end-to-end script runs against the **live Cloud Run URL** with real Kaggle cognition and generation:
  1. register, create a project, upload an image;
  2. ask KEYSTONE to animate it;
  3. compile the cognition prompt, receive a ProposedAction, authorize it, compile the target prompt;
  4. execute the workflow and evaluate the output;
  5. persist the video and lineage, debit credits exactly once;
  6. refresh the browser and recover the full project state.

  Then terminate the worker mid-run and verify recovery. Keep the logs as evidence.

### §34 alpha gate
- [ ] Every alpha-gate bullet is demonstrated on the live deployment, with evidence (test output, logs, screenshots).

### UX
- [ ] The UX research synthesis exists and cites the live Firecrawl captures for all 6 benchmark apps.
- [ ] An independent reviewer agent scores the live workspace against an explicit rubric: canvas-first hierarchy, composer, progress language, compare mode, lineage, motion polish, empty/error states, mobile review, and accessibility basics. No category scores below "good".

### Compliance
- [ ] The PII vault audit report has zero critical findings.

### Founder handoff
- [ ] A runbook covering: start the Kaggle notebooks → endpoints register → use the live app → shut down. Include rollback steps for every cloud resource created.

## 2026-10-22T16:11:55Z

FOUNDER DIRECTIVE (verbatim): "kaggle has around 80gb of system memory so offload the rest of the model into ram"

Apply this to the cognition plan for huihui-ai/Huihui-Qwen3.8-27B-abliterated on Kaggle T4x2: keep whatever fits in the 2x T4 VRAM (tensor parallel 2) and CPU-offload the remainder of the weights into host RAM (plan for ~80 GB). This is consistent with Bible §24 ("CPU weight offload permitted"). Per §24, the boot-time hardware probe still measures the actual available host RAM, and the MemoryHarness computes the offload ceiling and keeps a host reserve; the 80 GB figure is the founder's planning number, not a guarantee. Still NOT approved: any quantized/substitute checkpoint. Any dtype/precision change (e.g. BF16 -> FP16 because T4 lacks BF16 support) still needs explicit founder approval. Escalate that question to me if it comes up.


## 2026-10-22T16:13:56Z

FOUNDER DIRECTIVE (verbatim): "when its done in it's entirety, test bf16 vs fp16 and see what happens"

How to apply it:
1. Build everything in its entirety first. BF16 stays the default cognition configuration for the pinned checkpoint (huihui-ai/Huihui-Qwen3.8-27B-abliterated), using T4x2 tensor parallel plus CPU offload into host RAM (~80 GB).
2. After the full build is complete, run a documented BF16 vs FP16 comparison on Kaggle T4x2. Same checkpoint, same weights, no quantization. Run it as a KHF benchmark and record for each dtype:
   - load success or failure with exact error evidence;
   - GPU and host memory use, plus the offload amounts;
   - boot time;
   - tokens/sec and latency;
   - structured-output (ProposedAction) validity rate;
   - text and vision quality on a fixed prompt set;
   - numerical-stability issues such as NaN/inf or degenerate output.

   Deliver a written comparison report to the founder.
3. FP16 is authorized for that comparison test. It is NOT yet approved as the production default; the founder decides after seeing the report.
4. If BF16 cannot load or run on T4 during the build, do not stall the rest of the build. Record the evidence, finish every other part, and bring the BF16 vs FP16 question forward to the comparison test.
