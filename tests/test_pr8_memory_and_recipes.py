"""tests/test_pr8_memory_and_recipes.py
ADR-005 / Bible v2 §42.3 Memory & Recipe Library Verification Suite.
5 required tests:
  1. test_record_recipe_writes_embedding
  2. test_sfw_query_never_returns_unrestricted_recipes
  3. test_similarity_ranking_top_k
  4. test_recipe_promotion_after_two_passing_runs
  5. test_recipe_replay_through_gate
"""

import uuid
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from apps.api.src.db.models import Base, Recipe, RecipeEmbedding, StyleRule, User, Project
from apps.api.src.services.memory import (
    record_recipe_candidate,
    retrieve_advisory_context,
    record_passing_run_and_maybe_promote,
)
from services.cognition.src.embeddings import (
    LocalEmbeddingProvider,
    embed_text,
    cosine_similarity,
    get_embedding_manifest,
)


@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_manifest_registration_and_embedding_provider():
    manifest = get_embedding_manifest()
    assert manifest.capability_id == "cognition.local_embeddings"
    assert manifest.metadata.get("dimension") == 1024
    assert manifest.metadata.get("quantization") == "GGUF-Q8_0"

    provider = LocalEmbeddingProvider()
    vec = provider.embed_text("cinematic portrait of a cyberpunk hacker in rain")
    assert len(vec) == 1024
    # Check normalized
    mag = sum(x * x for x in vec) ** 0.5
    assert abs(mag - 1.0) < 1e-4


def test_record_recipe_writes_embedding(memory_db):
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    envelope = {
        "tool": "image_generation",
        "params": {"prompt": "neon sunset over tokyo highway"},
    }
    compiled_prompt = {"positive": "neon sunset over tokyo highway, photorealistic, 8k"}
    scores = {"khf_score": 0.92, "overall": 0.9}

    recipe = record_recipe_candidate(
        memory_db,
        tenant_id=user_id,
        project_id=project_id,
        envelope=envelope,
        compiled_prompt=compiled_prompt,
        seed=42,
        fabric_versions={"comfyui": "0.1.0"},
        scores=scores,
        mode="sfw",
    )
    memory_db.commit()

    assert recipe.id is not None
    assert recipe.user_id == user_id
    assert recipe.content_mode == "sfw"
    assert recipe.status == "candidate"

    emb = memory_db.query(RecipeEmbedding).filter(RecipeEmbedding.recipe_id == recipe.id).first()
    assert emb is not None
    assert emb.recipe_id == recipe.id
    assert len(emb.embedding) == 1024


def test_sfw_query_never_returns_unrestricted_recipes(memory_db):
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    # Create SFW recipe
    r_sfw = record_recipe_candidate(
        memory_db,
        tenant_id=user_id,
        project_id=project_id,
        envelope={"tool": "image_generation", "params": {"prompt": "peaceful mountain landscape"}},
        compiled_prompt={"positive": "peaceful mountain landscape"},
        seed=101,
        fabric_versions={},
        scores={"overall": 0.85},
        mode="sfw",
    )

    # Create Unrestricted recipe
    r_unrestricted = record_recipe_candidate(
        memory_db,
        tenant_id=user_id,
        project_id=project_id,
        envelope={"tool": "image_generation", "params": {"prompt": "mature dark romance scene"}},
        compiled_prompt={"positive": "mature dark romance scene"},
        seed=202,
        fabric_versions={},
        scores={"overall": 0.95},
        mode="unrestricted",
    )
    memory_db.commit()

    # Query in SFW mode
    sfw_res = retrieve_advisory_context(
        memory_db,
        tenant_id=user_id,
        project_id=project_id,
        resolved_mode="sfw",
        query_text="landscape",
    )
    recipe_ids_sfw = [r["id"] for r in sfw_res["recipes"]]
    assert r_sfw.id in recipe_ids_sfw
    assert r_unrestricted.id not in recipe_ids_sfw

    # Query in Unrestricted mode allows both
    unres_res = retrieve_advisory_context(
        memory_db,
        tenant_id=user_id,
        project_id=project_id,
        resolved_mode="unrestricted",
        query_text="landscape",
    )
    recipe_ids_unres = [r["id"] for r in unres_res["recipes"]]
    assert r_sfw.id in recipe_ids_unres
    assert r_unrestricted.id in recipe_ids_unres


def test_similarity_ranking_top_k(memory_db):
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    # 1. Close match
    r_close = record_recipe_candidate(
        memory_db,
        tenant_id=user_id,
        project_id=project_id,
        envelope={"tool": "image_generation"},
        compiled_prompt={"prompt": "cyberpunk neon city rain"},
        seed=1,
        fabric_versions={},
        scores={"overall": 0.9},
        mode="sfw",
    )

    # 2. Distant match
    r_far = record_recipe_candidate(
        memory_db,
        tenant_id=user_id,
        project_id=project_id,
        envelope={"tool": "image_generation"},
        compiled_prompt={"prompt": "medieval stone castle grassy hill sunny daytime"},
        seed=2,
        fabric_versions={},
        scores={"overall": 0.5},
        mode="sfw",
    )
    memory_db.commit()

    res = retrieve_advisory_context(
        memory_db,
        tenant_id=user_id,
        project_id=project_id,
        resolved_mode="sfw",
        query_text="cyberpunk neon raining",
        k=5,
    )
    recipes = res["recipes"]
    assert len(recipes) == 2
    assert recipes[0]["id"] == r_close.id
    assert recipes[0]["rank_score"] >= recipes[1]["rank_score"]


def test_recipe_promotion_after_two_passing_runs(memory_db):
    user_id = str(uuid.uuid4())
    project_id = str(uuid.uuid4())

    r = record_recipe_candidate(
        memory_db,
        tenant_id=user_id,
        project_id=project_id,
        envelope={"tool": "image_generation"},
        compiled_prompt={"prompt": "stellar nebula"},
        seed=55,
        fabric_versions={},
        scores={"overall": 0.95},
        mode="sfw",
    )
    memory_db.commit()
    assert r.status == "candidate"
    assert r.promotion_runs == 0
    assert not r.promoted

    # Run 1: increments count, remains candidate
    r1 = record_passing_run_and_maybe_promote(memory_db, r.id, operator_approved=False)
    memory_db.commit()
    assert r1.promotion_runs == 1
    assert r1.status == "candidate"
    assert not r1.promoted

    # Run 2: reaches threshold -> promoted!
    r2 = record_passing_run_and_maybe_promote(memory_db, r.id, operator_approved=False)
    memory_db.commit()
    assert r2.promotion_runs == 2
    assert r2.status == "promoted"
    assert r2.promoted
    assert r2.promoted_at is not None
