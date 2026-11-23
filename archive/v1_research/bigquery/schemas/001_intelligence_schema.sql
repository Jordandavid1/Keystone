-- ============================================================================
-- KEYSTONE ARCHITECTURAL INTELLIGENCE: BIGQUERY DDL DEFINITIONS
-- Schema Version: 001_intelligence_schema.sql
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
--   - Remote models MUST specify REMOTE WITH CONNECTION DEFAULT.
--   - Partitioning by DATE(extracted_at), clustering by inferred_domain, app_name.
--   - Resource attribution label: datacloud:antigravity.
-- ============================================================================

-- 1. Create Intelligence Dataset with Mandatory Antigravity Attribution Label
CREATE SCHEMA IF NOT EXISTS `keystone_intelligence`
OPTIONS (
  location = 'US',
  labels = [("datacloud", "antigravity"), ("service", "keystone_intelligence")]
);

-- 2. Create Remote Embedding Model (Vertex AI text-embedding-005)
-- Invariant: Remote models MUST specify REMOTE WITH CONNECTION DEFAULT
CREATE OR REPLACE MODEL `keystone_intelligence.embedding_model`
REMOTE WITH CONNECTION DEFAULT
OPTIONS (ENDPOINT = 'text-embedding-005');

-- 3. Create Remote Generative Model (Vertex AI gemini-2.5-flash)
-- Invariant: Remote models MUST specify REMOTE WITH CONNECTION DEFAULT
CREATE OR REPLACE MODEL `keystone_intelligence.generative_model`
REMOTE WITH CONNECTION DEFAULT
OPTIONS (ENDPOINT = 'gemini-2.5-flash');

-- 4. Base Table: Scraped UI/UX Architectures & Structural Patterns
-- Invariant: PARTITION BY DATE(extracted_at) CLUSTER BY inferred_domain, app_name
CREATE TABLE IF NOT EXISTS `keystone_intelligence.scraped_architectures` (
  pattern_id STRING NOT NULL,
  source_url STRING NOT NULL,
  app_name STRING NOT NULL,
  inferred_domain STRING,
  component_summary STRING NOT NULL,
  component_tree JSON,
  design_tokens JSON,
  api_contracts JSON,
  workflow_patterns JSON,
  sha256_hash STRING NOT NULL,
  vault_token_ref STRING,
  structural_embedding ARRAY<FLOAT64>,
  extracted_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
)
PARTITION BY DATE(extracted_at)
CLUSTER BY inferred_domain, app_name;

-- 5. Analytical View: Semantic Classification of Scraped Architectures
-- Uses AI.CLASSIFY in SELECT clause with canonical Keystone domains
CREATE OR REPLACE VIEW `keystone_intelligence.v_architecture_classifications` AS
SELECT
  pattern_id,
  app_name,
  source_url,
  component_summary,
  AI.CLASSIFY(
    component_summary,
    categories => ['software', 'creative', 'research', 'analytics', 'marketing', 'orchestration'],
    output_mode => 'single'
  ) AS classified_domain,
  extracted_at
FROM `keystone_intelligence.scraped_architectures`;

-- 6. Analytical View: Structured Prompt Anatomy Synthesis via AI.GENERATE
-- Uses AI.GENERATE in SELECT clause with quoted output_schema conforming to Keystone 6-part anatomy
-- Structural quarantine: Input wrapped in <untrusted_content> to prevent prompt injection
CREATE OR REPLACE VIEW `keystone_intelligence.v_prompt_anatomy_synthesis` AS
SELECT
  pattern_id,
  app_name,
  source_url,
  inferred_domain,
  AI.GENERATE(
    CONCAT(
      'Analyze this benchmark architecture and generate a canonical KEYSTONE 6-part prompt anatomy specification:\n\n',
      '<untrusted_content>\n',
      component_summary,
      '\n</untrusted_content>'
    ),
    endpoint => 'gemini-2.5-flash',
    output_schema => 'role STRING, task STRING, context ARRAY<STRING>, constraints ARRAY<STRING>, outputFormat STRING, reasoning STRING'
  ).*
