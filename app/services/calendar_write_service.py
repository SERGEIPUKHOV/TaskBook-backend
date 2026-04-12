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
    link = link_result.scalar_one_or_none()
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
