from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, auth, dashboard, days, habits, months, tasks, users, weeks

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(months.router, prefix="/months", tags=["months"])
api_router.include_router(habits.router, tags=["habits"])
api_router.include_router(weeks.router, prefix="/weeks", tags=["weeks"])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
api_router.include_router(days.router, prefix="/days", tags=["days"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])

__all__ = ["api_router"]
