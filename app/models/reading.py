import uuid
import enum
from sqlalchemy import (
    Column, String, Integer, Boolean,
    ForeignKey, Enum, JSON, Text
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class ReadingQuestionType(str, enum.Enum):
    mcq = "mcq"
    tfng = "tfng"
    fill = "fill"
    matching_headings = "matching_headings"
    matching_info = "matching_info"
    short_answer = "short_answer"


class ReadingTest(Base):
    __tablename__ = "reading_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    test_type = Column(String, default="academic")
    is_active = Column(Boolean, default=True)
    is_demo = Column(Boolean, default=False)

    passages = relationship(
        "ReadingPassage",
        back_populates="test",
        order_by="ReadingPassage.passage_number",
    )


class ReadingPassage(Base):
    """
    One passage inside a reading test.
    paragraphs is a JSON list of strings — each string is one labelled
    paragraph (e.g. "A  The phenomenon...").
    If paragraphs is null, body is shown as continuous prose.
    """
    __tablename__ = "reading_passages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey("reading_tests.id"))
    passage_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    paragraphs = Column(JSON)   # list[str] or null

    test = relationship("ReadingTest", back_populates="passages")
    question_groups = relationship(
        "ReadingQuestionGroup",
        back_populates="passage",
        order_by="ReadingQuestionGroup.order_index",
    )


class ReadingQuestionGroup(Base):
    """
    A block of questions sharing one instruction and one question type.
    Mirrors real IELTS paper layout exactly.

    heading_options  — for matching_headings: list of heading strings
    paragraph_labels — for matching_info: list of paragraph letters ["A","B","C"...]
    word_limit       — for fill/short_answer: e.g. "NO MORE THAN TWO WORDS"
    """
    __tablename__ = "reading_question_groups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    passage_id = Column(UUID(as_uuid=True), ForeignKey("reading_passages.id"))
    order_index = Column(Integer, nullable=False)
    question_type = Column(Enum(ReadingQuestionType), nullable=False)
    instruction = Column(Text, nullable=False)
    heading_options = Column(JSON)
    paragraph_labels = Column(JSON)
    word_limit = Column(String)

    passage = relationship("ReadingPassage", back_populates="question_groups")
    questions = relationship(
        "ReadingQuestion",
        back_populates="group",
        order_by="ReadingQuestion.order_index",
    )


class ReadingQuestion(Base):
    """
    One question inside a group.

    answer_key format per type:
      mcq              → int (option index)
      tfng             → int (0=True, 1=False, 2=Not Given)
      fill             → str (lowercase)
      matching_headings→ str (e.g. "iii")
      matching_info    → str (e.g. "B")
      short_answer     → list[str] (all accepted answers, lowercase)
    """
    __tablename__ = "reading_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    group_id = Column(UUID(as_uuid=True), ForeignKey("reading_question_groups.id"))
    order_index = Column(Integer, nullable=False)
    question_text = Column(Text, nullable=False)
    options = Column(JSON)        # for mcq only
    answer_key = Column(JSON, nullable=False)
    wrong_answer_tip = Column(Text)

    group = relationship("ReadingQuestionGroup", back_populates="questions")