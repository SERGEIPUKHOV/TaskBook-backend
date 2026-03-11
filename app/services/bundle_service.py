from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.month import MonthBundleOut
from app.schemas.week import WeekBundleOut
from app.services.day_entry_service import get_week_entry_summary
from app.services.habit_service import get_month_habit_grid, list_month_habits
from app.services.month_service import get_month_plan
from app.services.daily_state_service import get_month_states
from app.services.task_service import list_week_tasks
from app.services.week_service import get_or_create_week, serialize_week
from app.services.periods import week_bounds
from app.models.day_entry import Gratitude, KeyEvent


async def get_month_bundle(db: AsyncSession, user_id: str, year: int, month: int) -> MonthBundleOut:
    plan = await get_month_plan(db, user_id, year, month)
    states = await get_month_states(db, user_id, year, month)
    habits = await list_month_habits(db, user_id, year, month)
    grid = await get_month_habit_grid(db, user_id, year, month)
    return MonthBundleOut(plan=plan, states=states, habits=habits, grid=grid)


async def get_week_bundle(db: AsyncSession, user_id: str, year: int, week_number: int) -> WeekBundleOut:
    week = await get_or_create_week(db, user_id, year, week_number)
    tasks = await list_week_tasks(db, user_id, year, week_number)
    date_from, date_to = week_bounds(year, week_number)
    key_events = await get_week_entry_summary(db, user_id, date_from, date_to, KeyEvent)
    gratitudes = await get_week_entry_summary(db, user_id, date_from, date_to, Gratitude)

    day = date_from
    while day <= date_to:
        key_events.setdefault(day.isoformat(), None)
        gratitudes.setdefault(day.isoformat(), None)
        from datetime import timedelta
        day += timedelta(days=1)

    return WeekBundleOut(
        week=serialize_week(week),
        tasks=tasks,
        key_events=key_events,
        gratitudes=gratitudes,
    )
