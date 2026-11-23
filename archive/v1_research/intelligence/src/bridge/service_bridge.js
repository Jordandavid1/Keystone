'use strict';

/**
 * KEYSTONE Service Bridge
 * Connects intelligence capabilities (harvester, vault, aikido defense, BigQuery procedures)
 * to the Keystone runtime, PromptAnatomy context engine, and API execution pipeline.
 */

const path = require('node:path');
const fs = require('node:fs');

const { CAPABILITY_MANIFEST, getCapabilityManifest, validateCapabilityManifest } = require('./capability_manifest');
const { KeystoneBridgeService } = require('./prompt_bridge');
const { ScraperService, FirecrawlClient } = require('../scraper/firecrawl_client');
const { AstDeconstructor, targetsCatalog } = require('../scraper/ast_deconstructor');
const { EdgePiiScrubber } = require('../scraper/edge_pii');
const { SignalDeduplicator } = require('../scraper/dedup_cache');
const { PiiVaultService } = require('../vault/vault_service');
const { AikidoDefenseService } = require('../security/aikido_defense');
const { generate } = require('../../../../packages/prompt-engine/src/engine');
const { compilePrompt } = require('../../../../packages/prompt-engine/src/prompt-compiler');

class ServiceBridge {
  constructor(options = {}) {
    this.scraper = options.scraper || new ScraperService();
    this.edgePii = options.edgePii || new EdgePiiScrubber();
    this.dedup = options.dedup || new SignalDeduplicator();
    this.vault = options.vault || new PiiVaultService();
    this.aikido = options.aikido || new AikidoDefenseService();
    this.promptBridge = options.promptBridge || new KeystoneBridgeService();
    this.targetsCatalog = targetsCatalog;
  }

  /**
   * Retrieves the OpenAPI-compliant PublicCapability manifest.
   * @returns {object} PublicCapability manifest
   */
  getCapabilityManifest() {
    return getCapabilityManifest();
  }

  /**
   * Validates a capability manifest object against required OpenAPI fields.
   * @param {object} manifest 
   * @returns {{ valid: boolean, missing: string[] }}
   */
  validateCapabilityManifest(manifest) {
    return validateCapabilityManifest(manifest);
  }

