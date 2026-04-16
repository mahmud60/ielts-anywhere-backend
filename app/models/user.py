import uuid
from sqlalchemy import Column, String, Boolean, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base
import enum

class SubscriptionTier(str, enum.Enum):
    free = "free"
    pro = "pro"

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    firebase_uid = Column(String, unique=True, index=True, nullable=False)

    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    subscription = Column(
        Enum(SubscriptionTier), default=SubscriptionTier.free
    )
    lemonsqueezy_customer_id = Column(String, unique=True, nullable=True)
    
    test_attempts = relationship("TestAttempt", back_populates="user")
    sessions = relationship("TestSession", back_populates="user")