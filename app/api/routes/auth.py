from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from firebase_admin.auth import InvalidIdTokenError, ExpiredIdTokenError
import logging

from app.db.session import get_db
from app.models.user import User
from app.models.affiliate import Affiliate, AffiliateReferral, ReferralStatus
from app.core.security import verify_firebase_token
from app.schemas.auth import UserOut
from app.services.email import send_email_sync, build_referral_signup_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

bearer_scheme = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials

    try:
        decoded = verify_firebase_token(token)
    except ExpiredIdTokenError:
        raise HTTPException(status_code=401, detail="Token has expired - please log in again")
    except InvalidIdTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

    firebase_uid = decoded["uid"]
    email = decoded.get("email", "")
    full_name = decoded.get("name")

    # 1. Look up by firebase_uid (normal path)
    user = (await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )).scalar_one_or_none()

    if user:
        return user

    # 2. Same email, different UID — user re-authenticated or changed auth provider
    if email:
        user = (await db.execute(
            select(User).where(User.email == email)
        )).scalar_one_or_none()

    if user:
        user.firebase_uid = firebase_uid
        await db.flush()
        return user

    # 3. Genuinely new user — INSERT, guard against concurrent requests
    user = User(firebase_uid=firebase_uid, email=email, full_name=full_name)
    db.add(user)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        # Another request inserted the same row; fetch it
        user = (await db.execute(
            select(User).where(User.email == email)
        )).scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=500, detail="Could not create or find user account")

    return user

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    The frontend calls this once after login to:
    - Trigger the auto-create logic above on first login
    - Get the user's subscription tier and profile data
    """
    return current_user


@router.post("/link-referral")
async def link_referral(
    ref_code: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Called once by the frontend after signup when a referral code is stored in localStorage.
    Creates a signup-stage AffiliateReferral and emails the affiliate.
    Safe to call multiple times — returns {linked: false} if user is already linked.
    """
    # Idempotency: skip if this user is already attributed to any affiliate
    existing = (await db.execute(
        select(AffiliateReferral).where(AffiliateReferral.referred_user_id == current_user.id)
    )).scalar_one_or_none()
    if existing:
        return {"linked": False, "reason": "already_linked"}

    code = ref_code.strip().upper()
    aff_result = await db.execute(
        select(Affiliate)
        .where(Affiliate.code == code, Affiliate.is_active == True)
        .options(selectinload(Affiliate.user))
    )
    affiliate = aff_result.scalar_one_or_none()
    if not affiliate:
        return {"linked": False, "reason": "invalid_code"}

    # Prevent self-referral
    if affiliate.user_id == current_user.id:
        return {"linked": False, "reason": "self_referral"}

    db.add(AffiliateReferral(
        affiliate_id=affiliate.id,
        referred_user_id=current_user.id,
        status=ReferralStatus.pending,
    ))
    await db.flush()

    # Notify the affiliate by email (fire-and-forget; don't block on failure)
    if affiliate.user and affiliate.user.email:
        try:
            subject, html = build_referral_signup_email(
                affiliate_name=affiliate.user.full_name or "",
                referred_email=current_user.email or "",
                code=affiliate.code,
                commission_rate=float(affiliate.commission_rate),
            )
            send_email_sync(affiliate.user.email, subject, html)
        except Exception:
            logger.exception("Failed to send referral signup email to %s", affiliate.user.email)

    return {"linked": True}