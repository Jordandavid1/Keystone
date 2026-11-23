"""PR6 (ADR-005): Cross-modal Personas (§41), depicts lineage, full UX parity, and legacy SPA retirement."""

from __future__ import annotations

import json
import re
import shutil
import struct
import subprocess
import sys
import threading
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.src.auth.security import generate_token
from apps.api.src.db.models import (
    Asset,
    AssetRelationship,
    AuthorityDecision,
    Base,
    Persona,
    Project,
    Session as ChatSession,
    User,
)
from apps.api.src.db.session import get_db
from apps.api.src.routers import personas as personas_router
from apps.api.src.server import app
from services.comfy.src.video_ops import encode_frames_to_video

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def db_session():
    """Create an isolated in-memory SQLite database per test."""
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
    """Adapts a sync SQLAlchemy Session for async FastAPI dependencies."""

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
    base_color: Tuple[int, int, int] = (50, 130, 210),
) -> bytes:
    """Generate a valid RGB PNG image without external dependencies."""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(base_color) * width
    idat = zlib.compress(row * height)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _make_synthetic_mp4(out_path: Path, width: int = 64, height: int = 64, num_frames: int = 4) -> bytes:
    """Build a valid playable MP4 fixture via ffmpeg."""
    palette = [(200, 50, 50), (50, 200, 50), (50, 50, 200), (200, 180, 40)]
    frames = [_make_png_bytes(width, height, palette[i % len(palette)]) for i in range(num_frames)]
    encode_frames_to_video(frames, out_path, fps=12.0)
    return out_path.read_bytes()


def _extract_multipart_upload(body: bytes, content_type: str) -> Tuple[str, bytes]:
    match = re.search(r"boundary=([^\s;]+)", content_type or "")
    if not match:
        return "upload.bin", body
    boundary = match.group(1).strip('"').encode("utf-8")
    for part in body.split(b"--" + boundary):
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
        return (fn_match.group(1) if fn_match else "upload.bin"), file_bytes
    return "upload.bin", body


