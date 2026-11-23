"""
KEYSTONE Cognition Service Package
"""

from services.cognition.src.client import (
    CognitionConnector,
    CognitionClient,
    PINNED_CHECKPOINT,
)
from services.cognition.src.embeddings import (
    CAPABILITY_ID as LOCAL_EMBEDDINGS_CAPABILITY_ID,
    KEYSTONE_EMBEDDING_DIM,
    LOCAL_EMBEDDINGS_MANIFEST,
    LocalEmbeddingProvider,
    cosine_similarity,
    deterministic_hash_projection,
    embed_batch,
    embed_text,
    get_embedding_manifest,
    l2_normalize,
    local_embedding_provider,
)

__all__ = [
    "CognitionConnector",
    "CognitionClient",
    "PINNED_CHECKPOINT",
    "KEYSTONE_EMBEDDING_DIM",
    "LOCAL_EMBEDDINGS_CAPABILITY_ID",
    "LOCAL_EMBEDDINGS_MANIFEST",
    "LocalEmbeddingProvider",
    "cosine_similarity",
    "deterministic_hash_projection",
    "embed_batch",
    "embed_text",
    "get_embedding_manifest",
    "l2_normalize",
    "local_embedding_provider",
]
