import hmac
import hashlib
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.db.session import get_db
from app.models.user import User, SubscriptionTier
from app.models.affiliate import Affiliate, AffiliateReferral
from app.core.config import settings
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/checkout-url")
async def get_checkout_url(
    ref: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generates a LemonSqueezy checkout URL for the Pro plan.
    Prefills the customer's email and embeds their user ID in
    custom_data so the webhook can identify them after payment.
    Optionally accepts a referral code via ?ref=CODE.
    """
    if not settings.LEMONSQUEEZY_API_KEY:
        raise HTTPException(503, "Payment system not configured")

    custom = {"user_id": str(current_user.id)}

    if ref:
        code = ref.strip().upper()
        result = await db.execute(
            select(Affiliate).where(Affiliate.code == code, Affiliate.is_active == True)
        )
        affiliate = result.scalar_one_or_none()
        if affiliate:
            custom["ref_code"] = code

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.lemonsqueezy.com/v1/checkouts",
            headers={
                "Authorization": f"Bearer {settings.LEMONSQUEEZY_API_KEY}",
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json",
            },
            json={
                "data": {
                    "type": "checkouts",
                    "attributes": {
                        "checkout_data": {
                            "email": current_user.email,
                            "custom": custom,
                        },
                        "product_options": {
                            "redirect_url": "http://localhost:3000/dashboard",
                        },
                    },
                    "relationships": {
                        "variant": {
                            "data": {
                                "type": "variants",
                                "id": settings.LEMONSQUEEZY_PRO_VARIANT_ID,
                            }
                        }
                    },
                }
            },
        )

    if response.status_code not in (200, 201):
        raise HTTPException(502, "Failed to create checkout session")

    data = response.json()
    checkout_url = data["data"]["attributes"]["url"]
    return {"checkout_url": checkout_url}


@router.post("/webhook")
async def lemonsqueezy_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_signature: str = Header(None, alias="X-Signature"),
):
    """
    Receives payment events from LemonSqueezy.
    Verifies the HMAC-SHA256 signature then updates the user's subscription.

    Events we handle:
      order_created       — one-time purchase completed
      subscription_created — subscription started
      subscription_updated — subscription changed (upgrade/downgrade)
      subscription_cancelled — subscription cancelled → revert to free
    """
    body = await request.body()

    # Verify signature — reject anything that doesn't match
    if settings.LEMONSQUEEZY_WEBHOOK_SECRET:
        expected = hmac.new(
            settings.LEMONSQUEEZY_WEBHOOK_SECRET.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_signature or ""):
            raise HTTPException(401, "Invalid webhook signature")

    payload = json.loads(body)
    event_name = payload.get("meta", {}).get("event_name", "")
    custom_data = payload.get("meta", {}).get("custom_data", {})
    user_id = custom_data.get("user_id")

    if not user_id:
        # No user ID in custom_data — can't process
        return {"received": True}

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        return {"received": True}

    # Store the LemonSqueezy customer ID for future lookups
    attributes = payload.get("data", {}).get("attributes", {})
    customer_id = str(attributes.get("customer_id", ""))
    if customer_id:
        user.lemonsqueezy_customer_id = customer_id

    if event_name in ("order_created", "subscription_created", "subscription_updated"):
        status = attributes.get("status", "")
        # For subscriptions: only activate if status is active
        if event_name == "order_created" or status in ("active", "on_trial"):
            user.subscription = SubscriptionTier.pro

            # Record affiliate referral if a ref_code was passed at checkout
            ref_code = custom_data.get("ref_code", "").strip().upper()
            if ref_code:
                aff_result = await db.execute(
                    select(Affiliate).where(Affiliate.code == ref_code, Affiliate.is_active == True)
                )
                affiliate = aff_result.scalar_one_or_none()
                if affiliate:
                    order_id = str(payload.get("data", {}).get("id", ""))
                    # Avoid duplicate referral records for the same order
                    dup = await db.execute(
                        select(AffiliateReferral).where(AffiliateReferral.order_id == order_id)
                    )
                    if not dup.scalar_one_or_none():
                        total_cents = attributes.get("total", 0) or 0
                        order_amount = round(total_cents / 100, 2)
                        commission = round(order_amount * float(affiliate.commission_rate), 2)
                        db.add(AffiliateReferral(
                            affiliate_id=affiliate.id,
                            referred_user_id=user.id,
                            order_id=order_id,
                            order_amount=order_amount,
                            commission_amount=commission,
                        ))

    elif event_name == "subscription_cancelled":
        # Revert to free when subscription is cancelled
        user.subscription = SubscriptionTier.free

    await db.flush()
    return {"received": True}