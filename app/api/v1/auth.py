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

# BLOCK-START: AUTH_API_MODULE
# Description: Authentication API routes for registration, sessions, password recovery, and impersonation exchange.
router = APIRouter()
IMPERSONATE_KEY = "impersonate:{code}"


# BLOCK-START: AUTH_REFRESH_TOKEN_RESOLUTION
# Description: Resolves a refresh token from request payload or browser cookie for refresh/logout flows.
def _resolve_refresh_token(request: Request, payload: RefreshTokenIn | LogoutIn | None) -> str | None:
    """
    function_contracts:
      _resolve_refresh_token:
        description: "Extracts refresh token from JSON payload first, then falls back to httpOnly cookie."
        preconditions:
          - "request: FastAPI Request with optional auth cookies"
          - "payload: optional RefreshTokenIn or LogoutIn"
        postconditions:
          - "Returns refresh token string when available"
          - "Returns None when token is missing in both payload and cookie"
    """
    body_token = payload.refresh_token if payload and payload.refresh_token else None
    return body_token or request.cookies.get(settings.REFRESH_COOKIE_NAME)
# BLOCK-END: AUTH_REFRESH_TOKEN_RESOLUTION


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


# BLOCK-START: AUTH_LOGIN_ENDPOINT
# Description: Authenticates user credentials and rotates browser auth cookies.
@router.post("/login", response_model=Response[AuthResponseOut])
async def login(
    data: LoginIn,
    response: FastAPIResponse,
    db: AsyncSession = Depends(get_db),
) -> Response[AuthResponseOut]:
    """
    function_contracts:
      login:
        description: "Authenticates by email and password, then returns fresh auth tokens."
        preconditions:
          - "data.email: existing user email"
          - "data.password: plaintext password for verification"
        postconditions:
          - "Returns AuthResponseOut for the authenticated user"
          - "Sets access and refresh cookies on success"
          - "401 for invalid credentials, 403 for inactive accounts"
    """
    auth = await login_user(db, data.email, data.password)
    set_auth_cookies(response, auth.access_token, auth.refresh_token)
    return Response(data=auth)
# BLOCK-END: AUTH_LOGIN_ENDPOINT


# BLOCK-START: AUTH_REFRESH_ENDPOINT
# Description: Issues a fresh access/refresh token pair using refresh token from body or cookie.
@router.post("/refresh", response_model=Response[AuthResponseOut])
async def refresh(
    request: Request,
    response: FastAPIResponse,
    data: RefreshTokenIn | None = None,
    db: AsyncSession = Depends(get_db),
) -> Response[AuthResponseOut]:
    """
    function_contracts:
      refresh:
        description: "Refreshes the authenticated browser session using a valid refresh token."
        preconditions:
          - "Refresh token is present in request body or cookie"
          - "Refresh token belongs to an active user and is not revoked"
        postconditions:
          - "Returns a fresh AuthResponseOut"
          - "Rotates browser auth cookies"
          - "401 when refresh token is missing or invalid"
    """
    refresh_token = _resolve_refresh_token(request, data)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    auth = await refresh_session(db, refresh_token)
    set_auth_cookies(response, auth.access_token, auth.refresh_token)
    return Response(data=auth)
# BLOCK-END: AUTH_REFRESH_ENDPOINT


# BLOCK-START: AUTH_LOGOUT_ENDPOINT
# Description: Revokes refresh token when present and clears all browser auth cookies.
@router.post("/logout", response_model=Response[OperationStatus])
async def logout(request: Request, response: FastAPIResponse, data: LogoutIn | None = None) -> Response[OperationStatus]:
    """
    function_contracts:
      logout:
        description: "Revokes the active refresh token when present and clears auth cookies."
        preconditions:
          - "request may contain refresh token in payload or cookie"
        postconditions:
          - "Refresh token is revoked when available"
          - "Browser auth cookies are always cleared"
          - "Returns OperationStatus regardless of token presence"
    """
    refresh_token = _resolve_refresh_token(request, data)
    if refresh_token:
        await logout_user(refresh_token)
    clear_auth_cookies(response)
    return Response(data=OperationStatus())
