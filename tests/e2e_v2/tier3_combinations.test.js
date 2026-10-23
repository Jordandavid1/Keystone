'use strict';

/**
 * TIER 3: Cross-Feature Combinations (Pairwise Testing & State Transitions)
 * Verifies interaction points, data flows, and state transitions across subsystems (15 combinations).
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const { oracle } = require('./harness/loader');

// ----------------------------------------------------------------------------
// Pair 1: Prompt Compiler + Aikido Defense + PII Vault (F10 + F11 + F12)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 1: Untrusted prompt with PII is scrubbed, tokenized, and quarantined inside PromptAnatomy', () => {
  const vault = new oracle.PiiVaultOracle();
  const rawUserInput = 'Create character modeled after alice.v@keystone.ai <script>alert(1)</script>';

  // Step 1: PII Scrub & Tokenize
  const scrubbed = vault.scrubPlaintext(rawUserInput);
  assert.ok(scrubbed.includes('[REDACTED_EMAIL]'));
  assert.ok(!scrubbed.includes('alice.v@keystone.ai'));
  const token = vault.tokenize('alice.v@keystone.ai');

  // Step 2: Aikido Delimiter Quarantine
  const quarantined = oracle.AikidoDefenseOracle.quarantine(scrubbed);
  assert.ok(quarantined.startsWith('<untrusted_content>'));
  assert.ok(!quarantined.includes('<script>'));

  // Step 3: Prompt Compiler
  const intent = {
    objective: 'Generate stylized portrait',
    references: [token],
    constraints: [quarantined]
  };
  const compiled = oracle.PromptCompilerOracle.compile(intent, 'design');
  assert.ok(compiled.prompt_hash);
  assert.equal(compiled.anatomy.constraints[0], quarantined);
});

// ----------------------------------------------------------------------------
// Pair 2: Cognition Connector + ProposedAction Parser + Authority Engine (F13 + F14 + F15)
// ----------------------------------------------------------------------------
test('Tier 2 - Pair 2: Cognition completion parsed into ProposedAction and authorized by AuthorityEngine', () => {
  const rawModelResponse = JSON.stringify({
    action_type: 'GENERATE_VIDEO',
    capability: 'keystone.creative.wan_i2v',
    parameters: { frames: 49, motion: 'push_in' },
    rationale: 'Camera motion animation from source portrait',
    estimated_credits: 20
  });

  // Step 1: Parse structured output
  const action = oracle.ProposedActionOracle.parse(rawModelResponse);
  assert.equal(action.action_type, 'GENERATE_VIDEO');

  // Step 2: Evaluate with user balance of 50 credits
  const decision = oracle.AuthorityEngineOracle.evaluate(action, 50);
  assert.equal(decision.decision, 'APPROVE');
  assert.equal(decision.required_credits, 20);
  assert.ok(decision.decision_id.startsWith('dec_'));
});

// ----------------------------------------------------------------------------
// Pair 3: Authority Decision + Credits Ledger + Signed Execution Envelope (F15 + F25 + F18)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 3: Approved authority decision triggers credit hold and issues signed ExecutionEnvelope', () => {
  const action = {
    action_type: 'GENERATE_IMAGE',
    capability: 'keystone.creative.image_gen',
    parameters: { aspect_ratio: '16:9' },
    estimated_credits: 15
  };
  const decision = oracle.AuthorityEngineOracle.evaluate(action, 100);
  assert.equal(decision.decision, 'APPROVE');

  // Place credit hold
  const ledger = new oracle.CreditsLedgerOracle(100);
  const holdId = ledger.hold(decision.required_credits, 'job_combo_01');
  assert.equal(ledger.getAvailableBalance(), 85);

  // Issue Execution Envelope
  const envelope = oracle.ExecutionEnvelopeOracle.sign({
    job_id: 'job_combo_01',
    user_id: 'usr_combo_01',
    capability_id: action.capability,
    arguments: decision.sanitized_arguments
  });
  assert.equal(oracle.ExecutionEnvelopeOracle.verify(envelope), true);
  assert.equal(envelope.capability_id, 'keystone.creative.image_gen');
});

// ----------------------------------------------------------------------------
// Pair 4: Worker Bridge + Envelope Verification + Creative Adapter (F17 + F18 + F19)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 4: Worker verifies ExecutionEnvelope before dispatching to creative adapter', () => {
  const bridge = new oracle.WorkerBridgeOracle();
  const worker = bridge.registerWorker('worker_t4_wan', ['wan_i2v'], 'pk_hex', 'https://tunnel.keystone.io');

  const envelope = oracle.ExecutionEnvelopeOracle.sign({
    job_id: 'job_wan_01',
    user_id: 'usr_01',
    capability_id: 'wan_i2v',
    arguments: { source_image_asset_id: 'ast_portrait_101' }
  });

  // Worker verifies envelope
  assert.equal(oracle.ExecutionEnvelopeOracle.verify(envelope), true);

  // Dispatch to adapter
  const adapterRes = oracle.CreativeFabricOracle.validateAdapterRequest('wan_i2v', envelope.arguments);
  assert.equal(adapterRes.status, 'READY');
});

// ----------------------------------------------------------------------------
// Pair 5: Creative Generation + Lineage DAG + Short-Expiry URLs (F19 + F08 + F07)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 5: Generated creative asset records Lineage DAG relationship and signed storage URL', () => {
  const parentAssetId = 'ast_hero_source';
  const generatedVideoId = 'ast_hero_video_anim';
  const dag = new oracle.LineageDagOracle();

  // Record lineage
  const edge = dag.addRelationship(parentAssetId, generatedVideoId, 'animation', 'job_anim_99');
  assert.equal(edge.relationship_type, 'animation');
  assert.deepEqual(dag.getAncestors(generatedVideoId), [parentAssetId]);

  // Generate short-expiry download URL
  const storageKey = oracle.AssetStorageOracle.generateStorageKey('usr_creator', generatedVideoId, 'hero_video.mp4');
  const signedUrl = oracle.AssetStorageOracle.generateSignedUrl(storageKey, 900);
  assert.ok(signedUrl.includes(storageKey));
  assert.equal(oracle.AssetStorageOracle.validateSignedUrl(signedUrl).valid, true);
});

// ----------------------------------------------------------------------------
// Pair 6: Job State Machine + Credit Settlement + Job Repository (F09 + F25 + F05)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 6: Successful job completion settles credit hold and updates state to COMPLETED', () => {
  const repo = new oracle.RepositoryOracle();
  const user = repo.createUser('usr_p6', 'p6@k.ai', 'hpw');
  const proj = repo.createProject('proj_p6', user.id, 'Anim Project');

  const ledger = new oracle.CreditsLedgerOracle(100);
  const holdId = ledger.hold(20, 'job_p6');
  assert.equal(ledger.getAvailableBalance(), 80);

  // Transition state
  let state = 'CREATED';
  state = oracle.JobStateMachineOracle.transition(state, 'VALIDATING');
  state = oracle.JobStateMachineOracle.transition(state, 'PLANNING');
  state = oracle.JobStateMachineOracle.transition(state, 'AUTHORIZING');
  state = oracle.JobStateMachineOracle.transition(state, 'QUEUED');
  state = oracle.JobStateMachineOracle.transition(state, 'RUNNING');
  state = oracle.JobStateMachineOracle.transition(state, 'VALIDATING_OUTPUT');
  state = oracle.JobStateMachineOracle.transition(state, 'COMPLETED');
  assert.equal(state, 'COMPLETED');

  // Settle hold
  assert.equal(ledger.settle(holdId), true);
  assert.equal(ledger.getAvailableBalance(), 80);
});

// ----------------------------------------------------------------------------
// Pair 7: Quality Harness Evaluation + Quality Retry Loop (F02 + F09 + F10)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 7: Quality score below threshold triggers RETRY_PENDING and compiles revision v2', () => {
  const harnessRes = {
    harness_id: 'khf.quality.video',
    phase: 'post-execution',
    verdict: 'warn',
    score: 0.62,
    reason_codes: ['ARTIFACTS_DETECTED']
  };
  oracle.SchemaFreezeOracle.validateHarnessResult(harnessRes);

  let state = 'VALIDATING_OUTPUT';
  state = oracle.JobStateMachineOracle.transition(state, 'RETRY_PENDING');
  assert.equal(state, 'RETRY_PENDING');

  // Compile revision prompt
  const intentV2 = {
    objective: 'Animate portrait with reduced artifacts',
    constraints: ['high temporal coherence', 'motion smoothing']
  };
  const compiledV2 = oracle.PromptCompilerOracle.compile(intentV2, 'design');
  assert.ok(compiledV2.prompt_hash);
  assert.ok(compiledV2.anatomy.constraints.includes('high temporal coherence'));

  // Transition to queued for attempt 2
  state = oracle.JobStateMachineOracle.transition(state, 'QUEUED');
  assert.equal(state, 'QUEUED');
});

// ----------------------------------------------------------------------------
// Pair 8: Authority REPLAN + Job State Machine + Replan Action (F15 + F09 + F14)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 8: Parameter failure produces REPLAN and transitions job state machine back to PLANNING', () => {
  const invalidAction = {
    action_type: 'GENERATE_VIDEO',
    capability: 'keystone.creative.wan_i2v',
    parameters: { invalid_argument: true },
    estimated_credits: 10
  };
  const decision = oracle.AuthorityEngineOracle.evaluate(invalidAction, 100);
  assert.equal(decision.decision, 'REPLAN');

  let state = 'VALIDATING_OUTPUT';
  state = oracle.JobStateMachineOracle.transition(state, 'REPLAN_REQUIRED');
  state = oracle.JobStateMachineOracle.transition(state, 'PLANNING');
  assert.equal(state, 'PLANNING');
});

// ----------------------------------------------------------------------------
// Pair 9: Benchmark Extraction + Scraped Architecture + Keystone Prompt (F21 + F22 + F10)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 9: Scraped benchmark patterns feed into Keystone Design Playbook compilation', () => {
  const catalog = oracle.BenchmarkTargetOracle.getCatalog();
  const zencreator = catalog.find(c => c.id === 'zencreator');
  assert.ok(zencreator);

  const intent = {
    objective: 'Create multi-track node studio canvas',
    references: [`benchmark:${zencreator.id}`],
    metadata: { inspired_by: zencreator.domain }
  };
  const compiled = oracle.PromptCompilerOracle.compile(intent, 'design');
  assert.equal(compiled.provenance.playbook, 'design');
  assert.ok(compiled.anatomy.task.includes('node studio canvas'));
});

// ----------------------------------------------------------------------------
// Pair 10: Authentication + Tenant Scoping + Database Schema (F06 + F05 + F04)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 10: Authenticated user token strictly scopes repository queries preventing cross-tenant access', () => {
  const repo = new oracle.RepositoryOracle();
  const u1 = repo.createUser('usr_alice', 'alice@k.ai', 'hpw');
  const u2 = repo.createUser('usr_bob', 'bob@k.ai', 'hpw');

  repo.createProject('proj_alice_1', u1.id, 'Alice Secret Work');
  repo.createProject('proj_bob_1', u2.id, 'Bob Public Work');

  const tokenAlice = oracle.AuthOracle.generateToken(u1.id);
  const payloadAlice = oracle.AuthOracle.verifyToken(tokenAlice);

  // Alice queries projects
  const aliceProjects = repo.getProjectsForUser(payloadAlice.sub);
  assert.equal(aliceProjects.length, 1);
  assert.equal(aliceProjects[0].name, 'Alice Secret Work');

  // Cross tenant check
  assert.throws(() => {
    oracle.AuthOracle.enforceTenantIsolation(payloadAlice.sub, u2.id);
  }, /TENANT_ACCESS_DENIED/);
});

// ----------------------------------------------------------------------------
// Pair 11: Kaggle Memory Harness + Production Notebooks + Worker Bridge (F16 + F20 + F17)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 11: Hardware probe verifies offload parameters before gateway worker registration', () => {
  const offload = oracle.KaggleMemoryHarnessOracle.calculateOffload();
  assert.equal(offload.fits_in_memory, true);

  const nbs = oracle.KaggleSetupOracle.getRequiredNotebooks();
  assert.ok(nbs.includes('03_keystone_integrated_gateway.ipynb'));

  const bridge = new oracle.WorkerBridgeOracle();
  const w = bridge.registerWorker('worker_gateway_kaggle', ['qwen_cognition', 'comfyui'], 'pk_123', 'https://kaggle-tunnel.io');
  assert.equal(w.status, 'ONLINE');
});

// ----------------------------------------------------------------------------
// Pair 12: Stripe Webhook + Credit Ledger Idempotency (F26 + F25)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 12: Stripe webhook event adds credits to ledger, duplicate event adds nothing', () => {
  const billing = new oracle.StripeBillingOracle();
  const ledger = new oracle.CreditsLedgerOracle(50);

  const event = {
    id: 'evt_stripe_deposit_01',
    type: 'checkout.session.completed',
    data: { object: { metadata: { user_id: 'usr_stripe_1', credits: 100 } } }
  };
  const str = JSON.stringify(event);
  const sig = crypto.createHmac('sha256', oracle.StripeBillingOracle.WEBHOOK_SECRET).update(str).digest('hex');

  // First webhook processing
  const res1 = billing.processWebhook(event, sig);
  assert.equal(res1.status, 'PROCESSED');
  ledger.refund(res1.credits_added, 'Stripe top-up');
  assert.equal(ledger.getAvailableBalance(), 150);

  // Duplicate webhook delivery
  const res2 = billing.processWebhook(event, sig);
  assert.equal(res2.status, 'ALREADY_PROCESSED');
  assert.equal(res2.duplicate, true);
  // Ledger balance unchanged!
  assert.equal(ledger.getAvailableBalance(), 150);
});

// ----------------------------------------------------------------------------
// Pair 13: Admin Console + Worker Bridge + Memory Telemetry (F24 + F17 + F16)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 13: Admin console aggregates telemetry across online workers and hardware probes', () => {
  const bridge = new oracle.WorkerBridgeOracle();
  bridge.registerWorker('w_t4_1', ['wan'], 'pk1', 'https://t1.io');
  bridge.registerWorker('w_t4_2', ['qwen'], 'pk2', 'https://t2.io');

  const online = bridge.getOnlineWorkers();
  assert.equal(online.length, 2);

  const telemetry = oracle.AdminConsoleOracle.getTelemetryMetrics();
  assert.equal(telemetry.active_workers, 2);
  assert.ok(telemetry.gpu_vram_utilization_pct > 0);
  assert.ok(telemetry.host_ram_used_bytes > 0);
});

// ----------------------------------------------------------------------------
// Pair 14: Proprietary Scanner + Bible Checksum + Contract Freeze (F27 + F01 + F02)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 14: Proprietary scanner and Bible checksum verify integrity of frozen contracts', () => {
  const bibleCheck = oracle.InvariantOracle.verifyBibleChecksum();
  assert.equal(bibleCheck.matches, true);

  const cleanContracts = JSON.stringify({
    plan: 'plan.v1',
    promptAnatomy: ['role', 'task', 'context', 'constraints', 'outputFormat', 'reasoning']
  });
  const scan = oracle.ProprietaryPolicyOracle.scanContentForSecrets(cleanContracts);
  assert.equal(scan.hasSecrets, false);
});

// ----------------------------------------------------------------------------
// Pair 15: Chaos Worker Crash + Job State Machine + Credit Recovery (F34 + F09 + F25)
// ----------------------------------------------------------------------------
test('Tier 3 - Pair 15: Worker process crash mid-run recovers job to RETRY_PENDING and prevents credit leakage', () => {
  const ledger = new oracle.CreditsLedgerOracle(100);
  const holdId = ledger.hold(25, 'job_chaos_1');
  assert.equal(ledger.getAvailableBalance(), 75);

  const job = { id: 'job_chaos_1', state: 'RUNNING', retry_count: 0 };
  const crashRecovery = oracle.AdversarialHardeningOracle.simulateWorkerCrash(job, ledger);

  assert.equal(crashRecovery.job_state, 'RETRY_PENDING');
  assert.equal(crashRecovery.retry_count, 1);
  assert.equal(ledger.getAvailableBalance(), 75); // Hold intact

  // When job is retried and succeeds:
  job.state = oracle.JobStateMachineOracle.transition(job.state, 'QUEUED');
  job.state = oracle.JobStateMachineOracle.transition(job.state, 'RUNNING');
  job.state = oracle.JobStateMachineOracle.transition(job.state, 'VALIDATING_OUTPUT');
  job.state = oracle.JobStateMachineOracle.transition(job.state, 'COMPLETED');

  ledger.settle(holdId);
  assert.equal(ledger.getAvailableBalance(), 75); // Exactly 25 settled, no double debit!
});
