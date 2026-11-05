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
import json
import os
import random
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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
    """Loads KEY=VALUE pairs from .env in dist/, cwd, or repository root."""
    try:
        from services.cognition.src.client import load_keystone_dotenv
        load_keystone_dotenv()
    except Exception:
        pass
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
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


def comfy_base_url() -> str:
    _load_repo_env()
    env_url = os.getenv("COMFY_BASE_URL", "").rstrip("/")
    if env_url:
        return env_url
    try:
        from services.harness.src.worker_bridge import worker_bridge
        for cap in ("image.generation", "comfyui", "creative.generation"):
            matched = worker_bridge.route_for_capability(cap)
            if matched:
                return matched[0].tunnel_url.rstrip("/")
        for worker in worker_bridge.list_workers(active_only=True):
            if any(k in str(worker.get("worker_type", "")).lower() for k in ("creative", "comfy", "gateway")):
                return str(worker["tunnel_url"]).rstrip("/")
    except Exception:
        pass
    return ""



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
    if data is not None:
        req.add_header("Content-Type", "application/json")

    _load_repo_env()
    basic = os.getenv("COMFY_BASIC_AUTH", "").strip()
    if basic:
        token = base64.b64encode(basic.encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")

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


def upload_image_to_comfy(image_bytes: bytes, filename: str = "reference.png") -> str:
    """Uploads an image to ComfyUI's /upload/image endpoint using multipart/form-data."""
    base = comfy_base_url()
    if not base:
        return filename
    try:
        boundary = f"----KeystoneBoundary{int(time.time()*1000)}"
        body = bytearray()
        # Form field 'overwrite'
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n".encode("utf-8"))
        # File field 'image'
        safe_fname = os.path.basename(filename) or "reference.png"
        mime = "image/png" if safe_fname.lower().endswith(".png") else "image/jpeg"
        body.extend(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{safe_fname}\"\r\nContent-Type: {mime}\r\n\r\n".encode("utf-8"))
        body.extend(image_bytes)
        body.extend(f"\r\n--{boundary}--\r\n".encode("utf-8"))

        req = urllib.request.Request(f"{base}/upload/image", data=bytes(body), method="POST")
        req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        _load_repo_env()
        basic = os.getenv("COMFY_BASIC_AUTH", "").strip()
        if basic:
            token = base64.b64encode(basic.encode("utf-8")).decode("ascii")
            req.add_header("Authorization", f"Basic {token}")

        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
            return data.get("name", safe_fname)
    except Exception:
        return filename


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
    """Super-resolution upscale graph using ComfyUI UpscaleImageBy."""
    return {
        "1": {"class_type": "LoadImage", "inputs": {"image": image_name}},
        "2": {
            "class_type": "UpscaleImageBy",
            "inputs": {
                "image": ["1", 0],
                "upscale_method": "bicubic",
                "scale_by": float(scale_factor),
            },
        },
        "3": {
            "class_type": "SaveImage",
            "inputs": {"filename_prefix": "keystone_upscale", "images": ["2", 0]},
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
) -> Dict[str, Any]:
    """Full upscale execution against the live ComfyUI runtime."""
    scale = max(2, min(4, int(scale_factor)))
    if not is_configured():
        raise ComfyUINotConfigured(
            "COMFY_NOT_CONFIGURED: set COMFY_BASE_URL to a running ComfyUI instance"
        )
    fname = f"upscale_src_{int(time.time())}.png"
    comfy_name = upload_image_to_comfy(image_bytes, fname)
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
        w, h = 1024 * scale, 1024 * scale
    return {
        "bytes": data,
        "mime_type": mime,
        "scale_factor": scale,
        "width": w,
        "height": h,
        "prompt_id": prompt_id,
    }


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
            checkpoint=checkpoint,
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
            checkpoint=checkpoint,
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


def build_minimax_h3_prompt_graph(
    prompt: str,
    ref_image_filename: Optional[str] = None,
    ref_audio_filename: Optional[str] = None,
    ref_video_filename: Optional[str] = None,
    duration: float = 5.0,
    enable_lightning_lora: bool = True,
    unet_name: Optional[str] = None,
    ref_image_size: str = "match",
) -> Dict[str, Any]:
    """
    Constructs a ComfyUI executable prompt graph directly from the user's
    canonical PinkCherry_Ref2V.json workflow template, targeting
    PinkCherry_hybrid_v1.8_minimax_h3_pruned_bf16.safetensors.
    """
    wf_path = Path("PinkCherry_Ref2V.json")
    if not wf_path.exists():
        raise ComfyUIError("WORKFLOW_NOT_FOUND: PinkCherry_Ref2V.json is missing from repository root.")

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


class ComfyUIClient:
    """Thin object wrapper so callers can depend on an injectable client."""

    def is_configured(self) -> bool:
        return is_configured()

    def system_stats(self) -> Dict[str, Any]:
        return system_stats()

    def generate_image(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return generate_image(prompt, **kwargs)

    def generate_minimax_h3_video(self, prompt: str, **kwargs: Any) -> Dict[str, Any]:
        return generate_minimax_h3_video(prompt, **kwargs)

    def upscale_image(self, image_bytes: bytes, scale_factor: int = 2, **kwargs: Any) -> Dict[str, Any]:
        return upscale_image(image_bytes, scale_factor=scale_factor, **kwargs)

    def upload_image(self, image_bytes: bytes, filename: str = "reference.png") -> str:
        return upload_image_to_comfy(image_bytes, filename)


comfy_client = ComfyUIClient()
