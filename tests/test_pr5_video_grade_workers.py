"""PR5 (ADR-005): Video suite (t2v/i2v/ref2v/v2v/extend/upscale), deterministic grade lane, HTTP Range 206, and envelope-verifying worker."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import struct
import threading
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.src.auth.security import generate_token
from apps.api.src.db.models import (
    Asset,
    AssetRelationship,
    AttemptAsset,
    AuditEvent,
    AuthorityDecision,
    Base,
    CompiledPrompt,
    GenerationAttempt,
    HarnessRun,
    Job,
    Project,
    User,
)
from apps.api.src.db.session import get_db
from apps.api.src.server import app
from services.comfy.src import client as comfy_client_mod
from services.comfy.src.client import ComfyUIClient, decode_png_rgba, upscale_image
from services.comfy.src.grade import (
    GRADE_BOUNDS,
    apply_grade,
    grade_digest,
    is_neutral_grade,
)
from services.comfy.src.video_ops import encode_frames_to_video, probe_video_metadata
from services.harness.src.envelope import EnvelopeEngine
from services.harness.src.evaluators.deterministic import validate_asset_bytes
from services.workers.src.worker import AsyncJobQueue, KeystoneWorker


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


class _AsyncSessionAdapter:
    """Adapts a sync SQLAlchemy Session for async FastAPI dependencies and KeystoneWorker."""

    def __init__(self, sync_session):
        self._s = sync_session

    def __getattr__(self, name):
        return getattr(self._s, name)

    async def execute(self, *args, **kwargs):
        return self._s.execute(*args, **kwargs)

    async def commit(self):
        return self._s.commit()

    async def flush(self):
        return self._s.flush()

    async def refresh(self, instance, *args, **kwargs):
        return self._s.refresh(instance, *args, **kwargs)

    async def rollback(self):
        return self._s.rollback()

    async def close(self):
        return None

    async def run_sync(self, fn, *args, **kwargs):
        return fn(self._s, *args, **kwargs)


def _make_png_bytes(
    width: int = 32,
    height: int = 32,
    *,
    base_color: Optional[Tuple[int, int, int]] = None,
    rgba: bool = False,
) -> bytes:
    """Create a valid uncompressed/zlib-compressed PNG image in pure Python."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    color_type = 6 if rgba else 2
    ihdr = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # Filter type 0 (None)
        for x in range(width):
            if base_color is not None:
                r, g, b = base_color
            else:
                # Distinct multi-quadrant / gradient pixels so contrast, saturation & warmth all shift stats
                r = (40 + (x * 7) + (y * 3)) % 256
                g = (90 + (x * 3) + (y * 5)) % 256
                b = (160 + (x * 2) - (y * 4)) % 256
            if rgba:
                alpha = 180 if (x + y) % 2 == 0 else 255
                raw.extend((r, g, b, alpha))
            else:
                raw.extend((r, g, b))
    idat = zlib.compress(bytes(raw))
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _make_synthetic_mp4(
    out_path: Path,
    *,
    width: int = 64,
    height: int = 64,
    num_frames: int = 6,
    fps: float = 12.0,
    colors: Optional[List[Tuple[int, int, int]]] = None,
) -> bytes:
    """Build a real playable H.264 MP4 fixture via ffmpeg."""
    palette = colors or [
        (200, 40, 40),
        (40, 200, 40),
        (40, 40, 200),
        (220, 180, 40),
        (180, 40, 220),
        (40, 200, 220),
    ]
    frames = [
        _make_png_bytes(width, height, base_color=palette[i % len(palette)])
        for i in range(num_frames)
    ]
    encode_frames_to_video(frames, out_path, fps=fps)
    return out_path.read_bytes()


def _extract_multipart_upload(body: bytes, content_type: str) -> Tuple[str, bytes]:
    """Extract (filename, bytes) from ComfyUI /upload/image multipart/form-data payload."""
    match = re.search(r"boundary=([^\s;]+)", content_type or "")
    if not match:
        return "upload.bin", body
    boundary = match.group(1).strip('"').encode("utf-8")
    parts = body.split(b"--" + boundary)
    for part in parts:
        if b'name="image"' not in part:
            continue
        header_end = part.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        headers_raw = part[:header_end].decode("utf-8", errors="replace")
        file_bytes = part[header_end + 4 :]
        if file_bytes.endswith(b"\r\n"):
            file_bytes = file_bytes[:-2]
        fn_match = re.search(r'filename="([^"]+)"', headers_raw)
        fname = fn_match.group(1) if fn_match else "upload.bin"
        return fname, file_bytes
    return "upload.bin", body


