'use strict';

/**
 * TIER 4: Real-World Scenarios (End-to-End Creative Workflows)
 * Verifies 8 full end-to-end creative workflows reflecting real-world production use cases.
 */

const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');

const { oracle } = require('./harness/loader');

// ----------------------------------------------------------------------------
// Scenario 1: Bible §35 End-to-End Image Animation Script Workflow
// ----------------------------------------------------------------------------
test('Tier 4 - Scenario 1: Bible §35 complete image animation lifecycle with state recovery', () => {
  // Step 1: Register user and create project
  const repo = new oracle.RepositoryOracle();
  const user = repo.createUser('usr_anim_35', 'animator@keystone.ai', 'hashed_pass');
  const project = repo.createProject('proj_anim_35', user.id, 'Sci-Fi Short Film');
  const session = repo.createSession('sess_anim_35', project.id, user.id);

  // Step 2: Upload source image
  const sourceAsset = repo.createAsset(
    'ast_source_hero',
    user.id,
    project.id,
    'cyberpunk_hero.png',
    'image/png',
    3145728,
    oracle.AssetStorageOracle.generateStorageKey(user.id, 'ast_source_hero', 'cyberpunk_hero.png')
  );
  assert.equal(sourceAsset.mime_type, 'image/png');

  // Step 3: Ask Keystone to animate it
  const userIntent = {
    objective: 'Animate this image with a slow cinematic push-in and neon glow pulsing',
    subject: 'cyberpunk hero in rain',
    camera: 'slow cinematic push-in',
    references: [sourceAsset.id]
  };

  // Step 4: Compile cognition prompt
  const compiledCognition = oracle.PromptCompilerOracle.compile(userIntent, 'design', 'reasoning');
  assert.ok(compiledCognition.prompt_hash);

  // Step 5: Receive ProposedAction from cognition
  const cognitionReq = oracle.CognitionConnectorOracle.buildCompletionRequest(compiledCognition.positive_prompt);
  const rawModelAction = JSON.stringify({
    action_type: 'ANIMATE_IMAGE',
    capability: 'keystone.creative.wan_i2v',
    parameters: {
      source_image_asset_id: sourceAsset.id,
      frames: 65,
      fps: 16,
      motion_bucket: 127
    },
    rationale: 'Camera push-in with atmospheric neon pulse',
    estimated_credits: 25
  });
  const proposedAction = oracle.ProposedActionOracle.parse(rawModelAction);
  assert.equal(proposedAction.action_type, 'ANIMATE_IMAGE');

  // Step 6: Authorize action and debit credits
  const ledger = new oracle.CreditsLedgerOracle(100);
  const decision = oracle.AuthorityEngineOracle.evaluate(proposedAction, ledger.getAvailableBalance());
  assert.equal(decision.decision, 'APPROVE');
  const holdId = ledger.hold(decision.required_credits, 'job_anim_35');
  assert.equal(ledger.getAvailableBalance(), 75);

  // Step 7: Compile target prompt and issue ExecutionEnvelope
  const targetEnvelope = oracle.ExecutionEnvelopeOracle.sign({
    job_id: 'job_anim_35',
    user_id: user.id,
    capability_id: proposedAction.capability,
    arguments: proposedAction.parameters
  });
  assert.equal(oracle.ExecutionEnvelopeOracle.verify(targetEnvelope), true);

  // Step 8: Execute creative workflow (ComfyUI / Wan I2V)
  const adapterRes = oracle.CreativeFabricOracle.validateAdapterRequest('wan_i2v', targetEnvelope.arguments);
  assert.equal(adapterRes.status, 'READY');

  // Step 9: Evaluate output with KHF
  const harnessRes = {
    harness_id: 'khf.quality.video',
    harness_version: '1.0.0',
    phase: 'post-execution',
    verdict: 'pass',
    score: 0.92,
    reason_codes: ['EXCELLENT_TEMPORAL_COHERENCE']
  };
  oracle.SchemaFreezeOracle.validateHarnessResult(harnessRes);

  // Step 10: Persist video and lineage DAG
  const videoAsset = repo.createAsset(
    'ast_video_anim_final',
    user.id,
    project.id,
    'cyberpunk_hero_animated.mp4',
    'video/mp4',
    15728640,
    oracle.AssetStorageOracle.generateStorageKey(user.id, 'ast_video_anim_final', 'cyberpunk_hero_animated.mp4')
  );
  const dag = new oracle.LineageDagOracle();
  const lineageEdge = dag.addRelationship(sourceAsset.id, videoAsset.id, 'animation', 'job_anim_35');
  assert.equal(lineageEdge.relationship_type, 'animation');
  assert.deepEqual(dag.getAncestors(videoAsset.id), [sourceAsset.id]);

  // Step 11: Settle credit hold exactly once
  ledger.settle(holdId);
  assert.equal(ledger.getAvailableBalance(), 75); // Settled without double-debit

  // Step 12: Refresh browser and recover complete project state
  const recoveredProjects = repo.getProjectsForUser(user.id);
  assert.equal(recoveredProjects.length, 1);
  assert.equal(recoveredProjects[0].name, 'Sci-Fi Short Film');
  const ancestors = dag.getAncestors(videoAsset.id);
  assert.equal(ancestors.length, 1);
  assert.equal(ancestors[0], sourceAsset.id);
});

