from __future__ import annotations

from fastapi import APIRouter, Depends, Response as FastAPIResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cookies import set_auth_cookies
from app.core.database import get_db
from app.schemas.auth import AuthResponseOut, RegisterIn
from app.schemas.common import Response
from app.services.auth_service import register_user

# BLOCK-START: AUTH_REGISTER_MODULE
# Description: Registration endpoint for new user accounts and initial browser auth cookies.
router = APIRouter()


# BLOCK-START: AUTH_REGISTER_ENDPOINT
# Description: Registers a new user account and issues browser auth cookies.
@router.post("/register", response_model=Response[AuthResponseOut])
async def register(
    data: RegisterIn,
    response: FastAPIResponse,
    db: AsyncSession = Depends(get_db),
) -> Response[AuthResponseOut]:
    """
    function_contracts:
      register:
        description: "Creates a new user account, seeds default habits, and returns auth tokens."
        preconditions:
          - "data.email: valid user email"
          - "data.password: passes auth schema validation"
        postconditions:
          - "Returns AuthResponseOut with access and refresh tokens"
          - "Sets browser auth cookies on the response"
          - "409 if email is already in use"
    """
    auth = await register_user(db, data.email, data.password)
    set_auth_cookies(response, auth.access_token, auth.refresh_token)
    return Response(data=auth)
# BLOCK-END: AUTH_REGISTER_ENDPOINT
# BLOCK-END: AUTH_REGISTER_MODULE

__all__ = ["router"]