  /**
   * Runs the complete end-to-end intelligence extraction, sanitization, and Keystone prompt compilation pipeline.
   * @param {object} params
   * @param {string} [params.url] Target URL
   * @param {string} [params.html] Raw DOM markup if already fetched
   * @param {string} [params.targetId] Target identifier in targetsCatalog
   * @param {string} params.goal Keystone generation goal
   * @param {string} [params.profile='standard'] Compilation profile: 'standard' | 'chat' | 'reasoning'
   * @param {boolean} [params.redactPii=true] Enforce edge-level scrubbing and vault tokenization
   * @param {string} [params.subjectId='service_bridge_run'] Subject ID for PII vault tracking
   * @returns {Promise<object>} Result containing compiled plan.v1, deconstructed AST, tokens, and verification hashes
   */
  async harvestAndBridge(params = {}) {
    const {
      url,
      html,
      targetId,
      goal = 'build an AI workflow canvas',
      profile = 'standard',
      redactPii = true,
      subjectId = 'service_bridge_run'
    } = params;

    // 1. Resolve Target & Fetch Markup
    let rawHtml = html || '';
    let target = null;

    if (targetId) {
      target = this.targetsCatalog.find(t => t.id === targetId);
    }
    if (!target && url) {
      target = this.targetsCatalog.find(t => t.url === url || url.includes(t.url));
    }

    if (!rawHtml) {
      if (target) {
        const scrapeRes = await this.scraper.scrapeBenchmark(target.url);
        rawHtml = scrapeRes.html;
      } else if (url) {
        const scrapeRes = await this.scraper.scrapeBenchmark(url);
        rawHtml = scrapeRes.html;
      } else {
        throw new Error('INVALID_HARVEST_REQUEST: Neither url, html, nor valid targetId provided.');
      }
    }

    // 2. Edge PII Scrubbing
    let scrubbedHtml = rawHtml;
    const vaultTokens = [];

    if (redactPii) {
      // Find emails and tokenise them into the AES-256-GCM vault
      const emailMatches = rawHtml.match(/[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g) || [];
      for (const email of emailMatches) {
        const tok = this.vault.tokenize(email, subjectId, 'email');
        vaultTokens.push(tok);
        scrubbedHtml = scrubbedHtml.replace(new RegExp(email, 'g'), tok.token);
      }

      // Edge scrubbing for remaining patterns
      scrubbedHtml = this.edgePii.scrub(scrubbedHtml);
    }

    // 3. UX Deconstruction Engine
    const targetName = target ? target.appName : (params.targetName || 'Benchmark Application');
    const deconstructed = this.scraper.deconstructBenchmark(scrubbedHtml, target ? target.id : 'target_custom');

    // 4. SHA-256 Signal Deduplication Hash
    const contentHash = this.dedup.computeHash(
      url || target?.url || 'https://keystone.internal/benchmark',
      'architecture',
      deconstructed
    );

    // 5. Aikido Delimiter Containment & Threat Scan
    const threatScan = this.aikido.scanThreat(scrubbedHtml);
    const quarantined = this.aikido.quarantine(
      `Benchmark: ${deconstructed.appName}\nSummary: ${target?.summary || 'Extracted UX architecture'}\nTokenRef: ${vaultTokens[0]?.token || 'none'}`
    );

    // 6. Assemble PromptAnatomy Context
    const promptContext = this.promptBridge.buildIntelligencePromptContext({
      quarantinedContent: quarantined,
      vaultToken: vaultTokens[0]?.token || 'vault_tok_none',
      colorRoles: deconstructed.designTokens?.colorRoles || {},
      nodeCount: Object.keys(deconstructed.componentTree?.nodes || {}).length
    }, deconstructed.appName);

    // 7. Compile Authoritative Keystone plan.v1
    const compiledPlan = this.promptBridge.compilePlanWithBenchmark(goal, promptContext, profile);

    return {
      success: true,
      plan: compiledPlan,
      deconstructed,
      vaultTokens,
      contentHash,
      quarantinedContent: quarantined,
      threatLevel: threatScan.threatLevel,
      threatReasons: threatScan.reasons
    };
  }

  /**
   * Adapts Keystone API /v1/plan request into intelligence-augmented plan synthesis.
   * @param {object} planRequest Keystone API PlanRequest
   * @returns {Promise<object>} Compiled plan or standard plan.v1
   */
  async bridgePlanRequest(planRequest = {}) {
    const goal = planRequest.goal || 'build creative orchestration application';
    const options = planRequest.options || {};
    const profile = options.profile || 'standard';

    if (options.benchmarkUrl || options.targetId) {
      return this.harvestAndBridge({
        url: options.benchmarkUrl,
        targetId: options.targetId,
        goal,
        profile,
        redactPii: options.redactPii !== false
      });
    }

    // Standard compilation without benchmark injection
    const basePlan = generate(goal, planRequest.answers);
    const step = basePlan.path[0];
    step.promptText = compilePrompt(step.prompt, { profile });
    return {
      success: true,
      plan: basePlan,
      status: 'contract_fulfilled'
    };
  }

  /**
   * Sanitizes untrusted content with Aikido delimiter containment.
   * @param {string} content 
   * @returns {string} Quarantined content
   */
  sanitizePromptContext(content) {
    return this.aikido.quarantine(content);
  }

  /**
   * Tokenizes sensitive PII into the AES-256-GCM vault.
   * @param {string} plaintext 
   * @param {string} subjectId 
   * @param {string} entityType 
   * @returns {{ token: string, masked: string }}
   */
  tokenizePii(plaintext, subjectId, entityType = 'contact') {
    return this.vault.tokenize(plaintext, subjectId, entityType);
  }

  /**
   * Detokenizes a vault token with authenticated AES-256-GCM decryption.
   * @param {string} token 
   * @param {object} [authorityEnvelope] 
   * @returns {string} Plaintext
   */
  detokenizePii(token, authorityEnvelope) {
    return this.vault.detokenize(token, authorityEnvelope);
  }

  /**
   * Executes GDPR Article 17 cascading erasure for a data subject.
   * @param {string} subjectId 
   * @param {string} actorId 
   * @returns {object} Erasure receipt
   */
  purgeSubjectGdpr(subjectId, actorId) {
    return this.vault.purgeSubject(subjectId, actorId);
  }

  /**
   * Validates command against sysadmin safety rules.
   * @param {string} command 
   * @returns {{ safe: boolean, violations: string[] }}
   */
  validateCommandSafety(command) {
    const lower = (command || '').toLowerCase();
    const violations = [];

    if (lower.includes('rm -rf') || (lower.includes('remove-item') && lower.includes('-recurse') && lower.includes('-force'))) {
      violations.push('DESTRUCTIVE_COMMAND_PROHIBITED: Recursive force removal requires explicit user confirmation.');
    }
    if (lower.includes('drop table') || lower.includes('drop schema') || lower.includes('truncate table')) {
      violations.push('DATA_LOSS_RISK: Broad database drop or truncate is prohibited.');
    }
    if (lower.includes('pip install') && !lower.includes('.venv') && !lower.includes('python -m pip')) {
      violations.push('GLOBAL_PIP_PROHIBITED: Must use project virtual environment.');
    }

    return {
      safe: violations.length === 0,
      violations
    };
  }

  /**
   * Validates PowerShell execution flags for non-interactive execution.
   * @param {string} command 
   * @returns {{ compliant: boolean, hasNoProfile: boolean, hasNonInteractive: boolean }}
   */
  validateNonInteractiveFlags(command) {
    if (!command) return { compliant: true };
    if (command.startsWith('powershell') || command.startsWith('pwsh')) {
      const hasNoProfile = command.includes('-NoProfile');
      const hasNonInteractive = command.includes('-NonInteractive');
      return {
        compliant: hasNoProfile && hasNonInteractive,
        hasNoProfile,
        hasNonInteractive
      };
    }
    return { compliant: true };
  }
}

// Singleton Service Bridge instance
const serviceBridge = new ServiceBridge();

module.exports = {
  ServiceBridge,
  serviceBridge,
  getCapabilityManifest,
  validateCapabilityManifest,
  CAPABILITY_MANIFEST
};
