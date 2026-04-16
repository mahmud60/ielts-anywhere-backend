from pydantic import BaseModel
from typing import Any
import uuid

class SubmitAnswersRequest(BaseModel):
    answers: dict[str, Any]

class TestAttemptOut(BaseModel):
    id: uuid.UUID
    module: str
    status: str
    overall_band: float | None = None
    subscores: dict | None = None
    ai_feedback: str | None = None
    improvement_tips: list | None = None

    model_config = {"from_attributes": True}