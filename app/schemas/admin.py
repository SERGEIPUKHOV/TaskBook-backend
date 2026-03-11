from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class AdminUserOut(BaseModel):
    id: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    tasks_count: int

    model_config = ConfigDict(from_attributes=True)


class AdminUsersPageOut(BaseModel):
    items: list[AdminUserOut]
    total: int
    page: int
    per_page: int


class SetActiveIn(BaseModel):
    is_active: bool


class SetEmailIn(BaseModel):
    email: EmailStr


class ResetPasswordOut(BaseModel):
    temp_password: str


class ImpersonateOut(BaseModel):
    code: str


class PlatformStatsOut(BaseModel):
    total_users: int
    active_7d: int
    total_tasks: int
    total_habits: int
