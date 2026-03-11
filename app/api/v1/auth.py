from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response as FastAPIResponse, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.auth_cookies import clear_auth_cookies, set_auth_cookies
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import redis_client
from app.models.user import User
from app.schemas.auth import (
    AuthResponseOut,
    ChangePasswordIn,
    DeleteAccountIn,
    ExchangeImpersonateIn,
    ForgotPasswordIn,
    LoginIn,
    LogoutIn,
    RefreshTokenIn,
    RegisterIn,
    ResetPasswordIn,
    ResetTokenValidationOut,
)
from app.schemas.common import OperationStatus, Response
from app.services.auth_service import (
    change_password,
    delete_account,
    forgot_password,
    issue_auth_tokens,
    login_user,
    logout_user,
    refresh_session,
    register_user,
    reset_password,
    validate_reset_token,
)

router = APIRouter()
IMPERSONATE_KEY = "impersonate:{code}"


def _resolve_refresh_token(request: Request, payload: RefreshTokenIn | LogoutIn | None) -> str | None:
    body_token = payload.refresh_token if payload and payload.refresh_token else None
    return body_token or request.cookies.get(settings.REFRESH_COOKIE_NAME)


@router.post("/register", response_model=Response[AuthResponseOut])
async def register(
    data: RegisterIn,
    response: FastAPIResponse,
    db: AsyncSession = Depends(get_db),
) -> Response[AuthResponseOut]:
    auth = await register_user(db, data.email, data.password)
    set_auth_cookies(response, auth.access_token, auth.refresh_token)
    return Response(data=auth)


@router.post("/login", response_model=Response[AuthResponseOut])
async def login(
    data: LoginIn,
    response: FastAPIResponse,
    db: AsyncSession = Depends(get_db),
) -> Response[AuthResponseOut]:
    auth = await login_user(db, data.email, data.password)
    set_auth_cookies(response, auth.access_token, auth.refresh_token)
    return Response(data=auth)


@router.post("/refresh", response_model=Response[AuthResponseOut])
async def refresh(
    request: Request,
    response: FastAPIResponse,
    data: RefreshTokenIn | None = None,
    db: AsyncSession = Depends(get_db),
) -> Response[AuthResponseOut]:
    refresh_token = _resolve_refresh_token(request, data)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    auth = await refresh_session(db, refresh_token)
    set_auth_cookies(response, auth.access_token, auth.refresh_token)
    return Response(data=auth)


@router.post("/logout", response_model=Response[OperationStatus])
async def logout(request: Request, response: FastAPIResponse, data: LogoutIn | None = None) -> Response[OperationStatus]:
    refresh_token = _resolve_refresh_token(request, data)
    if refresh_token:
        await logout_user(refresh_token)
    clear_auth_cookies(response)
    return Response(data=OperationStatus())


@router.post("/exchange-impersonate")
async def exchange_impersonate(
    data: ExchangeImpersonateIn,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    key = IMPERSONATE_KEY.format(code=data.code)
    user_id = await redis_client.get(key)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired impersonation code")

    await redis_client.delete(key)

    result = await db.execute(select(User).where(User.id == str(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found or inactive")

    auth = await issue_auth_tokens(user)
    response = JSONResponse(content={})
    set_auth_cookies(response, auth.access_token, auth.refresh_token)
    return response


@router.post("/forgot-password", response_model=Response[OperationStatus])
async def forgot(data: ForgotPasswordIn, db: AsyncSession = Depends(get_db)) -> Response[OperationStatus]:
    await forgot_password(db, data.email)
    return Response(data=OperationStatus())


@router.get("/reset-password/validate", response_model=Response[ResetTokenValidationOut])
async def validate_reset(token: str, db: AsyncSession = Depends(get_db)) -> Response[ResetTokenValidationOut]:
    return Response(data=ResetTokenValidationOut(valid=await validate_reset_token(db, token)))


@router.post("/reset-password", response_model=Response[OperationStatus])
async def reset(data: ResetPasswordIn, db: AsyncSession = Depends(get_db)) -> Response[OperationStatus]:
    await reset_password(db, data.token, data.new_password)
    return Response(data=OperationStatus())


@router.post("/change-password", response_model=Response[OperationStatus])
async def change(
    data: ChangePasswordIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[OperationStatus]:
    await change_password(db, current_user, data.current_password, data.new_password)
    return Response(data=OperationStatus())


@router.delete("/account", response_model=Response[OperationStatus])
async def remove_account(
    data: DeleteAccountIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[OperationStatus]:
    await delete_account(db, current_user, data.password)
    return Response(data=OperationStatus())
