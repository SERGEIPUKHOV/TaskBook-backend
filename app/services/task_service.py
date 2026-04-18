from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_event import CalendarEvent
from app.models.planner_link import PlannerLink
from app.models.task import Task, TaskDayStatus
from app.models.week import Week
from app.schemas.habit import LinkedEventTimeOut
from app.schemas.task import ReorderIn, TaskDayStatusOut, TaskOut, TaskPatch
from app.services.cache_service import invalidate_dashboard
from app.services.periods import week_bounds
from app.services.week_service import get_or_create_week

_TASK_LINK_MODES = ["import_copy", "export_copy"]


def _utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _serialize_task(
    task: Task,
    statuses: dict[str, str],
    linked_event_time: LinkedEventTimeOut | None = None,
    calendar_connection_id: str | None = None,
) -> TaskOut:
    return TaskOut(
        id=task.id,
        title=task.title,
        time_planned=task.time_planned,
        time_actual=task.time_actual,
        is_priority=task.is_priority,
        order=task.order,
        start_day=task.start_day,
        calendar_export_enabled=task.calendar_export_enabled,
        calendar_export_bucket=task.calendar_export_bucket,
        carried_from_task_id=task.carried_from_task_id,
        statuses=statuses,
        linked_event_time=linked_event_time,
        calendar_connection_id=calendar_connection_id,
    )


async def _fetch_linked_event_times_for_tasks(
    db: AsyncSession,
    user_id: str,
    task_ids: list[str],
) -> dict[str, tuple[LinkedEventTimeOut | None, str | None]]:
    """Batch: task_id → (LinkedEventTimeOut | None, connection_id | None).

    Searches both import_copy and export_copy PlannerLinks.
    """
    if not task_ids:
        return {}

    links_result = await db.execute(
        select(PlannerLink).where(
            PlannerLink.user_id == user_id,
            PlannerLink.target_kind == "task",
            PlannerLink.target_id.in_(task_ids),
            PlannerLink.source_kind == "calendar_event",
            PlannerLink.link_mode.in_(_TASK_LINK_MODES),
        ),
    )
    links = links_result.scalars().all()
    if not links:
        return {}

    ref_to_task: dict[tuple[str, str], tuple[str, str]] = {}
    for link in links:
        conn_id, sep, ext_id = link.source_ref.partition(":")
        if sep and conn_id and ext_id:
            ref_to_task[(conn_id, ext_id)] = (str(link.target_id), conn_id)

    if not ref_to_task:
        return {}

    event_filters = [
        and_(CalendarEvent.connection_id == conn_id, CalendarEvent.external_event_id == ext_id)
        for conn_id, ext_id in ref_to_task
    ]
    events_result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.status != "cancelled",
            or_(*event_filters),
        ).order_by(CalendarEvent.starts_at.asc(), CalendarEvent.created_at.asc()),
    )

    result: dict[str, tuple[LinkedEventTimeOut | None, str | None]] = {}
    for event in events_result.scalars().all():
        task_conn = ref_to_task.get((str(event.connection_id), event.external_event_id))
        if not task_conn:
            continue
        task_id, conn_id = task_conn
        if task_id in result:
            continue
        time_out: LinkedEventTimeOut | None = None
        if not event.is_all_day and event.starts_at is not None and event.ends_at is not None:
            time_out = LinkedEventTimeOut(starts_at=_utc_iso(event.starts_at), ends_at=_utc_iso(event.ends_at))
        result[task_id] = (time_out, conn_id)

    return result


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


def _clamp_start_day(start_day: int | None) -> int:
    return min(max(start_day or 1, 1), 7)


def _has_terminal_status(task_statuses: dict[str, str]) -> bool:
    return any(status in {"done", "failed"} for status in task_statuses.values())


def _next_open_day(task: Task, week: Week, task_statuses: dict[str, str]) -> int | None:
    if _has_terminal_status(task_statuses):
        return None

    for day_num in range(_clamp_start_day(task.start_day), 8):
        status = task_statuses.get(date.fromisocalendar(week.year, week.week_number, day_num).isoformat())
        if status == "moved":
            continue
        if status in {"done", "failed"}:
            return None
        return day_num

    return 8


