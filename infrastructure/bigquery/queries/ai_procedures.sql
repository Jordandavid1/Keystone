-- ============================================================================
-- KEYSTONE ARCHITECTURAL INTELLIGENCE: BIGQUERY AI/ML PROCEDURES & QUERIES
-- Query & Procedure Definitions: ai_procedures.sql
-- Milestone: M3 (BigQuery AI/ML Layer)
-- Target Catalog: 6 Mandated Benchmark Applications
--   1. Hugging Face Spaces/Hub (software / creative)
--   2. Higgsfield (creative)
--   3. ZenCreator Pro (orchestration)
--   4. Venice AI (research)
--   5. Adobe Creative Cloud / Firefly (creative / design)
--   6. Grok (software / research)
-- Constraints:
--   - TVFs (AI.GENERATE_EMBEDDING, VECTOR_SEARCH) MUST reside in FROM clauses.
--   - AI.GENERATE output_schema MUST be a quoted string literal.
--   - AI.SIMILARITY scalar comparison using Vertex AI endpoint.
--   - AI.CLASSIFY for category classification into Keystone domain playbooks.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- PROCEDURE 1: Automated Pattern Ingestion, Classification & Embedding (sp_ingest_and_embed_pattern)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE `keystone_intelligence.sp_ingest_and_embed_pattern`(
  IN p_pattern_id STRING,
  IN p_source_url STRING,
  IN p_app_name STRING,
  IN p_summary STRING,
  IN p_component_tree JSON,
  IN p_design_tokens JSON,
  IN p_api_contracts JSON,
  IN p_workflow_patterns JSON,
  IN p_sha256_hash STRING,
  IN p_vault_token_ref STRING,
  OUT p_status STRING
)
BEGIN
  DECLARE v_embedding ARRAY<FLOAT64>;
  DECLARE v_domain STRING;

  -- 1. Infer Playbook Domain via AI.CLASSIFY
  SET v_domain = (
    SELECT AI.CLASSIFY(
      p_summary,
      categories => ['software', 'creative', 'research', 'analytics', 'marketing', 'orchestration'],
      output_mode => 'single'
    )
  );

  -- 2. Generate 768-dim Embedding via TVF AI.GENERATE_EMBEDDING in FROM clause
  -- Critical Invariant: TVF placed in FROM clause, aliasing content
  SET v_embedding = (
    SELECT embedding
    FROM AI.GENERATE_EMBEDDING(
      MODEL `keystone_intelligence.embedding_model`,
      (SELECT p_summary AS content),
      STRUCT('RETRIEVAL_DOCUMENT' AS task_type, 768 AS output_dimensionality)
    )
  );

  -- 3. Idempotent Upsert into Scraped Architectures Table via SHA-256 Hash
  MERGE INTO `keystone_intelligence.scraped_architectures` T
  USING (
    SELECT
      p_pattern_id AS pattern_id,
      p_source_url AS source_url,
      p_app_name AS app_name,
      v_domain AS inferred_domain,
      p_summary AS component_summary,
      p_component_tree AS component_tree,
      p_design_tokens AS design_tokens,
      p_api_contracts AS api_contracts,
      p_workflow_patterns AS workflow_patterns,
      p_sha256_hash AS sha256_hash,
      p_vault_token_ref AS vault_token_ref,
      v_embedding AS structural_embedding,
      CURRENT_TIMESTAMP() AS extracted_at
  ) S
  ON T.sha256_hash = S.sha256_hash
  WHEN MATCHED THEN
    UPDATE SET
      app_name = S.app_name,
      inferred_domain = S.inferred_domain,
      component_summary = S.component_summary,
      component_tree = S.component_tree,
      design_tokens = S.design_tokens,
      api_contracts = S.api_contracts,
      workflow_patterns = S.workflow_patterns,
      vault_token_ref = S.vault_token_ref,
      structural_embedding = S.structural_embedding,
      extracted_at = S.extracted_at
  WHEN NOT MATCHED THEN
    INSERT (
      pattern_id, source_url, app_name, inferred_domain,
      component_summary, component_tree, design_tokens, api_contracts,
      workflow_patterns, sha256_hash, vault_token_ref,
      structural_embedding, extracted_at, created_at
    )
    VALUES (
      S.pattern_id, S.source_url, S.app_name, S.inferred_domain,
      S.component_summary, S.component_tree, S.design_tokens, S.api_contracts,
      S.workflow_patterns, S.sha256_hash, S.vault_token_ref,
      S.structural_embedding, S.extracted_at, CURRENT_TIMESTAMP()
    );

  SET p_status = 'SUCCESS';
