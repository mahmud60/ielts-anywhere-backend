import uuid
import enum
from sqlalchemy import Column, String, Boolean, ForeignKey, Enum, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.db.base import Base

class SessionStatus(str, enum.Enum):
    in_progress = "in_progress"
    completed = "completed"

class IeltsTest(Base):
    """
    The test template — links one listening test (and later reading,
    writing, speaking) under a single ID. All students taking the
    same test share this row.
    """
    __tablename__ = "ielts_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    test_type = Column(String, default="academic")
    is_active = Column(Boolean, default=True)
    is_demo = Column(Boolean, default=False)

    # FK to each module's test table — nullable because we're building
    # one module at a time. Add reading_test_id etc. when ready.
    listening_test_id = Column(
        UUID(as_uuid=True), ForeignKey("listening_tests.id"), nullable=True
    )
    reading_test_id = Column(
        UUID(as_uuid=True), ForeignKey("reading_tests.id"), nullable=True
    )
    writing_test_id = Column(
        UUID(as_uuid=True), ForeignKey("writing_tests.id"), nullable=True
    )
    speaking_test_id = Column(
        UUID(as_uuid=True), ForeignKey("speaking_tests.id"), nullable=True
    )
    sessions = relationship("TestSession", back_populates="ielts_test")
    listening_test = relationship("ListeningTest")
    reading_test = relationship("ReadingTest")
    writing_test = relationship("WritingTest")
    speaking_test = relationship("SpeakingTest")

class TestSession(Base):
    """
    One student's attempt at a full IELTS test.
    Created when they click "Start test", updated as each module completes.
    Allows resume — if they close the browser and return, we find
    the existing in-progress session and put them back where they were.
    """
    __tablename__ = "test_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    ielts_test_id = Column(
        UUID(as_uuid=True), ForeignKey("ielts_tests.id"), nullable=False
    )
    status = Column(Enum(SessionStatus), default=SessionStatus.in_progress)

    # UUID of the TestAttempt for each module — null until that module is done
    listening_attempt_id = Column(UUID(as_uuid=True), nullable=True)
    reading_attempt_id = Column(UUID(as_uuid=True), nullable=True)
    writing_attempt_id = Column(UUID(as_uuid=True), nullable=True)
    speaking_attempt_id = Column(UUID(as_uuid=True), nullable=True)

    # Cached band scores — populated as each module completes
    # {"listening": 6.5, "reading": null, "writing": null, "speaking": null}
    module_bands = Column(JSON, default=dict)
    module_started_at = Column(JSON, default=dict)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="sessions")
    ielts_test = relationship("IeltsTest", back_populates="sessions")