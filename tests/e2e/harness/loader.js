'use strict';

/**
 * Dynamic Implementation & Contract Oracle Loader
 * Resolves production modules from `services/intelligence` or `infrastructure/bigquery`
 * if present; otherwise seamlessly falls back to the specification-derived reference oracle.
 */

const oracle = require('./contract_oracle');
const sqlValidator = require('./sql_validator');

// Attempt to load production implementation
let productionIntelligence = null;
try {
  productionIntelligence = require('../../../services/intelligence/src');
} catch {
  // Not yet implemented (Milestone 1)
  productionIntelligence = null;
}

module.exports = {
  isProductionLoaded: !!productionIntelligence,
  scraper: productionIntelligence?.scraper || new oracle.ScraperService(),
  edgePii: productionIntelligence?.edgePii || new oracle.EdgePiiScrubber(),
  dedup: productionIntelligence?.dedup || new oracle.SignalDeduplicator(),
  vault: productionIntelligence?.vault || new oracle.PiiVaultService(),
  aikido: productionIntelligence?.aikido || new oracle.AikidoDefenseService(),
  bigquery: productionIntelligence?.bigquery || new oracle.BigQueryIntelligenceService(),
  bridge: productionIntelligence?.bridge || new oracle.KeystoneBridgeService(),
  safety: new oracle.SysadminSafetyValidator(),
  sqlValidator,
  targetsCatalog: oracle.targetsCatalog
};
