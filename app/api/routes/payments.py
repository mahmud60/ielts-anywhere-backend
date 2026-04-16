import hmac
import hashlib
import json
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User, SubscriptionTier
from app.core.config import settings
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/payments", tags=["payments"])


@router.get("/checkout-url")
async def get_checkout_url(
    current_user: User = Depends(get_current_user),
):
    """
    Generates a LemonSqueezy checkout URL for the Pro plan.
    Prefills the customer's email and embeds their user ID in
    custom_data so the webhook can identify them after payment.
    """
    if not settings.LEMONSQUEEZY_API_KEY:
        raise HTTPException(503, "Payment system not configured")

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
                            "custom": {
                                # This comes back in the webhook so we know who paid
                                "user_id": str(current_user.id),
                            },
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

    elif event_name == "subscription_cancelled":
        # Revert to free when subscription is cancelled
        user.subscription = SubscriptionTier.free

    await db.flush()
    return {"received": True}