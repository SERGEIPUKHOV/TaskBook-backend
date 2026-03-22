from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.api.v1.auth.deps import get_current_user, get_optional_user
from app.models.user import User


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user


__all__ = ["get_current_user", "get_optional_user", "require_admin"]
