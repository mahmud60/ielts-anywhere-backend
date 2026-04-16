import uuid
import enum
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey, Enum, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class WritingTaskType(str, enum.Enum):
    task1_academic = "task1_academic"   # describe a graph/chart/diagram
    task1_general = "task1_general"     # write a letter
    task2 = "task2"                     # discursive essay


class WritingTest(Base):
    """
    A writing test containing exactly two tasks.
    Task 1 comes first (150+ words), Task 2 second (250+ words).
    """
    __tablename__ = "writing_tests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    test_type = Column(String, default="academic")
    is_active = Column(Boolean, default=True)
    is_demo = Column(Boolean, default=False)

    tasks = relationship(
        "WritingTask",
        back_populates="test",
        order_by="WritingTask.task_number",
    )


class WritingTask(Base):
    """
    One writing task — either Task 1 or Task 2.

    prompt        — the question/instruction shown to the student
    stimulus      — for Task 1: description of the graph/chart
                    (in a real system this would reference an image)
    min_words     — minimum word count (150 for Task 1, 250 for Task 2)
    sample_answer — used only for teacher reference, never shown to students
    """
    __tablename__ = "writing_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    test_id = Column(UUID(as_uuid=True), ForeignKey("writing_tests.id"))
    task_number = Column(Integer, nullable=False)   # 1 or 2
    task_type = Column(Enum(WritingTaskType), nullable=False)
    prompt = Column(Text, nullable=False)
    stimulus = Column(Text)      # graph description for Task 1
    min_words = Column(Integer, nullable=False)

    test = relationship("WritingTest", back_populates="tasks")