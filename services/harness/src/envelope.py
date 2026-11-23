"""
KEYSTONE Signed Execution Envelope Engine (Bible §12, §14).
Provides HMAC-SHA256 signature generation and verification, canonical JSON serialization,
single-use nonce cache for replay prevention, and clock skew tolerance.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from packages.contracts.src.models import AuthorityDecision, ExecutionEnvelope

ENVELOPE_TTL_SECONDS = 300
CLOCK_SKEW_TOLERANCE_SECONDS = 30


def get_envelope_secret(override: Optional[str] = None) -> str:
    """Resolve envelope signing secret from override or KEYSTONE_ENVELOPE_SECRET."""
    secret = override if override is not None else os.getenv("KEYSTONE_ENVELOPE_SECRET")
    if not secret:
        raise RuntimeError(
            "KEYSTONE_ENVELOPE_SECRET_MISSING: Must set KEYSTONE_ENVELOPE_SECRET in environment"
        )
    return secret


class RedisBackedNonceCache:
    """
    Redis-backed TTL cache for single-use cryptographic nonces with thread-safe
    in-memory fallback when REDIS_URL is unset or redis is unavailable.
    """

    def __init__(self, key_prefix: str = "keystone:nonce:"):
        self._key_prefix = key_prefix
        self._lock = threading.Lock()
        self._nonces: Dict[str, float] = {}
        self._redis_client: Any = None
        self._redis_url: Optional[str] = None

    def _get_redis(self) -> Any:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return None
        if self._redis_client is not None and self._redis_url == redis_url:
            return self._redis_client
        try:
            import redis  # type: ignore

            self._redis_client = redis.from_url(redis_url)
            self._redis_url = redis_url
            return self._redis_client
        except ImportError:
            return None

    def has(self, nonce: str) -> bool:
        client = self._get_redis()
        if client is not None:
            return bool(client.exists(f"{self._key_prefix}{nonce}"))
        with self._lock:
            self._cleanup_locked()
            return nonce in self._nonces

    def add(self, nonce: str, ttl: int = ENVELOPE_TTL_SECONDS) -> None:
        client = self._get_redis()
        if client is not None:
            client.set(f"{self._key_prefix}{nonce}", "1", ex=max(1, int(ttl)))
            return
        with self._lock:
            self._cleanup_locked()
            self._nonces[nonce] = time.time() + ttl

    def consume(self, nonce: str, ttl: int = ENVELOPE_TTL_SECONDS) -> bool:
        """Atomically consume a nonce; returns True if newly consumed, False on replay."""
        client = self._get_redis()
        if client is not None:
            return bool(client.set(f"{self._key_prefix}{nonce}", "1", nx=True, ex=max(1, int(ttl))))
        with self._lock:
            self._cleanup_locked()
            if nonce in self._nonces:
                return False
            self._nonces[nonce] = time.time() + ttl
            return True

    def _cleanup_locked(self) -> None:
        now = time.time()
        expired = [k for k, exp in self._nonces.items() if exp < now]
        for k in expired:
            del self._nonces[k]

    def cleanup(self) -> None:
        with self._lock:
            self._cleanup_locked()

    def clear(self) -> None:
        client = self._get_redis()
        if client is not None:
            keys = client.keys(f"{self._key_prefix}*")
            if keys:
                client.delete(*keys)
        with self._lock:
            self._nonces.clear()


NonceReplayCache = RedisBackedNonceCache

# Global nonce cache instance
nonce_cache = RedisBackedNonceCache()


def _normalize_timestamp(ts: Union[datetime, int, float, str]) -> int:
    """Normalizes any datetime or timestamp representation to integer seconds since epoch."""
    if isinstance(ts, (int, float)):
        return int(ts)
    if isinstance(ts, datetime):
        return int(ts.timestamp())
    if isinstance(ts, str):
        try:
            return int(float(ts))
        except ValueError:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return int(dt.timestamp())
    return int(time.time())


def canonical_serialize(payload_dict: Dict[str, Any]) -> bytes:
    """
    Generates deterministic canonical JSON bytes for HMAC signing.
    Excludes signature and sorts all keys.
    """
    clean_dict: Dict[str, Any] = {}
    for k, v in payload_dict.items():
        if k == "signature":
            continue
        if isinstance(v, datetime):
            clean_dict[k] = int(v.timestamp())
        elif isinstance(v, (int, float, str, bool, type(None))):
            clean_dict[k] = v
        elif isinstance(v, (dict, list)):
            clean_dict[k] = v
        else:
            clean_dict[k] = str(v)

    return json.dumps(clean_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")


def generate_signature(payload_dict: Dict[str, Any], secret: Optional[str] = None) -> str:
    """Generates HMAC-SHA256 signature for canonical envelope payload."""
    sec = get_envelope_secret(secret)
    canonical_bytes = canonical_serialize(payload_dict)
    return hmac.new(sec.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()


def verify_signature(envelope_dict: Dict[str, Any], secret: Optional[str] = None) -> bool:
    """Verifies HMAC-SHA256 signature against canonical payload."""
    sig = envelope_dict.get("signature")
    if not sig:
        return False
    expected = generate_signature(envelope_dict, secret=secret)
    return hmac.compare_digest(str(sig), expected)


class EnvelopeEngine:
    """
    Issues and verifies cryptographically signed ExecutionEnvelopes.
    """

    @classmethod
    def create_envelope(
        cls,
        decision: AuthorityDecision,
        job_id: str,
        user_id: str,
        workflow_id: str = "wf_default",
        workflow_version: str = "1.0.0",
        compiled_prompt_id: str = "cp_default",
        arguments: Optional[Dict[str, Any]] = None,
        input_asset_ids: Optional[List[str]] = None,
        secret: Optional[str] = None,
        ttl_seconds: int = ENVELOPE_TTL_SECONDS,
        intent: str = "generate",
        playbook: Optional[str] = None,
        content_mode: Optional[str] = None,
        age_verified: Optional[bool] = None,
        floor_verdict: Optional[str] = None,
    ) -> ExecutionEnvelope:
        """
        Signs and issues a new ExecutionEnvelope v2 for an approved decision.
        """
        resolved_content_mode = (
            content_mode if content_mode is not None else getattr(decision, "content_mode", "sfw")
        )
        resolved_age_verified = (
            age_verified if age_verified is not None else getattr(decision, "age_verified", False)
        )
        resolved_floor_verdict = (
            floor_verdict if floor_verdict is not None else getattr(decision, "floor_verdict", "pass")
        )

        if resolved_floor_verdict != "pass":
            raise ValueError(
                f"ENVELOPE_FLOOR_REJECTED: Cannot issue envelope with floor_verdict={resolved_floor_verdict}"
            )
        if resolved_content_mode == "unrestricted" and not resolved_age_verified:
            raise ValueError(
                "ENVELOPE_AGE_VERIFICATION_REQUIRED: Cannot issue unrestricted envelope without age_verified=True"
            )

        now = int(time.time())
        expires = now + ttl_seconds
        envelope_id = f"env_{uuid.uuid4().hex[:12]}"
        nonce = uuid.uuid4().hex

        args = arguments if arguments is not None else decision.sanitized_arguments
        asset_ids = input_asset_ids or []

        payload_to_sign = {
            "envelope_version": "2.0",
            "envelope_id": envelope_id,
            "decision_id": decision.decision_id,
            "job_id": job_id,
            "user_id": user_id,
            "capability_id": decision.capability_id or "image.generation",
            "provider_id": decision.provider_id or "keystone_internal",
            "workflow_id": workflow_id,
            "workflow_version": workflow_version,
            "compiled_prompt_id": compiled_prompt_id,
            "intent": intent,
            "playbook": playbook,
            "content_mode": resolved_content_mode,
            "age_verified": resolved_age_verified,
            "floor_verdict": resolved_floor_verdict,
            "arguments": args,
            "input_asset_ids": asset_ids,
            "issued_at": now,
            "expires_at": expires,
            "nonce": nonce,
        }

        signature = generate_signature(payload_to_sign, secret=secret)

        return ExecutionEnvelope(
            envelope_version="2.0",
            envelope_id=envelope_id,
            decision_id=decision.decision_id,
            job_id=job_id,
            user_id=user_id,
            capability_id=decision.capability_id or "image.generation",
            provider_id=decision.provider_id or "keystone_internal",
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            compiled_prompt_id=compiled_prompt_id,
            intent=intent,
            playbook=playbook,
            content_mode=resolved_content_mode,
            age_verified=resolved_age_verified,
            floor_verdict=resolved_floor_verdict,
            arguments=args,
            input_asset_ids=asset_ids,
            issued_at=now,
            expires_at=expires,
            nonce=nonce,
            signature=signature,
        )

    @classmethod
    def verify_envelope(
        cls,
        envelope: Union[ExecutionEnvelope, Dict[str, Any]],
        secret: Optional[str] = None,
        now_timestamp: Optional[Union[int, float]] = None,
        check_nonce: bool = True,
        expected_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verifies signature, expiration, clock skew, v2 policy fields, and single-use nonce.
        Raises ValueError if envelope is invalid or compromised.
        """
        data = envelope.model_dump() if isinstance(envelope, ExecutionEnvelope) else dict(envelope)

        # 1. Nonce Replay Check
        nonce = str(data.get("nonce", "")).strip()
        if not nonce:
            raise ValueError("INVALID_ENVELOPE: Missing nonce")

        if check_nonce and nonce_cache.has(nonce):
            raise ValueError(f"REPLAY_ATTACK_DETECTED: Nonce {nonce} has already been consumed")

        # 2. Expiration & Clock Skew Tolerance Check
        now = int(now_timestamp if now_timestamp is not None else time.time())
        issued_at = _normalize_timestamp(data.get("issued_at", now))
        expires_at = _normalize_timestamp(data.get("expires_at", now + ENVELOPE_TTL_SECONDS))

        if now > (expires_at + CLOCK_SKEW_TOLERANCE_SECONDS):
            raise ValueError(f"ENVELOPE_EXPIRED: Envelope expired at {expires_at}, current time is {now}")

        if now < (issued_at - CLOCK_SKEW_TOLERANCE_SECONDS):
            raise ValueError(f"ENVELOPE_FUTURE_ISSUED: Envelope issued in future at {issued_at}, current time is {now}")

        # 3. Cryptographic Signature Verification
        if not verify_signature(data, secret=secret):
            raise ValueError("INVALID_SIGNATURE: HMAC-SHA256 signature mismatch or envelope payload tampered")

        # 4. v2 Envelope Policy & Mode Verification
        if data.get("envelope_version") != "2.0":
            raise ValueError(f"INVALID_ENVELOPE_VERSION: Expected 2.0, got {data.get('envelope_version')}")

        if data.get("floor_verdict") != "pass":
            raise ValueError(f"ENVELOPE_FLOOR_REJECTED: floor_verdict={data.get('floor_verdict')}")

        content_mode = data.get("content_mode", "sfw")
        if content_mode == "unrestricted" and data.get("age_verified") is not True:
            raise ValueError("ENVELOPE_AGE_VERIFICATION_REQUIRED: unrestricted mode requires age_verified=True")

        if expected_mode is not None and content_mode != expected_mode:
            raise ValueError(
                f"ENVELOPE_MODE_MISMATCH: Expected content_mode={expected_mode}, got {content_mode}"
            )

        # 5. Consume Nonce Atomically
        if check_nonce:
            ttl = max(1, expires_at - now + CLOCK_SKEW_TOLERANCE_SECONDS)
            if not nonce_cache.consume(nonce, ttl=ttl):
                raise ValueError(f"REPLAY_ATTACK_DETECTED: Nonce {nonce} has already been consumed")

        return {
            "valid": True,
            "envelope_id": data.get("envelope_id"),
            "job_id": data.get("job_id"),
            "capability_id": data.get("capability_id"),
            "content_mode": content_mode,
            "nonce": nonce,
        }
