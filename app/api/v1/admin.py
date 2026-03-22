from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets
import string
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.database import get_db
from app.core.redis import redis_client
from app.core.security import hash_password
from app.models.habit import Habit
from app.models.task import Task
from app.models.user import User
from app.schemas.admin import (
    AdminUserOut,
    AdminUsersPageOut,
    ImpersonateOut,
    PlatformStatsOut,
    ResetPasswordOut,
    SetActiveIn,
    SetEmailIn,
)
from app.schemas.common import Response

# BLOCK-START: ADMIN_API_MODULE
# Description: Administrative routes for user moderation, impersonation, and platform-level statistics.
router = APIRouter()
IMPERSONATE_KEY = "impersonate:{code}"
TEMP_PASSWORD_ALPHABET = string.ascii_letters + string.digits
TEMP_PASSWORD_LENGTH = 12


# BLOCK-START: ADMIN_HELPERS
# Description: Shared helper functions for admin response shaping and mutation guards.
def build_admin_user_out(user: User, tasks_count: int) -> AdminUserOut:
    return AdminUserOut(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        is_admin=user.is_admin,
        created_at=user.created_at,
        tasks_count=tasks_count,
    )


async def get_user_tasks_count(db: AsyncSession, user_id: str) -> int:
    return int((await db.scalar(select(func.count()).select_from(Task).where(Task.user_id == user_id))) or 0)


async def get_admin_target_user(db: AsyncSession, user_id: str) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


def ensure_admin_target_allowed(current_admin: User, user: User) -> None:
    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify your own account",
        )

    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify another admin account",
        )
# BLOCK-END: ADMIN_HELPERS


# BLOCK-START: ADMIN_USER_LIST_ENDPOINT
# Description: Lists users with pagination and optional search for the admin UI.
@router.get("/users", response_model=Response[AdminUsersPageOut])
async def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response[AdminUsersPageOut]:
    """
    function_contracts:
      list_users:
        description: "Returns paginated admin-facing user list with optional email search."
        preconditions:
          - "Authenticated requester is an admin"
          - "page >= 1 and 1 <= per_page <= 100"
        postconditions:
          - "Returns AdminUsersPageOut with items, total, page, and per_page"
          - "Filters by case-insensitive email search when provided"
    """
    normalized_search = search.strip() if search else None
    task_counts = (
        select(Task.user_id.label("user_id"), func.count(Task.id).label("tasks_count"))
        .group_by(Task.user_id)
        .subquery()
    )
    base_query = (
        select(User, func.coalesce(task_counts.c.tasks_count, 0).label("tasks_count"))
        .outerjoin(task_counts, task_counts.c.user_id == User.id)
    )
    count_query = select(func.count()).select_from(User)

    if normalized_search:
        pattern = f"%{normalized_search}%"
        base_query = base_query.where(User.email.ilike(pattern))
        count_query = count_query.where(User.email.ilike(pattern))

    users_result = await db.execute(
        base_query.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page),
    )
    total = int((await db.scalar(count_query)) or 0)
    users = [build_admin_user_out(user, int(tasks_count)) for user, tasks_count in users_result.all()]

    return Response(
        data=AdminUsersPageOut(
            items=users,
            total=total,
            page=page,
            per_page=per_page,
        ),
    )
# BLOCK-END: ADMIN_USER_LIST_ENDPOINT


# BLOCK-START: ADMIN_USER_STATUS_ENDPOINT
# Description: Changes active status for a non-admin target user.
@router.patch("/users/{user_id}/block", response_model=Response[AdminUserOut])
async def set_user_active(
    user_id: str,
    data: SetActiveIn,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> Response[AdminUserOut]:
    """
    function_contracts:
      set_user_active:
        description: "Updates active status for a target user while preventing self-edit and admin-to-admin mutation."
        preconditions:
          - "Authenticated requester is an admin"
          - "Target user exists and is not the current admin"
        postconditions:
          - "Persists new active status"
          - "Returns refreshed AdminUserOut"
          - "400 for forbidden self/admin mutations"
          - "404 when target user does not exist"
    """
    user = await get_admin_target_user(db, user_id)

    if user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own active status",
        )

    if user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change another admin account",
        )

    user.is_active = data.is_active
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return Response(data=build_admin_user_out(user, await get_user_tasks_count(db, user.id)))
# BLOCK-END: ADMIN_USER_STATUS_ENDPOINT


