from __future__ import annotations

import logging
from datetime import datetime, timezone, tzinfo
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_connection import CalendarConnection
from app.models.calendar_event import CalendarEvent
from app.models.calendar_provider_account import CalendarProviderAccount
from app.models.planner_link import PlannerLink
from app.services.calendar_google_service import _ensure_google_access_token
from app.services.calendar_sync_service import CalendarSyncError

logger = logging.getLogger(__name__)

GOOGLE_API_BASE = "https://www.googleapis.com/calendar/v3"
ISO_DAY_TO_BYDAY = {1: "MO", 2: "TU", 3: "WE", 4: "TH", 5: "FR", 6: "SA", 7: "SU"}
BYDAY_TO_ISO_DAY = {v: k for k, v in ISO_DAY_TO_BYDAY.items()}


def _resolve_google_event_timezone(
    source_timezone: str | None,
    fallback_tzinfo: tzinfo | None,
) -> tuple[tzinfo, str | None]:
    if source_timezone:
        try:
            return ZoneInfo(source_timezone), source_timezone
        except ZoneInfoNotFoundError:
            pass

    if fallback_tzinfo is not None:
        return fallback_tzinfo, "UTC" if fallback_tzinfo == timezone.utc else None

    return timezone.utc, "UTC"


def _replace_google_wall_time(
    value: datetime,
    *,
    hour: int,
    minute: int,
    source_timezone: str | None,
) -> tuple[datetime, str | None]:
    base_value = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
    target_timezone, google_timezone_name = _resolve_google_event_timezone(source_timezone, base_value.tzinfo)
    localized_value = base_value.astimezone(target_timezone)
    return localized_value.replace(hour=hour, minute=minute, second=0, microsecond=0), google_timezone_name