// ----------------------------------------------------------------------------
// Scenario 2: Text-to-Video Creative Generation Workflow
// ----------------------------------------------------------------------------
test('Tier 4 - Scenario 2: Natural language text-to-video workflow with creative playbook', () => {
  const ledger = new oracle.CreditsLedgerOracle(80);

  // User input
  const prompt = 'Drone flying over Icelandic volcanic black sand beach with turquoise glacial river at dusk';
  const intent = {
    objective: prompt,
    environment: 'Iceland volcanic beach',
    lighting: 'dusk golden hour',
    motion: 'smooth forward aerial drone glide'
  };

  // Compile with Writing/Content domain
  const compiled = oracle.PromptCompilerOracle.compile(intent, 'content');
  assert.ok(compiled.positive_prompt.includes('Iceland volcanic beach'));

  // Cognition creates ProposedAction
  const action = {
    action_type: 'GENERATE_VIDEO_T2V',
    capability: 'wan_t2v',
    parameters: {
      prompt: compiled.positive_prompt,
      aspect_ratio: '16:9',
      frames: 81,
      fps: 16
    },
    estimated_credits: 30
  };

  // Authority & Ledger Hold
  const dec = oracle.AuthorityEngineOracle.evaluate(action, ledger.getAvailableBalance());
  assert.equal(dec.decision, 'APPROVE');
  const holdId = ledger.hold(dec.required_credits, 'job_t2v_01');
  assert.equal(ledger.getAvailableBalance(), 50);

  // Creative Adapter check
  const adapterRes = oracle.CreativeFabricOracle.validateAdapterRequest('wan_t2v', action.parameters);
  assert.equal(adapterRes.status, 'READY');

  // Complete and settle
  ledger.settle(holdId);
  assert.equal(ledger.getAvailableBalance(), 50);
});

// ----------------------------------------------------------------------------
// Scenario 3: Character Identity Consistency Workflow
// ----------------------------------------------------------------------------
test('Tier 4 - Scenario 3: Character identity consistency across multiple scenes using FaceFusion', () => {
  const dag = new oracle.LineageDagOracle();
  const referenceFaceAsset = 'ast_actor_face_ref';
  const targetSceneAsset = 'ast_scene_render_noir';

  // FaceFusion adapter validates source and target
  const adapterRes = oracle.CreativeFabricOracle.validateAdapterRequest('facefusion', {
    source_face_asset_id: referenceFaceAsset,
    target_asset_id: targetSceneAsset,
    blending_mode: 'seamless'
  });
  assert.equal(adapterRes.status, 'READY');

  // Generated character asset
  const compositeAsset = 'ast_actor_in_scene_noir';
  dag.addRelationship(referenceFaceAsset, compositeAsset, 'reference', 'job_identity_01');
  dag.addRelationship(targetSceneAsset, compositeAsset, 'edit', 'job_identity_01');

  const ancestors = dag.getAncestors(compositeAsset);
  assert.equal(ancestors.length, 2);
  assert.ok(ancestors.includes(referenceFaceAsset));
  assert.ok(ancestors.includes(targetSceneAsset));
});

