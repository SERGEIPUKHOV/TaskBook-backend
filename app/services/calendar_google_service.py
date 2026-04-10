from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.calendar_secrets import decrypt_secret, encrypt_secret
from app.core.config import settings
from app.models.calendar_connection import CalendarConnection
from app.models.calendar_event import CalendarEvent
from app.models.calendar_provider_account import CalendarProviderAccount
from app.schemas.calendar import GoogleCalendarOptionOut, GoogleCalendarOptionsOut
from app.services.calendar_sync_service import (
    CalendarSyncError,
    NormalizedCalendarEvent,
    all_day_bounds,
    ensure_utc,
    mark_connection_error,
    reconcile_connection_events,
    utc_now,
)

GOOGLE_API_BASE = "https://www.googleapis.com/calendar/v3"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
FULL_SYNC_PAST_DAYS = 30
FULL_SYNC_FUTURE_DAYS = 180


class InvalidGoogleSyncCursor(CalendarSyncError):
    pass


@dataclass(slots=True)
class GoogleCalendarOption:
    id: str
    summary: str
    access_role: str | None
    primary: bool
    selected: bool


def _validate_hex_color(value: str | None) -> str | None:
    if not value:
        return None

    return value.upper() if re.fullmatch(r"#[0-9A-Fa-f]{6}", value) else None


