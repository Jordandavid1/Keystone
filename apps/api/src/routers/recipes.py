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

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from apps.api.src.db.connection import get_db
from apps.api.src.db.models import Recipe, StyleRule, User
from apps.api.src.routers.auth import get_current_user
from apps.api.src.services.gate import GateService
from apps.api.src.services.memory import record_passing_run_and_maybe_promote

router = APIRouter(tags=["recipes"])


class StyleRuleCreate(BaseModel):
    rule_text: str = Field(..., min_length=1, max_length=1000)
    weight: float = Field(default=1.0, ge=0.0, le=5.0)
    active: bool = True


class StyleRuleUpdate(BaseModel):
    rule_text: Optional[str] = None
    weight: Optional[float] = None
    active: Optional[bool] = None


class ReplayRequest(BaseModel):
    override_seed: Optional[int] = None
    override_params: Optional[Dict[str, Any]] = None


@router.get("/v1/recipes")
def list_recipes(
    project_id: Optional[str] = Query(None),
    persona_id: Optional[str] = Query(None),
    promoted_only: bool = Query(False),
    mode: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Recipe).filter(Recipe.user_id == user.id)
    if project_id:
        query = query.filter(Recipe.project_id == project_id)
    if persona_id:
        query = query.filter(Recipe.persona_id == persona_id)
    if promoted_only:
        query = query.filter(Recipe.status == "promoted")

    # Scope by user's content mode or explicit query
    resolved_mode = mode or getattr(user, "content_mode", "sfw") or "sfw"
    if resolved_mode == "sfw":
        query = query.filter(Recipe.content_mode == "sfw")

    recipes = query.order_by(Recipe.created_at.desc()).all()
    return {"recipes": [r.to_dict() for r in recipes], "total": len(recipes)}


@router.get("/v1/recipes/{recipe_id}")
def get_recipe(
    recipe_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe.to_dict()


@router.post("/v1/recipes/{recipe_id}/promote")
def promote_recipe(
    recipe_id: str,
    operator_approved: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")
    promoted = record_passing_run_and_maybe_promote(db, recipe.id, operator_approved=operator_approved)
    db.commit()
    db.refresh(promoted)
    return promoted.to_dict()


@router.post("/v1/recipes/{recipe_id}/replay")
async def replay_recipe(
    recipe_id: str,
    replay_body: Optional[ReplayRequest] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id, Recipe.user_id == user.id).first()
    if not recipe:
        raise HTTPException(status_code=404, detail="Recipe not found")

    envelope = recipe.envelope or {}
    tool = envelope.get("tool", "image_generation")
    params = dict(envelope.get("params", {}))

    if replay_body and replay_body.override_seed is not None:
        params["seed"] = replay_body.override_seed
    elif recipe.seed is not None:
        params["seed"] = recipe.seed

    if replay_body and replay_body.override_params:
        params.update(replay_body.override_params)

    # Route through GateService.authorize_and_sign
    gate = GateService(db=db)
    signed_envelope = await gate.authorize_and_sign(
        user=user,
        tool=tool,
        params=params,
        project_id=recipe.project_id,
        persona_id=recipe.persona_id,
    )

    return {
        "status": "replayed",
        "recipe_id": recipe.id,
        "envelope": signed_envelope,
    }


# Style Rules endpoints
@router.get("/v1/projects/{project_id}/style-rules")
def list_style_rules(
    project_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rules = (
        db.query(StyleRule)
        .filter(StyleRule.user_id == user.id, StyleRule.project_id == project_id)
        .all()
    )
    return {
        "style_rules": [
            {
                "id": r.id,
                "project_id": r.project_id,
                "rule_text": r.rule_text,
                "weight": r.weight,
                "active": r.active,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rules
        ]
    }


@router.post("/v1/projects/{project_id}/style-rules")
def create_style_rule(
    project_id: str,
    body: StyleRuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rule = StyleRule(
        id=str(uuid.uuid4()),
        user_id=user.id,
        project_id=project_id,
        rule_text=body.rule_text,
        weight=body.weight,
        active=body.active,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return {
        "id": rule.id,
        "project_id": rule.project_id,
        "rule_text": rule.rule_text,
        "weight": rule.weight,
        "active": rule.active,
    }


@router.patch("/v1/projects/{project_id}/style-rules/{rule_id}")
def update_style_rule(
    project_id: str,
    rule_id: str,
    body: StyleRuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rule = (
        db.query(StyleRule)
        .filter(
            StyleRule.id == rule_id,
            StyleRule.project_id == project_id,
            StyleRule.user_id == user.id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="StyleRule not found")

    if body.rule_text is not None:
        rule.rule_text = body.rule_text
    if body.weight is not None:
        rule.weight = body.weight
    if body.active is not None:
        rule.active = body.active

    rule.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(rule)
    return {
        "id": rule.id,
        "project_id": rule.project_id,
        "rule_text": rule.rule_text,
        "weight": rule.weight,
        "active": rule.active,
    }


@router.delete("/v1/projects/{project_id}/style-rules/{rule_id}")
def delete_style_rule(
    project_id: str,
    rule_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rule = (
        db.query(StyleRule)
        .filter(
            StyleRule.id == rule_id,
            StyleRule.project_id == project_id,
            StyleRule.user_id == user.id,
        )
        .first()
    )
    if not rule:
        raise HTTPException(status_code=404, detail="StyleRule not found")

    db.delete(rule)
    db.commit()
    return {"deleted": True, "id": rule_id}