def _start_mock_comfy_video_server(
    *,
    png_output: Optional[bytes] = None,
    upscaled_png_output: Optional[bytes] = None,
    mp4_output: Optional[bytes] = None,
    upscaled_mp4_output: Optional[bytes] = None,
):
    """Local HTTP mock ComfyUI server recording uploads, workflows, and ordered events."""
    state: Dict[str, Any] = {
        "events": [],
        "uploads": {},
        "prompts": {},
        "submitted_workflows": [],
    }

    class _Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _json(self, status: int, payload: dict):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/system_stats":
                return self._json(200, {"system": {"os": "mock"}, "devices": [{"name": "MockGPU"}]})
            if path.startswith("/history/"):
                pid = path.rsplit("/", 1)[-1]
                rec = state["prompts"].get(pid)
                if not rec:
                    return self._json(200, {})
                if rec["is_video"]:
                    fname = "upscaled.mp4" if rec["is_upscale"] else "generated.mp4"
                    node_id = "4" if rec["is_upscale"] else "148"
                    outputs = {
                        node_id: {
                            "videos": [{"filename": fname, "subfolder": "", "type": "output"}]
                        }
                    }
                else:
                    fname = "upscaled.png" if rec["is_upscale"] else "generated.png"
                    outputs = {
                        "9": {"images": [{"filename": fname, "subfolder": "", "type": "output"}]}
                    }
                return self._json(
                    200,
                    {
                        pid: {
                            "status": {"status_str": "success", "completed": True},
                            "outputs": outputs,
                        }
                    },
                )
            if path == "/view":
                if "upscaled.mp4" in self.path and upscaled_mp4_output is not None:
                    data, ctype = upscaled_mp4_output, "video/mp4"
                elif ".mp4" in self.path and mp4_output is not None:
                    data, ctype = mp4_output, "video/mp4"
                elif "upscaled.png" in self.path and upscaled_png_output is not None:
                    data, ctype = upscaled_png_output, "image/png"
                else:
                    data, ctype = (png_output or _make_png_bytes(64, 64)), "image/png"
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            return self._json(404, {"error": "not found"})

        def do_POST(self):
            path = self.path.split("?")[0]
            length = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(length)
            if path == "/upload/image":
                orig_name, file_bytes = _extract_multipart_upload(
                    body, self.headers.get("Content-Type", "")
                )
                assigned = f"upload-{uuid.uuid4().hex[:8]}-{orig_name}"
                state["uploads"][assigned] = file_bytes
                state["events"].append(("upload", assigned, file_bytes))
                return self._json(200, {"name": assigned, "subfolder": "", "type": "input"})
            if path == "/prompt":
                payload = json.loads(body or b"{}")
                workflow = payload.get("prompt") or {}
                class_types = {
                    node.get("class_type")
                    for node in workflow.values()
                    if isinstance(node, dict)
                }
                is_upscale = "ImageUpscaleWithModel" in class_types
                is_video = (
                    "VHS_VideoCombine" in class_types
                    or "MiniMaxH3ReferenceToVideo" in class_types
                    or "VHS_LoadVideo" in class_types
                )
                pid = str(uuid.uuid4())
                state["prompts"][pid] = {
                    "is_upscale": is_upscale,
                    "is_video": is_video,
                    "workflow": workflow,
                }
                state["submitted_workflows"].append(workflow)
                state["events"].append(("prompt", pid, workflow))
                return self._json(200, {"prompt_id": pid, "number": 1})
            return self._json(404, {"error": "not found"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}", state


def _pixel_stats(png_bytes: bytes) -> Dict[str, float]:
    w, h, rgba = decode_png_rgba(png_bytes)
    n = w * h
    r_sum = g_sum = b_sum = 0
    for i in range(0, len(rgba), 4):
        r_sum += rgba[i]
        g_sum += rgba[i + 1]
        b_sum += rgba[i + 2]
    return {
        "mean_r": r_sum / n,
        "mean_g": g_sum / n,
        "mean_b": b_sum / n,
    }


def _signed_envelope(
    *,
    job_id: str,
    user_id: str,
    content_mode: str = "sfw",
    age_verified: bool = True,
    capability_id: str = "video.t2v",
    intent: str = "animate",
):
    decision = SimpleNamespace(
        decision_id=f"dec_{uuid.uuid4().hex[:12]}",
        decision="ALLOW",
        reason_code="OK",
        capability_id=capability_id,
        provider_id="keystone_internal",
        sanitized_arguments={},
    )
    return EnvelopeEngine.create_envelope(
        decision=decision,
        job_id=job_id,
        user_id=user_id,
        intent=intent,
        content_mode=content_mode,
        age_verified=age_verified,
        floor_verdict="pass",
    )


# ---------------------------------------------------------------------------
# 1. test_grade_lane_deterministic_and_runs_before_upscale
# ---------------------------------------------------------------------------
def test_grade_lane_deterministic_and_runs_before_upscale(tmp_path, monkeypatch):
    """
    Apply non-zero exposure/contrast/saturation/warmth, assert pixel stats change
    deterministically, identical inputs produce identical SHA-256 bytes, bounds are
    strictly clamped, and apply_grade executes BEFORE neural ESRGAN upscale.
    """
    src_png = _make_png_bytes(16, 16)
    src_stats = _pixel_stats(src_png)

    # Neutral grade is identity
    assert is_neutral_grade(0.0, 1.0, 1.0, 0.0) is True
    neutral_out = apply_grade(src_png, exposure=0.0, contrast=1.0, saturation=1.0, warmth=0.0)
    assert neutral_out == src_png
    assert grade_digest(neutral_out) == grade_digest(src_png)

    # Non-zero grade produces deterministic SHA-256 bytes & shifts RGB pixel statistics
    grade_kwargs = {"exposure": 0.6, "contrast": 1.35, "saturation": 1.25, "warmth": 0.45}
    assert is_neutral_grade(**grade_kwargs) is False

    graded_a = apply_grade(src_png, **grade_kwargs)
    graded_b = apply_grade(src_png, **grade_kwargs)
    assert graded_a == graded_b
    assert grade_digest(graded_a) == grade_digest(graded_b)
    assert graded_a != src_png

    graded_stats = _pixel_stats(graded_a)
    assert graded_stats["mean_r"] != pytest.approx(src_stats["mean_r"])
    assert graded_stats["mean_g"] != pytest.approx(src_stats["mean_g"])
    assert graded_stats["mean_b"] != pytest.approx(src_stats["mean_b"])

    # Positive warmth shifts R up relative to B compared to the same grade with warmth=0.0
    no_warm_stats = _pixel_stats(
        apply_grade(src_png, exposure=0.6, contrast=1.35, saturation=1.25, warmth=0.0)
    )
    assert (graded_stats["mean_r"] - graded_stats["mean_b"]) > (
        no_warm_stats["mean_r"] - no_warm_stats["mean_b"]
    )

    # Strict bound clamping: out-of-range values clamp identically to GRADE_BOUNDS extremes
    over_max = apply_grade(src_png, exposure=99.0, contrast=99.0, saturation=99.0, warmth=99.0)
    at_max = apply_grade(
        src_png,
        exposure=GRADE_BOUNDS["exposure"][1],
        contrast=GRADE_BOUNDS["contrast"][1],
        saturation=GRADE_BOUNDS["saturation"][1],
        warmth=GRADE_BOUNDS["warmth"][1],
    )
    assert grade_digest(over_max) == grade_digest(at_max)

    # RGBA alpha channel is preserved unmodified while RGB changes
    src_rgba = _make_png_bytes(12, 12, rgba=True)
    graded_rgba = apply_grade(src_rgba, **grade_kwargs)
    _, _, orig_px = decode_png_rgba(src_rgba)
    _, _, grad_px = decode_png_rgba(graded_rgba)
    assert orig_px[3::4] == grad_px[3::4]
    assert orig_px != grad_px

    # Grade runs BEFORE neural ESRGAN upscale in both image and video pipelines
    src_mp4 = _make_synthetic_mp4(tmp_path / "src.mp4", width=32, height=32, num_frames=3, fps=8.0)
    upscaled_mp4 = _make_synthetic_mp4(tmp_path / "up.mp4", width=64, height=64, num_frames=3, fps=8.0)
    upscaled_png = _make_png_bytes(64, 64)

    server, comfy_url, mock_state = _start_mock_comfy_video_server(
        png_output=src_png,
        upscaled_png_output=upscaled_png,
        mp4_output=src_mp4,
        upscaled_mp4_output=upscaled_mp4,
    )
    monkeypatch.setenv("COMFY_BASE_URL", comfy_url)
    monkeypatch.setenv("COMFY_URL", comfy_url)
    monkeypatch.setenv("COMFYUI_BASE_URL", comfy_url)

    try:
        # Image upscale: uploaded bytes sent to /upload/image BEFORE ImageUpscaleWithModel /prompt
        up_img_res = upscale_image(src_png, scale_factor=2, grade=grade_kwargs)
        assert up_img_res["bytes"] == upscaled_png
        assert len(mock_state["events"]) >= 2
        assert mock_state["events"][0][0] == "upload"
        assert mock_state["events"][1][0] == "prompt"
        uploaded_img_bytes = mock_state["events"][0][2]
        assert hashlib.sha256(uploaded_img_bytes).hexdigest() == grade_digest(graded_a)
        assert uploaded_img_bytes != src_png
        submitted_img_wf = mock_state["events"][1][2]
        assert any(
            isinstance(n, dict) and n.get("class_type") == "ImageUpscaleWithModel"
            for n in submitted_img_wf.values()
        )

        # Video upscale: apply_grade runs on extracted frames BEFORE video_esrgan_upscale /prompt
        mock_state["events"].clear()
        call_trace: List[str] = []
        orig_apply_grade = comfy_client_mod.apply_grade
        orig_submit_graph = comfy_client_mod.submit_graph

        def _spy_apply_grade(*args, **kwargs):
            call_trace.append("apply_grade")
            return orig_apply_grade(*args, **kwargs)

        def _spy_submit_graph(graph):
            call_trace.append("submit_graph")
            return orig_submit_graph(graph)

        monkeypatch.setattr(comfy_client_mod, "apply_grade", _spy_apply_grade)
        monkeypatch.setattr(comfy_client_mod, "submit_graph", _spy_submit_graph)

        uid = str(uuid.uuid4())
        jid = str(uuid.uuid4())
        env = _signed_envelope(
            job_id=jid,
            user_id=uid,
            content_mode="sfw",
            capability_id="upscale.clarity",
            intent="upscale",
        )
        vup_res = ComfyUIClient().execute_video_workflow(
            env,
            "video_upscaler",
            "Upscale and color-grade video",
            expected_mode="sfw",
            ref_video_bytes=src_mp4,
            grade=grade_kwargs,
            scale_factor=2,
        )
        assert vup_res["grade_applied"] is True
        assert "apply_grade" in call_trace and "submit_graph" in call_trace
        assert call_trace.index("apply_grade") < call_trace.index("submit_graph")
        assert mock_state["events"][0][0] == "upload"
        assert mock_state["events"][1][0] == "prompt"
        assert mock_state["events"][0][2] != src_mp4
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# 2. test_video_variants_and_extend_chain_through_gate
# ---------------------------------------------------------------------------
def test_video_variants_and_extend_chain_through_gate(db_session, tmp_path, monkeypatch):
    """
    Hit t2v, i2v, ref2v, v2v, extend, and video_upscaler through Gate + mock ComfyUI
    with synthetic MP4/PNG fixtures; verify camera_motion/motion_speed reach workflow
    params, extend stitches segments, and lineage edges + Gate DB rows persist.
    """
    ref_png = _make_png_bytes(64, 64)
    src_mp4 = _make_synthetic_mp4(
        tmp_path / "seed_clip.mp4",
        width=64,
        height=64,
        num_frames=6,
        fps=12.0,
    )
    mock_video_out = _make_synthetic_mp4(
        tmp_path / "mock_out.mp4",
        width=64,
        height=64,
        num_frames=6,
        fps=12.0,
        colors=[(30, 120, 220), (40, 150, 230), (60, 170, 240)],
    )
    mock_upscaled_out = _make_synthetic_mp4(
        tmp_path / "mock_upscaled.mp4",
        width=128,
        height=128,
        num_frames=6,
        fps=12.0,
    )

    server, comfy_url, mock_state = _start_mock_comfy_video_server(
        png_output=ref_png,
        mp4_output=mock_video_out,
        upscaled_mp4_output=mock_upscaled_out,
    )
    monkeypatch.setenv("COMFY_BASE_URL", comfy_url)
    monkeypatch.setenv("COMFY_URL", comfy_url)
    monkeypatch.setenv("COMFYUI_BASE_URL", comfy_url)
    monkeypatch.setenv("KEYSTONE_STORAGE_DIR", str(tmp_path / "storage"))

    user = User(
        id=str(uuid.uuid4()),
        email="pr5-video@example.com",
        password_hash="hashed",
        role="user",
        age_verified=True,
        content_mode="sfw",
    )
    project = Project(id=str(uuid.uuid4()), user_id=user.id, name="PR5 Video Suite")
    db_session.add_all([user, project])
    db_session.commit()

    token = generate_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    def _override_get_db():
        yield _AsyncSessionAdapter(db_session)

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)

        # Upload reference PNG & synthetic MP4 fixture
        up_img = client.post(
            "/v1/assets/upload-file",
            files={"file": ("anchor.png", ref_png, "image/png")},
            data={"project_id": project.id, "media_type": "image"},
            headers=headers,
        )
        assert up_img.status_code == 200, up_img.text
        ref_img_id = up_img.json()["id"]

        up_vid = client.post(
            "/v1/assets/upload-file",
            files={"file": ("seed_clip.mp4", src_mp4, "video/mp4")},
            data={"project_id": project.id, "media_type": "video"},
            headers=headers,
        )
        assert up_vid.status_code == 200, up_vid.text
        seed_vid_id = up_vid.json()["id"]

        # 1) t2v (text_to_video)
        r_t2v = client.post(
            "/v1/studio/generate",
            json={
                "tool": "t2v",
                "input": {
                    "prompt": "Drone sweep over neon skyline at rain-slicked dusk",
                    "camera_motion": "orbit_left",
                    "motion_speed": 1.35,
                    "duration": 4,
                    "aspect_ratio": "16:9",
                    "project_id": project.id,
                    "grade": {"exposure": 0.25, "contrast": 1.15, "saturation": 1.1, "warmth": 0.2},
                },
            },
            headers=headers,
        )
        assert r_t2v.status_code == 200, r_t2v.text
        t2v_data = r_t2v.json()
        assert t2v_data["status"] == "succeeded"
        assert t2v_data.get("envelope_id")
        wf_t2v = mock_state["submitted_workflows"][-1]
        assert wf_t2v["136"]["inputs"]["camera_motion"] == "orbit_left"
        assert wf_t2v["136"]["inputs"]["motion_speed"] == pytest.approx(1.35)
        assert wf_t2v["136"]["inputs"]["duration"] == pytest.approx(4.0)
        assert "orbit_left" in wf_t2v["138"]["inputs"]["value"]

        # 2) i2v (image_to_video)
        r_i2v = client.post(
            "/v1/studio/generate",
            json={
                "tool": "i2v",
                "input": {
                    "prompt": "Slow dolly push toward the subject",
                    "image_asset_id": ref_img_id,
                    "camera_motion": "dolly_in",
                    "motion_speed": 0.85,
                    "duration": 3,
                    "aspect_ratio": "9:16",
                    "project_id": project.id,
                },
            },
            headers=headers,
        )
        assert r_i2v.status_code == 200, r_i2v.text
        i2v_id = r_i2v.json()["outputs"][0]["asset_id"]
        wf_i2v = mock_state["submitted_workflows"][-1]
        assert wf_i2v["181"]["class_type"] == "LoadImage"
        assert wf_i2v["136"]["inputs"]["camera_motion"] == "dolly_in"
        assert wf_i2v["136"]["inputs"]["motion_speed"] == pytest.approx(0.85)

        # 3) ref2v (videogen)
        r_ref2v = client.post(
            "/v1/studio/generate",
            json={
                "tool": "ref2v",
                "input": {
                    "prompt": "Character turns calmly while wind ripples hair",
                    "ref_asset_id": ref_img_id,
                    "camera_motion": "pan_right",
                    "motion_speed": 1.5,
                    "duration": 5,
                    "aspect_ratio": "1:1",
                    "project_id": project.id,
                },
            },
            headers=headers,
        )
        assert r_ref2v.status_code == 200, r_ref2v.text
        ref2v_id = r_ref2v.json()["outputs"][0]["asset_id"]
        wf_ref2v = mock_state["submitted_workflows"][-1]
        assert wf_ref2v["136"]["inputs"]["camera_motion"] == "pan_right"
        assert wf_ref2v["136"]["inputs"]["motion_speed"] == pytest.approx(1.5)

        # 4) v2v (video2video)
        r_v2v = client.post(
            "/v1/studio/generate",
            json={
                "tool": "v2v",
                "input": {
                    "prompt": "Re-render as luminous watercolor motion",
                    "video_asset_id": seed_vid_id,
                    "camera_motion": "tilt_up",
                    "motion_speed": 1.1,
                    "duration": 4,
                    "denoise": 0.6,
                    "project_id": project.id,
                },
            },
            headers=headers,
        )
        assert r_v2v.status_code == 200, r_v2v.text
        v2v_id = r_v2v.json()["outputs"][0]["asset_id"]
        wf_v2v = mock_state["submitted_workflows"][-1]
        assert wf_v2v["190"]["class_type"] == "VHS_LoadVideo"
        assert wf_v2v["136"]["inputs"]["camera_motion"] == "tilt_up"
        assert wf_v2v["136"]["inputs"]["motion_speed"] == pytest.approx(1.1)

        # 5) extend (extract_last_frame -> i2v through Gate -> stitch_video_segments -> animation edge)
        uploads_before_extend = len(mock_state["uploads"])
        r_ext = client.post(
            "/v1/studio/generate",
            json={
                "tool": "extend",
                "input": {
                    "prompt": "Continue camera glide seamlessly",
                    "video_asset_id": seed_vid_id,
                    "camera_motion": "track_forward",
                    "motion_speed": 1.25,
                    "duration": 4,
                    "aspect_ratio": "16:9",
                    "project_id": project.id,
                },
            },
            headers=headers,
        )
        assert r_ext.status_code == 200, r_ext.text
        ext_id = r_ext.json()["outputs"][0]["asset_id"]
        assert len(mock_state["uploads"]) == uploads_before_extend + 1
        last_upload_name, last_upload_bytes = list(mock_state["uploads"].items())[-1]
        assert last_upload_name.endswith(".png")
        assert last_upload_bytes.startswith(b"\x89PNG\r\n\x1a\n")
        wf_ext = mock_state["submitted_workflows"][-1]
        assert wf_ext["181"]["class_type"] == "LoadImage"
        assert wf_ext["136"]["inputs"]["camera_motion"] == "track_forward"
        assert wf_ext["136"]["inputs"]["motion_speed"] == pytest.approx(1.25)

        ext_asset = db_session.get(Asset, ext_id)
        assert ext_asset is not None
        ext_file = Path(tmp_path / "storage") / ext_asset.storage_key
        assert ext_file.is_file()
        assert validate_asset_bytes(ext_file.read_bytes(), "video", "video/mp4").verdict == "pass"
        ext_meta = probe_video_metadata(ext_file)
        seed_meta = probe_video_metadata(tmp_path / "seed_clip.mp4")
        assert ext_meta["duration"] > seed_meta["duration"]

        # 6) video_upscaler (with non-neutral grade)
        r_vup = client.post(
            "/v1/studio/generate",
            json={
                "tool": "video_upscaler",
                "input": {
                    "video_asset_id": ext_id,
                    "scale_factor": 2,
                    "project_id": project.id,
                    "grade": {"exposure": 0.3, "contrast": 1.2, "saturation": 1.15, "warmth": 0.25},
                },
            },
            headers=headers,
        )
        assert r_vup.status_code == 200, r_vup.text
        vup_id = r_vup.json()["outputs"][0]["asset_id"]
        wf_vup = mock_state["submitted_workflows"][-1]
        assert any(
            isinstance(n, dict) and n.get("class_type") == "ImageUpscaleWithModel"
            for n in wf_vup.values()
        )

        # Verify persisted lineage edges & Gate / Audit / Harness rows in DB
        rels = db_session.execute(select(AssetRelationship)).scalars().all()
        rel_tuples = {(r.parent_asset_id, r.child_asset_id, r.relationship_type) for r in rels}
        assert (ref_img_id, i2v_id, "animation") in rel_tuples
        assert (ref_img_id, ref2v_id, "animation") in rel_tuples
        assert (seed_vid_id, v2v_id, "animation") in rel_tuples
        assert (seed_vid_id, ext_id, "animation") in rel_tuples
        assert (ext_id, vup_id, "upscale") in rel_tuples

        assert len(db_session.execute(select(CompiledPrompt)).scalars().all()) >= 6
        assert len(db_session.execute(select(AuthorityDecision)).scalars().all()) >= 6
        assert len(db_session.execute(select(Job)).scalars().all()) >= 6
        assert len(db_session.execute(select(GenerationAttempt)).scalars().all()) >= 6
        assert len(db_session.execute(select(AttemptAsset)).scalars().all()) >= 6
        assert len(db_session.execute(select(HarnessRun)).scalars().all()) >= 6
    finally:
        app.dependency_overrides.clear()
        server.shutdown()


