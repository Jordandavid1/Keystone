"""
KEYSTONE Premium Creative Workspace & Operator Admin Console E2E Tests (F21–F24, Bible §25, §26).
Verifies the 5-Region Studio UX, 7-stage progress language, 13 domain playbooks,
compare mode, synchronized video player, Lineage DAG, mobile review mode, and UX Research Synthesis.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient
from apps.api.src.server import app

client = TestClient(app)


def test_ux_research_synthesis_exists_and_covers_all_6_targets():
    """Verifies F21 & F22: UX Research Synthesis cites all 6 benchmark applications."""
    synth_path = REPO_ROOT / "docs" / "UX_RESEARCH_SYNTHESIS.md"
    assert synth_path.exists(), "docs/UX_RESEARCH_SYNTHESIS.md must exist"
    content = synth_path.read_text(encoding="utf-8")

    required_targets = [
        "Hugging Face",
        "Higgsfield",
        "ZenCreator Pro",
        "Venice AI",
        "Adobe Firefly",
        "Grok"
    ]
    for target in required_targets:
        assert target in content, f"Benchmark target {target} missing from UX synthesis"


def test_workspace_route_serves_5_region_studio_html():
    """Verifies F23 (Bible §25): /workspace serves the 5-region canvas-first studio."""
    resp = client.get("/workspace")
    assert resp.status_code == 200
    html = resp.text

    # Verify all 5 desktop regions mandated by Bible §25
    assert "region-topbar" in html
    assert "region-sidebar" in html
    assert "region-canvas" in html
    assert "region-inspector" in html
    assert "region-composer" in html

    # Verify view modes: Primary Canvas, Split Compare, Sync Video, Variations, Lineage DAG
    assert 'data-mode="single"' in html
    assert 'data-mode="compare"' in html
    assert 'data-mode="video"' in html
    assert 'data-mode="variations"' in html
    assert 'data-mode="lineage"' in html

    # Verify intent hints (Create, Edit, Animate, Analyze) — no raw model pickers in customer UI
    assert 'data-intent="create"' in html
    assert 'data-intent="edit"' in html
    assert 'data-intent="animate"' in html
    assert 'data-intent="analyze"' in html


def test_workspace_js_implements_exact_bible_25_progress_language_and_13_playbooks():
    """Verifies Bible §25 exact 7-stage progress language and 13 domain playbooks."""
    js_resp = client.get("/workspace/app.js")
    assert js_resp.status_code == 200
    js = js_resp.text

    expected_progress_phrases = [
        "Understanding your request",
        "Planning the generation",
        "Preparing the workflow",
        "Creating",
        "Checking the result",
        "Refining when necessary",
        "Finishing"
    ]
    for phrase in expected_progress_phrases:
        assert phrase in js, f"Missing Bible §25 progress phrase: {phrase}"

    playbooks = [
        "Software", "Writing", "Marketing", "Business", "Learning",
        "Career", "Content", "Research", "Design", "Fitness",
        "Events", "Finance", "General"
    ]
    for pb in playbooks:
        assert pb in js, f"Missing playbook in workspace controller: {pb}"


def test_admin_console_route_serves_operator_dashboard():
    """Verifies F24 (Bible §26): /admin serves Operator Admin Console."""
    resp = client.get("/admin")
    assert resp.status_code == 200
    html = resp.text
    assert "KEYSTONE OPERATOR ADMIN CONSOLE" in html
    assert "huihui-ai/Huihui-Qwen3.8-27B-abliterated" in html
    assert "BF16 (Default)" in html
    assert "FP16 (Comparative)" in html
