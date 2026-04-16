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
from app.services.supervision_service import get_active_grant_for_view, get_subject_owner_for_view

bearer_scheme = HTTPBearer(auto_error=False)
SECTION_BY_PATH_PREFIX: tuple[tuple[str, str], ...] = (
    ("/api/v1/dashboard", "dashboard"),
    ("/api/v1/months/", "month"),
    ("/api/v1/weeks/", "week"),
    ("/api/v1/days/", "day"),
    ("/api/v1/calendar/", "calendar"),
    ("/api/v1/habits/months/", "month"),
)


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


def _resolve_requested_section(path: str) -> str | None:
    for prefix, section in SECTION_BY_PATH_PREFIX:
        if path.startswith(prefix):
            return section
    return None


async def get_subject_user(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> User:
    view_as_owner_id = getattr(request.state, "view_as_user_id", None)
    if not view_as_owner_id:
        return current_user

    requested_section = _resolve_requested_section(request.url.path)
    if requested_section is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещён")

    grant = await get_active_grant_for_view(
        db,
        owner_id=view_as_owner_id,
        supervisor_id=current_user.id,
    )
    if grant is None or requested_section not in set(grant.sections or []):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещён")

    return await get_subject_owner_for_view(
        db,
        owner_id=view_as_owner_id,
        supervisor_id=current_user.id,
    )
# BLOCK-END: AUTH_DEPS_MODULE

__all__ = ["get_current_user", "get_optional_user", "get_subject_user"]