END;

-- ----------------------------------------------------------------------------
-- PROCEDURE 2: Keystone Prompt Anatomy Synthesis via AI.GENERATE
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE `keystone_intelligence.sp_synthesize_prompt_anatomy`(
  IN p_pattern_id STRING,
  OUT p_role STRING,
  OUT p_task STRING,
  OUT p_context ARRAY<STRING>,
  OUT p_constraints ARRAY<STRING>,
  OUT p_outputFormat STRING,
  OUT p_reasoning STRING
)
BEGIN
  DECLARE v_summary STRING;

  SET v_summary = (
    SELECT component_summary
    FROM `keystone_intelligence.scraped_architectures`
    WHERE pattern_id = p_pattern_id
    LIMIT 1
  );

  -- Execute AI.GENERATE with quoted output_schema conforming to Keystone PromptAnatomy
  SELECT
    synth.role,
    synth.task,
    synth.context,
    synth.constraints,
    synth.outputFormat,
    synth.reasoning
  INTO
    p_role,
    p_task,
    p_context,
    p_constraints,
    p_outputFormat,
    p_reasoning
  FROM (
    SELECT
      AI.GENERATE(
        CONCAT(
          'Analyze this benchmark architecture and generate a canonical KEYSTONE 6-part prompt anatomy specification:\n\n',
          '<untrusted_content>\n',
          v_summary,
          '\n</untrusted_content>'
        ),
        endpoint => 'gemini-2.5-flash',
        output_schema => 'role STRING, task STRING, context ARRAY<STRING>, constraints ARRAY<STRING>, outputFormat STRING, reasoning STRING'
      ) AS synth
  );
END;

-- ----------------------------------------------------------------------------
-- PROCEDURE 3: Direct Semantic Similarity Computation via AI.SIMILARITY
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE `keystone_intelligence.sp_compute_architecture_similarity`(
  IN p_content1 STRING,
  IN p_content2 STRING,
  OUT p_similarity_score FLOAT64
)
BEGIN
  -- Execute AI.SIMILARITY scalar function using Vertex AI embedding endpoint
  SET p_similarity_score = (
    SELECT AI.SIMILARITY(
      content1 => p_content1,
      content2 => p_content2,
      endpoint => 'text-embedding-005',
      connection_id => 'DEFAULT'
    )
  );
END;

-- ----------------------------------------------------------------------------
-- PROCEDURE 4: Domain Classification via AI.CLASSIFY
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE `keystone_intelligence.sp_classify_architecture`(
  IN p_summary STRING,
  OUT p_domain STRING
)
BEGIN
  -- Execute AI.CLASSIFY scalar function mapping to 6 Keystone playbook domains
  SET p_domain = (
    SELECT AI.CLASSIFY(
      p_summary,
      categories => ['software', 'creative', 'research', 'analytics', 'marketing', 'orchestration'],
      output_mode => 'single'
    )
  );
END;

