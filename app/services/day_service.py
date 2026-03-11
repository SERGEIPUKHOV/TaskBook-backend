from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.daily_state import DailyState
from app.models.habit import HabitLog
from app.schemas.day import DayBundleOut, DayHabitOut, DayReflectionOut, DayStateSummaryOut, DayTaskOut
from app.schemas.task import TaskOut
from app.services.day_entry_service import list_gratitudes, list_key_events
from app.services.habit_service import list_month_habits
from app.services.task_service import list_week_tasks

FINAL_TASK_STATUSES = {"done", "failed"}
VISIBLE_TASK_STATUSES = {"done", "moved", "failed"}


def _week_day_keys(target_date: date) -> list[str]:
    week_start = target_date - timedelta(days=target_date.isoweekday() - 1)
    return [(week_start + timedelta(days=index)).isoformat() for index in range(7)]


def _task_status_trail(task: TaskOut, day_keys: list[str]) -> list[str]:
    start_index = min(max((task.start_day or 1) - 1, 0), 6)
    trail: list[str] = []

    for day_key in day_keys[start_index:]:
        status = task.statuses.get(day_key)
        if status not in VISIBLE_TASK_STATUSES:
            if trail:
                break
            continue
        trail.append(status)

    return trail


def _resolve_day_task(task: TaskOut, target_date: date) -> DayTaskOut | None:
    day_keys = _week_day_keys(target_date)
    day_index = target_date.isoweekday() - 1
    start_index = min(max((task.start_day or 1) - 1, 0), 6)

    if day_index < start_index:
        return None

    trail = _task_status_trail(task, day_keys)
    relative_index = day_index - start_index

    if relative_index < len(trail):
        status = trail[relative_index]
    else:
        previous_status = trail[relative_index - 1] if relative_index > 0 and relative_index - 1 < len(trail) else None
        is_start_day = relative_index == 0
        is_next_open_day = relative_index == len(trail) and (is_start_day or previous_status == "moved")

        if is_next_open_day:
            status = "planned"
        elif trail and trail[-1] in FINAL_TASK_STATUSES and day_index > start_index + len(trail) - 1:
            status = trail[-1]
        else:
            return None

    return DayTaskOut(
        id=task.id,
        title=task.title,
        status=status,  # type: ignore[arg-type]
        time_planned=task.time_planned,
        time_actual=task.time_actual,
        is_priority=task.is_priority,
    )


async def get_day_tasks(db: AsyncSession, user_id: str, target_date: date) -> list[DayTaskOut]:
    iso = target_date.isocalendar()
    tasks = await list_week_tasks(db, user_id, iso.year, iso.week)
    result: list[DayTaskOut] = []

    for task in tasks:
        record = _resolve_day_task(task, target_date)
        if record is not None:
            result.append(record)

    return result


async def get_day_habits(db: AsyncSession, user_id: str, target_date: date) -> list[DayHabitOut]:
    habits = await list_month_habits(db, user_id, target_date.year, target_date.month)
    habit_ids = [habit.id for habit in habits]
    completed_ids: set[str] = set()

    if habit_ids:
        result = await db.execute(
            select(HabitLog.habit_id).where(
                HabitLog.habit_id.in_(habit_ids),
                HabitLog.date == target_date,
            ),
        )
        completed_ids = set(result.scalars().all())

    return [
        DayHabitOut(
            id=habit.id,
            title=habit.name,
            completed=habit.id in completed_ids,
        )
        for habit in habits
    ]


async def get_daily_state(db: AsyncSession, user_id: str, target_date: date) -> DayStateSummaryOut | None:
    result = await db.execute(
        select(DailyState).where(
            DailyState.user_id == user_id,
            DailyState.date == target_date,
        ),
    )
    record = result.scalar_one_or_none()

    if record is None:
        return None

    return DayStateSummaryOut(
        health=record.health,
        productivity=record.productivity,
        anxiety=record.anxiety,
    )


async def get_day_reflection(db: AsyncSession, user_id: str, target_date: date) -> DayReflectionOut:
    key_events = await list_key_events(db, user_id, target_date)
    gratitudes = await list_gratitudes(db, user_id, target_date)

    return DayReflectionOut(
        key_event=key_events[0].content if key_events else None,
        gratitude=gratitudes[0].content if gratitudes else None,
    )


async def get_day_bundle(db: AsyncSession, user_id: str, target_date: date) -> DayBundleOut:
    iso = target_date.isocalendar()
    tasks = await get_day_tasks(db, user_id, target_date)
    habits = await get_day_habits(db, user_id, target_date)
    daily_state = await get_daily_state(db, user_id, target_date)
    reflection = await get_day_reflection(db, user_id, target_date)

    return DayBundleOut(
        date=target_date,
        day_of_week=iso.weekday,
        iso_week=iso.week,
        tasks=tasks,
        habits=habits,
        daily_state=daily_state,
        key_event=reflection.key_event,
        gratitude=reflection.gratitude,
    )
