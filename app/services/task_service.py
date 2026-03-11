from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskDayStatus
from app.models.week import Week
from app.schemas.task import ReorderIn, TaskDayStatusOut, TaskOut, TaskPatch
from app.services.cache_service import invalidate_dashboard
from app.services.periods import week_bounds
from app.services.week_service import get_or_create_week


def _serialize_task(task: Task, statuses: dict[str, str]) -> TaskOut:
    return TaskOut(
        id=task.id,
        title=task.title,
        time_planned=task.time_planned,
        time_actual=task.time_actual,
        is_priority=task.is_priority,
        order=task.order,
        start_day=task.start_day,
        carried_from_task_id=task.carried_from_task_id,
        statuses=statuses,
    )


async def _task_status_map(db: AsyncSession, task_ids: list[str]) -> dict[str, dict[str, str]]:
    if not task_ids:
        return {}
    result = await db.execute(
        select(TaskDayStatus)
        .where(TaskDayStatus.task_id.in_(task_ids))
        .order_by(TaskDayStatus.date.asc()),
    )
    statuses: dict[str, dict[str, str]] = {task_id: {} for task_id in task_ids}
    for item in result.scalars().all():
        statuses.setdefault(item.task_id, {})[item.date.isoformat()] = item.status
    return statuses


async def list_week_tasks(db: AsyncSession, user_id: str, year: int, week_number: int) -> list[TaskOut]:
    week = await get_or_create_week(db, user_id, year, week_number)
    tasks_result = await db.execute(
        select(Task)
        .where(Task.user_id == user_id, Task.week_id == week.id)
        .order_by(Task.order.asc(), Task.created_at.asc()),
    )
    tasks = tasks_result.scalars().all()
    statuses = await _task_status_map(db, [task.id for task in tasks])
    return [_serialize_task(task, statuses.get(task.id, {})) for task in tasks]


async def create_task(
    db: AsyncSession,
    user_id: str,
    year: int,
    week_number: int,
    title: str = "",
    time_planned: int | None = None,
    time_actual: int | None = None,
    is_priority: bool = False,
    start_day: int | None = 1,
) -> TaskOut:
    week = await get_or_create_week(db, user_id, year, week_number)
    tasks_result = await db.execute(
        select(Task).where(Task.user_id == user_id, Task.week_id == week.id).order_by(Task.order.desc()).limit(1),
    )
    last_task = tasks_result.scalar_one_or_none()
    next_order = (last_task.order + 1) if last_task else 0
    task = Task(
        user_id=user_id,
        week_id=week.id,
        title=title,
        time_planned=time_planned,
        time_actual=time_actual,
        is_priority=is_priority,
        order=next_order,
        start_day=start_day or 1,
        carried_from_task_id=None,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await invalidate_dashboard(user_id)
    return _serialize_task(task, {})


async def get_task_for_user(db: AsyncSession, user_id: str, task_id: str) -> Task:
    result = await db.execute(select(Task).where(Task.id == task_id, Task.user_id == user_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


async def update_task(db: AsyncSession, user_id: str, task_id: str, patch: TaskPatch) -> TaskOut:
    task = await get_task_for_user(db, user_id, task_id)
    payload = patch.model_dump(exclude_unset=True)
    for field, value in payload.items():
        setattr(task, field, value)
    db.add(task)
    await db.commit()
    await db.refresh(task)
    statuses = await _task_status_map(db, [task.id])
    await invalidate_dashboard(user_id)
    return _serialize_task(task, statuses.get(task.id, {}))


async def delete_task(db: AsyncSession, user_id: str, task_id: str) -> None:
    task = await get_task_for_user(db, user_id, task_id)
    await db.delete(task)
    await db.commit()
    await invalidate_dashboard(user_id)


async def set_task_status(
    db: AsyncSession,
    user_id: str,
    task_id: str,
    target_date: date,
    status_value: str,
) -> TaskDayStatusOut:
    task = await get_task_for_user(db, user_id, task_id)
    week_record_result = await db.execute(select(Week).where(Week.id == task.week_id))
    week_record = week_record_result.scalar_one()
    date_from, date_to = week_bounds(week_record.year, week_record.week_number)
    if target_date < date_from or target_date > date_to:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Date is outside task week")

    result = await db.execute(
        select(TaskDayStatus).where(TaskDayStatus.task_id == task_id, TaskDayStatus.date == target_date),
    )
    record = result.scalar_one_or_none()

    if status_value == "planned":
        if record is not None:
            await db.delete(record)
            await db.commit()
            await invalidate_dashboard(user_id)
        return TaskDayStatusOut(task_id=task_id, date=target_date, status="planned")

    if record is None:
        record = TaskDayStatus(task_id=task_id, date=target_date, status=status_value)
    else:
        record.status = status_value
    db.add(record)
    await db.commit()
    await db.refresh(record)
    await invalidate_dashboard(user_id)
    return TaskDayStatusOut(task_id=task_id, date=target_date, status=record.status)


async def delete_task_status(db: AsyncSession, user_id: str, task_id: str, target_date: date) -> None:
    await get_task_for_user(db, user_id, task_id)
    result = await db.execute(
        select(TaskDayStatus).where(TaskDayStatus.task_id == task_id, TaskDayStatus.date == target_date),
    )
    record = result.scalar_one_or_none()
    if record is None:
        return
    await db.delete(record)
    await db.commit()
    await invalidate_dashboard(user_id)


async def reorder_tasks(db: AsyncSession, user_id: str, year: int, week_number: int, payload: ReorderIn) -> list[TaskOut]:
    week = await get_or_create_week(db, user_id, year, week_number)
    tasks_result = await db.execute(
        select(Task).where(Task.user_id == user_id, Task.week_id == week.id).order_by(Task.order.asc()),
    )
    tasks = tasks_result.scalars().all()
    by_id = {task.id: task for task in tasks}

    if set(by_id) != set(payload.task_ids):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Task ids mismatch")

    for index, task_id in enumerate(payload.task_ids):
        by_id[task_id].order = index
        db.add(by_id[task_id])

    await db.commit()
    statuses = await _task_status_map(db, list(by_id))
    await invalidate_dashboard(user_id)
    return [_serialize_task(by_id[task_id], statuses.get(task_id, {})) for task_id in payload.task_ids]
