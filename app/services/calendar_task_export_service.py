from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
import secrets

from fastapi import HTTPException, status
from icalendar import Calendar, Event
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.task import Task
from app.models.user import User
from app.models.week import Week
from app.schemas.calendar import CalendarTaskFeedLinkOut
from app.schemas.task import TaskCalendarExportBucket
from app.services.periods import week_bounds

# BLOCK-START: CALENDAR_TASK_EXPORT_SERVICE_MODULE
# Description: Tokenized ICS export for opt-in planner tasks, including feed-link discovery and bucket-filtered calendar serialization.
TASK_EXPORT_BUCKETS: tuple[TaskCalendarExportBucket, ...] = ("default", "work", "personal", "family")


# BLOCK-START: CALENDAR_TASK_EXPORT_HELPERS
# Description: Helpers for token provisioning, public feed path generation, and ICS event assembly.
def build_task_feed_path(token: str, bucket: TaskCalendarExportBucket) -> str:
    return f"{settings.API_V1_PREFIX}/calendar/feeds/tasks/{token}.ics?bucket={bucket}"


def task_bucket_label(bucket: str) -> str:
    labels = {
        "default": "default",
        "family": "family",
        "personal": "personal",
        "work": "work",
    }
    return labels[bucket]


def task_date_for_feed(week_year: int, week_number: int, start_day: int) -> date:
    week_start, _ = week_bounds(week_year, week_number)
    return week_start + timedelta(days=max(0, start_day - 1))


def build_task_feed_event(task: Task, week: Week) -> Event:
    day = task_date_for_feed(week.year, week.week_number, task.start_day or 1)
    stamp = task.updated_at or task.created_at or datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    else:
        stamp = stamp.astimezone(UTC)

    event = Event()
    event.add("uid", f"taskbook-task-{task.id}@taskbook.local")
    event.add("summary", task.title.strip() or "Без названия")
    event.add("dtstart", day)
    event.add("dtend", day + timedelta(days=1))
    event.add("dtstamp", stamp)
    event.add("status", "CONFIRMED")
    event.add("transp", "TRANSPARENT")
    event.add(
        "description",
        f"TaskBook task - week {week.week_number} / {week.year}"
        + (f" - bucket {task_bucket_label(task.calendar_export_bucket)}" if task.calendar_export_bucket else ""),
    )
    return event


async def ensure_task_feed_token(db: AsyncSession, user_id: str) -> str:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.task_feed_token:
        return user.task_feed_token

    while True:
        token = secrets.token_urlsafe(24)
        existing = await db.execute(select(User.id).where(User.task_feed_token == token))
        if existing.scalar_one_or_none() is None:
            user.task_feed_token = token
            db.add(user)
            await db.commit()
            await db.refresh(user)
            return token


def build_task_calendar(task_rows: list[tuple[Task, Week]], bucket: TaskCalendarExportBucket | None) -> bytes:
    calendar = Calendar()
    calendar.add("prodid", "-//TaskBook//Task Export//EN")
    calendar.add("version", "2.0")
    calendar.add("X-WR-CALNAME", "TaskBook Tasks" if bucket is None else f"TaskBook Tasks - {task_bucket_label(bucket)}")
    calendar.add("X-WR-TIMEZONE", "UTC")

    for task, week in task_rows:
        calendar.add_component(build_task_feed_event(task, week))

    return calendar.to_ical()
# BLOCK-END: CALENDAR_TASK_EXPORT_HELPERS


# BLOCK-START: CALENDAR_TASK_EXPORT_QUERY_FLOW
# Description: Database-backed discovery for bucket counts, token ownership lookup, and bucket-filtered task feed rows.
async def list_task_export_feed_links(db: AsyncSession, user_id: str) -> list[CalendarTaskFeedLinkOut]:
    token = await ensure_task_feed_token(db, user_id)

    counts_result = await db.execute(
        select(Task.calendar_export_bucket, func.count(Task.id))
        .where(
            Task.user_id == user_id,
            Task.calendar_export_enabled.is_(True),
            Task.start_day.is_not(None),
            Task.calendar_export_bucket.is_not(None),
        )
        .group_by(Task.calendar_export_bucket),
    )
    counts = {bucket: count for bucket, count in counts_result.all() if bucket}

    return [
        CalendarTaskFeedLinkOut(
            bucket=bucket,
            feed_path=build_task_feed_path(token, bucket),
            task_count=counts.get(bucket, 0),
        )
        for bucket in TASK_EXPORT_BUCKETS
    ]


async def get_user_id_by_task_feed_token(db: AsyncSession, token: str) -> str:
    result = await db.execute(select(User.id).where(User.task_feed_token == token))
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task feed not found")
    return user_id


async def list_task_feed_rows(
    db: AsyncSession,
    *,
    token: str,
    bucket: TaskCalendarExportBucket | None,
) -> tuple[str, list[tuple[Task, Week]]]:
    user_id = await get_user_id_by_task_feed_token(db, token)

    query = (
        select(Task, Week)
        .join(Week, Week.id == Task.week_id)
        .where(
            Task.user_id == user_id,
            Task.calendar_export_enabled.is_(True),
            Task.start_day.is_not(None),
            Task.calendar_export_bucket.is_not(None),
        )
        .order_by(Week.year.asc(), Week.week_number.asc(), Task.start_day.asc(), Task.order.asc(), Task.created_at.asc())
    )
    if bucket is not None:
        query = query.where(Task.calendar_export_bucket == bucket)

    result = await db.execute(query)
    return user_id, list(result.all())
# BLOCK-END: CALENDAR_TASK_EXPORT_QUERY_FLOW


# BLOCK-START: CALENDAR_TASK_EXPORT_RENDER_FLOW
# Description: Public render function that converts token-scoped task rows into ICS bytes.
async def render_task_feed_ics(
    db: AsyncSession,
    *,
    token: str,
    bucket: TaskCalendarExportBucket | None,
) -> bytes:
    _, task_rows = await list_task_feed_rows(db, token=token, bucket=bucket)
    return build_task_calendar(task_rows, bucket)
# BLOCK-END: CALENDAR_TASK_EXPORT_RENDER_FLOW
# BLOCK-END: CALENDAR_TASK_EXPORT_SERVICE_MODULE
