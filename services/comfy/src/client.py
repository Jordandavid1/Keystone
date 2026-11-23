"""
KEYSTONE ComfyUI Execution Client (Bible §8, §23).

Speaks the ComfyUI HTTP API directly: submit a node graph to /prompt, poll
/history/{prompt_id} until it finishes, then download the rendered image from
/view. Works against a local daemon (http://127.0.0.1:8188) or the ephemeral
Kaggle tunnel exposed by KAGGLE_SETUP/03_keystone_integrated_gateway.ipynb.

Configuration (environment, falling back to the repository .env file):
  COMFY_BASE_URL        e.g. https://random-words.trycloudflare.com  (required)
  COMFY_CHECKPOINT      checkpoint filename inside ComfyUI/models/checkpoints
  COMFY_BASIC_AUTH      optional "user:password" for tunnelled deployments
  COMFY_TIMEOUT_SECONDS generation budget, default 240
"""

from __future__ import annotations

import base64
from copy import deepcopy
import json
import os
import random
import tempfile
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from services.comfy.src.grade import apply_grade, is_neutral_grade
from services.comfy.src.video_ops import (
    VideoOpsError,
    encode_frames_to_video,
    extract_last_frame,
    extract_video_frames,
    probe_video_metadata,
    stitch_video_segments,
)

DEFAULT_CHECKPOINT = "sd_xl_base_1.0.safetensors"
DEFAULT_NEGATIVE_PROMPT = (
    "text, watermark, logo, blurred, low quality, deformed, extra limbs"
)
_ENV_LOADED = False


class ComfyUIError(RuntimeError):
    """Raised when ComfyUI rejects a graph or fails to produce an image."""


class ComfyUINotConfigured(ComfyUIError):
    """Raised when COMFY_BASE_URL is absent, i.e. no runtime is wired up yet."""


def _load_repo_env() -> None:
    """Loads KEY=VALUE pairs from .env in dist/, cwd, or repository root dynamically."""
    try:
        from services.cognition.src.client import load_keystone_dotenv
        load_keystone_dotenv()
    except Exception:
        pass
    env_path = Path(__file__).resolve().parents[3] / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def _normalize_comfy_url(url: str) -> str:
    clean = (url or "").strip().rstrip("/")
    if clean.endswith("/v1"):
        clean = clean[:-3].rstrip("/")
    return clean


def comfy_base_url() -> str:
    _load_repo_env()
    env_url = _normalize_comfy_url(
        os.getenv("COMFY_BASE_URL", "")
        or os.getenv("KEYSTONE_COMFY_URL", "")
        or os.getenv("KAGGLE_COMFYUI_TUNNEL", "")
    )
    if env_url:
        return env_url
    try:
        from services.harness.src.worker_bridge import worker_bridge
        for cap in ("image.generation", "comfyui", "creative.generation"):
            matched = worker_bridge.route_for_capability(cap)
            if matched:
                return _normalize_comfy_url(matched[0].tunnel_url)
        for worker in worker_bridge.list_workers(active_only=True):
            if any(k in str(worker.get("worker_type", "")).lower() for k in ("creative", "comfy", "gateway")):
                return _normalize_comfy_url(str(worker["tunnel_url"]))
    except Exception:
        pass
    return ""


def comfy_bearer_token() -> str:
    _load_repo_env()
    return (
        os.getenv("KEYSTONE_COMFY_API_KEY", "").strip()
        or os.getenv("COMFY_BEARER_TOKEN", "").strip()
        or os.getenv("COMFY_API_KEY", "").strip()
        or os.getenv("OPENAI_API_KEY", "").strip()
        or os.getenv("COGNITION_API_KEY", "").strip()
    )



def comfy_checkpoint() -> str:
    _load_repo_env()
    return os.getenv("COMFY_CHECKPOINT", DEFAULT_CHECKPOINT)


def comfy_timeout() -> float:
    _load_repo_env()
    try:
        return float(os.getenv("COMFY_TIMEOUT_SECONDS", "240"))
    except ValueError:
        return 240.0


def is_configured() -> bool:
    return bool(comfy_base_url())


def _request(
    path: str,
    *,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    raw: bool = False,
) -> Tuple[int, Any]:
    base = comfy_base_url()
    if not base:
        raise ComfyUINotConfigured(
            "COMFY_NOT_CONFIGURED: set COMFY_BASE_URL to a running ComfyUI instance"
        )

    url = f"{base}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Accept", "application/json")
    req.add_header("User-Agent", "Keystone/2.0")
    if data is not None:
        req.add_header("Content-Type", "application/json")

    _load_repo_env()
    basic = os.getenv("COMFY_BASIC_AUTH", "").strip()
    if basic:
        token = base64.b64encode(basic.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")
    else:
        bearer = comfy_bearer_token()
        if bearer:
            req.add_header("Authorization", f"Bearer {bearer}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            if raw:
                return resp.status, body
            return resp.status, json.loads(body or b"{}")
    except urllib.error.HTTPError as err:
        detail = err.read().decode("utf-8", errors="replace")[:600]
        raise ComfyUIError(f"COMFY_HTTP_{err.code}: {detail}") from err
    except urllib.error.URLError as err:
        raise ComfyUIError(
            f"COMFY_UNREACHABLE: {base} ({err.reason}). "
            "Confirm the ComfyUI daemon or tunnel is running."
        ) from err


def system_stats() -> Dict[str, Any]:
    """Health probe used by the workspace to show whether ComfyUI is reachable."""
    _, body = _request("/system_stats")
    return body if isinstance(body, dict) else {}


def build_sdxl_graph(
    prompt: str,
    *,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    cfg: float = 6.0,
    seed: Optional[int] = None,
    checkpoint: Optional[str] = None,
) -> Dict[str, Any]:
    """Standard SDXL text-to-image graph: checkpoint -> CLIP -> KSampler -> VAE."""
    ckpt = checkpoint or comfy_checkpoint()
    resolved_seed = seed if seed is not None else random.randint(0, 2**32 - 1)
    return {
        "1": {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ckpt},
        },
        "2": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": prompt, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": negative_prompt, "clip": ["1", 1]},
        },
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": width, "height": height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
                "seed": resolved_seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": 1.0,
            },
        },
        "6": {
            "class_type": "VAEDecode",
            "inputs": {"samples": ["5", 0], "vae": ["1", 2]},
        },
        "7": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "keystone", "images": ["6", 0]},
        },
    }


def submit_graph(graph: Dict[str, Any]) -> str:
    """Queues a graph and returns the ComfyUI prompt_id."""
    payload = {
        "prompt": graph,
        "client_id": f"keystone-{int(time.time())}",
    }
    _, body = _request("/prompt", method="POST", payload=payload)
    prompt_id = (body or {}).get("prompt_id")
    if not prompt_id:
        raise ComfyUIError(f"COMFY_REJECTED: no prompt_id returned ({body})")
    return str(prompt_id)


def wait_for_result(prompt_id: str, timeout: Optional[float] = None) -> Dict[str, Any]:
    """Polls /history until the prompt completes, then returns its outputs."""
    deadline = time.time() + (timeout if timeout is not None else comfy_timeout())
    while time.time() < deadline:
        _, history = _request(f"/history/{urllib.parse.quote(prompt_id)}")
        entry = (history or {}).get(prompt_id)
        if entry:
            status = entry.get("status", {})
            if status.get("status_str") == "error" or status.get("completed") is False:
                raise ComfyUIError(
                    f"COMFY_EXECUTION_FAILED: {json.dumps(status)[:600]}"
                )
            outputs = entry.get("outputs") or {}
            if outputs:
                return outputs
        time.sleep(2.0)
    raise ComfyUIError(
        f"COMFY_TIMEOUT: prompt {prompt_id} did not finish within the budget"
    )


def fetch_image(image_ref: Dict[str, Any]) -> Tuple[bytes, str]:
    """Downloads a rendered image from /view and returns (bytes, mime_type)."""
    query = urllib.parse.urlencode(
        {
            "filename": image_ref.get("filename", ""),
            "subfolder": image_ref.get("subfolder", ""),
            "type": image_ref.get("type", "output"),
        }
    )
    _, body = _request(f"/view?{query}", raw=True)
    if not body:
        raise ComfyUIError("COMFY_EMPTY_IMAGE: /view returned no bytes")
    filename = str(image_ref.get("filename", "")).lower()
    mime = "image/png"
    if filename.endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
    elif filename.endswith(".webp"):
        mime = "image/webp"
    return body, mime


