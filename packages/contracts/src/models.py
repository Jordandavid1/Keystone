"""
KEYSTONE Canonical Contracts & Schemas (Pydantic v2)
Authoritative specification for inter-subsystem data structures per KEYSTONE Bible §6–§16.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field, ConfigDict


# ============================================================================
# 1. Base Model Configuration
# ============================================================================

class KeystoneContractModel(BaseModel):
    """Base model enforcing strict Pydantic v2 configuration across Keystone contracts."""
    model_config = ConfigDict(
        populate_by_name=True,
        validate_assignment=True,
        extra="ignore",
        json_schema_serialization_defaults_required=True
    )


# ============================================================================
# 2. Prompt Engine Compatibility & Intermediate Representation (Bible §6, §7)
# ============================================================================

class PromptAnatomy(KeystoneContractModel):
    """
    Six-part prompt anatomy preserved from KEYSTONE baseline (Bible §2 Invariant 13, §6).
    """
    role: str = Field(..., description="Assigned cognitive role and persona")
    task: str = Field(..., description="Specific objective or generation task")
    context: List[str] = Field(default_factory=list, description="Background, assets, and project context")
    constraints: List[str] = Field(default_factory=list, description="Hard negative and operational boundaries")
    outputFormat: str = Field(..., description="Target output schema or syntax format")
    reasoning: str = Field(..., description="Reasoning directives and trade-off considerations")


class PromptIntent(KeystoneContractModel):
    """
    Provider-neutral creative and analytical intent representation (Bible §7).
    """
    objective: str = Field(..., min_length=1, description="Primary natural language creative objective")
    subject: Optional[str] = Field(None, description="Main visual subject or entity")
    environment: Optional[str] = Field(None, description="Setting, backdrop, or spatial context")
    visual_style: Optional[str] = Field(None, description="Aesthetic, rendering, or artistic style")
    composition: Optional[str] = Field(None, description="Framing, layout, and subject placement")
    camera: Optional[str] = Field(None, description="Lens, focal length, angle, and shot distance")
    lighting: Optional[str] = Field(None, description="Lighting setup, color temperature, and mood")
    mood: Optional[str] = Field(None, description="Emotional tone and atmospheric feel")
    motion: Optional[str] = Field(None, description="Camera or subject motion dynamics for video/animation")
    constraints: List[str] = Field(default_factory=list, description="Negative prompts and unwanted elements")
    references: List[str] = Field(default_factory=list, description="Asset IDs or reference image URIs")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Extensible contextual metadata")


# ============================================================================
# 3. Capability Manifests & Parameter Specs (Bible §8)
# ============================================================================

class ParameterSpec(KeystoneContractModel):
    """
    Detailed specification for a capability parameter (Bible §8).
    """
    type: str = Field(..., description="Parameter data type (string, number, integer, boolean, array, object)")
    required: bool = Field(False, description="Whether this parameter is mandatory")
    default: Optional[Any] = Field(None, description="Default parameter value if omitted")
    minimum: Optional[float] = Field(None, description="Inclusive minimum value for numeric parameters")
    maximum: Optional[float] = Field(None, description="Inclusive maximum value for numeric parameters")
    enum: Optional[List[Any]] = Field(None, description="Permitted enumeration values")
    description: Optional[str] = Field(None, description="Customer-facing or cognitive documentation")


class CapabilityManifest(KeystoneContractModel):
    """
    Provider capability declaration manifest (Bible §8).
    """
    schema_version: str = Field("1.0", description="Manifest schema version")
    capability_id: str = Field(..., description="Globally unique capability identifier e.g. creative.image_generation")
    provider_id: str = Field(..., description="Provider adapter identifier e.g. comfy.flux_schnell")
    provider_version: str = Field(..., description="Semantic version of the underlying provider adapter")
    capability_type: str = Field(..., description="Category: cognition, generation, transformation, analysis")
    description: str = Field(..., description="Human and machine-readable description of capability")
    accepts: List[str] = Field(..., description="List of accepted input modalities or MIME types")
    produces: List[str] = Field(..., description="List of produced output modalities or MIME types")
    parameters: Dict[str, ParameterSpec] = Field(default_factory=dict, description="Parameter schema dictionary")
    prompt_profile: Optional[str] = Field(None, description="Associated prompt profile identifier")
    workflow_id: Optional[str] = Field(None, description="Internal workflow graph template identifier")
    required_harnesses: List[str] = Field(default_factory=list, description="Harness IDs executed for this capability")
    estimated_resource_class: Optional[str] = Field(None, description="Resource class: gpu_t4, cpu_standard, etc.")
    enabled: bool = Field(True, description="Whether this capability is currently operational")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Provider-specific configuration metadata")


# ============================================================================
# 4. Harness & Measurement Contracts (Bible §13, §14)
# ============================================================================

class HarnessResult(KeystoneContractModel):
    """
    KHF evaluation and validation verdict (Bible §13).
    """
    harness_id: str = Field(..., description="Unique harness identifier e.g. khf.technical_output")
    harness_version: str = Field(..., description="Semantic version of the executing harness")
    phase: Literal["input", "proposal", "pre-execution", "post-execution", "benchmark"] = Field(
        ..., description="Execution phase during which the harness evaluated"
    )
    verdict: Literal["pass", "warn", "fail"] = Field(..., description="Evaluation outcome verdict")
    score: Optional[float] = Field(None, ge=0.0, le=1.0, description="Normalized quantitative score")
    reason_codes: List[str] = Field(default_factory=list, description="Standardized failure or warning codes")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic evidence and measurement data")
    runtime_ms: Optional[float] = Field(None, ge=0.0, description="Harness evaluation duration in milliseconds")


class QualityDimensions(KeystoneContractModel):
    """Multidimensional visual and technical evaluation scores (Bible §14)."""
    prompt_adherence: Optional[float] = Field(None, ge=0.0, le=1.0)
    technical_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    composition: Optional[float] = Field(None, ge=0.0, le=1.0)
    visual_consistency: Optional[float] = Field(None, ge=0.0, le=1.0)
    identity_consistency: Optional[float] = Field(None, ge=0.0, le=1.0)
    temporal_consistency: Optional[float] = Field(None, ge=0.0, le=1.0)
    artifact_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    user_satisfaction: Optional[float] = Field(None, ge=0.0, le=1.0)


class QualityScore(KeystoneContractModel):
    """Aggregated quality evaluation result (Bible §14)."""
    evaluator: str = Field(..., description="Evaluator name e.g. qwen_semantic_critic or technical_validator")
    evaluator_version: str = Field(..., description="Semantic version of the evaluator")
    dimensions: QualityDimensions = Field(..., description="Fine-grained quality dimension scores")
    overall: float = Field(..., ge=0.0, le=1.0, description="Overall weighted quality score")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evaluator confidence score")
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Supporting telemetry and visual critique")


class RetryPolicy(KeystoneContractModel):
    """Bounded retry policy to prevent runaway execution (Bible §14)."""
    max_attempts: int = Field(default=3, ge=1, le=10, description="Maximum execution attempts")
    max_total_runtime_seconds: int = Field(default=300, ge=1, description="Maximum cumulative job runtime")
    max_estimated_cost: float = Field(default=10.0, ge=0.0, description="Maximum total credit/monetary budget")


# ============================================================================
# 5. Core Operational Data Models (Bible §16)
# ============================================================================

class GenerationAttempt(KeystoneContractModel):
    """Historical record of an individual workflow generation attempt (Bible §16)."""
    attempt_id: str = Field(..., description="Unique attempt UUID")
    job_id: str = Field(..., description="Associated parent Job UUID")
    provider_id: str = Field(..., description="Provider adapter utilized")
    capability_id: str = Field(..., description="Target capability ID")
    prompt_hash: str = Field(..., description="SHA-256 hash of the compiled prompt")
    workflow_version: str = Field(..., description="ComfyUI or model workflow graph version")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(None)
    success: bool = Field(False)
    output_asset_ids: List[str] = Field(default_factory=list)
    metrics: Dict[str, float] = Field(default_factory=dict)
    failure_code: Optional[str] = Field(None)


# ============================================================================
# 6. Prompt Compiler Interfaces (Bible §9)
# ============================================================================

class PromptCompilationRequest(KeystoneContractModel):
    """Request envelope passed to domain PromptCompilers (Bible §9)."""
    request_id: str = Field(..., description="Unique compilation request identifier")
    target_capability: str = Field(..., description="Capability ID for which the prompt is compiled")
    target_provider: str = Field(..., description="Provider ID handling target execution")
    intent: PromptIntent = Field(..., description="Provider-neutral intent representation")
    user_context: Dict[str, Any] = Field(default_factory=dict, description="User preferences, style guidelines")
    workflow_context: Dict[str, Any] = Field(default_factory=dict, description="Session and project context")
    capability: CapabilityManifest = Field(..., description="Target capability manifest")
    harness_feedback: List[HarnessResult] = Field(default_factory=list, description="Prior attempt harness feedback")
    previous_attempts: List[GenerationAttempt] = Field(default_factory=list, description="Prior execution history")


class CompiledPrompt(KeystoneContractModel):
    """Authoritative compiled prompt artifact (Bible §9)."""
    compiler_version: str = Field(..., description="Semantic version of compiler")
    target_capability: str = Field(..., description="Capability ID")
    target_provider: str = Field(..., description="Target provider ID")
    positive_prompt: str = Field(..., description="Fully compiled positive prompt string")
    negative_prompt: Optional[str] = Field(None, description="Fully compiled negative prompt string")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Compiled provider parameter dictionary")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Compilation metadata, hash, and inputs")
    prompt_hash: str = Field(..., description="Deterministic SHA-256 hash of compiled prompt & parameters")


# ============================================================================
# 7. Cognition, Authority & Execution Envelopes (Bible §10, §12)
# ============================================================================

class ProposedAction(KeystoneContractModel):
    """
    Structured action proposed by Qwen cognition (Bible §10, §12).
    """
    action_type: str = Field(
        ..., min_length=1, description="Action category: generate, edit, animate, transform, analyze"
    )
    capability: str = Field(
        ..., min_length=1, description="Target capability identifier e.g. creative.image_generation"
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Proposed workflow parameter dictionary"
    )
    rationale: str = Field(
        default="", description="Cognitive rationale and justification"
    )
    estimated_credits: int = Field(
        default=1, ge=0, description="Estimated credit cost for pre-execution hold"
    )


class CognitiveResult(KeystoneContractModel):
    """
    Complete cognition output produced by Qwen runtime (Bible §10).
    """
    reasoning_id: str = Field(..., description="Unique reasoning session identifier")
    intent: PromptIntent = Field(..., description="Inferred and structured creative intent")
    proposed_actions: List[ProposedAction] = Field(..., min_length=1, description="Proposed execution actions")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Cognitive model confidence score")
    observations: Dict[str, Any] = Field(default_factory=dict, description="Extracted structural observations")


class AuthorityDecision(KeystoneContractModel):
    """
    Authoritative decision rendered by AuthorityEngine (Bible §12).
    """
    decision_id: str = Field(..., description="Unique decision UUID")
    request_id: str = Field(..., description="Associated request UUID")
    decision: Literal["approve", "deny", "replan"] = Field(
        ..., description="Authority outcome verdict"
    )
    capability_id: Optional[str] = Field(None, description="Approved capability ID")
    provider_id: Optional[str] = Field(None, description="Approved provider ID")
    sanitized_arguments: Dict[str, Any] = Field(
        default_factory=dict, description="Sanitized arguments with bounds enforced"
    )
    reason_codes: List[str] = Field(
        default_factory=list, description="Policy violation or approval codes"
    )
    policy_bundle_version: str = Field("1.0.0", description="Active policy bundle version")
    capability_registry_version: str = Field("1.0.0", description="Active capability registry version")
    harness_bundle_version: str = Field("1.0.0", description="Active harness bundle version")


class ExecutionEnvelope(KeystoneContractModel):
    """
    Cryptographically signed, short-expiry execution token delivered to workers (Bible §12).
    """
    envelope_id: str = Field(..., description="Unique envelope UUID")
    decision_id: str = Field(..., description="Authorizing decision UUID")
    job_id: str = Field(..., description="Job UUID")
    user_id: str = Field(..., description="User UUID owning the job")
    capability_id: str = Field(..., description="Capability ID")
    provider_id: str = Field(..., description="Provider ID")
    workflow_id: str = Field(..., description="Workflow graph identifier")
    workflow_version: str = Field(..., description="Workflow template version")
    compiled_prompt_id: str = Field(..., description="Hash or UUID of compiled prompt")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Immutable execution arguments")
    input_asset_ids: List[str] = Field(default_factory=list, description="IDs of input assets in Cloud Storage")
    issued_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(..., description="Strict short expiration timestamp (typically 15 min)")
    nonce: str = Field(..., description="Single-use cryptographic nonce")
    signature: str = Field(..., description="HMAC-SHA256 signature generated by KEYSTONE master authority")


# ============================================================================
# 8. Feedback & Replan Contracts (Bible §16)
# ============================================================================

class UserFeedback(KeystoneContractModel):
    """Customer-submitted evaluation and rating (Bible §16)."""
    job_id: str
    user_id: str
    rating: Optional[float] = Field(None, ge=0.0, le=5.0)
    accepted: Optional[bool] = None
    regeneration_requested: bool = False
    selected_asset_id: Optional[str] = None
    feedback_tags: List[str] = Field(default_factory=list)
    comment: Optional[str] = Field(None, max_length=4000)


class PromptRevisionRequest(KeystoneContractModel):
    """Input to Qwen when executing a bounded quality retry (Bible §16)."""
    original_intent: PromptIntent
    previous_prompt: CompiledPrompt
    quality_scores: List[QualityScore]
    failure_codes: List[str] = Field(default_factory=list)
    immutable_constraints: List[str] = Field(default_factory=list)
    attempt_number: int = Field(ge=1)


class PromptRevisionProposal(KeystoneContractModel):
    """Qwen revision proposal for next retry attempt (Bible §16)."""
    preserve: List[str] = Field(default_factory=list)
    change: List[str] = Field(default_factory=list)
    parameter_suggestions: Dict[str, Any] = Field(default_factory=dict)
    reasoning_summary: str
    confidence: float = Field(ge=0.0, le=1.0)
