from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.session import get_db
from app.models.user import User, SubscriptionTier
from .deps import require_admin

router = APIRouter()


@router.get("/users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
    skip: int = 0,
    limit: int = 50,
    search: str = "",
):
    """Returns paginated user list with optional email search."""
    query = select(User).order_by(User.created_at.desc()).offset(skip).limit(limit)
    if search:
        query = query.where(User.email.ilike(f"%{search}%"))

    result = await db.execute(query)
    users = result.scalars().all()

    return [
        {
            "id": str(u.id),
            "email": u.email,
            "full_name": u.full_name,
            "subscription": u.subscription,
            "is_admin": u.is_admin,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.patch("/users/{user_id}/subscription")
async def update_subscription(
    user_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Manually override a user's subscription tier.
    Useful for giving free access to testers or resolving payment issues.
    """
    user = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    tier = body.get("subscription")
    if tier not in ("free", "pro"):
        raise HTTPException(400, "Subscription must be 'free' or 'pro'")

    user.subscription = SubscriptionTier(tier)
    await db.flush()
    return {"id": str(user.id), "subscription": user.subscription}


@router.patch("/users/{user_id}/admin")
async def toggle_admin(
    user_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Grant or revoke admin status. Admins cannot remove their own status."""
    if str(admin.id) == user_id:
        raise HTTPException(400, "Cannot modify your own admin status")

    user = (await db.execute(
        select(User).where(User.id == user_id)
    )).scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")

    user.is_admin = bool(body.get("is_admin", False))
    await db.flush()
    return {"id": str(user.id), "is_admin": user.is_admin}
