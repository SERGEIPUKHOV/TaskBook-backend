from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field


class AuthUserOut(BaseModel):
    id: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field(return_type=Literal["admin", "user"])
    @property
    def role(self) -> Literal["admin", "user"]:
        return "admin" if self.is_admin else "user"


class AuthResponseOut(BaseModel):
    access_token: str
    refresh_token: str
    user: AuthUserOut


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=255)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=255)


class RefreshTokenIn(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=1)


class LogoutIn(BaseModel):
    refresh_token: str | None = Field(default=None, min_length=1)


class ExchangeImpersonateIn(BaseModel):
    code: str = Field(min_length=1)


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=255)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=255)
    new_password: str = Field(min_length=8, max_length=255)


class DeleteAccountIn(BaseModel):
    password: str = Field(min_length=1, max_length=255)


class ResetTokenValidationOut(BaseModel):
    valid: bool