# BLOCK-END: AUTH_LOGOUT_ENDPOINT


# BLOCK-START: AUTH_IMPERSONATION_EXCHANGE_ENDPOINT
# Description: Exchanges a short-lived admin impersonation code for browser auth cookies.
@router.post("/exchange-impersonate")
async def exchange_impersonate(
    data: ExchangeImpersonateIn,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """
    function_contracts:
      exchange_impersonate:
        description: "Consumes one-time impersonation code, resolves target user, and issues browser auth cookies."
        preconditions:
          - "data.code: valid impersonation code stored in Redis"
          - "Target user exists and is active"
        postconditions:
          - "Deletes impersonation code from Redis"
          - "Returns empty JSONResponse with auth cookies set"
          - "400 when code is invalid, expired, or user is inactive"
    """
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
# BLOCK-END: AUTH_IMPERSONATION_EXCHANGE_ENDPOINT


# BLOCK-START: AUTH_PASSWORD_RESET_FLOW
# Description: Handles password recovery flow: forgot-password, token validation, and password reset.
@router.post("/forgot-password", response_model=Response[OperationStatus])
async def forgot(data: ForgotPasswordIn, db: AsyncSession = Depends(get_db)) -> Response[OperationStatus]:
    """
    function_contracts:
      forgot:
        description: "Initiates password reset flow for an email address without leaking account existence."
        preconditions:
          - "data.email: valid email syntax"
        postconditions:
          - "Stores reset token for existing user when account exists"
          - "Returns OperationStatus in all cases"
    """
    await forgot_password(db, data.email)
    return Response(data=OperationStatus())


@router.get("/reset-password/validate", response_model=Response[ResetTokenValidationOut])
async def validate_reset(token: str, db: AsyncSession = Depends(get_db)) -> Response[ResetTokenValidationOut]:
    """
    function_contracts:
      validate_reset:
        description: "Checks whether password reset token is still valid."
        preconditions:
          - "token: reset token string from email flow"
        postconditions:
          - "Returns ResetTokenValidationOut(valid=bool)"
    """
    return Response(data=ResetTokenValidationOut(valid=await validate_reset_token(db, token)))


@router.post("/reset-password", response_model=Response[OperationStatus])
async def reset(data: ResetPasswordIn, db: AsyncSession = Depends(get_db)) -> Response[OperationStatus]:
    """
    function_contracts:
      reset:
        description: "Resets account password using a valid reset token."
        preconditions:
          - "data.token: valid reset token"
          - "data.new_password: passes schema validation"
        postconditions:
          - "Updates stored password hash"
          - "Clears reset token fields"
          - "400 when token is invalid or expired"
    """
    await reset_password(db, data.token, data.new_password)
    return Response(data=OperationStatus())
# BLOCK-END: AUTH_PASSWORD_RESET_FLOW


# BLOCK-START: AUTH_ACCOUNT_MANAGEMENT
# Description: Handles password change for current user and irreversible account deletion.
@router.post("/change-password", response_model=Response[OperationStatus])
async def change(
    data: ChangePasswordIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[OperationStatus]:
    """
    function_contracts:
      change:
        description: "Changes password for the currently authenticated user."
        preconditions:
          - "current_user: authenticated active user"
          - "data.current_password: current valid password"
          - "data.new_password: replacement password"
        postconditions:
          - "Stored password hash is updated"
          - "Reset token fields are cleared"
          - "401 when current password is invalid"
    """
    await change_password(db, current_user, data.current_password, data.new_password)
    return Response(data=OperationStatus())


@router.delete("/account", response_model=Response[OperationStatus])
async def remove_account(
    data: DeleteAccountIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[OperationStatus]:
    """
    function_contracts:
      remove_account:
        description: "Deletes the currently authenticated account after password confirmation."
        preconditions:
          - "current_user: authenticated user"
          - "data.password: current valid password"
        postconditions:
          - "User row is deleted from the database"
          - "401 when password verification fails"
    """
    await delete_account(db, current_user, data.password)
    return Response(data=OperationStatus())
# BLOCK-END: AUTH_ACCOUNT_MANAGEMENT
# BLOCK-END: AUTH_API_MODULE
