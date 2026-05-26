import uuid
from sqlalchemy import Column, String, Text, Numeric, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class SpeakingAttempt(Base):
    __tablename__ = "speaking_attempts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False)
    status = Column(String, default="in_progress")   # in_progress | completed | failed
    transcript = Column(JSONB)
    overall_band = Column(Numeric(2, 1))
    fluency_coherence_band = Column(Numeric(2, 1))
    fluency_coherence_feedback = Column(Text)
    lexical_resource_band = Column(Numeric(2, 1))
    lexical_resource_feedback = Column(Text)
    grammatical_range_band = Column(Numeric(2, 1))
    grammatical_range_feedback = Column(Text)
    pronunciation_band = Column(Numeric(2, 1))
    pronunciation_feedback = Column(Text)
    examiner_summary = Column(Text)
    errors = Column(JSONB)
    elevenlabs_session_id = Column(String)
    completed_at = Column(DateTime(timezone=True))