async def _upsert_moved_status(
    db: AsyncSession,
    task: Task,
    target_date: date,
    task_statuses: dict[str, str],
) -> bool:
    target_key = target_date.isoformat()
    if task_statuses.get(target_key) == "moved":
        return False

    result = await db.execute(
        select(TaskDayStatus).where(TaskDayStatus.task_id == task.id, TaskDayStatus.date == target_date),
    )
    record = result.scalar_one_or_none()
    if record is None:
        record = TaskDayStatus(task_id=task.id, date=target_date, status="moved")
    else:
        record.status = "moved"

    db.add(record)
    task_statuses[target_key] = "moved"
    return True


async def _ensure_carry_task(
    db: AsyncSession,
    user_id: str,
    canonical_id: str,
    source_task: Task,
    next_year: int,
    next_week_number: int,
) -> tuple[Task, Week, bool]:
    next_week = await get_or_create_week(db, user_id, next_year, next_week_number)
    next_task_result = await db.execute(
        select(Task)
        .where(
            Task.user_id == user_id,
            Task.week_id == next_week.id,
            Task.carried_from_task_id == canonical_id,
        )
        .order_by(Task.created_at.desc())
        .limit(1),
    )
    next_task = next_task_result.scalar_one_or_none()
    if next_task is not None:
        return next_task, next_week, False

    next_task = Task(
        user_id=user_id,
        week_id=next_week.id,
        title=source_task.title,
        time_planned=source_task.time_planned,
        time_actual=0,
        is_priority=source_task.is_priority,
        order=0,
        start_day=1,
        carried_from_task_id=canonical_id,
        calendar_export_enabled=False,
        calendar_export_bucket=None,
    )
    db.add(next_task)
    await db.flush()
    return next_task, next_week, True


async def _auto_carry_overdue_tasks(db: AsyncSession, user_id: str) -> None:
    today = date.today()
    rows_result = await db.execute(
        select(Task, Week)
        .join(Week, Week.id == Task.week_id)
        .where(Task.user_id == user_id)
        .order_by(Week.year.asc(), Week.week_number.asc(), Task.created_at.asc()),
    )
    rows = rows_result.all()
    if not rows:
        return

    task_ids = [task.id for task, _week in rows]
    statuses_by_task = await _task_status_map(db, task_ids)
    chain_map: dict[str, list[tuple[Task, Week]]] = {}
    task_refs: dict[tuple[str, int, int], tuple[Task, Week]] = {}

    for task, week in rows:
        canonical_id = task.carried_from_task_id or task.id
        chain_map.setdefault(canonical_id, []).append((task, week))
        task_refs[(canonical_id, week.year, week.week_number)] = (task, week)

    changed = False

    for canonical_id, entries in chain_map.items():
        entries.sort(key=lambda item: (item[1].year, item[1].week_number, item[0].created_at))
        entry_index = 0

        while entry_index < len(entries):
            task, week = entries[entry_index]
            week_start, week_end = week_bounds(week.year, week.week_number)
            if week_start > today:
                break

            task_statuses = statuses_by_task.setdefault(task.id, {})
            if _has_terminal_status(task_statuses):
                break

            open_day = _next_open_day(task, week, task_statuses)
            if open_day is None:
                break

            target_day = 7 if week_end < today else today.isoweekday() - 1
            if open_day <= target_day:
                for day_num in range(open_day, target_day + 1):
                    day_date = date.fromisocalendar(week.year, week.week_number, day_num)
                    changed = await _upsert_moved_status(db, task, day_date, task_statuses) or changed

            if week_end >= today:
                break

            next_week_date = week_end + timedelta(days=1)
            next_year, next_week_number, _ = next_week_date.isocalendar()
            next_ref = (canonical_id, next_year, next_week_number)
            next_entry = task_refs.get(next_ref)
            if next_entry is None:
                if changed:
                    await db.flush()
                next_task, next_week, created = await _ensure_carry_task(
                    db,
                    user_id,
                    canonical_id,
                    task,
                    next_year,
                    next_week_number,
                )
                next_entry = (next_task, next_week)
                entries.append(next_entry)
                task_refs[next_ref] = next_entry
                statuses_by_task.setdefault(next_task.id, {})
                changed = created or changed

            entry_index += 1

    if changed:
        await db.commit()
        await invalidate_dashboard(user_id)


