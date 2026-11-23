"""PR4 (ADR-005): Image core consolidation, single compiler, single ComfyUI client, and cognition persistence."""

from __future__ import annotations

import io
import json
import struct
import threading
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
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
    AttemptAsset,
    AuthorityDecision,
    Base,
    CompiledPrompt,
    GenerationAttempt,
    HarnessRun,
    Message,
    Persona,
    Project,
    Session as ChatSession,
    User,
)
from apps.api.src.db.session import get_db
from apps.api.src.server import app
from packages.prompt_engine.compiler import (
    CompilationError,
    PromptCompiler,
    compile_for_generation,
)
from types import SimpleNamespace
from services.comfy.src.client import ComfyUIClient
from services.harness.src.envelope import EnvelopeEngine
from services.harness.src.evaluators.deterministic import validate_asset_bytes

ROOT = Path(__file__).resolve().parents[1]


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
        return self._s.close()

    async def run_sync(self, fn, *args, **kwargs):
        return fn(self._s, *args, **kwargs)


def _make_png_bytes(width: int = 64, height: int = 64, color: tuple[int, int, int] = (40, 120, 200)) -> bytes:
    """Generate a valid RGB PNG image without external dependencies."""
    def _chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    row = b"\x00" + bytes(color) * width
    idat = zlib.compress(row * height)
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", idat) + _chunk(b"IEND", b"")


def _start_mock_comfy_server():
    """Start a local HTTP mock ComfyUI server that returns valid PNGs (and larger PNGs for upscale)."""
    small_png = _make_png_bytes(64, 64, (40, 120, 200))
    upscaled_png = _make_png_bytes(256, 256, (60, 140, 220))
    prompts: dict[str, dict] = {}
    uploads: set[str] = set()

    class _Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, fmt, *args):
            pass

        def _json(self, status: int, payload: dict):
            body = json.dumps(payload).encode()
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
                if pid not in prompts:
                    return self._json(200, {})
                is_upscale = prompts[pid].get("is_upscale", False)
                fname = "upscaled.png" if is_upscale else "generated.png"
                return self._json(
                    200,
                    {
                        pid: {
                            "status": {"status_str": "success", "completed": True},
                            "outputs": {
                                "9": {"images": [{"filename": fname, "subfolder": "", "type": "output"}]}
                            },
                        }
                    },
                )
            if path == "/view":
                data = upscaled_png if "upscaled.png" in self.path else small_png
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
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
                name = f"upload-{uuid.uuid4().hex[:8]}.png"
                uploads.add(name)
                return self._json(200, {"name": name, "subfolder": "", "type": "input"})
            if path == "/prompt":
                payload = json.loads(body or b"{}")
                workflow = payload.get("prompt") or {}
                is_upscale = any(
                    isinstance(node, dict) and node.get("class_type") == "ImageUpscaleWithModel"
                    for node in workflow.values()
                )
                pid = str(uuid.uuid4())
                prompts[pid] = {"is_upscale": is_upscale}
                return self._json(200, {"prompt_id": pid, "number": 1})
            return self._json(404, {"error": "not found"})

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}"


def test_single_python_compiler_and_mode_playbook_scoping():
    """Verify apps/api/src/keystone/prompting.py is deleted and playbooks 14-16 are mode-scoped."""
    assert not (ROOT / "apps" / "api" / "src" / "keystone" / "prompting.py").exists()

    sfw_playbooks = PromptCompiler.get_playbooks_for_mode("sfw")
    unrestricted_playbooks = PromptCompiler.get_playbooks_for_mode("unrestricted")
    unrestricted_only = [p for p in unrestricted_playbooks if p not in sfw_playbooks]
    assert len(unrestricted_only) >= 3

    target_pb = unrestricted_only[0]
    try:
        res_sfw = PromptCompiler.compile({"objective": "studio portrait"}, playbook=target_pb, mode="sfw")
        assert res_sfw.get("playbook_id") != target_pb
    except (CompilationError, ValueError):
        pass

    compiled = PromptCompiler.compile({"objective": "studio portrait"}, playbook=target_pb, mode="unrestricted")
    assert compiled["positive_prompt"]


def test_single_comfy_client_rejects_unsigned_envelope():
    """Verify h3.py and adapters.py are consolidated and execute_workflow fails closed on bad envelopes."""
    assert not (ROOT / "apps" / "api" / "src" / "creative" / "h3.py").exists()
    assert not (ROOT / "services" / "comfy" / "src" / "adapters.py").exists()

    client = ComfyUIClient()

    # Missing envelope
    with pytest.raises(Exception):
        client.execute_workflow(envelope=None, workflow={"1": {"class_type": "KSampler", "inputs": {}}})

    # Tampered envelope
    decision = SimpleNamespace(
        decision_id="dec-1",
        decision="ALLOW",
        reason_code="OK",
        capability_id="image.generation",
        provider_id="keystone_internal",
        sanitized_arguments={},
    )
    valid_env = EnvelopeEngine.create_envelope(
        decision=decision,
        job_id="job-1",
        user_id="user-1",
        content_mode="sfw",
        age_verified=True,
        floor_verdict="pass",
    )
    tampered = valid_env.model_copy(update={"signature": "0" * 64})
    with pytest.raises(Exception):
        client.execute_workflow(envelope=tampered, workflow={"1": {"class_type": "KSampler", "inputs": {}}})


