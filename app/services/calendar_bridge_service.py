from __future__ import annotations

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_event import CalendarEvent
from app.models.habit import Habit
from app.models.planner_link import PlannerLink
from app.models.task import Task
from app.models.week import Week
from app.schemas.calendar import CalendarEventImportIn, CalendarEventImportOut, PlannerLinkOut
from app.services.habit_service import create_habit
from app.services.periods import month_key, validate_month, validate_week
from app.services.task_service import create_task

# BLOCK-START: CALENDAR_BRIDGE_SERVICE_MODULE
# Description: Calendar-to-planner import orchestration, type suggestion helpers, and planner-link resolution for idempotent event imports.
CALENDAR_EVENT_SOURCE_KIND = "calendar_event"
IMPORT_COPY_LINK_MODE = "import_copy"


# BLOCK-START: CALENDAR_BRIDGE_HELPERS
# Description: Pure helpers for event classification, title normalization, and planner-link serialization.
def build_calendar_event_source_ref(connection_id: str, external_event_id: str) -> str:
    return f"{connection_id}:{external_event_id}"


def is_calendar_event_recurring(event: CalendarEvent) -> bool:
    raw_payload = event.raw_payload or {}
    return bool(
        raw_payload.get("recurringEventId")
        or raw_payload.get("recurrence")
        or raw_payload.get("rrule")
    )


def get_calendar_event_suggested_target_type(event: CalendarEvent) -> str:
    return "habit" if is_calendar_event_recurring(event) else "task"


def is_calendar_event_multi_day(event: CalendarEvent) -> bool:
    day_span = (event.ends_at.date() - event.starts_at.date()).days
    if event.is_all_day:
        return day_span > 1
    return event.starts_at.date() != event.ends_at.date()


def normalize_import_title(value: str | None, *, max_length: int) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Title is required")
    if len(normalized) > max_length:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Title is too long")
    return normalized


def planner_link_to_schema(link: PlannerLink, *, open_path: str) -> PlannerLinkOut:
    return PlannerLinkOut(
        id=link.id,
        link_mode="import_copy",
        open_path=open_path,
        target_id=link.target_id,
        target_kind=link.target_kind,
    )


def month_key_to_open_path(month_key_value: str | None, fallback_date: date) -> str:
    if month_key_value and len(month_key_value) == 7:
        year_text, month_text = month_key_value.split("-")
        return f"/month/{int(year_text)}/{int(month_text)}"

    return f"/month/{fallback_date.year}/{fallback_date.month}"


async def find_active_habit_by_name(
    db: AsyncSession,
    user_id: str,
    month_key_value: str,
    name: str,
) -> Habit | None:
    result = await db.execute(
        select(Habit)
        .where(
            Habit.user_id == user_id,
            or_(Habit.starts_at_month_key.is_(None), Habit.starts_at_month_key <= month_key_value),
            or_(Habit.ends_before_month_key.is_(None), Habit.ends_before_month_key > month_key_value),
        )
        .order_by(Habit.order.asc(), Habit.created_at.asc()),
    )
    normalized_name = name.strip().lower()
    return next(
        (habit for habit in result.scalars().all() if habit.name.strip().lower() == normalized_name),
        None,
    )


async def get_planner_link_for_habit(db: AsyncSession, user_id: str, habit_id: str) -> PlannerLink | None:
    result = await db.execute(
        select(PlannerLink).where(
            PlannerLink.user_id == user_id,
            PlannerLink.target_kind == "habit",
            PlannerLink.target_id == habit_id,
            PlannerLink.source_kind == CALENDAR_EVENT_SOURCE_KIND,
            PlannerLink.link_mode == IMPORT_COPY_LINK_MODE,
        ),
    )
    return result.scalar_one_or_none()
# BLOCK-END: CALENDAR_BRIDGE_HELPERS


# BLOCK-START: CALENDAR_BRIDGE_LOOKUP_FLOW
# Description: User-scoped lookup and resolution flow for calendar events and existing planner links.
async def get_calendar_event_for_user(db: AsyncSession, user_id: str, event_id: str) -> CalendarEvent:
    result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.id == event_id,
            CalendarEvent.user_id == user_id,
        ),
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar event not found")
    return event


async def get_planner_link_by_source_ref(db: AsyncSession, user_id: str, source_ref: str) -> PlannerLink | None:
    result = await db.execute(
        select(PlannerLink).where(
            PlannerLink.user_id == user_id,
            PlannerLink.source_kind == CALENDAR_EVENT_SOURCE_KIND,
            PlannerLink.source_ref == source_ref,
            PlannerLink.link_mode == IMPORT_COPY_LINK_MODE,
        ),
    )
    return result.scalar_one_or_none()


async def resolve_planner_link(db: AsyncSession, user_id: str, link: PlannerLink) -> PlannerLinkOut | None:
    if link.target_kind == "task":
        result = await db.execute(
            select(Task, Week)
            .join(Week, Week.id == Task.week_id)
            .where(Task.id == link.target_id, Task.user_id == user_id),
        )
        task_row = result.one_or_none()
        if task_row is None:
            return None
        _, week = task_row
        return planner_link_to_schema(link, open_path=f"/week/{week.year}/{week.week_number}")

    if link.target_kind == "habit":
        result = await db.execute(
            select(Habit).where(Habit.id == link.target_id, Habit.user_id == user_id),
        )
        habit = result.scalar_one_or_none()
        if habit is None:
            return None
        return planner_link_to_schema(
            link,
            open_path=month_key_to_open_path(habit.starts_at_month_key, habit.created_at.date()),
        )

    return None


