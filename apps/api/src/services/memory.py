"""apps/api/src/services/memory.py
ADR-005 / Bible v2 §42.3 Memory & Recipe Library Service.
Implements pgvector recipe candidate recording, advisory context retrieval with mode scoping,
cosine similarity ranking, token-budgeted formatting, and 2-run promotion.
"""

from __future__ import annotations

import inspect
import math
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

import sqlalchemy as sa
from sqlalchemy.orm import Session

from apps.api.src.db.models import Recipe, RecipeEmbedding, StyleRule
from services.cognition.src.embeddings import (
    KEYSTONE_EMBEDDING_DIM,
    cosine_similarity,
    embed_text,
)

T = TypeVar("T")


def _safe_float(val: Any, default: float = 0.0) -> float:
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


async def _run_sync(db: Any, fn: Callable[[Session], T]) -> T:
    """Execute a synchronous ORM callable against AsyncSession, _AsyncSessionAdapter, or sync Session."""
    if hasattr(db, "run_sync"):
        res = db.run_sync(fn)
        if inspect.isawaitable(res):
            return await res
        return res
    sync_session = getattr(db, "_s", db)
    return fn(sync_session)


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
        tool = (envelope or {}).get("tool") or (envelope or {}).get("capability_id") or "asset"
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

    if embedding is None:
        text_for_embed = ""
        if isinstance(compiled_prompt, dict):
            text_for_embed = (
                compiled_prompt.get("user_prompt")
                or compiled_prompt.get("positive_prompt")
                or compiled_prompt.get("prompt")
                or compiled_prompt.get("raw_prompt")
                or ""
            )
        if not text_for_embed and isinstance(envelope, dict):
            params = envelope.get("params") or envelope.get("arguments") or {}
            text_for_embed = str(params.get("prompt", ""))
        embedding = embed_text(text_for_embed or name)

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

    # Mandatory SQL scope invariant (SPEC_MEMORY.md §3):
    # - tenant_id matches, project_id matches, never retired
    # - SFW mode strictly filters content_mode == 'sfw' (no unrestricted leak)
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

    try:
        from apps.api.src.services.floor_watchdog import floor_watchdog
    except Exception:
        floor_watchdog = None

    now = datetime.now(timezone.utc)
    scored_candidates: List[Tuple[float, Recipe, float]] = []

    for recipe, emb_row in results:
        if floor_watchdog is not None:
            cp = recipe.compiled_prompt or {}
            snippet = ""
            if isinstance(cp, dict):
                snippet = str(
                    cp.get("positive_prompt")
                    or cp.get("prompt")
                    or cp.get("user_prompt")
                    or cp.get("raw_prompt")
                    or ""
                )
            if not snippet and isinstance(recipe.envelope, dict):
                params = recipe.envelope.get("params") or recipe.envelope.get("arguments") or {}
                if isinstance(params, dict):
                    snippet = str(params.get("prompt") or "")
            if snippet and floor_watchdog.evaluate(prompt_text=snippet, content_mode=norm_mode).verdict == "fail":
                continue

        emb_vector = None
        if emb_row and emb_row.embedding is not None:
            emb_vector = list(emb_row.embedding)

        sim = 0.5
        if emb_vector and query_embedding:
            sim = cosine_similarity(query_embedding, emb_vector)

        quality = 0.5
        score_per_credit = 0.5
        if isinstance(recipe.scores, dict):
            quality = _safe_float(
                recipe.scores.get("khf_score")
                or recipe.scores.get("composite_score")
                or recipe.scores.get("overall"),
                default=0.5,
            )
            cost = max(
                1.0,
                _safe_float(
                    recipe.scores.get("cost") or recipe.scores.get("credits"),
                    default=1.0,
                ),
            )
            score_per_credit = min(
                1.0,
                _safe_float(
                    recipe.scores.get("score_per_credit"),
                    default=(quality / cost),
                ),
            )

        # Recency decay (half-life ~30 days)
        recency = 1.0
        if recipe.created_at:
            dt = recipe.created_at
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
            recency = math.exp(-0.023 * age_days)

        rank_score = (
            (0.45 * sim)
            + (0.30 * quality)
            + (0.10 * score_per_credit)
            + (0.15 * recency)
        )
        if recipe.promoted:
            rank_score += 0.1
        if persona_id and recipe.persona_id == persona_id:
            rank_score += 0.12

        scored_candidates.append((rank_score, recipe, sim))

    scored_candidates.sort(key=lambda x: x[0], reverse=True)
    top_k = scored_candidates[:k]

    recipes_payload = []
    for rank_score, r, sim in top_k:
        d = r.to_dict()
        d["similarity"] = round(sim, 4)
        d["rank_score"] = round(rank_score, 4)
        recipes_payload.append(d)

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
            "text": rule.rule_text,
            "weight": float(rule.weight) if rule.weight is not None else 1.0,
            "active": bool(rule.active),
        }
        for rule in style_rules_query
    ]

    return {
        "recipes": recipes_payload,
        "style_rules": style_rules_payload,
        "resolved_mode": norm_mode,
        "count": len(recipes_payload),
    }