async def _google_patch(
    access_token: str,
    calendar_id: str,
    event_id: str,
    body: dict[str, Any],
) -> None:
    """PATCH one Google Calendar event and raise CalendarSyncError on HTTP failure."""
    encoded_calendar_id = quote(calendar_id, safe="")
    encoded_event_id = quote(event_id, safe="")

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.patch(
            f"{GOOGLE_API_BASE}/calendars/{encoded_calendar_id}/events/{encoded_event_id}",
            json=body,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code >= 400:
        raise CalendarSyncError(f"Google PATCH failed: {response.status_code} {response.text[:200]}")


async def _resolve_google_link(
    db: AsyncSession,
    user_id: str,
    target_kind: str,
    target_id: str,
) -> tuple[CalendarEvent, CalendarConnection, CalendarProviderAccount] | None:
    """Resolve planner item -> imported calendar event -> Google connection/account."""
    link_result = await db.execute(
        select(PlannerLink).where(
            PlannerLink.user_id == user_id,
            PlannerLink.target_kind == target_kind,
            PlannerLink.target_id == target_id,
            PlannerLink.source_kind == "calendar_event",
            PlannerLink.link_mode == "import_copy",
        ),
    )
    link = link_result.scalars().first()
    if link is None:
        return None

    connection_id, separator, external_event_id = link.source_ref.partition(":")
    if not separator or not connection_id or not external_event_id:
        return None

    connection_result = await db.execute(
        select(CalendarConnection).where(
            CalendarConnection.id == connection_id,
            CalendarConnection.user_id == user_id,
        ),
    )
    connection = connection_result.scalar_one_or_none()
    if connection is None or connection.provider != "google" or connection.provider_account_id is None:
        return None

    event_result = await db.execute(
        select(CalendarEvent).where(
            CalendarEvent.connection_id == connection_id,
            CalendarEvent.external_event_id == external_event_id,
            CalendarEvent.user_id == user_id,
        ),
    )
    event = event_result.scalar_one_or_none()
    if event is None:
        return None

    provider_account_result = await db.execute(
        select(CalendarProviderAccount).where(
            CalendarProviderAccount.id == connection.provider_account_id,
        ),
    )
    provider_account = provider_account_result.scalar_one_or_none()
    if provider_account is None:
        return None

    return event, connection, provider_account


async def push_task_title_to_google(
    db: AsyncSession,
    user_id: str,
    task_id: str,
    new_title: str,
) -> None:
    """Best-effort: update linked Google event summary after planner task rename."""
    try:
        resolved = await _resolve_google_link(db, user_id, "task", task_id)
        if resolved is None:
            return

        event, connection, provider_account = resolved
        access_token, token_changed = await _ensure_google_access_token(provider_account)
        if token_changed:
            await db.commit()
            await db.refresh(provider_account)

        await _google_patch(access_token, connection.external_account_id, event.external_event_id, {"summary": new_title})
    except Exception:
        logger.debug("push_task_title_to_google: best-effort failed for task %s", task_id, exc_info=True)


async def push_habit_title_to_google(
    db: AsyncSession,
    user_id: str,
    habit_id: str,
    new_name: str,
) -> None:
    """Best-effort: update linked Google event summary after planner habit rename."""
    try:
        resolved = await _resolve_google_link(db, user_id, "habit", habit_id)
        if resolved is None:
            return

        event, connection, provider_account = resolved
        access_token, token_changed = await _ensure_google_access_token(provider_account)
        if token_changed:
            await db.commit()
            await db.refresh(provider_account)

        raw_payload = event.raw_payload or {}
        event_id = str(raw_payload.get("recurringEventId") or event.external_event_id)
        await _google_patch(access_token, connection.external_account_id, event_id, {"summary": new_name})
    except Exception:
        logger.debug("push_habit_title_to_google: best-effort failed for habit %s", habit_id, exc_info=True)


def _build_updated_rrule(existing_rrule: str, new_schedule_days: list[int]) -> str | None:
    """Replace BYDAY inside an existing weekly RRULE while preserving other RRULE parts."""
    prefix = "RRULE:" if existing_rrule.startswith("RRULE:") else ""
    body = existing_rrule[len(prefix):]
    props: dict[str, str] = {}

    for part in body.split(";"):
        if "=" in part:
            key, _, value = part.partition("=")
            props[key.upper()] = value
        elif part:
            props[part.upper()] = ""

    if props.get("FREQ", "").upper() != "WEEKLY":
        return None

    byday_codes = [ISO_DAY_TO_BYDAY[day] for day in sorted(set(new_schedule_days)) if day in ISO_DAY_TO_BYDAY]
    if not byday_codes:
        return None

    props["BYDAY"] = ",".join(byday_codes)
    ordered_keys = ["FREQ", "BYDAY"] + sorted(key for key in props if key not in ("FREQ", "BYDAY"))
    rrule_body = ";".join(f"{key}={props[key]}" if props[key] else key for key in ordered_keys if key in props)
    return f"{prefix}{rrule_body}"


async def _fetch_google_event(
    access_token: str,
    calendar_id: str,
    event_id: str,
) -> dict | None:
    """Fetch a single Google Calendar event by ID. Returns None on any error."""
    from app.services.calendar_google_service import _google_get

    try:
        encoded_calendar_id = quote(calendar_id, safe="")
        encoded_event_id = quote(event_id, safe="")
        return await _google_get(access_token, f"/calendars/{encoded_calendar_id}/events/{encoded_event_id}")
    except Exception:
        return None


async def _get_master_rrule_from_google(
    access_token: str,
    calendar_id: str,
    master_id: str,
) -> str | None:
    """Fetch master event from Google and return the first RRULE item."""
    data = await _fetch_google_event(access_token, calendar_id, master_id)
    if data is None:
        return None
    recurrence = data.get("recurrence") or []
    return next((item for item in recurrence if isinstance(item, str) and item.startswith("RRULE:")), None)


async def push_habit_schedule_to_google(
    db: AsyncSession,
    user_id: str,
    habit_id: str,
    new_schedule_days: list[int],
) -> None:
    """Best-effort: update Google master-event BYDAY and sync the connection immediately."""
    try:
        resolved = await _resolve_google_link(db, user_id, "habit", habit_id)
        if resolved is None:
            return

        event, connection, provider_account = resolved
        access_token, token_changed = await _ensure_google_access_token(provider_account)
        if token_changed:
            await db.commit()
            await db.refresh(provider_account)

        raw_payload = event.raw_payload or {}
        master_id = str(raw_payload.get("recurringEventId") or event.external_event_id)
        calendar_id = connection.external_account_id

        recurrence_items = [item for item in (raw_payload.get("recurrence") or []) if isinstance(item, str)]
        existing_rrule = next((item for item in recurrence_items if item.startswith("RRULE:")), None)
        if existing_rrule is None:
            existing_rrule = await _get_master_rrule_from_google(access_token, calendar_id, master_id)
        if existing_rrule is None:
            logger.debug("push_habit_schedule_to_google: no RRULE for habit %s, skipping", habit_id)
            return

        updated_rrule = _build_updated_rrule(existing_rrule, new_schedule_days)
        if updated_rrule is None:
            if "FREQ=WEEKLY" not in existing_rrule.upper():
                logger.warning(
                    "push_habit_schedule_to_google: unsupported RRULE '%s' for habit %s, skipping",
                    existing_rrule,
                    habit_id,
                )
            else:
                logger.debug(
                    "push_habit_schedule_to_google: no valid schedule days for habit %s, skipping",
                    habit_id,
                )
            return

        preserved_recurrence = [item for item in recurrence_items if not item.startswith("RRULE:")]
        next_recurrence = [updated_rrule, *preserved_recurrence] if preserved_recurrence else [updated_rrule]
        await _google_patch(access_token, calendar_id, master_id, {"recurrence": next_recurrence})

        from app.services.calendar_google_service import sync_google_connection

        try:
            await sync_google_connection(db, connection, provider_account=provider_account)
        except Exception:
            logger.debug(
                "push_habit_schedule_to_google: post-patch sync failed for habit %s",
                habit_id,
                exc_info=True,
            )
    except Exception:
        logger.debug("push_habit_schedule_to_google: best-effort failed for habit %s", habit_id, exc_info=True)


async def push_habit_event_time_to_google(
    db: AsyncSession,
    user_id: str,
    habit_id: str,
    starts_hhmm: str,
    ends_hhmm: str,
) -> None:
    """Best-effort: update Google event start/end time using event-local wall clock HH:MM.

    For recurring events: fetches the master event to use its own original date,
    then patches the master so all instances update via next sync.
    For non-recurring events: patches the event directly using its own date.
    """
    try:
        resolved = await _resolve_google_link(db, user_id, "habit", habit_id)
        if resolved is None:
            return

        event, connection, provider_account = resolved
        access_token, token_changed = await _ensure_google_access_token(provider_account)
        if token_changed:
            await db.commit()
            await db.refresh(provider_account)

        if event.starts_at is None or event.ends_at is None:
            return

        raw_payload = event.raw_payload or {}
        recurring_event_id = raw_payload.get("recurringEventId")
        calendar_id = connection.external_account_id

        start_h, start_m = (int(value) for value in starts_hhmm.split(":"))
        end_h, end_m = (int(value) for value in ends_hhmm.split(":"))

        if recurring_event_id:
            # Recurring: must patch the master using the master's own start date.
            # Using an instance's date would shift the entire series to a different date.
            master_data = await _fetch_google_event(access_token, calendar_id, recurring_event_id)
            if master_data is None:
                logger.debug("push_habit_event_time_to_google: could not fetch master for habit %s", habit_id)
                return

            master_start_str = (master_data.get("start") or {}).get("dateTime")
            master_end_str = (master_data.get("end") or {}).get("dateTime")
            master_start_timezone = (master_data.get("start") or {}).get("timeZone")
            master_end_timezone = (master_data.get("end") or {}).get("timeZone")
            if not master_start_str or not master_end_str:
                return

            base_start = datetime.fromisoformat(master_start_str)
            base_end = datetime.fromisoformat(master_end_str)
            if base_start.tzinfo is None:
                base_start = base_start.replace(tzinfo=timezone.utc)
            if base_end.tzinfo is None:
                base_end = base_end.replace(tzinfo=timezone.utc)
            target_timezone = master_start_timezone or master_end_timezone or event.source_timezone
            target_id = recurring_event_id
        else:
            base_start = event.starts_at if event.starts_at.tzinfo is not None else event.starts_at.replace(tzinfo=timezone.utc)
            base_end = event.ends_at if event.ends_at.tzinfo is not None else event.ends_at.replace(tzinfo=timezone.utc)
            target_timezone = event.source_timezone
            target_id = event.external_event_id

        new_start, start_timezone_name = _replace_google_wall_time(
            base_start,
            hour=start_h,
            minute=start_m,
            source_timezone=target_timezone,
        )
        new_end, end_timezone_name = _replace_google_wall_time(
            base_end,
            hour=end_h,
            minute=end_m,
            source_timezone=target_timezone,
        )

        start_payload = {"dateTime": new_start.isoformat()}
        end_payload = {"dateTime": new_end.isoformat()}
        if start_timezone_name:
            start_payload["timeZone"] = start_timezone_name
        if end_timezone_name:
            end_payload["timeZone"] = end_timezone_name

        await _google_patch(
            access_token,
            calendar_id,
            target_id,
            {
                "start": start_payload,
                "end": end_payload,
            },
        )
    except Exception:
        logger.debug(
            "push_habit_event_time_to_google: best-effort failed for habit %s",
            habit_id,
            exc_info=True,
        )


def _parse_rrule_schedule_days(rrule_str: str) -> list[int] | None:
    """Parse BYDAY from RRULE string → sorted ISO day list, or None if FREQ≠WEEKLY / no BYDAY."""
    body = rrule_str[len("RRULE:"):] if rrule_str.startswith("RRULE:") else rrule_str
    props: dict[str, str] = {}
    for part in body.split(";"):
        if "=" in part:
            k, _, v = part.partition("=")
            props[k.upper()] = v

    if props.get("FREQ", "").upper() != "WEEKLY":
        return None

    byday = props.get("BYDAY", "")
    if not byday:
        return None

    days: list[int] = []
    for code in byday.split(","):
        # Handle offset codes like 1MO or -1FR → take last 2 chars
        day_code = code.strip().upper()[-2:]
        if day_code in BYDAY_TO_ISO_DAY:
            days.append(BYDAY_TO_ISO_DAY[day_code])

    return sorted(set(days)) if days else None


async def backpropagate_google_rrule_to_habits(
    db: AsyncSession,
    connection_id: str,
    user_id: str,
    synced_events: list[Any],
) -> None:
    """Best-effort: after Google sync, update habit.schedule_days when linked master event RRULE changed."""
    try:
        from app.models.habit import Habit
        from app.schemas.habit import HabitPatch
        from app.services.habit_service import update_habit

        # Collect source_ref → rrule for every synced event that carries recurrence
        rrule_by_source_ref: dict[str, str] = {}
        for event in synced_events:
            raw = getattr(event, "raw_payload", None) or {}
            recurrence = raw.get("recurrence") or []
            rrule = next((r for r in recurrence if isinstance(r, str) and r.startswith("RRULE:")), None)
            if rrule:
                source_ref = f"{connection_id}:{event.external_event_id}"
                rrule_by_source_ref[source_ref] = rrule

        if not rrule_by_source_ref:
            return

        # Find habit PlannerLinks for these events in one query
        links_result = await db.execute(
            select(PlannerLink).where(
                PlannerLink.user_id == user_id,
                PlannerLink.source_kind == "calendar_event",
                PlannerLink.link_mode == "import_copy",
                PlannerLink.target_kind == "habit",
                PlannerLink.source_ref.in_(list(rrule_by_source_ref.keys())),
            ),
        )
        links = links_result.scalars().all()
        if not links:
            return

        # Fetch habits in one query
        habit_ids = list({link.target_id for link in links})
        habits_result = await db.execute(
            select(Habit).where(
                Habit.id.in_(habit_ids),
                Habit.user_id == user_id,
            ),
        )
        habits_by_id = {str(h.id): h for h in habits_result.scalars().all()}

        for link in links:
            rrule = rrule_by_source_ref.get(link.source_ref)
            if not rrule:
                continue
            new_days = _parse_rrule_schedule_days(rrule)
            if new_days is None:
                continue
            habit = habits_by_id.get(str(link.target_id))
            if habit is None:
                continue
            current_days = sorted(habit.schedule_days or [])
            if current_days == new_days:
                continue
            await update_habit(db, user_id, str(link.target_id), HabitPatch(schedule_days=new_days))
            logger.debug(
                "backpropagate_google_rrule_to_habits: habit %s schedule_days %s → %s",
                link.target_id,
                current_days,
                new_days,
            )
    except Exception:
        logger.debug("backpropagate_google_rrule_to_habits: best-effort failed", exc_info=True)