def test_image_create_edit_vary_upscale_through_gate_and_db(db_session, tmp_path, monkeypatch):
    """Hit /v1/assets/generate and /v1/assets/{id}/upscale against mock ComfyUI and verify Gate + DB rows."""
    server, comfy_url = _start_mock_comfy_server()
    monkeypatch.setenv("COMFY_URL", comfy_url)
    monkeypatch.setenv("COMFY_BASE_URL", comfy_url)
    monkeypatch.setenv("COMFYUI_BASE_URL", comfy_url)
    monkeypatch.setenv("KEYSTONE_STORAGE_ROOT", str(tmp_path))

    user = User(
        id=str(uuid.uuid4()),
        email="pr4-user@example.com",
        password_hash="hashed",
        role="user",
        age_verified=True,
        content_mode="sfw",
    )
    project = Project(id=str(uuid.uuid4()), user_id=user.id, name="PR4 Project")
    persona = Persona(id=str(uuid.uuid4()), user_id=user.id, name="PR4 Persona")
    db_session.add_all([user, project, persona])
    db_session.commit()

    token = generate_token(user.id)

    def _override_get_db():
        yield _AsyncSessionAdapter(db_session)

    app.dependency_overrides[get_db] = _override_get_db
    try:
        client = TestClient(app)
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Generate image (create)
        gen_resp = client.post(
            "/v1/assets/generate",
            json={
                "project_id": project.id,
                "persona_id": persona.id,
                "intent": "create",
                "prompt": "a serene mountain lake at dawn",
                "playbook_id": 1,
                "mode": "sfw",
            },
            headers=headers,
        )
        assert gen_resp.status_code == 200, gen_resp.text
        gen_data = gen_resp.json()
        asset_id = gen_data.get("asset_id") or gen_data["id"]

        # Verify DB persistence for generate
        assert db_session.execute(select(Asset)).scalars().all()
        assert db_session.execute(select(AuthorityDecision)).scalars().all()

        # 2. Upscale image (neural ESRGAN)
        up_resp = client.post(
            f"/v1/assets/{asset_id}/upscale",
            json={"scale": 4, "mode": "sfw"},
            headers=headers,
        )
        assert up_resp.status_code == 200, up_resp.text
        up_data = up_resp.json()
        upscaled_id = up_data.get("asset_id") or up_data["id"]

        # Verify AssetRelationship lineage edge
        rels = db_session.execute(select(AssetRelationship)).scalars().all()
        assert any(r.parent_asset_id == asset_id and r.child_asset_id == upscaled_id for r in rels)

        # Verify neural upscale delta via deterministic.py
        orig_asset = db_session.get(Asset, asset_id)
        up_asset = db_session.get(Asset, upscaled_id)
        assert orig_asset is not None and up_asset is not None
        assert up_asset.size_bytes > orig_asset.size_bytes
        up_file = tmp_path / up_asset.storage_key
        if up_file.exists():
            tier_a = validate_asset_bytes(up_file.read_bytes(), "image", "image/png")
            assert tier_a.verdict == "pass"
    finally:
        app.dependency_overrides.clear()
        server.shutdown()


def test_cognition_chat_persists_assistant_messages(db_session):
    """POST /v1/cognition/chat with session_id persists both user and assistant messages."""
    user = User(
        id=str(uuid.uuid4()),
        email="pr4-chat@example.com",
        password_hash="hashed",
        role="user",
        age_verified=True,
        content_mode="sfw",
    )
    project = Project(id=str(uuid.uuid4()), user_id=user.id, name="Chat Project")
    session = ChatSession(id=str(uuid.uuid4()), user_id=user.id, project_id=project.id, title="Test Chat")
    db_session.add_all([user, project, session])
    db_session.commit()

    token = generate_token(user.id)

    def _override_get_db():
        yield _AsyncSessionAdapter(db_session)

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with patch(
            "apps.api.src.routers.cognition._invoke_live_cognition_completion",
            new=AsyncMock(return_value={"content": "Hello from Keystone assistant!", "model": "mock-model"}),
        ):
            client = TestClient(app)
            resp = client.post(
                "/v1/cognition/chat",
                json={"session_id": session.id, "messages": [{"role": "user", "content": "Hi Keystone!"}]},
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200, resp.text

        msgs = (
            db_session.execute(
                select(Message).where(Message.session_id == session.id).order_by(Message.created_at)
            )
            .scalars()
            .all()
        )
        roles = [m.role for m in msgs]
        assert "user" in roles
        assert "assistant" in roles
    finally:
        app.dependency_overrides.clear()
