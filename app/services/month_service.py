from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.month_plan import MonthPlan
from app.schemas.month import MonthPlanIn, MonthPlanOut
from app.services.cache_service import invalidate_dashboard
from app.services.periods import validate_month


def _ensure_valid_month(year: int, month: int) -> None:
    try:
        validate_month(year, month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


async def get_month_plan(db: AsyncSession, user_id: str, year: int, month: int) -> MonthPlanOut | None:
    _ensure_valid_month(year, month)
    result = await db.execute(
        select(MonthPlan).where(
            MonthPlan.user_id == user_id,
            MonthPlan.year == year,
            MonthPlan.month == month,
        ),
    )
    record = result.scalar_one_or_none()
    if record is None:
        return None
    return MonthPlanOut.model_validate(record)


async def upsert_month_plan(
    db: AsyncSession,
    user_id: str,
    year: int,
    month: int,
    data: MonthPlanIn,
) -> MonthPlanOut:
    _ensure_valid_month(year, month)
    result = await db.execute(
        select(MonthPlan).where(
            MonthPlan.user_id == user_id,
            MonthPlan.year == year,
            MonthPlan.month == month,
        ),
    )
    record = result.scalar_one_or_none()

    if record is None:
        record = MonthPlan(user_id=user_id, year=year, month=month)
        db.add(record)

    payload = data.model_dump()
    record.main_goal = payload["main_goal"]
    record.focuses = payload["focuses"]
    record.innovations = payload["innovations"]
    record.rejections = payload["rejections"]
    record.other = payload["other"]
    db.add(record)
    await db.commit()
    await db.refresh(record)
    await invalidate_dashboard(user_id)
    return MonthPlanOut.model_validate(record)
