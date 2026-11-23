# SPEC B: Memory & Recipe Library (`pgvector` + Local Embeddings)

**Authority:** KEYSTONE Bible v2 (§2 Invariants 9–10, §15, §21, §42) & ADR-005  
**Target Implementation:** PR1 (schema migrations) & PR8 (embedding service, retrieval, replay, promotion)

---

## 1. Infrastructure & Closure Rule

- **Database:** PostgreSQL + `pgvector` extension.
- **Embedding Service:** Local Qwen-embedding-class model served beside the reasoning core behind `CognitiveProvider`; vector dimension recorded in `CapabilityManifest`.
- **Invariant 2 Closure:** **Zero external embedding vendors** (replaces retired BigQuery / `text-embedding-005` / `gemini-2.5-flash` pipeline).

---

## 2. Database Schema (§21, §42.2)

```sql
CREATE TABLE recipes (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    persona_id UUID NULL REFERENCES personas(id) ON DELETE SET NULL,
    envelope JSONB NOT NULL,
    compiled_prompt JSONB NOT NULL,
    seed BIGINT NOT NULL,
    fabric_versions JSONB NOT NULL,
    scores JSONB NOT NULL,
    mode VARCHAR(16) NOT NULL CHECK (mode IN ('sfw', 'unrestricted')),
    vendor BOOLEAN NOT NULL DEFAULT FALSE,
    promoted_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE recipe_embeddings (
    recipe_id UUID PRIMARY KEY REFERENCES recipes(id) ON DELETE CASCADE,
    embedding VECTOR(n) NOT NULL
);

CREATE TABLE style_rules (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    weight FLOAT NOT NULL DEFAULT 1.0,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

*(Vector dimension `n` is pinned in Alembic PR1 migration to match the operator-configured local Qwen embedding model declared in the manifest.)*

---

## 3. Compile Integration & Mode Scoping (§42.3–42.5)

- Interface: `compiler.compile(intent, mode, memory=k)`
- Mandatory filter invariant:
  ```sql
  WHERE tenant_id = :tenant_id
    AND project_id = :project_id
    AND (mode = 'sfw' OR mode = :resolved_mode)
  ORDER BY (quality_score * recency_decay) DESC
  LIMIT :k
  ```
- Under `SFW`, mature (`unrestricted`) recipes **never** surface in retrieval.
- Retrieved recipes and active `style_rules` are token-budgeted and injected strictly as **advisory (non-authority) context** (Invariant 9); the PromptCompiler remains sole prompting authority.
- Ranking considers quality score, score-per-credit (§27 measurement), recency decay, and persona affinity.

---

## 4. Replay & Promotion (§42.6–42.7)

- **Replay Route:** `POST /v1/recipes/{id}/replay` — re-executes the stored envelope + compiled prompt + seed + fabric versions through the **normal Gate** (mode check, age gate, and lawful-content floor still apply).
- **Promotion Rule (§15 / §42.7):** Operator review can promote eval-passing candidates to reusable status; automatic promotion requires **two independent passing runs** (no single result ever self-promotes).

---

## 5. Real Acceptance Tests (ADR-005)

1. Cross-tenant retrieval query returns zero rows.
2. `SFW` compile never retrieves any `unrestricted` / mature recipe.
3. `POST /v1/recipes/{id}/replay` reproduces deterministic staging (matching prompt hash, seed, and fabric version) through the Gate.
4. Automatic promotion does not trigger after 1 passing run and succeeds only after 2 independent passing runs.
