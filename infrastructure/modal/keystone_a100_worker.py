"""KEYSTONE Modal A100-80GB remote worker for ComfyUI and Qwen 3.8 cognition.

Matches the Colab G4 High-RAM profile (80 GB VRAM, 180 GB system RAM) with
persistent volume caching at ``/models`` and 5-minute scale-to-zero idle windows.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

import modal

APP_NAME = "keystone-a100-worker"
GPU_SPEC = "A100-80GB"
SYSTEM_RAM_MB = 184320  # 180 GiB host RAM
COMFY_DIR = pathlib.Path("/opt/ComfyUI")
MODELS_ROOT = pathlib.Path("/models")

PINKCHERRY_REPO = "SexGod1979/PinkCherry-NSFW_MiniMax-H3"
PINKCHERRY_BF16_FILE = "PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors"
PINKCHERRY_SUBPATH = f"1.8-hybrid/{PINKCHERRY_BF16_FILE}"
MINIMAX_REPO = "Comfy-Org/MiniMax-H3"
COGNITION_MODEL_ID = "huihui-ai/Huihui-Qwen3.8-27B-abliterated"
COGNITION_ALIAS = "huihui-qwen3.8-abliterated"

# (remote_repo_path, relative_path_under_comfy_models)
MINIMAX_COMPANION_ASSETS: tuple[tuple[str, str], ...] = (
    (
        "split_files/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
        "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    ),
    (
        "split_files/vae/minimax_h3_video_vae_fp16.safetensors",
        "vae/minimax_h3_video_vae_fp16.safetensors",
    ),
    (
        "split_files/vae/minimax_h3_audio_vae_fp32.safetensors",
        "vae/minimax_h3_audio_vae_fp32.safetensors",
    ),
    (
        "split_files/loras/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
        "loras/MiniMaxh3 Turbo/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors",
    ),
    (
        "split_files/loras/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
        "loras/MiniMaxh3 Turbo/minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
    ),
)

CUSTOM_NODE_REPOS: tuple[tuple[str, str], ...] = (
    ("ComfyUI-KJNodes", "https://github.com/kijai/ComfyUI-KJNodes.git"),
    ("ComfyUI-VideoHelperSuite", "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git"),
)

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("git", "ffmpeg", "aria2", "libgl1", "libglib2.0-0")
    .pip_install(
        "torch",
        "torchvision",
        "torchaudio",
        "vllm",
        "huggingface_hub[hf_transfer]",
        "safetensors",
        "accelerate",
        "einops",
        "librosa",
        "soundfile",
        "gguf",
    )
    .run_commands(
        f"git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git {COMFY_DIR}",
        f"pip install --no-cache-dir -r {COMFY_DIR}/requirements.txt",
        *[
            cmd
            for name, url in CUSTOM_NODE_REPOS
            for cmd in (
                f"git clone --depth 1 {url} {COMFY_DIR}/custom_nodes/{name}",
                f"if [ -f {COMFY_DIR}/custom_nodes/{name}/requirements.txt ]; then pip install --no-cache-dir -r {COMFY_DIR}/custom_nodes/{name}/requirements.txt; fi",
            )
        ],
    )
    .env(
        {
            "HF_HUB_ENABLE_HF_TRANSFER": "1",
            "HF_HOME": f"{MODELS_ROOT}/hf_cache",
            "PYTORCH_CUDA_ALLOC_CONF": "expandable_segments:True",
        }
    )
)

app = modal.App(APP_NAME, image=image)
models_volume = modal.Volume.from_name("keystone-models-vol", create_if_missing=True)


def _ensure_symlink(source: pathlib.Path, target: pathlib.Path) -> None:
    """Create or refresh a symlink at ``target`` pointing to ``source``."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink() or target.exists():
        if target.is_symlink() and target.resolve() == source.resolve():
            return
        target.unlink()
    target.symlink_to(source)


def _link_volume_models_into_comfy() -> None:
    """Expose staged weights from ``/models/comfyui`` inside ``/opt/ComfyUI/models``."""
    staged_root = MODELS_ROOT / "comfyui"
    if not staged_root.exists():
        return
    for item in staged_root.rglob("*.safetensors"):
        rel = item.relative_to(staged_root)
        _ensure_symlink(item, COMFY_DIR / "models" / rel)


