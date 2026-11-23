"""apps/api/src/services/memory.py
ADR-005 / Bible v2 §42.3 Memory & Recipe Library Service.
Implements pgvector recipe candidate recording, advisory context retrieval with mode scoping,
cosine similarity ranking, and 2-run promotion.
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import sqlalchemy as sa
from sqlalchemy.orm import Session

from apps.api.src.db.models import Recipe, RecipeEmbedding, StyleRule
from services.cognition.src.embeddings import (
    KEYSTONE_EMBEDDING_DIM,
    cosine_similarity,
    embed_text,
)


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def record_recipe_candidate(
    db: Session,
    *,
    tenant_id: str,
    project_id: str,
    envelope: Dict[str, Any],
    compiled_prompt: Dict[str, Any],
    seed: int,
    fabric_versions: Dict[str, Any],
    scores: Dict[str, Any],
    mode: str,
    persona_id: Optional[str] = None,
    name: Optional[str] = None,
    embedding: Optional[List[float]] = None,
) -> Recipe:
    """Record a recipe candidate in the database along with its pgvector embedding."""
    resolved_mode = (mode or "sfw").lower().strip()
    if resolved_mode not in ("sfw", "unrestricted"):
        resolved_mode = "sfw"

    recipe_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    if not name:
        tool = (envelope or {}).get("tool", "asset")
        name = f"recipe-{tool}-{recipe_id[:8]}"

    recipe = Recipe(
        id=recipe_id,
        user_id=tenant_id,
        project_id=project_id,
        persona_id=persona_id,
        name=name,
        envelope=envelope,
        compiled_prompt=compiled_prompt,
        seed=int(seed) if seed is not None else 0,
        fabric_versions=fabric_versions or {},
        scores=scores or {},
        content_mode=resolved_mode,
        status="candidate",
        promotion_runs=0,
        promoted_at=None,
        created_at=now,
        updated_at=now,
    )
    db.add(recipe)
    db.flush()

    # Calculate embedding if not supplied
    if embedding is None:
        text_for_embed = ""
        if isinstance(compiled_prompt, dict):
            text_for_embed = (
                compiled_prompt.get("user_prompt")
                or compiled_prompt.get("prompt")
                or compiled_prompt.get("raw_prompt")
                or ""
            )
        if not text_for_embed and isinstance(envelope, dict):
            text_for_embed = str(envelope.get("params", {}).get("prompt", ""))
        embedding = embed_text(text_for_embed or name)

    # Pad or truncate to KEYSTONE_EMBEDDING_DIM
    if len(embedding) != KEYSTONE_EMBEDDING_DIM:
        if len(embedding) < KEYSTONE_EMBEDDING_DIM:
            embedding = list(embedding) + [0.0] * (KEYSTONE_EMBEDDING_DIM - len(embedding))
        else:
            embedding = list(embedding[:KEYSTONE_EMBEDDING_DIM])

    recipe_embedding = RecipeEmbedding(
        recipe_id=recipe_id,
        embedding=embedding,
        model="qwen-embedding-1024",
        created_at=now,
    )
    db.add(recipe_embedding)
    db.flush()

    return recipe


def retrieve_advisory_context(
    db: Session,
    *,
    tenant_id: str,
    project_id: str,
    resolved_mode: str,
    query_embedding: Optional[List[float]] = None,
    persona_id: Optional[str] = None,
    query_text: Optional[str] = None,
    k: int = 5,
) -> Dict[str, Any]:
    """Retrieve advisory recipes and active style rules with strict mode and tenant scoping."""
    norm_mode = (resolved_mode or "sfw").lower().strip()
    if norm_mode not in ("sfw", "unrestricted"):
        norm_mode = "sfw"

    if query_embedding is None:
        query_embedding = embed_text(query_text or "advisory context query")

    # Invariant: If mode is SFW, strictly filter by content_mode == 'sfw' (no unrestricted recipes leak).
    # If mode is unrestricted, user may access sfw and unrestricted recipes.
    query = (
        db.query(Recipe, RecipeEmbedding)
        .outerjoin(RecipeEmbedding, Recipe.id == RecipeEmbedding.recipe_id)
        .filter(Recipe.user_id == tenant_id)
        .filter(Recipe.project_id == project_id)
        .filter(Recipe.status != "retired")
    )

    if norm_mode == "sfw":
        query = query.filter(Recipe.content_mode == "sfw")

    if persona_id:
        query = query.filter(
            sa.or_(Recipe.persona_id == persona_id, Recipe.persona_id.is_(None))
        )

    results = query.all()

    now = datetime.now(timezone.utc)
    scored_candidates: List[Tuple[float, Recipe, float]] = []

    for recipe, emb_row in results:
        emb_vector = None
        if emb_row and emb_row.embedding is not None:
            emb_vector = list(emb_row.embedding)

        sim = 0.5
        if emb_vector and query_embedding:
            sim = cosine_similarity(query_embedding, emb_vector)

        # Quality multiplier from scores (KHF aggregate)
        quality = 0.5
        if isinstance(recipe.scores, dict):
            quality = _safe_float(
                recipe.scores.get("khf_score")
                or recipe.scores.get("composite_score")
                or recipe.scores.get("overall"),
                default=0.5,
            )

        # Recency decay (half-life of 30 days)
        recency = 1.0
        if recipe.created_at:
            dt = recipe.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
            recency = math.exp(-0.023 * age_days)  # ~0.5 at 30 days

        # Composite score
        rank_score = (0.5 * sim) + (0.35 * quality) + (0.15 * recency)
        if recipe.promoted:
            rank_score += 0.1  # Promoted boost

        scored_candidates.append((rank_score, recipe, sim))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    top_k = scored_candidates[:k]

    recipes_payload = []
    for rank_score, r, sim in top_k:
        d = r.to_dict()
        d["similarity"] = round(sim, 4)
        d["rank_score"] = round(rank_score, 4)
        recipes_payload.append(d)

    # Active StyleRules
    style_rules_query = (
        db.query(StyleRule)
        .filter(StyleRule.user_id == tenant_id)
        .filter(StyleRule.project_id == project_id)
        .filter(StyleRule.active.is_(True))
        .all()
    )
    style_rules_payload = [
        {
            "id": rule.id,
            "rule_text": rule.rule_text,
            "weight": rule.weight,
            "active": rule.active,
        }
        for rule in style_rules_query
    ]

    return {
        "recipes": recipes_payload,
        "style_rules": style_rules_payload,
        "resolved_mode": norm_mode,
        "count": len(recipes_payload),
    }


def record_passing_run_and_maybe_promote(
    db: Session,
    recipe_id: str,
    *,
    operator_approved: bool = False,
) -> Recipe:
    """Record a passing evaluation run. Promotes immediately on operator approval or on 2 passing runs."""
    recipe = db.query(Recipe).filter(Recipe.id == recipe_id).first()
    if not recipe:
        raise ValueError(f"Recipe not found: {recipe_id}")

    recipe.promotion_runs = (recipe.promotion_runs or 0) + 1
    now = datetime.now(timezone.utc)
    recipe.updated_at = now

    if operator_approved or recipe.promotion_runs >= 2:
        recipe.status = "promoted"
        if not recipe.promoted_at:
            recipe.promoted_at = now

    db.flush()
    return recipe
