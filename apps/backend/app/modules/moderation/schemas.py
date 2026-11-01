import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ReportIn(BaseModel):
    entity_type: Literal["post", "comment", "user", "story", "message"]
    entity_id: uuid.UUID
    reason: Literal["spam", "harassment", "hate", "violence", "nudity", "child_safety", "self_harm", "other"]
    details: str | None = Field(None, max_length=1000)


class ReportOut(BaseModel):
    id: uuid.UUID
    entity_type: str
    entity_id: uuid.UUID
    reason: str
    details: str | None
    status: str
    source: str
    score: float | None
    created_at: datetime