def upload_image_to_comfy(image_bytes: bytes, filename: Optional[str] = None) -> str:
    """Uploads binary reference media to ComfyUI's /upload/image endpoint using multipart/form-data."""
    base = comfy_base_url()
    if not base:
        raise ComfyUINotConfigured(
            "COMFY_NOT_CONFIGURED: cannot upload reference media because COMFY_BASE_URL is not configured"
        )
    safe_fname = os.path.basename(filename or "") or f"upload_{uuid.uuid4().hex[:12]}.png"
    boundary = f"----KeystoneBoundary{int(time.time()*1000)}"
    body = bytearray()
    # Form field 'overwrite'
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n".encode("utf-8"))
    # File field 'image'
    lower_name = safe_fname.lower()
    if lower_name.endswith(".png"):
        mime = "image/png"
    elif lower_name.endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
    elif lower_name.endswith(".webp"):
        mime = "image/webp"
    elif lower_name.endswith(".wav"):
        mime = "audio/wav"
    elif lower_name.endswith(".mp3"):
        mime = "audio/mpeg"
    elif lower_name.endswith(".mp4"):
        mime = "video/mp4"
    else:
        mime = "application/octet-stream"
    body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{safe_fname}\"\r\nContent-Type: {mime}\r\n\r\n".encode("utf-8"))
    body.extend(image_bytes)
    body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(f"{base}/upload/image", data=bytes(body), method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    req.add_header("User-Agent", "Keystone/2.0")
    _load_repo_env()
    basic = os.getenv("COMFY_BASIC_AUTH", "").strip()
    if basic:
        token = base64.b64encode(basic.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")
    else:
        bearer = comfy_bearer_token()
        if bearer:
            req.add_header("Authorization", f"Bearer {bearer}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
            uploaded_name = data.get("name")
            if not uploaded_name:
                raise ComfyUIError(f"COMFY_UPLOAD_INVALID_RESPONSE: missing 'name' in /upload/image response ({data})")
            return str(uploaded_name)
    except ComfyUIError:
        raise
    except Exception as exc:
        raise ComfyUIError(f"COMFY_UPLOAD_FAILED: {type(exc).__name__}: {exc}") from exc


def build_img2img_graph(
    prompt: str,
    image_name: str,
    *,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    denoise: float = 0.65,
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    cfg: float = 6.0,
    seed: Optional[int] = None,
    checkpoint: Optional[str] = None,
) -> Dict[str, Any]:
    """Reference-guided image-to-image graph using ComfyUI LoadImage -> VAEEncode -> KSampler."""
    ckpt = checkpoint or comfy_checkpoint()
    resolved_seed = seed if seed is not None else random.randint(0, 2**32 - 1)
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["1", 1]}},
        "3": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["1", 1]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "5": {"class_type": "VAEEncode", "inputs": {"pixels": ["4", 0], "vae": ["1", 2]}},
        "6": {
            "class_type": "KSampler",
            "inputs": {
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["5", 0],
                "seed": resolved_seed,
                "steps": steps,
                "cfg": cfg,
                "sampler_name": "euler",
                "scheduler": "normal",
                "denoise": max(0.05, min(1.0, float(denoise))),
            },
        },
        "7": {"class_type": "VAEDecode", "inputs": {"samples": ["6", 0], "vae": ["1", 2]}},
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": "keystone_ref", "images": ["7", 0]}},
    }


def build_upscale_graph(
    image_name: str,
    scale_factor: int = 2,
    model_name: str = "4x-UltraSharp.pth",
) -> Dict[str, Any]:
    """Neural ESRGAN super-resolution upscale graph using UpscaleModelLoader + ImageUpscaleWithModel."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {"class_type": "UpscaleModelLoader", "inputs": {"model_name": model_name}},
        "3": {
            "class_type": "ImageUpscaleWithModel",
            "inputs": {
                "upscale_model": ["2", 0],
                "image": ["1", 0],
            },
        },
        "4": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "keystone_upscale", "images": ["3", 0]},
        },
    }


def decode_png_rgba(data: bytes) -> Tuple[int, int, bytearray]:
    """Pure-Python standard PNG chunk decoder and scanline unfilterer (RFC 2083)."""
    import zlib
    import struct

    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Not a valid PNG stream")
    pos = 8
    width = height = None
    color_type = bit_depth = None
    idat = bytearray()
    while pos < len(data):
        length, chunk_type = struct.unpack(">I4s", data[pos : pos + 8])
        pos += 8
        chunk_data = data[pos : pos + length]
        pos += length + 4  # skip crc
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", chunk_data[:10])
        elif chunk_type == b"IDAT":
            idat.extend(chunk_data)
        elif chunk_type == b"IEND":
            break
    if width is None or height is None:
        raise ValueError("Missing IHDR in PNG")
    decomp = zlib.decompress(bytes(idat))
    bytes_per_pixel = 4 if color_type == 6 else (3 if color_type == 2 else 4)
    stride = width * bytes_per_pixel
    raw_pixels = bytearray(width * height * 4)
    prev_row = bytearray(stride)
    curr_row = bytearray(stride)
    src_pos = 0
    for y in range(height):
        filter_type = decomp[src_pos]
        src_pos += 1
        scanline = decomp[src_pos : src_pos + stride]
        src_pos += stride
        for i in range(stride):
            filt = scanline[i]
            a = curr_row[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
            b = prev_row[i]
            c = prev_row[i - bytes_per_pixel] if i >= bytes_per_pixel else 0
            if filter_type == 0:
                val = filt
            elif filter_type == 1:
                val = (filt + a) & 0xFF
            elif filter_type == 2:
                val = (filt + b) & 0xFF
            elif filter_type == 3:
                val = (filt + ((a + b) >> 1)) & 0xFF
            elif filter_type == 4:
                p = a + b - c
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                val = (filt + pr) & 0xFF
            else:
                val = filt
            curr_row[i] = val
        prev_row[:] = curr_row
        dst_idx = y * width * 4
        if bytes_per_pixel == 4:
            raw_pixels[dst_idx : dst_idx + width * 4] = curr_row
        elif bytes_per_pixel == 3:
            for x in range(width):
                px = x * 3
                raw_pixels[dst_idx + x * 4 : dst_idx + x * 4 + 4] = curr_row[px : px + 3] + b"\xff"
    return width, height, raw_pixels


def upscale_image(
    image_bytes: bytes,
    scale_factor: int = 2,
    prompt: str = "",
    timeout: Optional[float] = None,
    grade: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Full upscale execution against the live ComfyUI runtime (applying non-neutral grade BEFORE ESRGAN)."""
    scale = max(2, min(4, int(scale_factor)))
    if not is_configured():
        raise ComfyUINotConfigured(
            "COMFY_NOT_CONFIGURED: set COMFY_BASE_URL to a running ComfyUI instance"
        )
    source_bytes = image_bytes
    norm_grade = normalize_grade_params(grade)
    if is_non_neutral_grade(norm_grade):
        source_bytes = apply_grade(
            source_bytes,
            exposure=norm_grade["exposure"],
            contrast=norm_grade["contrast"],
            saturation=norm_grade["saturation"],
            warmth=norm_grade["warmth"],
        )
    fname = f"upscale_src_{int(time.time())}.png"
    comfy_name = upload_image_to_comfy(source_bytes, fname)
    graph = build_upscale_graph(comfy_name, scale_factor=scale)
    prompt_id = submit_graph(graph)
    outputs = wait_for_result(prompt_id, timeout=timeout)
    images = []
    for node_output in outputs.values():
        images.extend(node_output.get("images", []) or [])
    if not images:
        raise ComfyUIError("COMFY_NO_IMAGE: upscale workflow produced no image outputs")
    data, mime = fetch_image(images[0])
    try:
        w, h, _ = decode_png_rgba(data)
    except Exception:
        w, h = None, None
    return {
        "bytes": data,
        "mime_type": mime,
        "scale_factor": scale,
        "width": w,
        "height": h,
        "prompt_id": prompt_id,
    }


def _resolve_remote_checkpoint_name(preferred: Optional[str] = None) -> str:
    """Resolve an available CheckpointLoaderSimple checkpoint on the remote ComfyUI instance."""
    target = preferred or comfy_checkpoint()
    try:
        _, info = _request("/object_info/CheckpointLoaderSimple")
        if isinstance(info, dict):
            available = (
                info.get("CheckpointLoaderSimple", {})
                .get("input", {})
                .get("required", {})
                .get("ckpt_name", [[]])[0]
            )
            if isinstance(available, list) and available:
                if target in available:
                    return target
                basename = target.split("/")[-1].split("\\")[-1]
                for item in available:
                    if item == basename or item.endswith(f"/{basename}") or item.endswith(f"\\{basename}"):
                        return item
                return str(available[0])
    except Exception:
        pass
    return target


