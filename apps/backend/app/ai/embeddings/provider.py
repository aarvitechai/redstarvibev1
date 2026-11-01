"""Text embeddings. Default 'hash' needs no model download; 'bge' uses BGE-M3 (install the ai extra)."""
import asyncio
import hashlib
import re
from functools import lru_cache

import numpy as np

from app.core.config import settings

TOKEN_RE = re.compile(r"\w+", re.UNICODE)


def model_name() -> str:
    return "BAAI/bge-m3" if settings.embedding_provider == "bge" else "hash-v1"


def _normalize(vec: np.ndarray) -> list[float]:
    norm = float(np.linalg.norm(vec))
    if norm > 0:
        vec = vec / norm
    return [float(x) for x in vec]


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
    return _normalize(vec)


@lru_cache
def _bge():  # type: ignore[no-untyped-def]
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("BAAI/bge-m3", device="cpu")


def embed_texts_sync(texts: list[str]) -> list[list[float]]:
    if settings.embedding_provider == "bge":
        vectors = _bge().encode(texts, normalize_embeddings=True)
        return [_normalize(np.asarray(v)[: settings.embedding_dim]) for v in vectors]
    return [hash_embed(t) for t in texts]


async def embed_texts(texts: list[str]) -> list[list[float]]:
    if settings.embedding_provider == "bge":
        return await asyncio.to_thread(embed_texts_sync, texts)
    return embed_texts_sync(texts)


async def embed_query(text: str) -> list[float]:
    return (await embed_texts([text]))[0]
