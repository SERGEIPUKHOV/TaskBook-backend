from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_state import DailyState
from app.schemas.daily_state import DailyStateIn, DailyStateOut
from app.services.cache_service import invalidate_dashboard
from app.services.periods import month_bounds, validate_month, validate_month_day


async def get_month_states(db: AsyncSession, user_id: str, year: int, month: int) -> list[DailyStateOut]:
    try:
        validate_month(year, month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    start, end = month_bounds(year, month)
    result = await db.execute(
        select(DailyState)
        .where(
            DailyState.user_id == user_id,
            DailyState.date >= start,
            DailyState.date <= end,
        )
        .order_by(DailyState.date.asc()),
    )
    return [DailyStateOut.model_validate(item) for item in result.scalars().all()]


async def upsert_daily_state(
    db: AsyncSession,
    user_id: str,
    year: int,
    month: int,
    day: int,
    data: DailyStateIn,
) -> DailyStateOut:
    try:
        target_date = validate_month_day(year, month, day)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    result = await db.execute(
        select(DailyState).where(
            DailyState.user_id == user_id,
            DailyState.date == target_date,
        ),
    )
    record = result.scalar_one_or_none()

    if record is None:
        record = DailyState(
            user_id=user_id,
            date=target_date,
            health=data.health if data.health is not None else 0,
            productivity=data.productivity if data.productivity is not None else 0,
            anxiety=data.anxiety if data.anxiety is not None else 0,
        )
        db.add(record)
    else:
        if data.health is not None:
            record.health = data.health
        if data.productivity is not None:
            record.productivity = data.productivity
        if data.anxiety is not None:
            record.anxiety = data.anxiety
        db.add(record)

    await db.commit()
    await db.refresh(record)
    await invalidate_dashboard(user_id)
    return DailyStateOut.model_validate(record)


async def delete_daily_state(
    db: AsyncSession,
    user_id: str,
    year: int,
    month: int,
    day: int,
) -> None:
    try:
        target_date = validate_month_day(year, month, day)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

    result = await db.execute(
        select(DailyState).where(
            DailyState.user_id == user_id,
            DailyState.date == target_date,
        ),
    )
    record = result.scalar_one_or_none()
    if record is None:
        return

    await db.delete(record)
    await db.commit()
    await invalidate_dashboard(user_id)