async def list_resolved_planner_links_for_source_refs(
    db: AsyncSession,
    user_id: str,
    source_refs: list[str],
) -> dict[str, PlannerLinkOut]:
    if not source_refs:
        return {}

    result = await db.execute(
        select(PlannerLink).where(
            PlannerLink.user_id == user_id,
            PlannerLink.source_kind == CALENDAR_EVENT_SOURCE_KIND,
            PlannerLink.link_mode == IMPORT_COPY_LINK_MODE,
            PlannerLink.source_ref.in_(source_refs),
        ),
    )
    links = result.scalars().all()
    resolved: dict[str, PlannerLinkOut] = {}
    for link in links:
        planner_link = await resolve_planner_link(db, user_id, link)
        if planner_link is not None:
            resolved[link.source_ref] = planner_link
    return resolved
# BLOCK-END: CALENDAR_BRIDGE_LOOKUP_FLOW


# BLOCK-START: CALENDAR_BRIDGE_IMPORT_FLOW
# Description: Imports a calendar event into task or habit domain objects with backend-enforced idempotency.
async def import_calendar_event_to_planner(
    db: AsyncSession,
    user_id: str,
    event_id: str,
    payload: CalendarEventImportIn,
) -> CalendarEventImportOut:
    event = await get_calendar_event_for_user(db, user_id, event_id)

    if event.status == "cancelled":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cancelled calendar event cannot be imported")

    if is_calendar_event_multi_day(event):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Multi-day calendar event import is not supported yet",
        )

    source_ref = build_calendar_event_source_ref(event.connection_id, event.external_event_id)
    existing_link = await get_planner_link_by_source_ref(db, user_id, source_ref)
    if existing_link is not None:
        resolved_link = await resolve_planner_link(db, user_id, existing_link)
        if resolved_link is not None:
            return CalendarEventImportOut(status="existing", planner_link=resolved_link)

        await db.delete(existing_link)
        await db.commit()

    if payload.target_type == "task":
        if payload.week is None:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Week is required for task import")

        try:
            validate_week(payload.year, payload.week)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

        task = await create_task(
            db,
            user_id,
            payload.year,
            payload.week,
            title=normalize_import_title(payload.title or event.title, max_length=500),
            time_planned=payload.time_planned,
            time_actual=None,
            is_priority=payload.is_priority,
            start_day=payload.start_day or event.starts_at.isoweekday(),
        )
        link = PlannerLink(
            user_id=user_id,
            source_kind=CALENDAR_EVENT_SOURCE_KIND,
            source_ref=source_ref,
            target_kind="task",
            target_id=task.id,
            link_mode=IMPORT_COPY_LINK_MODE,
        )
        db.add(link)
        await db.commit()
        await db.refresh(link)
        return CalendarEventImportOut(
            status="created",
            planner_link=planner_link_to_schema(link, open_path=f"/week/{payload.year}/{payload.week}"),
        )

    if payload.month is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Month is required for habit import")

    try:
        validate_month(payload.year, payload.month)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    title = normalize_import_title(payload.title or event.title, max_length=255)
    target_month_key = month_key(payload.year, payload.month)
    existing_habit = await find_active_habit_by_name(db, user_id, target_month_key, title)
    if existing_habit is not None:
        existing_habit_link = await get_planner_link_for_habit(db, user_id, existing_habit.id)
        if existing_habit_link is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Привычка «{title}» уже существует. Измените название и создайте снова или отмените.",
            )

        link = PlannerLink(
            user_id=user_id,
            source_kind=CALENDAR_EVENT_SOURCE_KIND,
            source_ref=source_ref,
            target_kind="habit",
            target_id=existing_habit.id,
            link_mode=IMPORT_COPY_LINK_MODE,
        )
        db.add(link)
        await db.commit()
        await db.refresh(link)
        return CalendarEventImportOut(
            status="existing",
            planner_link=planner_link_to_schema(
                link,
                open_path=month_key_to_open_path(
                    existing_habit.starts_at_month_key,
                    existing_habit.created_at.date(),
                ),
            ),
        )

    habit = await create_habit(
        db,
        user_id,
        payload.year,
        payload.month,
        title,
        schedule_days=payload.schedule_days,
    )
    link = PlannerLink(
        user_id=user_id,
        source_kind=CALENDAR_EVENT_SOURCE_KIND,
        source_ref=source_ref,
        target_kind="habit",
        target_id=habit.id,
        link_mode=IMPORT_COPY_LINK_MODE,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)
    return CalendarEventImportOut(
        status="created",
        planner_link=planner_link_to_schema(link, open_path=f"/month/{payload.year}/{payload.month}"),
    )
# BLOCK-END: CALENDAR_BRIDGE_IMPORT_FLOW
# BLOCK-END: CALENDAR_BRIDGE_SERVICE_MODULE
