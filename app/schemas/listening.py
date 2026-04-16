from pydantic import BaseModel
from typing import Any
import uuid

# ── Sent to frontend (no answer keys ever) ─────────────────────────────────

class QuestionOut(BaseModel):
    id: uuid.UUID
    order_index: int
    question_type: str
    question_text: str
    options: list[str] | None = None
    matching_pool: list[str] | None = None

    model_config = {"from_attributes": True}

class SectionOut(BaseModel):
    id: uuid.UUID
    section_number: int
    title: str | None = None
    context: str | None = None
    audio_url: str | None = None
    audio_duration_seconds: int | None = None
    questions: list[QuestionOut] = []

    model_config = {"from_attributes": True}

class ListeningTestOut(BaseModel):
    id: uuid.UUID
    title: str
    sections: list[SectionOut] = []

    model_config = {"from_attributes": True}

# ── Sent from frontend on submit ───────────────────────────────────────────

class SubmitListeningRequest(BaseModel):
    test_id: uuid.UUID
    answers: dict[str, Any]   # keyed by question UUID string

# ── Returned after scoring ─────────────────────────────────────────────────

class QuestionResult(BaseModel):
    question_id: str
    question_type: str
    question_text: str
    user_answer: Any
    correct_answer: Any
    is_correct: bool
    tip: str | None = None

class ListeningResultOut(BaseModel):
    attempt_id: uuid.UUID
    correct: int
    total: int
    overall_band: float
    section_scores: dict
    question_results: list[QuestionResult]
    improvement_tips: list[str]

    model_config = {"from_attributes": True}