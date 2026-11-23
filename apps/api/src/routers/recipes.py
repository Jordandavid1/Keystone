"""apps/api/src/routers/recipes.py
ADR-005 / Bible v2 §42.3 Recipe Library and Style Rules Router.
Routes:
  GET /v1/recipes
  GET /v1/recipes/{recipe_id}
  POST /v1/recipes/{recipe_id}/replay
  POST /v1/recipes/{recipe_id}/promote
  GET /v1/projects/{project_id}/style-rules
  POST /v1/projects/{project_id}/style-rules
  PATCH /v1/projects/{project_id}/style-rules/{rule_id}
  DELETE /v1/projects/{project_id}/style-rules/{rule_id}
"""

from __future__ import annotations

import inspect
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.src.auth.dependencies import get_current_user
from apps.api.src.db.models import Project, Recipe, StyleRule, User
from apps.api.src.db.session import get_db
from apps.api.src.services.gate import GateService
from apps.api.src.services.memory import record_passing_run_and_maybe_promote_async

router = APIRouter(tags=["recipes"])


async def _await_if_needed(val: Any) -> Any:
    if inspect.isawaitable(val):
        return await val
    return val


class StyleRuleCreate(BaseModel):
    rule_text: Optional[str] = Field(default=None, max_length=1000)
    text: Optional[str] = Field(default=None, max_length=1000)
    weight: float = Field(default=1.0, ge=0.0, le=5.0)
    active: bool = True

    @model_validator(mode="after")
    def _ensure_rule_text(self) -> "StyleRuleCreate":
        resolved = (self.rule_text or self.text or "").strip()
        if not resolved:
            raise ValueError("Either 'rule_text' or 'text' must be a non-empty string")
        self.rule_text = resolved
        return self


class StyleRuleUpdate(BaseModel):
    rule_text: Optional[str] = None
    text: Optional[str] = None
    weight: Optional[float] = Field(default=None, ge=0.0, le=5.0)
    active: Optional[bool] = None


class ReplayRequest(BaseModel):
    override_seed: Optional[int] = None
    override_params: Optional[Dict[str, Any]] = None


@router.get("/v1/recipes")
async def list_recipes(
    project_id: Optional[str] = Query(None),
    persona_id: Optional[str] = Query(None),
    promoted_only: bool = Query(False),
    content_mode: Optional[str] = Query(None),
    mode: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    requested = (content_mode or mode or getattr(user, "content_mode", "sfw") or "sfw").lower().strip()
    if requested == "unrestricted" and not bool(getattr(user, "age_verified", False)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "AGE_VERIFICATION_REQUIRED",
                "message": "Age verification is required for unrestricted content mode.",
            },
        )
    if requested not in ("sfw", "unrestricted"):
        requested = "sfw"

    stmt = select(Recipe).where(Recipe.user_id == str(user.id))
    if project_id:
        stmt = stmt.where(Recipe.project_id == str(project_id))
    if persona_id:
        stmt = stmt.where(Recipe.persona_id == str(persona_id))
    if promoted_only:
        stmt = stmt.where(Recipe.status == "promoted")
    if requested == "sfw":
        stmt = stmt.where(Recipe.content_mode == "sfw")
    stmt = stmt.order_by(Recipe.created_at.desc())

    res = await db.execute(stmt)
    recipes = res.scalars().all()
    return {"recipes": [r.to_dict() for r in recipes], "total": len(recipes)}


@router.get("/v1/recipes/{recipe_id}")
async def get_recipe(
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    res = await db.execute(
        select(Recipe).where(Recipe.id == recipe_id, Recipe.user_id == str(user.id))
    )
    recipe = res.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    if recipe.content_mode == "unrestricted" and not bool(getattr(user, "age_verified", False)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "AGE_VERIFICATION_REQUIRED",
                "message": "Age verification is required for unrestricted recipes.",
            },
        )
    return recipe.to_dict()


