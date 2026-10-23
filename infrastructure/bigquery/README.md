# KEYSTONE BigQuery AI/ML Intelligence & Embeddings Layer

> **Milestone**: Milestone 3 (R3: BigQuery AI/ML Layer)  
> **Location**: `infrastructure/bigquery/`  
> **Status**: Verified & Production-Ready  
> **Catalog Scope**: 6 Mandated Benchmark Applications (Hugging Face, Higgsfield, ZenCreator Pro, Venice AI, Adobe Creative Cloud / Firefly, Grok)

---

## 1. Overview & Architecture

The KEYSTONE BigQuery AI/ML Layer provides an enterprise analytical and semantic vector database engine for scraped UI/UX structural patterns, component trees, design tokens, and workflow contracts extracted from leading AI applications.

By embedding Vertex AI foundation models (`text-embedding-005` and `gemini-2.5-flash`) natively into BigQuery SQL, Keystone achieves high-throughput semantic similarity search, automatic domain classification, and structured 6-part `PromptAnatomy` synthesis without external orchestration latency.

```
+-----------------------------------------------------------------------------------+
|               KEYSTONE BENCHMARK INTELLIGENCE & EMBEDDING PIPELINE               |
+-----------------------------------------------------------------------------------+
  Scraped & Sanitized AST (Firecrawl + AES-256-GCM PII Vault + Aikido Quarantine)
                                     │
                                     ▼
        `infrastructure/bigquery/schemas/001_intelligence_schema.sql`
                                     │
              ┌──────────────────────┴──────────────────────┐
              ▼                                             ▼
   Dataset & Partitioned Table                   Remote Vertex AI Models
   `keystone_intelligence`                       (REMOTE WITH CONNECTION DEFAULT)
   .scraped_architectures                        - embedding_model (text-embedding-005)
   PARTITION BY DATE(extracted_at)               - generative_model (gemini-2.5-flash)
   CLUSTER BY inferred_domain, app_name
              │                                             │
              └──────────────────────┬──────────────────────┘
                                     │
                                     ▼
        `infrastructure/bigquery/queries/ai_procedures.sql`
              ┌─────────────────────────────────────────────┐
              │  TVF: AI.GENERATE_EMBEDDING (FROM clause)    │ --> 768-dim Structural Vector
              │  TVF: VECTOR_SEARCH (FROM clause)           │ --> Cosine Nearest Neighbors
              │  Scalar: AI.CLASSIFY (SELECT clause)        │ --> Domain Playbook Inferences
              │  Scalar: AI.SIMILARITY (SELECT clause)      │ --> Cross-Benchmark Similarity
              │  Scalar: AI.GENERATE (SELECT clause)        │ --> 6-Part PromptAnatomy Struct
              └─────────────────────────────────────────────┘
                                     │
                                     ▼
                      Keystone Prompt Engine & Playbooks
```

---

## 2. Directory Layout & Artifacts

```
infrastructure/bigquery/
├── README.md                           # Authoritative technical documentation
├── schemas/
│   └── 001_intelligence_schema.sql    # Dataset DDL, remote models, base tables, views
├── queries/
│   └── ai_procedures.sql               # Stored procedures, TVFs, similarity & synthesis queries
├── scripts/
│   ├── deploy_bigquery.sh              # Non-interactive Bash deployment script
│   └── deploy_bigquery.ps1             # Non-interactive PowerShell deployment script
└── mocks/
    └── ast_validator.js                # Offline AST parser, syntax checker, simulation harness
```

---

## 3. Critical BigQuery Syntax Invariants

All SQL artifacts and deployment scripts strictly adhere to BigQuery ML syntax invariants:

### A. Table-Valued Function (TVF) Placement Invariant
- **Rule**: Table-Valued Functions (`AI.GENERATE_EMBEDDING`, `VECTOR_SEARCH`, `AI.GENERATE_TABLE`) **MUST** appear in the `FROM` clause. They are strictly prohibited from the `SELECT` list.
- **Valid Pattern**:
  ```sql
  SELECT base.pattern_id, emb.embedding
  FROM `keystone_intelligence.scraped_architectures` base,
  AI.GENERATE_EMBEDDING(
    MODEL `keystone_intelligence.embedding_model`,
    (SELECT base.component_summary AS content),
    STRUCT('RETRIEVAL_DOCUMENT' AS task_type, 768 AS output_dimensionality)
  ) emb;
  ```