# ---------------------------------------------------------------------------
# 3. test_asset_content_http_range_206
# ---------------------------------------------------------------------------
def test_asset_content_http_range_206(db_session, tmp_path, monkeypatch):
    """
    Request `Range: bytes=0-1023` on a persisted video asset -> HTTP 206 Partial Content
    with exact `Content-Range`, `Accept-Ranges: bytes`, and 1024 exact bytes.
    """
    monkeypatch.setenv("KEYSTONE_STORAGE_DIR", str(tmp_path / "storage"))

    user = User(
        id=str(uuid.uuid4()),
        email="pr5-range@example.com",
        password_hash="hashed",
        role="user",
        age_verified=True,
        content_mode="sfw",
    )
    db_session.add(user)
    db_session.commit()
    headers = {"Authorization": f"Bearer {generate_token(user.id)}"}

    # Build a synthetic MP4 guaranteed > 2048 bytes
    video_bytes = _make_synthetic_mp4(
        tmp_path / "range_fixture.mp4",
        width=128,
        height=128,
        num_frames=16,
        fps=12.0,
    )
    assert len(video_bytes) > 2048

    def _override_get_db():
        yield _AsyncSessionAdapter(db_session)

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        upload_resp = client.post(
            "/v1/assets/upload-file",
            files={"file": ("timeline.mp4", video_bytes, "video/mp4")},
            data={"media_type": "video"},
            headers=headers,
        )
        assert upload_resp.status_code == 200, upload_resp.text
        download_url = upload_resp.json()["download_url"]
        total_size = len(video_bytes)

        # Primary 0-1023 range check
        r206 = client.get(download_url, headers={"Range": "bytes=0-1023"})
        assert r206.status_code == 206, r206.text
        assert r206.headers.get("Accept-Ranges") == "bytes"
        assert r206.headers.get("Content-Range") == f"bytes 0-1023/{total_size}"
        assert r206.headers.get("Content-Length") == "1024"
        assert len(r206.content) == 1024
        assert r206.content == video_bytes[:1024]

        # Mid-file seek range check
        r206_mid = client.get(download_url, headers={"Range": "bytes=1024-1535"})
        assert r206_mid.status_code == 206
        assert r206_mid.headers.get("Content-Range") == f"bytes 1024-1535/{total_size}"
        assert len(r206_mid.content) == 512
        assert r206_mid.content == video_bytes[1024:1536]

        # Full GET still advertises Accept-Ranges and returns complete video
        r200 = client.get(download_url)
        assert r200.status_code == 200
        assert r200.headers.get("Accept-Ranges") == "bytes"
        assert r200.content == video_bytes

        # Unsatisfiable Range returns 416
        r416 = client.get(download_url, headers={"Range": f"bytes={total_size + 100}-"})
        assert r416.status_code == 416
        assert r416.headers.get("Content-Range") == f"bytes */{total_size}"
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 4. test_worker_refuses_unsigned_or_mode_mismatched_job
# ---------------------------------------------------------------------------
def test_worker_refuses_unsigned_or_mode_mismatched_job(db_session, monkeypatch):
    """
    Push unsigned, tampered, and SFW-on-UNRESTRICTED payloads to KeystoneWorker:
    all are refused before execution (0 executor calls), DB Job transitions to
    REJECTED, and AuditEvent(event_type='worker.envelope_rejected') rows persist.
    """
    monkeypatch.delenv("REDIS_URL", raising=False)

    user = User(
        id=str(uuid.uuid4()),
        email="pr5-worker@example.com",
        password_hash="hashed",
        role="user",
        age_verified=True,
        content_mode="unrestricted",
    )
    db_session.add(user)
    db_session.commit()

    exec_calls: List[Tuple[str, str]] = []

    def _spy_executor(envelope, payload, verified):
        exec_calls.append((verified["job_id"], verified["content_mode"]))
        return {"prompt_id": f"p-{verified['job_id'][:8]}", "outputs": []}

    queue = AsyncJobQueue()
    worker = KeystoneWorker(queue=queue, executor=_spy_executor, worker_id="test-worker-pr5")
    adapter = _AsyncSessionAdapter(db_session)

    async def _run_scenarios():
        assert queue.backend == "asyncio.Queue"

        # A. Unsigned payload (missing envelope)
        job_unsigned = Job(
            id=str(uuid.uuid4()),
            user_id=user.id,
            capability_id="video.t2v",
            provider_id="comfyui",
            workflow_id="h3_t2v",
            workflow_version="1.0.0",
            status="QUEUED",
            content_mode="sfw",
        )
        db_session.add(job_unsigned)
        db_session.commit()

        await worker.enqueue_job({"job_id": job_unsigned.id, "user_id": user.id, "workflow_name": "h3_t2v"})
        res_unsigned = await worker.run_once(timeout=0.5, db=adapter)
        assert res_unsigned is not None
        assert res_unsigned.accepted is False
        assert res_unsigned.status == "REJECTED"
        assert res_unsigned.reason_code == "MISSING_ENVELOPE"

        # B. Tampered signature payload
        job_tampered = Job(
            id=str(uuid.uuid4()),
            user_id=user.id,
            capability_id="video.t2v",
            provider_id="comfyui",
            workflow_id="h3_t2v",
            workflow_version="1.0.0",
            status="QUEUED",
            content_mode="sfw",
        )
        db_session.add(job_tampered)
        db_session.commit()

        good_env = _signed_envelope(job_id=job_tampered.id, user_id=user.id, content_mode="sfw")
        bad_env = good_env.model_copy(update={"signature": "0" * 64})
        await worker.enqueue_job({"job_id": job_tampered.id, "user_id": user.id, "envelope": bad_env.model_dump()})
        res_tampered = await worker.run_once(timeout=0.5, db=adapter)
        assert res_tampered is not None
        assert res_tampered.accepted is False
        assert res_tampered.status == "REJECTED"

        # C. SFW envelope pushed for an UNRESTRICTED job (mode mismatch)
        job_mismatch = Job(
            id=str(uuid.uuid4()),
            user_id=user.id,
            capability_id="video.t2v",
            provider_id="comfyui",
            workflow_id="h3_t2v",
            workflow_version="1.0.0",
            status="QUEUED",
            content_mode="unrestricted",
        )
        db_session.add(job_mismatch)
        db_session.commit()

        sfw_env = _signed_envelope(job_id=job_mismatch.id, user_id=user.id, content_mode="sfw")
        await worker.enqueue_job({"job_id": job_mismatch.id, "user_id": user.id, "envelope": sfw_env.model_dump()})
        res_mismatch = await worker.run_once(timeout=0.5, db=adapter, expected_mode="unrestricted")
        assert res_mismatch is not None
        assert res_mismatch.accepted is False
        assert res_mismatch.status == "REJECTED"
        assert "MODE" in (res_mismatch.reason_code or "") or "unrestricted" in (res_mismatch.reason or "").lower()

        # Zero executions across all three rejected jobs
        assert len(exec_calls) == 0

        # D. Control: valid signed envelope with matching unrestricted mode completes cleanly
        job_valid = Job(
            id=str(uuid.uuid4()),
            user_id=user.id,
            capability_id="video.t2v",
            provider_id="comfyui",
            workflow_id="h3_t2v",
            workflow_version="1.0.0",
            status="QUEUED",
            content_mode="unrestricted",
        )
        db_session.add(job_valid)
        db_session.commit()

        unrestricted_env = _signed_envelope(
            job_id=job_valid.id,
            user_id=user.id,
            content_mode="unrestricted",
            age_verified=True,
        )
        await worker.enqueue_job(
            {"job_id": job_valid.id, "user_id": user.id, "envelope": unrestricted_env.model_dump()}
        )
        res_valid = await worker.run_once(timeout=0.5, db=adapter, expected_mode="unrestricted")
        assert res_valid is not None
        assert res_valid.accepted is True
        assert res_valid.status == "COMPLETED"
        assert exec_calls == [(job_valid.id, "unrestricted")]

        return job_unsigned.id, job_tampered.id, job_mismatch.id, job_valid.id

    id_u, id_t, id_m, id_v = asyncio.run(_run_scenarios())

    db_session.expire_all()
    for rejected_id in (id_u, id_t, id_m):
        j = db_session.get(Job, rejected_id)
        assert j is not None
        assert j.status == "REJECTED"
        assert j.failure_code
        audits = (
            db_session.execute(
                select(AuditEvent).where(
                    AuditEvent.job_id == rejected_id,
                    AuditEvent.event_type == "worker.envelope_rejected",
                )
            )
            .scalars()
            .all()
        )
        assert len(audits) == 1

    mismatch_audit = (
        db_session.execute(
            select(AuditEvent).where(
                AuditEvent.job_id == id_m,
                AuditEvent.event_type == "worker.envelope_rejected",
            )
        )
        .scalars()
        .one()
    )
    assert mismatch_audit.payload["expected_mode"] == "unrestricted"
    assert mismatch_audit.payload["envelope_mode"] == "sfw"

    j_valid = db_session.get(Job, id_v)
    assert j_valid is not None
    assert j_valid.status == "COMPLETED"
    completed_audits = (
        db_session.execute(
            select(AuditEvent).where(
                AuditEvent.job_id == id_v,
                AuditEvent.event_type == "worker.job_completed",
            )
        )
        .scalars()
        .all()
    )
    assert len(completed_audits) == 1
