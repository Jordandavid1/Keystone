"""MiniMax H3 (PinkCherry) executor — the ComfyUI API client for the Kaggle notebook.

The deployed runtime is the notebook's ComfyUI on port 8188 running
``PinkCherry_ref2va_turbo_lightx2v_workflow.json`` (MiniMaxH3ReferenceToVideo).
This module speaks ComfyUI's real HTTP API, so nothing here is simulated:

    1. ``POST /upload/image``          reference images are written into ComfyUI's input/
    2. ``POST /prompt``                the workflow is converted to API format and queued
    3. ``GET  /history/{prompt_id}``   polled until the graph reports completion
    4. ``GET  /view``                  the produced H.264/AAC MP4 is downloaded

Configuration (``.env`` in the repo root):

    KEYSTONE_COMFY_URL=https://<tunnel>      public origin of the Kaggle ComfyUI
    KEYSTONE_COMFY_API_KEY=<token>           bearer token enforced by the tunnel proxy
    KEYSTONE_COMFY_WORKFLOW=workflows/h3-ref2va.json
    KEYSTONE_COMFY_DURATION=5               seconds of video
    KEYSTONE_COMFY_STEPS=8                  turbo sampler steps
    KEYSTONE_COMFY_MEGAPIXELS=0.5           resolution budget (0.8 => 1216x672 at 16:9)
    KEYSTONE_COMFY_ASPECT=9:16 (Portrait Widescreen)
    KEYSTONE_COMFY_TIMEOUT=900
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

COMFY_URL = (os.getenv("KEYSTONE_COMFY_URL") or "").rstrip("/")
COMFY_API_KEY = os.getenv("KEYSTONE_COMFY_API_KEY") or ""
COMFY_WORKFLOW = os.getenv("KEYSTONE_COMFY_WORKFLOW") or "workflows/h3-ref2va.json"
COMFY_TIMEOUT = float(os.getenv("KEYSTONE_COMFY_TIMEOUT") or 900)
COMFY_POLL_INTERVAL = float(os.getenv("KEYSTONE_COMFY_POLL_INTERVAL") or 5)
COMFY_DURATION = float(os.getenv("KEYSTONE_COMFY_DURATION") or 5)
COMFY_STEPS = int(os.getenv("KEYSTONE_COMFY_STEPS") or 8)
COMFY_MEGAPIXELS = float(os.getenv("KEYSTONE_COMFY_MEGAPIXELS") or 0.5)
COMFY_ASPECT = os.getenv("KEYSTONE_COMFY_ASPECT") or "9:16 (Portrait Widescreen)"

CHECKPOINT = "PinkCherry_hybrid_v1.8_int8_minimax_h3_pruned.safetensors"
TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
LORA = "MiniMaxh3 Turbo/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"
VIDEO_VAE = "minimax_h3_video_vae_fp16.safetensors"

PROMPT_NODE = "138"
REFERENCE_NODES = ["181", "187"]          # ref_image_0, ref_image_1
REFERENCE_INPUTS = ["ref_images.ref_image_0", "ref_images.ref_image_1"]
REFERENCE_NODE = "136"
OUTPUT_NODE = "148"
DURATION_NODE = "132"
STEPS_NODE = "143"
BYPASS_NODES = {"PathchSageAttentionKJ"}
DROPPED_INPUTS = ("ref_audios.",)          # no audio references are uploaded yet


class H3Error(RuntimeError):
    """Raised whenever the deployed runtime did not produce a video."""


def workflow_path() -> Optional[Path]:
    path = Path(COMFY_WORKFLOW)
    if not path.is_absolute():
        path = Path(__file__).resolve().parents[4] / path
    return path if path.is_file() else None


def configured() -> bool:
    return bool(COMFY_URL and workflow_path())


def describe() -> Dict[str, Any]:
    return {
        "configured": configured(),
        "base_url": COMFY_URL or None,
        "workflow": str(workflow_path()) if workflow_path() else COMFY_WORKFLOW,
        "duration": COMFY_DURATION,
        "steps": COMFY_STEPS,
        "api_key": bool(COMFY_API_KEY),
    }


# ------------------------------------------------------------------ transport

def _headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = dict(extra or {})
    if COMFY_API_KEY:
        headers["Authorization"] = f"Bearer {COMFY_API_KEY}"
    return headers


def _open(url: str, data: Optional[bytes] = None, headers: Optional[Dict[str, str]] = None,
          timeout: float = 60):
    request = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    for key, value in _headers(headers).items():
        request.add_header(key, value)
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        body = exc.read()[:2000].decode("utf-8", "replace")
        raise H3Error(f"COMFY_HTTP_{exc.code}: {body or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise H3Error(f"COMFY_UNREACHABLE: {exc.reason}") from exc


def health() -> Dict[str, Any]:
    if not COMFY_URL:
        return {"configured": False, "reachable": False, "detail": "KEYSTONE_COMFY_URL is not set"}
    try:
        with _open(f"{COMFY_URL}/system_stats", timeout=10) as response:
            return {
                "configured": configured(),
                "reachable": True,
                "status": response.status,
                "body": response.read()[:600].decode("utf-8", "replace"),
            }
    except H3Error as exc:
        return {"configured": configured(), "reachable": False, "detail": str(exc)}


def _upload_image(filename: str, payload: bytes, mime: str) -> str:
    boundary = f"----keystone{uuid.uuid4().hex}"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
        f"Content-Type: {mime or 'application/octet-stream'}\r\n\r\n"
    ).encode() + payload + (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="overwrite"\r\n\r\ntrue'
        f"\r\n--{boundary}--\r\n"
    ).encode()
    with _open(
        f"{COMFY_URL}/upload/image",
        body,
        {"Content-Type": f"multipart/form-data; boundary={boundary}"},
        timeout=180,
    ) as response:
        result = json.loads(response.read() or b"{}")
    name = result.get("name") or filename
    subfolder = result.get("subfolder") or ""
    return f"{subfolder}/{name}" if subfolder else name


# ------------------------------------------------------- workflow -> api prompt

def _set_widget(node: Dict[str, Any], name: str, value: Any) -> None:
    current = node.get("widgets_values")
    if isinstance(current, dict):
        current[name] = value
        return
    current = list(current or [])
    widget_names = [(item.get("widget") or {}).get("name") for item in node.get("inputs", []) if item.get("widget")]
    if name in widget_names:
        current[widget_names.index(name)] = value
        node["widgets_values"] = current
        return
    raise H3Error(f"H3_WORKFLOW_CHANGED: widget {name} missing from node {node['id']} ({node['type']})")


def _prepare(template: Dict[str, Any], prompt: str, references: List[str]) -> Dict[str, Any]:
    """Fill the versioned workflow with this job's prompt and references."""
    nodes = {str(node["id"]): node for node in template["nodes"]}

    for required in (PROMPT_NODE, REFERENCE_NODE, OUTPUT_NODE, "115", "128", "119", "120"):
        if required not in nodes:
            raise H3Error(f"H3_WORKFLOW_CHANGED: expected node {required} is missing")

    _set_widget(nodes[PROMPT_NODE], "value", prompt)
    _set_widget(nodes[DURATION_NODE], "value", COMFY_DURATION) if DURATION_NODE in nodes else None
    if STEPS_NODE in nodes:
        _set_widget(nodes[STEPS_NODE], "value", COMFY_STEPS)

    for node in template["nodes"]:
        kind = node["type"]
        if kind == "UNETLoader":
            _set_widget(node, "unet_name", CHECKPOINT)
        elif kind == "CLIPLoader":
            _set_widget(node, "clip_name", TEXT_ENCODER)
        elif kind == "LoraLoaderModelOnly":
            _set_widget(node, "lora_name", LORA)
        elif kind == "VAELoader":
            names = node.get("widgets_values") or []
            if isinstance(names, dict) and "minimax_h3_video_vae" in str(names.get("vae_name")):
                _set_widget(node, "vae_name", VIDEO_VAE)
        elif kind == "ModelPreviewOverrideKJ":
            _set_widget(node, "tiny_vae", "none")
        elif kind == "ResolutionSelector":
            _set_widget(node, "aspect_ratio", COMFY_ASPECT)
            _set_widget(node, "megapixels", COMFY_MEGAPIXELS)
            _set_widget(node, "multiple", 32)
        elif kind == "VHS_VideoCombine":
            _set_widget(node, "filename_prefix", f"keystone/{uuid.uuid4().hex[:8]}")
            _set_widget(node, "format", "video/h264-mp4")

    # Attach reference images, or detach the slot when fewer were supplied so a
    # placeholder filename can never be sent to the runtime.
    reference_node = nodes[REFERENCE_NODE]
    links = {str(link[0]): link for link in template["links"]}
    for index, input_name in enumerate(REFERENCE_INPUTS):
        loader_id = REFERENCE_NODES[index]
        loader = nodes.get(loader_id)
        if loader is None:
            raise H3Error(f"H3_WORKFLOW_CHANGED: reference loader {loader_id} is missing")
        slot = next((item for item in reference_node.get("inputs", []) if item["name"] == input_name), None)
        if index < len(references):
            _set_widget(loader, "image", references[index])
        elif slot is not None:
            slot["link"] = None

    # Audio reference sockets point at LoadAudio nodes with files that do not
    # exist in the deployed runtime; leave them disconnected.
    for item in reference_node.get("inputs", []):
        if item["name"].startswith(DROPPED_INPUTS):
            item["link"] = None

    return template