FROM `keystone_intelligence.scraped_architectures`;

-- 7. Analytical View: Semantic Vector Search
-- TVF Placement Invariant: Both VECTOR_SEARCH and AI.GENERATE_EMBEDDING MUST reside in FROM clause
CREATE OR REPLACE VIEW `keystone_intelligence.v_similar_architectures` AS
SELECT
  query.search_query,
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
        search_query,
        embedding
      FROM
        AI.GENERATE_EMBEDDING(
          MODEL `keystone_intelligence.embedding_model`,
          (SELECT 'interactive canvas with node graph orchestration and generative controls' AS content, 'interactive canvas' AS search_query),
          STRUCT('RETRIEVAL_QUERY' AS task_type, 768 AS output_dimensionality)
        )
    ),
    top_k => 5,
    distance_type => 'COSINE'
  );

-- 8. Reference View: Benchmark Application Catalog
-- Documents and tracks all 6 mandated benchmark targets across the Keystone intelligence pipeline
CREATE OR REPLACE VIEW `keystone_intelligence.v_benchmark_catalog` AS
SELECT * FROM UNNEST([
  STRUCT(
    'hf-space-gradio' AS target_id,
    'Hugging Face Spaces/Hub' AS app_name,
    'https://huggingface.co/spaces' AS base_url,
    'software' AS canonical_domain,
    'Interactive Gradio prompt canvas, diffusion sliders, and community model cards' AS core_capability,
    ARRAY['GradioCanvas', 'DiffusionSlider', 'ModelCard', 'ParameterPanel', 'RunButton'] AS key_components
  ),
  STRUCT(
    'higgsfield-motion' AS target_id,
    'Higgsfield' AS app_name,
    'https://higgsfield.ai' AS base_url,
    'creative' AS canonical_domain,
    'Video and motion generative AI controls, frame interpolators, and camera motion curves' AS core_capability,
    ARRAY['VideoMotionTimeline', 'KeyframeCurve', 'CameraControl', 'InterpolationSlider', 'RenderPreview'] AS key_components
  ),
  STRUCT(
    'zencreator-studio' AS target_id,
    'ZenCreator Pro' AS app_name,
    'https://zencreator.pro' AS base_url,
    'orchestration' AS canonical_domain,
    'Creator studio workflows, multi-track node timelines, and asset export trees' AS core_capability,
    ARRAY['NodeEditorGraph', 'MultiTrackTimeline', 'AssetComposer', 'ExportMatrix', 'PipelineOrchestrator'] AS key_components
  ),
  STRUCT(
    'venice-ai-privacy' AS target_id,
    'Venice AI' AS app_name,
    'https://venice.ai' AS base_url,
    'research' AS canonical_domain,
    'Privacy-first generative AI interfaces, zero-log ephemeral pipelines, and decentralized inference endpoints' AS core_capability,
    ARRAY['EphemeralChatView', 'PrivacyBoundaryShield', 'ModelSelector', 'ParameterDrawer', 'ZeroRetentionIndicator'] AS key_components
  ),
  STRUCT(
    'adobe-firefly-tools' AS target_id,
    'Adobe Creative Cloud / Firefly' AS app_name,
    'https://firefly.adobe.com' AS base_url,
    'creative' AS canonical_domain,
    'Enterprise creative tooling pipelines, generative fill palettes, vector presets, and brush engines' AS core_capability,
    ARRAY['GenerativeFillPalette', 'VectorPresetDrawer', 'BrushStyleEngine', 'LayerStack', 'EnterpriseAssetManager'] AS key_components
  ),
  STRUCT(
    'grok-multimodal' AS target_id,
    'Grok' AS app_name,
    'https://x.ai' AS base_url,
    'software' AS canonical_domain,
    'Multimodal reasoning UX, interactive thinking trees, source citations, and real-time query controls' AS core_capability,
    ARRAY['ThinkingTraceViewer', 'CitationChipList', 'RealtimeQueryInput', 'ReasoningStepTree', 'SourceVerificationBadge'] AS key_components
  )
]);