async def _google_post_token(data: dict[str, str]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(GOOGLE_TOKEN_URL, data=data)

    if response.status_code >= 400:
        raise CalendarSyncError(response.text or "Google token exchange failed")

    return response.json()


async def exchange_google_code_for_tokens(code: str) -> dict[str, Any]:
    return await _google_post_token(
        {
            "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID or "",
            "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET or "",
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.GOOGLE_CALENDAR_REDIRECT_URI or "",
        },
    )


async def refresh_google_access_token(refresh_token: str) -> dict[str, Any]:
    return await _google_post_token(
        {
            "client_id": settings.GOOGLE_CALENDAR_CLIENT_ID or "",
            "client_secret": settings.GOOGLE_CALENDAR_CLIENT_SECRET or "",
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )


async def _google_get(access_token: str, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(
            f"{GOOGLE_API_BASE}{path}",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if response.status_code == 410:
        raise InvalidGoogleSyncCursor("Google sync token устарел")

    if response.status_code >= 400:
        raise CalendarSyncError(response.text or "Google API request failed")

    return response.json()


async def _fetch_google_calendar_list(access_token: str) -> list[dict[str, Any]]:
    calendars: list[dict[str, Any]] = []
    next_page_token: str | None = None

    while True:
        params: dict[str, Any] = {
            "minAccessRole": "reader",
            "showDeleted": "false",
            "showHidden": "false",
        }
        if next_page_token:
            params["pageToken"] = next_page_token

        payload = await _google_get(access_token, "/users/me/calendarList", params=params)
        calendars.extend(payload.get("items", []))
        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            break

    return calendars


async def _fetch_google_calendar_item(access_token: str, calendar_id: str) -> dict[str, Any]:
    encoded_calendar_id = quote(calendar_id, safe="")
    return await _google_get(access_token, f"/users/me/calendarList/{encoded_calendar_id}")


async def _fetch_google_events(
    access_token: str,
    calendar_id: str,
    sync_cursor: str | None,
) -> tuple[list[NormalizedCalendarEvent], str | None, bool]:
    events: list[NormalizedCalendarEvent] = []
    next_page_token: str | None = None
    next_sync_token: str | None = None
    incremental = bool(sync_cursor)
    encoded_calendar_id = quote(calendar_id, safe="")

    while True:
        params: dict[str, Any]
        if sync_cursor:
            params = {
                "showDeleted": "true",
                "singleEvents": "true",
                "syncToken": sync_cursor,
            }
        else:
            now = utc_now()
            params = {
                "orderBy": "startTime",
                "showDeleted": "true",
                "singleEvents": "true",
                "timeMin": (now - timedelta(days=FULL_SYNC_PAST_DAYS)).isoformat().replace("+00:00", "Z"),
                "timeMax": (now + timedelta(days=FULL_SYNC_FUTURE_DAYS)).isoformat().replace("+00:00", "Z"),
            }

        if next_page_token:
            params["pageToken"] = next_page_token

        payload = await _google_get(access_token, f"/calendars/{encoded_calendar_id}/events", params=params)
        events.extend(_map_google_event(item, calendar_id) for item in payload.get("items", []))
        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            next_sync_token = payload.get("nextSyncToken")
            break

    return events, next_sync_token, not incremental


def _parse_google_event_times(item: dict[str, Any]) -> tuple[datetime | None, datetime | None, str | None, bool]:
    start_payload = item.get("start") or {}
    end_payload = item.get("end") or {}

    if start_payload.get("date"):
        start_date = datetime.fromisoformat(start_payload["date"]).date()
        end_date = datetime.fromisoformat(end_payload.get("date", start_payload["date"]))
        start_at, end_at = all_day_bounds(start_date, end_date.date())
        return start_at, end_at, start_payload.get("timeZone") or end_payload.get("timeZone"), True

    if start_payload.get("dateTime"):
        start_at = ensure_utc(datetime.fromisoformat(start_payload["dateTime"].replace("Z", "+00:00")))
        end_raw = end_payload.get("dateTime")
        end_at = ensure_utc(datetime.fromisoformat(end_raw.replace("Z", "+00:00"))) if end_raw else start_at
        return start_at, end_at, start_payload.get("timeZone") or end_payload.get("timeZone"), False

    return None, None, None, False


def _map_google_event(item: dict[str, Any], calendar_id: str) -> NormalizedCalendarEvent:
    starts_at, ends_at, source_timezone, is_all_day = _parse_google_event_times(item)
    return NormalizedCalendarEvent(
        external_event_id=str(item.get("id") or ""),
        external_calendar_id=calendar_id,
        title=item.get("summary") or "Без названия",
        description=item.get("description"),
        location=item.get("location"),
        starts_at=starts_at,
        ends_at=ends_at,
        source_timezone=source_timezone,
        is_all_day=is_all_day,
        status="cancelled" if item.get("status") == "cancelled" else "confirmed",
        raw_payload=item,
    )


async def get_google_provider_account(db: AsyncSession, user_id: str) -> CalendarProviderAccount | None:
    result = await db.execute(
        select(CalendarProviderAccount).where(
            CalendarProviderAccount.user_id == user_id,
            CalendarProviderAccount.provider == "google",
        ),
    )
    return result.scalar_one_or_none()


async def get_or_create_google_provider_account(db: AsyncSession, user_id: str) -> CalendarProviderAccount:
    provider_account = await get_google_provider_account(db, user_id)
    if provider_account is not None:
        return provider_account

    provider_account = CalendarProviderAccount(
        user_id=user_id,
        provider="google",
        status="active",
        account_label="Google Calendar",
    )
    db.add(provider_account)
    await db.flush()
    return provider_account


async def _ensure_google_access_token(provider_account: CalendarProviderAccount) -> tuple[str, bool]:
    access_token = decrypt_secret(provider_account.access_token_encrypted)
    refresh_token = decrypt_secret(provider_account.refresh_token_encrypted)
    expires_at = ensure_utc(provider_account.token_expires_at) if provider_account.token_expires_at else None
    is_expired = expires_at is None or expires_at <= utc_now() + timedelta(seconds=60)

    if access_token and not is_expired:
        return access_token, False

    if not refresh_token:
        raise CalendarSyncError("У Google-подключения отсутствует refresh token")

    token_payload = await refresh_google_access_token(refresh_token)
    provider_account.access_token_encrypted = encrypt_secret(token_payload.get("access_token"))
    if token_payload.get("refresh_token"):
        provider_account.refresh_token_encrypted = encrypt_secret(token_payload["refresh_token"])
    expires_in = int(token_payload.get("expires_in", 3600))
    provider_account.token_expires_at = utc_now() + timedelta(seconds=expires_in)
    provider_account.status = "active"
    provider_account.last_error = None
    return token_payload.get("access_token") or "", True


async def store_google_tokens(
    db: AsyncSession,
    user_id: str,
    token_payload: dict[str, Any],
) -> CalendarProviderAccount:
    provider_account = await get_or_create_google_provider_account(db, user_id)
    provider_account.access_token_encrypted = encrypt_secret(token_payload.get("access_token"))
    provider_account.refresh_token_encrypted = encrypt_secret(
        token_payload.get("refresh_token") or decrypt_secret(provider_account.refresh_token_encrypted),
    )
    expires_in = int(token_payload.get("expires_in", 3600))
    provider_account.token_expires_at = utc_now() + timedelta(seconds=expires_in)
    provider_account.status = "active"
    provider_account.last_error = None
    await db.commit()
    await db.refresh(provider_account)
    return provider_account


async def list_google_calendar_options(db: AsyncSession, user_id: str) -> GoogleCalendarOptionsOut:
    provider_account = await get_google_provider_account(db, user_id)
    if provider_account is None:
        return GoogleCalendarOptionsOut(connected=False, provider_account_label=None, options=[])

    try:
        access_token, token_changed = await _ensure_google_access_token(provider_account)
        if token_changed:
            await db.commit()
            await db.refresh(provider_account)

        calendar_items = await _fetch_google_calendar_list(access_token)
        result = await db.execute(
            select(CalendarConnection.external_account_id).where(
                CalendarConnection.user_id == user_id,
                CalendarConnection.provider == "google",
                CalendarConnection.provider_account_id == provider_account.id,
            ),
        )
        selected_calendar_ids = set(result.scalars().all())

        primary_item = next((item for item in calendar_items if item.get("primary")), None)
        if primary_item is not None:
            provider_account.external_account_id = str(primary_item.get("id") or provider_account.external_account_id or "") or None
            provider_account.account_label = str(
                primary_item.get("summaryOverride")
                or primary_item.get("summary")
                or primary_item.get("id")
                or provider_account.account_label
                or "Google Calendar"
            )
            await db.commit()
            await db.refresh(provider_account)

        options = [
            GoogleCalendarOptionOut(
                id=str(item.get("id") or ""),
                summary=str(item.get("summaryOverride") or item.get("summary") or item.get("id") or "Без названия"),
                access_role=item.get("accessRole"),
                primary=bool(item.get("primary")),
                selected=str(item.get("id") or "") in selected_calendar_ids,
            )
            for item in calendar_items
            if item.get("id")
        ]
        options.sort(key=lambda item: (not item.primary, item.summary.lower()))
        return GoogleCalendarOptionsOut(
            connected=True,
            provider_account_label=provider_account.account_label,
            options=options,
        )
    except CalendarSyncError as error:
        provider_account.status = "error"
        provider_account.last_error = str(error)
        await db.commit()
        await db.refresh(provider_account)
        raise


async def save_google_calendar_selections(
    db: AsyncSession,
    user_id: str,
    calendar_ids: list[str],
) -> list[CalendarConnection]:
    provider_account = await get_google_provider_account(db, user_id)
    if provider_account is None:
        raise CalendarSyncError("Google Calendar ещё не подключён")

    access_token, token_changed = await _ensure_google_access_token(provider_account)
    if token_changed:
        await db.commit()
        await db.refresh(provider_account)

    calendar_items = await _fetch_google_calendar_list(access_token)
    option_by_id = {
        str(item.get("id")): item
        for item in calendar_items
        if item.get("id")
    }

    requested_ids = []
    seen_ids: set[str] = set()
    for calendar_id in calendar_ids:
        normalized_id = calendar_id.strip()
        if not normalized_id or normalized_id in seen_ids:
            continue
        if normalized_id not in option_by_id:
            raise CalendarSyncError(f"Google calendar '{normalized_id}' недоступен для выбора")
        requested_ids.append(normalized_id)
        seen_ids.add(normalized_id)

    existing_result = await db.execute(
        select(CalendarConnection).where(
            CalendarConnection.user_id == user_id,
            CalendarConnection.provider == "google",
            CalendarConnection.provider_account_id == provider_account.id,
        ),
    )
    existing_connections = existing_result.scalars().all()
    existing_by_calendar_id = {connection.external_account_id: connection for connection in existing_connections}
    removed_connection_ids = [
        connection.id
        for connection in existing_connections
        if connection.external_account_id not in seen_ids
    ]

    for connection in existing_connections:
        if connection.external_account_id not in seen_ids:
            await db.delete(connection)
    if removed_connection_ids:
        await db.execute(delete(CalendarEvent).where(CalendarEvent.connection_id.in_(removed_connection_ids)))
    await db.flush()

    selected_connections: list[CalendarConnection] = []
    for calendar_id in requested_ids:
        option = option_by_id[calendar_id]
        connection = existing_by_calendar_id.get(calendar_id)
        if connection is None:
            connection = CalendarConnection(
                user_id=user_id,
                provider_account_id=provider_account.id,
                provider="google",
                status="active",
                external_account_id=calendar_id,
                account_label=str(option.get("summaryOverride") or option.get("summary") or calendar_id),
                color=_validate_hex_color(option.get("backgroundColor")),
            )
            db.add(connection)
            await db.flush()
        else:
            connection.account_label = str(option.get("summaryOverride") or option.get("summary") or connection.account_label or calendar_id)
            connection.status = "active"
            connection.last_error = None
            if connection.color is None:
                connection.color = _validate_hex_color(option.get("backgroundColor"))

        selected_connections.append(connection)

    for connection in selected_connections:
        try:
            await sync_google_connection(db, connection, provider_account=provider_account)
        except CalendarSyncError:
            await db.refresh(connection)

    refreshed_result = await db.execute(
        select(CalendarConnection).where(
            CalendarConnection.user_id == user_id,
            CalendarConnection.provider == "google",
            CalendarConnection.provider_account_id == provider_account.id,
        ).order_by(CalendarConnection.account_label.asc(), CalendarConnection.created_at.asc()),
    )
    return refreshed_result.scalars().all()


async def disconnect_google_account(db: AsyncSession, user_id: str) -> None:
    provider_account = await get_google_provider_account(db, user_id)
    if provider_account is None:
        return

    result = await db.execute(
        select(CalendarConnection.id).where(
            CalendarConnection.user_id == user_id,
            CalendarConnection.provider == "google",
            CalendarConnection.provider_account_id == provider_account.id,
        ),
    )
    connection_ids = result.scalars().all()
    if connection_ids:
        await db.execute(delete(CalendarEvent).where(CalendarEvent.connection_id.in_(connection_ids)))
        await db.execute(delete(CalendarConnection).where(CalendarConnection.id.in_(connection_ids)))

    await db.delete(provider_account)
    await db.commit()


async def sync_google_connection(
    db: AsyncSession,
    connection: CalendarConnection,
    *,
    provider_account: CalendarProviderAccount | None = None,
) -> CalendarConnection:
    resolved_provider_account = provider_account
    if resolved_provider_account is None:
        if not connection.provider_account_id:
            raise CalendarSyncError("Google provider account не найден")
        result = await db.execute(
            select(CalendarProviderAccount).where(CalendarProviderAccount.id == connection.provider_account_id),
        )
        resolved_provider_account = result.scalar_one_or_none()
    if resolved_provider_account is None:
        raise CalendarSyncError("Google provider account не найден")

    calendar_id = connection.external_account_id
    if not calendar_id:
        raise CalendarSyncError("У Google calendar connection отсутствует calendar id")

    try:
        access_token, token_changed = await _ensure_google_access_token(resolved_provider_account)
        if token_changed:
            await db.commit()
            await db.refresh(resolved_provider_account)

        calendar_item = await _fetch_google_calendar_item(access_token, calendar_id)
        connection.account_label = str(
            calendar_item.get("summaryOverride") or calendar_item.get("summary") or connection.account_label or calendar_id
        )
        if connection.color is None:
            connection.color = _validate_hex_color(calendar_item.get("backgroundColor"))

        try:
            events, next_sync_token, full_sync = await _fetch_google_events(access_token, calendar_id, connection.sync_cursor)
        except InvalidGoogleSyncCursor:
            connection.sync_cursor = None
            await db.commit()
            events, next_sync_token, full_sync = await _fetch_google_events(access_token, calendar_id, None)

        resolved_provider_account.status = "active"
        resolved_provider_account.last_error = None
        resolved_provider_account.last_synced_at = utc_now()
        return await reconcile_connection_events(
            db,
            connection,
            events,
            full_sync=full_sync,
            sync_cursor=next_sync_token,
        )
    except CalendarSyncError as error:
        resolved_provider_account.status = "error"
        resolved_provider_account.last_error = str(error)
        await mark_connection_error(db, connection, str(error))
        raise


async def sync_all_google_connections(
    db: AsyncSession,
    *,
    user_id: str | None = None,
) -> list[CalendarConnection]:
    query = (
        select(CalendarConnection, CalendarProviderAccount)
        .join(CalendarProviderAccount, CalendarProviderAccount.id == CalendarConnection.provider_account_id)
        .where(CalendarConnection.provider == "google")
        .order_by(CalendarProviderAccount.id.asc(), CalendarConnection.account_label.asc(), CalendarConnection.created_at.asc())
    )
    if user_id is not None:
        query = query.where(CalendarConnection.user_id == user_id)

    result = await db.execute(query)
    pairs = result.all()
    synced: list[CalendarConnection] = []
    for connection, provider_account in pairs:
        try:
            synced.append(await sync_google_connection(db, connection, provider_account=provider_account))
        except CalendarSyncError:
            await db.refresh(connection)
            synced.append(connection)
    return synced
