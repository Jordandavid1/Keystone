'use strict';

/**
 * KEYSTONE Intelligence Service Boundary
 * Unified export module providing Firecrawl scraping, UX deconstruction,
 * PII Vault boundary encryption, and Aikido prompt injection defense.
 */

const { ScraperService, FirecrawlClient } = require('./scraper/firecrawl_client');
const { AstDeconstructor, targetsCatalog } = require('./scraper/ast_deconstructor');
const { EdgePiiScrubber } = require('./scraper/edge_pii');
const { SignalDeduplicator } = require('./scraper/dedup_cache');
const { PiiVaultService } = require('./vault/vault_service');
const { AikidoDefenseService } = require('./security/aikido_defense');
const { KeystoneBridgeService } = require('./bridge/prompt_bridge');
const { getCapabilityManifest, validateCapabilityManifest } = require('./bridge/capability_manifest');

// BigQuery Intelligence Service fallback simulation
class BigQueryIntelligenceService {
  constructor() {
    this.tableStore = [];
  }

  validateDdl(ddl) {
    if (!ddl || typeof ddl !== 'string') return { valid: false, errors: ['DDL_EMPTY'] };
    const errors = [];

    if (ddl.includes('CREATE SCHEMA') && !ddl.includes('keystone_intelligence')) {
      errors.push('INVALID_SCHEMA_NAME: Dataset name must be keystone_intelligence.');
    }
    if (ddl.includes('CREATE SCHEMA') && !ddl.includes('datacloud') && !ddl.includes('antigravity')) {
      errors.push('MISSING_DATASET_LABEL: Dataset must include datacloud:antigravity label.');
    }
    if (ddl.includes('CREATE OR REPLACE MODEL') && !ddl.includes('REMOTE WITH CONNECTION DEFAULT')) {
      errors.push('MISSING_REMOTE_CONNECTION: Model must specify REMOTE WITH CONNECTION DEFAULT.');
    }
    if (ddl.includes('CREATE TABLE') && !ddl.includes('PARTITION BY DATE(extracted_at)')) {
      errors.push('MISSING_PARTITION: scraped_architectures must be partitioned by DATE(extracted_at).');
    }
    if (ddl.includes('CREATE TABLE') && !ddl.includes('CLUSTER BY inferred_domain, app_name')) {
      errors.push('MISSING_CLUSTER: scraped_architectures must be clustered by inferred_domain, app_name.');
    }

    return { valid: errors.length === 0, errors };
  }

  simulateIngestAndEmbed(patternData) {
    if (!patternData || !patternData.pattern_id || !patternData.sha256_hash) {
      throw new Error('INVALID_INGEST_PAYLOAD: pattern_id and sha256_hash are required.');
    }

    const existingIndex = this.tableStore.findIndex(p => p.sha256_hash === patternData.sha256_hash);
    const embedding = patternData.structural_embedding || Array(768).fill(0.01);

    if (existingIndex >= 0) {
      this.tableStore[existingIndex] = {
        ...this.tableStore[existingIndex],
        ...patternData,
        structural_embedding: embedding,
        updated_at: new Date().toISOString()
      };
      return { status: 'SUCCESS', action: 'UPDATED', pattern_id: patternData.pattern_id };
    }

    const record = {
      ...patternData,
      structural_embedding: embedding,
      created_at: new Date().toISOString()
    };
    this.tableStore.push(record);
    return { status: 'SUCCESS', action: 'INSERTED', pattern_id: patternData.pattern_id };
  }

  simulateVectorSearch(queryEmbedding, topK = 5) {
    if (!Array.isArray(queryEmbedding) || queryEmbedding.length !== 768) {
      throw new Error('INVALID_EMBEDDING_DIMENSION: Embedding must be an array of exactly 768 floats.');
    }
    if (topK <= 0) {
      throw new Error('INVALID_TOP_K: topK must be positive integer.');
    }

    return this.tableStore.slice(0, topK).map((item, idx) => ({
      pattern_id: item.pattern_id,
      app_name: item.app_name,
      inferred_domain: item.inferred_domain,
      cosine_distance: 0.12 + idx * 0.05,
      cosine_similarity: 0.88 - idx * 0.05
    }));
  }
}

// Default Service Singletons
const scraper = new ScraperService();
const edgePii = new EdgePiiScrubber();
const dedup = new SignalDeduplicator();
const vault = new PiiVaultService();
const aikido = new AikidoDefenseService();
const bigquery = new BigQueryIntelligenceService();
const bridge = new KeystoneBridgeService();

module.exports = {
  // Service Singletons (Required by tests/e2e/harness/loader.js)
  scraper,
  edgePii,
  dedup,
  vault,
  aikido,
  bigquery,
  bridge,

  // Service Classes
  ScraperService,
  FirecrawlClient,
  AstDeconstructor,
  EdgePiiScrubber,
  SignalDeduplicator,
  PiiVaultService,
  AikidoDefenseService,
  BigQueryIntelligenceService,
  KeystoneBridgeService,

  // Metadata & Schemas
  targetsCatalog,
  getCapabilityManifest,
  validateCapabilityManifest,

  // Functional Convenience API for External Callers
  quarantineUntrustedContent: (content) => aikido.quarantine(content),
  escapeDelimiterTags: (content) => aikido.escapeDelimiters(content),
  scanInjectionThreat: (content) => aikido.scanThreat(content),
  sanitizeModelOutput: (output) => aikido.sanitizeOutput(output),

  tokenizePii: (plaintext, subjectId, entityType) => vault.tokenize(plaintext, subjectId, entityType),
  detokenizePii: (token, authorityEnvelope) => vault.detokenize(token, authorityEnvelope),
  purgeSubjectGdpr: (subjectId, actorId) => vault.purgeSubject(subjectId, actorId),

  scrapeBenchmark: (url, options) => scraper.scrapeBenchmark(url, options),
  deconstructBenchmark: (html, url) => scraper.deconstructBenchmark(html, url),
  computeSignalHash: (url, entityType, payload) => dedup.computeHash(url, entityType, payload)
};