def generate_image(
    prompt: str,
    *,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    width: int = 1024,
    height: int = 1024,
    steps: int = 25,
    cfg: float = 6.0,
    seed: Optional[int] = None,
    checkpoint: Optional[str] = None,
    timeout: Optional[float] = None,
    reference_image_bytes: Optional[bytes] = None,
    reference_filename: Optional[str] = None,
    denoise: float = 0.65,
    mode: str = "text2image",
) -> Dict[str, Any]:
    """Full text-to-image or reference-guided generation round trip against live ComfyUI."""
    if not is_configured():
        raise ComfyUINotConfigured(
            "COMFY_NOT_CONFIGURED: set COMFY_BASE_URL to a running ComfyUI instance"
        )
    resolved_ckpt = _resolve_remote_checkpoint_name(checkpoint)
    if reference_image_bytes:
        ref_name = upload_image_to_comfy(
            reference_image_bytes,
            reference_filename or f"ref_{int(time.time())}.png"
        )
        graph = build_img2img_graph(
            prompt,
            ref_name,
            negative_prompt=negative_prompt,
            denoise=denoise,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed,
            checkpoint=resolved_ckpt,
        )
        sampler_node = "6"
    else:
        graph = build_sdxl_graph(
            prompt,
            negative_prompt=negative_prompt,
            width=width,
            height=height,
            steps=steps,
            cfg=cfg,
            seed=seed,
            checkpoint=resolved_ckpt,
        )
        sampler_node = "5"

    prompt_id = submit_graph(graph)
    outputs = wait_for_result(prompt_id, timeout=timeout)

    images = []
    for node_output in outputs.values():
        images.extend(node_output.get("images", []) or [])
    if not images:
        raise ComfyUIError("COMFY_NO_IMAGE: workflow produced no image outputs")

    data, mime = fetch_image(images[0])
    return {
        "bytes": data,
        "mime_type": mime,
        "prompt_id": prompt_id,
        "seed": graph[sampler_node]["inputs"]["seed"],
        "checkpoint": graph["1"]["inputs"]["ckpt_name"],
        "width": width,
        "height": height,
        "steps": steps,
        "cfg": cfg,
        "filename": images[0].get("filename"),
        "reference_used": bool(reference_image_bytes),
    }


PINKCHERRY_H3_BF16_CHECKPOINT = "PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors"


def _resolve_remote_unet_name(preferred: Optional[str] = None) -> str:
    """Resolve the exact UNETLoader filename registered on the remote ComfyUI instance."""
    target = (
        preferred
        or os.environ.get("COMFY_CHECKPOINT", "").strip()
        or PINKCHERRY_H3_BF16_CHECKPOINT
    )
    try:
        _, info = _request("/object_info/UNETLoader")
        if isinstance(info, dict):
            available = (
                info.get("UNETLoader", {})
                .get("input", {})
                .get("required", {})
                .get("unet_name", [[]])[0]
            )
            if isinstance(available, list) and available:
                if target in available:
                    return target
                basename = target.split("/")[-1].split("\\")[-1]
                for item in available:
                    if item == basename or item.endswith(f"/{basename}") or item.endswith(f"\\{basename}"):
                        return item
                for item in available:
                    if "pinkcherry" in item.lower() or "minimax" in item.lower():
                        return item
    except Exception:
        pass
    return target.split("/")[-1] if target.startswith("1.8-hybrid/") else target


