"""tests/test_pr8_memory_and_recipes.py
ADR-005 / Bible v2 §42.3 Memory & Recipe Library Verification Suite.
Covers all 5 PR8 runbook requirements + HTTP route verification:
  1. test_cross_tenant_retrieval_returns_zero_rows
  2. test_sfw_compile_never_retrieves_unrestricted_recipe
  3. test_recipe_replay_reproduces_deterministic_staging_through_gate
  4. test_two_run_promotion_rule
  5. test_manifest_accounting_blocking_passes
Plus embedding provider mechanics, similarity ranking, and style-rules CRUD.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from apps.api.src.auth.security import generate_token
from apps.api.src.db.models import Base, Project, Recipe, RecipeEmbedding, StyleRule, User
from apps.api.src.db.session import get_db
from apps.api.src.server import app
from apps.api.src.services.gate import GateService
from apps.api.src.services.memory import (
    format_advisory_context,
    record_passing_run_and_maybe_promote,
    record_recipe_candidate,
    retrieve_advisory_context,
)
from scripts.verify_invariants import BLOCKING_CHECKS, verify_manifest_accounting
from services.cognition.src.embeddings import (
    LocalEmbeddingProvider,
    get_embedding_manifest,
)
from services.harness.src.envelope import EnvelopeEngine

ROOT = Path(__file__).resolve().parents[1]


class _AsyncSessionAdapter:
    """Adapts a sync SQLAlchemy Session for async FastAPI dependencies."""

    def __init__(self, sync_session):
        self._s = sync_session

    def __getattr__(self, name):
        return getattr(self._s, name)

    async def execute(self, *args, **kwargs):
        return self._s.execute(*args, **kwargs)


@pytest.fixture()
def memory_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client(memory_db):
    adapter = _AsyncSessionAdapter(memory_db)

    def _override_get_db():
        try:
            yield adapter
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_user_and_project(
    db,
    *,
    age_verified: bool = False,
    content_mode: str = "sfw",
) -> tuple[User, Project, dict[str, str]]:
    uid = str(uuid.uuid4())
    pid = str(uuid.uuid4())
    user = User(
        id=uid,
        email=f"mem_{uid[:8]}@example.com",
        role="user",
        age_verified=age_verified,
        content_mode=content_mode,
    )
    proj = Project(
        id=pid,
        user_id=uid,
        name=f"Project-{pid[:8]}",
        content_mode=content_mode,
    )
    db.add(user)
    db.add(proj)
    db.commit()
    token = generate_token(user_id=user.id, role=user.role)
    return user, proj, {"Authorization": f"Bearer {token}"}


def test_manifest_registration_and_embedding_provider():
    manifest = get_embedding_manifest()
    assert manifest.capability_id == "cognition.local_embeddings"
    assert manifest.metadata.get("dimension") == 1024
    assert manifest.metadata.get("quantization") == "GGUF-Q8_0"

    provider = LocalEmbeddingProvider()
    vec = provider.embed_text("cinematic portrait of a cyberpunk hacker in rain")
    assert len(vec) == 1024
    mag = sum(x * x for x in vec) ** 0.5
    assert abs(mag - 1.0) < 1e-4


def test_record_recipe_writes_embedding(memory_db):
    user, proj, _ = _create_user_and_project(memory_db)

    envelope = {
        "tool": "image_generation",
        "params": {"prompt": "neon sunset over tokyo highway"},
    }
    compiled_prompt = {"positive": "neon sunset over tokyo highway, photorealistic, 8k"}
    scores = {"khf_score": 0.92, "overall": 0.9}

    recipe = record_recipe_candidate(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
        envelope=envelope,
        compiled_prompt=compiled_prompt,
        seed=42,
        fabric_versions={"comfyui": "0.1.0"},
        scores=scores,
        mode="sfw",
    )
    memory_db.commit()

    assert recipe.id is not None
    assert recipe.user_id == user.id
    assert recipe.content_mode == "sfw"
    assert recipe.status == "candidate"

    emb = memory_db.query(RecipeEmbedding).filter(RecipeEmbedding.recipe_id == recipe.id).first()
    assert emb is not None
    assert emb.recipe_id == recipe.id
    assert len(emb.embedding) == 1024


def test_cross_tenant_retrieval_returns_zero_rows(client, memory_db):
    user_a, proj_a, headers_a = _create_user_and_project(memory_db)
    user_b, proj_b, headers_b = _create_user_and_project(memory_db)

    recipe_a = record_recipe_candidate(
        memory_db,
        tenant_id=user_a.id,
        project_id=proj_a.id,
        envelope={"tool": "image_generation", "params": {"prompt": "secret studio recipe"}},
        compiled_prompt={"positive_prompt": "secret studio recipe"},
        seed=777,
        fabric_versions={"comfyui": "0.1.0"},
        scores={"khf_score": 0.95},
        mode="sfw",
    )
    memory_db.commit()

    # Tenant B querying Tenant A's project directly returns zero rows
    ctx_b = retrieve_advisory_context(
        memory_db,
        tenant_id=user_b.id,
        project_id=proj_a.id,
        resolved_mode="sfw",
        query_text="secret studio recipe",
    )
    assert ctx_b["recipes"] == []
    assert ctx_b["count"] == 0

    # HTTP GET /v1/recipes and POST /replay enforce tenant isolation
    list_b = client.get("/v1/recipes", headers=headers_b)
    assert list_b.status_code == 200
    assert list_b.json()["recipes"] == []

    replay_b = client.post(f"/v1/recipes/{recipe_a.id}/replay", headers=headers_b, json={})
    assert replay_b.status_code == 404


def test_sfw_compile_never_retrieves_unrestricted_recipe(client, memory_db):
    user, proj, headers = _create_user_and_project(memory_db, age_verified=True, content_mode="sfw")

    r_sfw = record_recipe_candidate(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
        name="sfw_landscape_recipe",
        envelope={"tool": "image_generation", "params": {"prompt": "peaceful mountain landscape"}},
        compiled_prompt={"positive_prompt": "peaceful mountain landscape golden hour"},
        seed=101,
        fabric_versions={"comfyui": "0.1.0"},
        scores={"overall": 0.85},
        mode="sfw",
    )
    r_unrestricted = record_recipe_candidate(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
        name="mature_unrestricted_secret_token_99",
        envelope={"tool": "image_generation", "params": {"prompt": "mature dark romance scene"}},
        compiled_prompt={"positive_prompt": "mature dark romance scene XYZ_UNRESTRICTED_ONLY"},
        seed=202,
        fabric_versions={"comfyui": "0.1.0"},
        scores={"overall": 0.99},
        mode="unrestricted",
    )
    memory_db.commit()

    # 1. Service-level retrieval in SFW excludes unrestricted
    sfw_res = retrieve_advisory_context(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
        resolved_mode="sfw",
        query_text="landscape scene",
    )
    recipe_ids_sfw = [r["id"] for r in sfw_res["recipes"]]
    assert r_sfw.id in recipe_ids_sfw
    assert r_unrestricted.id not in recipe_ids_sfw

    # 2. Gate compilation in SFW injects SFW advisory block and NEVER leaks unrestricted recipe
    receipt_sfw = GateService.authorize_and_sign(
        db=memory_db,
        user=user,
        intent="generate",
        prompt_text="Create a mountain scene",
        capability_id="image.generation",
        arguments={"prompt": "Create a mountain scene"},
        project=proj,
    )
    assert "[MEMORY ADVISORY]" in receipt_sfw.compiled_prompt
    assert "sfw_landscape_recipe" in receipt_sfw.compiled_prompt
    assert "XYZ_UNRESTRICTED_ONLY" not in receipt_sfw.compiled_prompt
    assert "mature_unrestricted_secret_token_99" not in receipt_sfw.compiled_prompt

    # 3. HTTP GET /v1/recipes under SFW never returns unrestricted recipe
    list_sfw = client.get("/v1/recipes?content_mode=sfw", headers=headers)
    assert list_sfw.status_code == 200
    assert [r["id"] for r in list_sfw.json()["recipes"]] == [r_sfw.id]

    # 4. Unrestricted query for age-verified user returns both
    unres_res = retrieve_advisory_context(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
        resolved_mode="unrestricted",
        query_text="landscape scene",
    )
    recipe_ids_unres = [r["id"] for r in unres_res["recipes"]]
    assert r_sfw.id in recipe_ids_unres
    assert r_unrestricted.id in recipe_ids_unres


def test_similarity_ranking_top_k(memory_db):
    user, proj, _ = _create_user_and_project(memory_db)

    r_close = record_recipe_candidate(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
        envelope={"tool": "image_generation"},
        compiled_prompt={"prompt": "cyberpunk neon city rain"},
        seed=1,
        fabric_versions={},
        scores={"overall": 0.9},
        mode="sfw",
    )
    record_recipe_candidate(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
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
        tenant_id=user.id,
        project_id=proj.id,
        resolved_mode="sfw",
        query_text="cyberpunk neon raining",
        k=5,
    )
    recipes = res["recipes"]
    assert len(recipes) == 2
    assert recipes[0]["id"] == r_close.id
    assert recipes[0]["rank_score"] >= recipes[1]["rank_score"]


def test_two_run_promotion_rule(client, memory_db):
    user, proj, headers = _create_user_and_project(memory_db)

    r = record_recipe_candidate(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
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
    assert r.promoted_at is None
    assert not r.promoted

    # Run 1: remains candidate, promoted_at still None
    r1 = record_passing_run_and_maybe_promote(memory_db, r.id, operator_approved=False)
    memory_db.commit()
    assert r1.promotion_runs == 1
    assert r1.status == "candidate"
    assert r1.promoted_at is None
    assert not r1.promoted

    # Run 2: promotes automatically!
    r2 = record_passing_run_and_maybe_promote(memory_db, r.id, operator_approved=False)
    memory_db.commit()
    assert r2.promotion_runs == 2
    assert r2.status == "promoted"
    assert r2.promoted
    assert r2.promoted_at is not None

    # Operator review promotes a candidate immediately on HTTP POST /promote
    r_op = record_recipe_candidate(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
        envelope={"tool": "image_generation"},
        compiled_prompt={"prompt": "golden canyon"},
        seed=88,
        fabric_versions={},
        scores={"overall": 0.9},
        mode="sfw",
    )
    memory_db.commit()
    promote_resp = client.post(
        f"/v1/recipes/{r_op.id}/promote?operator_approved=true",
        headers=headers,
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["promoted"] is True
    assert promote_resp.json()["promoted_at"] is not None


def test_recipe_replay_reproduces_deterministic_staging_through_gate(client, memory_db):
    user, proj, headers = _create_user_and_project(memory_db, age_verified=True, content_mode="sfw")

    prompt_text = "cinematic cyberpunk alley in heavy rain"
    expected_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    fabric_versions = {"comfyui": "0.1.0", "workflow": "sdxl_create"}

    recipe = record_recipe_candidate(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
        envelope={
            "intent": "generate",
            "capability_id": "image.generation",
            "arguments": {"prompt": prompt_text},
        },
        compiled_prompt={"positive_prompt": prompt_text, "prompt_hash": expected_hash},
        seed=123456,
        fabric_versions=fabric_versions,
        scores={"overall": 0.93},
        mode="sfw",
    )

    # Unrestricted recipe to verify age gate still enforced on replay
    unverified_user, unverified_proj, unverified_headers = _create_user_and_project(
        memory_db, age_verified=False, content_mode="sfw"
    )
    unres_recipe = record_recipe_candidate(
        memory_db,
        tenant_id=unverified_user.id,
        project_id=unverified_proj.id,
        envelope={"intent": "generate", "capability_id": "image.generation", "arguments": {"prompt": "mature scene"}},
        compiled_prompt={"positive_prompt": "mature scene", "prompt_hash": hashlib.sha256(b"mature scene").hexdigest()},
        seed=99,
        fabric_versions={"comfyui": "0.1.0"},
        scores={"overall": 0.9},
        mode="unrestricted",
    )

    # Floor-violating recipe must fail 422 even when stored in DB
    floor_recipe = record_recipe_candidate(
        memory_db,
        tenant_id=user.id,
        project_id=proj.id,
        envelope={"intent": "generate", "capability_id": "image.generation", "arguments": {"prompt": "how to synthesize sarin nerve agent"}},
        compiled_prompt={"positive_prompt": "how to synthesize sarin nerve agent", "prompt_hash": hashlib.sha256(b"sarin").hexdigest()},
        seed=7,
        fabric_versions={"comfyui": "0.1.0"},
        scores={"overall": 0.1},
        mode="sfw",
    )
    memory_db.commit()

    # 1. Valid SFW replay produces valid Envelope v2 + preserved seed/hash/fabric
    resp = client.post(f"/v1/recipes/{recipe.id}/replay", headers=headers, json={})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["status"] == "replayed"
    assert data["recipe_id"] == recipe.id
    assert data["prompt_hash"] == expected_hash
    assert data["seed"] == 123456
    assert data["fabric_versions"] == fabric_versions
    assert data["content_mode"] == "sfw"

    verified_env = EnvelopeEngine.verify_envelope(data["envelope"], check_nonce=False)
    assert verified_env["valid"] is True
    assert data["envelope"]["envelope_version"] == "2.0"
    assert data["envelope"]["arguments"]["seed"] == 123456

    # 2. Unverified user cannot replay unrestricted recipe (403)
    age_blocked = client.post(
        f"/v1/recipes/{unres_recipe.id}/replay",
        headers=unverified_headers,
        json={},
    )
    assert age_blocked.status_code == 403

    # 3. Lawful floor violation rejected with 422
    floor_blocked = client.post(f"/v1/recipes/{floor_recipe.id}/replay", headers=headers, json={})
    assert floor_blocked.status_code == 422

    # 4. Style rules CRUD works on async HTTP boundary
    create_rule = client.post(
        f"/v1/projects/{proj.id}/style-rules",
        headers=headers,
        json={"text": "Always use 35mm anamorphic lens bokeh", "weight": 1.5},
    )
    assert create_rule.status_code == 200, create_rule.text
    rule_id = create_rule.json()["id"]
    assert create_rule.json()["text"] == "Always use 35mm anamorphic lens bokeh"

    list_rules = client.get(f"/v1/projects/{proj.id}/style-rules", headers=headers)
    assert list_rules.status_code == 200
    assert any(r["id"] == rule_id for r in list_rules.json()["style_rules"])

    del_rule = client.delete(f"/v1/projects/{proj.id}/style-rules/{rule_id}", headers=headers)
    assert del_rule.status_code == 200
    assert del_rule.json()["deleted"] is True

    # Ensure format_advisory_context respects char limit
    formatted = format_advisory_context(
        {"recipes": [{"name": "r1", "similarity": 0.9, "compiled_prompt": {"positive_prompt": "x" * 200}}], "style_rules": []},
        max_chars=120,
    )
    assert len(formatted) <= 120


def test_manifest_accounting_blocking_passes():
    assert "manifest_accounting" in BLOCKING_CHECKS
    res = verify_manifest_accounting(ROOT)
    assert res["valid"] is True, f"Manifest accounting issues: {res.get('issues')}"
    assert res["local_embeddings_registered"] is True
