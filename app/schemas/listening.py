from pydantic import BaseModel, Field
from typing import Any
import uuid
from datetime import datetime


# ── Sent to frontend (no answer keys ever) ─────────────────────────────────

class QuestionOut(BaseModel):
    id: int
    order: int
    group_label: str | None = None
    question_type: str
    ielts_question_type: str | None = None
    text: str | None = Field(None, validation_alias="stem")
    max_selected_options: int | None = None
    options: list[dict] = []

    model_config = {"from_attributes": True, "populate_by_name": True}


class SubsectionOut(BaseModel):
    id: int
    order: int
    title: str | None = None
    subsection_type: str
    text: str | None = Field(None, validation_alias="instruction")
    visual: Any = None
    grid_headers: Any = None
    grid_cells: Any = None
    questions: list[QuestionOut] = []

    model_config = {"from_attributes": True}


class SectionOut(BaseModel):
    id: int
    part: int
    title: str | None = None
    audio: str | None = None
    transcript: str | None = None
    subsections: list[SubsectionOut] = []

    model_config = {"from_attributes": True, "populate_by_name": True}


# ── Sent from frontend on submit ───────────────────────────────────────────

class SubmitListeningRequest(BaseModel):
    test_id: uuid.UUID
    answers: dict[str, Any]   # keyed by question integer ID (as string)


# ── Returned after scoring ─────────────────────────────────────────────────

class QuestionResult(BaseModel):
    question_id: str
    question_type: str
    text: str
    user_answer: Any
    correct_answer: Any
    is_correct: bool
    tip: str | None = None
    has_tip: bool = False


class ListeningResultOut(BaseModel):
    attempt_id: uuid.UUID
    correct: int
    total: int
    overall_band: float
    section_scores: dict
    question_results: list[QuestionResult]
    improvement_tips: list[str]

    model_config = {"from_attributes": True}