def _stage_comfy_assets(hf_token: str | None = None) -> None:
    """Download PinkCherry BF16 and MiniMax H3 companion weights into ``/models``."""
    from huggingface_hub import hf_hub_download

    comfy_cache = MODELS_ROOT / "comfyui"
    hf_stage = MODELS_ROOT / "_hf_stage"
    comfy_cache.mkdir(parents=True, exist_ok=True)
    hf_stage.mkdir(parents=True, exist_ok=True)

    ckpt_target = comfy_cache / "checkpoints" / PINKCHERRY_SUBPATH
    if not (ckpt_target.exists() and ckpt_target.stat().st_size > 1_000_000_000):
        ckpt_target.parent.mkdir(parents=True, exist_ok=True)
        downloaded = pathlib.Path(
            hf_hub_download(
                repo_id=PINKCHERRY_REPO,
                filename=PINKCHERRY_SUBPATH,
                local_dir=str(hf_stage / "pinkcherry"),
                token=hf_token,
            )
        ).resolve()
        _ensure_symlink(downloaded, ckpt_target)

    # Mirror into diffusion_models/ so both UNETLoader and CheckpointLoaderSimple resolve it.
    _ensure_symlink(ckpt_target.resolve(), comfy_cache / "diffusion_models" / PINKCHERRY_BF16_FILE)
    _ensure_symlink(
        ckpt_target.resolve(),
        comfy_cache / "diffusion_models" / "1.8-hybrid" / PINKCHERRY_BF16_FILE,
    )

    for remote_rel, comfy_rel in MINIMAX_COMPANION_ASSETS:
        dest = comfy_cache / comfy_rel
        if dest.exists() and dest.stat().st_size > 1_000_000:
            continue
        downloaded = pathlib.Path(
            hf_hub_download(
                repo_id=MINIMAX_REPO,
                filename=remote_rel,
                local_dir=str(hf_stage / "minimax_h3"),
                token=hf_token,
            )
        ).resolve()
        _ensure_symlink(downloaded, dest)

    _link_volume_models_into_comfy()


@app.function(
    gpu=GPU_SPEC,
    memory=SYSTEM_RAM_MB,
    volumes={str(MODELS_ROOT): models_volume},
    timeout=3600,
)
def stage_weights(hf_token: str | None = None) -> dict[str, str]:
    """Download all ComfyUI + Qwen 3.8 weights into the persistent ``keystone-models-vol``."""
    from huggingface_hub import snapshot_download

    token = hf_token or os.environ.get("HF_TOKEN") or None
    _stage_comfy_assets(token)
    snapshot_download(
        repo_id=COGNITION_MODEL_ID,
        local_dir=str(MODELS_ROOT / "qwen3_8_27b"),
        token=token,
    )
    models_volume.commit()
    return {
        "status": "staged",
        "volume": "keystone-models-vol",
        "comfy_checkpoint": PINKCHERRY_SUBPATH,
        "cognition_model": COGNITION_MODEL_ID,
    }


@app.function(
    gpu=GPU_SPEC,
    memory=SYSTEM_RAM_MB,
    volumes={str(MODELS_ROOT): models_volume},
    scaledown_window=300,
    timeout=3600,
)
@modal.web_server(8188, startup_timeout=300)
def comfyui_server() -> None:
    """Serve headless ComfyUI on port 8188 using full VRAM with 5-minute idle scale-down."""
    _stage_comfy_assets(os.environ.get("HF_TOKEN") or None)
    models_volume.commit()
    subprocess.Popen(
        [
            sys.executable,
            "main.py",
            "--listen",
            "0.0.0.0",
            "--port",
            "8188",
            "--normalvram",
        ],
        cwd=str(COMFY_DIR),
    )


@app.function(
    gpu=GPU_SPEC,
    memory=SYSTEM_RAM_MB,
    volumes={str(MODELS_ROOT): models_volume},
    scaledown_window=300,
    timeout=3600,
)
@modal.web_server(8000, startup_timeout=300)
def cognition_server() -> None:
    """Serve Huihui-Qwen3.8-27B-abliterated (BF16) via vLLM on port 8000."""
    local_model_dir = MODELS_ROOT / "qwen3_8_27b"
    model_ref = str(local_model_dir) if (local_model_dir / "config.json").exists() else COGNITION_MODEL_ID
    api_key = os.environ.get("KEYSTONE_API_KEY", "keystone-live-key")
    subprocess.Popen(
        [
            sys.executable,
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--model",
            model_ref,
            "--served-model-name",
            COGNITION_MODEL_ID,
            COGNITION_ALIAS,
            "--api-key",
            api_key,
            "--dtype",
            "bfloat16",
            "--tensor-parallel-size",
            "1",
            "--gpu-memory-utilization",
            "0.90",
            "--max-model-len",
            "8192",
            "--trust-remote-code",
            "--port",
            "8000",
        ]
    )


@app.local_entrypoint()
def main() -> None:
    """Stage weights into the persistent Modal volume when invoked via ``modal run``."""
    result = stage_weights.remote(os.environ.get("HF_TOKEN") or None)
    print(result)
