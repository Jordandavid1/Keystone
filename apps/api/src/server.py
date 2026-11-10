"""
KEYSTONE Additive Production API Server
Extends baseline main.py additively by mounting the Intelligence Router,
publishing Canonical Contracts, and configuring OpenAPI metadata.

CRITICAL INVARIANT: apps/api/src/main.py remains 100% byte-identical.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

try:
    from services.cognition.src.client import load_keystone_dotenv
    load_keystone_dotenv()
except Exception:
    pass

# 1. Import pre-built baseline app (preserves main.py byte-identical)
from apps.api.src.main import app, PlanRequest

# 2. Import pre-built intelligence router
from apps.api.src.intelligence_router import router as intelligence_router

# 2.1 Import Milestone M1 Domain Routers & DB session
from apps.api.src.routers.auth import router as auth_router
from apps.api.src.routers.projects import router as projects_router
from apps.api.src.routers.sessions import router as sessions_router
from apps.api.src.routers.assets import router as assets_router
from apps.api.src.routers.jobs import router as jobs_router
from apps.api.src.routers.planning import router as planning_router
from apps.api.src.routers.authority import router as authority_router
from apps.api.src.routers.workers import router as workers_router
from apps.api.src.routers.creative import router as creative_router
from apps.api.src.routers.billing import router as billing_router
from apps.api.src.routers.admin import router as admin_router
from apps.api.src.routers.personas import router as personas_router
from apps.api.src.routers.audio import router as audio_router
from apps.api.src.routers.cognition import router as cognition_router
from apps.api.src.routers.zencreator import router as zencreator_router
from apps.api.src.db.session import init_db

# 3. Import canonical Pydantic v2 contract models
from packages.contracts.src.models import (
    PromptIntent,
    ParameterSpec,
    CapabilityManifest,
    PromptCompilationRequest,
    CompiledPrompt,
    ProposedAction,
    CognitiveResult,
    AuthorityDecision,
    ExecutionEnvelope,
    HarnessResult,
    QualityDimensions,
    QualityScore,
    RetryPolicy,
    GenerationAttempt,
    PromptAnatomy
)


# ============================================================================
# Runtime Directory Resolution (Supports Development and PyInstaller Frozen .exe)
# ============================================================================

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _REPO_ROOT = Path(sys._MEIPASS)
else:
    _REPO_ROOT = Path(__file__).resolve().parents[3]
_WEB_DIR = _REPO_ROOT / "apps" / "web"
_ADMIN_DIR = _REPO_ROOT / "apps" / "admin"


# ============================================================================
# Configure Production OpenAPI Metadata
# ============================================================================

app.title = "KEYSTONE API"
app.version = "2.0.0-alpha.1"
app.description = (
    "KEYSTONE is the proprietary prompt-intelligence engine, prompting authority, "
    "cognition controller, workflow orchestrator, and quality authority for multimodal creative AI.\n\n"
    "Canonical spec: KEYSTONE Bible (SHA-256: 3BFF4E7063733146B663BDBE9C9BAD7271D480152243A05542F256DC05E7B25D)."
)

app.openapi_tags = [
    {
        "name": "System",
        "description": "Platform health, liveness, and compatibility contract verification"
    },
    {
        "name": "Contracts",
        "description": "Frozen canonical contracts, schemas, and state invariants (F02)"
    },
    {
        "name": "Intelligence",
        "description": "Firecrawl benchmark application extraction, PII Vault, and Aikido prompt defense"
    },
    {
        "name": "Capabilities",
        "description": "Provider-agnostic capability discovery and registry"
    },
    {
        "name": "Authentication",
        "description": "User registration, authentication, tokens, and API key management (F06)"
    },
    {
        "name": "Projects",
        "description": "Tenant-scoped creative workspace projects (F05)"
    },
    {
        "name": "Sessions",
        "description": "Multi-turn multimodal creative sessions and messages (F05)"
    },
    {
        "name": "Assets",
        "description": "Asset registration, storage keys, signed URLs, and Lineage DAG tracking (F07, F08)"
    },
    {
        "name": "Jobs",
        "description": "Job lifecycle orchestration and 13-state deterministic state machine (F09)"
    },
    {
        "name": "Planning",
        "description": "Deterministic plan.v1 generation and PromptCompiler execution across 16 playbooks (F10)"
    },
    {
        "name": "Authority",
        "description": "Authority Decision Engine, policy enforcement, and execution envelopes (F15, F18)"
    },
    {
        "name": "Workers",
        "description": "Kaggle Worker Bridge, dynamic tunnel registration, and heartbeat monitoring (F17)"
    },
    {
        "name": "Personas",
        "description": "Character identities, avatar reference anchoring, personality traits, and ElevenLabs voice assignment"
    },
    {
        "name": "Audio",
        "description": "ElevenLabs Text-to-Speech synthesis and voice catalogs with offline formant fallback"
    }
]


# ============================================================================
# Mount Additive Routers
# ============================================================================

# Mount Intelligence Router (/v1/intelligence)
app.include_router(intelligence_router)

# Mount Milestone M1 Domain Routers
app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(sessions_router)
app.include_router(assets_router)
app.include_router(jobs_router)

# Mount Milestone M2 Planning Router (/v1/planning)
app.include_router(planning_router)

# Mount Milestone M3 Cognition & Authority Routers
app.include_router(authority_router)
app.include_router(workers_router)

# Mount Milestone M4 Creative Tool Fabric Router
app.include_router(creative_router)

# Mount Milestone M5 Billing & Admin Routers
app.include_router(billing_router)
app.include_router(admin_router)

# Mount Milestone M6 Personas & ElevenLabs Audio Routers
app.include_router(personas_router)
app.include_router(audio_router)

# Mount Autonomous Cognition Agent & Direct LLM Chat Router (/v1/cognition, Bible §39, ADR-002)
app.include_router(cognition_router)

# Mount ZenCreator Full Generative Pipeline Router (/v1/zencreator, all 17 generative tools)
app.include_router(zencreator_router)


# ============================================================================
# Database Schema Initialization Hook
# ============================================================================

@app.on_event("startup")
async def on_startup() -> None:
    """Initialize database tables and Kaggle worker daemon on server startup."""
    try:
        await init_db()
    except Exception as exc:
        print(f"[Warning] Failed to initialize database: {exc}")

    if not os.getenv("PYTEST_CURRENT_TEST") and os.getenv("KEYSTONE_ENABLE_KAGGLE_DAEMON", "true").lower() == "true":
        try:
            from services.harness.src.kaggle_daemon import start_kaggle_daemon
            start_kaggle_daemon(in_process=True)
            print("[+] Kaggle Worker Bridge & Heartbeat Daemon initialized (T4x2 Cognition + ComfyUI).")
        except Exception as exc:
            print(f"[Warning] Failed to start Kaggle worker daemon: {exc}")



# ============================================================================
# Additive Canonical Contracts Endpoint (/v1/contracts)
# ============================================================================

@app.get(
    "/v1/contracts",
    tags=["Contracts"],
    summary="Get Canonical Contracts & Schemas",
    description=(
        "Returns the frozen contract definitions, state machines, and complete "
        "JSON schemas for all Keystone Pydantic v2 models per Bible §6–§16."
    )
)
def get_contracts() -> Dict[str, Any]:
    """Exposes all canonical contracts, enums, and schemas for platform clients and workers."""
    return {
        "status": "ok",
        "product": "KEYSTONE",
        "contract_version": "2.0.0",
        "plan": "plan.v1",
        "promptAnatomy": [
            "role", "task", "context", "constraints", "outputFormat", "reasoning"
        ],
        "authorityDecisions": ["approve", "deny", "replan"],
        "jobStates": [
            "created", "validating", "planning", "authorizing", "queued",
            "running", "validating_output", "retry_pending", "replan_required",
            "completed", "failed", "cancelled", "rejected"
        ],
        "playbooks": [
            "Software", "Writing", "Marketing", "Business", "Learning",
            "Career", "Content", "Research", "Design", "Fitness",
            "Events", "Finance", "Nsfw", "Hacker", "Freedom", "General"
        ],
        "schemas": {
            "PromptIntent": PromptIntent.model_json_schema(),
            "ParameterSpec": ParameterSpec.model_json_schema(),
            "CapabilityManifest": CapabilityManifest.model_json_schema(),
            "PromptCompilationRequest": PromptCompilationRequest.model_json_schema(),
            "CompiledPrompt": CompiledPrompt.model_json_schema(),
            "ProposedAction": ProposedAction.model_json_schema(),
            "CognitiveResult": CognitiveResult.model_json_schema(),
            "AuthorityDecision": AuthorityDecision.model_json_schema(),
            "ExecutionEnvelope": ExecutionEnvelope.model_json_schema(),
            "HarnessResult": HarnessResult.model_json_schema(),
            "QualityDimensions": QualityDimensions.model_json_schema(),
            "QualityScore": QualityScore.model_json_schema(),
            "RetryPolicy": RetryPolicy.model_json_schema(),
            "GenerationAttempt": GenerationAttempt.model_json_schema(),
            "PromptAnatomy": PromptAnatomy.model_json_schema()
        }
    }


@app.get(
    "/v1/config/remote",
    tags=["Configuration"],
    summary="Firebase Remote Config Template & Feature Flags",
    description="Returns the active remote config parameters, feature toggles, and in-app defaults."
)
def get_remote_config() -> Dict[str, Any]:
    """Serves the Firebase Remote Config template for client feature activation."""
    import json
    config_file = _REPO_ROOT / "remote_config.json"
    if config_file.exists():
        try:
            return json.loads(config_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "parameters": {
            "enable_zencreator_node_graph": {"defaultValue": {"value": "true"}},
            "enable_cursor_floating_composer": {"defaultValue": {"value": "true"}},
            "enable_vscode_activity_bar": {"defaultValue": {"value": "true"}},
            "enable_higgsfield_motion_controls": {"defaultValue": {"value": "true"}},
            "enable_firecrawl_style_scrape": {"defaultValue": {"value": "true"}},
            "default_cinema_framerate": {"defaultValue": {"value": "24"}},
            "credit_hold_estimate": {"defaultValue": {"value": "3"}}
        },
        "conditions": []
    }


@app.post(
    "/v1/config/remote",
    tags=["Configuration"],
    summary="Update Firebase Remote Config Feature Flags",
    description="Updates in-app defaults and feature toggles in remote_config.json."
)
async def update_remote_config(request: Request) -> Dict[str, Any]:
    """Updates the active remote config template."""
    import json
    data = await request.json()
    config_file = _REPO_ROOT / "remote_config.json"
    existing = get_remote_config()
    
    params = data.get("parameters", data)
    for k, v in params.items():
        if k in existing.get("parameters", {}):
            val_str = str(v.get("defaultValue", {}).get("value", v) if isinstance(v, dict) else v)
            existing["parameters"][k] = {"defaultValue": {"value": val_str}}
            
    try:
        config_file.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    except Exception:
        pass
    return existing


# ============================================================================
# CORS Middleware Configuration (Permissive for local development & Canvas)
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def disable_static_caching(request, call_next):
    """Workspace/admin assets are edited live during development, so prevent
    browsers from heuristically caching them and running stale JavaScript."""
    response = await call_next(request)
    if request.url.path.startswith(("/workspace", "/admin")):
        response.headers["Cache-Control"] = "no-store"
    return response


# ============================================================================
# Mount Premium Creative Workspace (/workspace) & Operator Admin Console (/admin)
# ============================================================================

if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    _REPO_ROOT = Path(sys._MEIPASS)
else:
    _REPO_ROOT = Path(__file__).resolve().parents[3]
_WEB_DIR = _REPO_ROOT / "apps" / "web"
_ADMIN_DIR = _REPO_ROOT / "apps" / "admin"



@app.get("/workspace", tags=["Workspace UX"], summary="Premium Creative Workspace UI")
def serve_workspace_index() -> FileResponse:
    """Serves the 5-Region KEYSTONE Premium Creative Workspace (Bible §25)."""
    return FileResponse(_WEB_DIR / "index.html")


@app.get("/admin", tags=["Operator Admin Console"], summary="Operator Admin Console UI")
def serve_admin_index() -> FileResponse:
    """Serves the KEYSTONE Operator Admin Console (Bible §26)."""
    return FileResponse(_ADMIN_DIR / "index.html")


if _WEB_DIR.exists():
    app.mount("/workspace", StaticFiles(directory=str(_WEB_DIR), html=True), name="workspace_static")

if _ADMIN_DIR.exists():
    app.mount("/admin", StaticFiles(directory=str(_ADMIN_DIR), html=True), name="admin_static")


# ============================================================================
# Standalone CLI Entrypoint
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.src.server:app", host="0.0.0.0", port=8000, reload=True)