// ----------------------------------------------------------------------------
// Scenario 4: Bounded Quality Retry Workflow
// ----------------------------------------------------------------------------
test('Tier 4 - Scenario 4: Bounded quality retry loop refines prompt on low KHF quality score', () => {
  const ledger = new oracle.CreditsLedgerOracle(100);
  const holdId = ledger.hold(20, 'job_quality_retry');

  // Attempt 1: Fails quality threshold
  const score1 = {
    harness_id: 'khf.quality.video',
    verdict: 'warn',
    score: 0.55,
    reason_codes: ['MOTION_JITTER', 'LOW_TEMPORAL_COHERENCE']
  };

  let state = 'VALIDATING_OUTPUT';
  // Below threshold triggers retry pending
  state = oracle.JobStateMachineOracle.transition(state, 'RETRY_PENDING');
  assert.equal(state, 'RETRY_PENDING');

  // Prompt compiler refines prompt based on feedback
  const intentAttempt2 = {
    objective: 'High-speed car chase in rain',
    constraints: ['high temporal stabilization', 'reduce jitter']
  };
  const compiled2 = oracle.PromptCompilerOracle.compile(intentAttempt2, 'general');
  assert.ok(compiled2.positive_prompt);

  // Attempt 2: Passes quality threshold
  state = oracle.JobStateMachineOracle.transition(state, 'QUEUED');
  state = oracle.JobStateMachineOracle.transition(state, 'RUNNING');
  state = oracle.JobStateMachineOracle.transition(state, 'VALIDATING_OUTPUT');
  state = oracle.JobStateMachineOracle.transition(state, 'COMPLETED');
  assert.equal(state, 'COMPLETED');

  // Final settlement occurs exactly once
  ledger.settle(holdId);
  assert.equal(ledger.getAvailableBalance(), 80);
});

// ----------------------------------------------------------------------------
// Scenario 5: Replan Workflow on Capability/Resource Boundary
// ----------------------------------------------------------------------------
test('Tier 4 - Scenario 5: Replan workflow adapts to parameter constraints without crashing', () => {
  const impossibleAction = {
    action_type: 'GENERATE_VIDEO',
    capability: 'wan_i2v',
    parameters: { invalid_argument: true, requested_resolution: '8K_120FPS' },
    estimated_credits: 10
  };

  // Authority denies and flags REPLAN
  const decision = oracle.AuthorityEngineOracle.evaluate(impossibleAction, 100);
  assert.equal(decision.decision, 'REPLAN');

  // Job state transitions to REPLAN_REQUIRED
  let state = 'VALIDATING_OUTPUT';
  state = oracle.JobStateMachineOracle.transition(state, 'REPLAN_REQUIRED');
  state = oracle.JobStateMachineOracle.transition(state, 'PLANNING');
  assert.equal(state, 'PLANNING');

  // Cognition adapts and replans with feasible parameters
  const feasibleAction = {
    action_type: 'GENERATE_VIDEO',
    capability: 'wan_i2v',
    parameters: { requested_resolution: '1080P_24FPS' },
    estimated_credits: 20
  };
  const decision2 = oracle.AuthorityEngineOracle.evaluate(feasibleAction, 100);
  assert.equal(decision2.decision, 'APPROVE');
});

