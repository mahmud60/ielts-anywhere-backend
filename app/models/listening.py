import uuid
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Text, JSON, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base import Base


class ListeningTest(Base):
    __tablename__ = "listening_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    task = Column(String, default="ielts_listening")
    type = Column(String, default="text")
    order = Column(Integer, default=1)
    is_active = Column(Boolean, default=True)
    is_recommended = Column(Boolean, default=False)
    mock_test_order = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=True)

    sections = relationship(
        "ListeningSection",
        back_populates="test",
        order_by="ListeningSection.part",
        cascade="all, delete-orphan",
    )


class ListeningSection(Base):
    __tablename__ = "listening_sections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    test_id = Column(UUID(as_uuid=True), ForeignKey("listening_tests.id"))
    part = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    audio = Column(String, nullable=True)

    test = relationship("ListeningTest", back_populates="sections")
    subsections = relationship(
        "ListeningSubsection",
        back_populates="section",
        order_by="ListeningSubsection.order",
        cascade="all, delete-orphan",
    )


class ListeningSubsection(Base):
    __tablename__ = "listening_subsections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    section_id = Column(Integer, ForeignKey("listening_sections.id"))
    order = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    subsection_type = Column(String, nullable=False)  # "form" or "regular"
    text = Column(Text, nullable=True)
    visual = Column(JSON, nullable=True)
    grid_headers = Column(JSON, nullable=True)
    grid_cells = Column(JSON, nullable=True)

    section = relationship("ListeningSection", back_populates="subsections")
    questions = relationship(
        "ListeningQuestion",
        back_populates="subsection",
        order_by="ListeningQuestion.order",
        cascade="all, delete-orphan",
    )


class ListeningQuestion(Base):
    __tablename__ = "listening_questions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subsection_id = Column(Integer, ForeignKey("listening_subsections.id"))
    order = Column(Integer, nullable=False)
    title = Column(String, nullable=True)
    question_type = Column(String, nullable=False)  # fill_in_the_blank | multiple_choices | multiple_select | dropdown
    ielts_question_type = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    max_selected_options = Column(Integer, nullable=True)
    options = Column(JSON, default=list)  # [{order: int, option: str}]
    answer_key = Column(JSON, nullable=False)
    wrong_answer_tip = Column(Text, nullable=True)

    subsection = relationship("ListeningSubsection", back_populates="questions")
