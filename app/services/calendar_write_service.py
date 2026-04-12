from __future__ import annotations

import logging
from typing import Any
from urllib.parse import quote

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


async def _get_master_rrule_from_google(
    access_token: str,
    calendar_id: str,
    master_id: str,
) -> str | None:
    """Fetch master event directly from Google and return the first RRULE item."""
    from app.services.calendar_google_service import _google_get

    try:
        encoded_calendar_id = quote(calendar_id, safe="")
        encoded_event_id = quote(master_id, safe="")
        data = await _google_get(access_token, f"/calendars/{encoded_calendar_id}/events/{encoded_event_id}")
        recurrence = data.get("recurrence") or []
        return next((item for item in recurrence if isinstance(item, str) and item.startswith("RRULE:")), None)
    except Exception:
        return None


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
