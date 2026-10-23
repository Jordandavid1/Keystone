/**
 * KEYSTONE Canonical Contracts & Schemas (TypeScript)
 * Authoritative types mirroring Python Pydantic v2 schemas per KEYSTONE Bible §6–§16.
 */

export type JobState =
  | 'created'
  | 'validating'
  | 'planning'
  | 'authorizing'
  | 'queued'
  | 'running'
  | 'validating_output'
  | 'retry_pending'
  | 'replan_required'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'rejected';

export type AuthorityDecisionType = 'approve' | 'deny' | 'replan';
export type HarnessVerdict = 'pass' | 'warn' | 'fail';
export type HarnessPhase = 'input' | 'proposal' | 'pre-execution' | 'post-execution' | 'benchmark';

export interface PromptAnatomy {
  role: string;
  task: string;
  context: string[];
  constraints: string[];
  outputFormat: string;
  reasoning: string;
}

export interface PromptIntent {
  objective: string;
  subject?: string | null;
  environment?: string | null;
  visual_style?: string | null;
  composition?: string | null;
  camera?: string | null;
  lighting?: string | null;
  mood?: string | null;
  motion?: string | null;
  constraints: string[];
  references: string[];
  metadata: Record<string, unknown>;
}

export interface ParameterSpec {
  type: string;
  required?: boolean;
  default?: unknown;
  minimum?: number | null;
  maximum?: number | null;
  enum?: unknown[] | null;
  description?: string | null;
}

export interface CapabilityManifest {
  schema_version: string;
  capability_id: string;
  provider_id: string;
  provider_version: string;
  capability_type: string;
  description: string;
  accepts: string[];
  produces: string[];
  parameters: Record<string, ParameterSpec>;
  prompt_profile?: string | null;
  workflow_id?: string | null;
  required_harnesses: string[];
  estimated_resource_class?: string | null;
  enabled: boolean;
  metadata: Record<string, unknown>;
}

export interface HarnessResult {
  harness_id: string;
  harness_version: string;
  phase: HarnessPhase;
  verdict: HarnessVerdict;
  score?: number | null;
  reason_codes: string[];
  evidence: Record<string, unknown>;
  runtime_ms?: number | null;
}

export interface QualityDimensions {
  prompt_adherence?: number | null;
  technical_quality?: number | null;
  composition?: number | null;
  visual_consistency?: number | null;
  identity_consistency?: number | null;
  temporal_consistency?: number | null;
  artifact_score?: number | null;
  user_satisfaction?: number | null;
}

export interface QualityScore {
  evaluator: string;
  evaluator_version: string;
  dimensions: QualityDimensions;
  overall: number;
  confidence: number;
  evidence: Record<string, unknown>;
}

export interface RetryPolicy {
  max_attempts: number;
  max_total_runtime_seconds: number;
  max_estimated_cost: number;
}

export interface GenerationAttempt {
  attempt_id: string;
  job_id: string;
  provider_id: string;
  capability_id: string;
  prompt_hash: string;
  workflow_version: string;
  started_at: string;
  completed_at?: string | null;
  success: boolean;
  output_asset_ids: string[];
  metrics: Record<string, number>;
  failure_code?: string | null;
}

export interface PromptCompilationRequest {
  request_id: string;
  target_capability: string;
  target_provider: string;
  intent: PromptIntent;
  user_context: Record<string, unknown>;
  workflow_context: Record<string, unknown>;
  capability: CapabilityManifest;
  harness_feedback: HarnessResult[];
  previous_attempts: GenerationAttempt[];
}

export interface CompiledPrompt {
  compiler_version: string;
  target_capability: string;
  target_provider: string;
  positive_prompt: string;
  negative_prompt?: string | null;
  parameters: Record<string, unknown>;
  provenance: Record<string, unknown>;
  prompt_hash: string;
}

export interface ProposedAction {
  action_type: string;
  capability: string;
  parameters: Record<string, unknown>;
  rationale: string;
  estimated_credits: number;
}

export interface CognitiveResult {
  reasoning_id: string;
  intent: PromptIntent;
  proposed_actions: ProposedAction[];
  confidence: number;
  observations: Record<string, unknown>;
}

export interface AuthorityDecision {
  decision_id: string;
  request_id: string;
  decision: AuthorityDecisionType;
  capability_id?: string | null;
  provider_id?: string | null;
  sanitized_arguments: Record<string, unknown>;
  reason_codes: string[];
  policy_bundle_version: string;
  capability_registry_version: string;
  harness_bundle_version: string;
}

export interface ExecutionEnvelope {
  envelope_id: string;
  decision_id: string;
  job_id: string;
  user_id: string;
  capability_id: string;
  provider_id: string;
  workflow_id: string;
  workflow_version: string;
  compiled_prompt_id: string;
  arguments: Record<string, unknown>;
  input_asset_ids: string[];
  issued_at: string;
  expires_at: string;
  nonce: string;
  signature: string;
}

export interface UserFeedback {
  job_id: string;
  user_id: string;
  rating?: number | null;
  accepted?: boolean | null;
  regeneration_requested: boolean;
  selected_asset_id?: string | null;
  feedback_tags: string[];
  comment?: string | null;
}

export interface PromptRevisionRequest {
  original_intent: PromptIntent;
  previous_prompt: CompiledPrompt;
  quality_scores: QualityScore[];
  failure_codes: string[];
  immutable_constraints: string[];
  attempt_number: number;
}

export interface PromptRevisionProposal {
  preserve: string[];
  change: string[];
  parameter_suggestions: Record<string, unknown>;
  reasoning_summary: string;
  confidence: number;
}
