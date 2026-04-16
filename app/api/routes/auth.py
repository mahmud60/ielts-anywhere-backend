from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from firebase_admin.auth import InvalidIdTokenError, ExpiredIdTokenError

from app.db.session import get_db
from app.models.user import User
from app.core.security import verify_firebase_token
from app.schemas.auth import UserOut

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
    email = decoded.get("email","")
    full_name = decoded.get("name")

    result = await db.execute(
        select(User).where(User.firebase_uid == firebase_uid)
    )
    user = result.scalar_one_or_none()

    if not user:
        #First time logging in
        user = User(
            firebase_uid = firebase_uid,
            email = email,
            full_name = full_name,
        )
        db.add(user)
        await db.flush()

    return user

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    """
    The frontend calls this once after login to:
    - Trigger the auto-create logic above on first login
    - Get the user's subscription tier and profile data
    """
    return current_user