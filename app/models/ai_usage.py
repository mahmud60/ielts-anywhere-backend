import uuid

from sqlalchemy import Column, String, Integer, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID

from app.db.base import Base


class AIUsage(Base):
    """One row per AI API call (Claude grading/tips/learn, Whisper) — model,
    token counts, and an estimated USD cost. Powers the admin AI-usage view."""

    __tablename__ = "ai_usage"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    module = Column(String(40), nullable=False, index=True)   # writing / speaking / vocabulary / ...
    provider = Column(String(20), nullable=False, default="anthropic")
    model = Column(String(60), nullable=False)
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)
    # created_at / updated_at inherited from Base

    __table_args__ = (Index("ix_ai_usage_created_at", "created_at"),)
