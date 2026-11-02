import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.config import settings
from app.core.database import Base
from app.core.ids import uuid7


class Embedding(Base):
    """Vectors for RAG chunks. Post search vectors live on posts.embedding. owner_id is the tenant filter at query time."""

    __tablename__ = "embeddings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    entity_type: Mapped[str] = mapped_column(String(20))  # help own_post own_comment
    entity_id: Mapped[str] = mapped_column(String(120))
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))  # null: public (help docs)
    chunk: Mapped[str | None] = mapped_column(Text)
    title: Mapped[str | None] = mapped_column(String(200))
    model: Mapped[str] = mapped_column(String(60))
    vector: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