- **Prohibited Pattern (Violates Syntax)**:
  ```sql
  -- REJECTED: TVF placed in SELECT list
  SELECT pattern_id, AI.GENERATE_EMBEDDING(...) FROM scraped_architectures;
  ```

### B. Remote Model Connection Declaration
- Remote models interfacing with Vertex AI endpoints must specify `REMOTE WITH CONNECTION DEFAULT`:
  ```sql
  CREATE OR REPLACE MODEL `keystone_intelligence.embedding_model`
  REMOTE WITH CONNECTION DEFAULT
  OPTIONS (ENDPOINT = 'text-embedding-005');
  ```

### C. Quoted `output_schema` Parameter
- In `AI.GENERATE`, structured output extraction requires the `output_schema` argument to be a **quoted string literal**:
  ```sql
  AI.GENERATE(
    prompt,
    endpoint => 'gemini-2.5-flash',
    output_schema => 'role STRING, task STRING, context ARRAY<STRING>, constraints ARRAY<STRING>, outputFormat STRING, reasoning STRING'
  )
  ```

### D. Table Partitioning & Clustering
- Base tables must be partitioned by `DATE(extracted_at)` and clustered by `inferred_domain, app_name` for query cost efficiency and partition pruning:
  ```sql
  PARTITION BY DATE(extracted_at)
  CLUSTER BY inferred_domain, app_name;
  ```

---

## 4. Mandatory Resource Attribution Rules

To track resources manipulated by AI agents per `enforcing-resource-attribution`:

### A. BigQuery CLI (`bq`) Attribution
- **Mutating Commands** (`bq query`, `bq load`, `bq extract`, `bq mk`, `bq update`, `bq cp`):
  **MUST** include `--label datacloud:antigravity`.
  ```bash
  bq mk --dataset --label datacloud:antigravity keystone_intelligence
  bq query --use_legacy_sql=false --label datacloud:antigravity "SELECT count(*) FROM ..."
  ```
- **Read-Only Commands** (`bq show`, `bq ls`, `bq version`, `bq rm`, `bq cancel`, `bq head`):
  **MUST OMIT** `--label` (the flag is unsupported on read-only subcommands and causes errors).
  ```bash
  bq show keystone_intelligence.scraped_architectures
  bq ls keystone_intelligence
  ```

### B. Google Cloud SDK (`gcloud`) Metrics Attribution
- All `gcloud` invocations must set or prepend the `CLOUDSDK_METRICS_ENVIRONMENT` variable:
  - **Bash**:
    ```bash
    export CLOUDSDK_METRICS_ENVIRONMENT="${CLOUDSDK_METRICS_ENVIRONMENT:+$CLOUDSDK_METRICS_ENVIRONMENT }datacloud.antigravity"
    ```
  - **PowerShell**:
    ```powershell
    $env:CLOUDSDK_METRICS_ENVIRONMENT = if ($env:CLOUDSDK_METRICS_ENVIRONMENT) { "$($env:CLOUDSDK_METRICS_ENVIRONMENT) datacloud.antigravity" } else { "datacloud.antigravity" }
    ```

---

## 5. 6-Target Benchmark Application Catalog

The intelligence schema and procedures natively support and categorize all six mandated benchmark applications:

