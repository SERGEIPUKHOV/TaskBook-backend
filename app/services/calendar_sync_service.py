from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_connection import CalendarConnection
from app.models.calendar_provider_account import CalendarProviderAccount
from app.models.calendar_event import CalendarEvent
from app.models.habit import Habit
from app.models.planner_link import PlannerLink
from app.services.calendar_bridge_service import (
    CALENDAR_EVENT_SOURCE_KIND,
    IMPORT_COPY_LINK_MODE,
    build_calendar_event_source_ref,
    get_calendar_event_suggested_target_type,
    list_resolved_planner_links_for_source_refs,
    resolve_planner_link,
)
from app.schemas.calendar import CalendarConnectionOut, CalendarEventOut


@dataclass(slots=True)
class NormalizedCalendarEvent:
    external_event_id: str
    external_calendar_id: str | None
    title: str | None
    description: str | None
    location: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    source_timezone: str | None
    is_all_day: bool
    status: str
    raw_payload: dict[str, Any] | None = None


class CalendarSyncError(RuntimeError):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def all_day_bounds(start_value: date, end_value: date | None = None) -> tuple[datetime, datetime]:
    start_at = datetime.combine(start_value, time.min, tzinfo=timezone.utc)
    resolved_end = end_value or (start_value + timedelta(days=1))
    end_at = datetime.combine(resolved_end, time.min, tzinfo=timezone.utc)
    if end_at <= start_at:
        end_at = start_at + timedelta(days=1)
    return start_at, end_at


async def mark_connection_error(db: AsyncSession, connection: CalendarConnection, message: str) -> None:
    connection.status = "error"
    connection.last_error = message[:2000]
    await db.commit()
    await db.refresh(connection)


async def reconcile_connection_events(
    db: AsyncSession,
    connection: CalendarConnection,
    events: list[NormalizedCalendarEvent],
    *,
    full_sync: bool,
    sync_cursor: str | None,
) -> CalendarConnection:
    now = utc_now()
    event_ids = [event.external_event_id for event in events]
    existing_by_external_id: dict[str, CalendarEvent] = {}

    if event_ids:
        existing_result = await db.execute(
            select(CalendarEvent).where(
                CalendarEvent.connection_id == connection.id,
                CalendarEvent.external_event_id.in_(event_ids),
            ),
        )
        existing_by_external_id = {
            record.external_event_id: record
            for record in existing_result.scalars().all()
        }

    for event in events:
        record = existing_by_external_id.get(event.external_event_id)
        if record is None:
            if event.starts_at is None or event.ends_at is None:
                continue

            record = CalendarEvent(
                connection_id=connection.id,
                user_id=connection.user_id,
                external_event_id=event.external_event_id,
                external_calendar_id=event.external_calendar_id,
                title=event.title or "Без названия",
                description=event.description,
                location=event.location,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                source_timezone=event.source_timezone,
                is_all_day=event.is_all_day,
                status=event.status,
                raw_payload=event.raw_payload,
                last_seen_at=now,
            )
            db.add(record)
            continue

        if event.external_calendar_id is not None:
            record.external_calendar_id = event.external_calendar_id
        if event.title is not None:
            record.title = event.title or record.title
        if event.description is not None or record.description is None:
            record.description = event.description
        if event.location is not None or record.location is None:
            record.location = event.location
        if event.starts_at is not None:
            record.starts_at = event.starts_at
        if event.ends_at is not None:
            record.ends_at = event.ends_at
        if event.source_timezone is not None or record.source_timezone is None:
            record.source_timezone = event.source_timezone
        record.is_all_day = event.is_all_day
        record.status = event.status
        record.raw_payload = event.raw_payload
        record.last_seen_at = now

    if full_sync:
        stale_update = (
            update(CalendarEvent)
            .where(CalendarEvent.connection_id == connection.id)
            .values(last_seen_at=now, status="cancelled")
        )
        if event_ids:
            stale_update = stale_update.where(CalendarEvent.external_event_id.not_in(event_ids))
        await db.execute(stale_update)

    connection.status = "active"
    connection.last_error = None
    connection.last_synced_at = now
    connection.sync_cursor = sync_cursor
    await db.commit()
    await db.refresh(connection)
    return connection