async def list_week_tasks(db: AsyncSession, user_id: str, year: int, week_number: int) -> list[TaskOut]:
    week = await get_or_create_week(db, user_id, year, week_number)
    await _auto_carry_overdue_tasks(db, user_id)
    tasks_result = await db.execute(
        select(Task)
        .where(Task.user_id == user_id, Task.week_id == week.id)
        .order_by(Task.order.asc(), Task.created_at.asc()),
    )
    tasks = tasks_result.scalars().all()
    task_ids = [task.id for task in tasks]
    statuses = await _task_status_map(db, task_ids)
    linked_times = await _fetch_linked_event_times_for_tasks(db, user_id, task_ids)
    return [
        _serialize_task(
            task,
            statuses.get(task.id, {}),
            linked_event_time=linked_times.get(task.id, (None, None))[0],
            calendar_connection_id=linked_times.get(task.id, (None, None))[1],
        )
        for task in tasks
    ]


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
    calendar_export_enabled: bool = False,
    calendar_export_bucket: str | None = None,
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
        calendar_export_enabled=calendar_export_enabled,
        calendar_export_bucket=calendar_export_bucket,
        carried_from_task_id=None,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    await invalidate_dashboard(user_id)
    return _serialize_task(task, {})


async def update_task_event_time(
    db: AsyncSession,
    user_id: str,
    task_id: str,
    starts_hhmm: str,
    ends_hhmm: str,
) -> LinkedEventTimeOut | None:
    """Update time on the linked CalendarEvent for a task (DB side).

    Returns new LinkedEventTimeOut, or None if no link found.
    Works for both import_copy and export_copy links.
    All-day events are promoted to timed using the event's UTC date.
    """
    link_result = await db.execute(
        select(PlannerLink).where(
            PlannerLink.user_id == user_id,
            PlannerLink.target_kind == "task",
            PlannerLink.target_id == task_id,
            PlannerLink.source_kind == "calendar_event",
            PlannerLink.link_mode.in_(_TASK_LINK_MODES),
        ),
    )
    link = link_result.scalars().first()
    if link is None:
        return None

    conn_id, sep, ext_id = link.source_ref.partition(":")
    if not sep or not conn_id or not ext_id:
        return None

    event_result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.connection_id == conn_id,
            CalendarEvent.external_event_id == ext_id,
            CalendarEvent.user_id == user_id,
            CalendarEvent.status != "cancelled",
        ),
    )
    event = event_result.scalar_one_or_none()
    if event is None or event.starts_at is None or event.ends_at is None:
        return None

    start_h, start_m = (int(v) for v in starts_hhmm.split(":"))
    end_h, end_m = (int(v) for v in ends_hhmm.split(":"))

    if event.is_all_day:
        event_date = event.starts_at.date()
        new_start = datetime(event_date.year, event_date.month, event_date.day, start_h, start_m, tzinfo=timezone.utc)
        new_end = datetime(event_date.year, event_date.month, event_date.day, end_h, end_m, tzinfo=timezone.utc)
        event.is_all_day = False
    else:
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        tz_obj = timezone.utc
        if event.source_timezone:
            try:
                tz_obj = ZoneInfo(event.source_timezone)
            except ZoneInfoNotFoundError:
                pass
        base_start = event.starts_at if event.starts_at.tzinfo else event.starts_at.replace(tzinfo=timezone.utc)
        base_end = event.ends_at if event.ends_at.tzinfo else event.ends_at.replace(tzinfo=timezone.utc)
        new_start = base_start.astimezone(tz_obj).replace(hour=start_h, minute=start_m, second=0, microsecond=0).astimezone(timezone.utc)
        new_end = base_end.astimezone(tz_obj).replace(hour=end_h, minute=end_m, second=0, microsecond=0).astimezone(timezone.utc)

    event.starts_at = new_start
    event.ends_at = new_end
    await db.commit()
    await db.refresh(event)
    return LinkedEventTimeOut(starts_at=_utc_iso(event.starts_at), ends_at=_utc_iso(event.ends_at))


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
    await db.execute(
        delete(PlannerLink).where(
            PlannerLink.user_id == user_id,
            PlannerLink.target_kind == "task",
            PlannerLink.target_id == task.id,
        ),
    )
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
