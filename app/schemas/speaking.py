from pydantic import BaseModel
from typing import Any
import uuid


# ── Sent to frontend ──────────────────────────────────────────────────────────

class SpeakingPartOut(BaseModel):
    id: uuid.UUID
    part_number: int
    part_type: str
    instructions: str
    questions: list[str]
    cue_card: str | None = None
    prep_time_seconds: int = 0
    response_time_seconds: int | None = None

    model_config = {"from_attributes": True}


class SpeakingTestOut(BaseModel):
    id: uuid.UUID
    title: str
    parts: list[SpeakingPartOut] = []

    model_config = {"from_attributes": True}


# ── Sent from frontend on submit ──────────────────────────────────────────────

class PartResponse(BaseModel):
    part_number: int
    # list of {question, answer} dicts — one per question in this part
    exchanges: list[dict[str, str]]


class SubmitSpeakingRequest(BaseModel):
    test_id: uuid.UUID
    part_responses: list[PartResponse]


# ── Returned after grading ────────────────────────────────────────────────────

class PartScore(BaseModel):
    part_number: int
    part_type: str
    fluency_coherence: float
    lexical_resource: float
    grammatical_range: float
    pronunciation: float      # estimated from text patterns for now
    band: float
    feedback: str
    examiner_notes: str | None = None   # specific observations


class SpeakingResultOut(BaseModel):
    attempt_id: uuid.UUID
    status: str
    overall_band: float | None = None
    part_scores: list[PartScore] | None = None
    improvement_tips: list[str] | None = None
    transcript: list[dict] | None = None   # full Q&A transcript

    model_config = {"from_attributes": True}