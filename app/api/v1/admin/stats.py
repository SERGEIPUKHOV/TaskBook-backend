from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.admin.deps import require_admin
from app.core.database import get_db
from app.models.habit import Habit
from app.models.task import Task
from app.models.user import User
from app.schemas.admin import PlatformStatsOut
from app.schemas.common import Response

# BLOCK-START: ADMIN_STATS_MODULE
# Description: Admin endpoints for platform-level usage statistics.
router = APIRouter()


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
# BLOCK-END: ADMIN_STATS_MODULE
