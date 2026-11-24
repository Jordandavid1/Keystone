"""End-to-end verification of 30 / 60 / 100 / 120 Hz video generation across all KEYSTONE video generators."""

from __future__ import annotations

import json
import struct
import threading
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Tuple

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.src.auth.security import generate_token
from apps.api.src.db.models import Asset, Base, CreditAccount, User
from apps.api.src.db.session import get_db
from apps.api.src.server import app
from packages.contracts.src.models import ProposedAction
from services.authority.src.engine import authority_engine
from services.authority.src.evaluator import ParameterBoundaryEvaluator
from services.authority.src.rules import (
    VIDEO_DEFAULT_FPS,
    VIDEO_FPS_RANGE,
    VIDEO_MAX_FPS,
    VIDEO_SUPPORTED_FPS_PRESETS,
)
from services.comfy.src.client import (
    ComfyUIClient,
    build_minimax_h3_prompt_graph,
    build_video_workflow_graph,
    generate_minimax_h3_video,
    get_adapter,
)
from services.comfy.src.video_ops import (
    convert_video_bytes_fps,
    encode_frames_to_video,
    probe_video_metadata,
    stitch_video_segments,
)
from services.harness.src.envelope import EnvelopeEngine
from services.harness.src.evaluators.deterministic import validate_asset_bytes


def _make_png_bytes(width: int = 64, height: int = 64, rgb: Tuple[int, int, int] = (40, 120, 210)) -> bytes:
    row = b"\x00" + bytes(rgb) * width
    raw = row * height

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw))
        + _chunk(b"IEND", b"")
    )


def _make_mp4_bytes(tmp_path: Path, name: str = "src.mp4", fps: float = 24.0, num_frames: int = 6) -> bytes:
    frames = [_make_png_bytes(64, 64, (40 + idx * 12, 110, 200)) for idx in range(num_frames)]
    out_path = tmp_path / name
    encode_frames_to_video(frames, out_path, fps=fps)
    return out_path.read_bytes()


class _AsyncSessionAdapter:
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


@pytest.fixture()
def api_client(db_session):
    def _override_get_db():
        yield _AsyncSessionAdapter(db_session)

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