def _resolve_workflow_file() -> Path:
    repo_root = Path(__file__).resolve().parents[3]
    candidates = [
        Path.cwd() / "PinkCherry_Ref2V.json",
        repo_root / "PinkCherry_Ref2V.json",
        Path.cwd() / "workflows" / "h3-ref2va.json",
        repo_root / "workflows" / "h3-ref2va.json",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise ComfyUIError("WORKFLOW_NOT_FOUND: PinkCherry_Ref2V.json is missing from repository root.")


def build_minimax_h3_prompt_graph(
    prompt: str,
    ref_image_filename: Optional[str] = None,
    ref_audio_filename: Optional[str] = None,
    ref_video_filename: Optional[str] = None,
    duration: float = 5.0,
    enable_lightning_lora: bool = True,
    unet_name: Optional[str] = None,
    ref_image_size: str = "match",
    seed: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Constructs a ComfyUI executable prompt graph directly from the user's
    canonical PinkCherry_Ref2V.json workflow template, targeting
    PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors.
    """
    wf_path = _resolve_workflow_file()

    with open(wf_path, "r", encoding="utf-8") as f:
        wf = json.load(f)

    link_map = {}
    for link in wf.get("links", []):
        if len(link) >= 5:
            link_id, from_node, from_slot, to_node, to_slot = link[:5]
            link_map[link_id] = (str(from_node), from_slot)

    resolved_unet = unet_name or os.environ.get("COMFY_CHECKPOINT", "").strip() or PINKCHERRY_H3_BF16_CHECKPOINT
    if resolved_unet.startswith("1.8-hybrid/"):
        resolved_unet = resolved_unet.split("/", 1)[1]

    graph: Dict[str, Any] = {}
    for node in wf.get("nodes", []):
        nid = str(node["id"])
        ntype = node.get("type")
        if ntype == "MarkdownNote":
            continue

        inputs: Dict[str, Any] = {}

        # Populate named widget values for ComfyUI /prompt execution
        named_widgets = node.get("widgets_values_named")
        if isinstance(named_widgets, dict):
            for k, v in named_widgets.items():
                if k in ("videopreview", "control_after_generate", "preview"):
                    continue
                if k in ("lora_name", "unet_name", "ckpt_name") and isinstance(v, str):
                    v = v.replace("\\", "/")
                inputs[k] = v

        widgets = node.get("widgets_values")
        if isinstance(widgets, list):
            inputs["widgets_values"] = list(widgets)
        elif isinstance(widgets, dict):
            inputs["widgets_values"] = dict(widgets)

        for inp in node.get("inputs", []):
            name = inp.get("name")
            lid = inp.get("link")
            if lid is not None and lid in link_map:
                inputs[name] = [link_map[lid][0], link_map[lid][1]]

        graph[nid] = {
            "class_type": ntype,
            "inputs": inputs
        }

    # Inject PinkCherry BF16 checkpoint into Node 127 (UNETLoader)
    if "127" in graph:
        graph["127"]["inputs"]["unet_name"] = resolved_unet
        graph["127"]["inputs"]["weight_dtype"] = graph["127"]["inputs"].get("weight_dtype", "default")
        graph["127"]["inputs"]["widgets_values"] = [resolved_unet, "default"]

    # Inject prompt text into Node 138 (Input Text (Prompt))
    if "138" in graph:
        graph["138"]["inputs"]["value"] = prompt
        graph["138"]["inputs"]["widgets_values"] = [prompt]

    # Inject duration into Node 132
    if "132" in graph:
        graph["132"]["inputs"]["value"] = float(duration)
        graph["132"]["inputs"]["widgets_values"] = [float(duration)]

    # Inject fresh runtime seed into Node 129 (RandomNoise) so no baked template seed is reused
    resolved_seed = seed if seed is not None else random.randint(1, 2**53 - 1)
    if "129" in graph:
        graph["129"]["inputs"]["noise_seed"] = resolved_seed
        graph["129"]["inputs"]["widgets_values"] = [resolved_seed, "randomize"]

    # Inject Lightning LoRA toggle into Node 146
    if "146" in graph:
        graph["146"]["inputs"]["value"] = bool(enable_lightning_lora)
        graph["146"]["inputs"]["widgets_values"] = [bool(enable_lightning_lora)]

    # Configure Node 136 (MiniMaxH3ReferenceToVideo) and optional reference loaders
    if "136" in graph:
        n136_in = graph["136"]["inputs"]
        n136_in["ref_image_size"] = ref_image_size
        # Always detach secondary template image slot 187
        n136_in.pop("ref_images.ref_image_1", None)
        graph.pop("187", None)

        if ref_image_filename and "181" in graph:
            graph["181"]["inputs"]["image"] = ref_image_filename
            graph["181"]["inputs"]["upload"] = "image"
            graph["181"]["inputs"]["widgets_values"] = [ref_image_filename, "image"]
        else:
            n136_in.pop("ref_images.ref_image_0", None)
            graph.pop("181", None)

        if ref_audio_filename and "188" in graph:
            graph["188"]["inputs"]["audio"] = ref_audio_filename
            graph["188"]["inputs"]["widgets_values"] = [ref_audio_filename, ""]
            n136_in["ref_audios.ref_audio_0"] = ["188", 0]
            n136_in.pop("ref_audios.ref_audio_1", None)
            graph.pop("189", None)
        else:
            n136_in.pop("ref_audios.ref_audio_0", None)
            n136_in.pop("ref_audios.ref_audio_1", None)
            graph.pop("188", None)
            graph.pop("189", None)

        if ref_video_filename and "190" in graph:
            graph["190"]["inputs"]["video"] = ref_video_filename
            if isinstance(graph["190"]["inputs"].get("widgets_values"), dict):
                graph["190"]["inputs"]["widgets_values"]["video"] = ref_video_filename
        else:
            n136_in.pop("ref_videos.ref_video_0", None)
            graph.pop("190", None)

    if "148" in graph:
        graph["148"]["inputs"]["filename_prefix"] = "keystone/h3_"

    return graph


def generate_minimax_h3_video(
    prompt: str,
    ref_image_bytes: Optional[bytes] = None,
    ref_image_filename: Optional[str] = None,
    ref_video_bytes: Optional[bytes] = None,
    ref_video_filename: Optional[str] = None,
    ref_audio_bytes: Optional[bytes] = None,
    ref_audio_filename: Optional[str] = None,
    duration_seconds: int = 5,
    resolution: str = "720p",
    ref_image_size: str = "match",
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    """
    Executes the PinkCherry MiniMax H3 Reference-to-Video (ref2va) pipeline
    with Qwen 3.8-VL 32B text encoder (qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors),
    joint audio-video diffusion (PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors),
    and dual VAE decoders (minimax_h3_video_vae_fp16.safetensors + minimax_h3_audio_vae_fp32.safetensors)
    per PinkCherry_Ref2V.json.
    """
    if not is_configured():
        raise ComfyUIError(
            f"COMFY_UNREACHABLE: No ComfyUI runtime configured at {comfy_base_url()}. "
            "To execute the MiniMax H3 Ref2VA pipeline with native stereo audio and Qwen 3.8, "
            "ensure the ComfyUI daemon or Colab/Kaggle bridge is active with required weights: "
            f"{PINKCHERRY_H3_BF16_CHECKPOINT}, "
            "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors, "
            "minimax_h3_video_vae_fp16.safetensors, and "
            "minimax_h3_audio_vae_fp32.safetensors."
        )

    uploaded_img_name = None
    if ref_image_bytes:
        uploaded_img_name = upload_image_to_comfy(
            ref_image_bytes,
            ref_image_filename or f"minimax_ref_img_{int(time.time())}.png"
        )

    uploaded_audio_name = None
    if ref_audio_bytes:
        uploaded_audio_name = upload_image_to_comfy(
            ref_audio_bytes,
            ref_audio_filename or f"minimax_ref_audio_{int(time.time())}.wav"
        )

    uploaded_video_name = None
    if ref_video_bytes:
        uploaded_video_name = upload_image_to_comfy(
            ref_video_bytes,
            ref_video_filename or f"minimax_ref_video_{int(time.time())}.mp4"
        )

    resolved_unet = _resolve_remote_unet_name()

    # Build real execution graph from PinkCherry_Ref2V.json
    graph = build_minimax_h3_prompt_graph(
        prompt,
        ref_image_filename=uploaded_img_name,
        ref_audio_filename=uploaded_audio_name,
        ref_video_filename=uploaded_video_name,
        duration=float(duration_seconds),
        enable_lightning_lora=True,
        unet_name=resolved_unet,
        ref_image_size=ref_image_size,
    )

    # Strip widgets_values helper keys before submitting to strict ComfyUI /prompt API
    api_graph: Dict[str, Any] = {}
    for nid, nspec in graph.items():
        clean_inputs = {k: v for k, v in nspec.get("inputs", {}).items() if k != "widgets_values"}
        api_graph[nid] = {
            "class_type": nspec["class_type"],
            "inputs": clean_inputs,
        }

    prompt_id = submit_graph(api_graph)
    outputs = wait_for_result(prompt_id, timeout=timeout or 300.0)

    # Extract real video from node 148 (VHS_VideoCombine)
    videos = []
    if "148" in outputs:
        videos.extend(outputs["148"].get("gifs", []) or outputs["148"].get("videos", []) or [])

    if not videos:
        for node_out in outputs.values():
            videos.extend(node_out.get("gifs", []) or node_out.get("videos", []) or [])
            if videos:
                break

    if not videos:
        raise ComfyUIError("COMFY_NO_VIDEO: MiniMax H3 workflow produced no video outputs from VHS_VideoCombine.")

    # Download the real generated video file from ComfyUI
    video_ref = videos[0]
    query = urllib.parse.urlencode({
        "filename": video_ref.get("filename", ""),
        "subfolder": video_ref.get("subfolder", ""),
        "type": video_ref.get("type", "output")
    })
    _, video_bytes = _request(f"/view?{query}", raw=True)

    return {
        "bytes": video_bytes,
        "mime_type": "video/mp4",
        "prompt_id": prompt_id,
        "model": resolved_unet,
        "text_encoder": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors (Qwen 3.8)",
        "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
        "video_vae": "minimax_h3_video_vae_fp16.safetensors",
        "duration_seconds": duration_seconds,
        "resolution": resolution,
        "reference_image_used": bool(ref_image_bytes),
        "reference_audio_used": bool(ref_audio_bytes),
        "filename": video_ref.get("filename", f"minimax_h3_{prompt_id[:8]}.mp4")
    }


ASPECT_RATIO_DIMENSIONS: Dict[str, Tuple[int, int]] = {
    "1:1": (768, 768),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "4:3": (960, 720),
    "3:4": (720, 960),
    "21:9": (1344, 576),
}

_ASPECT_RESOLUTION_LABELS: Dict[str, str] = {
    "16:9": "16:9 (Widescreen)",
    "9:16": "9:16 (Portrait)",
    "1:1": "1:1 (Square)",
    "4:3": "4:3 (Standard)",
    "3:4": "3:4 (Portrait)",
    "21:9": "21:9 (Cinema)",
}

VIDEO_WORKFLOW_TEMPLATES: Dict[str, str] = {
    "t2v": "h3_t2v",
    "text_to_video": "h3_t2v",
    "i2v": "h3_i2v",
    "image_to_video": "h3_i2v",
    "ref2v": "h3_ref2v",
    "videogen": "h3_ref2v",
    "v2v": "h3_v2v",
    "video2video": "h3_v2v",
    "re-render": "h3_v2v",
    "video_upscale": "video_esrgan_upscale",
    "video_upscaler": "video_esrgan_upscale",
}


def resolve_aspect_dimensions(
    aspect_ratio: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Tuple[int, int]:
    """Map an aspect ratio string to pixel dimensions when explicit dimensions are omitted."""
    if width and height:
        return int(width), int(height)
    ar = (aspect_ratio or "16:9").strip().split()[0]
    return ASPECT_RATIO_DIMENSIONS.get(ar, (1280, 720))


def normalize_grade_params(params: Optional[Dict[str, Any]] = None) -> Dict[str, float]:
    """Extract and normalize Look grade parameters (handling both unit scale and UI % sliders)."""
    src = dict(params or {})
    nested = src.get("grade") or src.get("look") or {}
    merged = {**src, **nested} if isinstance(nested, dict) else src

    def _pick(key: str, default: float) -> float:
        val = merged.get(key)
        if val is None:
            return default
        try:
            return float(val)
        except (TypeError, ValueError):
            return default

    exposure = _pick("exposure", 0.0)
    contrast = _pick("contrast", 1.0)
    saturation = _pick("saturation", 1.0)
    warmth = _pick("warmth", 0.0)

    if contrast > 10.0:
        contrast = contrast / 100.0
    if saturation > 10.0:
        saturation = saturation / 100.0
    if abs(warmth) > 2.0:
        warmth = warmth / 30.0

    return {
        "exposure": max(-2.0, min(2.0, exposure)),
        "contrast": max(0.0, min(2.0, contrast)),
        "saturation": max(0.0, min(2.0, saturation)),
        "warmth": max(-1.0, min(1.0, warmth)),
    }


def is_non_neutral_grade(grade: Optional[Dict[str, Any]]) -> bool:
    """Return True when normalized grade parameters differ from identity."""
    if not grade:
        return False
    norm = normalize_grade_params(grade)
    return not is_neutral_grade(
        exposure=norm["exposure"],
        contrast=norm["contrast"],
        saturation=norm["saturation"],
        warmth=norm["warmth"],
    )


def compile_video_prompt(
    prompt: str,
    *,
    camera_motion: Optional[str] = None,
    motion_speed: Optional[float] = None,
    duration: Optional[float] = None,
    aspect_ratio: Optional[str] = None,
    grade: Optional[Dict[str, Any]] = None,
    lut: Optional[str] = None,
) -> str:
    """Enrich prompt text with camera motion, speed, duration, aspect ratio, and Look grade cues."""
    base = (prompt or "").strip()
    directives: List[str] = []

    if camera_motion:
        cam_str = str(camera_motion).strip()
        if motion_speed is not None:
            directives.append(f"Camera motion: {cam_str} (speed {float(motion_speed):.2f}x)")
        else:
            directives.append(f"Camera motion: {cam_str}")
    elif motion_speed is not None:
        directives.append(f"Motion speed: {float(motion_speed):.2f}x")

    if duration is not None:
        directives.append(f"Duration: {float(duration):g}s")
    if aspect_ratio:
        directives.append(f"Aspect ratio: {str(aspect_ratio).strip()}")
    if lut and str(lut).strip().lower() not in ("", "none"):
        directives.append(f"Film look: {str(lut).strip()}")

    norm_grade = normalize_grade_params(grade)
    if is_non_neutral_grade(norm_grade):
        directives.append(
            f"Color grade: exposure={norm_grade['exposure']:+.2f}, "
            f"contrast={norm_grade['contrast']:.2f}, "
            f"saturation={norm_grade['saturation']:.2f}, "
            f"warmth={norm_grade['warmth']:+.2f}"
        )

    if not directives:
        return base
    directive_block = "; ".join(directives)
    if directive_block in base:
        return base
    return f"{base}\n\n[{directive_block}]" if base else f"[{directive_block}]"


def _substitute_placeholders(obj: Any, values: Dict[str, Any]) -> Any:
    """Recursively substitute `{{key}}` placeholders, preserving native numeric/bool types."""
    if isinstance(obj, dict):
        return {k: _substitute_placeholders(v, values) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute_placeholders(item, values) for item in obj]
    if isinstance(obj, str) and "{{" in obj:
        stripped = obj.strip()
        if stripped.startswith("{{") and stripped.endswith("}}") and stripped.count("{{") == 1:
            key = stripped[2:-2].strip()
            if key in values and values[key] is not None:
                return values[key]
        out = obj
        for k, v in values.items():
            if v is not None and f"{{{{{k}}}}}" in out:
                out = out.replace(f"{{{{{k}}}}}", str(v))
        return out
    return obj


def render_workflow_graph(graph: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Hydrate a ComfyUI workflow template with runtime prompt, media references,
    seed, motion, duration, aspect ratio, and Look grade parameters.
    """
    raw = dict(params or {})
    prompt = str(raw.get("prompt") or raw.get("positive_prompt") or "").strip()
    negative_prompt = raw.get("negative_prompt") or DEFAULT_NEGATIVE_PROMPT
    aspect_ratio = str(raw.get("aspect_ratio") or raw.get("ratio") or "16:9").strip().split()[0]
    width, height = resolve_aspect_dimensions(aspect_ratio, raw.get("width"), raw.get("height"))
    duration = float(raw.get("duration") or raw.get("duration_seconds") or 5.0)
    camera_motion = raw.get("camera_motion") or raw.get("motion")
    motion_speed = raw.get("motion_speed")
    grade = normalize_grade_params(raw)
    seed_val = raw.get("seed")
    resolved_seed = int(seed_val) if seed_val is not None else random.randint(1, 2**32 - 1)
    steps = int(raw.get("steps") or 25)
    cfg = float(raw.get("cfg") or raw.get("guidance") or 6.0)
    denoise = raw.get("denoise") if raw.get("denoise") is not None else raw.get("strength")
    scale_factor = int(raw.get("scale_factor") or raw.get("scale") or 2)

    image_name = raw.get("image_name") or raw.get("ref_image") or raw.get("source_image")
    second_image_name = raw.get("second_image_name")
    video_name = raw.get("video_name") or raw.get("ref_video") or raw.get("source_video")
    audio_name = raw.get("audio_name") or raw.get("ref_audio")

    sub_values: Dict[str, Any] = {
        "prompt": prompt,
        "positive_prompt": prompt,
        "negative_prompt": negative_prompt,
        "image_name": image_name,
        "ref_image": image_name,
        "source_image": image_name,
        "video_name": video_name,
        "ref_video": video_name,
        "source_video": video_name,
        "audio_name": audio_name,
        "ref_audio": audio_name,
        "duration": duration,
        "duration_seconds": duration,
        "aspect_ratio": aspect_ratio,
        "width": width,
        "height": height,
        "camera_motion": camera_motion,
        "motion_speed": float(motion_speed) if motion_speed is not None else None,
        "seed": resolved_seed,
        "steps": steps,
        "cfg": cfg,
        "denoise": float(denoise) if denoise is not None else None,
        "scale_factor": scale_factor,
        "exposure": grade["exposure"],
        "contrast": grade["contrast"],
        "saturation": grade["saturation"],
        "warmth": grade["warmth"],
    }

    rendered = _substitute_placeholders(deepcopy(graph), sub_values)

    for nid, node in list(rendered.items()):
        if not isinstance(node, dict):
            continue
        ctype = node.get("class_type", "")
        inputs = node.setdefault("inputs", {})

        if ctype == "PrimitiveStringMultiline" and prompt:
            inputs["value"] = prompt
        elif ctype == "CLIPTextEncode":
            txt = inputs.get("text")
            if isinstance(txt, str) and ("{{prompt}}" in txt or (nid == "2" and prompt)):
                inputs["text"] = prompt
            elif isinstance(txt, str) and "{{negative_prompt}}" in txt:
                inputs["text"] = negative_prompt
        elif ctype == "EmptyLatentImage":
            inputs["width"] = width
            inputs["height"] = height
        elif ctype == "ResolutionSelector":
            inputs["aspect_ratio"] = _ASPECT_RESOLUTION_LABELS.get(aspect_ratio, aspect_ratio)
        elif ctype == "PrimitiveFloat" and nid == "132":
            inputs["value"] = duration
        elif ctype == "RandomNoise":
            inputs["noise_seed"] = resolved_seed
        elif ctype == "KSampler":
            inputs["seed"] = resolved_seed
            if raw.get("steps") is not None:
                inputs["steps"] = steps
            if raw.get("cfg") is not None or raw.get("guidance") is not None:
                inputs["cfg"] = cfg
            if denoise is not None:
                inputs["denoise"] = max(0.05, min(1.0, float(denoise)))
        elif ctype == "BasicScheduler" and denoise is not None:
            inputs["denoise"] = max(0.05, min(1.0, float(denoise)))
        elif ctype == "LoadImage":
            if nid == "187" and second_image_name:
                inputs["image"] = second_image_name
            elif image_name:
                inputs["image"] = image_name
        elif ctype == "VHS_LoadVideo" and video_name:
            inputs["video"] = video_name
        elif ctype == "ImageUpscaleWithModel":
            if raw.get("scale_factor") is not None or raw.get("scale") is not None:
                inputs["scale_factor"] = scale_factor
            if is_non_neutral_grade(grade):
                inputs["grade"] = grade
        elif ctype == "MiniMaxH3ReferenceToVideo":
            inputs["duration"] = duration
            inputs["aspect_ratio"] = aspect_ratio
            inputs["target_width"] = width
            inputs["target_height"] = height
            if camera_motion:
                inputs["camera_motion"] = str(camera_motion)
            if motion_speed is not None:
                inputs["motion_speed"] = float(motion_speed)
            if is_non_neutral_grade(grade):
                inputs["grade"] = grade

    # Optional secondary image / audio / video attachment for H3 workflows
    if "136" in rendered and isinstance(rendered["136"], dict):
        n136_inputs = rendered["136"].setdefault("inputs", {})
        if second_image_name:
            rendered["187"] = {
                "class_type": "LoadImage",
                "inputs": {"image": second_image_name, "upload": "image"},
            }
            n136_inputs["ref_images.ref_image_1"] = ["187", 0]
        if image_name and "181" not in rendered:
            rendered["181"] = {
                "class_type": "LoadImage",
                "inputs": {"image": image_name, "upload": "image"},
            }
            n136_inputs["ref_images.ref_image_0"] = ["181", 0]
        if video_name and "190" not in rendered:
            rendered["190"] = {
                "class_type": "VHS_LoadVideo",
                "inputs": {"video": video_name, "format": "H3"},
            }
            n136_inputs["ref_videos.ref_video_0"] = ["190", 0]
        if audio_name:
            rendered["188"] = {
                "class_type": "LoadAudio",
                "inputs": {"audio": audio_name},
            }
            n136_inputs["ref_audios.ref_audio_0"] = ["188", 0]

    return rendered


def build_video_workflow_graph(
    variant: str,
    prompt: str,
    *,
    image_name: Optional[str] = None,
    second_image_name: Optional[str] = None,
    video_name: Optional[str] = None,
    audio_name: Optional[str] = None,
    camera_motion: Optional[str] = None,
    motion_speed: Optional[float] = None,
    duration: float = 5.0,
    aspect_ratio: str = "16:9",
    width: Optional[int] = None,
    height: Optional[int] = None,
    denoise: Optional[float] = None,
    seed: Optional[int] = None,
    steps: Optional[int] = None,
    grade: Optional[Dict[str, Any]] = None,
    lut: Optional[str] = None,
    scale_factor: int = 2,
) -> Dict[str, Any]:
    """Load the canonical video workflow template for `variant` and hydrate all runtime params."""
    key = (variant or "").strip().lower()
    template_name = VIDEO_WORKFLOW_TEMPLATES.get(key)
    if not template_name:
        raise ComfyUIError(f"UNKNOWN_VIDEO_VARIANT: '{variant}'")
    template = load_workflow_template(template_name)
    compiled_prompt = compile_video_prompt(
        prompt,
        camera_motion=camera_motion,
        motion_speed=motion_speed,
        duration=duration,
        aspect_ratio=aspect_ratio,
        grade=grade,
        lut=lut,
    )
    return render_workflow_graph(
        template,
        {
            "prompt": compiled_prompt,
            "image_name": image_name,
            "second_image_name": second_image_name,
            "video_name": video_name,
            "audio_name": audio_name,
            "camera_motion": camera_motion,
            "motion_speed": motion_speed,
            "duration": duration,
            "aspect_ratio": aspect_ratio,
            "width": width,
            "height": height,
            "denoise": denoise,
            "seed": seed,
            "steps": steps,
            "grade": grade,
            "scale_factor": scale_factor,
        },
    )


def _fetch_view_ref(media_ref: Dict[str, Any], default_mime: str) -> Tuple[bytes, str, str]:
    filename = str(media_ref.get("filename", ""))
    query = urllib.parse.urlencode(
        {
            "filename": filename,
            "subfolder": media_ref.get("subfolder", ""),
            "type": media_ref.get("type", "output"),
        }
    )
    _, body = _request(f"/view?{query}", raw=True)
    if not body:
        raise ComfyUIError("COMFY_EMPTY_OUTPUT: /view returned no bytes")

    lower = filename.lower()
    mime = default_mime
    if lower.endswith(".mp4"):
        mime = "video/mp4"
    elif lower.endswith(".webm"):
        mime = "video/webm"
    elif lower.endswith(".mov"):
        mime = "video/quicktime"
    elif lower.endswith(".png"):
        mime = "image/png"
    elif lower.endswith((".jpg", ".jpeg")):
        mime = "image/jpeg"
    elif lower.endswith(".webp"):
        mime = "image/webp"
    return body, mime, filename


def _extract_output_media(outputs: Dict[str, Any]) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
    """Fetch first video/gif or image output produced in ComfyUI history outputs."""
    if not isinstance(outputs, dict):
        return None, None, None

    video_refs: List[Dict[str, Any]] = []
    if "148" in outputs and isinstance(outputs["148"], dict):
        video_refs.extend(outputs["148"].get("videos") or outputs["148"].get("gifs") or [])
    if not video_refs:
        for node_out in outputs.values():
            if not isinstance(node_out, dict):
                continue
            video_refs.extend(node_out.get("videos") or node_out.get("gifs") or [])
            if video_refs:
                break
    if video_refs:
        return _fetch_view_ref(video_refs[0], "video/mp4")

    image_refs: List[Dict[str, Any]] = []
    for node_out in outputs.values():
        if isinstance(node_out, dict):
            image_refs.extend(node_out.get("images") or [])
    if image_refs:
        return _fetch_view_ref(image_refs[0], "image/png")

    return None, None, None


class ComfyUIClient:
    """Thin object wrapper so callers can depend on an injectable client."""

    def base_url(self) -> str:
        return comfy_base_url()

    def is_configured(self) -> bool:
        return is_configured()

    def system_stats(self) -> Dict[str, Any]:
        return system_stats()

    def execute_workflow(
        self,
        envelope: Any,
        workflow_name: Optional[str] = None,
        graph: Optional[Dict[str, Any]] = None,
        expected_mode: Optional[str] = None,
        timeout: Optional[float] = None,
        parameters: Optional[Dict[str, Any]] = None,
        workflow: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Verify ExecutionEnvelope v2 signature & mode, then execute workflow on ComfyUI."""
        from services.harness.src.envelope import EnvelopeEngine

        if envelope is None:
            raise ValueError("MISSING_ENVELOPE: ExecutionEnvelope v2 is required")

        verified = EnvelopeEngine.verify_envelope(envelope, expected_mode=expected_mode)

        target_graph = graph if graph is not None else workflow
        from_template = False
        if target_graph is None:
            if not workflow_name:
                raise ComfyUIError("Either workflow_name or graph must be provided")
            target_graph = load_workflow_template(workflow_name)
            from_template = True

        env_args = envelope.get("arguments") if isinstance(envelope, dict) else getattr(envelope, "arguments", None)
        merged_params: Dict[str, Any] = {}
        if isinstance(env_args, dict):
            merged_params.update(env_args)
        if isinstance(parameters, dict):
            merged_params.update(parameters)

        if from_template or isinstance(parameters, dict):
            rendered_graph = render_workflow_graph(target_graph, merged_params)
        else:
            rendered_graph = target_graph

        prompt_id = submit_graph(rendered_graph)
        history = wait_for_result(prompt_id, timeout=timeout)
        media_bytes, mime_type, filename = _extract_output_media(history)
        return {
            "prompt_id": prompt_id,
            "envelope_id": verified.get("envelope_id"),
            "job_id": verified.get("job_id"),
            "history": history,
            "bytes": media_bytes,
            "mime_type": mime_type,
            "filename": filename,
            "graph": rendered_graph,
        }

    def execute_video_workflow(
        self,
        envelope: Any,
        variant: str,
        prompt: str,
        *,
        expected_mode: Optional[str] = None,
        ref_image_bytes: Optional[bytes] = None,
        ref_image_filename: Optional[str] = None,
        second_image_bytes: Optional[bytes] = None,
        second_image_filename: Optional[str] = None,
        ref_video_bytes: Optional[bytes] = None,
        ref_video_filename: Optional[str] = None,
        ref_audio_bytes: Optional[bytes] = None,
        ref_audio_filename: Optional[str] = None,
        camera_motion: Optional[str] = None,
        motion_speed: Optional[float] = None,
        duration: float = 5.0,
        aspect_ratio: str = "16:9",
        width: Optional[int] = None,
        height: Optional[int] = None,
        denoise: Optional[float] = None,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        grade: Optional[Dict[str, Any]] = None,
        lut: Optional[str] = None,
        scale_factor: int = 2,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Verify envelope, upload reference media, apply grade before upscale, and execute video graph."""
        from services.harness.src.envelope import EnvelopeEngine

        if envelope is None:
            raise ValueError("MISSING_ENVELOPE: ExecutionEnvelope v2 is required")
        # Pre-check signature & mode without consuming nonce yet (consumed once in execute_workflow)
        EnvelopeEngine.verify_envelope(envelope, expected_mode=expected_mode, check_nonce=False)

        if not is_configured():
            raise ComfyUINotConfigured(
                "COMFY_NOT_CONFIGURED: set COMFY_BASE_URL to a running ComfyUI instance"
            )

        norm_grade = normalize_grade_params(grade)
        non_neutral = is_non_neutral_grade(norm_grade)
        variant_key = (variant or "").strip().lower()

        # For video_upscale(r), run deterministic grade BEFORE neural ESRGAN upscale
        effective_video_bytes = ref_video_bytes
        extracted_frames: List[bytes] = []
        source_fps = 24.0
        if variant_key in ("video_upscale", "video_upscaler") and ref_video_bytes:
            with tempfile.TemporaryDirectory(prefix="ks_vup_") as tmpdir:
                tmp_root = Path(tmpdir)
                src_path = tmp_root / "src.mp4"
                src_path.write_bytes(ref_video_bytes)
                try:
                    meta = probe_video_metadata(src_path)
                    if meta.get("fps"):
                        source_fps = float(meta["fps"])
                    has_audio = bool(meta.get("has_audio"))
                except VideoOpsError:
                    has_audio = False

                try:
                    extracted_frames = extract_video_frames(src_path)
                except VideoOpsError:
                    extracted_frames = []

                if non_neutral and extracted_frames:
                    graded_frames = [
                        apply_grade(
                            frame,
                            exposure=norm_grade["exposure"],
                            contrast=norm_grade["contrast"],
                            saturation=norm_grade["saturation"],
                            warmth=norm_grade["warmth"],
                        )
                        for frame in extracted_frames
                    ]
                    graded_path = tmp_root / "graded.mp4"
                    encode_frames_to_video(
                        graded_frames,
                        graded_path,
                        fps=source_fps,
                        audio_source=src_path if has_audio else None,
                    )
                    effective_video_bytes = graded_path.read_bytes()

        image_name = None
        if ref_image_bytes:
            src_img = ref_image_bytes
            if non_neutral and variant_key not in ("video_upscale", "video_upscaler"):
                try:
                    src_img = apply_grade(
                        src_img,
                        exposure=norm_grade["exposure"],
                        contrast=norm_grade["contrast"],
                        saturation=norm_grade["saturation"],
                        warmth=norm_grade["warmth"],
                    )
                except Exception:
                    pass
            image_name = upload_image_to_comfy(
                src_img,
                ref_image_filename or f"ref_{uuid.uuid4().hex[:8]}.png",
            )

        second_image_name = None
        if second_image_bytes:
            second_image_name = upload_image_to_comfy(
                second_image_bytes,
                second_image_filename or f"ref2_{uuid.uuid4().hex[:8]}.png",
            )

        video_name = None
        if effective_video_bytes:
            video_name = upload_image_to_comfy(
                effective_video_bytes,
                ref_video_filename or f"vid_{uuid.uuid4().hex[:8]}.mp4",
            )

        audio_name = None
        if ref_audio_bytes:
            audio_name = upload_image_to_comfy(
                ref_audio_bytes,
                ref_audio_filename or f"aud_{uuid.uuid4().hex[:8]}.wav",
            )

        graph = build_video_workflow_graph(
            variant,
            prompt,
            image_name=image_name,
            second_image_name=second_image_name,
            video_name=video_name,
            audio_name=audio_name,
            camera_motion=camera_motion,
            motion_speed=motion_speed,
            duration=duration,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
            denoise=denoise,
            seed=seed,
            steps=steps,
            grade=norm_grade if non_neutral else None,
            lut=lut,
            scale_factor=scale_factor,
        )

        exec_res = self.execute_workflow(
            envelope,
            graph=graph,
            expected_mode=expected_mode,
            timeout=timeout or 300.0,
        )

        out_bytes = exec_res.get("bytes")
        out_mime = exec_res.get("mime_type") or "video/mp4"

        # If a ComfyUI server returned upscaled PNG frame bytes for video_upscaler, encode back to MP4
        if variant_key in ("video_upscale", "video_upscaler") and out_bytes and out_mime.startswith("image/"):
            with tempfile.TemporaryDirectory(prefix="ks_vup_out_") as tmpdir:
                tmp_root = Path(tmpdir)
                out_mp4 = tmp_root / "upscaled.mp4"
                frame_seq: List[bytes] = [out_bytes]
                if len(extracted_frames) > 1:
                    # Upscale remaining frames sequentially through neural ESRGAN
                    for extra_frame in extracted_frames[1:]:
                        graded_f = (
                            apply_grade(
                                extra_frame,
                                exposure=norm_grade["exposure"],
                                contrast=norm_grade["contrast"],
                                saturation=norm_grade["saturation"],
                                warmth=norm_grade["warmth"],
                            )
                            if non_neutral
                            else extra_frame
                        )
                        up_res = upscale_image(graded_f, scale_factor=scale_factor)
                        frame_seq.append(up_res["bytes"])
                encode_frames_to_video(frame_seq, out_mp4, fps=source_fps)
                out_bytes = out_mp4.read_bytes()
                out_mime = "video/mp4"

        if not out_bytes:
            raise ComfyUIError(f"COMFY_NO_VIDEO: {variant} workflow produced no video output")

        exec_res["bytes"] = out_bytes
        exec_res["mime_type"] = out_mime
        exec_res["grade_applied"] = non_neutral
        return exec_res

    def generate_image(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return generate_image(prompt, **kwargs)

    def generate_minimax_h3_video(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return generate_minimax_h3_video(prompt, **kwargs)

    def upscale_image(self, image_bytes: bytes, scale_factor: int = 2, **kwargs: Any) -> Dict[str, Any]:
        return upscale_image(image_bytes, scale_factor=scale_factor, **kwargs)

    def upload_image(self, image_bytes: bytes, filename: Optional[str] = None) -> str:
        return upload_image_to_comfy(image_bytes, filename)


comfy_client = ComfyUIClient()


# ---------------------------------------------------------------------------
# Workflow templates & MiniMax H3 helpers (consolidated from creative/h3.py)
# ---------------------------------------------------------------------------

WORKFLOWS_DIR = Path(__file__).resolve().parent / "workflows"
H3Error = ComfyUIError


def load_workflow_template(name: str) -> Dict[str, Any]:
    """Load a JSON workflow template from services/comfy/src/workflows/."""
    filename = name if name.endswith(".json") else f"{name}.json"
    path = WORKFLOWS_DIR / filename
    if not path.exists():
        raise ComfyUIError(f"Workflow template not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def h3_workflow_path() -> Optional[Path]:
    try:
        return _resolve_workflow_file()
    except Exception:
        return None


def h3_describe() -> Dict[str, Any]:
    wf = h3_workflow_path()
    return {
        "configured": is_configured(),
        "url": comfy_base_url(),
        "workflow": str(wf) if wf else None,
    }


def h3_health() -> Dict[str, Any]:
    if not is_configured():
        return {"configured": False, "reachable": False, "detail": "COMFY_BASE_URL is not set"}
    try:
        stats = system_stats()
        return {"configured": True, "reachable": True, "system_stats": stats}
    except Exception as exc:
        return {"configured": True, "reachable": False, "detail": str(exc)}


async def h3_generate(
    prompt: str,
    references: Optional[list] = None,
) -> Tuple[bytes, str, Dict[str, Any]]:
    import asyncio
    ref_images = [item[2] for item in (references or []) if len(item) >= 3]
    ref_name = references[0][0] if references and len(references[0]) >= 1 else None
    res = await asyncio.to_thread(
        generate_minimax_h3_video,
        prompt=prompt,
        ref_image_bytes=ref_images[0] if ref_images else None,
        ref_image_filename=ref_name,
    )
    return res["bytes"], res.get("mime_type", "video/mp4"), res


# ---------------------------------------------------------------------------
# Creative Tool Fabric Adapters (consolidated from services/comfy/src/adapters.py)
# ---------------------------------------------------------------------------

from packages.contracts.src.models import CapabilityManifest, ParameterSpec, ExecutionEnvelope

SUPPORTED_ADAPTERS = [
    "comfyui",
    "image_gen",
    "image_edit",
    "wan_i2v",
    "wan_t2v",
    "facefusion",
    "upscale",
]


class CreativeAdapterBase:
    """Base interface for all creative tool fabric adapters."""

    def __init__(self, adapter_name: str, capability_id: str, provider_id: str, version: str = "1.0.0"):
        self.adapter_name = adapter_name
        self.capability_id = capability_id
        self.provider_id = provider_id
        self.version = version

    def get_manifest(self) -> CapabilityManifest:
        raise NotImplementedError

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return params

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        raise NotImplementedError

    def execute(self, params: Dict[str, Any], envelope: Optional[ExecutionEnvelope] = None) -> Dict[str, Any]:
        validated = self.validate_parameters(params)
        prompt = validated.get("prompt", "")
        graph = self.build_workflow_graph(validated, prompt)
        return {
            "adapter": self.adapter_name,
            "capability_id": self.capability_id,
            "status": "READY",
            "workflow_id": f"wf_{self.adapter_name}_v1",
            "graph": graph,
            "parameters": validated,
            "estimated_runtime_seconds": 45,
        }


class ComfyUIAdapter(CreativeAdapterBase):
    def __init__(self):
        super().__init__("comfyui", "creative.comfyui", "comfy.core")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="creative.comfyui",
            provider_id="comfy.core",
            provider_version="1.0.0",
            capability_type="generation",
            description="ComfyUI modular graph generation engine",
            accepts=["application/json"],
            produces=["image/png", "video/mp4"],
            parameters={
                "workflow_graph": ParameterSpec(type="object", required=True, description="ComfyUI node graph JSON")
            },
        )

    def validate_parameters(self, params: Dict[str, Any]) -> Dict[str, Any]:
        if "workflow_graph" not in params and "prompt" not in params:
            raise ValueError("MISSING_GRAPH_OR_PROMPT: workflow_graph or prompt required for ComfyUI adapter")
        return params

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return params.get("workflow_graph", {"3": {"inputs": {"text": prompt}, "class_type": "CLIPTextEncode"}})


class ImageGenAdapter(CreativeAdapterBase):
    """Flux Schnell / Dev text-to-image adapter."""

    def __init__(self):
        super().__init__("image_gen", "image.generation", "comfy.flux_schnell")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="image.generation",
            provider_id="comfy.flux_schnell",
            provider_version="1.0.0",
            capability_type="generation",
            description="High-fidelity text-to-image generation powered by Flux",
            accepts=["text/plain"],
            produces=["image/png"],
            parameters={
                "prompt": ParameterSpec(type="string", required=True, description="Generation prompt"),
                "width": ParameterSpec(type="integer", required=False, default=1024),
                "height": ParameterSpec(type="integer", required=False, default=1024),
                "steps": ParameterSpec(type="integer", required=False, default=4),
                "seed": ParameterSpec(type="integer", required=False, description="Deterministic seed"),
            },
        )

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return build_sdxl_graph(
            prompt=prompt,
            width=params.get("width", 1024),
            height=params.get("height", 1024),
            steps=params.get("steps", 25),
            seed=params.get("seed"),
        )


class ImageEditAdapter(CreativeAdapterBase):
    def __init__(self):
        super().__init__("image_edit", "image.edit", "comfy.image_edit")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="image.edit",
            provider_id="comfy.image_edit",
            provider_version="1.0.0",
            capability_type="edit",
            description="Reference-guided image editing",
            accepts=["image/png", "text/plain"],
            produces=["image/png"],
            parameters={
                "prompt": ParameterSpec(type="string", required=True, description="Edit instruction"),
                "image_name": ParameterSpec(type="string", required=True, description="Input image filename"),
                "denoise": ParameterSpec(type="number", required=False, default=0.65),
            },
        )

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return build_img2img_graph(
            prompt=prompt,
            image_name=params.get("image_name", ""),
            denoise=params.get("denoise", 0.65),
        )


class WanI2VAdapter(CreativeAdapterBase):
    def __init__(self):
        super().__init__("wan_i2v", "video.i2v", "comfy.wan_2_1")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="video.i2v",
            provider_id="comfy.wan_2_1",
            provider_version="1.0.0",
            capability_type="video",
            description="Wan 2.1 Image-to-Video generation",
            accepts=["image/png", "text/plain"],
            produces=["video/mp4"],
            parameters={
                "prompt": ParameterSpec(type="string", required=True, description="Motion prompt"),
                "image_name": ParameterSpec(type="string", required=False, description="Source image"),
            },
        )

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return {
            "1": {"class_type": "WanImageToVideo", "inputs": {"prompt": prompt, "image": params.get("image_name", "")}},
            "3": {"class_type": "WanMotionPrompt", "inputs": {"motion_text": prompt}},
        }


class WanT2VAdapter(CreativeAdapterBase):
    def __init__(self):
        super().__init__("wan_t2v", "video.t2v", "comfy.wan_2_1")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="video.t2v",
            provider_id="comfy.wan_2_1",
            provider_version="1.0.0",
            capability_type="video",
            description="Wan 2.1 Text-to-Video generation",
            accepts=["text/plain"],
            produces=["video/mp4"],
            parameters={"prompt": ParameterSpec(type="string", required=True, description="Video prompt")},
        )

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return {"1": {"class_type": "WanTextToVideo", "inputs": {"prompt": prompt}}}


class FaceFusionAdapter(CreativeAdapterBase):
    def __init__(self):
        super().__init__("facefusion", "image.facefusion", "comfy.facefusion")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="image.facefusion",
            provider_id="comfy.facefusion",
            provider_version="1.0.0",
            capability_type="edit",
            description="FaceFusion 3.x identity-preserving face swap",
            accepts=["image/png"],
            produces=["image/png"],
            parameters={
                "source_image": ParameterSpec(type="string", required=True),
                "target_image": ParameterSpec(type="string", required=True),
            },
        )

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return {"1": {"class_type": "FaceFusion", "inputs": {"source": params.get("source_image", ""), "target": params.get("target_image", "")}}}


