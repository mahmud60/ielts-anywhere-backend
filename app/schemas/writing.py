from pydantic import BaseModel
from typing import Any
import uuid


# ── Sent to frontend ──────────────────────────────────────────────────────────

class WritingTaskOut(BaseModel):
    id: uuid.UUID
    task_number: int
    task_type: str
    prompt: str
    stimulus: str | None = None
    min_words: int

    model_config = {"from_attributes": True}


class WritingTestOut(BaseModel):
    id: uuid.UUID
    title: str
    test_type: str
    tasks: list[WritingTaskOut] = []

    model_config = {"from_attributes": True}


# ── Sent from frontend on submit ──────────────────────────────────────────────

class SubmitWritingRequest(BaseModel):
    test_id: uuid.UUID
    # keyed by task UUID string → student's written response
    responses: dict[str, str]


# ── Task-level scores returned after grading ──────────────────────────────────

class TaskScore(BaseModel):
    task_number: int
    task_type: str
    # The 4 official IELTS writing criteria
    task_achievement: float       # how well the task is addressed
    coherence_cohesion: float     # logical flow and linking
    lexical_resource: float       # vocabulary range and accuracy
    grammatical_range: float      # grammar range and accuracy
    band: float                   # average of the 4 criteria
    feedback: str                 # 2-3 sentence examiner comment
    word_count: int


class WritingResultOut(BaseModel):
    attempt_id: uuid.UUID
    status: str                   # "pending" | "complete" | "failed"
    overall_band: float | None = None
    task_scores: list[TaskScore] | None = None
    improvement_tips: list[str] | None = None

    model_config = {"from_attributes": True}