def _start_local_comfy_server(mp4_bytes: bytes) -> Tuple[ThreadingHTTPServer, str]:
    class _Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_bytes(self, status_code: int, content_type: str, payload: bytes) -> None:
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Connection", "close")
            self.end_headers()
            if payload:
                self.wfile.write(payload)
            self.wfile.flush()

        def do_GET(self):
            if self.path.startswith("/system_stats"):
                body = json.dumps({"system": {"os": "posix"}, "devices": [{"name": "test-gpu"}]}).encode()
                self._send_bytes(200, "application/json", body)
            elif self.path.startswith("/history/"):
                pid = self.path.split("/history/", 1)[1].split("?")[0]
                body = json.dumps(
                    {
                        pid: {
                            "status": {"completed": True},
                            "outputs": {
                                "148": {
                                    "videos": [{"filename": f"{pid}.mp4", "subfolder": "", "type": "output"}]
                                }
                            },
                        }
                    }
                ).encode()
                self._send_bytes(200, "application/json", body)
            elif self.path.startswith("/view"):
                self._send_bytes(200, "video/mp4", mp4_bytes)
            else:
                self._send_bytes(404, "text/plain", b"")

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            remaining = length
            while remaining > 0:
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            if self.path.startswith("/upload/"):
                body = json.dumps({"name": "uploaded_ref.png"}).encode()
            elif self.path.startswith("/prompt"):
                body = json.dumps({"prompt_id": f"pid_{uuid.uuid4().hex[:10]}"}).encode()
            else:
                self._send_bytes(404, "text/plain", b"")
                return
            self._send_bytes(200, "application/json", body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address
    return server, f"http://{host}:{port}"


def test_authority_allows_30_60_100_120hz_and_clamps_above_120():
    assert VIDEO_FPS_RANGE == (8, 120)
    assert VIDEO_MAX_FPS == 120
    assert VIDEO_DEFAULT_FPS == 30
    assert VIDEO_SUPPORTED_FPS_PRESETS == (30, 60, 100, 120)

    for cap in ("video.t2v", "video.i2v", "video.minimax_h3_ref2va", "creative.video_wan"):
        for hz in (30, 60, 100, 120):
            params: Dict[str, Any] = {"prompt": "Cinematic camera pan", "fps": hz}
            if cap == "video.i2v":
                params["input_asset_id"] = str(uuid.uuid4())
            action = ProposedAction(
                action_type="animate",
                capability=cap,
                parameters=params,
                rationale=f"Render at {hz}Hz",
                estimated_credits=5,
            )
            res = ParameterBoundaryEvaluator.evaluate(action)
            assert res.passed is True
            assert res.sanitized_arguments["fps"] == hz
            assert not any("fps" in code for code in res.reason_codes)

    alias_action = ProposedAction(
        action_type="animate",
        capability="video.t2v",
        parameters={"prompt": "Smooth motion", "frame_rate": "120Hz"},
        rationale="Alias string parsing",
        estimated_credits=5,
    )
    alias_res = ParameterBoundaryEvaluator.evaluate(alias_action)
    assert alias_res.passed is True
    assert alias_res.sanitized_arguments["fps"] == 120

    over_action = ProposedAction(
        action_type="animate",
        capability="video.t2v",
        parameters={"prompt": "Too fast", "fps": 240},
        rationale="Clamp check",
        estimated_credits=5,
    )
    over_res = ParameterBoundaryEvaluator.evaluate(over_action)
    assert over_res.passed is True
    assert over_res.sanitized_arguments["fps"] == 120
    assert any("OUT_OF_BOUNDS_PARAMETER" in code and "fps" in code for code in over_res.reason_codes)


def test_ffmpeg_converts_and_stitches_30_60_100_120hz_mp4(tmp_path: Path):
    src_bytes = _make_mp4_bytes(tmp_path, "base_24.mp4", fps=24.0, num_frames=6)
    seg_a = tmp_path / "seg_a.mp4"
    seg_b = tmp_path / "seg_b.mp4"
    seg_a.write_bytes(src_bytes)
    seg_b.write_bytes(src_bytes)

    for hz in (30, 60, 100, 120):
        converted = convert_video_bytes_fps(src_bytes, hz)
        out_file = tmp_path / f"converted_{hz}.mp4"
        out_file.write_bytes(converted)
        meta = probe_video_metadata(out_file)
        assert abs(meta["fps"] - float(hz)) <= 0.5
        assert meta["duration"] > 0.0
        det = validate_asset_bytes(converted, "video", "video/mp4")
        assert det.verdict == "pass"

    stitched_120 = tmp_path / "stitched_120.mp4"
    stitch_video_segments([seg_a, seg_b], stitched_120, target_fps=120)
    stitched_meta = probe_video_metadata(stitched_120)
    assert abs(stitched_meta["fps"] - 120.0) <= 0.5
    assert validate_asset_bytes(stitched_120.read_bytes(), "video", "video/mp4").verdict == "pass"


def test_all_video_workflow_templates_and_adapters_support_up_to_120hz():
    for variant in ("t2v", "i2v", "ref2v", "v2v", "video_upscale"):
        for hz in (30, 60, 100, 120):
            graph = build_video_workflow_graph(
                variant,
                "Neon rain tracking shot",
                image_name="ref.png",
                video_name="src.mp4",
                fps=hz,
            )
            combine_nodes = [
                n for n in graph.values() if isinstance(n, dict) and n.get("class_type") == "VHS_VideoCombine"
            ]
            assert combine_nodes, f"Missing VHS_VideoCombine node for {variant}"
            assert all(node["inputs"]["frame_rate"] == hz for node in combine_nodes)

    h3_graph = build_minimax_h3_prompt_graph("High framerate shot", ref_image_filename="ref.png", fps=120)
    assert h3_graph["148"]["inputs"]["frame_rate"] == 120

    for adapter_name in ("wan_i2v", "wan_t2v", "minimax_h3"):
        adapter = get_adapter(adapter_name)
        manifest = adapter.get_manifest()
        assert "fps" in manifest.parameters
        assert manifest.parameters["fps"].maximum == 120
        assert manifest.parameters["fps"].enum == [30, 60, 100, 120]
        exec_out = adapter.execute({"prompt": "Dynamic camera sweep", "fps": 120})
        combine = [
            n for n in exec_out["graph"].values() if isinstance(n, dict) and n.get("class_type") == "VHS_VideoCombine"
        ]
        assert combine and combine[0]["inputs"]["frame_rate"] == 120


def test_comfy_video_generators_produce_real_100_120hz_outputs(tmp_path: Path, monkeypatch):
    base_mp4 = _make_mp4_bytes(tmp_path, "remote_24.mp4", fps=24.0, num_frames=6)
    server, base_url = _start_local_comfy_server(base_mp4)
    monkeypatch.setenv("COMFY_BASE_URL", base_url)
    monkeypatch.setenv("KEYSTONE_COMFY_URL", base_url)

    try:
        client = ComfyUIClient()
        ref_png = _make_png_bytes(64, 64, (90, 140, 210))
        ref_asset_id = str(uuid.uuid4())
        for idx, variant in enumerate(("t2v", "i2v", "ref2v", "v2v", "video_upscale")):
            cap = "upscale.clarity" if variant == "video_upscale" else ("video.i2v" if variant == "i2v" else "video.t2v")
            act_type = "upscale" if variant == "video_upscale" else "animate"
            params: Dict[str, Any] = {"prompt": "Smooth shot", "fps": 120}
            if cap in ("video.i2v", "upscale.clarity"):
                params["input_asset_id"] = ref_asset_id
            if cap == "upscale.clarity":
                params["scale_factor"] = 2
            decision = authority_engine.evaluate(
                action=ProposedAction(
                    action_type=act_type,
                    capability=cap,
                    parameters=params,
                    rationale="Verify 120Hz workflow",
                    estimated_credits=5,
                ),
                credit_balance=500,
            )
            assert decision.decision == "ALLOW", decision.reason_codes
            env = EnvelopeEngine.create_envelope(
                decision=decision,
                job_id=f"job_fps_{variant}_{idx}",
                user_id="usr_fps_test",
                workflow_id=variant,
                workflow_version="2.0.0",
                compiled_prompt_id=f"cp_{variant}_{idx}",
                arguments=params,
                intent=act_type,
                content_mode="sfw",
            )
            res = client.execute_video_workflow(
                env,
                variant,
                "Smooth tracking shot at 120Hz",
                expected_mode="sfw",
                ref_image_bytes=ref_png if variant in ("i2v", "ref2v") else None,
                ref_video_bytes=base_mp4 if variant in ("v2v", "video_upscale") else None,
                fps=120,
            )
            assert res["fps"] == 120
            out_path = tmp_path / f"exec_{variant}_120.mp4"
            out_path.write_bytes(res["bytes"])
            meta = probe_video_metadata(out_path)
            assert abs(meta["fps"] - 120.0) <= 0.5
            assert validate_asset_bytes(res["bytes"], "video", "video/mp4").verdict == "pass"

        for hz in (100, 120):
            h3_res = generate_minimax_h3_video(
                "H3 high refresh test",
                ref_image_bytes=ref_png,
                fps=hz,
            )
            assert h3_res["fps"] == hz
            h3_path = tmp_path / f"h3_{hz}.mp4"
            h3_path.write_bytes(h3_res["bytes"])
            assert abs(probe_video_metadata(h3_path)["fps"] - float(hz)) <= 0.5
    finally:
        server.shutdown()
        server.server_close()


def test_http_routes_support_and_persist_120hz_video(api_client: TestClient, db_session, tmp_path: Path, monkeypatch):
    base_mp4 = _make_mp4_bytes(tmp_path, "api_src_24.mp4", fps=24.0, num_frames=6)
    server, base_url = _start_local_comfy_server(base_mp4)
    monkeypatch.setenv("COMFY_BASE_URL", base_url)
    monkeypatch.setenv("KEYSTONE_COMFY_URL", base_url)

    try:
        pol_res = api_client.get("/v1/authority/policies")
        assert pol_res.status_code == 200
        pol_data = pol_res.json()
        assert pol_data["video_max_fps"] == 120
        assert pol_data["video_supported_fps"] == [30, 60, 100, 120]

        status_res = api_client.get("/v1/creative/comfy/status")
        assert status_res.status_code == 200
        status_data = status_res.json()
        assert status_data["max_video_fps"] == 120
        assert status_data["supported_video_fps"] == [30, 60, 100, 120]

        user = User(
            id=str(uuid.uuid4()),
            email=f"fps120_{uuid.uuid4().hex[:8]}@keystone.local",
            role="user",
            content_mode="sfw",
            age_verified=True,
            is_active=True,
        )
        db_session.add(user)
        db_session.add(CreditAccount(id=str(uuid.uuid4()), user_id=user.id, balance=500))
        db_session.commit()
        token = generate_token(user_id=user.id)
        headers = {"Authorization": f"Bearer {token}"}

        t2v_res = api_client.post(
            "/v1/zencreator/generate",
            headers=headers,
            json={
                "tool": "text_to_video",
                "input": {
                    "prompt": "High framerate city flythrough",
                    "duration": 2,
                    "fps": 120,
                    "aspect_ratio": "16:9",
                },
            },
        )
        assert t2v_res.status_code == 200, t2v_res.text
        t2v_asset_id = t2v_res.json()["outputs"][0]["asset_id"]
        t2v_asset = db_session.query(Asset).filter(Asset.id == t2v_asset_id).one()
        assert abs(float((t2v_asset.metadata_ or {}).get("fps") or 0) - 120.0) <= 0.5

        t2v_meta = api_client.get(f"/v1/assets/{t2v_asset_id}", headers=headers)
        assert t2v_meta.status_code == 200, t2v_meta.text
        dl_t2v = api_client.get(t2v_meta.json()["download_url"], headers=headers)
        assert dl_t2v.status_code == 200, dl_t2v.text
        dl_path = tmp_path / "dl_t2v_120.mp4"
        dl_path.write_bytes(dl_t2v.content)
        assert abs(probe_video_metadata(dl_path)["fps"] - 120.0) <= 0.5

        ext_res = api_client.post(
            "/v1/zencreator/generate",
            headers=headers,
            json={
                "tool": "extend",
                "input": {
                    "prompt": "Continue flythrough seamlessly",
                    "video_asset_id": t2v_asset_id,
                    "duration": 2,
                    "fps": 120,
                },
            },
        )
        assert ext_res.status_code == 200, ext_res.text
        ext_asset_id = ext_res.json()["outputs"][0]["asset_id"]
        ext_asset = db_session.query(Asset).filter(Asset.id == ext_asset_id).one()
        assert abs(float((ext_asset.metadata_ or {}).get("fps") or 0) - 120.0) <= 0.5

        assets_gen = api_client.post(
            "/v1/assets/generate",
            headers=headers,
            json={
                "prompt": "Cinema crane shot",
                "mode": "minimax_h3",
                "duration_seconds": 2,
                "fps": 120,
                "resolution": "720p",
            },
        )
        assert assets_gen.status_code == 200, assets_gen.text
        ag_id = assets_gen.json()["id"]
        ag_asset = db_session.query(Asset).filter(Asset.id == ag_id).one()
        assert (ag_asset.metadata_ or {}).get("fps") == 120
        ag_meta = api_client.get(f"/v1/assets/{ag_id}", headers=headers)
        assert ag_meta.status_code == 200, ag_meta.text
        dl_ag = api_client.get(ag_meta.json()["download_url"], headers=headers)
        assert dl_ag.status_code == 200, dl_ag.text
        ag_path = tmp_path / "dl_ag_120.mp4"
        ag_path.write_bytes(dl_ag.content)
        assert abs(probe_video_metadata(ag_path)["fps"] - 120.0) <= 0.5
    finally:
        server.shutdown()
        server.server_close()
