'use strict';

/**
 * Dynamic Implementation & Contract Oracle Loader for E2E v2 (F01–F35)
 * Dynamically resolves production modules from apps/, packages/, services/
 * or gracefully falls back to the authoritative specification reference oracle.
 */

const oracle = require('./keystone_oracle');

// Try loading production packages if available
let productionContracts = null;
try {
  productionContracts = require('../../../packages/contracts/src/contracts.json');
} catch {
  productionContracts = null;
}

let productionPromptEngine = null;
try {
  productionPromptEngine = require('../../../packages/prompt-engine/src/engine');
} catch {
  productionPromptEngine = null;
}

module.exports = {
  isProductionLoaded: !!(productionContracts && productionPromptEngine),
  productionContracts,
  productionPromptEngine,
  oracle
};
