# KEYSTONE Milestone M3 Architectural Blueprint: Cognition & Authority
**Milestone:** M3 (Wave 3: Cognition & Authority)  
**Author:** explorer_m3_2 (teamwork_preview_explorer)  
**Date:** 2026-10-23  
**Status:** Canonical Architectural Blueprint  
**Target Delivery Path:** `services/cognition/`, `services/authority/`, `services/harness/`, `apps/api/src/routers/`  

---

## 1. Executive Summary & Invariant System Boundaries

Milestone M3 establishes the sovereign cognitive reasoning, capability typing, and deterministic authority enforcement layer for KEYSTONE per `KEYSTONE_BIBLE.md` (§2, §10, §11, §12, §13, §14, §24) and `ORIGINAL_REQUEST.md`.

```text
+----------------------------------------------------------------------------------------------------+
|                                    KEYSTONE APPLICATION CORE                                       |
|                                                                                                    |
|  [User Request]                                                                                    |
|         |                                                                                          |
|         v                                                                                          |
|  [Prompt Engine & Aikido Defense (M2)]                                                             |
|         |                                                                                          |
|         v                                                                                          |
|  +-----------------------------------------------------------------------------------------------+ |
|  | F14 / F13: Cognition Connector (Qwen-27B on Kaggle T4x2 TP=2 + 26.7GB CPU Offload)           | |
|  | - Pinned Checkpoint: huihui-ai/Huihui-Qwen3.8-27B-abliterated (Locked Invariant §2 #6, §11)   | |
|  | - Structured Output: ProposedAction across 6 Action Types & 6 Capability Namespaces            | |
|  +-----------------------------------------------------------------------------------------------+ |
|         |                                                                                          |
|         | (ProposedAction)                                                                         |
|         v                                                                                          |
|  +-----------------------------------------------------------------------------------------------+ |
|  | F15: Authority Decision Engine (services/authority/src/)                                      | |
|  | - SafetyPolicyEvaluator (Forbidden terms, destructive ops, Aikido delimiter quarantine)       | |
|  | - CreditBalanceEvaluator (Tenant available credits: balance - held >= estimated_credits)     | |
|  | - ParameterBoundaryEvaluator (Resolution ceilings, aspect ratio whitelist, step limits)       | |
|  | - Generates AuthorityDecision: ALLOW | DENY | REQUIRE_CONFIRMATION                              | |
|  | - Emits AuditEvent into audit_events table                                                     | |
|  +-----------------------------------------------------------------------------------------------+ |
|         |                                                                                          |
|         | (On ALLOW)                                                                               |
|         v                                                                                          |
|  +-----------------------------------------------------------------------------------------------+ |
|  | F18: Signed Execution Envelope Engine (services/harness/src/envelope.py)                       | |
|  | - Cryptographic HMAC-SHA256 signature with master secret                                      | |
|  | - Single-use nonce & replay prevention (TTL cache)                                              | |
|  | - Short expiration (300s) + clock skew tolerance (+/- 30s)                                    | |
|  +-----------------------------------------------------------------------------------------------+ |
|         |                                                                                          |
|         | (Signed ExecutionEnvelope)                                                               |
|         v                                                                                          |
|  +-----------------------------------------------------------------------------------------------+ |
|  | F17: Kaggle Worker Bridge & Ephemeral Registration (services/harness/src/worker_bridge.py)     | |
|  | - POST /internal/workers/register (Dynamic tunnel discovery: Cloudflare / ngrok)              | |
|  | - 30s Heartbeat loop & 90s offline detection                                                   | |
|  | - Secure dispatch to ephemeral ComfyUI / Wan / FaceFusion workers                             | |
|  +-----------------------------------------------------------------------------------------------+ |
+----------------------------------------------------------------------------------------------------+
```

