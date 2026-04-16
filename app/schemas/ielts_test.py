from pydantic import BaseModel
import uuid

class IeltsTestOut(BaseModel):
    id: uuid.UUID
    title: str
    test_type: str
    is_demo: bool
    listening_test_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}

class StartSessionRequest(BaseModel):
    ielts_test_id: uuid.UUID

class TestSessionOut(BaseModel):
    id: uuid.UUID
    ielts_test_id: uuid.UUID
    status: str
    listening_attempt_id: uuid.UUID | None = None
    reading_attempt_id: uuid.UUID | None = None
    writing_attempt_id: uuid.UUID | None = None
    speaking_attempt_id: uuid.UUID | None = None
    module_bands: dict = {}
    # Tells the frontend which module to render next
    current_module: str
    time_limit_seconds: int = 3600
    model_config = {"from_attributes": True}