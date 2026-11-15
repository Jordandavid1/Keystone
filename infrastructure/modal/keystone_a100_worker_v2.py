"""KEYSTONE Modal A100-80GB Worker — Iteration v2 (Ephemeral Clean-Boot).

Additive iteration that preserves ``keystone_a100_worker.py``, ``.env``, and
``.venv`` untouched. On every container wake-up, transient runtime directories
(``/tmp``, ComfyUI ``input``/``output``/``temp``) are wiped cleanly while
read-only weights remain cached in ``keystone-models-vol`` at ``/models``.
"""

from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys

import modal

_CURRENT_DIR = pathlib.Path(__file__).resolve().parent
for _candidate in (str(_CURRENT_DIR), "/root"):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from keystone_a100_worker import (  # noqa: E402
    COGNITION_ALIAS,
    COGNITION_MODEL_ID,
    COMFY_DIR,
    GPU_SPEC,
    MODELS_ROOT,
    PINKCHERRY_SUBPATH,
    SYSTEM_RAM_MB,
    _stage_comfy_assets,
    image as _base_image,
    models_volume,
)

APP_NAME = "keystone-a100-worker-v2"
EPHEMERAL_CLEAN_BOOT = True

image = _base_image.add_local_file(
    _CURRENT_DIR / "keystone_a100_worker.py",
    "/root/keystone_a100_worker.py",
)

app = modal.App(APP_NAME, image=image)


def _clean_dir_contents(directory: pathlib.Path) -> None:
    """Best-effort wipe of transient files inside ``directory`` without removing it."""
    if not directory.exists():
        return
    for entry in directory.iterdir():
        try:
            if entry.is_symlink() or entry.is_file():
                entry.unlink(missing_ok=True)
            elif entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
        except OSError:
            pass


def _ephemeral_clean_reset() -> None:
    """Reset transient container state on wake-up so every session boots fresh."""
    if not EPHEMERAL_CLEAN_BOOT:
        return
    for transient_dir in (
        pathlib.Path("/tmp"),
        COMFY_DIR / "input",
        COMFY_DIR / "output",
        COMFY_DIR / "temp",
    ):
        _clean_dir_contents(transient_dir)


@app.function(
    gpu=GPU_SPEC,
    memory=SYSTEM_RAM_MB,
    volumes={str(MODELS_ROOT): models_volume},
    timeout=3600,
)
def stage_weights_v2(hf_token: str | None = None) -> dict[str, str]:
    """Stage ComfyUI and Qwen 3.8 weights into ``keystone-models-vol``."""
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
        "app": APP_NAME,
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
    """Serve clean-boot ephemeral ComfyUI on port 8188 with 5-minute idle scale-down."""
    _ephemeral_clean_reset()
    _stage_comfy_assets(os.environ.get("HF_TOKEN") or None)
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
    """Serve clean-boot ephemeral Huihui-Qwen3.8-27B-abliterated (BF16) via vLLM."""
    _ephemeral_clean_reset()
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
    """Stage weights into the persistent volume when invoked via ``modal run``."""
    print(stage_weights_v2.remote(os.environ.get("HF_TOKEN") or None))
