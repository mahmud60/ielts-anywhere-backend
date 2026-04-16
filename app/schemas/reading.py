from pydantic import BaseModel
from typing import Any
import uuid


# ── Sent to frontend — no answer keys ────────────────────────────────────────

class ReadingQuestionOut(BaseModel):
    id: uuid.UUID
    order_index: int
    question_text: str
    options: list[str] | None = None
    # answer_key intentionally absent

    model_config = {"from_attributes": True}


class ReadingQuestionGroupOut(BaseModel):
    id: uuid.UUID
    order_index: int
    question_type: str
    instruction: str
    heading_options: list[str] | None = None
    paragraph_labels: list[str] | None = None
    word_limit: str | None = None
    questions: list[ReadingQuestionOut] = []

    model_config = {"from_attributes": True}


class ReadingPassageOut(BaseModel):
    id: uuid.UUID
    passage_number: int
    title: str
    body: str
    paragraphs: list[str] | None = None
    question_groups: list[ReadingQuestionGroupOut] = []

    model_config = {"from_attributes": True}


class ReadingTestOut(BaseModel):
    id: uuid.UUID
    title: str
    test_type: str
    passages: list[ReadingPassageOut] = []

    model_config = {"from_attributes": True}


# ── Sent from frontend on submit ──────────────────────────────────────────────

class SubmitReadingRequest(BaseModel):
    test_id: uuid.UUID
    # keyed by question UUID string
    # mcq/tfng          → int
    # fill/short_answer → str
    # matching_*        → str (heading roman numeral or paragraph letter)
    answers: dict[str, Any]


# ── Returned after scoring ────────────────────────────────────────────────────

class QuestionResult(BaseModel):
    question_id: str
    question_type: str
    question_text: str
    user_answer: Any
    correct_answer: Any
    is_correct: bool
    tip: str | None = None


class PassageResult(BaseModel):
    passage_number: int
    passage_title: str
    correct: int
    total: int
    band: float


class ReadingResultOut(BaseModel):
    attempt_id: uuid.UUID
    correct: int
    total: int
    overall_band: float
    passage_results: list[PassageResult]
    question_results: list[QuestionResult]
    improvement_tips: list[str]

    model_config = {"from_attributes": True}