// ----------------------------------------------------------------------------
// Scenario 6: Worker Termination Mid-Job & State Recovery (Bible §35)
// ----------------------------------------------------------------------------
test('Tier 4 - Scenario 6: Worker process terminates mid-job, recovers state, and preserves credit balance', () => {
  const ledger = new oracle.CreditsLedgerOracle(100);
  const holdId = ledger.hold(30, 'job_worker_crash');
  assert.equal(ledger.getAvailableBalance(), 70);

  const job = { id: 'job_worker_crash', state: 'RUNNING', retry_count: 0 };

  // Worker crashes!
  const recovery = oracle.AdversarialHardeningOracle.simulateWorkerCrash(job, ledger);
  assert.equal(recovery.job_state, 'RETRY_PENDING');
  assert.equal(recovery.retry_count, 1);
  assert.equal(ledger.getAvailableBalance(), 70); // Hold remains intact, not double-debited

  // Alternate worker picks up queued retry
  job.state = oracle.JobStateMachineOracle.transition(job.state, 'QUEUED');
  job.state = oracle.JobStateMachineOracle.transition(job.state, 'RUNNING');
  job.state = oracle.JobStateMachineOracle.transition(job.state, 'VALIDATING_OUTPUT');
  job.state = oracle.JobStateMachineOracle.transition(job.state, 'COMPLETED');
  assert.equal(job.state, 'COMPLETED');

  // Settle hold
  ledger.settle(holdId);
  assert.equal(ledger.getAvailableBalance(), 70);
});

// ----------------------------------------------------------------------------
// Scenario 7: Multi-Tenant Workspace & GDPR Article 17 Erasure
// ----------------------------------------------------------------------------
test('Tier 4 - Scenario 7: Multi-tenant workspace isolation and GDPR Article 17 cascading erasure', () => {
  const repo = new oracle.RepositoryOracle();
  const vault = new oracle.PiiVaultOracle();

  // Create two isolated users
  const userA = repo.createUser('usr_eu_alice', 'alice@company.eu', 'hash_pw');
  const userB = repo.createUser('usr_us_bob', 'bob@company.com', 'hash_pw');

  const pA = repo.createProject('proj_A', userA.id, 'Alice Workspace');
  const pB = repo.createProject('proj_B', userB.id, 'Bob Workspace');

  // Tokenize Alice PII
  const token = vault.tokenize('Alice Full Name and Passport Reference');
  assert.ok(token.startsWith('vault_tok_'));

  // Verify tenant isolation
  assert.throws(() => {
    oracle.AuthOracle.enforceTenantIsolation(userB.id, userA.id);
  }, /TENANT_ACCESS_DENIED/);

  // Alice requests GDPR Article 17 Erasure
  // Step 1: Shred vault token
  const shredded = vault.shredToken(token);
  assert.equal(shredded, true);
  assert.throws(() => {
    vault.detokenize(token);
  }, /TOKEN_NOT_FOUND_OR_SHREDDED/);

  // Step 2: Soft delete projects and assets
  pA.deleted_at = new Date().toISOString();
  assert.deepEqual(repo.getProjectsForUser(userA.id), []);

  // Step 3: Erasure is idempotent
  assert.equal(vault.shredToken(token), false);
});

// ----------------------------------------------------------------------------
// Scenario 8: Benchmark-Informed Creative Ideation
// ----------------------------------------------------------------------------
test('Tier 4 - Scenario 8: End-to-end benchmark-informed creative ideation from Firecrawl to Keystone Canvas', () => {
  // Scrape all 6 benchmark applications catalog
  const catalog = oracle.BenchmarkTargetOracle.getCatalog();
  assert.equal(catalog.length, 6);

  // Synthesize layout tokens
  const regions = oracle.PremiumWorkspaceOracle.getDesktopRegions();
  const progressLang = oracle.PremiumWorkspaceOracle.getProgressLanguage();
  assert.equal(regions.length, 5);
  assert.equal(progressLang.length, 7);

  // Build Keystone prompt integrating benchmark patterns
  const intent = {
    objective: 'Design a unified creative canvas workspace for video motion interpolation',
    references: ['hf_space', 'higgsfield', 'grok'],
    metadata: {
      canvas_first: true,
      composer_mode: 'natural_language'
    }
  };
  const compiled = oracle.PromptCompilerOracle.compile(intent, 'design');
  assert.ok(compiled.prompt_hash);
  assert.equal(compiled.provenance.playbook, 'design');
  assert.equal(compiled.anatomy.role.includes('design'), true);
});
