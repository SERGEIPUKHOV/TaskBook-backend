from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskDayStatus
from app.models.week import Week
from app.schemas.week import WeekOut, WeekPatch
from app.services.cache_service import invalidate_dashboard
from app.services.periods import previous_week_reference, validate_week, week_bounds


def _ensure_valid_week(year: int, week_number: int) -> None:
    try:
        validate_week(year, week_number)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc


def serialize_week(record: Week) -> WeekOut:
    _ensure_valid_week(record.year, record.week_number)
    date_from, date_to = week_bounds(record.year, record.week_number)
    return WeekOut(
        id=record.id,
        year=record.year,
        week_number=record.week_number,
        focus=record.focus,
        reward=record.reward,
        date_from=date_from,
        date_to=date_to,
    )


async def _sync_carry_over_tasks(db: AsyncSession, user_id: str, week: Week) -> bool:
    previous_year, previous_week_number = previous_week_reference(week.year, week.week_number)
    previous_week_result = await db.execute(
        select(Week).where(
            Week.user_id == user_id,
            Week.year == previous_year,
            Week.week_number == previous_week_number,
        ),
    )
    previous_week = previous_week_result.scalar_one_or_none()
    if previous_week is None:
        return False

    tasks_result = await db.execute(
        select(Task).where(Task.user_id == user_id, Task.week_id == previous_week.id).order_by(Task.order.asc()),
    )
    tasks = tasks_result.scalars().all()
    if not tasks:
        return False

    sunday_date = date.fromisocalendar(previous_year, previous_week_number, 7)
    task_ids = [task.id for task in tasks]

    moved_on_sunday_result = await db.execute(
        select(TaskDayStatus.task_id).where(
            TaskDayStatus.task_id.in_(task_ids),
            TaskDayStatus.date == sunday_date,
            TaskDayStatus.status == "moved",
        ),
    )
    moved_task_ids = set(moved_on_sunday_result.scalars().all())
    if not moved_task_ids:
        current_carried_result = await db.execute(
            select(Task)
            .where(
                Task.user_id == user_id,
                Task.week_id == week.id,
                Task.carried_from_task_id.is_not(None),
            )
            .order_by(Task.order.asc(), Task.created_at.asc()),
        )
        current_carried_tasks = current_carried_result.scalars().all()
        if not current_carried_tasks:
            return False

        for task in current_carried_tasks:
            await db.delete(task)

        return True

    valid_canonical_ids = {
        task.carried_from_task_id or task.id
        for task in tasks
        if task.id in moved_task_ids
    }

    current_carried_result = await db.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.week_id == week.id,
            Task.carried_from_task_id.is_not(None),
        )
        .order_by(Task.order.asc(), Task.created_at.asc()),
    )
    current_carried_tasks = current_carried_result.scalars().all()
    already_carried_ids: set[str] = set()
    changed = False

    for carried_task in current_carried_tasks:
        canonical_id = carried_task.carried_from_task_id
        if canonical_id is None:
            continue

        if canonical_id not in valid_canonical_ids or canonical_id in already_carried_ids:
            await db.delete(carried_task)
            changed = True
            continue

        already_carried_ids.add(canonical_id)

    if changed:
        await db.flush()

    max_order_result = await db.execute(
        select(Task.order)
        .where(Task.user_id == user_id, Task.week_id == week.id)
        .order_by(Task.order.desc())
        .limit(1),
    )
    max_order = max_order_result.scalar_one_or_none()
    next_order = (max_order + 1) if max_order is not None else 0

    for task in tasks:
        if task.id not in moved_task_ids:
            continue

        canonical_id = task.carried_from_task_id or task.id
        if canonical_id in already_carried_ids:
            continue

        db.add(
            Task(
                user_id=user_id,
                week_id=week.id,
                title=task.title,
                time_planned=task.time_planned,
                time_actual=0,
                is_priority=task.is_priority,
                order=next_order,
                start_day=1,
                carried_from_task_id=canonical_id,
            ),
        )
        already_carried_ids.add(canonical_id)
        next_order += 1
        changed = True

    return changed


async def get_or_create_week(db: AsyncSession, user_id: str, year: int, week_number: int) -> Week:
    _ensure_valid_week(year, week_number)
    result = await db.execute(
        select(Week).where(
            Week.user_id == user_id,
            Week.year == year,
            Week.week_number == week_number,
        ),
    )
    record = result.scalar_one_or_none()
    if record is not None:
        added = await _sync_carry_over_tasks(db, user_id, record)
        if added:
            await db.commit()
            await db.refresh(record)
            await invalidate_dashboard(user_id)
        return record

    record = Week(user_id=user_id, year=year, week_number=week_number, focus="", reward="")
    db.add(record)
    await db.flush()
    added = await _sync_carry_over_tasks(db, user_id, record)
    await db.commit()
    await db.refresh(record)
    if added:
        await invalidate_dashboard(user_id)
    return record


async def update_week(
    db: AsyncSession,
    user_id: str,
    year: int,
    week_number: int,
    patch: WeekPatch,
) -> WeekOut:
    record = await get_or_create_week(db, user_id, year, week_number)
    if patch.focus is not None:
        record.focus = patch.focus
    if patch.reward is not None:
        record.reward = patch.reward
    db.add(record)
    await db.commit()
    await db.refresh(record)
    await invalidate_dashboard(user_id)
    return serialize_week(record)


async def get_week_for_user(db: AsyncSession, user_id: str, task_or_week_id: str, by_week_id: bool = True) -> Week:
    field = Week.id if by_week_id else Week.id
    result = await db.execute(select(Week).where(field == task_or_week_id, Week.user_id == user_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Week not found")
    return record
