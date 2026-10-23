"""
KEYSTONE Authentication & Security Primitives
Implements PBKDF2 password hashing, HMAC-SHA256 Bearer JWT tokens,
SHA-256 API key hashing, and strict tenant isolation guards.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from typing import Any, Dict, Optional, Tuple

JWT_SECRET_KEY = os.getenv("KEYSTONE_SECRET_KEY", "mock_jwt_secret")
PBKDF2_ITERATIONS = 600_000
INTERNAL_SERVICE_TOKEN = "keystone-internal-worker-secret"


# ============================================================================
# Password Hashing (PBKDF2-HMAC-SHA256, OWASP Benchmark)
# ============================================================================

def hash_password(plain_password: str) -> str:
    """Hashes a password using PBKDF2-HMAC-SHA256 with 600,000 iterations."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain password against the stored PBKDF2 hash."""
    if not hashed_password or not hashed_password.startswith("pbkdf2_sha256$"):
        return False
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4:
            return False
        _, iterations_str, salt_hex, key_hex = parts
        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        key = bytes.fromhex(key_hex)
        computed_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return secrets.compare_digest(key, computed_key)
    except Exception:
        return False


# ============================================================================
# JWT Stateless Bearer Tokens (HMAC-SHA256)
# ============================================================================

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def generate_token(
    user_id: str,
    role: str = "user",
    expiry_seconds: int = 3600,
    secret: Optional[str] = None
) -> str:
    """Generates a base64url HMAC-SHA256 signed JWT token."""
    key = secret or JWT_SECRET_KEY
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + expiry_seconds
    }
    b64_payload = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(key.encode("utf-8"), b64_payload.encode("utf-8"), hashlib.sha256).digest()
    b64_sig = _b64url_encode(signature)
    return f"{b64_payload}.{b64_sig}"


def verify_token(token: str, secret: Optional[str] = None) -> Dict[str, Any]:
    """Verifies and decodes a JWT token."""
    if not token or "." not in token:
        raise ValueError("MALFORMED_TOKEN")

    key = secret or JWT_SECRET_KEY
    parts = token.split(".")
    if len(parts) != 2:
        raise ValueError("MALFORMED_TOKEN")

    b64_payload, b64_sig = parts
    expected_sig = _b64url_encode(
        hmac.new(key.encode("utf-8"), b64_payload.encode("utf-8"), hashlib.sha256).digest()
    )

    if not secrets.compare_digest(b64_sig, expected_sig):
        raise ValueError("INVALID_SIGNATURE")

    try:
        payload = json.loads(_b64url_decode(b64_payload).decode("utf-8"))
    except Exception:
        raise ValueError("MALFORMED_TOKEN")

    exp = payload.get("exp")
    if exp is None or int(time.time()) > int(exp):
        raise ValueError("TOKEN_EXPIRED")

    return payload


# ============================================================================
# API Key Management (SHA-256 Hashing)
# ============================================================================

def hash_api_key(raw_key: str) -> str:
    """Computes SHA-256 hash of raw API key. Raw keys are never stored."""
    if not raw_key or not isinstance(raw_key, str) or not raw_key.strip():
        raise ValueError("INVALID_KEY")
    return hashlib.sha256(raw_key.strip().encode("utf-8")).hexdigest()


def generate_api_key_pair() -> Tuple[str, str, str]:
    """
    Generates a new API key pair.
    Returns: (raw_key, key_prefix, key_hash)
    """
    prefix = secrets.token_hex(4)
    secret_part = secrets.token_hex(20)
    raw_key = f"ks_live_{prefix}_{secret_part}"
    key_hash = hash_api_key(raw_key)
    return raw_key, prefix, key_hash


# ============================================================================
# Tenant Isolation Guards
# ============================================================================

def enforce_tenant_isolation(request_user_id: str, resource_owner_id: str) -> bool:
    """Enforces strict cross-tenant boundary."""
    if str(request_user_id) != str(resource_owner_id):
        raise ValueError("TENANT_ACCESS_DENIED: Cross-tenant access is strictly prohibited")
    return True


def verify_service_token(token: Optional[str]) -> bool:
    """Verifies internal service token for /internal/* endpoints."""
    if not token:
        return False
    return secrets.compare_digest(token, INTERNAL_SERVICE_TOKEN)
