## 2026-10-22T14:57:36Z
You are the BigQuery AI/ML Layer Worker (teamwork_preview_worker) for Milestone 3.
Working directory: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m3
Project root: c:\Users\Lesia Eden\Downloads\keystone-cowork
Authoritative Request: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\ORIGINAL_REQUEST.md
Authoritative Plan: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\orchestrator_1\PROJECT.md
Test Infra: c:\Users\Lesia Eden\Downloads\keystone-cowork\TEST_INFRA.md
Test Ready: c:\Users\Lesia Eden\Downloads\keystone-cowork\TEST_READY.md
Explorer 3 Survey Report: c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\explorer_survey_3\survey_report.md

SKILLS & REFERENCES TO APPLY:
- BigQuery AI/ML: C:\Users\Lesia Eden\.gemini\config\skills\bigquery-ai-ml\SKILL.md
- BigQuery SQL: C:\Users\Lesia Eden\.gemini\config\skills\bigquery-sql\SKILL.md
- Enforcing Resource Attribution: C:\Users\Lesia Eden\.gemini\config\skills\enforcing-resource-attribution\SKILL.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

EXCLUSIVE WRITE OWNERSHIP:
Files under `infrastructure/bigquery/` ONLY:
- `infrastructure/bigquery/schemas/001_intelligence_schema.sql`
- `infrastructure/bigquery/queries/ai_procedures.sql`
- `infrastructure/bigquery/scripts/deploy_bigquery.sh`
- `infrastructure/bigquery/scripts/deploy_bigquery.ps1`
- `infrastructure/bigquery/mocks/ast_validator.js`
- `infrastructure/bigquery/README.md`
DO NOT modify any of the 21 baseline tracked files or tests in `tests/identity.test.js`.

CRITICAL BIGQUERY SYNTAX CONSTRAINTS:
1. TVF Placement: Table-Valued Functions (`AI.GENERATE_EMBEDDING`, `VECTOR_SEARCH`) MUST be placed in the `FROM` clause, NEVER in the `SELECT` list.
2. Resource Attribution: All mutating `bq` commands (`bq query`, `bq load`, `bq extract`, `bq mk`, `bq update`, `bq cp`) MUST include `--label datacloud:antigravity`. Read-only commands (`bq show`, `bq ls`, `bq rm`) MUST omit labels. All `gcloud` invocations must prepend `CLOUDSDK_METRICS_ENVIRONMENT="datacloud.antigravity"`.
3. Schema Design: Support all 6 benchmark applications (Hugging Face, Higgsfield, ZenCreator Pro, Venice AI, Adobe Creative Cloud/Firefly, Grok). Remote models must specify `REMOTE WITH CONNECTION DEFAULT`. Partition base tables by `DATE(extracted_at)` and cluster by `inferred_domain, app_name`.
4. Procedures: Implement `AI.GENERATE` (with quoted `output_schema` mapping to Keystone PromptAnatomy), `AI.SIMILARITY`, and `AI.CLASSIFY`.

TASKS:
1. Author all SQL DDL, queries, procedures, deployment scripts, and mock AST validator under `infrastructure/bigquery/`.
2. Run baseline tests: `npm test` (must pass 3/3, 100% green).
3. Run E2E tests: `node --test tests/e2e/*.test.js` and `node tests/e2e/runner.js` (must pass 132/132, 100% green).
4. Write your handoff report to `c:\Users\Lesia Eden\Downloads\keystone-cowork\.agents\teamwork\worker_m3\handoff.md` with full execution evidence and command results, and notify the orchestrator.
