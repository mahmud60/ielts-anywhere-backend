import uuid
import enum
from sqlalchemy import (
    Column, String, Integer, Boolean,
    ForeignKey, Enum, JSON, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class SpeakingPartType(str, enum.Enum):
    part1 = "part1"   # interview — 4-5 short questions
    part2 = "part2"   # long turn — cue card monologue
    part3 = "part3"   # discussion — 4-5 abstract questions


class SpeakingTest(Base):
    """
    A full speaking test — always three parts in order.
    All students taking the same test share this template.
    """
    __tablename__ = "speaking_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_demo = Column(Boolean, default=False)

    parts = relationship(
        "SpeakingPart",
        back_populates="test",
        order_by="SpeakingPart.part_number",
    )


class SpeakingPart(Base):
    """
    One part of the speaking test.

    For Part 1 and Part 3: questions is a JSON list of question strings.
    For Part 2: cue_card is the topic card text, questions contains
    the bullet points the student should cover.

    prep_time_seconds: preparation time before speaking (Part 2 only — 60s)
    response_time_seconds: suggested speaking time
    """
    __tablename__ = "speaking_parts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey("speaking_tests.id"))
    part_number = Column(Integer, nullable=False)   # 1, 2, or 3
    part_type = Column(Enum(SpeakingPartType), nullable=False)
    instructions = Column(Text, nullable=False)      # shown to student at top
    questions = Column(JSON, nullable=False)         # list of question strings
    cue_card = Column(Text)                          # Part 2 only
    prep_time_seconds = Column(Integer, default=0)   # Part 2: 60
    response_time_seconds = Column(Integer)          # suggested speaking time

    test = relationship("SpeakingTest", back_populates="parts")