### Locked Invariants Governed in M3
1. **Bible Invariant 2 (§2 #2, §5)**: KEYSTONE alone compiles and authorizes model prompts. External models and workers cannot mutate approved prompts.
2. **Bible Invariant 6 & 10 (§2 #6, §11, §24)**: The cognition checkpoint is permanently pinned to `huihui-ai/Huihui-Qwen3.8-27B-abliterated`. It must NEVER be replaced, realigned, fine-tuned for refusals, or quantized (AWQ/GPTQ/GGUF/BitsAndBytes/FP8 are strictly prohibited).
3. **Bible Invariant 8 (§2 #8, §12)**: Workers execute only cryptographically validated `ExecutionEnvelope`s issued by the Authority Engine.
4. **Bible Invariant 9 (§2 #9, §12)**: Users, models, harnesses, and workers cannot bypass the `AuthorityEngine`.
5. **Bible Invariant 11 (§2 #11, §24)**: Memory pressure on Kaggle is managed strictly through hardware probing, CPU offload into host RAM, context reduction, or the 7 controlled retry profiles—never by substituting the model.

---

## 2. F14: ProposedAction Structured Output & Capability Typing (Bible §12)

### 2.1 Action Types & Capability Namespaces
M3 mandates strict schema definitions and validation for all 6 action types across 6 capability namespaces:

| Action Type (`action_type`) | Capability Namespace (`capability`) | Description | Mandatory Parameters | Optional Parameters |
|---|---|---|---|---|
| `generate` | `image.generation` | Text-to-image synthesis (ComfyUI / FLUX / SDXL) | `prompt` | `negative_prompt`, `aspect_ratio`, `width`, `height`, `steps`, `guidance`, `seed` |
| `edit` | `image.editing` | Inpainting, region replacement, instruct-editing | `prompt`, `input_asset_id` | `mask_asset_id`, `edit_mode` (inpaint/replace/instruct), `denoise`, `steps` |
| `animate` | `video.i2v` | Image-to-video animation (Wan 2.1 / ComfyUI) | `prompt`, `input_asset_id` | `duration_seconds`, `fps`, `motion_strength`, `aspect_ratio`, `resolution` |
| `generate` / `animate` | `video.t2v` | Text-to-video direct generation (Wan 2.1) | `prompt` | `duration_seconds`, `fps`, `aspect_ratio`, `resolution`, `steps`, `seed` |
| `variate` | `identity.flux_pulid` | Identity-preserving portrait variation (PuLID) | `prompt`, `identity_asset_id` | `identity_weight`, `aspect_ratio`, `steps`, `guidance`, `seed` |
| `upscale` | `upscale.clarity` | High-fidelity latent upscale and clarity enhance | `input_asset_id` | `scale_factor` (2 or 4), `creativity`, `resemblance`, `steps` |
| `analyze` | `analysis.inspect` | Multimodal visual inspection & prompt critique | `input_asset_ids`, `query` | `detail_level`, `aspects` (list of inspection dimensions) |

### 2.2 Parameter Boundary Specifications & Invariants
```python
ASPECT_RATIO_WHITELIST = {"1:1", "16:9", "9:16", "4:3", "3:4", "21:9"}
IMAGE_MAX_WIDTH = 2048
IMAGE_MAX_HEIGHT = 2048
IMAGE_MIN_DIMENSION = 256
VIDEO_MAX_RESOLUTION = "1080p"  # 1920x1080
VIDEO_DEFAULT_RESOLUTION = "720p"  # 1280x720
VIDEO_MAX_DURATION_SECONDS = 10
VIDEO_MIN_DURATION_SECONDS = 1
VIDEO_FPS_RANGE = (8, 30)
STEPS_RANGE = (1, 50)
GUIDANCE_RANGE = (1.0, 20.0)
DENOISE_RANGE = (0.05, 1.0)
IDENTITY_WEIGHT_RANGE = (0.1, 1.0)
UPSCALE_SCALE_FACTORS = {2, 4}
```

### 2.3 Estimated Credit Calculation Rules
Credit calculation is deterministic and calculated before authority evaluation:
$$\text{Estimated Credits} = \text{Base Credits} + \sum \text{Modifiers}$$

```python
BASE_CREDIT_TABLE = {
    "image.generation": 1,
    "image.editing": 2,
    "video.i2v": 5,
    "video.t2v": 5,
    "identity.flux_pulid": 3,
    "upscale.clarity": 2,
    "analysis.inspect": 1,
}

def calculate_estimated_credits(capability: str, params: dict) -> int:
    base = BASE_CREDIT_TABLE.get(capability, 1)
    modifiers = 0
    
    # 1. Video modifiers
    if capability in ("video.i2v", "video.t2v"):
        resolution = params.get("resolution", "720p")
        if resolution == "1080p":
            modifiers += 5  # High-res video penalty
        duration = params.get("duration_seconds", 5)
        if duration > 5:
            modifiers += int(duration - 5)  # 1 credit per second above 5s
            
    # 2. Image modifiers
    elif capability in ("image.generation", "image.editing", "identity.flux_pulid"):
        w = params.get("width", 1024)
        h = params.get("height", 1024)
        if (w * h) > (1024 * 1024):
            modifiers += 1  # 2K resolution bonus
        steps = params.get("steps", 30)
        if steps > 35:
            modifiers += 1  # High step sampling bonus
            
    # 3. Upscale modifiers
    elif capability == "upscale.clarity":
        scale = params.get("scale_factor", 2)
        if scale == 4:
            modifiers += 2  # 4x upscale requires 2x compute
            
    return base + modifiers
```

### 2.4 Resilient JSON Parsing & Fallback Handling
The cognition output parser in `services/cognition/src/client.py` implements multi-stage recovery:
1. **Markdown Stripping**: Strips ````json ... ```` fences, raw quotes, and leading/trailing whitespace.
2. **JSON Heuristic Repair**: Replaces trailing commas, normalizes single quotes, and extracts balanced `{ ... }` blocks.
3. **Pydantic Validation**: Validates against `ProposedAction`.
4. **Fallback Proposal**: If parsing fails after retries, returns a safe fallback proposal:
   ```json
   {
     "action_type": "generate",
     "capability": "image.generation",
     "parameters": {"prompt": prompt, "aspect_ratio": "16:9"},
     "rationale": "Deterministic fallback action generated following cognitive parsing anomaly",
     "estimated_credits": 1
   }
   ```

---

## 3. F15: Authority Decision Engine (Bible §13, services/authority/src/)

### 3.1 Architectural Structure
The Authority subsystem resides in `services/authority/src/`:
- `engine.py`: `AuthorityEngine` orchestrating the evaluation pipeline.
- `evaluator.py`: Component evaluators (`SafetyPolicyEvaluator`, `CreditBalanceEvaluator`, `ParameterBoundaryEvaluator`).
- `registry.py`: `PolicyRegistry`, `CapabilityRegistry`, and `HarnessRegistry`.
- `models.py`: Internal evaluation state and decision models.

### 3.2 Evaluation Pipeline
The `AuthorityEngine.evaluate(request)` method executes sequential gates:

```text
[Incoming ProposedAction]
          |
          v
[Gate 1: Safety & Security Policy] -----> REJECT? ----> DENY (SAFETY_POLICY_VIOLATION)
          | (Pass)
          v
[Gate 2: Capability & Registry] --------> REJECT? ----> DENY (UNKNOWN_CAPABILITY)
          | (Pass)
          v
[Gate 3: Parameter Boundary Check] -----> INVALID? ---> Clamp or DENY (OUT_OF_BOUNDS_PARAMETER)
          | (Pass/Clamped)
          v
[Gate 4: Tenant Credit Balance] --------> < Cost? ----> DENY (INSUFFICIENT_CREDITS)
          | (Sufficient)
          v
[Gate 5: Confirmation Policy] ----------> Cost > 10? -> REQUIRE_CONFIRMATION
          | (Under threshold)
          v
      [ALLOW] ---> Emit AuditEvent into audit_events
```

### 3.3 Detailed Policy Gate Specifications
1. **SafetyPolicyEvaluator**:
   - Inspects `prompt`, `parameters`, and `rationale`.
   - Forbidden terms: CSAM, weapons of mass destruction, violent hate, credential harvesting, malware.
   - Destructive operations: SQL injection, database destruction (`DROP TABLE`, `DELETE FROM`, `TRUNCATE`), system commands (`rm -rf`, `chmod`, `system override`).
   - Aikido Quarantine Verification: Verifies that untrusted inputs remain inside `<untrusted_content>` delimiters and closing tags are escaped (`&lt;/untrusted_content&gt;`).
2. **CreditBalanceEvaluator**:
   - Retrieves tenant's `CreditAccount` from the database.
   - Calculates `available_credits = balance - held_balance`.
   - Invariant check: `available_credits >= estimated_credits`.
   - If `available_credits < estimated_credits`, returns `DENY` with reason code `INSUFFICIENT_CREDITS`.
3. **ParameterBoundaryEvaluator**:
   - Validates `aspect_ratio` against whitelist. Clamps or rejects unsupported ratios.
   - Validates resolution against ceilings (`width <= 2048`, `height <= 2048`).
   - Clamps `steps` to `[1, 50]`, `guidance` to `[1.0, 20.0]`, and `denoise` to `[0.05, 1.0]`.
   - Checks presence of required asset IDs for image editing, video I2V, identity, and upscale.
4. **Decision Output Model**:
   ```python
   class AuthorityDecisionResult(BaseModel):
       decision_id: str = Field(default_factory=lambda: f"dec_{uuid.uuid4().hex[:12]}")
       request_id: str
       decision: Literal["ALLOW", "DENY", "REQUIRE_CONFIRMATION"]
       decision_enum: Literal["approve", "deny", "replan"]  # Backward compatibility with models.py
       capability_id: str
       provider_id: str
       required_credits: int
       sanitized_arguments: Dict[str, Any]
       reason_codes: List[str]
       policy_bundle_version: str = "1.0.0"
       capability_registry_version: str = "1.0.0"
       harness_bundle_version: str = "1.0.0"
       created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
   ```
5. **Audit Event Emission**:
   Every decision writes an entry to `audit_events`:
   - `id`: UUID
   - `actor_type`: `"authority_engine"`
   - `actor_id`: user_id or `"keystone_system"`
   - `event_type`: `"authority.decision"`
   - `request_id`: request UUID
   - `job_id`: job UUID (if present)
   - `data`: `{ "decision": decision, "capability_id": capability_id, "required_credits": credits, "reason_codes": reason_codes, "sanitized_parameters": sanitized_arguments }`
   - `created_at`: UTC timestamp

---

## 4. F16: Kaggle Memory Harness & Hardware Probe (Bible §24)

### 4.1 Kaggle Tier 0 Hardware Topology
- **Host**: Kaggle GPU VM (Linux, Python 3.10+, CUDA 12.x).
- **Accelerators**: 2x NVIDIA Tesla T4 (PCIe, 16 GB GDDR6 VRAM each, total 32 GB VRAM).
- **Interconnect**: PCIe Gen3 (no NVLink; vLLM requires Tensor Parallelism = 2).
- **System Memory**: ~80 GB host RAM (dynamic allocation, observed ~78-83 GiB).

### 4.2 Exact Memory Offload Derivation
Model: `huihui-ai/Huihui-Qwen3.8-27B-abliterated`
- **Total Parameters ($N$)**: ~27 Billion ($27 \times 10^9$).
- **Precision**: BF16 (16-bit floating point = 2 bytes per parameter).
- **Raw Weights Footprint**:
  $$W_{\text{raw}} = 27 \times 10^9 \times 2 \text{ bytes} \approx 54 \text{ GB} = 51.7 \text{ GiB}$$
- **GPU VRAM Breakdown (2x T4, 32.0 GiB total)**:
  - Total raw VRAM: $2 \times 16.0 \text{ GiB} = 32.0 \text{ GiB}$
  - CUDA Driver & PyTorch context reserve: $2 \times 1.0 \text{ GiB} = 2.0 \text{ GiB}$
  - Working KV Cache & Scratchpad reserve ($TP=2$): $5.0 \text{ GiB}$
  - **Usable Weight VRAM on GPUs**:
    $$V_{\text{usable}} = 30.0 \text{ GiB} - 5.0 \text{ GiB} = 25.0 \text{ GiB}$$
- **Required CPU Weight Offload**:
  $$W_{\text{offload}} = W_{\text{raw}} - V_{\text{usable}} = 51.7 \text{ GiB} - 25.0 \text{ GiB} = \mathbf{26.7 \text{ GiB}}$$
- **Host RAM Budget & Headroom Check**:
  - Kaggle Host RAM pool: $\sim 80.0 \text{ GiB}$
  - Host OS & vLLM CPU process reserve: $12.0 \text{ GiB}$
  - Safe Offload Ceiling: $80.0 \text{ GiB} - 12.0 \text{ GiB} = 68.0 \text{ GiB}$
  - **Safety Assertion**:
    $$W_{\text{offload}} (26.7 \text{ GiB}) \ll \text{Ceiling} (68.0 \text{ GiB})$$
    $$\text{Host RAM Headroom} = 68.0 \text{ GiB} - 26.7 \text{ GiB} = \mathbf{41.3 \text{ GiB surplus}}$$
  Conclusion: The 27B model fits with high stability without triggering the Linux OOM killer (`oom-killer`).

### 4.3 7 Controlled Retry Profiles (Bible §24)
Per Bible §24 and Locked Invariants §2 #10 and §11, model quantization (AWQ/GPTQ/GGUF/BitsAndBytes/FP8) is strictly PROHIBITED. Memory pressure is resolved solely through the 7 controlled retry profiles:

```python
KAGGLE_RETRY_PROFILES = [
    {
        "profile_id": 1,
        "name": "baseline_tp2",
        "description": "Standard baseline: TP=2, 27GB CPU offload, 2048 context",
        "tensor_parallel_size": 2,
        "cpu_offload_gb": 27,
        "max_model_len": 2048,
        "max_num_seqs": 4,
        "gpu_memory_utilization": 0.90,
        "max_num_batched_tokens": 2048
    },
    {
        "profile_id": 2,
        "name": "memory_conserve",
        "description": "Reduce VRAM fragmentation: gpu_mem_util=0.85, 28GB offload",
        "tensor_parallel_size": 2,
        "cpu_offload_gb": 28,
        "max_model_len": 2048,
        "max_num_seqs": 2,
        "gpu_memory_utilization": 0.85,
        "max_num_batched_tokens": 1024
    },
    {
        "profile_id": 3,
        "name": "context_truncate",
        "description": "Slash KV cache by 50%: max_model_len=1024",
        "tensor_parallel_size": 2,
        "cpu_offload_gb": 27,
        "max_model_len": 1024,
        "max_num_seqs": 2,
        "gpu_memory_utilization": 0.85,
        "max_num_batched_tokens": 1024
    },
    {
        "profile_id": 4,
        "name": "single_sequence",
        "description": "Zero concurrency: max_num_seqs=1, strict sequential execution",
        "tensor_parallel_size": 2,
        "cpu_offload_gb": 27,
        "max_model_len": 1024,
        "max_num_seqs": 1,
        "gpu_memory_utilization": 0.80,
        "max_num_batched_tokens": 512
    },
    {
        "profile_id": 5,
        "name": "batch_token_conserve",
        "description": "Strict batch budget: max_num_batched_tokens=512, 28GB offload",
        "tensor_parallel_size": 2,
        "cpu_offload_gb": 28,
        "max_model_len": 1024,
        "max_num_seqs": 1,
        "gpu_memory_utilization": 0.80,
        "max_num_batched_tokens": 512
    },
    {
        "profile_id": 6,
        "name": "swap_heavy",
        "description": "Extreme host buffering: 29GB offload, 512 context, gpu_mem_util=0.75",
        "tensor_parallel_size": 2,
        "cpu_offload_gb": 29,
        "max_model_len": 512,
        "max_num_seqs": 1,
        "gpu_memory_utilization": 0.75,
        "max_num_batched_tokens": 256
    },
    {
        "profile_id": 7,
        "name": "stop_and_report",
        "description": "Exhausted all approved profiles: Halt execution, emit KHF diagnostic memory report, trigger founder escalation",
        "action": "HALT_AND_ESCALATE",
        "allow_quantization": False
    }
]
```

---

## 5. F17: Kaggle Worker Bridge & Ephemeral Registration (Bible §24)

### 5.1 Dynamic Handshake Architecture
Because Kaggle sessions terminate every ~9-12 hours and assign dynamic tunnel hostnames (via Cloudflare Quick Tunnels or ngrok), KEYSTONE Cloud Run API must discover and register workers dynamically without redeploying.

```text
[Kaggle Worker Boot]
         |
         v
[Start vLLM / ComfyUI on localhost:8000]
         |
         v
[Start Cloudflare Tunnel] ----> Yields: https://brave-frog-42.trycloudflare.com
         |
         v
[POST /internal/workers/register to Cloud Run API]
  Headers: { "Authorization": "Bearer KEYSTONE_WORKER_SECRET" }
  Payload: {
    "worker_id": "kaggle-node-t4x2-01",
    "worker_type": "cognition",
    "tunnel_url": "https://brave-frog-42.trycloudflare.com",
    "capabilities": ["image.generation", "video.i2v"],
    "hardware": { "gpu_count": 2, "gpu_vram_gb": 32, "host_ram_gb": 80 }
  }
         |
         v
[Cloud Run API: Probe Handshake]
  GET https://brave-frog-42.trycloudflare.com/health
         | (200 OK)
         v
[Registered in WorkerRegistry: State=ACTIVE]
         |
         +<----------------------------------+
         |                                   |
         v (Every 30s)                       |
[POST /internal/workers/heartbeat] ----------+
         |
         +--> Missed 3 heartbeats (90s)? --> State=OFFLINE (Re-route jobs)
```

### 5.2 Worker Bridge Endpoints
1. `POST /internal/workers/register`:
   - Validates `worker_auth_token`.
   - Dispatches a verification `GET {tunnel_url}/health` ping.
   - Saves or updates record in `WorkerRegistry`.
2. `POST /internal/workers/heartbeat`:
   - Receives `{ "worker_id": str, "metrics": { "gpu_utilization": float, "vram_used_gb": float, "active_jobs": int } }`.
   - Updates `last_heartbeat_at`.
3. `GET /internal/workers`:
   - Returns list of active workers and capabilities for routing.
4. `POST /internal/workers/drain`:
   - Gracefully drains a worker before Kaggle session timeout.

---

## 6. F18: Signed Execution Envelope Engine (Bible §14)

### 6.1 Cryptographic Specification
Workers execute only signed `ExecutionEnvelope`s. Any tampering or unauthorized replay causes immediate rejection.

```python
class ExecutionEnvelopePayload(BaseModel):
    envelope_id: str = Field(default_factory=lambda: f"env_{uuid.uuid4().hex[:12]}")
    decision_id: str
    job_id: str
    user_id: str
    capability_id: str
    provider_id: str
    workflow_id: str
    workflow_version: str
    compiled_prompt_id: str
    arguments: Dict[str, Any]
    input_asset_ids: List[str]
    issued_at: int  # UTC Unix timestamp in seconds
    expires_at: int  # UTC Unix timestamp in seconds (issued_at + 300)
    nonce: str = Field(default_factory=lambda: uuid.uuid4().hex)
```

### 6.2 Signature Generation & Verification Algorithm
- **Algorithm**: `HMAC-SHA256`
- **Key**: `KEYSTONE_ENVELOPE_SECRET`
- **Canonical Serialization**:
  ```python
  def canonical_serialize(payload_dict: dict) -> bytes:
      # Exclude signature during signing
      signing_data = {k: v for k, v in payload_dict.items() if k != "signature"}
      return json.dumps(signing_data, sort_keys=True, separators=(",", ":")).encode("utf-8")

  def generate_signature(payload_dict: dict, secret: str) -> str:
      canonical_bytes = canonical_serialize(payload_dict)
      return hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()

  def verify_signature(envelope_dict: dict, secret: str) -> bool:
      sig = envelope_dict.get("signature")
      if not sig:
          return False
      expected = generate_signature(envelope_dict, secret)
      return hmac.compare_digest(sig, expected)
  ```

### 6.3 Nonce Management & Replay Defense
- **Single-Use Invariant**: Every nonce must be used at most once.
- **Nonce Cache**: `NonceReplayCache` with TTL = 300 seconds (matching envelope lifetime).
- When validating an envelope:
  ```python
  if nonce_cache.has(envelope.nonce):
      raise ReplayAttackError(f"REPLAY_ATTACK_DETECTED: Nonce {envelope.nonce} has already been consumed")
  nonce_cache.set(envelope.nonce, ttl=300)
  ```

### 6.4 Expiration & Clock Skew Tolerance
- **Lifetime**: Exactly 300 seconds (5 minutes).
- **Clock Skew Tolerance**: $\pm 30$ seconds to absorb drift between Cloud Run and Kaggle hosts.
- **Validation Rule**:
  $$\text{issued\_at} - 30 \le \text{now} \le \text{expires\_at} + 30$$
  If $\text{now} > \text{expires\_at} + 30$: reject with `ENVELOPE_EXPIRED`.  
  If $\text{now} < \text{issued\_at} - 30$: reject with `ENVELOPE_FUTURE_ISSUED`.

---

## 7. Additive REST API Integration

All new M3 routers are mounted additively in `apps/api/src/server.py` without modifying `main.py` or existing routes:

```python
# apps/api/src/server.py (additive modifications)
from apps.api.src.routers.cognition import router as cognition_router
from apps.api.src.routers.authority import router as authority_router
from apps.api.src.routers.workers import router as workers_router

# Mount M3 Routers
app.include_router(cognition_router)
app.include_router(authority_router)
app.include_router(workers_router)
```

### Route Specifications
| Path | Method | Tag | Description |
|---|---|---|---|
| `/v1/cognition/reason` | `POST` | `Cognition` | Submits prompt to Qwen-27B, parses and returns typed `ProposedAction` and telemetry |
| `/v1/cognition/health` | `GET` | `Cognition` | Returns cognition provider health, pinned checkpoint name, latency |
| `/v1/cognition/profiles` | `GET` | `Cognition` | Returns the 7 Kaggle controlled retry profiles |
| `/v1/authority/evaluate` | `POST` | `Authority` | Evaluates `ProposedAction` against safety, credits, parameters; emits audit event |
| `/v1/authority/envelope/issue` | `POST` | `Authority` | Signs and issues an `ExecutionEnvelope` for an approved decision |
| `/v1/authority/envelope/verify`| `POST` | `Authority` | Verifies envelope signature, expiration, and single-use nonce |
| `/internal/workers/register` | `POST` | `Workers` | Registers Kaggle worker tunnel URL, capabilities, and hardware specs |
| `/internal/workers/heartbeat`| `POST` | `Workers` | 30s heartbeat from registered Kaggle worker |
| `/internal/workers` | `GET` | `Workers` | Lists active registered workers and capabilities |

---

## 8. Comprehensive Test Suite Specification: `test_m3_cognition_authority.py`

Test file path: `tests/e2e_v2/test_m3_cognition_authority.py`

### Test Suite Matrix
1. **F14: ProposedAction & Capability Typing (`TestProposedActionF14`)**
   - `test_all_6_action_types_valid`: Verifies `generate`, `edit`, `variate`, `animate`, `upscale`, `analyze`.
   - `test_all_6_capability_namespaces`: Verifies `image.generation`, `image.editing`, `video.i2v`, `video.t2v`, `identity.flux_pulid`, `upscale.clarity`.
   - `test_parameter_boundaries_aspect_ratio_whitelist`: Validates `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `21:9`; rejects invalid `"32:9"`.
   - `test_parameter_boundaries_resolution_ceilings`: Rejects width/height > 2048.
   - `test_estimated_credit_calculation_accuracy`: Verifies base credits and modifiers (1080p video modifier, 2K image modifier, 4x upscale modifier).
   - `test_resilient_markdown_json_parsing`: Verifies parsing of ````json ... ```` fences and single-quote repairs.
   - `test_invalid_action_fallback_recovery`: Verifies fallback to safe deterministic `image.generation` proposal when model output is unrecoverable.

2. **F15: Authority Decision Engine (`TestAuthorityEngineF15`)**
   - `test_safety_policy_forbidden_terms_denial`: Prohibits CSAM, weapons, malicious exploits.
   - `test_safety_policy_destructive_operations_denial`: Prohibits `DROP TABLE`, `rm -rf`, system bypass.
   - `test_aikido_quarantine_integrity`: Confirms untrusted content is quarantined and escaped inside `<untrusted_content>`.
   - `test_tenant_credit_balance_allow`: Allows execution when `balance - held >= estimated_credits`.
   - `test_tenant_credit_balance_insufficient_denial`: Denies execution with `INSUFFICIENT_CREDITS` when balance is deficient.
   - `test_high_cost_confirmation_requirement`: Returns `REQUIRE_CONFIRMATION` when credits > 10.
   - `test_audit_event_emission`: Verifies that every decision emits an `AuditEvent` with actor, request_id, and metadata.

3. **F16: Kaggle Memory Harness & Hardware Probe (`TestKaggleMemoryHarnessF16`)**
   - `test_hardware_probe_2x_t4_tp2`: Simulates probe measuring 2x T4 (32GB VRAM total).
   - `test_bf16_weight_and_offload_math`: Asserts 27B model in BF16 = 51.7 GiB, usable GPU = 25.0 GiB, offload = 26.7 GiB.
   - `test_host_ram_safe_headroom`: Asserts 80GB host RAM - 12GB reserve = 68GB ceiling > 26.7GB offload (headroom > 40GB).
   - `test_all_7_controlled_retry_profiles`: Verifies configuration of profiles 1 through 7.
   - `test_prohibition_of_quantized_substitutes`: Asserts that AWQ, GPTQ, GGUF, BitsAndBytes, and FP8 are strictly prohibited.

4. **F17: Kaggle Worker Bridge (`TestWorkerBridgeF17`)**
   - `test_worker_registration_handshake`: Verifies `POST /internal/workers/register` with tunnel URL and capabilities.
   - `test_worker_heartbeat_loop`: Verifies `POST /internal/workers/heartbeat` updates `last_heartbeat_at`.
   - `test_worker_offline_detection_timeout`: Verifies transition to `OFFLINE` after 90 seconds without heartbeat.
   - `test_worker_capability_routing`: Routes `video.i2v` only to workers declaring video capabilities.

5. **F18: Signed Execution Envelope Engine (`TestExecutionEnvelopeF18`)**
   - `test_hmac_sha256_signature_generation_and_verification`: Verifies valid signature matches canonical serialization.
   - `test_nonce_replay_attack_prevention`: Rejects second submission of the same nonce with `REPLAY_ATTACK_DETECTED`.
   - `test_envelope_expiration`: Rejects envelope after 300 seconds.
   - `test_clock_skew_tolerance`: Accepts envelope within $\pm 30$ seconds window.
   - `test_envelope_tamper_detection`: Tampering with arguments, capability, or prompt hash invalidates HMAC signature.

6. **E2E Integration Flow (`TestM3E2EIntegration`)**
   - End-to-end flow: User Intent $\to$ PromptCompiler $\to$ CognitionConnector $\to$ ProposedAction $\to$ AuthorityEngine $\to$ Credit Hold $\to$ Signed ExecutionEnvelope $\to$ Mock Worker Verification.

---

## 9. Implementation File Layout for Milestone M3 Workers

```text
services/
├── authority/
│   └── src/
│       ├── __init__.py
│       ├── engine.py           # AuthorityEngine coordinator
│       ├── evaluator.py        # Safety, Credit, Parameter evaluators
│       ├── registry.py         # Policy & Capability registries
│       └── models.py           # Internal evaluation models
├── harness/
│   └── src/
│       ├── __init__.py
│       ├── envelope.py         # HMAC-SHA256 ExecutionEnvelope engine & Nonce cache
│       ├── worker_bridge.py    # Ephemeral Kaggle worker registry & heartbeat
│       └── memory_harness.py   # Hardware probe & 7 retry profiles
apps/api/src/routers/
├── authority.py                # /v1/authority endpoints
├── cognition.py                # /v1/cognition endpoints
└── workers.py                  # /internal/workers endpoints
tests/e2e_v2/
└── test_m3_cognition_authority.py # 100% comprehensive pytest verification suite
```

---
*End of Blueprint. Fully compliant with KEYSTONE Bible §2, §10, §11, §12, §13, §14, §24.*
