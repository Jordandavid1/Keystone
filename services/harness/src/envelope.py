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
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from packages.contracts.src.models import AuthorityDecision, ExecutionEnvelope

DEFAULT_ENVELOPE_SECRET = os.getenv("KEYSTONE_ENVELOPE_SECRET", "keystone_master_secret_2026_authority_key")
ENVELOPE_TTL_SECONDS = 300
CLOCK_SKEW_TOLERANCE_SECONDS = 30


class NonceReplayCache:
    """
    In-memory TTL cache for single-use cryptographic nonces.
    Prevents envelope replay attacks.
    """

    def __init__(self):
        self._nonces: Dict[str, float] = {}

    def has(self, nonce: str) -> bool:
        self.cleanup()
        return nonce in self._nonces

    def add(self, nonce: str, ttl: int = ENVELOPE_TTL_SECONDS) -> None:
        self.cleanup()
        self._nonces[nonce] = time.time() + ttl

    def cleanup(self) -> None:
        now = time.time()
        expired = [k for k, exp in self._nonces.items() if exp < now]
        for k in expired:
            del self._nonces[k]

    def clear(self) -> None:
        self._nonces.clear()


# Global nonce cache instance
nonce_cache = NonceReplayCache()


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
    sec = secret or DEFAULT_ENVELOPE_SECRET
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
        ttl_seconds: int = ENVELOPE_TTL_SECONDS
    ) -> ExecutionEnvelope:
        """
        Signs and issues a new ExecutionEnvelope for an approved decision.
        """
        now = int(time.time())
        expires = now + ttl_seconds
        envelope_id = f"env_{uuid.uuid4().hex[:12]}"
        nonce = uuid.uuid4().hex

        args = arguments if arguments is not None else decision.sanitized_arguments
        asset_ids = input_asset_ids or []

        payload_to_sign = {
            "envelope_id": envelope_id,
            "decision_id": decision.decision_id,
            "job_id": job_id,
            "user_id": user_id,
            "capability_id": decision.capability_id or "image.generation",
            "provider_id": decision.provider_id or "keystone_internal",
            "workflow_id": workflow_id,
            "workflow_version": workflow_version,
            "compiled_prompt_id": compiled_prompt_id,
            "arguments": args,
            "input_asset_ids": asset_ids,
            "issued_at": now,
            "expires_at": expires,
            "nonce": nonce
        }

        signature = generate_signature(payload_to_sign, secret=secret)

        return ExecutionEnvelope(
            envelope_id=envelope_id,
            decision_id=decision.decision_id,
            job_id=job_id,
            user_id=user_id,
            capability_id=decision.capability_id or "image.generation",
            provider_id=decision.provider_id or "keystone_internal",
            workflow_id=workflow_id,
            workflow_version=workflow_version,
            compiled_prompt_id=compiled_prompt_id,
            arguments=args,
            input_asset_ids=asset_ids,
            issued_at=now,
            expires_at=expires,
            nonce=nonce,
            signature=signature
        )

    @classmethod
    def verify_envelope(
        cls,
        envelope: Union[ExecutionEnvelope, Dict[str, Any]],
        secret: Optional[str] = None,
        now_timestamp: Optional[Union[int, float]] = None,
        check_nonce: bool = True
    ) -> Dict[str, Any]:
        """
        Verifies signature, expiration, clock skew, and single-use nonce.
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

        # 4. Consume Nonce
        if check_nonce:
            ttl = max(1, expires_at - now + CLOCK_SKEW_TOLERANCE_SECONDS)
            nonce_cache.add(nonce, ttl=ttl)

        return {
            "valid": True,
            "envelope_id": data.get("envelope_id"),
            "job_id": data.get("job_id"),
            "capability_id": data.get("capability_id"),
            "nonce": nonce
        }
