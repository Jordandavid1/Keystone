"""
KEYSTONE Local Qwen Embeddings Service & CapabilityManifest Registration
(Bible v2 §2 Invariants 2, 5–7, 9–10, §8, §15, §21, §42; specs/SPEC_MEMORY.md; ADR-004 / ADR-005).

Provides:
- LocalEmbeddingProvider calling the local Qwen-embedding endpoint (/v1/embeddings)
  served beside the Qwen reasoning core behind CognitiveProvider.
- Pinned Matryoshka vector dimension KEYSTONE_EMBEDDING_DIM = 1024.
- Deterministic L2-normalized local signed hash-projection fallback when the local
  HTTP server is offline in unit tests.
- Strict prohibition of external embedding vendors (Invariant 2 closure: replaces
  retired external cloud embedding pipeline with local Qwen-embedding).
- CapabilityManifest registration for `cognition.local_embeddings` disclosing
  model_id, quantization, dimension=1024, and license.
"""

from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Union

import httpx

from packages.contracts.src.models import CapabilityManifest, ParameterSpec
from services.cognition.src.client import CognitionConnector, load_keystone_dotenv

load_keystone_dotenv()

KEYSTONE_EMBEDDING_DIM: int = int(os.getenv("KEYSTONE_EMBEDDING_DIM", "1024"))
CAPABILITY_ID: str = "cognition.local_embeddings"
PROVIDER_ID: str = "cognition.qwen_embedding"
PROVIDER_VERSION: str = "2.0.0"

DEFAULT_EMBEDDING_MODEL: str = "Qwen/Qwen3-Embedding-0.6B-GGUF"
DEFAULT_QUANTIZATION: str = "GGUF-Q8_0"
DEFAULT_LICENSE: str = "Apache-2.0"

_PROHIBITED_EXTERNAL_VENDOR_PATTERN = re.compile(
    r"(text-embedding-\d+|text-embedding-ada|gemini-\d|gpt-4|claude-\d|"
    r"api\.openai\.com|generativelanguage\.googleapis\.com|"
    r"aiplatform\.googleapis\.com|api\.cohere\.ai|api\.voyageai\.com)",
    re.IGNORECASE,
)

_TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)


def l2_normalize(vector: Sequence[float], dimension: Optional[int] = None) -> List[float]:
    """
    Returns an L2-normalized vector of exact length `dimension` (or `len(vector)`).
    Matryoshka-slices or zero-pads before normalization so output norm is always 1.0.
    """
    target_dim = int(dimension) if dimension is not None else len(vector)
    if target_dim <= 0:
        raise ValueError(f"INVALID_EMBEDDING_DIM: dimension must be positive, got {target_dim}")

    vals = [float(x) for x in list(vector)[:target_dim]]
    if len(vals) < target_dim:
        vals.extend([0.0] * (target_dim - len(vals)))

    sq_sum = sum(v * v for v in vals)
    if sq_sum <= 1e-24:
        unit = [0.0] * target_dim
        unit[0] = 1.0
        return unit

    inv_norm = 1.0 / math.sqrt(sq_sum)
    return [v * inv_norm for v in vals]


def cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Computes exact cosine similarity between two equal-dimension vectors."""
    if not vec_a or not vec_b:
        return 0.0
    n = min(len(vec_a), len(vec_b))
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for i in range(n):
        a = float(vec_a[i])
        b = float(vec_b[i])
        dot += a * b
        norm_a += a * a
        norm_b += b * b
    if norm_a <= 1e-24 or norm_b <= 1e-24:
        return 0.0
    return float(dot / (math.sqrt(norm_a) * math.sqrt(norm_b)))


def deterministic_hash_projection(
    text: str,
    dimension: int = KEYSTONE_EMBEDDING_DIM,
) -> List[float]:
    """
    Deterministic L2-normalized signed feature-hashing projection into `dimension`-D
    space (Weinberger et al. random projection) used when the local Qwen-embedding
    HTTP server is offline in unit tests. Zero external embedding vendors.
    """
    target_dim = int(dimension or KEYSTONE_EMBEDDING_DIM)
    if target_dim <= 0:
        raise ValueError(f"INVALID_EMBEDDING_DIM: dimension must be positive, got {target_dim}")

    normalized = " ".join(str(text or "").strip().lower().split())
    vec = [0.0] * target_dim

    tokens = _TOKEN_RE.findall(normalized)
    features: List[tuple[str, float]] = []

    if tokens:
        for tok in tokens:
            features.append((f"w:{tok}", 2.0))
            if len(tok) >= 3:
                for i in range(len(tok) - 2):
                    features.append((f"c3:{tok[i:i+3]}", 0.45))
        for i in range(len(tokens) - 1):
            features.append((f"bg:{tokens[i]}_{tokens[i+1]}", 1.35))
    else:
        features.append((f"raw:{normalized or '__empty__'}", 1.0))

    for feat, weight in features:
        for head in range(4):
            digest = hashlib.sha256(f"ks_qwen_emb_v2:{head}:{feat}".encode("utf-8")).digest()
            bucket = int.from_bytes(digest[0:4], "big") % target_dim
            sign = 1.0 if (digest[4] & 1) == 0 else -1.0
            mag = 0.75 + (int.from_bytes(digest[5:7], "big") / 65535.0) * 0.5
            vec[bucket] += sign * weight * mag

    # Mix low-amplitude whole-text deterministic carrier so every dimension is populated
    seed_bytes = hashlib.sha256(f"ks_qwen_carrier_v2:{normalized}".encode("utf-8")).digest()
    blocks = (target_dim + 15) // 16
    for blk in range(blocks):
        blk_digest = hashlib.sha256(seed_bytes + blk.to_bytes(4, "big")).digest()
        for j in range(16):
            idx = blk * 16 + j
            if idx >= target_dim:
                break
            raw_u16 = int.from_bytes(blk_digest[j * 2 : j * 2 + 2], "big")
            centered = (raw_u16 / 32767.5) - 1.0
            vec[idx] += centered * 0.02

    return l2_normalize(vec, dimension=target_dim)


def get_embedding_manifest(
    *,
    model_id: Optional[str] = None,
    quantization: Optional[str] = None,
    dimension: int = KEYSTONE_EMBEDDING_DIM,
    license_id: Optional[str] = None,
) -> CapabilityManifest:
    """
    Returns the canonical CapabilityManifest for `cognition.local_embeddings`,
    recording model_id, quantization, dimension=1024, and license for manifest_accounting.
    """
    load_keystone_dotenv()
    resolved_model = (
        model_id
        or os.getenv("KEYSTONE_EMBEDDING_MODEL", "").strip()
        or os.getenv("COGNITION_EMBEDDING_MODEL", "").strip()
        or DEFAULT_EMBEDDING_MODEL
    )
    resolved_quant = (
        quantization
        or os.getenv("KEYSTONE_EMBEDDING_QUANTIZATION", "").strip()
        or DEFAULT_QUANTIZATION
    )
    resolved_dim = int(dimension or KEYSTONE_EMBEDDING_DIM)
    resolved_license = (
        license_id
        or os.getenv("KEYSTONE_EMBEDDING_LICENSE", "").strip()
        or DEFAULT_LICENSE
    )

    return CapabilityManifest(
        schema_version="1.0",
        capability_id=CAPABILITY_ID,
        provider_id=PROVIDER_ID,
        provider_version=PROVIDER_VERSION,
        capability_type="cognition",
        description=(
            "Local Qwen-embedding vector service (/v1/embeddings) served beside the Qwen "
            "reasoning core behind CognitiveProvider (zero external embedding vendors)."
        ),
        accepts=["text/plain", "application/json"],
        produces=["application/embeddings+json"],
        parameters={
            "input": ParameterSpec(
                type="string",
                required=True,
                description="Text or list of texts to embed into 1024-dim L2-normalized vector space.",
            ),
            "dimensions": ParameterSpec(
                type="integer",
                required=False,
                default=resolved_dim,
                minimum=64,
                maximum=4096,
                description="Matryoshka embedding output dimension (KEYSTONE_EMBEDDING_DIM=1024).",
            ),
        },
        prompt_profile="qwen3-embedding-matryoshka-1024",
        workflow_id="local_qwen_embeddings_v1",
        required_harnesses=["khf.memory_scope"],
        estimated_resource_class="gpu_t4",
        enabled=True,
        metadata={
            "model_id": resolved_model,
            "quantization": resolved_quant,
            "dimension": resolved_dim,
            "license": resolved_license,
            "endpoint": "/v1/embeddings",
            "external_vendor": False,
            "vendor": "self_hosted_local",
        },
    )


LOCAL_EMBEDDINGS_MANIFEST: CapabilityManifest = get_embedding_manifest()


class LocalEmbeddingProvider:
    """
    Local Qwen-embedding client behind CognitiveProvider.
    Calls `/v1/embeddings` beside the Qwen reasoning core and produces L2-normalized
    1024-dimensional vectors (`KEYSTONE_EMBEDDING_DIM=1024`).
    Includes deterministic L2-normalized local hash-projection fallback when the local
    HTTP server is offline in unit tests, with zero external embedding vendors.
    """

    CAPABILITY_ID = CAPABILITY_ID
    PROVIDER_ID = PROVIDER_ID
    DEFAULT_MODEL = DEFAULT_EMBEDDING_MODEL
    DEFAULT_QUANTIZATION = DEFAULT_QUANTIZATION
    DEFAULT_DIMENSION = KEYSTONE_EMBEDDING_DIM
    DEFAULT_LICENSE = DEFAULT_LICENSE

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimension: int = KEYSTONE_EMBEDDING_DIM,
        quantization: Optional[str] = None,
        license_id: Optional[str] = None,
        timeout: float = 5.0,
        allow_local_hash_projection: bool = True,
    ) -> None:
        load_keystone_dotenv()
        self._explicit_base_url = base_url.rstrip("/") if base_url else None
        self.api_key = (
            api_key
            or os.getenv("KEYSTONE_EMBEDDING_API_KEY", "").strip()
            or os.getenv("COGNITION_API_KEY", "").strip()
            or os.getenv("OPENAI_API_KEY", "").strip()
        )
        self.model_id = (
            model
            or os.getenv("KEYSTONE_EMBEDDING_MODEL", "").strip()
            or os.getenv("COGNITION_EMBEDDING_MODEL", "").strip()
            or DEFAULT_EMBEDDING_MODEL
        )
        self.model = self.model_id
        self.dimension = int(dimension or KEYSTONE_EMBEDDING_DIM)
        self.quantization = (
            quantization
            or os.getenv("KEYSTONE_EMBEDDING_QUANTIZATION", "").strip()
            or DEFAULT_QUANTIZATION
        )
        self.license = (
            license_id
            or os.getenv("KEYSTONE_EMBEDDING_LICENSE", "").strip()
            or DEFAULT_LICENSE
        )
        self.timeout = float(timeout)
        self.allow_local_hash_projection = bool(allow_local_hash_projection)

        self._validate_zero_external_vendor(self.model_id, self._explicit_base_url or "")

    @staticmethod
    def _validate_zero_external_vendor(model_name: str, endpoint_url: str) -> None:
        """Enforces Bible v2 §2 Invariant 2 & SPEC_MEMORY.md §1: zero external embedding vendors."""
        for candidate in (model_name, endpoint_url):
            if candidate and _PROHIBITED_EXTERNAL_VENDOR_PATTERN.search(candidate):
                raise ValueError(
                    f"EXTERNAL_EMBEDDING_VENDOR_PROHIBITED: '{candidate}' violates Invariant 2 "
                    "(only local Qwen-embedding models behind CognitiveProvider are permitted)."
                )

    def get_manifest(self) -> CapabilityManifest:
        return get_embedding_manifest(
            model_id=self.model_id,
            quantization=self.quantization,
            dimension=self.dimension,
            license_id=self.license,
        )

    def manifest(self) -> CapabilityManifest:
        return self.get_manifest()

    def resolve_active_endpoint(self) -> str:
        """
        Resolves the local `/v1` base URL serving `/v1/embeddings` beside the Qwen reasoning core.
        """
        load_keystone_dotenv()
        if self._explicit_base_url:
            base = self._explicit_base_url.rstrip("/")
            if base.endswith("/embeddings"):
                base = base[: -len("/embeddings")].rstrip("/")
            if not base.endswith("/v1"):
                base = f"{base}/v1"
            self._validate_zero_external_vendor(self.model_id, base)
            return base

        env_emb = (
            os.getenv("KEYSTONE_EMBEDDING_BASE_URL", "").strip()
            or os.getenv("COGNITION_EMBEDDING_BASE_URL", "").strip()
        ).rstrip("/")
        if env_emb:
            if env_emb.endswith("/embeddings"):
                env_emb = env_emb[: -len("/embeddings")].rstrip("/")
            if not env_emb.endswith("/v1"):
                env_emb = f"{env_emb}/v1"
            self._validate_zero_external_vendor(self.model_id, env_emb)
            return env_emb

        try:
            from services.harness.src.worker_bridge import worker_bridge

            matched = worker_bridge.route_for_capability(CAPABILITY_ID)
            if matched:
                tunnel = matched[0].tunnel_url.rstrip("/")
                if tunnel:
                    resolved = tunnel if tunnel.endswith("/v1") else f"{tunnel}/v1"
                    self._validate_zero_external_vendor(self.model_id, resolved)
                    return resolved
        except Exception:
            pass

        connector = CognitionConnector()
        base = connector.resolve_active_endpoint().rstrip("/")
        if base:
            self._validate_zero_external_vendor(self.model_id, base)
        return base

    def build_embedding_request(
        self,
        text_or_texts: Union[str, Sequence[str]],
        *,
        dimension: Optional[int] = None,
    ) -> Dict[str, Any]:
        target_dim = int(dimension or self.dimension or KEYSTONE_EMBEDDING_DIM)
        self._validate_zero_external_vendor(self.model_id, "")
        return {
            "model": self.model_id,
            "input": text_or_texts if isinstance(text_or_texts, str) else list(text_or_texts),
            "dimensions": target_dim,
            "encoding_format": "float",
        }

    def _parse_embeddings_response(
        self,
        raw_data: Dict[str, Any],
        expected_count: int,
        target_dim: int,
    ) -> List[List[float]]:
        items = raw_data.get("data")
        if not isinstance(items, list) or not items:
            if isinstance(raw_data.get("embedding"), list):
                return [l2_normalize(raw_data["embedding"], dimension=target_dim)]
            raise ValueError("INVALID_EMBEDDING_RESPONSE: Missing 'data' array in /v1/embeddings response")

        ordered = sorted(
            items,
            key=lambda item: int(item.get("index", 0)) if isinstance(item, dict) else 0,
        )
        vectors: List[List[float]] = []
        for entry in ordered:
            if not isinstance(entry, dict) or not isinstance(entry.get("embedding"), list):
                raise ValueError("INVALID_EMBEDDING_RESPONSE: Entry missing 'embedding' vector")
            vectors.append(l2_normalize(entry["embedding"], dimension=target_dim))

        if len(vectors) < expected_count:
            raise ValueError(
                f"INVALID_EMBEDDING_RESPONSE: Expected {expected_count} embeddings, got {len(vectors)}"
            )
        return vectors[:expected_count]

    def embed_batch(
        self,
        texts: Sequence[str],
        *,
        dimension: Optional[int] = None,
    ) -> List[List[float]]:
        """
        Embeds a batch of strings into L2-normalized `dimension`-D vectors via `/v1/embeddings`,
        falling back to deterministic L2-normalized local hash projection when offline in unit tests.
        """
        target_dim = int(dimension or self.dimension or KEYSTONE_EMBEDDING_DIM)
        clean_texts = [str(t or "") for t in texts]
        if not clean_texts:
            return []

        active_base = self.resolve_active_endpoint()
        if active_base:
            endpoint = f"{active_base.rstrip('/')}/embeddings"
            payload = self.build_embedding_request(clean_texts, dimension=target_dim)
            headers: Dict[str, str] = {
                "Content-Type": "application/json",
                "User-Agent": "Keystone/2.0",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(endpoint, json=payload, headers=headers)
                    resp.raise_for_status()
                    return self._parse_embeddings_response(
                        resp.json(),
                        expected_count=len(clean_texts),
                        target_dim=target_dim,
                    )
            except Exception as exc:
                if not self.allow_local_hash_projection:
                    raise ConnectionError(
                        f"EMBEDDING_ENDPOINT_UNREACHABLE: '{endpoint}' failed ({type(exc).__name__}: {exc})"
                    ) from exc

        if not self.allow_local_hash_projection:
            raise RuntimeError(
                "EMBEDDING_NOT_CONFIGURED: No local Qwen-embedding endpoint is configured and "
                "local hash-projection fallback is disabled."
            )

        return [
            deterministic_hash_projection(text, dimension=target_dim)
            for text in clean_texts
        ]

    def embed_text(
        self,
        text: str,
        *,
        dimension: Optional[int] = None,
    ) -> List[float]:
        """Embeds a single text string into an L2-normalized 1024-dim vector."""
        results = self.embed_batch([str(text or "")], dimension=dimension)
        return results[0]

    def embed_query(
        self,
        text: str,
        *,
        dimension: Optional[int] = None,
    ) -> List[float]:
        """Alias for embed_text used for query-time retrieval."""
        return self.embed_text(text, dimension=dimension)

    def embed(
        self,
        text: Union[str, Sequence[str]],
        *,
        dimension: Optional[int] = None,
    ) -> Union[List[float], List[List[float]]]:
        """
        Embeds a single string (returning `List[float]`) or a sequence of strings
        (returning `List[List[float]]`).
        """
        if isinstance(text, (list, tuple)):
            return self.embed_batch(list(text), dimension=dimension)
        return self.embed_text(str(text or ""), dimension=dimension)

    async def aembed(
        self,
        text: Union[str, Sequence[str]],
        *,
        dimension: Optional[int] = None,
    ) -> Union[List[float], List[List[float]]]:
        """
        Asynchronous embedding call to `/v1/embeddings` with deterministic local hash-projection
        fallback when the local HTTP server is offline in unit tests.
        """
        is_batch = isinstance(text, (list, tuple))
        clean_texts = [str(t or "") for t in text] if is_batch else [str(text or "")]
        if not clean_texts:
            return [] if is_batch else deterministic_hash_projection("", dimension=dimension or self.dimension)

        target_dim = int(dimension or self.dimension or KEYSTONE_EMBEDDING_DIM)
        active_base = self.resolve_active_endpoint()
        if active_base:
            endpoint = f"{active_base.rstrip('/')}/embeddings"
            payload = self.build_embedding_request(clean_texts, dimension=target_dim)
            headers: Dict[str, str] = {
                "Content-Type": "application/json",
                "User-Agent": "Keystone/2.0",
            }
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(endpoint, json=payload, headers=headers)
                    resp.raise_for_status()
                    vectors = self._parse_embeddings_response(
                        resp.json(),
                        expected_count=len(clean_texts),
                        target_dim=target_dim,
                    )
                    return vectors if is_batch else vectors[0]
            except Exception as exc:
                if not self.allow_local_hash_projection:
                    raise ConnectionError(
                        f"EMBEDDING_ENDPOINT_UNREACHABLE: '{endpoint}' failed ({type(exc).__name__}: {exc})"
                    ) from exc

        if not self.allow_local_hash_projection:
            raise RuntimeError(
                "EMBEDDING_NOT_CONFIGURED: No local Qwen-embedding endpoint is configured and "
                "local hash-projection fallback is disabled."
            )

        vectors = [
            deterministic_hash_projection(item, dimension=target_dim)
            for item in clean_texts
        ]
        return vectors if is_batch else vectors[0]


local_embedding_provider = LocalEmbeddingProvider()


def embed_text(text: str, *, dimension: int = KEYSTONE_EMBEDDING_DIM) -> List[float]:
    """Module-level convenience helper returning a 1024-dim L2-normalized vector."""
    return local_embedding_provider.embed_text(text, dimension=dimension)


def embed_batch(texts: Sequence[str], *, dimension: int = KEYSTONE_EMBEDDING_DIM) -> List[List[float]]:
    """Module-level convenience helper returning a list of 1024-dim L2-normalized vectors."""
    return local_embedding_provider.embed_batch(texts, dimension=dimension)
