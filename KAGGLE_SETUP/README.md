# KEYSTONE Tier 0 GPU Production Workspace (`KAGGLE_SETUP`)

**Authoritative Specification**: `KEYSTONE_BIBLE.md` §2 (Invariants 6, 10, 11, 15), §11, §24  
**Directives**: `ORIGINAL_REQUEST.md` (2026-10-22T16:11:55Z & 2026-10-22T16:13:56Z)  
**Cognitive Checkpoint**: `huihui-ai/Huihui-Qwen3.8-27B-abliterated` (Pinned, no substitute, no quantization)  
**Target Hardware**: Kaggle 2x NVIDIA Tesla T4 (15 GiB VRAM each = 30 GiB total) + ~80 GB Host RAM  

---

## 1. Executive Summary & Architecture

The `KAGGLE_SETUP` production workspace provides a sovereign, reproducible GPU execution environment running on Kaggle Tier 0 hardware without modifying the core cloud architecture.

```
                    ┌──────────────────────────────────────────────┐
                    │            Google Cloud Run API              │
                    │   (FastAPI Authority, Ledger, Lineage DAG)   │
                    └──────────────────────▲───────────────────────┘
                                           │
                        POST /internal/workers/register
                        POST /internal/workers/heartbeat
                                           │
  ┌────────────────────────────────────────┴────────────────────────────────────────┐
  │                           KAGGLE T4x2 ENVIRONMENT                               │
  │                                                                                 │
  │  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────┐  │
  │  │ Notebook 01: Cognition  │  │ Notebook 02: ComfyUI    │  │ Notebook 03:    │  │
  │  │ vLLM Qwen 27B TP=2      │  │ Headless Runtime        │  │ Gateway Tunnel  │  │
  │  │ + 26.7 GiB CPU Offload  │  │ Wan 2.1 Video + Harness │  │ Reverse Proxy   │  │
  │  │ Port 8000 (OpenAI API)  │  │ Port 8188 & Port 8189   │  │ cloudflared     │  │
  │  └─────────────────────────┘  └─────────────────────────┘  └─────────────────┘  │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Step-by-Step Founder Execution Guide

### Step 1: Launch Notebook 01 (Cognition Bootstrap)
1. Navigate to [Kaggle](https://www.kaggle.com/) and create a new Python notebook.
2. In the right panel under **Notebook options**:
   - **Accelerator**: Select **GPU T4 x 2**.
   - **Internet**: Toggle **On**.
3. Upload and open `KAGGLE_SETUP/01_keystone_cognition_bootstrap.ipynb`.
4. Run all cells in sequence:
   - Cell 1–2 performs the hardware probe, verifying 2x T4 GPUs and host RAM.
   - Cell 3 calculates the CPU weight offload (~26.7 GiB) and asserts host RAM safety headroom.
   - Cell 4–5 launches vLLM with `tensor-parallel-size 2`, `cpu-offload-gb 27`, and `dtype bfloat16`.
   - Cell 6 verifies structured JSON output conforming to `ProposedAction`.
5. Keep Notebook 01 active.

### Step 2: Launch Notebook 02 (Creative Tool Fabric)
1. Open a second Kaggle session with **GPU T4 x 2** accelerator and **Internet On**.
2. Upload and open `KAGGLE_SETUP/02_keystone_comfyui_runtime.ipynb`.
3. Run all cells in sequence:
   - Clones ComfyUI and installs custom nodes for Wan 2.1 (T2V & I2V), FaceFusion, and Upscale.
   - Provisions model checkpoints into persistent cache.
   - Launches headless ComfyUI daemon on port 8188.
   - Mounts the Keystone Execution Harness on port 8189, validating `ExecutionEnvelope` HMAC signatures and nonces.

### Step 3: Launch Notebook 03 (Integrated Gateway & Cloud Bridge)
1. Open a third Kaggle session (GPU or CPU) with **Internet On**.
2. Upload and open `KAGGLE_SETUP/03_keystone_integrated_gateway.ipynb`.
3. Set your live Cloud Run API URL:
   ```python
   os.environ["KEYSTONE_API_URL"] = "https://your-keystone-api.a.run.app"
   ```
4. Run all cells:
   - Establishes Cloudflare public reverse tunnels mapping to local ports 8000 and 8189.
   - Dispatches worker registration handshake to `POST /internal/workers/register`.
   - Spawns background heartbeat daemon pinging Cloud Run every 30 seconds.
5. In your KEYSTONE workspace, check system capabilities (`GET /v1/capabilities`) to confirm green status.

---

## 3. Cognitive Memory Strategy & CPU Offload Math

Running the 27B parameter model in 16-bit precision requires ~51.7 GiB of weight storage. Two T4 GPUs provide 30.0 GiB total VRAM.

$$\text{Usable GPU VRAM} = \text{Total VRAM} (30.0\,\text{GiB}) - \text{GPU Reserve} (5.0\,\text{GiB}) = 25.0\,\text{GiB}$$

$$\text{Required CPU Offload} = \text{Model Weights} (51.7\,\text{GiB}) - \text{Usable GPU} (25.0\,\text{GiB}) = 26.7\,\text{GiB}$$

$$\text{Host RAM Safety Margin} = \text{Available Host RAM} (\sim 75\text{–}80\,\text{GiB}) - (\text{Offload} (26.7\,\text{GiB}) + \text{Host Reserve} (12.0\,\text{GiB})) \ge 36.3\,\text{GiB}$$

The Memory Harness enforces:
`assert offload <= host_available - HOST_RESERVE_GIB`

---

## 4. The 7 Controlled Retry Profiles (Bible §24)

If memory pressure or allocator fragmentation arises, the system strictly traverses these 7 approved profiles:

| # | Profile | Action | Command Flag / Config |
|---|---------|--------|-----------------------|
| 1 | `baseline tensor parallel 2` | Standard distributed TP across both T4 GPUs | `--tensor-parallel-size 2` |
| 2 | `tune CPU offload` | Increase CPU weight offload ratio | `--cpu-offload-gb 29` |
| 3 | `reduce maximum context` | Lower max token context window | `--max-model-len 2048` |
| 4 | `reduce maximum sequences to one` | Restrict concurrency to single sequence | `--max-num-seqs 1` |
| 5 | `reduce batch token budget` | Lower maximum batched token allocation | `--max-num-batched-tokens 2048` |
| 6 | `lower GPU-memory-utilization target` | Prevent CUDA allocator fragmentation | `--gpu-memory-utilization 0.85` |
| 7 | `stop and report evidence` | Halt execution with diagnostic telemetry | **Quantized fallback is strictly forbidden** |

---

## 5. Post-Build BF16 vs FP16 Comparative Benchmark Procedure

Per Founder Directive (2026-10-22T16:13:56Z):
1. **Build Default**: BF16 remains the official default for all M0–M6 implementations.
2. **Post-Build Evaluation**: After the entire system is built and green, execute the documented comparative benchmark on Kaggle T4x2.
3. **Fixed Prompt Suite**: 20 multimodal creative prompts (T2V, I2V, image generation, editing, reasoning).
4. **Metrics Collected**:
   - Initialization and weight load duration (seconds).
   - VRAM allocation per GPU and host RAM allocation (GiB).
   - Token throughput (tokens/sec) and time-to-first-token (TTFT ms).
   - Structured output validity rate (`ProposedAction` JSON schema conformance, target 100%).
   - Numerical stability check (NaN/inf occurrence, perplexity divergence).
5. **Report Deliverable**: A written comparative evaluation submitted to the founder. FP16 will not be promoted to production default without explicit founder sign-off.

---

## 6. Directory Layout

```
KAGGLE_SETUP/
├── README.md                                   # This operational guide
├── 01_keystone_cognition_bootstrap.ipynb       # vLLM Qwen 27B bootstrap
├── 02_keystone_comfyui_runtime.ipynb           # ComfyUI & Wan 2.1 execution harness
├── 03_keystone_integrated_gateway.ipynb        # Tunnel & registration bridge
├── notebooks/                                  # Canonical copies for setup oracle
│   ├── 01_keystone_cognition_bootstrap.ipynb
│   ├── 02_keystone_comfyui_runtime.ipynb
│   └── 03_keystone_integrated_gateway.ipynb
├── configs/                                    # Hardware, vLLM & ComfyUI configurations
│   ├── README.md
│   ├── vllm_config.json
│   └── comfyui_config.json
├── scripts/                                    # Operational & hardware probe scripts
│   ├── README.md
│   ├── probe_hardware.py
│   └── start_gateway.sh
├── logs/                                       # Runtime diagnostics & stdout logs
│   ├── README.md
│   └── .gitkeep
└── checklists/                                 # Pre-flight & session startup checklists
    ├── README.md
    ├── pre_flight_checklist.md
    └── session_startup_checklist.md
```

