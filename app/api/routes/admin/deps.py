from fastapi import Depends, HTTPException

from app.models.user import User
from app.api.routes.auth import get_current_user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    Dependency that blocks non-admin users from all admin routes.
    Add this to every admin endpoint.
    """
    if not current_user.is_admin:
        raise HTTPException(403, "Admin access required")
    return current_user
