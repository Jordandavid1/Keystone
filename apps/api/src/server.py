"""
KEYSTONE API — Wave 1 vertical shell (Bible §17, §19, §25, §33).

Register -> project -> session -> upload asset -> message -> job -> streamed
job events -> persisted state the workspace can recover after a refresh.

Persistence is SQLite under state/keystone.db. Uploaded binaries live under
state/assets/. No generated media is fabricated here: jobs record their state
transitions and stop at COMPLETED with no output asset until the Wave 5
creative fabric is wired to a real runtime.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import sqlite3
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel, Field


def _load_dotenv() -> None:
    """Load KEYSTONE_* settings from the repo-root .env without overriding the shell."""
    env_file = Path(__file__).resolve().parents[3] / ".env"
    if not env_file.is_file():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()

from apps.api.src.creative import h3  # noqa: E402  (reads the env loaded above)

ROOT = Path(__file__).resolve().parents[3]
STATE_DIR = Path(os.getenv("KEYSTONE_STATE_DIR", ROOT / "state"))
ASSET_DIR = STATE_DIR / "assets"
DB_PATH = Path(os.getenv("KEYSTONE_DB", STATE_DIR / "keystone.db"))
WEB_DIR = ROOT / "apps" / "web"

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
ALLOWED_PREFIXES = ("image/", "video/")
GENERATION_INTENTS = {"create", "edit", "animate"}

JOB_STATES = [
    "CREATED", "VALIDATING", "PLANNING", "AUTHORIZING", "QUEUED",
    "RUNNING", "VALIDATING_OUTPUT", "RETRY_PENDING", "REPLAN_REQUIRED",
    "COMPLETED", "FAILED", "CANCELLED", "REJECTED",
]
TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED", "REJECTED"}

# Bible §25 exact customer progress language, in order.
PROGRESS_STAGES = [
    ("VALIDATING", "Understanding your request"),
    ("PLANNING", "Planning the generation"),
    ("AUTHORIZING", "Preparing the workflow"),
    ("RUNNING", "Creating"),
    ("VALIDATING_OUTPUT", "Checking the result"),
    ("COMPLETED", "Finishing"),
]


# --------------------------------------------------------------------- storage

def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tokens (
                token TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS assets (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                project_id TEXT REFERENCES projects(id) ON DELETE SET NULL,
                filename TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                media_type TEXT NOT NULL,
                byte_size INTEGER NOT NULL,
                storage_path TEXT NOT NULL,
                parent_asset_id TEXT REFERENCES assets(id) ON DELETE SET NULL,
                relationship TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
                asset_id TEXT REFERENCES assets(id) ON DELETE SET NULL,
                intent TEXT NOT NULL,
                prompt TEXT NOT NULL,
                state TEXT NOT NULL,
                detail TEXT,
                output_asset_id TEXT,
                reference_ids TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS job_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                state TEXT NOT NULL,
                label TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        # Additive migration for databases created before lineage and outputs.
        for table, column, decl in (
            ("assets", "parent_asset_id", "TEXT"),
            ("assets", "relationship", "TEXT"),
            ("jobs", "output_asset_id", "TEXT"),
            ("jobs", "reference_ids", "TEXT"),
        ):
            existing = {row["name"] for row in db.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")


def hash_password(password: str, salt: Optional[bytes] = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return f"pbkdf2_sha256$200000${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iterations, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return secrets.compare_digest(digest.hex(), digest_hex)
    except Exception:
        return False


# ------------------------------------------------------------------------ app

@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="KEYSTONE API",
    version="2.0.0-alpha.0",
    description="Prompt-intelligence and creative orchestration platform. Wave 1 shell per Bible §33.",
    lifespan=lifespan,
)


# --------------------------------------------------------------------- models

class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: str
    password: str


class ProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class SessionRequest(BaseModel):
    project_id: str


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    intent: str = Field("create")
    asset_ids: List[str] = Field(default_factory=list)


# ----------------------------------------------------------------------- auth

def current_user(authorization: Optional[str] = Header(None), token: Optional[str] = Query(None)) -> Dict[str, Any]:
    raw = None
    if authorization and authorization.lower().startswith("bearer "):
        raw = authorization[7:].strip()
    elif token:
        raw = token.strip()
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "AUTH_REQUIRED: send Authorization: Bearer <token>")

    with connect() as db:
        row = db.execute(
            "SELECT u.id, u.email FROM tokens t JOIN users u ON u.id = t.user_id WHERE t.token = ?",
            (raw,),
        ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "AUTH_INVALID: unknown or expired token")
    return {"id": row["id"], "email": row["email"]}


def issue_token(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("INSERT INTO tokens (token, user_id, created_at) VALUES (?, ?, ?)", (token, user_id, now()))
    return token


@app.post("/v1/auth/register", tags=["Authentication"], status_code=201)
def register(req: RegisterRequest) -> Dict[str, Any]:
    email = req.email.strip().lower()
    user_id = str(uuid.uuid4())
    with connect() as db:
        if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise HTTPException(status.HTTP_409_CONFLICT, "EMAIL_TAKEN: that email already has an account")
        db.execute(
            "INSERT INTO users (id, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
            (user_id, email, hash_password(req.password), now()),
        )
    return {"token": issue_token(user_id), "user": {"id": user_id, "email": email}}


@app.post("/v1/auth/login", tags=["Authentication"])
def login(req: LoginRequest) -> Dict[str, Any]:
    email = req.email.strip().lower()
    with connect() as db:
        row = db.execute("SELECT id, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "INVALID_CREDENTIALS: email or password is wrong")
    return {"token": issue_token(row["id"]), "user": {"id": row["id"], "email": email}}


@app.get("/v1/me", tags=["Authentication"])
def me(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    return user


# ------------------------------------------------------------------- projects

@app.post("/v1/projects", tags=["Projects"], status_code=201)
def create_project(req: ProjectRequest, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    project_id = str(uuid.uuid4())
    with connect() as db:
        db.execute(
            "INSERT INTO projects (id, user_id, name, created_at) VALUES (?, ?, ?, ?)",
            (project_id, user["id"], req.name.strip(), now()),
        )
    return {"id": project_id, "name": req.name.strip(), "created_at": now()}


@app.get("/v1/projects", tags=["Projects"])
def list_projects(user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    with connect() as db:
        rows = db.execute(
            "SELECT id, name, created_at FROM projects WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
        assets = db.execute(
            "SELECT id, filename, mime_type, media_type, byte_size, created_at FROM assets "
            "WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
        sessions = db.execute(
            "SELECT id, project_id, created_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC",
            (user["id"],),
        ).fetchall()
    return {
        "projects": [dict(r) for r in rows],
        "assets": [dict(r) for r in assets],
        "sessions": [dict(r) for r in sessions],
    }


# ------------------------------------------------------------------- sessions

@app.post("/v1/sessions", tags=["Sessions"], status_code=201)
def create_session(req: SessionRequest, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    with connect() as db:
        project = db.execute(
            "SELECT id FROM projects WHERE id = ? AND user_id = ?", (req.project_id, user["id"])
        ).fetchone()
        if not project:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND")
        session_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO sessions (id, project_id, user_id, created_at) VALUES (?, ?, ?, ?)",
            (session_id, req.project_id, user["id"], now()),
        )
    return {"id": session_id, "project_id": req.project_id, "created_at": now()}


@app.get("/v1/sessions/{session_id}/messages", tags=["Sessions"])
def list_messages(session_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    with connect() as db:
        session = db.execute(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?", (session_id, user["id"])
        ).fetchone()
        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND")
        rows = db.execute(
            "SELECT id, role, content, created_at FROM messages WHERE session_id = ? ORDER BY created_at",
            (session_id,),
        ).fetchall()
    return {"messages": [dict(r) for r in rows]}


# --------------------------------------------------------------------- assets

def require_asset(db: sqlite3.Connection, asset_id: str, user_id: str) -> sqlite3.Row:
    row = db.execute(
        "SELECT * FROM assets WHERE id = ? AND user_id = ?", (asset_id, user_id)
    ).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ASSET_NOT_FOUND")
    return row


@app.post("/v1/assets/upload", tags=["Assets"], status_code=201)
async def upload_asset(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    mime = (file.content_type or "").lower()
    if not mime.startswith(ALLOWED_PREFIXES):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, f"UNSUPPORTED_MEDIA: {mime or 'unknown'}")

    payload = await file.read()
    if not payload:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "EMPTY_FILE")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "FILE_TOO_LARGE: 50 MB maximum")

    asset_id = str(uuid.uuid4())
    safe_name = Path(file.filename or "upload").name.replace("\\", "_").replace("/", "_")
    target_dir = ASSET_DIR / asset_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / safe_name
    target.write_bytes(payload)

    media_type = "video" if mime.startswith("video/") else "image"
    with connect() as db:
        if project_id:
            owned = db.execute(
                "SELECT 1 FROM projects WHERE id = ? AND user_id = ?", (project_id, user["id"])
            ).fetchone()
            if not owned:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "PROJECT_NOT_FOUND")
        db.execute(
            "INSERT INTO assets (id, user_id, project_id, filename, mime_type, media_type, byte_size, storage_path, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (asset_id, user["id"], project_id, safe_name, mime, media_type, len(payload), str(target), now()),
        )
    return {
        "id": asset_id,
        "filename": safe_name,
        "mime_type": mime,
        "media_type": media_type,
        "byte_size": len(payload),
        "content_url": f"/v1/assets/{asset_id}/content",
        "created_at": now(),
    }


@app.get("/v1/assets/{asset_id}", tags=["Assets"])
def get_asset(asset_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    with connect() as db:
        row = require_asset(db, asset_id, user["id"])
    return {
        "id": row["id"],
        "filename": row["filename"],
        "mime_type": row["mime_type"],
        "media_type": row["media_type"],
        "byte_size": row["byte_size"],
        "parent_asset_id": row["parent_asset_id"],
        "relationship": row["relationship"],
        "content_url": f"/v1/assets/{asset_id}/content",
        "created_at": row["created_at"],
    }


@app.get("/v1/assets/{asset_id}/content", tags=["Assets"], include_in_schema=False)
def asset_content(
    asset_id: str,
    authorization: Optional[str] = Header(None),
    token: Optional[str] = Query(None),
) -> FileResponse:
    user = current_user(authorization=authorization, token=token)
    with connect() as db:
        row = require_asset(db, asset_id, user["id"])
    path = Path(row["storage_path"])
    if not path.exists():
        raise HTTPException(status.HTTP_410_GONE, "ASSET_BYTES_MISSING")
    return FileResponse(path, media_type=row["mime_type"], filename=row["filename"])


# ----------------------------------------------------------------------- jobs

def append_event(db: sqlite3.Connection, job_id: str, state: str, label: str) -> None:
    db.execute(
        "INSERT INTO job_events (job_id, state, label, created_at) VALUES (?, ?, ?, ?)",
        (job_id, state, label, now()),
    )
    db.execute("UPDATE jobs SET state = ?, updated_at = ? WHERE id = ?", (state, now(), job_id))


def load_job(db: sqlite3.Connection, job_id: str) -> sqlite3.Row:
    row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND")
    return row


async def execute_h3(job_id: str) -> None:
    """Run the deployed H3 runtime for one job and persist the returned video."""
    with connect() as db:
        job = load_job(db, job_id)
        try:
            asset_ids = json.loads(job["reference_ids"] or "[]")
        except json.JSONDecodeError:
            asset_ids = []
        if not asset_ids and job["asset_id"]:
            asset_ids = [job["asset_id"]]

        references: List[Tuple[str, str, bytes]] = []
        for asset_id in asset_ids:
            row = db.execute(
                "SELECT * FROM assets WHERE id = ? AND user_id = ?", (asset_id, job["user_id"])
            ).fetchone()
            if row is None:
                continue
            references.append((row["filename"], row["mime_type"], Path(row["storage_path"]).read_bytes()))

    video, content_type, result = await h3.generate(job["prompt"], references)
    if not video:
        raise h3.H3Error("H3_EMPTY_VIDEO: the runtime returned zero bytes")

    asset_id = str(uuid.uuid4())
    target_dir = ASSET_DIR / asset_id
    target_dir.mkdir(parents=True, exist_ok=True)
    extension = ".webm" if "webm" in content_type else ".mp4"
    filename = f"h3-{job['id'][:8]}{extension}"
    target = target_dir / filename
    target.write_bytes(video)

    with connect() as db:
        db.execute(
            "INSERT INTO assets (id, user_id, project_id, filename, mime_type, media_type, byte_size, "
            "storage_path, parent_asset_id, relationship, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                asset_id, job["user_id"], None, filename, content_type, "video", len(video),
                str(target), job["asset_id"], "animation" if job["intent"] == "animate" else "variation", now(),
            ),
        )
        db.execute("UPDATE jobs SET output_asset_id = ? WHERE id = ?", (asset_id, job_id))
        append_event(db, job_id, "COMPLETED", "Finishing")
        model = result.get("model") if isinstance(result, dict) else None
        detail = f"H3 rendered {len(video)} bytes" + (f" with {model}" if model else "")
        db.execute("UPDATE jobs SET detail = ? WHERE id = ?", (detail, job_id))


async def run_job(job_id: str) -> None:
    """Drives the Bible §25 progress stages, then executes against the deployed
    H3 runtime. A job only reaches COMPLETED when the backend returned bytes."""
    for state, label in PROGRESS_STAGES[:-1]:
        await asyncio.sleep(0.35)
        with connect() as db:
            append_event(db, job_id, state, label)

    try:
        await execute_h3(job_id)
    except h3.H3Error as exc:
        with connect() as db:
            append_event(db, job_id, "FAILED", "Generation failed")
            db.execute("UPDATE jobs SET detail = ? WHERE id = ?", (str(exc), job_id))
    except Exception as exc:  # pragma: no cover - defensive
        with connect() as db:
            append_event(db, job_id, "FAILED", "Generation failed")
            db.execute("UPDATE jobs SET detail = ? WHERE id = ?", (f"H3_RUNTIME_ERROR: {exc}", job_id))


@app.post("/v1/sessions/{session_id}/messages", tags=["Sessions"], status_code=202)
async def post_message(
    session_id: str,
    req: MessageRequest,
    user: Dict[str, Any] = Depends(current_user),
) -> Dict[str, Any]:
    if req.intent in GENERATION_INTENTS:
        if not req.asset_ids:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "REFERENCE_REQUIRED: the H3 ref2va workflow needs one or two reference images.",
            )
        if len(req.asset_ids) > 2:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                "REFERENCE_LIMIT: the H3 ref2va workflow accepts at most two reference images.",
            )
        if not h3.configured():
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "H3_NOT_CONFIGURED: no ComfyUI H3 runtime is reachable. Set KEYSTONE_COMFY_URL to the "
                "Kaggle tunnel and keep KEYSTONE_COMFY_WORKFLOW at workflows/h3-ref2va.json.",
            )

    with connect() as db:
        session = db.execute(
            "SELECT id FROM sessions WHERE id = ? AND user_id = ?", (session_id, user["id"])
        ).fetchone()
        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND")

        for asset_id in req.asset_ids:
            require_asset(db, asset_id, user["id"])

        message_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (message_id, session_id, "user", req.content, now()),
        )

        job_id = str(uuid.uuid4())
        db.execute(
            "INSERT INTO jobs (id, user_id, session_id, asset_id, intent, prompt, state, reference_ids, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                job_id, user["id"], session_id, req.asset_ids[0] if req.asset_ids else None,
                req.intent, req.content, "CREATED", json.dumps(req.asset_ids), now(), now(),
            ),
        )
        append_event(db, job_id, "CREATED", "Job accepted")

    asyncio.create_task(run_job(job_id))
    return {"message_id": message_id, "job_id": job_id, "state": "CREATED"}


@app.get("/v1/jobs/{job_id}", tags=["Jobs"])
def get_job(job_id: str, user: Dict[str, Any] = Depends(current_user)) -> Dict[str, Any]:
    with connect() as db:
        row = db.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?", (job_id, user["id"])
        ).fetchone()
        if not row:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND")
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "asset_id": row["asset_id"],
        "intent": row["intent"],
        "prompt": row["prompt"],
        "state": row["state"],
        "detail": row["detail"],
        "output_asset_id": row["output_asset_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.get("/v1/jobs/{job_id}/events", tags=["Jobs"])
async def job_events_stream(job_id: str, token: Optional[str] = Query(None),
                            authorization: Optional[str] = Header(None)) -> StreamingResponse:
    user = current_user(authorization=authorization, token=token)

    with connect() as db:
        job = db.execute(
            "SELECT id FROM jobs WHERE id = ? AND user_id = ?", (job_id, user["id"])
        ).fetchone()
    if not job:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND")

    async def stream():
        last_seq = 0
        for _ in range(600):
            with connect() as db:
                rows = db.execute(
                    "SELECT seq, state, label, created_at FROM job_events WHERE job_id = ? AND seq > ? ORDER BY seq",
                    (job_id, last_seq),
                ).fetchall()
                state = db.execute(
                    "SELECT state, detail, output_asset_id FROM jobs WHERE id = ?", (job_id,)
                ).fetchone()

            for row in rows:
                last_seq = row["seq"]
                payload = {"state": row["state"], "label": row["label"], "at": row["created_at"]}
                yield f"data: {json.dumps(payload)}\n\n"

            if state and state["state"] in TERMINAL_STATES:
                final = {
                    "state": state["state"],
                    "detail": state["detail"],
                    "output_asset_id": state["output_asset_id"],
                    "terminal": True,
                }
                yield f"data: {json.dumps(final)}\n\n"
                return

            await asyncio.sleep(0.25)

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# -------------------------------------------------------------------- surface

@app.get("/v1/health", tags=["System"])
def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "product": "KEYSTONE",
        "version": app.version,
        "contract": "plan.v1",
        "wave": "1",
        "creative": h3.describe(),
    }


@app.get("/v1/creative/h3", tags=["Creative"])
def creative_h3() -> Dict[str, Any]:
    """Report the deployed H3 runtime exactly as configured, including reachability."""
    return {"runtime": h3.describe(), "health": h3.health()}


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/workspace")


STATIC_HEADERS = {"Cache-Control": "no-store, must-revalidate"}


@app.get("/workspace", include_in_schema=False)
@app.get("/workspace/", include_in_schema=False)
def workspace_index() -> FileResponse:
    index = WEB_DIR / "index.html"
    if not index.exists():  # pragma: no cover
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "apps/web is missing")
    return FileResponse(index, headers=STATIC_HEADERS)


@app.get("/workspace/{filename}", include_in_schema=False)
def workspace_asset(filename: str) -> FileResponse:
    """Serve the shell without caching, so a stale bundle can never shadow the API."""
    target = (WEB_DIR / filename).resolve()
    if WEB_DIR.resolve() not in target.parents or not target.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "NOT_FOUND")
    return FileResponse(target, headers=STATIC_HEADERS)
