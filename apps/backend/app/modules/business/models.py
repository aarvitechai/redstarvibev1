import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.core.ids import uuid7
from app.modules.users.models import User


class VerificationRequest(Base):
    __tablename__ = "verification_requests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(10))  # person business
    details: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending approved rejected
    reason: Mapped[str | None] = mapped_column(String(300))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship(lazy="joined", innerjoin=True)


class Plan(Base):
    __tablename__ = "plans"
    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(40))
    includes: Mapped[str] = mapped_column(String(300))
    price_paise: Mapped[int | None] = mapped_column(Integer)  # blank until a super admin sets it
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)


class AdRequest(Base):
    """A business asks to promote a post. Delivering approved ads into the feed is a later feature."""

    __tablename__ = "ad_requests"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid7)
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id", ondelete="CASCADE"))
    headline: Mapped[str] = mapped_column(String(80))
    city: Mapped[str | None] = mapped_column(String(80))
    daily_budget_paise: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending approved rejected
    reason: Mapped[str | None] = mapped_column(String(300))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    business: Mapped[User] = relationship(lazy="joined", innerjoin=True)


class BusinessStaff(Base):
    __tablename__ = "business_staff"
    business_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
