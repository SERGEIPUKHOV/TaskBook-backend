from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordIn,
    DeleteAccountIn,
    ForgotPasswordIn,
    ResetPasswordIn,
    ResetTokenValidationOut,
)
from app.schemas.common import OperationStatus, Response
from app.services.auth_service import (
    change_password,
    delete_account,
    forgot_password,
    reset_password,
    validate_reset_token,
)

from .deps import get_current_user

# BLOCK-START: AUTH_PASSWORD_MODULE
# Description: Password recovery, password change, and account deletion endpoints.
router = APIRouter()


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
# BLOCK-END: AUTH_PASSWORD_MODULE

__all__ = ["router"]
