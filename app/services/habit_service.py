from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.habit import Habit, HabitLog
from app.schemas.habit import HabitGridOut, HabitOut
from app.services.cache_service import invalidate_dashboard
from app.services.periods import days_in_month, month_key, validate_month

DEFAULT_HABIT_NAMES = [
    "Сон до 23:30",
    "Вода 2л",
    "20 минут чтения",
    "Тренировка / прогулка",
    "Английский",
]


async def seed_default_habits_for_user(db: AsyncSession, user_id: str) -> None:
    existing = await db.execute(select(Habit.id).where(Habit.user_id == user_id).limit(1))
    if existing.scalar_one_or_none():
        return

    for index, name in enumerate(DEFAULT_HABIT_NAMES):
        db.add(
            Habit(
                user_id=user_id,
                name=name,
                order=index,
                source="default",
                starts_at_month_key=None,
                ends_before_month_key=None,
            ),
        )


async def _active_habit_query(user_id: str, target_month_key: str):
    return (
        select(Habit)
        .where(
            Habit.user_id == user_id,
            or_(Habit.starts_at_month_key.is_(None), Habit.starts_at_month_key <= target_month_key),
            or_(Habit.ends_before_month_key.is_(None), Habit.ends_before_month_key > target_month_key),
        )
        .order_by(Habit.order.asc(), Habit.created_at.asc())
    )


def _normalize_habit_name(name: str) -> str:
    normalized = name.strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Habit name is required")
    return normalized


def _validated_month_key(year: int, month: int) -> str:
    try:
        validate_month(year, month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    return month_key(year, month)


async def list_month_habits(db: AsyncSession, user_id: str, year: int, month: int) -> list[HabitOut]:
    target_month_key = _validated_month_key(year, month)
    result = await db.execute(await _active_habit_query(user_id, target_month_key))
    return [HabitOut.model_validate(item) for item in result.scalars().all()]


async def get_month_habit_grid(db: AsyncSession, user_id: str, year: int, month: int) -> HabitGridOut:
    target_month_key = _validated_month_key(year, month)
    habits_result = await db.execute(await _active_habit_query(user_id, target_month_key))
    habits = habits_result.scalars().all()
    habit_ids = [habit.id for habit in habits]
    logs: dict[str, list[int]] = {habit.id: [] for habit in habits}

    if habit_ids:
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month(year, month))
        logs_result = await db.execute(
            select(HabitLog)
            .where(
                HabitLog.habit_id.in_(habit_ids),
                HabitLog.date >= month_start,
                HabitLog.date <= month_end,
            )
            .order_by(HabitLog.date.asc()),
        )
        for item in logs_result.scalars().all():
            logs.setdefault(item.habit_id, []).append(item.date.day)

    return HabitGridOut(
        habits=[HabitOut.model_validate(item) for item in habits],
        logs=logs,
        days_in_month=days_in_month(year, month),
    )


async def create_habit(db: AsyncSession, user_id: str, year: int, month: int, name: str) -> HabitOut:
    target_month_key = _validated_month_key(year, month)
    active_habits_result = await db.execute(await _active_habit_query(user_id, target_month_key))
    active_habits = active_habits_result.scalars().all()
    normalized_name = _normalize_habit_name(name)
    normalized = normalized_name.lower()

    if any(habit.name.strip().lower() == normalized for habit in active_habits):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Habit already exists")

    max_order_result = await db.execute(select(func.max(Habit.order)).where(Habit.user_id == user_id))
    max_order = max_order_result.scalar_one_or_none() or 0
    record = Habit(
        user_id=user_id,
        name=normalized_name,
        order=max_order + 1,
        source="user",
        starts_at_month_key=target_month_key,
        ends_before_month_key=None,
    )
    db.add(record)
    await db.commit()
    await db.refresh(record)
    await invalidate_dashboard(user_id)
    return HabitOut.model_validate(record)


async def get_habit_for_user(db: AsyncSession, user_id: str, habit_id: str) -> Habit:
    result = await db.execute(select(Habit).where(Habit.id == habit_id, Habit.user_id == user_id))
    habit = result.scalar_one_or_none()
    if habit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Habit not found")
    return habit


async def update_habit(db: AsyncSession, user_id: str, habit_id: str, name: str) -> HabitOut:
    habit = await get_habit_for_user(db, user_id, habit_id)
    normalized_name = _normalize_habit_name(name)
    normalized = normalized_name.lower()
    active_habits_result = await db.execute(
        await _active_habit_query(user_id, habit.starts_at_month_key or month_key(habit.created_at.year, habit.created_at.month)),
    )
    active_habits = active_habits_result.scalars().all()

    if any(item.id != habit.id and item.name.strip().lower() == normalized for item in active_habits):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Habit already exists")

    habit.name = normalized_name
    db.add(habit)
    await db.commit()
    await db.refresh(habit)
    await invalidate_dashboard(user_id)
    return HabitOut.model_validate(habit)


async def delete_habit_for_month(db: AsyncSession, user_id: str, habit_id: str, year: int, month: int) -> None:
    habit = await get_habit_for_user(db, user_id, habit_id)
    habit.ends_before_month_key = _validated_month_key(year, month)
    db.add(habit)
    await db.commit()
    await invalidate_dashboard(user_id)


async def log_habit_completion(db: AsyncSession, user_id: str, habit_id: str, target_date: date) -> None:
    await get_habit_for_user(db, user_id, habit_id)
    result = await db.execute(
        select(HabitLog).where(HabitLog.habit_id == habit_id, HabitLog.date == target_date),
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        db.add(HabitLog(habit_id=habit_id, date=target_date))
        await db.commit()
        await invalidate_dashboard(user_id)


async def unlog_habit_completion(db: AsyncSession, user_id: str, habit_id: str, target_date: date) -> None:
    await get_habit_for_user(db, user_id, habit_id)
    result = await db.execute(
        select(HabitLog).where(HabitLog.habit_id == habit_id, HabitLog.date == target_date),
    )
    existing = result.scalar_one_or_none()
    if existing is None:
        return

    await db.delete(existing)
    await db.commit()
    await invalidate_dashboard(user_id)
