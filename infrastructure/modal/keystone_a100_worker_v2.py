"""
KEYSTONE Modal Serverless GPU Worker v2 — Exact 1:1 Mirror of `3.ipynb`
(https://colab.research.google.com/drive/1-irYXNdOfDqUOZhKP8xveCczanNEhlw3#scrollTo=pull_model)

Architecture identical to `3.ipynb`:
1. Cognition Engine (`llama.cpp` `llama-cli` & `llama-server`):
   - Compiled with Native CUDA + Flash Attention (`-DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="80;90;120" -DGGML_CUDA_FA_QUANTS=all`)
   - Model: `OBLITERATUS/Qwen3.8-27B-OBLITERATED` (`Qwen3.8-27B-OBLITERATED-Q8_0.gguf`, plus full BF16 safetensors support)
   - Flags (`LLAMA_CONFIG`): `-ngl 999 --flash-attn on -c 32768 -ctk q8_0 -ctv q8_0 -b 2048 -ub 2048 -np 16 --cont-batching --jinja --temp 0.2 --min-p 0.05 --repeat-penalty 1.05`
   - Served on Port 8081 (`--alias OBLITERATUS/Qwen3.8-27B-OBLITERATED:fastest`, `--api-key keystone-live-key`)
2. Creative Video & Audio Engine (`ComfyUI` + `ComfyUI-KJNodes` + `ComfyUI-VideoHelperSuite` + `ComfyUI-Manager` + `SageAttention`):
   - Diffusion Models (`SexGod1979/PinkCherry-NSFW_MiniMax-H3`):
     - `1.8-hybrid/PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors`
     - `1.8-hybrid/PinkCherry_hybrid_v1.8_int8_minimax_h3_pruned.safetensors`
     - Plus all 5 workflow & CheckpointLoader symlinks
   - VAEs, TAEH3 & 3D-Conv Latent Upscaler:
     - `Comfy-Org/MiniMax-H3`: `vae/minimax_h3_video_vae_fp16.safetensors`
     - `Comfy-Org/MiniMax-H3`: `vae/minimax_h3_audio_vae_fp32.safetensors`
     - `t8star/Taeh3-Comfy`: `models/vae_approx/taeh3.safetensors` & `models/vae_approx/taeh3_2d_kijai.safetensors`
     - `LBH-123-AI/Minimax_h3_latent_Upscaler`: `minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors`
   - Qwen3-VL 32B Text Encoders (`Comfy-Org/MiniMax-H3`):
     - `text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors`
     - `text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors`
   - Turbo LoRAs & Embeddings (`Comfy-Org/MiniMax-H3`):
     - `loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors` (+ `MiniMaxh3 Turbo/` symlink)
     - `loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors`
     - `embeddings/minimaxh3_art_is_explosion.safetensors`
   - Sample Reference Inputs & Patched Workflows (`SexGod1979/PinkCherry-NSFW_MiniMax-H3`):
     - `1.8-hybrid/Test__00347-audio.mp4` + video/image aliases in `input/`
     - `1.8-hybrid/PinkCherry_ref2va_turbo_lightx2v_workflow.json` & `v1.5-fl2va/MiniMaxH3_PinkCherryV15_Fla2va_wTurbo.json`
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import modal

APP_NAME = "keystone-a100-worker-v2"
VOLUME_NAME = "keystone-models-vol"
MODEL_MOUNT_PATH = "/models"

COGNITION_REPO = "OBLITERATUS/Qwen3.8-27B-OBLITERATED"
COGNITION_GGUF = "Qwen3.8-27B-OBLITERATED-Q8_0.gguf"
COGNITION_ALIAS = "OBLITERATUS/Qwen3.8-27B-OBLITERATED:fastest"
COGNITION_API_KEY = "keystone-live-key"

PINKCHERRY_REPO = "SexGod1979/PinkCherry-NSFW_MiniMax-H3"
PINKCHERRY_BF16 = "1.8-hybrid/PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors"
PINKCHERRY_INT8 = "1.8-hybrid/PinkCherry_hybrid_v1.8_int8_minimax_h3_pruned.safetensors"

# Exact LLAMA_CONFIG from 3.ipynb Section 3
LLAMA_CONFIG: Dict[str, str] = {
    "-ngl": "999",
    "--flash-attn": "on",
    "-c": "32768",
    "-ctk": "q8_0",
    "-ctv": "q8_0",
    "-b": "2048",
    "-ub": "2048",
    "-np": "16",
    "--cont-batching": "",
    "--jinja": "",
    "--temp": "0.2",
    "--min-p": "0.05",
    "--repeat-penalty": "1.05",
}


def build_llama_flags(config_dict: Dict[str, str]) -> List[str]:
    flags: List[str] = []
    for k, v in config_dict.items():
        flags.append(k.strip())
        if v != "":
            flags.append(str(v))
    return flags


# Exact 11 ComfyUI safetensor assets from 3.ipynb Section 6 (Cell fe2cb246)
COMFY_SAFETENSOR_ASSETS: List[Dict[str, str]] = [
    {
        "repo_id": PINKCHERRY_REPO,
        "filename": PINKCHERRY_BF16,
        "subdir": "diffusion_models",
    },
    {
        "repo_id": PINKCHERRY_REPO,
        "filename": PINKCHERRY_INT8,
        "subdir": "diffusion_models",
    },
    {
        "repo_id": "Comfy-Org/MiniMax-H3",
        "filename": "vae/minimax_h3_video_vae_fp16.safetensors",
        "subdir": "vae",
    },
    {
        "repo_id": "Comfy-Org/MiniMax-H3",
        "filename": "vae/minimax_h3_audio_vae_fp32.safetensors",
        "subdir": "vae",
    },
    {
        "repo_id": "t8star/Taeh3-Comfy",
        "filename": "models/vae_approx/taeh3.safetensors",
        "subdir": "vae_approx",
    },
    {
        "repo_id": "t8star/Taeh3-Comfy",
        "filename": "models/vae_approx/taeh3_2d_kijai.safetensors",
        "subdir": "vae_approx",
    },
    {
        "repo_id": "LBH-123-AI/Minimax_h3_latent_Upscaler",
        "filename": "minimax_h3_latent_upscaler_3d_conv_v1_bf16.safetensors",
        "subdir": "latent_upscale_models",
    },
    {
        "repo_id": "Comfy-Org/MiniMax-H3",
        "filename": "text_encoders/qwen3vl_32b_minimax_h3_int8_convrot.safetensors",
        "subdir": "text_encoders",
    },
    {
        "repo_id": "Comfy-Org/MiniMax-H3",
        "filename": "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "subdir": "text_encoders",
    },
    {
        "repo_id": "Comfy-Org/MiniMax-H3",
        "filename": "loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
        "subdir": "loras",
    },
    {
        "repo_id": "Comfy-Org/MiniMax-H3",
        "filename": "loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
        "subdir": "loras",
    },
    {
        "repo_id": "Comfy-Org/MiniMax-H3",
        "filename": "embeddings/minimaxh3_art_is_explosion.safetensors",
        "subdir": "embeddings",
    },
]

app = modal.App(APP_NAME)
vol = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)

# Container image with CUDA devel toolchain (for llama.cpp native CUDA + Flash Attention)
# plus ComfyUI + KJNodes + VideoHelperSuite + ComfyUI-Manager + SageAttention
image = (
    modal.Image.from_registry(
        "nvidia/cuda:12.4.1-devel-ubuntu22.04",
        add_python="3.11",
    )
    .apt_install(
        "git",
        "cmake",
        "build-essential",
        "ffmpeg",
        "aria2",
        "curl",
        "wget",
        "libgl1",
        "libglib2.0-0",
    )
    .pip_install(
        "torch>=2.4.0",
        "torchvision",
        "torchaudio",
        "huggingface_hub[hf_transfer]>=0.26.0",
        "safetensors",
        "accelerate",
        "transformers>=4.46.0",
        "sentencepiece",
        "einops",
        "scipy",
        "aiohttp",
        "fastapi",
        "uvicorn",
        "sageattention",
    )
    .run_commands(
        # 1. Compile & Install llama-cli and llama-server (Native CUDA + Flash Attention) — 3.ipynb Section 1
        "git clone --depth 1 https://github.com/ggerganov/llama.cpp /opt/llama.cpp",
        "cmake -B /opt/llama.cpp/build -S /opt/llama.cpp "
        "-DGGML_CUDA=ON "
        "-DCMAKE_CUDA_ARCHITECTURES='80;90' "
        "-DGGML_CUDA_FA_QUANTS=all "
        "-DGGML_CCACHE=OFF "
        "-DBUILD_SHARED_LIBS=OFF "
        "-DCMAKE_BUILD_TYPE=Release",
        "cmake --build /opt/llama.cpp/build --config Release -j$(nproc) "
        "--target llama-cli llama-server llama-bench llama-quantize",
        "cp /opt/llama.cpp/build/bin/llama-cli "
        "/opt/llama.cpp/build/bin/llama-server "
        "/opt/llama.cpp/build/bin/llama-bench "
        "/opt/llama.cpp/build/bin/llama-quantize /usr/local/bin/",
        # 2. Clone ComfyUI & Required Custom Nodes (KJNodes, VideoHelperSuite, ComfyUI-Manager) — 3.ipynb Section 6
        "git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git /root/ComfyUI",
        "pip install -r /root/ComfyUI/requirements.txt",
        "git clone --depth 1 https://github.com/kijai/ComfyUI-KJNodes.git "
        "/root/ComfyUI/custom_nodes/ComfyUI-KJNodes",
        "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-KJNodes/requirements.txt || true",
        "git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git "
        "/root/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite",
        "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-VideoHelperSuite/requirements.txt || true",
        "git clone --depth 1 https://github.com/ltdrdata/ComfyUI-Manager.git "
        "/root/ComfyUI/custom_nodes/ComfyUI-Manager",
        "pip install -r /root/ComfyUI/custom_nodes/ComfyUI-Manager/requirements.txt || true",
    )
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "GGML_CUDA_P2P": "1",
            "HF_HOME": f"{MODEL_MOUNT_PATH}/hf_cache",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        }
    )
)


def _ensure_symlink(target_path: Path, link_path: Path) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    if not link_path.exists():
        if link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(target_path)


def _download_flat(repo_id: str, filename: str, target_dir: Path, hf_token: str | None = None) -> Path:
    from huggingface_hub import hf_hub_download

    target_dir.mkdir(parents=True, exist_ok=True)
    basename = os.path.basename(filename)
    dest_path = target_dir / basename
    if dest_path.exists() and dest_path.stat().st_size > 0:
        print(f"✓ Already present: {dest_path}")
        return dest_path
    print(f"Downloading {filename} from {repo_id} -> {dest_path}...")
    cache_dir = Path(MODEL_MOUNT_PATH) / "hf_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    downloaded = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=str(cache_dir),
        token=hf_token,
    )
    shutil.move(downloaded, str(dest_path))
    return dest_path


def _wire_comfy_volume_layout(base_models: Path, input_dir: Path, workflow_dir: Path) -> None:
    """Create all symlinks, sample inputs, and patched workflows exactly as in 3.ipynb Section 6."""
    for sub in [
        "diffusion_models",
        "checkpoints",
        "vae",
        "vae_approx",
        "text_encoders",
        "loras",
        "embeddings",
        "latent_upscale_models",
    ]:
        (base_models / sub).mkdir(parents=True, exist_ok=True)

    diff_dir = base_models / "diffusion_models"
    pinkcherry_bf16 = diff_dir / "PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors"
    pinkcherry_int8 = diff_dir / "PinkCherry_hybrid_v1.8_int8_minimax_h3_pruned.safetensors"

    if pinkcherry_bf16.exists():
        _ensure_symlink(pinkcherry_bf16, base_models / "checkpoints" / pinkcherry_bf16.name)
        _ensure_symlink(pinkcherry_bf16, diff_dir / "minimax_h3_fl2va_int8_convrot.safetensors")
        _ensure_symlink(pinkcherry_bf16, diff_dir / "minimax_h3_fl2va_pruned_int8_convrot.safetensors")
        _ensure_symlink(pinkcherry_bf16, diff_dir / "minimax_h3_ref2va_pruned_int8_convrot.safetensors")
    if pinkcherry_int8.exists():
        _ensure_symlink(pinkcherry_int8, diff_dir / "PinkCherry_hybrid_v1.8_int8_minimax_h3.safetensors")

    lora_dir = base_models / "loras"
    lora_8step = lora_dir / "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
    if lora_8step.exists():
        _ensure_symlink(lora_8step, lora_dir / "MiniMaxh3 Turbo" / lora_8step.name)

    sample_mp4 = input_dir / "Test__00347-audio.mp4"
    if sample_mp4.exists():
        for vid_alias in [
            "3e785606-83ea-4a5f-8dde-437d60f41b71.mp4",
            "ref_clip.mp4",
            "source.mp4",
            "tail_22frames.mp4",
        ]:
            _ensure_symlink(sample_mp4, input_dir / vid_alias)
        for img_name in [
            "49697335_091_3b3d.jpg",
            "Krea2__00319_.png",
            "0027.jpg",
            "ref_1.png",
            "ref_2.png",
        ]:
            img_dest = input_dir / img_name
            if not img_dest.exists():
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(sample_mp4), "-frames:v", "1", str(img_dest)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )


@app.function(
    image=image,
    volumes={MODEL_MOUNT_PATH: vol},
    timeout=7200,
    cpu=8.0,
    memory=32768,
)
def stage_weights_v2(include_bf16_cognition: bool = False) -> Dict[str, Any]:
    """
    Stages every model, symlink, sample input, and patched workflow from `3.ipynb`
    into the persistent `keystone-models-vol` Modal Volume:
      1. `OBLITERATUS/Qwen3.8-27B-OBLITERATED` (`Qwen3.8-27B-OBLITERATED-Q8_0.gguf` in `/models/models/`)
      2. All 12 ComfyUI safetensor files across `diffusion_models`, `vae`, `vae_approx`,
         `latent_upscale_models`, `text_encoders`, `loras`, and `embeddings`
      3. Sample reference audio/video (`Test__00347-audio.mp4`) + frame/clip aliases
      4. Patched PinkCherry 1.8 & 1.5 workflows
    """
    from huggingface_hub import snapshot_download

    hf_token = os.environ.get("HF_TOKEN") or None
    staged: Dict[str, Any] = {
        "cognition_gguf": None,
        "cognition_bf16": None,
        "comfyui_safetensors": {},
        "workflows": [],
    }

    # 1. Pull OBLITERATUS/Qwen3.8-27B-OBLITERATED (3.ipynb Cell `pull_model`)
    cognition_dir = Path(MODEL_MOUNT_PATH) / "models"
    cognition_dir.mkdir(parents=True, exist_ok=True)
    gguf_path = _download_flat(COGNITION_REPO, COGNITION_GGUF, cognition_dir, hf_token=hf_token)
    staged["cognition_gguf"] = str(gguf_path)

    if include_bf16_cognition:
        bf16_dir = Path(MODEL_MOUNT_PATH) / "cognition" / "qwen3.8-27b-obliterated-bf16"
        bf16_dir.mkdir(parents=True, exist_ok=True)
        snapshot_download(
            repo_id=COGNITION_REPO,
            local_dir=str(bf16_dir),
            allow_patterns=["*.safetensors", "*.json", "*.model", "tokenizer*"],
            ignore_patterns=["*.gguf", "*.bin"],
            token=hf_token,
        )
        staged["cognition_bf16"] = str(bf16_dir)

    # 2. Pull all ComfyUI safetensors (3.ipynb Cell `fe2cb246`)
    base_models = Path(MODEL_MOUNT_PATH) / "comfyui_models"
    for item in COMFY_SAFETENSOR_ASSETS:
        target_dir = base_models / item["subdir"]
        dest = _download_flat(item["repo_id"], item["filename"], target_dir, hf_token=hf_token)
        staged["comfyui_safetensors"][os.path.basename(item["filename"])] = str(dest)

    # 3. Sample reference inputs
    input_dir = Path(MODEL_MOUNT_PATH) / "comfyui_input"
    input_dir.mkdir(parents=True, exist_ok=True)
    _download_flat(PINKCHERRY_REPO, "1.8-hybrid/Test__00347-audio.mp4", input_dir, hf_token=hf_token)

    # 4. Download & patch workflows (3.ipynb Section 6 Step 7)
    workflow_dir = Path(MODEL_MOUNT_PATH) / "comfyui_workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)
    for wf in [
        "1.8-hybrid/PinkCherry_ref2va_turbo_lightx2v_workflow.json",
        "v1.5-fl2va/MiniMaxH3_PinkCherryV15_Fla2va_wTurbo.json",
    ]:
        wf_path = _download_flat(PINKCHERRY_REPO, wf, workflow_dir, hf_token=hf_token)
        wf_text = wf_path.read_text(encoding="utf-8")
        wf_text = wf_text.replace(
            "MiniMaxh3 Turbo\\minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
            "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
        )
        wf_text = wf_text.replace(
            "PinkCherry_hybrid_v1.8_int8_minimax_h3.safetensors",
            "PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors",
        )
        wf_text = wf_text.replace(
            "minimax_h3_fl2va_int8_convrot.safetensors",
            "PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors",
        )
        wf_text = wf_text.replace(
            "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
            "PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors",
        )
        wf_text = wf_text.replace("REf2va\\TEST_", "REf2va/TEST_")
        wf_text = wf_text.replace("MiniMaxH3_BaseLora\\Test_", "MiniMaxH3_BaseLora/Test_")
        wf_data = json.loads(wf_text)
        if "MiniMaxH3_PinkCherryV15" in str(wf_path) and not any(
            l[0] == 391 for l in wf_data.get("links", [])
        ):
            wf_data["links"].append([391, 168, 0, 119, 0, "IMAGE"])
            for n in wf_data.get("nodes", []):
                if n["id"] == 168 and 391 not in n["outputs"][0]["links"]:
                    n["outputs"][0]["links"].append(391)
                elif n["id"] == 119:
                    n["inputs"][0]["link"] = 391
            wf_data["last_link_id"] = max(wf_data.get("last_link_id", 390), 391)
        wf_path.write_text(json.dumps(wf_data, indent=2), encoding="utf-8")
        staged["workflows"].append(str(wf_path))

    # 5. Wire symlinks and sample frame aliases
    _wire_comfy_volume_layout(base_models, input_dir, workflow_dir)

    # Clean temporary hf_cache inside volume
    shutil.rmtree(Path(MODEL_MOUNT_PATH) / "hf_cache", ignore_errors=True)
    vol.commit()
    return staged


@app.function(
    image=image,
    gpu="A100-80GB",
    volumes={MODEL_MOUNT_PATH: vol},
    scaledown_window=600,
    timeout=3600,
)
@modal.concurrent(max_inputs=16)
@modal.web_server(port=8081, startup_timeout=600)
def cognition_llama_server() -> None:
    """
    Launches `llama-server` on Port 8081 with the exact `LLAMA_CONFIG` from `3.ipynb` Section 5:
      `llama-server -m /models/models/Qwen3.8-27B-OBLITERATED-Q8_0.gguf`
      `--alias OBLITERATUS/Qwen3.8-27B-OBLITERATED:fastest`
      `--host 0.0.0.0 --port 8081 --api-key keystone-live-key --metrics --slots`
      `-ngl 999 --flash-attn on -c 32768 -ctk q8_0 -ctv q8_0 -b 2048 -ub 2048 -np 16`
      `--cont-batching --jinja --temp 0.2 --min-p 0.05 --repeat-penalty 1.05`
    """
    model_path = Path(MODEL_MOUNT_PATH) / "models" / COGNITION_GGUF
    if not model_path.exists():
        _download_flat(COGNITION_REPO, COGNITION_GGUF, model_path.parent)
        vol.commit()

    cmd = [
        "llama-server",
        "-m",
        str(model_path),
        "--alias",
        COGNITION_ALIAS,
        "--host",
        "0.0.0.0",
        "--port",
        "8081",
        "--api-key",
        COGNITION_API_KEY,
        "--metrics",
        "--slots",
    ] + build_llama_flags(LLAMA_CONFIG)

    subprocess.Popen(cmd)


@app.function(
    image=image,
    gpu="A100-80GB",
    volumes={MODEL_MOUNT_PATH: vol},
    scaledown_window=600,
    timeout=3600,
)
@modal.concurrent(max_inputs=8)
@modal.web_server(port=8188, startup_timeout=600)
def creative_comfyui_server() -> None:
    """
    Launches ComfyUI on Port 8188 with all 12 PinkCherry 1.8 / MiniMax-H3 safetensors,
    symlinks, sample reference inputs, and patched workflows from `3.ipynb` Sections 6 & 7.
    """
    base_models = Path(MODEL_MOUNT_PATH) / "comfyui_models"
    input_dir = Path(MODEL_MOUNT_PATH) / "comfyui_input"
    workflow_dir = Path(MODEL_MOUNT_PATH) / "comfyui_workflows"

    _wire_comfy_volume_layout(base_models, input_dir, workflow_dir)

    # Link volume directories into /root/ComfyUI
    comfy_root = Path("/root/ComfyUI")
    for sub in [
        "diffusion_models",
        "checkpoints",
        "vae",
        "vae_approx",
        "text_encoders",
        "loras",
        "embeddings",
        "latent_upscale_models",
    ]:
        src = base_models / sub
        dst = comfy_root / "models" / sub
        if dst.exists() or dst.is_symlink():
            shutil.rmtree(dst, ignore_errors=True)
            if dst.is_symlink():
                dst.unlink()
        dst.symlink_to(src)

    comfy_input = comfy_root / "input"
    if comfy_input.exists() or comfy_input.is_symlink():
        shutil.rmtree(comfy_input, ignore_errors=True)
        if comfy_input.is_symlink():
            comfy_input.unlink()
    comfy_input.symlink_to(input_dir)

    comfy_wf = comfy_root / "user" / "default" / "workflows"
    comfy_wf.parent.mkdir(parents=True, exist_ok=True)
    if comfy_wf.exists() or comfy_wf.is_symlink():
        shutil.rmtree(comfy_wf, ignore_errors=True)
        if comfy_wf.is_symlink():
            comfy_wf.unlink()
    comfy_wf.symlink_to(workflow_dir)

    cmd = [
        "python3",
        "main.py",
        "--listen",
        "0.0.0.0",
        "--port",
        "8188",
    ]
    subprocess.Popen(cmd, cwd="/root/ComfyUI")


@app.local_entrypoint()
def main() -> None:
    print(f"Staging all 3.ipynb weights into Modal volume '{VOLUME_NAME}'...")
    res = stage_weights_v2.remote()
    print("Staged assets:", json.dumps(res, indent=2))
