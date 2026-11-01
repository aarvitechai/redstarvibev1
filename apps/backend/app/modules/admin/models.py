import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.ids import uuid7


class TestDataBatch(Base):
    __tablename__ = "test_data_batches"
    __test__ = False  # not a pytest class
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    label: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(12), default="creating")  # creating ready failed removing removed
    error: Mapped[str | None] = mapped_column(String(300))
    params: Mapped[dict[str, Any]] = mapped_column(JSONB)
    user_count: Mapped[int] = mapped_column(Integer, default=0)
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
