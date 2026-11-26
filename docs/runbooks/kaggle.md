# KEYSTONE Tier 0 GPU Bootstrap Runbook (Kaggle / Colab)

**Migrated from:** KEYSTONE Bible v1 §24 (`bible-v1-final`) per Bible v2 §24 & ADR-004  
**Scope:** Operator configuration and bootstrap deployment procedures. Hardware specifics, serving stacks (`llama.cpp` / `vLLM`), and sanctioned quantization profiles (`Q8_0.gguf`, `int8`, `fp8`) live here and in `CapabilityManifest` disclosures — never hardcoded in Bible canon.

---

## 1. Deployment Tiers (Bible v2 §24)

```text
Tier 0: Bootstrap GPU infrastructure (Kaggle 2× T4 / Colab Pro)
Tier 1: Dedicated GPU host — cognition GPU-resident where practical, stable workers & storage
Tier 2: Distributed KEYSTONE — dedicated cognition, image, video, and transformation pools
        with autoscaling and queue isolation
```

Tier migration changes deployment and capacity, never KEYSTONE's identity or public contracts.

---

## 2. Active Tier 0 Operator Configuration (Record, Not Canon)

- **Primary Headless GPU Worker (Colab Pro A100 / RTX PRO 6000):**
  - Notebook definition: `3.ipynb`
  - Cognition core: `OBLITERATUS/Qwen3.8-27B-OBLITERATED` (`Qwen3.8-27B-OBLITERATED-Q8_0.gguf` served via `llama-server` on port `8081`, Q8_0 KV cache; quantization sanctioned under Bible v2 §2 Invariant 6)
  - Video core: ComfyUI on port `8188` running `SexGod1979/PinkCherry-NSFW_MiniMax-H3` v1.8 + MiniMax H3 VAEs, Turbo LoRAs, Qwen3-VL 32B text encoder, TAEH3, and 3D-Conv latent upscaler
  - Image & neural upscale staging: SDXL-class (FLUX slot) + ESRGAN chain (PR4/PR5)
- **Legacy Kaggle 2× T4 Bootstrap (`KAGGLE_SETUP/`):**
  - Note: NVIDIA Tesla T4 is Turing (`sm_75`) and does not support native `bfloat16` tensor cores in `vLLM`. Use `llama.cpp` GGUF or `fp16` on T4 hardware, or run on Colab Pro.

---

## 3. Runtime Discovery Discipline (Preserved from Bible v1 §24)

Every Tier 0/1 worker boot measures and reports:
- GPU count, architecture, and model;
- per-GPU VRAM total and available;
- system RAM total and available;
- CUDA and driver versions;
- installed runtime versions (`llama-server`, `vLLM`, `ComfyUI`, `ffmpeg`);
- writable and persistent storage capacity;
- model cache status.

Observed host-memory ceilings are never treated as platform guarantees.

---

## 4. Memory Strategy & Controlled Retry Profiles (Preserved from Bible v1 §24)

When running under VRAM pressure:
1. Measure GPU VRAM + available host RAM before launching serving processes.
2. Preserve host reserve and GPU runtime headroom.
3. Step down cleanly through controlled profiles:
   - adjust CPU layer offload;
   - reduce maximum context length;
   - reduce concurrent sequences (`-np` / `max-num-seqs`);
   - reduce batch token budget;
   - lower GPU memory utilization target on fragmentation;
   - stop and capture OOM evidence if approved profiles are exhausted.
4. **Never** silently substitute an aligned/censored checkpoint or switch model identity to recover from OOM (Bible v2 §2 Invariant 2 & §10).

---

## 5. Legacy Kaggle Setup Directory (`KAGGLE_SETUP/`)

```text
KAGGLE_SETUP/
├── README.md
├── notebooks/
│   ├── 01_keystone_cognition_bootstrap.ipynb
│   ├── 02_keystone_comfyui_runtime.ipynb
│   └── 03_keystone_integrated_gateway.ipynb
├── bridge/
├── configs/
├── scripts/
├── logs/
└── checklists/
```

Security note (Bible v2 §28): Never commit live API keys or print raw bearer tokens in notebook stdout logs; inject secrets via Kaggle Secrets / Modal Secrets / environment secret managers only.
