import uuid
import enum
from sqlalchemy import Column, String, Boolean, Numeric, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.db.base import Base


class ReferralStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    paid = "paid"


class Affiliate(Base):
    __tablename__ = "affiliates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    commission_rate = Column(Numeric(5, 4), nullable=False, default=0.20)  # e.g. 0.20 = 20%
    is_active = Column(Boolean, default=True, nullable=False)
    discount_code = Column(String(100), nullable=True)

    user = relationship("User", back_populates="affiliate")
    referrals = relationship("AffiliateReferral", back_populates="affiliate")


class AffiliateReferral(Base):
    __tablename__ = "affiliate_referrals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    affiliate_id = Column(UUID(as_uuid=True), ForeignKey("affiliates.id"), nullable=False, index=True)
    referred_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    order_id = Column(String(100), unique=True, nullable=True)
    order_amount = Column(Numeric(10, 2), nullable=True)
    commission_amount = Column(Numeric(10, 2), nullable=True)
    status = Column(SAEnum(ReferralStatus), default=ReferralStatus.pending, nullable=False)

    affiliate = relationship("Affiliate", back_populates="referrals")
    referred_user = relationship("User", foreign_keys=[referred_user_id])