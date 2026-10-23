# Handoff Report: Explorer 3 (BigQuery AI/ML & Integration/Testing Investigator)

## 1. Observation
- `c:\Users\Lesia Eden\Downloads\keystone-cowork\package.json`: Lines 8–13 define `"workspaces": ["apps/*", "packages/*", "services/*"]`, `"test": "node --test tests/*.test.js"`, and `"dev:api": "python -m uvicorn apps.api.src.main:app --reload --port 8000"`.
- `npm test` baseline run: Executed `npm test`, passed 3 of 3 tests (`tests/identity.test.js`) in 259ms (`✔ KEYSTONE preserves plan.v1 and six-part PromptAnatomy`, `✔ KEYSTONE preserves all 13 domain playbooks`, `✔ compiler remains model-agnostic with chat and reasoning profiles`). Exit code was 0.
- `c:\Users\Lesia Eden\Downloads\keystone-cowork\openapi.yaml`: Lines 253–267 define `/capabilities` returning `PublicCapability`. Lines 388–399 define `PublicCapability` schema with fields `id`, `available`, `label`, `accepts`, `produces`.
- `c:\Users\Lesia Eden\Downloads\keystone-cowork\packages\prompt-engine\src\prompt-compiler.js`: Lines 3–9 enforce six-part `PromptAnatomy` (`REQUIRED = ['role', 'task', 'context', 'constraints', 'outputFormat', 'reasoning']`).
- `c:\Users\Lesia Eden\Downloads\keystone-cowork\packages\contracts\src\contracts.json`: Defines `"plan": "plan.v1"`, `"promptAnatomy"`, `"authorityDecisions"`, `"jobStates"`.
- BigQuery AI/ML skill references (`C:\Users\Lesia Eden\.gemini\config\skills\bigquery-ai-ml\references\`):
  - `ai_function_best_practices.md`: Line 18–19 specifies that Table-Valued Functions (TVFs) including `AI.GENERATE_EMBEDDING` and `AI.GENERATE_TABLE` **must** be placed in the `FROM` clause. Line 7–8 specifies `connection => 'DEFAULT'` for remote models.
  - `ai_generate.md`: Defines `AI.GENERATE(prompt, [endpoint], [output_schema], [connection_id])` returning structured fields or `result`.
  - `ai_similarity.md`: Defines scalar `AI.SIMILARITY(content1 => ..., content2 => ..., [endpoint => ...])` returning `FLOAT64`.
  - `ai_classify.md`: Defines `AI.CLASSIFY(input, categories => [...], [output_mode => ...])` returning `STRING` or `ARRAY<STRING>`.
  - `vector_search.md`: Defines TVF `VECTOR_SEARCH(TABLE base_table, 'col', TABLE query_table, top_k => 5, distance_type => 'COSINE')` in the `FROM` clause.
- Resource attribution skill (`C:\Users\Lesia Eden\.gemini\config\skills\enforcing-resource-attribution\SKILL.md`): Line 48–58 mandates `--label datacloud:<ide>` (e.g. `datacloud:antigravity`) for mutating `bq` commands (`bq query`, `bq load`, `bq extract`, `bq mk`, `bq update`, `bq cp`) and forbids `--label` on read-only subcommands (`bq show`, `bq ls`, `bq rm`, etc.). Mandates `CLOUDSDK_METRICS_ENVIRONMENT` prepend for `gcloud`.
- Python dependency skill (`C:\Users\Lesia Eden\.gemini\config\skills\managing-python-dependencies\SKILL.md`): Line 89–103 mandates local `venv + pip + requirements.txt` when no lockfile exists, strictly forbids global `pip install`, and requires composite bundled environment probes.

## 2. Logic Chain
1. From the observation that `npm test` runs `node --test tests/*.test.js` and tests identity invariants, any additive tests must be placed either as new test files in `tests/` that pass 100% or within dedicated service directories, ensuring `npm test` remains completely green.
2. From the observation of `openapi.yaml` lines 388–399 and `contracts.json`, Keystone's existing contracts already anticipate modular capabilities via `PublicCapability`. Therefore, an additive capability manifest under `services/intelligence` or `packages/contracts/src/manifests/ux_intelligence.json` integrates without mutating core contracts.
3. From `ai_function_best_practices.md` and `ai_generate_embedding.md`, `AI.GENERATE_EMBEDDING` is a TVF that cannot be called as a scalar function in the `SELECT` clause; it must be invoked in the `FROM` clause. Downstream BigQuery SQL procedures and views must strictly follow this pattern.
4. From `enforcing-resource-attribution`, all CLI scripts invoking `bq query` or `bq mk` must attach `--label datacloud:antigravity` to avoid attribution policy violations.
5. From `managing-python-dependencies`, because no `.venv` or lockfile currently exists in the repository, any Python backend execution (such as `apps.api.src.main:app` or BigQuery client scripts) must be hosted in an isolated `.venv` created via `python -m venv .venv`, with dependencies locked into `requirements.txt`.
6. From the requirement to test across Tiers 1–4, combining Category-Partition, BVA, Pairwise Orthogonal Arrays, and Real-world workload tests ensures zero regressions on pre-built Keystone files while comprehensively verifying edge PII scrubbing, prompt injection defense, and BigQuery AI/ML analytics.

## 3. Caveats
- BigQuery remote models (`keystone_intelligence.embedding_model`, `keystone_intelligence.generative_model`) require a valid GCP project and Vertex AI connection in live production. For local CI testing, an AST query validator and mock execution harness should be supplied alongside live DDL scripts.
- Python 3.14.8 is installed on the host system. Certain legacy packages may have compatibility nuances on Python 3.14; modern packages like `fastapi`, `uvicorn`, and `pydantic` are recommended.

## 4. Conclusion
The architecture and verification strategy for R3 and R4 are completely designed, documented, and ready for implementation:
- Full BigQuery AI/ML schema, remote models, views, and stored procedures authored in `survey_report.md`.
- Strict compliance with `FROM` clause TVF syntax and `--label datacloud:antigravity` attribution established.
- Additive Keystone capability manifest and non-invasive routing outlined.
- Four-tier E2E testing framework (Category-Partition, BVA, Pairwise, Real-world workload) established.
- Baseline `npm test` confirmed green (3/3 pass), with zero modification to pre-built files.

## 5. Verification Method
- Independent command to verify baseline non-regression:
  ```bash
  npm test
  ```
  Expected output: 3 tests pass, 0 fail.
- Inspect detailed survey report:
  `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_survey_3\survey_report.md`
- Invalidation conditions: Any syntax using `AI.GENERATE_EMBEDDING` in the `SELECT` list, missing `--label datacloud:antigravity` on `bq query`, global `pip install` usage, or modification of existing pre-built files.
