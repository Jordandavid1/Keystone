"""apps/api/src/services/c2pa_credentials.py
ADR-005 / Bible v2 §25 C2PA Content Credentials Signing Service.
Signs C2PA assertions with a dedicated signing key distinct from KEYSTONE_ENVELOPE_SECRET.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

KEYSTONE_C2PA_SIGNING_KEY_ENV = "KEYSTONE_C2PA_SIGNING_KEY"
DEFAULT_C2PA_KEY = "keystone-c2pa-root-manifest-signing-key-v1"


def get_c2pa_signing_key() -> str:
    key = os.getenv(KEYSTONE_C2PA_SIGNING_KEY_ENV, "").strip()
    if not key:
        return DEFAULT_C2PA_KEY
    # Verify invariant: distinct from KEYSTONE_ENVELOPE_SECRET
    env_secret = os.getenv("KEYSTONE_ENVELOPE_SECRET", "").strip()
    if env_secret and key == env_secret:
        raise ValueError("C2PA_KEY_COLLISION: KEYSTONE_C2PA_SIGNING_KEY must not equal KEYSTONE_ENVELOPE_SECRET")
    return key


def sign_c2pa_manifest(
    *,
    asset_id: str,
    job_id: str,
    user_id: str,
    claim_generator: str = "KEYSTONE Production Suite v2",
    title: Optional[str] = None,
    fabric_versions: Optional[Dict[str, Any]] = None,
    actions: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Generate and sign a standard C2PA Content Credentials manifest structure."""
    signing_key = get_c2pa_signing_key()
    manifest_id = f"urn:c2pa:{uuid.uuid4()}"
    timestamp = datetime.now(timezone.utc).isoformat()

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
                "asset_id": asset_id,
                "job_id": job_id,
                "user_id": user_id,
                "fabric_versions": fabric_versions or {},
            },
        },
    ]

    claim_payload = {
        "manifest_id": manifest_id,
        "asset_id": asset_id,
        "claim_generator": claim_generator,
        "title": title or f"Asset {asset_id}",
        "timestamp": timestamp,
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
        "manifest_id": manifest_id,
        "signature_algorithm": "HMAC-SHA256",
        "signature": signature,
        "claim": claim_payload,
    }
