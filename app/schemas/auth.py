from pydantic import BaseModel
import uuid

class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None = None
    subscription: str
    is_admin: bool = False 
    model_config= {"from_attributes": True}