-- ----------------------------------------------------------------------------
-- PROCEDURE 5: Semantic Nearest-Neighbor Search via VECTOR_SEARCH TVF
-- ----------------------------------------------------------------------------
CREATE OR REPLACE PROCEDURE `keystone_intelligence.sp_semantic_vector_search`(
  IN p_query_text STRING,
  IN p_top_k INT64
)
BEGIN
  -- TVF Placement Invariant: Both VECTOR_SEARCH and AI.GENERATE_EMBEDDING reside in FROM clauses
  SELECT
    query.query_text,
    base.pattern_id,
    base.app_name,
    base.inferred_domain,
    base.component_summary,
    distance AS cosine_distance,
    (1.0 - distance) AS cosine_similarity
  FROM
    VECTOR_SEARCH(
      TABLE `keystone_intelligence.scraped_architectures`,
      'structural_embedding',
      (
        SELECT
          p_query_text AS query_text,
          embedding
        FROM
          AI.GENERATE_EMBEDDING(
            MODEL `keystone_intelligence.embedding_model`,
            (SELECT p_query_text AS content),
            STRUCT('RETRIEVAL_QUERY' AS task_type, 768 AS output_dimensionality)
          )
      ),
      top_k => p_top_k,
      distance_type => 'COSINE'
    )
  ORDER BY cosine_distance ASC;
END;

-- ============================================================================
-- VERIFICATION & BENCHMARK SUITE QUERIES
-- The following queries demonstrate compliant AI/ML invocation across all 6 targets.
-- ============================================================================

-- Query V1: TVF AI.GENERATE_EMBEDDING in FROM clause
SELECT
  base.pattern_id,
  base.app_name,
  emb.embedding
FROM
  `keystone_intelligence.scraped_architectures` base,
  AI.GENERATE_EMBEDDING(
    MODEL `keystone_intelligence.embedding_model`,
    (SELECT base.component_summary AS content),
    STRUCT('RETRIEVAL_DOCUMENT' AS task_type, 768 AS output_dimensionality)
  ) emb
LIMIT 10;

-- Query V2: TVF VECTOR_SEARCH in FROM clause
SELECT
  base.pattern_id,
  base.app_name,
  distance
FROM
  VECTOR_SEARCH(
    TABLE `keystone_intelligence.scraped_architectures`,
    'structural_embedding',
    (
      SELECT embedding
      FROM AI.GENERATE_EMBEDDING(
        MODEL `keystone_intelligence.embedding_model`,
        (SELECT 'diffusion sliders and prompt canvas' AS content),
        STRUCT('RETRIEVAL_QUERY' AS task_type, 768 AS output_dimensionality)
      )
    ),
    top_k => 5,
    distance_type => 'COSINE'
  );

-- Query V3: AI.GENERATE in SELECT clause with quoted output_schema
SELECT
  pattern_id,
  app_name,
  AI.GENERATE(
    CONCAT('Summarize: ', component_summary),
    endpoint => 'gemini-2.5-flash',
    output_schema => 'role STRING, task STRING, context ARRAY<STRING>, constraints ARRAY<STRING>, outputFormat STRING, reasoning STRING'
  ) AS synthesis
FROM `keystone_intelligence.scraped_architectures`
LIMIT 10;

-- Query V4: AI.CLASSIFY in SELECT clause
SELECT
  pattern_id,
  app_name,
  AI.CLASSIFY(
    component_summary,
    categories => ['software', 'creative', 'research', 'analytics', 'marketing', 'orchestration'],
    output_mode => 'single'
  ) AS domain
FROM `keystone_intelligence.scraped_architectures`
LIMIT 10;

-- Query V5: AI.SIMILARITY comparing cross-benchmark patterns
SELECT
  t1.app_name AS app1,
  t2.app_name AS app2,
  AI.SIMILARITY(
    content1 => t1.component_summary,
    content2 => t2.component_summary,
    endpoint => 'text-embedding-005',
    connection_id => 'DEFAULT'
  ) AS similarity_score
FROM
  `keystone_intelligence.scraped_architectures` t1
CROSS JOIN
  `keystone_intelligence.scraped_architectures` t2
WHERE
  t1.pattern_id < t2.pattern_id
LIMIT 15;