def _to_api_prompt(template: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a UI-format ComfyUI graph into the /prompt API format."""
    nodes = {str(node["id"]): node for node in template["nodes"]}
    links = {str(link[0]): (str(link[1]), link[2]) for link in template["links"]}

    output_ids = [str(node["id"]) for node in template["nodes"] if node["type"] == "VHS_VideoCombine"]
    if not output_ids:
        raise H3Error("H3_WORKFLOW_CHANGED: no VHS_VideoCombine output node")

    needed, pending = set(), output_ids[:]
    while pending:
        node_id = pending.pop()
        if node_id in needed or node_id not in nodes:
            continue
        needed.add(node_id)
        for item in nodes[node_id].get("inputs", []):
            if item.get("link") is not None and str(item["link"]) in links:
                pending.append(links[str(item["link"])][0])

    api: Dict[str, Any] = {}
    for node_id in needed:
        node = nodes[node_id]
        kind = node["type"]
        if kind in {"MarkdownNote", "Note"}:
            continue
        current = node.get("widgets_values") or []
        if isinstance(current, dict):
            widget_values = dict(current)
        else:
            widget_names = [(item.get("widget") or {}).get("name") for item in node.get("inputs", []) if item.get("widget")]
            widget_values = dict(zip(widget_names, current))

        inputs: Dict[str, Any] = {}
        for item in node.get("inputs", []):
            name = item["name"]
            if item.get("link") is not None and str(item["link"]) in links:
                origin, slot = links[str(item["link"])]
                inputs[name] = [origin, slot]
            else:
                key = (item.get("widget") or {}).get("name", name)
                if key in widget_values:
                    inputs[name] = widget_values[key]
        api[node_id] = {"class_type": kind, "inputs": inputs}

    # ComfyUI bypass semantics: PathchSageAttentionKJ is disabled, so consumers
    # receive its upstream model instead of the patch node.
    for node_id in [nid for nid, node in api.items() if node["class_type"] in BYPASS_NODES]:
        upstream = next((value for value in api[node_id]["inputs"].values() if isinstance(value, list)), None)
        if upstream is None:
            raise H3Error(f"H3_WORKFLOW_CHANGED: bypass node {node_id} has no upstream input")
        for consumer in api.values():
            for key, value in list(consumer["inputs"].items()):
                if isinstance(value, list) and len(value) == 2 and value[0] == node_id:
                    consumer["inputs"][key] = list(upstream)
        api.pop(node_id, None)

    return api


# ------------------------------------------------------------------- execution

def _pick_output(history: Dict[str, Any], prompt_id: str) -> Optional[Dict[str, str]]:
    entry = history.get(prompt_id) or {}
    for node in (entry.get("outputs") or {}).values():
        for key in ("gifs", "videos", "video", "images"):
            for item in node.get(key) or []:
                filename = item.get("filename") or ""
                if not filename:
                    continue
                if key == "images" and not filename.lower().endswith((".mp4", ".webm", ".gif", ".mov")):
                    continue
                return {
                    "filename": filename,
                    "subfolder": item.get("subfolder") or "",
                    "type": item.get("type") or "output",
                }
    return None


def _download(filename: str, subfolder: str, kind: str) -> Tuple[bytes, str]:
    query = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder, "type": kind})
    with _open(f"{COMFY_URL}/view?{query}", timeout=300) as response:
        data = response.read()
        content_type = response.headers.get("Content-Type", "video/mp4")
    if not data:
        raise H3Error("COMFY_EMPTY_OUTPUT: ComfyUI returned zero bytes")
    return data, content_type if content_type.startswith("video/") else "video/mp4"


def _run_blocking(prompt: str, references: List[Tuple[str, str, bytes]]) -> Tuple[bytes, str, Dict[str, Any]]:
    path = workflow_path()
    if not path:
        raise H3Error(f"H3_WORKFLOW_MISSING: {COMFY_WORKFLOW} is not a file")

    uploaded = [_upload_image(name, payload, mime) for name, mime, payload in references[:2]]
    template = json.loads(path.read_text(encoding="utf-8"))
    workflow = _to_api_prompt(_prepare(template, prompt, uploaded))

    body = json.dumps({"prompt": workflow, "client_id": f"keystone-{uuid.uuid4()}"}).encode()
    with _open(f"{COMFY_URL}/prompt", body, {"Content-Type": "application/json"}, timeout=60) as response:
        queued = json.loads(response.read() or b"{}")
    prompt_id = queued.get("prompt_id")
    if not prompt_id:
        raise H3Error(f"COMFY_REJECTED: {json.dumps(queued)[:800]}")

    deadline = time.monotonic() + COMFY_TIMEOUT
    while time.monotonic() < deadline:
        with _open(f"{COMFY_URL}/history/{prompt_id}", timeout=60) as response:
            history = json.loads(response.read() or b"{}")
        if prompt_id in history:
            status = history[prompt_id].get("status") or {}
            if status.get("status_str") == "error":
                raise H3Error(f"COMFY_EXECUTION_FAILED: {json.dumps(status)[:900]}")
            output = _pick_output(history, prompt_id)
            if output:
                data, content_type = _download(output["filename"], output["subfolder"], output["type"])
                return data, content_type, {
                    "model": "minimax-h3-pinkcherry-1.8",
                    "prompt_id": prompt_id,
                    "references": len(uploaded),
                    "filename": output["filename"],
                }
        time.sleep(COMFY_POLL_INTERVAL)

    raise H3Error(f"COMFY_TIMEOUT: prompt {prompt_id} produced no video within {int(COMFY_TIMEOUT)}s")


async def generate(prompt: str, references: List[Tuple[str, str, bytes]]) -> Tuple[bytes, str, Dict[str, Any]]:
    if not configured():
        raise H3Error(
            "H3_NOT_CONFIGURED: set KEYSTONE_COMFY_URL to the Kaggle ComfyUI tunnel and keep "
            "KEYSTONE_COMFY_WORKFLOW at workflows/h3-ref2va.json"
        )
    return await asyncio.to_thread(_run_blocking, prompt, references)
