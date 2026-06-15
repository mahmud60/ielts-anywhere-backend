from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from typing import Optional
import re
import uuid

from app.db.session import get_db
from app.models.user import User
from app.models.affiliate import Affiliate, AffiliateReferral, ReferralStatus
from app.api.routes.auth import get_current_user
from app.api.routes.admin import require_admin

router = APIRouter(tags=["affiliates"])


# ── Schemas ────────────────────────────────────────────────────────────────────

class AffiliateCreate(BaseModel):
    user_email: str
    code: str = Field(..., min_length=3, max_length=50)
    commission_rate: float = Field(0.20, ge=0.0, le=1.0)


class AffiliateUpdate(BaseModel):
    commission_rate: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None
    discount_code: Optional[str] = Field(None, max_length=100)


def _clean_code(code: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "", code).upper()


def _referral_summary(referrals):
    signup_count = sum(1 for r in referrals if r.referred_user_id is not None)
    conversion_count = sum(1 for r in referrals if r.order_id is not None)
    earnings = sum(float(r.commission_amount or 0) for r in referrals if r.status != ReferralStatus.pending)
    pending = sum(float(r.commission_amount or 0) for r in referrals if r.status == ReferralStatus.pending)
    return {
        "signup_count": signup_count,
        "conversion_count": conversion_count,
        "confirmed_earnings": earnings,
        "pending_earnings": pending,
    }


def _affiliate_out(aff):
    summary = _referral_summary(aff.referrals)
    return {
        "id": str(aff.id),
        "user_id": str(aff.user_id),
        "user_email": aff.user.email if aff.user else None,
        "user_name": aff.user.full_name if aff.user else None,
        "code": aff.code,
        "commission_rate": float(aff.commission_rate),
        "discount_code": aff.discount_code,
        "is_active": aff.is_active,
        "created_at": aff.created_at.isoformat() if aff.created_at else None,
        **summary,
    }


# ── Admin routes ───────────────────────────────────────────────────────────────

@router.post("/admin/affiliates")
async def create_affiliate(
    body: AffiliateCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    code = _clean_code(body.code)
    if not code:
        raise HTTPException(400, "Invalid affiliate code")

    user_result = await db.execute(select(User).where(User.email == body.user_email))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, f"No user found with email {body.user_email}")

    existing_aff = await db.execute(select(Affiliate).where(Affiliate.user_id == user.id))
    if existing_aff.scalar_one_or_none():
        raise HTTPException(409, "This user already has an affiliate account")

    code_taken = await db.execute(select(Affiliate).where(Affiliate.code == code))
    if code_taken.scalar_one_or_none():
        raise HTTPException(409, f"Code '{code}' is already taken")

    aff = Affiliate(
        user_id=user.id,
        code=code,
        commission_rate=body.commission_rate,
    )
    db.add(aff)
    await db.flush()
    await db.refresh(aff)

    # Load relationships for response
    result = await db.execute(
        select(Affiliate)
        .where(Affiliate.id == aff.id)
        .options(selectinload(Affiliate.user), selectinload(Affiliate.referrals))
    )
    aff = result.scalar_one()
    return _affiliate_out(aff)


@router.get("/admin/affiliates")
async def list_affiliates(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(Affiliate)
        .options(selectinload(Affiliate.user), selectinload(Affiliate.referrals))
        .order_by(Affiliate.created_at.desc())
    )
    affiliates = result.scalars().all()
    return [_affiliate_out(a) for a in affiliates]


@router.patch("/admin/affiliates/{affiliate_id}")
async def update_affiliate(
    affiliate_id: str,
    body: AffiliateUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(Affiliate)
        .where(Affiliate.id == affiliate_id)
        .options(selectinload(Affiliate.user), selectinload(Affiliate.referrals))
    )
    aff = result.scalar_one_or_none()
    if not aff:
        raise HTTPException(404, "Affiliate not found")

    if body.commission_rate is not None:
        aff.commission_rate = body.commission_rate
    if body.is_active is not None:
        aff.is_active = body.is_active
    if body.discount_code is not None:
        aff.discount_code = body.discount_code or None  # empty string → NULL

    await db.flush()
    return _affiliate_out(aff)


@router.get("/admin/affiliates/{affiliate_id}/referrals")
async def get_affiliate_referrals(
    affiliate_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    result = await db.execute(
        select(AffiliateReferral)
        .where(AffiliateReferral.affiliate_id == affiliate_id)
        .options(selectinload(AffiliateReferral.referred_user))
        .order_by(AffiliateReferral.created_at.desc())
    )
    referrals = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "referred_user_email": r.referred_user.email if r.referred_user else None,
            "order_id": r.order_id,
            "order_amount": float(r.order_amount) if r.order_amount else None,
            "commission_amount": float(r.commission_amount) if r.commission_amount else None,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in referrals
    ]


# ── Affiliate self-service ─────────────────────────────────────────────────────

@router.get("/affiliate/me")
async def get_my_affiliate(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Affiliate)
        .where(Affiliate.user_id == current_user.id)
        .options(selectinload(Affiliate.referrals).selectinload(AffiliateReferral.referred_user))
    )
    aff = result.scalar_one_or_none()
    if not aff:
        raise HTTPException(404, "You don't have an affiliate account")

    referrals_out = [
        {
            "id": str(r.id),
            "referred_user_email": r.referred_user.email if r.referred_user else None,
            "signed_up": r.referred_user_id is not None,
            "converted": r.order_id is not None,
            "order_amount": float(r.order_amount) if r.order_amount else None,
            "commission_amount": float(r.commission_amount) if r.commission_amount else None,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in aff.referrals
    ]
    summary = _referral_summary(aff.referrals)
    return {
        "id": str(aff.id),
        "code": aff.code,
        "commission_rate": float(aff.commission_rate),
        "discount_code": aff.discount_code,
        "is_active": aff.is_active,
        "referral_link": f"https://ieltsanywhere.com/login?ref={aff.code}",
        "referrals": referrals_out,
        **summary,
    }


@router.get("/affiliate/validate/{code}")
async def validate_code(
    code: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint — frontend calls this to confirm a code is valid before checkout."""
    result = await db.execute(
        select(Affiliate).where(Affiliate.code == code.upper(), Affiliate.is_active == True)
    )
    aff = result.scalar_one_or_none()
    if not aff:
        raise HTTPException(404, "Invalid or inactive affiliate code")
    return {"valid": True, "code": aff.code}