| # | Benchmark Application | Inferred Domain | Primary UX Patterns | Key Components |
|---|-----------------------|-----------------|---------------------|----------------|
| 1 | **Hugging Face Spaces/Hub** | `software` / `creative` | Diffusion sliders, prompt canvas, model cards | `GradioCanvas`, `DiffusionSlider`, `ModelCard` |
| 2 | **Higgsfield** | `creative` | Video & motion timelines, camera curves | `VideoMotionTimeline`, `KeyframeCurve`, `CameraControl` |
| 3 | **ZenCreator Pro** | `orchestration` | Multi-track timelines, node graph editor | `NodeEditorGraph`, `MultiTrackTimeline`, `AssetComposer` |
| 4 | **Venice AI** | `research` | Privacy-first chat, ephemeral parameters | `EphemeralChatView`, `PrivacyBoundaryShield`, `ZeroRetention` |
| 5 | **Adobe Creative Cloud / Firefly** | `creative` / `design` | Generative fill, vector presets, brush engines | `GenerativeFillPalette`, `VectorPresetDrawer`, `BrushStyleEngine` |
| 6 | **Grok** | `software` / `research` | Multimodal reasoning, interactive thinking traces | `ThinkingTraceViewer`, `CitationChipList`, `ReasoningStepTree` |

---

## 6. Stored Procedures & Analytical Primitives

### `keystone_intelligence.sp_ingest_and_embed_pattern`
- **Purpose**: Idempotent ingestion of deconstructed UI/UX benchmark signals.
- **Workflow**:
  1. Classifies component summary into canonical Keystone domain playbooks via `AI.CLASSIFY`.
  2. Generates 768-dimensional vector embedding via TVF `AI.GENERATE_EMBEDDING` in `FROM` clause.
  3. Executes `MERGE INTO` keyed on `sha256_hash`: updates matched records or inserts new records.
  4. Sets `p_status = 'SUCCESS'`.

### `keystone_intelligence.sp_synthesize_prompt_anatomy`
- **Purpose**: Maps scraped architectural summaries into canonical Keystone 6-part `PromptAnatomy`.
- **Workflow**:
  1. Wraps untrusted component markup within `<untrusted_content>` containment tags.
  2. Executes `AI.GENERATE` with quoted `output_schema` defining `role`, `task`, `context`, `constraints`, `outputFormat`, and `reasoning`.

### `keystone_intelligence.sp_compute_architecture_similarity`
- **Purpose**: Scalar cosine similarity calculation between two benchmark patterns via `AI.SIMILARITY`.

### `keystone_intelligence.sp_classify_architecture`
- **Purpose**: Direct classification of component summaries into domain playbooks (`software`, `creative`, `research`, `analytics`, `marketing`, `orchestration`) via `AI.CLASSIFY`.

### `keystone_intelligence.sp_semantic_vector_search`
- **Purpose**: Nearest-neighbor semantic search using TVF `VECTOR_SEARCH` in `FROM` clause over 768-dim structural embeddings with cosine distance metric.

---

## 7. Deployment Instructions

### Linux / macOS (Bash)
```bash
# Set execute permissions
chmod +x infrastructure/bigquery/scripts/deploy_bigquery.sh

# Dry-run validation (verifies syntax without calling GCP)
./infrastructure/bigquery/scripts/deploy_bigquery.sh --dry-run

# Production deployment
./infrastructure/bigquery/scripts/deploy_bigquery.sh --project my-gcp-project --location US
```

### Windows (PowerShell)
```powershell
# Dry-run validation
powershell -NoProfile -NonInteractive -File .\infrastructure\bigquery\scripts\deploy_bigquery.ps1 -DryRun

# Production deployment
powershell -NoProfile -NonInteractive -File .\infrastructure\bigquery\scripts\deploy_bigquery.ps1 -ProjectId "my-gcp-project" -Location "US"
```

---

## 8. Verification & Test Execution

### 1. Offline AST Syntax & Attribution Self-Test
```bash
node infrastructure/bigquery/mocks/ast_validator.js
```
*Expected: 8/8 checks passing (DDL validation, TVF placement, attribution syntax, 768-dim vector search simulation).*

### 2. Baseline Invariant Preservation
```bash
npm test
```
*Expected: 3/3 tests passing (tests/identity.test.js).*

### 3. Comprehensive E2E Verification Suite
```bash
node --test tests/e2e/*.test.js
# Or using the tiered runner:
node tests/e2e/runner.js
```
*Expected: 132/132 tests passing across Tiers 1-4.*
