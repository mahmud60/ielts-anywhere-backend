import uuid
import enum
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Enum, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base

class QuestionType(str, enum.Enum):
    mcq = "mcq"
    fill = "fill"
    tfng = "tfng"
    matching = "matching"

class ListeningTest(Base):
    __tablename__ = "listening_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_demo = Column(Boolean, default=False)

    sections = relationship(
        "ListeningSection",
        back_populates="test",
        order_by="ListeningSection.section_number",
    )

class ListeningSection(Base):
    __tablename__ = "listening_sections"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey("listening_tests.id"))
    section_number = Column(Integer, nullable=False)
    title = Column(String)
    context = Column(Text)
    audio_url = Column(String)
    audio_duration_seconds = Column(Integer)

    test = relationship("ListeningTest", back_populates="sections")
    questions = relationship(
        "ListeningQuestion",
        back_populates="section",
        order_by="ListeningQuestion.order_index",
    )

class ListeningQuestion(Base):
    __tablename__ = "listening_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    section_id = Column(UUID(as_uuid=True), ForeignKey("listening_sections.id"))
    order_index = Column(Integer, nullable=False)
    question_type = Column(Enum(QuestionType), nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSON)
    matching_pool = Column(JSON)
    answer_key = Column(JSON, nullable=False)
    wrong_answer_tip = Column(Text)

    section = relationship("ListeningSection", back_populates="questions")