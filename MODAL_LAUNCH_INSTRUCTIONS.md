# KEYSTONE Modal Headless Worker Launch Instructions (`3.ipynb` 1:1 Parity)

This guide covers deploying [keystone_a100_worker_v2.py](file:///c:/Users/Lesia%20Eden/Downloads/keystone-cowork/infrastructure/modal/keystone_a100_worker_v2.py) on Modal (`jordandavid1`) as an exact headless mirror of [3.ipynb](file:///c:/Users/Lesia%20Eden/Downloads/keystone-cowork/3.ipynb) (`https://colab.research.google.com/drive/1-irYXNdOfDqUOZhKP8xveCczanNEhlw3#scrollTo=pull_model`).

---

## 1. Exact `3.ipynb` Parity in `keystone_a100_worker_v2.py`

1. **Cognition Engine (`llama.cpp` `llama-cli` & `llama-server` on Port `8081`):**
   - Compiles `llama.cpp` with `-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="80;90" -DGGML_CUDA_FA_QUANTS=all`.
   - Downloads `OBLITERATUS/Qwen3.8-27B-OBLITERATED` (`Qwen3.8-27B-OBLITERATED-Q8_0.gguf`) into `/models/models/Qwen3.8-27B-OBLITERATED-Q8_0.gguf`.
   - Runs `llama-server` with the exact `LLAMA_CONFIG` flags from `3.ipynb`:
     ```text
     llama-server -m /models/models/Qwen3.8-27B-OBLITERATED-Q8_0.gguf
       --alias OBLITERATUS/Qwen3.8-27B-OBLITERATED:fastest
       --host 0.0.0.0 --port 8081 --api-key keystone-live-key --metrics --slots
       -ngl 999 --flash-attn on -c 32768 -ctk q8_0 -ctv q8_0 -b 2048 -ub 2048 -np 16
       --cont-batching --jinja --temp 0.2 --min-p 0.05 --repeat-penalty 1.05
     ```
2. **Creative Video & Audio Engine (`ComfyUI` on Port `8188`):**
   - Clones `ComfyUI` + `ComfyUI-KJNodes` + `ComfyUI-VideoHelperSuite` + `ComfyUI-Manager` + `sageattention`.
   - Downloads all **12** model files from `3.ipynb` Section 6 (`#fe2cb246`) into `/models/comfyui_models`:
     - `diffusion_models/PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors` (`SexGod1979/PinkCherry-NSFW_MiniMax-H3`)
     - `diffusion_models/PinkCherry_hybrid_v1.8_int8_minimax_h3_pruned.safetensors` (`SexGod1979/PinkCherry-NSFW_MiniMax-H3`)
     - Plus all 5 workflow & `CheckpointLoader` symlinks
     - `vae/minimax_h3_video_vae_fp16.safetensors` & `vae/minimax_h3_audio_vae_fp32.safetensors` (`Comfy-Org/MiniMax-H3`)
     - `vae_approx/taeh3.safetensors` & `vae_approx/taeh3_2d_kijai.safetensors` (`t8star/Taeh3-Comfy`)
     - `latent_upscale_models/minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors` (`LBH-123-AI/Minimax_h3_latent_Upscaler`)
     - `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors` & `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` (`Comfy-Org/MiniMax-H3`)
     - `loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` (+ `MiniMaxh3 Turbo/` symlink) & `loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors` (`Comfy-Org/MiniMax-H3`)
     - `embeddings/minimaxh3_art_is_explosion.safetensors` (`Comfy-Org/MiniMax-H3`)
   - Populates sample reference inputs (`Test__00347-audio.mp4` + frame/clip aliases) and patches both workflows (`PinkCherry_ref2va_turbo_lightx2v_workflow.json` & `MiniMaxH3_PinkCherryV15_Fla2va_wTurbo.json`).

---

## 2. Step-by-Step Terminal Commands

Run these commands in PowerShell from `c:\Users\Lesia Eden\Downloads\keystone-cowork`:

### Step 1 — Stage All `3.ipynb` Weights into the Modal Volume (`keystone-models-vol`)
```powershell
$env:PYTHONIOENCODING = "utf-8"
.\.venv-modal\Scripts\modal.exe run infrastructure/modal/keystone_a100_worker_v2.py
```

### Step 2 — Verify the Modal Volume Contents
```powershell
.\.venv-modal\Scripts\modal.exe volume ls keystone-models-vol
.\.venv-modal\Scripts\modal.exe volume ls keystone-models-vol/models
.\.venv-modal\Scripts\modal.exe volume ls keystone-models-vol/comfyui_models
```

### Step 3 — Deploy the Persistent Headless Endpoints (`cognition_llama_server` & `creative_comfyui_server`)
```powershell
.\.venv-modal\Scripts\modal.exe deploy infrastructure/modal/keystone_a100_worker_v2.py
```

### Step 4 — Connect `.env` (or `3.ipynb` Section 8) to the Modal URLs
Update [.env](file:///c:/Users/Lesia%20Eden/Downloads/keystone-cowork/.env) with the two Modal URLs printed by `modal deploy`:
```ini
OPENAI_BASE_URL=https://jordandavid1--keystone-a100-worker-v2-cognition-llama-server.modal.run/v1
OPENAI_API_KEY=keystone-live-key
OPENAI_MODEL=OBLITERATUS/Qwen3.8-27B-OBLITERATED:fastest

KEYSTONE_COMFY_URL=https://jordandavid1--keystone-a100-worker-v2-creative-comfyui-server.modal.run
KEYSTONE_COMFY_WORKFLOW=workflows/h3-ref2va.json
KEYSTONE_H3_CHECKPOINT=PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors
KEYSTONE_H3_REPO=SexGod1979/PinkCherry-NSFW_MiniMax-H3
```
