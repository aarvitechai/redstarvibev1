"""Hybrid search (vector + Postgres full text) merged by reciprocal rank fusion.

The tenant filter is part of the SQL: a user can only ever retrieve public help docs and their own content.
"""
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.provider import embed_query
from app.ai.models import Embedding

WORD = re.compile(r"\w+", re.UNICODE)
RAG_TYPES = ("help", "own_post", "own_comment")


@dataclass
class Chunk:
    entity_type: str
    entity_id: str
    title: str
    text: str
    score: float


def _tenant(user_id: uuid.UUID):  # type: ignore[no-untyped-def]
    return or_(Embedding.owner_id == user_id, Embedding.owner_id.is_(None))


async def retrieve(s: AsyncSession, user_id: uuid.UUID, query: str, k: int = 5) -> list[Chunk]:
    vector = await embed_query(query)
    base = select(Embedding).where(Embedding.entity_type.in_(RAG_TYPES), _tenant(user_id))
    by_vector = list((await s.execute(base.order_by(Embedding.vector.cosine_distance(vector)).limit(20))).scalars())
    tsv = func.to_tsvector("simple", func.coalesce(Embedding.chunk, ""))
    # OR of the words: only \w tokens reach to_tsquery, so its query syntax cannot be injected.
    words = [w for w in WORD.findall(query.lower()) if len(w) > 2]
    by_text: list[Embedding] = []
    if words:
        tsq = func.to_tsquery("simple", " | ".join(words))
        by_text = list((await s.execute(
            base.where(tsv.op("@@")(tsq)).order_by(func.ts_rank(tsv, tsq).desc()).limit(20)
        )).scalars())

    scores: dict[uuid.UUID, float] = {}
    rows: dict[uuid.UUID, Embedding] = {}
    for ranked, weight in ((by_vector, 1.0), (by_text, 2.0)):
        for rank, row in enumerate(ranked):
            scores[row.id] = scores.get(row.id, 0.0) + weight / (60 + rank)
            rows[row.id] = row
    best = sorted(scores, key=lambda i: scores[i], reverse=True)[:k]
    return [
        Chunk(rows[i].entity_type, rows[i].entity_id, rows[i].title or "", rows[i].chunk or "", scores[i]) for i in best
    ]