class UpscaleAdapter(CreativeAdapterBase):
    def __init__(self):
        super().__init__("upscale", "image.upscale", "comfy.esrgan")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="image.upscale",
            provider_id="comfy.esrgan",
            provider_version="1.0.0",
            capability_type="upscale",
            description="Neural ESRGAN 4x-UltraSharp super-resolution upscale",
            accepts=["image/png"],
            produces=["image/png"],
            parameters={
                "image_name": ParameterSpec(type="string", required=True),
                "model_name": ParameterSpec(type="string", required=False, default="4x-UltraSharp.pth"),
            },
        )

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return build_upscale_graph(
            image_name=params.get("image_name", ""),
            model_name=params.get("model_name", "4x-UltraSharp.pth"),
        )


class MiniMaxH3Adapter(CreativeAdapterBase):
    def __init__(self):
        super().__init__("minimax_h3", "video.minimax_h3_ref2va", "comfy.minimax_h3")

    def get_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            capability_id="video.minimax_h3_ref2va",
            provider_id="comfy.minimax_h3",
            provider_version="1.0.0",
            capability_type="video",
            description="MiniMax H3 Reference-to-Video",
            accepts=["image/png", "text/plain"],
            produces=["video/mp4"],
            parameters={
                "prompt": ParameterSpec(type="string", required=True),
                "duration_seconds": ParameterSpec(type="integer", required=False, default=5),
            },
        )

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        return {
            "ref2v": {
                "class_type": "MiniMaxH3ReferenceToVideo",
                "inputs": {
                    "prompt": prompt,
                    "ref_image_size": params.get("ref_image_size", "match"),
                    "duration": params.get("duration_seconds", 5),
                    "ref_image": params.get("ref_image_asset_id"),
                    "ref_video": params.get("ref_video_asset_id"),
                    "ref_audio": params.get("ref_audio_asset_id"),
                },
            },
            "output": {"class_type": "VHS_VideoCombine", "inputs": {"format": "video/h264-mp4", "audio": True, "filename_prefix": "keystone/h3_"}},
        }