@router.post("/v1/recipes/{recipe_id}/promote")
async def promote_recipe(
    recipe_id: str,
    operator_approved: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    res = await db.execute(
        select(Recipe).where(Recipe.id == recipe_id, Recipe.user_id == str(user.id))
    )
    recipe = res.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    promoted = await record_passing_run_and_maybe_promote_async(
        db, recipe.id, operator_approved=operator_approved
    )
    await _await_if_needed(db.commit())
    await _await_if_needed(db.refresh(promoted))
    return promoted.to_dict()


@router.post("/v1/recipes/{recipe_id}/replay")
async def replay_recipe(
    recipe_id: str,
    replay_body: Optional[ReplayRequest] = Body(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    res = await db.execute(
        select(Recipe).where(Recipe.id == recipe_id, Recipe.user_id == str(user.id))
    )
    recipe = res.scalar_one_or_none()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    if recipe.content_mode == "unrestricted" and not bool(getattr(user, "age_verified", False)):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "AGE_VERIFICATION_REQUIRED",
                "message": "Age verification is required to replay unrestricted recipes.",
            },
        )

    env_dict = recipe.envelope if isinstance(recipe.envelope, dict) else {}
    compiled_dict = recipe.compiled_prompt if isinstance(recipe.compiled_prompt, dict) else {}

    intent = str(env_dict.get("intent") or "generate")
    capability_id = str(env_dict.get("capability_id") or env_dict.get("tool") or "image.generation")
    arguments = dict(env_dict.get("arguments") or env_dict.get("params") or {})

    seed = (
        replay_body.override_seed
        if (replay_body and replay_body.override_seed is not None)
        else recipe.seed
    )
    if seed is not None:
        arguments["seed"] = int(seed)

    if replay_body and replay_body.override_params:
        arguments.update(replay_body.override_params)

    prompt_text = str(
        compiled_dict.get("positive_prompt")
        or compiled_dict.get("prompt")
        or compiled_dict.get("user_prompt")
        or arguments.get("prompt")
        or recipe.name
        or "replay recipe"
    )
    playbook = env_dict.get("playbook")

    receipt = await GateService.authorize_async(
        db,
        user_id=str(user.id),
        intent=intent,
        prompt_text=prompt_text,
        capability_id=capability_id,
        arguments=arguments,
        project_id=recipe.project_id,
        persona_id=recipe.persona_id,
        playbook=playbook,
    )

    return {
        "status": "replayed",
        "recipe_id": recipe.id,
        "prompt_hash": recipe.prompt_hash,
        "seed": seed,
        "fabric_versions": recipe.fabric_versions or {},
        "compiled_prompt": recipe.compiled_prompt,
        "content_mode": receipt.content_mode,
        "decision_id": receipt.decision_id,
        "job_id": receipt.job_id,
        "envelope": receipt.envelope.model_dump(mode="json"),
    }


async def _require_owned_project(db: AsyncSession, project_id: str, user_id: str) -> Project:
    res = await db.execute(
        select(Project).where(
            Project.id == str(project_id),
            Project.user_id == str(user_id),
            Project.deleted_at.is_(None),
        )
    )
    project = res.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found or access denied")
    return project


# Style Rules endpoints
@router.get("/v1/projects/{project_id}/style-rules")
async def list_style_rules(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    await _require_owned_project(db, project_id, str(user.id))
    res = await db.execute(
        select(StyleRule)
        .where(StyleRule.user_id == str(user.id), StyleRule.project_id == str(project_id))
        .order_by(StyleRule.created_at.desc())
    )
    rules = res.scalars().all()
    return {"style_rules": [r.to_dict() for r in rules]}


@router.post("/v1/projects/{project_id}/style-rules")
async def create_style_rule(
    project_id: str,
    body: StyleRuleCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    await _require_owned_project(db, project_id, str(user.id))
    now = datetime.now(timezone.utc)
    rule = StyleRule(
        id=str(uuid.uuid4()),
        user_id=str(user.id),
        project_id=str(project_id),
        rule_text=body.rule_text or "",
        weight=body.weight,
        active=body.active,
        created_at=now,
        updated_at=now,
    )
    db.add(rule)
    await _await_if_needed(db.commit())
    await _await_if_needed(db.refresh(rule))
    return rule.to_dict()


@router.patch("/v1/projects/{project_id}/style-rules/{rule_id}")
async def update_style_rule(
    project_id: str,
    rule_id: str,
    body: StyleRuleUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    await _require_owned_project(db, project_id, str(user.id))
    res = await db.execute(
        select(StyleRule).where(
            StyleRule.id == rule_id,
            StyleRule.project_id == str(project_id),
            StyleRule.user_id == str(user.id),
        )
    )
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="StyleRule not found")

    new_text = body.rule_text if body.rule_text is not None else body.text
    if new_text is not None:
        rule.rule_text = new_text
    if body.weight is not None:
        rule.weight = body.weight
    if body.active is not None:
        rule.active = body.active

    rule.updated_at = datetime.now(timezone.utc)
    await _await_if_needed(db.commit())
    await _await_if_needed(db.refresh(rule))
    return rule.to_dict()


@router.delete("/v1/projects/{project_id}/style-rules/{rule_id}")
async def delete_style_rule(
    project_id: str,
    rule_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    await _require_owned_project(db, project_id, str(user.id))
    res = await db.execute(
        select(StyleRule).where(
            StyleRule.id == rule_id,
            StyleRule.project_id == str(project_id),
            StyleRule.user_id == str(user.id),
        )
    )
    rule = res.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="StyleRule not found")

    await _await_if_needed(db.delete(rule))
    await _await_if_needed(db.commit())
    return {"deleted": True, "id": rule_id}
