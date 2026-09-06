from typing import Optional

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_access_token
from app.core.exceptions import ValidationException


async def get_current_user_id(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        return "anonymous-user"

    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    if not payload:
        raise ValidationException("Invalid or expired token")

    return payload.get("sub", "anonymous-user")
