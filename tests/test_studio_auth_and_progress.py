"""Studio sign-in paths (dev bypass guard) and live generation progress."""

import uuid

import pytest

from apps.api.src.auth import dependencies as deps
from apps.api.src.jobs import generation_progress as gp


class _Client:
    def __init__(self, host):
        self.host = host


class _Req:
    def __init__(self, host="127.0.0.1", headers=None):
        self.client = _Client(host)
        self.headers = headers or {}


def test_dev_bypass_off_by_default(monkeypatch):
    monkeypatch.delenv(deps.DEV_BYPASS_ENV, raising=False)
    assert not deps.dev_bypass_applies(_Req(), None, None)


def test_dev_bypass_loopback_only(monkeypatch):
    monkeypatch.setenv(deps.DEV_BYPASS_ENV, "1")
    assert deps.dev_bypass_applies(_Req(), None, None)
    assert not deps.dev_bypass_applies(_Req(host="10.0.0.8"), None, None)
    assert not deps.dev_bypass_applies(_Req(headers={"x-forwarded-for": "203.0.113.9"}), None, None)
    assert deps.dev_bypass_applies(_Req(headers={"x-forwarded-for": "::ffff:127.0.0.1"}), None, None)


def test_dev_bypass_never_overrides_sent_credentials(monkeypatch):
    monkeypatch.setenv(deps.DEV_BYPASS_ENV, "1")
    assert not deps.dev_bypass_applies(_Req(), "Bearer x", None)
    assert not deps.dev_bypass_applies(_Req(), None, "ks_live_x")


def test_progress_follows_state_machine():
    jid = str(uuid.uuid4())
    p = gp.GenerationProgress(jid, "run_any_llm")
    for st in ("VALIDATING", "PLANNING", "AUTHORIZING", "QUEUED", "RUNNING", "VALIDATING_OUTPUT", "COMPLETED"):
        p.advance(st, st.lower())
    snap = gp.snapshot(jid)
    assert snap["current_state"] == "COMPLETED" and snap["terminal"]
    assert [e["state"] for e in snap["events"]][0] == "CREATED"


def test_progress_rejects_illegal_jump_and_reused_id():
    jid = str(uuid.uuid4())
    p = gp.GenerationProgress(jid, "videogen")
    with pytest.raises(ValueError):
        p.advance("RUNNING", "skipped validation")
    with pytest.raises(gp.JobIdConflict):
        gp.GenerationProgress(jid, "videogen")


def test_progress_failure_keeps_last_state_in_events():
    jid = str(uuid.uuid4())
    p = gp.GenerationProgress(jid, "by_prompt")
    p.advance("VALIDATING", "checking")
    p.fail("NO_ENGINE_CONFIGURED: test")
    snap = gp.snapshot(jid)
    assert snap["current_state"] == "FAILED"
    assert snap["error"].startswith("NO_ENGINE_CONFIGURED")
    assert [e["state"] for e in snap["events"]][-2:] == ["VALIDATING", "FAILED"]


def test_job_id_must_be_uuid():
    with pytest.raises(ValueError):
        gp.normalize_job_id("not-a-uuid")
    assert uuid.UUID(gp.normalize_job_id(None))
