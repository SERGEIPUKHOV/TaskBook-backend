from __future__ import annotations

from datetime import date, datetime, timedelta
from hashlib import sha256
from typing import Any

import httpx
from icalendar import Calendar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calendar_secrets import decrypt_secret, encrypt_secret
from app.models.calendar_connection import CalendarConnection
from app.services.calendar_sync_service import (
    CalendarSyncError,
    NormalizedCalendarEvent,
    all_day_bounds,
    ensure_utc,
    mark_connection_error,
    reconcile_connection_events,
)


async def fetch_ics_feed(ics_url: str) -> str:
    url = ics_url.replace("webcal://", "https://", 1) if ics_url.startswith("webcal://") else ics_url
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        response = await client.get(url)

    if response.status_code >= 400:
        raise CalendarSyncError(response.text or "Не удалось загрузить ICS feed")

    return response.text


def build_ics_external_account_id(ics_url: str) -> str:
    return sha256(ics_url.strip().encode("utf-8")).hexdigest()


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def _parse_ics_times(component) -> tuple[datetime, datetime, str | None, bool]:
    dtstart = component.decoded("DTSTART")
    dtend = component.decoded("DTEND") if component.get("DTEND") else None
    tzid = _to_text(component.get("DTSTART").params.get("TZID")) if component.get("DTSTART") else None

    if isinstance(dtstart, date) and not isinstance(dtstart, datetime):
        start_at, end_at = all_day_bounds(dtstart, dtend if isinstance(dtend, date) and not isinstance(dtend, datetime) else None)
        return start_at, end_at, tzid, True

    start_at = ensure_utc(dtstart)
    if isinstance(dtend, datetime):
        end_at = ensure_utc(dtend)
    elif isinstance(dtend, date):
        _, end_at = all_day_bounds(dtstart.date(), dtend)
    else:
        end_at = start_at + timedelta(hours=1)

    if end_at <= start_at:
        end_at = start_at + timedelta(hours=1)

    return start_at, end_at, tzid, False


def parse_ics_events(payload: str) -> tuple[str | None, list[NormalizedCalendarEvent]]:
    calendar = Calendar.from_ical(payload)
    feed_label = _to_text(calendar.get("X-WR-CALNAME")) or _to_text(calendar.get("NAME"))
    events: list[NormalizedCalendarEvent] = []

    for component in calendar.walk():
        if component.name != "VEVENT":
            continue

        uid = _to_text(component.get("UID"))
        if not uid:
            continue

        starts_at, ends_at, source_timezone, is_all_day = _parse_ics_times(component)
        status_raw = (_to_text(component.get("STATUS")) or "CONFIRMED").lower()
        events.append(
            NormalizedCalendarEvent(
                external_event_id=uid,
                external_calendar_id=_to_text(component.get("UID")),
                title=_to_text(component.get("SUMMARY")) or "Без названия",
                description=_to_text(component.get("DESCRIPTION")),
                location=_to_text(component.get("LOCATION")),
                starts_at=starts_at,
                ends_at=ends_at,
                source_timezone=source_timezone,
                is_all_day=is_all_day,
                status="cancelled" if status_raw == "cancelled" else "confirmed",
                raw_payload={
                    "summary": _to_text(component.get("SUMMARY")),
                    "uid": uid,
                },
            ),
        )

    return feed_label, events


async def get_or_create_apple_connection(
    db: AsyncSession,
    user_id: str,
    *,
    ics_url: str,
    account_label: str | None,
) -> CalendarConnection:
    external_account_id = build_ics_external_account_id(ics_url)
    result = await db.execute(
        select(CalendarConnection).where(
            CalendarConnection.user_id == user_id,
            CalendarConnection.provider == "apple",
            CalendarConnection.external_account_id == external_account_id,
        ),
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        connection = CalendarConnection(
            user_id=user_id,
            provider="apple",
            status="active",
            external_account_id=external_account_id,
            account_label=account_label or "Apple Calendar",
            ics_url_encrypted=encrypt_secret(ics_url),
        )
        db.add(connection)
        await db.flush()
    else:
        connection.account_label = account_label or connection.account_label
        connection.ics_url_encrypted = encrypt_secret(ics_url)
        connection.status = "active"
        connection.last_error = None

    return connection


async def sync_apple_connection(db: AsyncSession, connection: CalendarConnection) -> CalendarConnection:
    ics_url = decrypt_secret(connection.ics_url_encrypted)
    if not ics_url:
        await mark_connection_error(db, connection, "Отсутствует ICS URL для Apple Calendar")
        raise CalendarSyncError("Отсутствует ICS URL для Apple Calendar")

    try:
        payload = await fetch_ics_feed(ics_url)
        feed_label, events = parse_ics_events(payload)
        if feed_label and not connection.account_label:
            connection.account_label = feed_label
        elif feed_label and connection.account_label in {None, "Apple Calendar"}:
            connection.account_label = feed_label
        return await reconcile_connection_events(
            db,
            connection,
            events,
            full_sync=True,
            sync_cursor=None,
        )
    except CalendarSyncError as error:
        await mark_connection_error(db, connection, str(error))
        raise
