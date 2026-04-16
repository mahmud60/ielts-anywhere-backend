import uuid
from sqlalchemy import Column, Float, Text, ForeignKey, Enum, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class ModuleType(str, enum.Enum):
    listening = "listening"
    reading = "reading"
    writing = "writing"
    speaking = "speaking"

class GradingStatus(str, enum.Enum):
    pending = "pending"
    grading = "grading"
    complete = "complete"
    failed = "failed"

class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    module = Column(Enum(ModuleType), nullable=False)
    status = Column(Enum(GradingStatus), default=GradingStatus.pending)
    overall_band = Column(Float)
    subscores = Column(JSON)
    ai_feedback = Column(Text)
    improvement_tips = Column(JSON)
    raw_answers = Column(JSON)

    user = relationship("User", back_populates="test_attempts")