# BLOCK-START: ADMIN_USER_EMAIL_ENDPOINT
# Description: Changes a target user's email address with uniqueness enforcement.
@router.patch("/users/{user_id}/email", response_model=Response[AdminUserOut])
async def set_user_email(
    user_id: str,
    data: SetEmailIn,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> Response[AdminUserOut]:
    """
    function_contracts:
      set_user_email:
        description: "Normalizes and updates a target user's email when it is unique."
        preconditions:
          - "Authenticated requester is an admin"
          - "Target user exists and passes admin mutation guard"
        postconditions:
          - "Email is stored lower-cased and trimmed"
          - "Returns refreshed AdminUserOut"
          - "400 when email is already in use"
    """
    user = await get_admin_target_user(db, user_id)
    ensure_admin_target_allowed(current_admin, user)

    normalized_email = data.email.strip().lower()
    existing = await db.execute(select(User).where(User.email == normalized_email, User.id != user.id))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already in use")

    user.email = normalized_email
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return Response(data=build_admin_user_out(user, await get_user_tasks_count(db, user.id)))
# BLOCK-END: ADMIN_USER_EMAIL_ENDPOINT


# BLOCK-START: ADMIN_PASSWORD_RESET_ENDPOINT
# Description: Generates and applies a temporary password for a target user.
@router.post("/users/{user_id}/reset-password", response_model=Response[ResetPasswordOut])
async def reset_user_password(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> Response[ResetPasswordOut]:
    """
    function_contracts:
      reset_user_password:
        description: "Resets target user password to a generated temporary credential."
        preconditions:
          - "Authenticated requester is an admin"
          - "Target user exists and passes admin mutation guard"
        postconditions:
          - "Stored password hash is replaced"
          - "Reset token fields are cleared"
          - "Returns generated temporary password"
    """
    user = await get_admin_target_user(db, user_id)
    ensure_admin_target_allowed(current_admin, user)

    temp_password = "".join(secrets.choice(TEMP_PASSWORD_ALPHABET) for _ in range(TEMP_PASSWORD_LENGTH))
    user.hashed_password = hash_password(temp_password)
    user.reset_token = None
    user.reset_token_expires_at = None
    db.add(user)
    await db.commit()

    return Response(data=ResetPasswordOut(temp_password=temp_password))
# BLOCK-END: ADMIN_PASSWORD_RESET_ENDPOINT


# BLOCK-START: ADMIN_IMPERSONATION_ENDPOINT
# Description: Creates a short-lived impersonation code for a target user.
@router.post("/users/{user_id}/impersonate", response_model=Response[ImpersonateOut])
async def impersonate_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: User = Depends(require_admin),
) -> Response[ImpersonateOut]:
    """
    function_contracts:
      impersonate_user:
        description: "Creates a one-time impersonation code stored in Redis for the chosen user."
        preconditions:
          - "Authenticated requester is an admin"
          - "Target user exists and passes admin mutation guard"
        postconditions:
          - "Returns ImpersonateOut with generated code"
          - "Stores code in Redis with 120-second TTL"
    """
    user = await get_admin_target_user(db, user_id)
    ensure_admin_target_allowed(current_admin, user)

    code = str(uuid4())
    await redis_client.set(IMPERSONATE_KEY.format(code=code), user.id, ex=120)
    return Response(data=ImpersonateOut(code=code))
# BLOCK-END: ADMIN_IMPERSONATION_ENDPOINT


# BLOCK-START: ADMIN_STATS_ENDPOINT
# Description: Returns platform-level counts for users, recent activity, tasks, and habits.
@router.get("/stats", response_model=Response[PlatformStatsOut])
async def get_stats(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> Response[PlatformStatsOut]:
    """
    function_contracts:
      get_stats:
        description: "Returns high-level platform statistics for admin dashboard widgets."
        preconditions:
          - "Authenticated requester is an admin"
        postconditions:
          - "Returns counts for total users, active_7d, total tasks, and total habits"
    """
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    total_users = int((await db.scalar(select(func.count()).select_from(User))) or 0)
    active_7d = int(
        (
            await db.scalar(
                select(func.count()).select_from(User).where(User.last_login >= seven_days_ago),
            )
        )
        or 0
    )
    total_tasks = int((await db.scalar(select(func.count()).select_from(Task))) or 0)
    total_habits = int((await db.scalar(select(func.count()).select_from(Habit))) or 0)

    return Response(
        data=PlatformStatsOut(
            total_users=total_users,
            active_7d=active_7d,
            total_tasks=total_tasks,
            total_habits=total_habits,
        ),
    )
# BLOCK-END: ADMIN_STATS_ENDPOINT
# BLOCK-END: ADMIN_API_MODULE
