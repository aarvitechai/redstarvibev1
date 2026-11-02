"""Assistant embeddings: bge-m3 on Workers AI when configured, otherwise offline hashing. Each row records its model."""
import hashlib
import re

import numpy as np

from app.ai.embeddings import search as cloud
from app.core.config import settings

TOKEN_RE = re.compile(r"\w+", re.UNICODE)
HASH_MODEL = "hash-v1"


def current_model() -> str:
    return settings.embed_model if cloud.is_enabled() else HASH_MODEL


def hash_embed(text: str, dim: int | None = None) -> list[float]:
    """Signed feature hashing of words and character trigrams. Lexical, not semantic, and fully offline."""
    size = dim or settings.embedding_dim
    vec = np.zeros(size, dtype=np.float32)
    words = TOKEN_RE.findall(text.lower())
    features = list(words)
    for word in words:
        padded = f"#{word}#"
        features.extend(padded[i:i + 3] for i in range(max(0, len(padded) - 2)))
    for feature in features:
        digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "big") % size
        sign = 1.0 if digest[4] & 1 else -1.0
        weight = 2.0 if feature in words else 1.0
        vec[idx] += sign * weight
    norm = float(np.linalg.norm(vec))
    return [float(x) for x in (vec / norm if norm > 0 else vec)]


async def embed_texts(texts: list[str]) -> tuple[list[list[float]], str]:
    vectors = await cloud.embed_many(texts)
    if vectors:
        return vectors, settings.embed_model
    return [hash_embed(t) for t in texts], HASH_MODEL


async def embed_query(text: str) -> tuple[list[float], str]:
    vector = await cloud.embed_query(text)
    if vector:
        return vector, settings.embed_model
    return hash_embed(text), HASH_MODEL
