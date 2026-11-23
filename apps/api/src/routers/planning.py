"""
KEYSTONE Planning & Prompt Compilation Router
Exposes endpoints for plan.v1 generation using the 16 domain playbooks,
PromptCompiler execution across standard/chat/reasoning profiles,
and playbook discovery per Bible §6, §7, §9, §33.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_optional_user
from apps.api.src.db.models import User
from apps.api.src.db.session import get_db
from apps.api.src.services.gate import GateService
from packages.prompt_engine.engine import generate
from packages.prompt_engine.compiler import PromptCompiler
from packages.prompt_engine.playbooks import PlaybookRegistry, PLAYBOOK_IDS
from packages.contracts.src.models import PromptIntent, CompiledPrompt

router = APIRouter(prefix="/v1/planning", tags=["Planning"])


class PlanRequestModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    goal: str = Field(..., min_length=1, max_length=102400, description="User creative or analytical goal")
    answers: Dict[str, Any] = Field(default_factory=dict, description="Answers to clarifying questions")
    options: Dict[str, Any] = Field(default_factory=dict, description="Compiler and heuristic options")
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    as_persona: Optional[str] = Field(None, alias="as", description="Optional persona ID")
    persona_id: Optional[str] = Field(None, description="Optional persona ID (alias for `as`)")


class CompileRequestModel(BaseModel):
    intent: Dict[str, Any] = Field(..., description="PromptIntent dictionary or object")
    playbook: str = Field("general", description="Target domain playbook")
    profile: str = Field("standard", description="Compiler profile: standard, chat, reasoning")


@router.post(
    "/plan",
    summary="Generate Execution Plan (plan.v1)",
    description="Transforms a high-level goal into a deterministic, finishable 6-step path conforming to plan.v1 plus the digested KEYSTONE compiled prompt."
)
async def plan_goal(
    request: PlanRequestModel,
    current_user: Optional[User] = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Generates a plan.v1 structure and digests the goal via KEYSTONE + Embedded Cognition."""
    options = dict(request.options)
    if request.answers:
        options["answers"] = request.answers

    target_persona_id = request.as_persona or request.persona_id or options.get("as") or options.get("persona_id")
    persona_sheet: Optional[str] = None
    receipt = None
    if target_persona_id:
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Authentication required to plan with a persona",
            )
        receipt = await GateService.authorize_async(
            db,
            user_id=str(current_user.id),
            intent="plan",
            prompt_text=request.goal,
            capability_id="cognition.reasoning",
            arguments={"goal": request.goal},
            project_id=request.project_id,
            session_id=request.session_id,
            persona_id=str(target_persona_id),
        )
        persona_sheet = receipt.persona_sheet

    result = generate(request.goal, options)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result["error"]["message"])

    try:
        from packages.prompt_engine import compiler as keystone_prompting
        compiled = await keystone_prompting.digest_and_compile_prompt(
            user_text=request.goal,
            reference_count=int(options.get("reference_count", 0)),
            intent_hint="plan",
            persona_sheet=persona_sheet,
        )
        result["compiledPrompt"] = compiled.positive_prompt
        result["promptHash"] = compiled.prompt_hash
        result["cognitionProvenance"] = compiled.provenance.get("cognition")
        if receipt is not None:
            result["persona"] = receipt.persona_summary
            result["content_mode"] = receipt.content_mode
            result["envelope_id"] = receipt.envelope.envelope_id
    except Exception as exc:
        result["cognitionProvenance"] = {
            "status": "error",
            "detail": f"{type(exc).__name__}: {exc}",
        }

    return result


@router.post(
    "/compile",
    summary="Compile PromptIntent",
    description="Compiles PromptIntent into PromptAnatomy, computes deterministic SHA-256 hash, and attaches provenance."
)
def compile_prompt_intent(request: CompileRequestModel) -> Dict[str, Any]:
    """Compiles a PromptIntent using the specified playbook and profile."""
    try:
        return PromptCompiler.compile(
            intent=request.intent,
            playbook=request.playbook,
            profile=request.profile
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.get(
    "/playbooks",
    summary="List All 16 Domain Playbooks with Preloaded Use-Case Context & Skills",
    description="Returns all 16 canonical domain playbooks preserved in KEYSTONE with preloaded domain_context, use_cases, skills, criticalSlots, and 6-step paths."
)
def list_playbooks() -> Dict[str, Any]:
    """Lists all 16 first-class domain playbooks with full context and skills."""
    playbooks = PlaybookRegistry.list_playbooks()
    return {
        "status": "ok",
        "count": len(playbooks),
        "playbooks": [p.to_dict() for p in playbooks]
    }


@router.get(
    "/playbooks/{playbook_id}",
    summary="Get Domain Playbook Context, Use Cases & Skills",
    description="Returns a single domain playbook by ID with its preloaded use-case context, bound skills, critical slots, and 6-step execution path."
)
def get_playbook_detail(playbook_id: str) -> Dict[str, Any]:
    """Returns full playbook definition including preloaded use cases and skills."""
    if not PlaybookRegistry.exists(playbook_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Playbook '{playbook_id}' not found")
    pb = PlaybookRegistry.get(playbook_id)
    return {
        "status": "ok",
        "playbook": pb.to_dict()
    }
