from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


# BLOCK-START: AUTH_DEPS_MODULE
# Description: Auth dependencies for access token extraction and current-user resolution.
def _extract_access_token(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    """
    function_contracts:
      _extract_access_token:
        description: "Returns access token from Bearer auth first, then from access cookie."
        preconditions:
          - "request: FastAPI request object"
          - "credentials: optional HTTPBearer credentials"
        postconditions:
          - "Returns token string when present"
          - "Returns None when both header and cookie are empty"
    """
    if credentials:
        return credentials.credentials

    return request.cookies.get(settings.ACCESS_COOKIE_NAME)


async def _resolve_user_from_token(token: str, db: AsyncSession) -> User | None:
    """
    function_contracts:
      _resolve_user_from_token:
        description: "Decodes access token and resolves active user from the database."
        preconditions:
          - "token: access JWT token string"
          - "db: active AsyncSession"
        postconditions:
          - "Returns active User when token is valid and user exists"
          - "Returns None when token is invalid, wrong type, missing subject, or user inactive"
    """
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
    except JWTError:
        return None

    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        return None

    return user


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    function_contracts:
      get_current_user:
        description: "Resolves authenticated user from Bearer header or browser auth cookie."
        preconditions:
          - "Access token exists in Authorization header or access cookie"
          - "db: active AsyncSession"
        postconditions:
          - "Returns active User from the database"
          - "Raises 401 when token is missing, invalid, expired, or user is inactive"
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить токен",
        headers={"WWW-Authenticate": "Bearer"},
    )

    token = _extract_access_token(request, credentials)
    if not token:
        raise credentials_exception

    user = await _resolve_user_from_token(token, db)
    if user is None:
        raise credentials_exception

    return user


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """
    function_contracts:
      get_optional_user:
        description: "Returns authenticated user when token is present, otherwise None."
        preconditions:
          - "request: FastAPI request object"
          - "db: active AsyncSession"
        postconditions:
          - "Returns User when token is valid"
          - "Returns None when no token is provided"
          - "Raises 401 when token is present but invalid"
    """
    token = _extract_access_token(request, credentials)
    if not token:
        return None

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить токен",
        headers={"WWW-Authenticate": "Bearer"},
    )
    user = await _resolve_user_from_token(token, db)
    if user is None:
        raise credentials_exception

    return user
# BLOCK-END: AUTH_DEPS_MODULE

__all__ = ["get_current_user", "get_optional_user"]
