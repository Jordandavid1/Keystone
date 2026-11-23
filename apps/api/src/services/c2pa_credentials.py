"""apps/api/src/services/c2pa_credentials.py
ADR-005 / Bible v2 §43 C2PA Content Credentials Signing & Verification Service.
Signs C2PA assertions with a dedicated env-held signing key distinct from KEYSTONE_ENVELOPE_SECRET.
Zero hardcoded production signing keys.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

KEYSTONE_C2PA_SIGNING_KEY_ENV = "KEYSTONE_C2PA_SIGNING_KEY"
_EPHEMERAL_DEV_C2PA_KEY: Optional[str] = None


def get_c2pa_signing_key() -> str:
    global _EPHEMERAL_DEV_C2PA_KEY
    key = os.getenv(KEYSTONE_C2PA_SIGNING_KEY_ENV, "").strip()
    if not key:
        env_name = os.getenv("KEYSTONE_ENV", "development").strip().lower()
        if env_name == "production":
            raise RuntimeError(
                "KEYSTONE_C2PA_SIGNING_KEY_MISSING: Must configure KEYSTONE_C2PA_SIGNING_KEY in production."
            )
        if _EPHEMERAL_DEV_C2PA_KEY is None:
            _EPHEMERAL_DEV_C2PA_KEY = secrets.token_hex(32)
        key = _EPHEMERAL_DEV_C2PA_KEY

    # Verify invariant: dedicated signing key must be distinct from KEYSTONE_ENVELOPE_SECRET
    env_secret = os.getenv("KEYSTONE_ENVELOPE_SECRET", "").strip()
    if env_secret and key == env_secret:
        raise ValueError(
            "C2PA_KEY_COLLISION: KEYSTONE_C2PA_SIGNING_KEY must not equal KEYSTONE_ENVELOPE_SECRET"
        )
    return key


def sign_c2pa_manifest(
    *,
    asset_id: str,
    job_id: str,
    user_id: str,
    asset_bytes: Optional[bytes] = None,
    asset_sha256: Optional[str] = None,
    fabric: str = "comfyui",
    recipe_id: Optional[str] = None,
    content_mode: str = "sfw",
    claim_generator: str = "KEYSTONE Production Suite v2",
    title: Optional[str] = None,
    fabric_versions: Optional[Dict[str, Any]] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate and sign a C2PA Content Credentials manifest structure."""
    signing_key = get_c2pa_signing_key()
    manifest_id = f"urn:c2pa:{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat()
    resolved_sha256 = asset_sha256 or (
        hashlib.sha256(asset_bytes).hexdigest() if asset_bytes is not None else None
    )
    resolved_mode = (content_mode or "sfw").lower().strip()

    assertions = [
        {
            "label": "c2pa.actions",
            "data": {
                "actions": actions
                or [
                    {
                        "action": "c2pa.created",
                        "softwareAgent": claim_generator,
                        "when": timestamp,
                    }
                ]
            },
        },
        {
            "label": "keystone.provenance",
            "data": {
                "platform": "KEYSTONE",
                "asset_id": asset_id,
                "job_id": job_id,
                "user_id": user_id,
                "fabric": fabric,
                "recipe_id": recipe_id,
                "content_mode": resolved_mode,
                "asset_sha256": resolved_sha256,
                "fabric_versions": fabric_versions or {},
            },
        },
    ]

    claim_payload = {
        "manifest_id": manifest_id,
        "platform": "KEYSTONE",
        "asset_id": asset_id,
        "claim_generator": claim_generator,
        "title": title or f"Asset {asset_id}",
        "timestamp": timestamp,
        "fabric": fabric,
        "recipe_id": recipe_id,
        "content_mode": resolved_mode,
        "asset_sha256": resolved_sha256,
        "assertions": assertions,
    }

    serialized = json.dumps(claim_payload, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(
        signing_key.encode("utf-8"),
        serialized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return {
        "c2pa_version": "2.0.0",
        "platform": "KEYSTONE",
        "manifest_id": manifest_id,
        "timestamp": timestamp,
        "fabric": fabric,
        "recipe_id": recipe_id,
        "content_mode": resolved_mode,
        "asset_sha256": resolved_sha256,
        "signature_algorithm": "HMAC-SHA256",
        "signature": signature,
        "claim": claim_payload,
    }


def verify_c2pa_manifest(
    manifest: Dict[str, Any],
    *,
    asset_bytes: Optional[bytes] = None,
) -> bool:
    """Verify HMAC-SHA256 signature (and optional payload hash) of a C2PA manifest."""
    if not isinstance(manifest, dict):
        return False
    claim = manifest.get("claim")
    signature = manifest.get("signature")
    if not isinstance(claim, dict) or not isinstance(signature, str) or not signature:
        return False

    signing_key = get_c2pa_signing_key()
    serialized = json.dumps(claim, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(
        signing_key.encode("utf-8"),
        serialized.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        return False

    if asset_bytes is not None:
        expected_sha = manifest.get("asset_sha256") or claim.get("asset_sha256")
        if not expected_sha:
            return False
        actual_sha = hashlib.sha256(asset_bytes).hexdigest()
        if not hmac.compare_digest(actual_sha, str(expected_sha)):
            return False

    return True
