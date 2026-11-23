"""PR2 (ADR-005): ExecutionEnvelope v2, env-held secrets, and nonce replay cache tests."""

import pytest

from apps.api.src.auth.security import verify_service_token
from packages.contracts.src.models import AuthorityDecision
from services.harness.src.envelope import EnvelopeEngine


def _make_decision(
    decision_id: str = "dec_test_1",
    content_mode: str = "sfw",
    age_verified: bool = False,
    floor_verdict: str = "pass",
) -> AuthorityDecision:
    return AuthorityDecision(
        decision_id=decision_id,
        request_id="req_test_1",
        decision="ALLOW",
        capability_id="image.generation",
        provider_id="keystone_internal",
        content_mode=content_mode,
        age_verified=age_verified,
        floor_verdict=floor_verdict,
    )


def test_missing_envelope_secret_fails_closed(monkeypatch):
    """Unsetting KEYSTONE_ENVELOPE_SECRET must fail closed on both sign and verify."""
    monkeypatch.setenv("KEYSTONE_ENVELOPE_SECRET", "temp-secret-for-signing")
    decision = _make_decision()
    env = EnvelopeEngine.create_envelope(
        decision=decision,
        job_id="job_1",
        user_id="usr_1",
    )

    monkeypatch.delenv("KEYSTONE_ENVELOPE_SECRET", raising=False)
    with pytest.raises(RuntimeError, match="KEYSTONE_ENVELOPE_SECRET_MISSING"):
        EnvelopeEngine.create_envelope(
            decision=decision,
            job_id="job_1",
            user_id="usr_1",
        )

    with pytest.raises(RuntimeError, match="KEYSTONE_ENVELOPE_SECRET_MISSING"):
        EnvelopeEngine.verify_envelope(env)


def test_envelope_v2_sign_and_verify_roundtrip(monkeypatch):
    """Valid SFW and age-verified UNRESTRICTED envelopes sign and verify cleanly."""
    monkeypatch.setenv("KEYSTONE_ENVELOPE_SECRET", "test-envelope-secret-v2")

    sfw_env = EnvelopeEngine.create_envelope(
        decision=_make_decision(content_mode="sfw", age_verified=False, floor_verdict="pass"),
        job_id="job_sfw",
        user_id="usr_sfw",
    )
    assert sfw_env.content_mode == "sfw"
    assert sfw_env.age_verified is False
    assert EnvelopeEngine.verify_envelope(sfw_env, expected_mode="sfw")["valid"] is True

    unrestricted_env = EnvelopeEngine.create_envelope(
        decision=_make_decision(content_mode="unrestricted", age_verified=True, floor_verdict="pass"),
        job_id="job_adult",
        user_id="usr_adult",
    )
    assert unrestricted_env.content_mode == "unrestricted"
    assert unrestricted_env.age_verified is True
    assert EnvelopeEngine.verify_envelope(unrestricted_env, expected_mode="unrestricted")["valid"] is True


def test_unverified_unrestricted_or_failed_floor_cannot_sign(monkeypatch):
    """Unverified unrestricted requests and failed floor verdicts must not be signed."""
    monkeypatch.setenv("KEYSTONE_ENVELOPE_SECRET", "test-envelope-secret-v2")

    with pytest.raises(ValueError):
        EnvelopeEngine.create_envelope(
            decision=_make_decision(content_mode="unrestricted", age_verified=False, floor_verdict="pass"),
            job_id="job_minor",
            user_id="usr_minor",
        )

    with pytest.raises(ValueError):
        EnvelopeEngine.create_envelope(
            decision=_make_decision(content_mode="sfw", age_verified=False, floor_verdict="fail"),
            job_id="job_fail",
            user_id="usr_fail",
        )


def test_tampered_content_mode_rejected(monkeypatch):
    """Mutating content_mode after signing must fail HMAC verification."""
    monkeypatch.setenv("KEYSTONE_ENVELOPE_SECRET", "test-envelope-secret-v2")

    env = EnvelopeEngine.create_envelope(
        decision=_make_decision(content_mode="sfw", age_verified=False, floor_verdict="pass"),
        job_id="job_tamper",
        user_id="usr_tamper",
    )
    env.content_mode = "unrestricted"

    with pytest.raises(ValueError, match="INVALID_SIGNATURE"):
        EnvelopeEngine.verify_envelope(env)


def test_sfw_envelope_on_unrestricted_path_rejected(monkeypatch):
    """Presenting a valid SFW envelope to an unrestricted path must be rejected."""
    monkeypatch.setenv("KEYSTONE_ENVELOPE_SECRET", "test-envelope-secret-v2")

    env = EnvelopeEngine.create_envelope(
        decision=_make_decision(content_mode="sfw", age_verified=False, floor_verdict="pass"),
        job_id="job_sfw_only",
        user_id="usr_sfw_only",
    )

    with pytest.raises(ValueError, match="ENVELOPE_MODE_MISMATCH"):
        EnvelopeEngine.verify_envelope(env, expected_mode="unrestricted")


def test_replay_and_expiry_rejected(monkeypatch):
    """Verifying the same nonce twice raises REPLAY_ATTACK_DETECTED; expired raises ENVELOPE_EXPIRED."""
    monkeypatch.setenv("KEYSTONE_ENVELOPE_SECRET", "test-envelope-secret-v2")

    env = EnvelopeEngine.create_envelope(
        decision=_make_decision(content_mode="sfw", age_verified=False, floor_verdict="pass"),
        job_id="job_replay",
        user_id="usr_replay",
    )
    assert EnvelopeEngine.verify_envelope(env)["valid"] is True

    with pytest.raises(ValueError, match="REPLAY_ATTACK_DETECTED"):
        EnvelopeEngine.verify_envelope(env)

    expired_env = EnvelopeEngine.create_envelope(
        decision=_make_decision(content_mode="sfw", age_verified=False, floor_verdict="pass"),
        job_id="job_expired",
        user_id="usr_expired",
        ttl_seconds=-120,
    )
    with pytest.raises(ValueError, match="ENVELOPE_EXPIRED"):
        EnvelopeEngine.verify_envelope(expired_env)


def test_service_token_env_only(monkeypatch):
    """Service token verification must read KEYSTONE_INTERNAL_SERVICE_TOKEN dynamically."""
    monkeypatch.delenv("KEYSTONE_INTERNAL_SERVICE_TOKEN", raising=False)
    assert verify_service_token("keystone-internal-worker-secret") is False

    monkeypatch.setenv("KEYSTONE_INTERNAL_SERVICE_TOKEN", "dynamic-ci-token")
    assert verify_service_token("dynamic-ci-token") is True
    assert verify_service_token("keystone-internal-worker-secret") is False