class LocalEmbeddingsAdapter(CreativeAdapterBase):
    """Local Qwen-embedding capability adapter behind CognitiveProvider (Bible v2 §2 Invariants 2, 5–7, §42.3)."""

    def __init__(self):
        super().__init__("local_embeddings", "cognition.local_embeddings", "cognition.qwen_embedding", version="2.0.0")

    def get_manifest(self) -> CapabilityManifest:
        from services.cognition.src.embeddings import get_embedding_manifest

        return get_embedding_manifest()

    def build_workflow_graph(self, params: Dict[str, Any], prompt: str) -> Dict[str, Any]:
        from services.cognition.src.embeddings import DEFAULT_EMBEDDING_MODEL, KEYSTONE_EMBEDDING_DIM

        return {
            "endpoint": "/v1/embeddings",
            "model": params.get("model", DEFAULT_EMBEDDING_MODEL),
            "input": prompt or params.get("input", ""),
            "dimensions": int(params.get("dimensions", KEYSTONE_EMBEDDING_DIM)),
            "quantization": params.get("quantization", "GGUF-Q8_0"),
            "license": "Apache-2.0",
        }


ADAPTER_REGISTRY: Dict[str, CreativeAdapterBase] = {
    "comfyui": ComfyUIAdapter(),
    "image_gen": ImageGenAdapter(),
    "image_edit": ImageEditAdapter(),
    "wan_i2v": WanI2VAdapter(),
    "wan_t2v": WanT2VAdapter(),
    "facefusion": FaceFusionAdapter(),
    "upscale": UpscaleAdapter(),
    "minimax_h3": MiniMaxH3Adapter(),
    "local_embeddings": LocalEmbeddingsAdapter(),
}


def get_adapter(adapter_name: str) -> CreativeAdapterBase:
    if adapter_name == "cognition.local_embeddings" and "local_embeddings" in ADAPTER_REGISTRY:
        return ADAPTER_REGISTRY["local_embeddings"]
    if adapter_name not in ADAPTER_REGISTRY:
        raise ValueError(f"UNKNOWN_ADAPTER: {adapter_name}")
    return ADAPTER_REGISTRY[adapter_name]


def list_capabilities() -> List[CapabilityManifest]:
    return [adapter.get_manifest() for adapter in ADAPTER_REGISTRY.values()]


def validate_adapter_request(adapter: str, params: Dict[str, Any]) -> Dict[str, Any]:
    ad = get_adapter(adapter)
    return ad.execute(params)