async def list_connection_events_in_range(
    db: AsyncSession,
    user_id: str,
    date_from: date,
    date_to: date,
) -> list[CalendarEventOut]:
    range_start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    range_end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)

    result = await db.execute(
        select(CalendarEvent, CalendarConnection)
        .join(CalendarConnection, CalendarConnection.id == CalendarEvent.connection_id)
        .where(
            CalendarEvent.user_id == user_id,
            CalendarEvent.status != "cancelled",
            CalendarConnection.status != "disconnected",
            and_(
                CalendarEvent.starts_at < range_end,
                CalendarEvent.ends_at > range_start,
            ),
        )
        .order_by(CalendarEvent.starts_at.asc(), CalendarEvent.title.asc()),
    )

    rows = result.all()
    source_refs = [
        build_calendar_event_source_ref(event.connection_id, event.external_event_id)
        for event, _connection in rows
    ]
    source_dates = {
        build_calendar_event_source_ref(event.connection_id, event.external_event_id): event.starts_at.date()
        for event, _connection in rows
    }
    planner_links = await list_resolved_planner_links_for_source_refs(
        db,
        user_id,
        source_refs,
        source_dates=source_dates,
    )
    # recurring_id -> earliest starts_at_month_key of a linked habit ("YYYY-MM")
    # Only habits contribute: task imports are per-instance and don't block other weeks.
    linked_recurring_ids: dict[str, str] = {}
    linked_refs_result = await db.execute(
        select(PlannerLink).where(
            PlannerLink.user_id == user_id,
            PlannerLink.source_kind == CALENDAR_EVENT_SOURCE_KIND,
            PlannerLink.link_mode == IMPORT_COPY_LINK_MODE,
            PlannerLink.target_kind == "habit",
        ),
    )
    linked_links_by_ref = {
        link.source_ref: link
        for link in linked_refs_result.scalars().all()
    }

    if linked_links_by_ref:
        # Pre-fetch starts_at_month_key for all linked habits in one query.
        habit_target_ids = list({link.target_id for link in linked_links_by_ref.values()})
        habits_result = await db.execute(
            select(Habit.id, Habit.starts_at_month_key).where(
                Habit.user_id == user_id,
                Habit.id.in_(habit_target_ids),
            ),
        )
        habit_starts: dict[str, str] = {
            str(row.id): (row.starts_at_month_key or "")
            for row in habits_result.all()
        }

        linked_events_result = await db.execute(select(CalendarEvent).where(CalendarEvent.user_id == user_id))
        for linked_event in linked_events_result.scalars().all():
            source_ref = build_calendar_event_source_ref(
                linked_event.connection_id,
                linked_event.external_event_id,
            )
            linked_link = linked_links_by_ref.get(source_ref)
            if linked_link is None:
                continue
            resolved_link = await resolve_planner_link(
                db,
                user_id,
                linked_link,
                as_of_date=linked_event.starts_at.date(),
            )
            if resolved_link is None:
                continue

            recurring_id = (linked_event.raw_payload or {}).get("recurringEventId")
            if isinstance(recurring_id, str) and recurring_id:
                starts = habit_starts.get(str(linked_link.target_id), "")
                # Keep the earliest start month if multiple habits link to the same series.
                current = linked_recurring_ids.get(recurring_id, "9999-99")
                if starts < current:
                    linked_recurring_ids[recurring_id] = starts

    events_out: list[CalendarEventOut] = []
    for event, connection in rows:
        recurring_id_value = (event.raw_payload or {}).get("recurringEventId")
        recurring_id = recurring_id_value if isinstance(recurring_id_value, str) and recurring_id_value else None
        event_month = (
            f"{event.starts_at.year:04d}-{event.starts_at.month:02d}"
            if event.starts_at else ""
        )
        habit_active_from = linked_recurring_ids.get(recurring_id, "9999-99") if recurring_id else "9999-99"
        events_out.append(
            CalendarEventOut(
                planner_link=planner_links.get(
                    build_calendar_event_source_ref(event.connection_id, event.external_event_id),
                ),
                series_linked=bool(
                    recurring_id and
                    recurring_id in linked_recurring_ids and
                    event_month >= habit_active_from
                ),
                suggested_target_type=get_calendar_event_suggested_target_type(event),
                recurrence=[
                    item for item in ((event.raw_payload or {}).get("recurrence") or [])
                    if isinstance(item, str)
                ],
                id=event.id,
                connection_id=event.connection_id,
                provider=connection.provider,
                account_label=connection.account_label,
                external_event_id=event.external_event_id,
                external_calendar_id=event.external_calendar_id,
                title=event.title,
                description=event.description,
                location=event.location,
                starts_at=event.starts_at,
                ends_at=event.ends_at,
                source_timezone=event.source_timezone,
                is_all_day=event.is_all_day,
                status=event.status,
                recurring_event_id=recurring_id,
            )
        )

    return events_out


def connection_to_schema(
    connection: CalendarConnection,
    provider_account: CalendarProviderAccount | None = None,
) -> CalendarConnectionOut:
    return CalendarConnectionOut(
        id=connection.id,
        provider=connection.provider,
        status=connection.status,
        external_account_id=connection.external_account_id,
        account_label=connection.account_label,
        provider_account_label=provider_account.account_label if provider_account else None,
        last_synced_at=connection.last_synced_at,
        last_error=connection.last_error,
        color=connection.color,
        token_expires_at=connection.token_expires_at,
        created_at=connection.created_at,
        updated_at=connection.updated_at,
    )