def _start_mock_comfy_server(*, png_output: bytes, mp4_output: Optional[bytes] = None):
    """Local HTTP mock ComfyUI server recording uploads and submitted workflows."""
    state: Dict[str, Any] = {
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
                    outputs = {
                        "148": {"videos": [{"filename": "generated.mp4", "subfolder": "", "type": "output"}]}
                    }
                else:
                    outputs = {
                        "9": {"images": [{"filename": "generated.png", "subfolder": "", "type": "output"}]}
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
                if ".mp4" in self.path and mp4_output is not None:
                    data, ctype = mp4_output, "video/mp4"
                else:
                    data, ctype = png_output, "image/png"
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
                orig_name, file_bytes = _extract_multipart_upload(body, self.headers.get("Content-Type", ""))
                assigned = f"upload-{uuid.uuid4().hex[:8]}-{orig_name}"
                state["uploads"][assigned] = file_bytes
                return self._json(200, {"name": assigned, "subfolder": "", "type": "input"})
            if path == "/prompt":
                payload = json.loads(body or b"{}")
                workflow = payload.get("prompt") or {}
                class_types = {
                    node.get("class_type") for node in workflow.values() if isinstance(node, dict)
                }
                is_video = bool(
                    {"VHS_VideoCombine", "MiniMaxH3ReferenceToVideo", "VHS_LoadVideo"} & class_types
                )
                pid = str(uuid.uuid4())
                state["prompts"][pid] = {"is_video": is_video, "workflow": workflow}
                state["submitted_workflows"].append(workflow)
                return self._json(200, {"prompt_id": pid, "number": 1})
            return self._json(404, {"error": "not found"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}", state


def _setup_user_and_client(
    db_session,
    *,
    content_mode: str = "sfw",
    age_verified: bool = True,
) -> Tuple[User, Project, Dict[str, str]]:
    user = User(
        id=str(uuid.uuid4()),
        email=f"pr6-{uuid.uuid4().hex[:8]}@example.com",
        password_hash="hashed",
        role="user",
        age_verified=age_verified,
        content_mode=content_mode,
    )
    project = Project(id=str(uuid.uuid4()), user_id=user.id, name="PR6 Studio Project")
    db_session.add_all([user, project])
    db_session.commit()
    token = generate_token(user.id)
    return user, project, {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# 1. test_persona_versioning_soft_delete_and_mature_isolation
# ---------------------------------------------------------------------------
def test_persona_versioning_soft_delete_and_mature_isolation(db_session, tmp_path, monkeypatch):
    """
    Create persona under unrestricted (mature=True, v=1) -> invisible in sfw GET /v1/personas;
    PATCH creates v=2 leaving v=1 immutable; DELETE sets deleted_at without breaking depicts edges.
    """
    png_bytes = _make_png_bytes(48, 48)
    server, comfy_url, _ = _start_mock_comfy_server(png_output=png_bytes)
    monkeypatch.setenv("COMFY_BASE_URL", comfy_url)
    monkeypatch.setenv("COMFY_URL", comfy_url)
    monkeypatch.setenv("COMFYUI_BASE_URL", comfy_url)
    monkeypatch.setenv("KEYSTONE_STORAGE_DIR", str(tmp_path / "storage"))

    user, project, headers = _setup_user_and_client(
        db_session, content_mode="unrestricted", age_verified=True
    )

    def _override_get_db():
        yield _AsyncSessionAdapter(db_session)

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)

        # 1) Create mature persona under unrestricted mode -> v=1, mature=True
        create_resp = client.post(
            "/v1/personas",
            json={
                "name": "Nyx Vance",
                "description": "Noir cybernetic investigator in charcoal trenchcoat",
                "project_id": project.id,
                "personality_traits": ["observant", "laconic"],
                "backstory": "Operates exclusively after midnight in Sector 9.",
                "voice_id": "voice_noir_01",
                "voice_name": "Nyx Noir",
            },
            headers=headers,
        )
        assert create_resp.status_code == 200, create_resp.text
        created = create_resp.json()["persona"]
        persona_id = created["id"]
        assert created["version"] == 1
        assert created["mature"] is True
        assert created["is_current"] is True
        assert created["deleted_at"] is None

        # 2) Switch to SFW mode -> mature persona is invisible in GET /v1/personas and GET /v1/personas/{id}
        mode_sfw = client.patch(
            "/v1/account/content-mode",
            json={"content_mode": "sfw"},
            headers=headers,
        )
        assert mode_sfw.status_code == 200, mode_sfw.text

        list_sfw = client.get("/v1/personas", headers=headers)
        assert list_sfw.status_code == 200, list_sfw.text
        assert list_sfw.json()["content_mode"] == "sfw"
        assert all(p["id"] != persona_id for p in list_sfw.json()["personas"])

        get_sfw = client.get(f"/v1/personas/{persona_id}", headers=headers)
        assert get_sfw.status_code == 404

        patch_sfw = client.patch(
            f"/v1/personas/{persona_id}",
            json={"description": "Should fail in SFW"},
            headers=headers,
        )
        assert patch_sfw.status_code == 403
        assert "MATURE_PERSONA_BLOCKED_IN_SFW" in patch_sfw.text

        # 3) Switch back to unrestricted -> visible, and PATCH creates immutable v=2 leaving v=1 untouched
        mode_unr = client.patch(
            "/v1/account/content-mode",
            json={"content_mode": "unrestricted"},
            headers=headers,
        )
        assert mode_unr.status_code == 200, mode_unr.text

        list_unr = client.get("/v1/personas", headers=headers)
        assert list_unr.status_code == 200, list_unr.text
        assert any(p["id"] == persona_id and p["version"] == 1 for p in list_unr.json()["personas"])

        patch_resp = client.patch(
            f"/v1/personas/{persona_id}",
            json={
                "description": "Upgraded chrome optics and rain-slicked trenchcoat",
                "personality_traits": ["observant", "stoic", "relentless"],
                "backstory": "Promoted to lead investigator in Sector 9.",
            },
            headers=headers,
        )
        assert patch_resp.status_code == 200, patch_resp.text
        v2_data = patch_resp.json()["persona"]
        assert v2_data["id"] == persona_id
        assert v2_data["version"] == 2
        assert v2_data["is_current"] is True
        assert v2_data["parent_persona_id"] == persona_id
        assert v2_data["mature"] is True
        assert v2_data["description"] == "Upgraded chrome optics and rain-slicked trenchcoat"
        assert patch_resp.json()["previous_version"] == 1

        # Verify v=1 row remains immutable in DB & via ?version=1
        rows = (
            db_session.execute(
                select(Persona).where(Persona.id == persona_id).order_by(Persona.version.asc())
            )
            .scalars()
            .all()
        )
        assert len(rows) == 2
        v1_row, v2_row = rows[0], rows[1]
        assert v1_row.version == 1
        assert v1_row.is_current is False
        assert v1_row.description == "Noir cybernetic investigator in charcoal trenchcoat"
        assert v1_row.backstory == "Operates exclusively after midnight in Sector 9."
        assert v2_row.version == 2
        assert v2_row.is_current is True
        assert v2_row.parent_persona_id == persona_id

        v1_get = client.get(f"/v1/personas/{persona_id}?version=1", headers=headers)
        assert v1_get.status_code == 200, v1_get.text
        assert v1_get.json()["persona"]["version"] == 1
        assert v1_get.json()["persona"]["description"] == "Noir cybernetic investigator in charcoal trenchcoat"

        # 4) Create an asset depicting v=2 before soft-deleting the persona
        gen_resp = client.post(
            "/v1/assets/generate",
            json={
                "project_id": project.id,
                "as": persona_id,
                "intent": "create",
                "prompt": "Standing beneath neon rain on a wet rooftop",
                "mode": "unrestricted",
            },
            headers=headers,
        )
        assert gen_resp.status_code == 200, gen_resp.text
        depicting_asset_id = gen_resp.json()["id"]
        assert gen_resp.json()["persona_id"] == persona_id
        assert gen_resp.json()["persona_version"] == 2
        assert gen_resp.json()["mature"] is True

        # 5) Soft-delete persona -> deleted_at set on all versions, excluded from queries, depicts edge preserved
        del_resp = client.delete(f"/v1/personas/{persona_id}", headers=headers)
        assert del_resp.status_code == 200, del_resp.text
        assert del_resp.json()["deleted_persona_id"] == persona_id
        assert del_resp.json()["deleted_at"]

        db_session.expire_all()
        rows_after = (
            db_session.execute(
                select(Persona).where(Persona.id == persona_id).order_by(Persona.version.asc())
            )
            .scalars()
            .all()
        )
        assert len(rows_after) == 2
        assert all(r.deleted_at is not None for r in rows_after)

        assert all(
            p["id"] != persona_id
            for p in client.get("/v1/personas", headers=headers).json()["personas"]
        )
        assert client.get(f"/v1/personas/{persona_id}", headers=headers).status_code == 404

        # Verify depicts lineage edge remains intact in DB and GET /v1/assets/{id}/lineage
        depicts_edges = (
            db_session.execute(
                select(AssetRelationship).where(
                    AssetRelationship.child_asset_id == depicting_asset_id,
                    AssetRelationship.relationship_type == "depicts",
                )
            )
            .scalars()
            .all()
        )
        assert len(depicts_edges) == 1
        assert depicts_edges[0].persona_id == persona_id
        assert depicts_edges[0].persona_version == 2
        assert depicts_edges[0].mature is True

        lineage_resp = client.get(f"/v1/assets/{depicting_asset_id}/lineage", headers=headers)
        assert lineage_resp.status_code == 200, lineage_resp.text
        lineage_depicts = lineage_resp.json()["depicts"]
        assert len(lineage_depicts) == 1
        assert lineage_depicts[0]["persona_id"] == persona_id
        assert lineage_depicts[0]["persona_version"] == 2
        assert lineage_depicts[0]["mature"] is True
    finally:
        app.dependency_overrides.clear()
        server.shutdown()


# ---------------------------------------------------------------------------
# 2. test_as_persona_cross_modal_and_depicts_lineage
# ---------------------------------------------------------------------------
def test_as_persona_cross_modal_and_depicts_lineage(db_session, tmp_path, monkeypatch):
    """
    Generate image/video/speech/cognition with `as=persona_id` -> injects persona sheet/descriptors/refs,
    propagates `mature`, and persists `AssetRelationship(relationship_type="depicts", persona_id=..., persona_version=..., mature=...)`.
    """
    png_bytes = _make_png_bytes(64, 64, (45, 115, 195))
    mp4_bytes = _make_synthetic_mp4(tmp_path / "persona_clip.mp4", width=64, height=64, num_frames=4)
    server, comfy_url, mock_state = _start_mock_comfy_server(png_output=png_bytes, mp4_output=mp4_bytes)
    monkeypatch.setenv("COMFY_BASE_URL", comfy_url)
    monkeypatch.setenv("COMFY_URL", comfy_url)
    monkeypatch.setenv("COMFYUI_BASE_URL", comfy_url)
    monkeypatch.setenv("KEYSTONE_STORAGE_DIR", str(tmp_path / "storage"))

    user, project, headers = _setup_user_and_client(
        db_session, content_mode="sfw", age_verified=True
    )
    session = ChatSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        project_id=project.id,
        title="Persona Cross-Modal Session",
    )
    db_session.add(session)
    db_session.commit()

    def _override_get_db():
        yield _AsyncSessionAdapter(db_session)

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)

        # Upload reference portrait for the persona
        up_ref = client.post(
            "/v1/assets/upload-file",
            files={"file": ("elena_ref.png", png_bytes, "image/png")},
            data={"project_id": project.id, "media_type": "image"},
            headers=headers,
        )
        assert up_ref.status_code == 200, up_ref.text
        ref_img_id = up_ref.json()["id"]

        # Create SFW persona (v=1, unbound voice to also verify §41.3 warning on speak)
        p_resp = client.post(
            "/v1/personas",
            json={
                "name": "Elena Solis",
                "description": "Silver-haired orbital botanist in cobalt EVA suit",
                "project_id": project.id,
                "reference_assets": [ref_img_id],
                "identity_adapter": "reference_set",
                "personality_traits": ["calm", "methodical"],
                "backstory": "Tends the orbital biosphere greenhouse.",
            },
            headers=headers,
        )
        assert p_resp.status_code == 200, p_resp.text
        persona_id = p_resp.json()["persona"]["id"]
        assert p_resp.json()["persona"]["version"] == 1
        assert p_resp.json()["persona"]["mature"] is False

        # A) Image generation with `as=persona_id`
        img_resp = client.post(
            "/v1/assets/generate",
            json={
                "project_id": project.id,
                "as": persona_id,
                "intent": "create",
                "prompt": "Inspecting bioluminescent ferns inside the dome",
                "mode": "sfw",
            },
            headers=headers,
        )
        assert img_resp.status_code == 200, img_resp.text
        img_data = img_resp.json()
        img_asset_id = img_data["id"]
        assert img_data["persona_id"] == persona_id
        assert img_data["persona_version"] == 1
        assert img_data["mature"] is False
        assert len(mock_state["uploads"]) >= 1
        assert img_data["reference_used"] is True

        img_wf_str = json.dumps(mock_state["submitted_workflows"][-1])
        assert "Elena Solis" in img_wf_str

        # B) Video generation (`t2v`) with `as=persona_id`
        vid_resp = client.post(
            "/v1/zencreator/generate",
            json={
                "tool": "t2v",
                "input": {
                    "prompt": "Slow dolly shot across the orbital greenhouse",
                    "as": persona_id,
                    "project_id": project.id,
                    "camera_motion": "dolly_in",
                    "motion_speed": 1.1,
                    "duration": 3,
                    "aspect_ratio": "16:9",
                },
            },
            headers=headers,
        )
        assert vid_resp.status_code == 200, vid_resp.text
        vid_data = vid_resp.json()
        assert vid_data["status"] == "succeeded"
        assert vid_data["persona_id"] == persona_id
        assert vid_data["persona_version"] == 1
        assert vid_data["mature"] is False
        vid_asset_id = vid_data["outputs"][0]["asset_id"]

        vid_wf_str = json.dumps(mock_state["submitted_workflows"][-1])
        assert "Elena Solis" in vid_wf_str

        # C) Persona speak with unbound voice -> warning header + depicts edge
        with patch.object(
            personas_router.elevenlabs_client,
            "generate_speech",
            return_value=(b"RIFF" + b"\x00" * 64, "audio/wav", {"duration_seconds": 1.1, "provider": "local_tts"}),
        ):
            speak_resp = client.post(
                f"/v1/personas/{persona_id}/speak",
                json={"text": "Greenhouse oxygen levels are nominal.", "project_id": project.id},
                headers=headers,
            )
        assert speak_resp.status_code == 200, speak_resp.text
        speak_data = speak_resp.json()
        audio_asset_id = speak_data["asset_id"]
        assert speak_data["persona_id"] == persona_id
        assert speak_data["persona_version"] == 1
        assert speak_data["warning"]
        assert speak_resp.headers.get("X-Keystone-Warning")

        # D) Cognition chat & analyze with `as=persona_id` inject [PERSONA SHEET]
        captured_messages: List[List[Dict[str, Any]]] = []

        async def _fake_cognition(**kwargs):
            captured_messages.append(kwargs["messages"])
            return {"content": "Elena responds calmly.", "model": "mock-qwen"}

        with patch(
            "apps.api.src.routers.cognition._invoke_live_cognition_completion",
            side_effect=_fake_cognition,
        ):
            chat_resp = client.post(
                "/v1/cognition/chat",
                json={
                    "project_id": project.id,
                    "session_id": session.id,
                    "as": persona_id,
                    "messages": [{"role": "user", "content": "Report status on sector 4."}],
                },
                headers=headers,
            )
            assert chat_resp.status_code == 200, chat_resp.text

            analyze_resp = client.post(
                "/v1/cognition/analyze",
                json={
                    "asset_id": img_asset_id,
                    "project_id": project.id,
                    "session_id": session.id,
                    "as": persona_id,
                    "prompt": "Inspect lighting and character continuity.",
                },
                headers=headers,
            )
            assert analyze_resp.status_code == 200, analyze_resp.text
            assert analyze_resp.json()["persona"]["id"] == persona_id

        assert len(captured_messages) == 2
        for msg_list in captured_messages:
            sys_text = msg_list[0]["content"]
            assert "[PERSONA SHEET]" in sys_text
            assert "Elena Solis" in sys_text

        # Verify persisted `depicts` edges for image, video, and audio assets
        for target_asset_id in (img_asset_id, vid_asset_id, audio_asset_id):
            rel = db_session.execute(
                select(AssetRelationship).where(
                    AssetRelationship.child_asset_id == target_asset_id,
                    AssetRelationship.relationship_type == "depicts",
                )
            ).scalar_one_or_none()
            assert rel is not None, f"Missing depicts edge for {target_asset_id}"
            assert rel.parent_asset_id is None
            assert rel.persona_id == persona_id
            assert rel.persona_version == 1
            assert rel.mature is False

            lin = client.get(f"/v1/assets/{target_asset_id}/lineage", headers=headers)
            assert lin.status_code == 200
            assert len(lin.json()["depicts"]) == 1
            assert lin.json()["depicts"][0]["persona_id"] == persona_id

        assert len(db_session.execute(select(AuthorityDecision)).scalars().all()) >= 5

        # E) Mature `as=persona_id` propagation & SFW blocking
        assert client.patch(
            "/v1/account/content-mode",
            json={"content_mode": "unrestricted"},
            headers=headers,
        ).status_code == 200

        m_resp = client.post(
            "/v1/personas",
            json={
                "name": "Kaelen Vex",
                "description": "Dark fantasy battle mage",
                "project_id": project.id,
            },
            headers=headers,
        )
        assert m_resp.status_code == 200, m_resp.text
        mature_persona_id = m_resp.json()["persona"]["id"]
        assert m_resp.json()["persona"]["mature"] is True

        # Generate video in unrestricted mode -> mature=True propagates to Asset and depicts edge
        m_vid = client.post(
            "/v1/zencreator/generate",
            json={
                "tool": "t2v",
                "input": {
                    "prompt": "Dramatic obsidian ritual hall pan",
                    "as": mature_persona_id,
                    "project_id": project.id,
                    "duration": 3,
                    "aspect_ratio": "16:9",
                },
            },
            headers=headers,
        )
        assert m_vid.status_code == 200, m_vid.text
        m_vid_id = m_vid.json()["outputs"][0]["asset_id"]
        m_asset = db_session.get(Asset, m_vid_id)
        assert m_asset is not None and m_asset.mature is True
        m_rel = db_session.execute(
            select(AssetRelationship).where(
                AssetRelationship.child_asset_id == m_vid_id,
                AssetRelationship.relationship_type == "depicts",
            )
        ).scalar_one_or_none()
        assert m_rel is not None
        assert m_rel.persona_id == mature_persona_id
        assert m_rel.persona_version == 1
        assert m_rel.mature is True

        # Switch to SFW mode -> using mature persona via `as` is blocked with 403
        assert client.patch(
            "/v1/account/content-mode",
            json={"content_mode": "sfw"},
            headers=headers,
        ).status_code == 200
        blocked = client.post(
            "/v1/assets/generate",
            json={
                "project_id": project.id,
                "as": mature_persona_id,
                "intent": "create",
                "prompt": "Portrait in SFW mode",
            },
            headers=headers,
        )
        assert blocked.status_code == 403
        assert "MATURE_PERSONA_BLOCKED_IN_SFW" in blocked.text
    finally:
        app.dependency_overrides.clear()
        server.shutdown()


# ---------------------------------------------------------------------------
# 3. test_nextjs_typecheck_and_legacy_spa_retired
# ---------------------------------------------------------------------------
def test_nextjs_typecheck_and_legacy_spa_retired():
    """
    Assert legacy SPA files (`apps/web/index.html`, `app.js`, `styles.css`, `legacy/`) are gone,
    `npx tsc --noEmit` in `apps/web` exits 0, and `verify_invariants.py` passes with `no_duplicate_engines` BLOCKING.
    """
    web_dir = ROOT / "apps" / "web"
    assert (web_dir / "app" / "page.tsx").is_file()
    assert not (web_dir / "index.html").exists()
    assert not (web_dir / "app.js").exists()
    assert not (web_dir / "styles.css").exists()
    assert not (web_dir / "legacy").exists()

    npx_bin = shutil.which("npx")
    assert npx_bin is not None, "npx executable not found on PATH"
    tsc_proc = subprocess.run(
        [npx_bin, "tsc", "--noEmit"],
        cwd=str(web_dir),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert tsc_proc.returncode == 0, f"tsc failed:\n{tsc_proc.stdout}\n{tsc_proc.stderr}"

    inv_proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_invariants.py"), "--json"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert inv_proc.returncode == 0, f"verify_invariants failed:\n{inv_proc.stdout}\n{inv_proc.stderr}"

    json_start = inv_proc.stdout.find("{")
    assert json_start != -1, f"Expected JSON output from verify_invariants.py, got:\n{inv_proc.stdout}"
    report = json.loads(inv_proc.stdout[json_start:])
    assert report["all_passed"] is True
    assert report["blocking_failures"] == []
    assert "no_duplicate_engines" in report["blocking_checks"]
    no_dup = report["checks"]["no_duplicate_engines"]
    assert no_dup["mode"] == "blocking"
    assert no_dup["valid"] is True
    assert no_dup["finding_count"] == 0
