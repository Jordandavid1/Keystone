"""
KEYSTONE Additive Production API Server
Extends baseline main.py additively by mounting the Intelligence Router,
publishing Canonical Contracts, and configuring OpenAPI metadata.

CRITICAL INVARIANT: apps/api/src/main.py remains 100% byte-identical.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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
# Configure Production OpenAPI Metadata
# ============================================================================

app.title = "KEYSTONE API"
app.version = "2.0.0-alpha.1"
app.description = (
    "KEYSTONE is the proprietary prompt-intelligence engine, prompting authority, "
    "cognition controller, workflow orchestrator, and quality authority for multimodal creative AI.\n\n"
    "Canonical spec: KEYSTONE Bible (SHA-256: 1D31D909790ED73506004B0233AEDE617761E99916D9A7D209BD9086B3063788)."
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
        "description": "Deterministic plan.v1 generation and PromptCompiler execution across 13 playbooks (F10)"
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


# ============================================================================
# Database Schema Initialization Hook
# ============================================================================

@app.on_event("startup")
async def on_startup() -> None:
    """Initialize database tables on server startup."""
    try:
        await init_db()
    except Exception as exc:
        print(f"[Warning] Failed to initialize database: {exc}")


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
            "Events", "Finance", "General"
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


# ============================================================================
# Standalone CLI Entrypoint
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("apps.api.src.server:app", host="0.0.0.0", port=8000, reload=True)