def format_advisory_context(
    advisory: Optional[Dict[str, Any]],
    *,
    max_chars: int = 1200,
) -> str:
    """Format retrieved style rules and recipes into a concise, token-budgeted advisory block."""
    if not advisory or not isinstance(advisory, dict):
        return ""

    recipes = advisory.get("recipes") or []
    style_rules = advisory.get("style_rules") or []
    if not recipes and not style_rules:
        return ""

    sections: List[str] = []
    if style_rules:
        rule_lines = []
        for rule in style_rules:
            r_text = str(rule.get("rule_text") or rule.get("text") or "").strip()
            if r_text:
                w = _safe_float(rule.get("weight"), default=1.0)
                rule_lines.append(f"- {r_text} (weight={w:.1f})")
        if rule_lines:
            sections.append("Style Rules:\n" + "\n".join(rule_lines))

    if recipes:
        rec_lines = []
        for r in recipes:
            r_name = str(r.get("name") or r.get("id") or "recipe").strip()
            cp = r.get("compiled_prompt") or {}
            prompt_snippet = ""
            if isinstance(cp, dict):
                prompt_snippet = str(
                    cp.get("positive_prompt")
                    or cp.get("prompt")
                    or cp.get("user_prompt")
                    or ""
                ).strip()
            if len(prompt_snippet) > 160:
                prompt_snippet = prompt_snippet[:157].rstrip() + "..."
            sim = r.get("similarity")
            tag = f"sim={sim}" if sim is not None else f"seed={r.get('seed')}"
            rec_lines.append(
                f"- {r_name} ({tag}): {prompt_snippet}" if prompt_snippet else f"- {r_name} ({tag})"
            )
        if rec_lines:
            sections.append("Proven Recipes:\n" + "\n".join(rec_lines))

    if not sections:
        return ""

    formatted = "\n".join(sections)
    if len(formatted) > max_chars:
        formatted = formatted[: max(0, max_chars - 3)].rstrip() + "..."
    return formatted


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


async def record_recipe_candidate_async(
    db: Any,
    **kwargs: Any,
) -> Recipe:
    return await _run_sync(db, lambda sync_db: record_recipe_candidate(sync_db, **kwargs))


async def retrieve_advisory_context_async(
    db: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    return await _run_sync(db, lambda sync_db: retrieve_advisory_context(sync_db, **kwargs))


async def record_passing_run_and_maybe_promote_async(
    db: Any,
    recipe_id: str,
    *,
    operator_approved: bool = False,
) -> Recipe:
    return await _run_sync(
        db,
        lambda sync_db: record_passing_run_and_maybe_promote(
            sync_db,
            recipe_id,
            operator_approved=operator_approved,
        ),
    )
