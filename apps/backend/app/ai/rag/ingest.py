"""Clean, chunk, embed and store. Replaces earlier chunks of the same entity."""
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings.provider import embed_texts, model_name
from app.ai.models import Embedding
from app.ai.rag.chunking import chunk_text
from app.ai.rag.help_docs import HELP_DOCS


async def upsert_entity(
    s: AsyncSession, entity_type: str, entity_id: str, owner_id: uuid.UUID | None, title: str, text: str
) -> int:
    await delete_entity(s, entity_type, entity_id)
    chunks = chunk_text(" ".join(text.split()))
    if not chunks:
        return 0
    vectors = await embed_texts(chunks)
    for chunk, vector in zip(chunks, vectors, strict=True):
        s.add(Embedding(
            entity_type=entity_type, entity_id=entity_id, owner_id=owner_id, title=title[:200],
            chunk=chunk, model=model_name(), vector=vector,
        ))
    return len(chunks)


async def delete_entity(s: AsyncSession, entity_type: str, entity_id: str) -> None:
    await s.execute(delete(Embedding).where(Embedding.entity_type == entity_type, Embedding.entity_id == entity_id))


async def ingest_help_docs(s: AsyncSession) -> int:
    total = 0
    for doc_id, (title, body) in HELP_DOCS.items():
        total += await upsert_entity(s, "help", doc_id, None, title, body)
    await s.commit()
    return total
