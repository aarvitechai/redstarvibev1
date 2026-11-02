import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.ids import uuid7
from app.modules.media.models import MediaAsset
from app.modules.users.models import User


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    caption: Mapped[str] = mapped_column(Text, default="")
    location: Mapped[str | None] = mapped_column(CITEXT)
    visibility: Mapped[str] = mapped_column(String(12), default="public")  # public followers
    status: Mapped[str] = mapped_column(String(14), default="processing")
    # draft scheduled processing published failed blocked
    is_reel: Mapped[bool] = mapped_column(Boolean, default=False)
    like_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_count: Mapped[int] = mapped_column(Integer, default=0)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    save_count: Mapped[int] = mapped_column(Integer, default=0)
    engagement_score: Mapped[float] = mapped_column(Float, default=0)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    author: Mapped[User] = relationship(lazy="joined", innerjoin=True)
    media: Mapped[list["PostMedia"]] = relationship(
        order_by="PostMedia.position", lazy="selectin", cascade="all, delete-orphan"
    )

    @property
    def overlay_texts(self) -> list[str]:
        return [m.text_overlay["text"] for m in self.media if m.text_overlay]

    @property
    def full_text(self) -> str:
        """Everything the author wrote. Moderation and search indexing must read this, not only the caption."""
        return "\n".join(filter(None, [self.caption, *self.overlay_texts]))


class PostMedia(Base):
    __tablename__ = "post_media"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    asset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("media_assets.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer, default=0)
    alt_text: Mapped[str | None] = mapped_column(String(500))
    text_overlay: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    asset: Mapped[MediaAsset] = relationship(lazy="joined", innerjoin=True)


class Like(Base):
    __tablename__ = "likes"  # hash partitioned by user_id, see ADR 0003
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Hashtag(Base):
    __tablename__ = "hashtags"
    tag: Mapped[str] = mapped_column(CITEXT, primary_key=True)
    post_count: Mapped[int] = mapped_column(Integer, default=0)


class PostHashtag(Base):
    __tablename__ = "post_hashtags"
    tag: Mapped[str] = mapped_column(ForeignKey("hashtags.tag", ondelete="CASCADE"), primary_key=True)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)


class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Save(Base):
    __tablename__ = "saves"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid7, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True)
    collection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("collections.id", ondelete="SET NULL"))
