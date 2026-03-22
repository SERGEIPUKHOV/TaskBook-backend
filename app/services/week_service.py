from __future__ import annotations

from datetime import date
import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task, TaskDayStatus
from app.models.week import Week
from app.schemas.week import WeekOut, WeekPatch
from app.services.cache_service import invalidate_dashboard
from app.services.periods import previous_week_reference, validate_week, week_bounds

logger = logging.getLogger(__name__)


# BLOCK-START: WEEK_SERVICE_MODULE
# Description: Week service with ISO-week validation, carry-over synchronization, serialization, and update flows.
# BLOCK-START: WEEK_VALIDATION_HELPER
# Description: Validates ISO week reference and translates validation failures to HTTP 422.
def _ensure_valid_week(year: int, week_number: int) -> None:
    """
    function_contracts:
      _ensure_valid_week:
        description: "Validates ISO week input and raises HTTPException for invalid year/week pairs."
        preconditions:
          - "year: integer ISO year"
          - "week_number: integer ISO week number"
        postconditions:
          - "Returns None for valid ISO week references"
          - "Raises HTTP 422 when week reference is invalid"
    """
    try:
        validate_week(year, week_number)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
# BLOCK-END: WEEK_VALIDATION_HELPER


# BLOCK-START: WEEK_SERIALIZATION_HELPER
# Description: Serializes Week ORM record into API schema with computed ISO date bounds.
def serialize_week(record: Week) -> WeekOut:
    """
    function_contracts:
      serialize_week:
        description: "Converts Week ORM model into WeekOut with computed ISO week bounds."
        preconditions:
          - "record.year and record.week_number describe a valid ISO week"
        postconditions:
          - "Returns WeekOut with date_from and date_to"
          - "Raises HTTP 422 when stored week reference is invalid"
    """
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
# BLOCK-END: WEEK_SERIALIZATION_HELPER


# BLOCK-START: WEEK_CARRY_OVER_SYNC
# Description: Syncs tasks moved from the previous Sunday into the current week and removes stale carry-over tasks.
async def _sync_carry_over_tasks(db: AsyncSession, user_id: str, week: Week) -> bool:
    """
    function_contracts:
      _sync_carry_over_tasks:
        description: "Copies eligible moved tasks from the previous week and removes stale carry-over entries."
        preconditions:
          - "week: persisted Week record or flushed Week instance"
          - "user_id: current user identifier"
        postconditions:
          - "Returns True when carry-over tasks were added or removed"
          - "Returns False when there is nothing to sync"
    """
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
# BLOCK-END: WEEK_CARRY_OVER_SYNC


# BLOCK-START: WEEK_GET_OR_CREATE_FLOW
# Description: Loads an existing week or creates it on first access, including carry-over synchronization and LDD logs.
async def get_or_create_week(db: AsyncSession, user_id: str, year: int, week_number: int) -> Week:
    """
    function_contracts:
      get_or_create_week:
        description: "Returns an existing week or creates a new one, synchronizing carry-over tasks from the previous ISO week."
        preconditions:
          - "db: active AsyncSession"
          - "user_id: current user identifier"
          - "year/week_number: valid ISO week reference"
        postconditions:
          - "Returns persisted Week instance"
          - "Creates week when it does not exist"
          - "Invalidates dashboard cache when carry-over sync changes visible task state"
    """
    logger.info("[WEEK][GET_OR_CREATE][START] user_id=%s year=%s week=%s", user_id, year, week_number)
    try:
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
                logger.info("[WEEK][GET_OR_CREATE][SYNCED] user_id=%s week_id=%s", user_id, record.id)
            else:
                logger.debug("[WEEK][GET_OR_CREATE][FOUND] user_id=%s week_id=%s", user_id, record.id)
            return record

        record = Week(user_id=user_id, year=year, week_number=week_number, focus="", reward="")
        db.add(record)
        await db.flush()
        added = await _sync_carry_over_tasks(db, user_id, record)
        await db.commit()
        await db.refresh(record)
        if added:
            await invalidate_dashboard(user_id)
        logger.info(
            "[WEEK][GET_OR_CREATE][CREATED] user_id=%s week_id=%s carry_over=%s",
            user_id,
            record.id,
            added,
        )
        return record
    except Exception:
        logger.exception("[WEEK][GET_OR_CREATE][FAILED] user_id=%s year=%s week=%s", user_id, year, week_number)
        raise
# BLOCK-END: WEEK_GET_OR_CREATE_FLOW


# BLOCK-START: WEEK_UPDATE_FLOW
# Description: Applies editable patch fields to a week and invalidates dashboard cache.
async def update_week(
    db: AsyncSession,
    user_id: str,
    year: int,
    week_number: int,
    patch: WeekPatch,
) -> WeekOut:
    """
    function_contracts:
      update_week:
        description: "Updates editable week reflection fields and returns serialized week data."
        preconditions:
          - "patch.focus and patch.reward are optional string fields"
          - "year/week_number identify an ISO week for the current user"
        postconditions:
          - "Week record exists after the call"
          - "Updated fields are persisted"
          - "Dashboard cache is invalidated"
    """
    logger.info("[WEEK][UPDATE][START] user_id=%s year=%s week=%s", user_id, year, week_number)
    try:
        record = await get_or_create_week(db, user_id, year, week_number)
        if patch.focus is not None:
            record.focus = patch.focus
        if patch.reward is not None:
            record.reward = patch.reward
        db.add(record)
        await db.commit()
        await db.refresh(record)
        await invalidate_dashboard(user_id)
        logger.info("[WEEK][UPDATE][SUCCESS] user_id=%s week_id=%s", user_id, record.id)
        return serialize_week(record)
    except Exception:
        logger.exception("[WEEK][UPDATE][FAILED] user_id=%s year=%s week=%s", user_id, year, week_number)
        raise
# BLOCK-END: WEEK_UPDATE_FLOW


# BLOCK-START: WEEK_LOOKUP_HELPER
# Description: Retrieves one week owned by the current user or raises HTTP 404.
async def get_week_for_user(db: AsyncSession, user_id: str, task_or_week_id: str, by_week_id: bool = True) -> Week:
    """
    function_contracts:
      get_week_for_user:
        description: "Fetches one Week record scoped to the current user."
        preconditions:
          - "task_or_week_id: persisted week identifier"
          - "user_id: current user identifier"
        postconditions:
          - "Returns Week when found"
          - "Raises HTTP 404 when week is missing"
    """
    field = Week.id if by_week_id else Week.id
    result = await db.execute(select(Week).where(field == task_or_week_id, Week.user_id == user_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Week not found")
    return record
# BLOCK-END: WEEK_LOOKUP_HELPER
# BLOCK-END: WEEK_SERVICE_MODULE
