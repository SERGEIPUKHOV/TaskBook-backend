from __future__ import annotations

from fastapi import Depends, HTTPException, status

from app.api.deps import get_current_user
from app.models.user import User

# BLOCK-START: ADMIN_DEPS
# Description: Admin-specific dependencies local to the admin route package.
async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """
    function_contracts:
      require_admin:
        description: "Ensures that the authenticated caller has admin access."
        preconditions:
          - "Requester is authenticated through get_current_user"
        postconditions:
          - "Returns the current user when is_admin is true"
          - "Raises 403 when admin access is missing"
    """
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return current_user
# BLOCK-END: ADMIN_DEPS

__all__ = ["require_admin"]
