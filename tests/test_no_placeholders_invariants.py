"""
KEYSTONE Zero-Placeholder, Zero-Sample-Input & Live-Only Output Invariants Guard.

Enforces permanently across the backend, Comfy workflows, audio/cognition adapters,
and every frontend surface (/workspace, /admin, Next.js Studio) that:
1. No placeholder credits, hardcoded fake health badges, or sample prompts exist.
2. No backend client silently falls back to synthetic, offline mock, or stale static data.
3. Unconfigured or failing external runtimes fail loudly with explicit error codes.
4. Change-control §37 audits pass.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


STATIC_FORBIDDEN_RULES: List[Tuple[str, List[str], List[str], re.Pattern[str]]] = [
    (
        "cognition_offline_mock",
        ["services/cognition", "apps/api/src"],
        [".py"],
        re.compile(
            r"mock_action|mock_resp|Fallback mock|default_placeholder|"
            r"kaggle-cognition-t4x2\.trycloudflare\.com|mock_jwt_secret|mock_storage_signing_key"
        ),
    ),
    (
        "comfy_sample_or_silent_fallback",
        ["services/comfy", "apps/api/src/creative"],
        [".py"],
        re.compile(
            r"subtle realistic motion|default\s*=\s*42|seed.*,\s*42|1024 \* scale|"
            r"fallback_origin|def upload_image_to_comfy.*reference\.png"
        ),
    ),
    (
        "audio_static_catalog_or_silent_fallback",
        ["services/audio", "apps/api/src/routers/audio.py", "apps/api/src/routers/personas.py"],
        [".py"],
        re.compile(r"PREMIER_VOICES|keystone_speech_synth"),
    ),
    (
        "gcs_silent_local_fallback",
        ["apps/api/src/storage"],
        [".py"],
        re.compile(r"_fallback_local"),
    ),
    (
        "frontend_placeholders_and_sample_inputs",
        [
            "apps/web/index.html",
            "apps/web/app.js",
            "apps/web/legacy",
            "apps/web/components",
            "apps/web/lib",
            "apps/web/app",
            "apps/admin",
        ],
        [".html", ".js", ".ts", ".tsx"],
        re.compile(
            r"1,250 CREDITS|>1,250<|HOLD: 3|\?\?\s*1250|btn-sample-script|btn-agent-sample|"
            r'class="chat-starter-grid"|data-prompt=|Cinematic Hollywood Scene|sha256:genesis_root|'
            r"running on dual NVIDIA T4 GPUs|Directive completed\.|Retrying via fallback cognitive engine|"
            r'value="usr_system"|starterPrompt:\s*[\'"][^\'"]+[\'"]|'
            r"local_dev_token|tenant-keystone-local|operator@keystone\.internal|huihui-ai/|huihui-qwen"
        ),
    ),
]


def scan_zero_placeholder_invariants(root_dir: Path = REPO_ROOT) -> Dict[str, object]:
    """Scans code, frontend assets, and Comfy workflow templates for banned placeholders or samples."""
    violations: List[Dict[str, object]] = []

    for rule_name, rel_roots, suffixes, pattern in STATIC_FORBIDDEN_RULES:
        for rel_root in rel_roots:
            target = root_dir / rel_root
            if not target.exists():
                continue
            files = (
                [target]
                if target.is_file()
                else sorted(
                    f
                    for f in target.rglob("*")
                    if f.is_file()
                    and f.suffix.lower() in suffixes
                    and not any(part in f.parts for part in ("node_modules", ".next", "__pycache__", ".venv"))
                )
            )
            for file_path in files:
                text = file_path.read_text(encoding="utf-8", errors="replace")
                for line_no, line in enumerate(text.splitlines(), 1):
                    if pattern.search(line):
                        violations.append(
                            {
                                "rule": rule_name,
                                "file": str(file_path.relative_to(root_dir)).replace("\\", "/"),
                                "line": line_no,
                                "snippet": line.strip()[:140],
                            }
                        )

    # Verify ComfyUI workflow JSONs ship with empty user-input widgets (no sample prompts/media filenames)
    workflow_files = [root_dir / "PinkCherry_Ref2V.json"]
    workflows_dir = root_dir / "workflows"
    if workflows_dir.is_dir():
        workflow_files.extend(sorted(workflows_dir.glob("*.json")))

    for wf_path in workflow_files:
        if not wf_path.is_file():
            continue
        data = json.loads(wf_path.read_text(encoding="utf-8"))
        for node in data.get("nodes", []):
            ntype = node.get("type")
            if ntype not in {"PrimitiveStringMultiline", "LoadImage", "LoadAudio", "VHS_LoadVideo"}:
                continue
            wv = node.get("widgets_values")
            if isinstance(wv, list) and wv and str(wv[0]).strip():
                violations.append(
                    {
                        "rule": "comfy_workflow_sample_widget",
                        "file": str(wf_path.relative_to(root_dir)).replace("\\", "/"),
                        "line": 0,
                        "snippet": f"node {node.get('id')} ({ntype}) non-empty widget[0]={wv[0]!r}",
                    }
                )
            elif isinstance(wv, dict) and str(wv.get("video", "")).strip():
                violations.append(
                    {
                        "rule": "comfy_workflow_sample_widget",
                        "file": str(wf_path.relative_to(root_dir)).replace("\\", "/"),
                        "line": 0,
                        "snippet": f"node {node.get('id')} ({ntype}) non-empty video={wv.get('video')!r}",
                    }
                )

    return {
        "valid": len(violations) == 0,
        "violation_count": len(violations),
        "violations": violations,
    }


def test_source_tree_and_workflows_have_zero_placeholders_or_sample_inputs():
    res = scan_zero_placeholder_invariants(REPO_ROOT)
    assert res["valid"], f"Placeholder/sample violations found: {res['violations']}"


def test_cognition_connector_never_fabricates_mock_actions(monkeypatch):
    from services.cognition.src.client import CognitionConnector

    monkeypatch.delenv("COGNITION_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("KAGGLE_COGNITION_TUNNEL", raising=False)

    client = CognitionConnector()
    monkeypatch.setattr(client, "resolve_active_endpoint", lambda: "")
    with pytest.raises(RuntimeError, match="COGNITION_NOT_CONFIGURED"):
        client.complete("Render an architectural penthouse")

    unreachable = CognitionConnector(base_url="http://127.0.0.1:9999/v1")
    with pytest.raises(ConnectionError, match="COGNITION_UNREACHABLE"):
        unreachable.complete("Render an architectural penthouse")


def test_comfy_client_and_adapters_never_fallback_or_use_sample_inputs(monkeypatch):
    from services.comfy.src import client as comfy_client_mod
    from services.comfy.src.client import ImageGenAdapter, WanI2VAdapter
    from services.harness.src.worker_bridge import worker_bridge

    monkeypatch.setattr(comfy_client_mod, "_load_repo_env", lambda: None)
    monkeypatch.delenv("COMFY_BASE_URL", raising=False)
    monkeypatch.delenv("KEYSTONE_COMFY_URL", raising=False)
    monkeypatch.delenv("KAGGLE_COMFYUI_TUNNEL", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "https://cognition-only.invalid/v1")
    monkeypatch.setattr(worker_bridge, "route_for_capability", lambda _cap: [])
    monkeypatch.setattr(worker_bridge, "list_workers", lambda active_only=True: [])

    assert comfy_client_mod.comfy_base_url() == ""
    assert not comfy_client_mod.is_configured()

    with pytest.raises(comfy_client_mod.ComfyUINotConfigured):
        comfy_client_mod.upload_image_to_comfy(b"\x89PNG\r\n\x1a\n")

    with pytest.raises(comfy_client_mod.ComfyUINotConfigured):
        comfy_client_mod.generate_image("A glass bridge at dawn")

    with pytest.raises(comfy_client_mod.ComfyUINotConfigured):
        comfy_client_mod.upscale_image(b"\x89PNG\r\n\x1a\n")

    manifest = ImageGenAdapter().get_manifest()
    assert manifest.parameters["seed"].default is None
    graph = ImageGenAdapter().build_workflow_graph({"prompt": "Live prompt"}, "Live prompt")
    assert isinstance(graph["5"]["inputs"]["seed"], int)

    wan_graph = WanI2VAdapter().build_workflow_graph({"source_image_asset_id": "asset_1"}, "")
    assert wan_graph["3"]["inputs"]["motion_text"] == ""


def test_audio_service_never_silently_falls_back_on_broken_elevenlabs(monkeypatch):
    from services.audio.src.elevenlabs import ElevenLabsClient

    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk_invalid_test_key")

    def fail_urlopen(*_args, **_kwargs):
        raise urllib.error.URLError("simulated network failure")

    monkeypatch.setattr(urllib.request, "urlopen", fail_urlopen)

    with pytest.raises(RuntimeError, match="ELEVENLABS_VOICES_FAILED"):
        ElevenLabsClient.list_voices()

    with pytest.raises(RuntimeError, match="ELEVENLABS_SYNTHESIS_FAILED"):
        ElevenLabsClient.generate_speech("Test speech", voice_id="voice_abc")


def test_audio_unconfigured_uses_real_local_sapi_never_static_premier_catalog(monkeypatch):
    from services.audio.src.elevenlabs import ElevenLabsClient

    monkeypatch.setattr("services.audio.src.elevenlabs.get_elevenlabs_api_key", lambda: "")
    voices = ElevenLabsClient.list_voices()
    assert isinstance(voices, list) and len(voices) >= 1
    assert all(v.get("provider") == "windows_sapi_speech" for v in voices)


def test_gcs_storage_provider_never_silently_falls_back_to_local(monkeypatch):
    from apps.api.src.storage.service import GoogleCloudStorageProvider

    monkeypatch.delenv("GCS_ASSET_BUCKET", raising=False)
    with pytest.raises(RuntimeError, match="GCS_NOT_CONFIGURED"):
        GoogleCloudStorageProvider()


def test_zencreator_unwired_tool_returns_explicit_503_no_placeholder():
    from apps.api.src.server import app

    client = TestClient(app)
    res = client.post("/v1/zencreator/generate", json={"tool": "text_to_video", "input": {"prompt": "test"}})
    assert res.status_code == 503
    assert "NO_ENGINE_CONFIGURED" in res.text


def test_change_control_validator_passes():
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "verify_change_control.py"), "--root", str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, f"verify_change_control failed:\n{proc.stdout}\n{proc.stderr}"


def test_obliteratus_v3_checkpoint_pinned_and_resolve_served_model(monkeypatch):
    from services.cognition.src import client as cog_client_mod
    from services.cognition.src.client import CognitionConnector

    assert CognitionConnector.PINNED_CHECKPOINT == "OBLITERATUS/Qwen3.8-27B-OBLITERATED"

    monkeypatch.setattr(cog_client_mod, "load_keystone_dotenv", lambda: None)
    connector = CognitionConnector(base_url="http://127.0.0.1:9999/v1")

    monkeypatch.setenv("OPENAI_MODEL", "OBLITERATUS/Qwen3.8-27B-OBLITERATED:fastest")
    assert connector.resolve_served_model() == "OBLITERATUS/Qwen3.8-27B-OBLITERATED:fastest"

    monkeypatch.setenv("OPENAI_MODEL", "obliteratus-qwen3.8-v3")
    assert connector.resolve_served_model() == "obliteratus-qwen3.8-v3"

    monkeypatch.setenv("OPENAI_MODEL", "huihui-ai/Huihui-Qwen3.8-27B-abliterated")
    assert connector.resolve_served_model() == "OBLITERATUS/Qwen3.8-27B-OBLITERATED"


def test_dev_bypass_accepts_ipv4_mapped_ipv6_loopback_behind_proxy(monkeypatch):
    from types import SimpleNamespace
    from apps.api.src.auth.dependencies import dev_bypass_applies

    monkeypatch.setenv("KEYSTONE_DEV_AUTH_BYPASS", "1")
    proxied_req = SimpleNamespace(
        client=SimpleNamespace(host="::ffff:127.0.0.1"),
        headers={"x-forwarded-for": "::ffff:127.0.0.1"},
    )
    assert dev_bypass_applies(proxied_req, authorization=None, x_api_key=None) is True

    spoofed_req = SimpleNamespace(
        client=SimpleNamespace(host="::ffff:127.0.0.1"),
        headers={"x-forwarded-for": "203.0.113.5"},
    )
    assert dev_bypass_applies(spoofed_req, authorization=None, x_api_key=None) is False

