'use strict';

/**
 * Additive Keystone Capability Manifest
 * Declares the OpenAPI-compliant capability manifest for the UX & Architecture Intelligence Harvester.
 */

const CAPABILITY_MANIFEST = {
  id: 'intelligence.ux_harvester',
  available: true,
  label: 'UX & Architecture Intelligence Harvester',
  accepts: ['url', 'dom_snapshot', 'ux_pattern_spec'],
  produces: ['component_tree', 'design_tokens', 'plan.v1', 'similarity_matches'],
  authorityLevel: 'restricted',
  policies: ['pii-vault-compliance', 'aikido-injection-defense', 'dedup-verification'],
  contracts: {
    outputPlan: 'plan.v1',
    promptAnatomy: ['role', 'task', 'context', 'constraints', 'outputFormat', 'reasoning']
  }
};

/**
 * Returns a clone of the capability manifest.
 * @returns {object} PublicCapability manifest
 */
function getCapabilityManifest() {
  return JSON.parse(JSON.stringify(CAPABILITY_MANIFEST));
}

/**
 * Validates whether a given capability manifest conforms to the OpenAPI specification.
 * @param {object} manifest 
 * @returns {{ valid: boolean, missing: string[] }}
 */
function validateCapabilityManifest(manifest) {
  if (!manifest || typeof manifest !== 'object') {
    return { valid: false, missing: ['manifest'] };
  }
  const required = ['id', 'available', 'label', 'accepts', 'produces', 'authorityLevel', 'contracts'];
  const missing = required.filter(k => !(k in manifest));
  return {
    valid: missing.length === 0,
    missing
  };
}

module.exports = {
  CAPABILITY_MANIFEST,
  getCapabilityManifest,
  validateCapabilityManifest
};
