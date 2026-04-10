from __future__ import annotations

from datetime import date
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.calendar_connection import CalendarConnection
from app.models.calendar_event import CalendarEvent
from app.models.calendar_provider_account import CalendarProviderAccount
from app.schemas.calendar import (
    CalendarEventImportIn,
    CalendarEventImportOut,
    CalendarConnectionOut,
    CalendarEventsRangeOut,
    CalendarTaskFeedLinkOut,
    GoogleCalendarOptionsOut,
    UpdateConnectionColorIn,
)
from app.services.calendar_bridge_service import import_calendar_event_to_planner
from app.services.calendar_google_service import (
    exchange_google_code_for_tokens,
    disconnect_google_account,
    get_google_provider_account,
    list_google_calendar_options,
    save_google_calendar_selections,
    sync_all_google_connections,
    store_google_tokens,
    sync_google_connection,
)
from app.services.calendar_ics_service import get_or_create_apple_connection, sync_apple_connection
from app.services.calendar_task_export_service import list_task_export_feed_links, render_task_feed_ics
from app.services.calendar_oauth_service import (
    CalendarOAuthError,
    consume_google_auth_state,
    create_google_auth_session,
)
from app.services.calendar_sync_service import CalendarSyncError, connection_to_schema, list_connection_events_in_range


def append_redirect_status(return_to: str, provider: str, status_value: str, message: str | None = None) -> str:
    parsed = urlsplit(return_to)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({"calendar_provider": provider, "calendar_status": status_value})
    if message:
        query["calendar_message"] = message
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


async def list_calendar_connections(db: AsyncSession, user_id: str) -> list[CalendarConnectionOut]:
    result = await db.execute(
        select(CalendarConnection, CalendarProviderAccount)
        .outerjoin(CalendarProviderAccount, CalendarProviderAccount.id == CalendarConnection.provider_account_id)
        .where(CalendarConnection.user_id == user_id)
        .order_by(CalendarConnection.provider.asc(), CalendarConnection.created_at.asc()),
    )
    return [
        connection_to_schema(connection, provider_account)
        for connection, provider_account in result.all()
    ]


async def create_google_auth_redirect(user_id: str, return_to: str | None) -> tuple[str, int]:
    try:
        return await create_google_auth_session(user_id, return_to)
    except CalendarOAuthError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error


async def complete_google_auth_callback(db: AsyncSession, code: str, state: str) -> str:
    try:
        oauth_state = await consume_google_auth_state(state)
    except CalendarOAuthError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    try:
        token_payload = await exchange_google_code_for_tokens(code)
        await store_google_tokens(db, oauth_state.user_id, token_payload)
        await list_google_calendar_options(db, oauth_state.user_id)
        return append_redirect_status(oauth_state.return_to, "google", "connected")
    except (CalendarOAuthError, CalendarSyncError) as error:
        return append_redirect_status(oauth_state.return_to, "google", "error", str(error))


async def read_google_calendar_options(db: AsyncSession, user_id: str) -> GoogleCalendarOptionsOut:
    try:
        return await list_google_calendar_options(db, user_id)
    except CalendarSyncError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


async def update_google_calendar_selections(
    db: AsyncSession,
    user_id: str,
    calendar_ids: list[str],
) -> list[CalendarConnectionOut]:
    try:
        connections = await save_google_calendar_selections(db, user_id, calendar_ids)
    except CalendarSyncError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    provider_account = await get_google_provider_account(db, user_id)
    return [connection_to_schema(connection, provider_account) for connection in connections]


async def sync_all_google_calendar_connections(db: AsyncSession, user_id: str) -> list[CalendarConnectionOut]:
    connections = await sync_all_google_connections(db, user_id=user_id)
    provider_account = await get_google_provider_account(db, user_id)
    return [connection_to_schema(connection, provider_account) for connection in connections]


async def disconnect_google_provider_account(db: AsyncSession, user_id: str) -> None:
    await disconnect_google_account(db, user_id)


async def create_or_sync_apple_connection(
    db: AsyncSession,
    user_id: str,
    *,
    ics_url: str,
    account_label: str | None,
) -> CalendarConnectionOut:
    connection = await get_or_create_apple_connection(db, user_id, ics_url=ics_url, account_label=account_label)
    try:
        connection = await sync_apple_connection(db, connection)
    except CalendarSyncError:
        await db.refresh(connection)
    return connection_to_schema(connection, None)


async def get_calendar_connection_for_user(db: AsyncSession, user_id: str, connection_id: str) -> CalendarConnection:
    result = await db.execute(
        select(CalendarConnection).where(
            CalendarConnection.id == connection_id,
            CalendarConnection.user_id == user_id,
        ),
    )
    connection = result.scalar_one_or_none()
    if connection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Calendar connection not found")
    return connection


async def sync_calendar_connection(db: AsyncSession, user_id: str, connection_id: str) -> CalendarConnectionOut:
    connection = await get_calendar_connection_for_user(db, user_id, connection_id)
    provider_account = None
    try:
        if connection.provider == "google":
            connection = await sync_google_connection(db, connection)
            if connection.provider_account_id:
                result = await db.execute(
                    select(CalendarProviderAccount).where(CalendarProviderAccount.id == connection.provider_account_id),
                )
                provider_account = result.scalar_one_or_none()
        elif connection.provider == "apple":
            connection = await sync_apple_connection(db, connection)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported calendar provider")
    except CalendarSyncError as error:
        await db.refresh(connection)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error

    return connection_to_schema(connection, provider_account)


async def delete_calendar_connection(db: AsyncSession, user_id: str, connection_id: str) -> None:
    connection = await get_calendar_connection_for_user(db, user_id, connection_id)
    await db.execute(delete(CalendarEvent).where(CalendarEvent.connection_id == connection.id))
    await db.delete(connection)
    await db.commit()


async def update_calendar_connection_color(
    db: AsyncSession,
    user_id: str,
    connection_id: str,
    body: UpdateConnectionColorIn,
) -> CalendarConnectionOut:
    connection = await get_calendar_connection_for_user(db, user_id, connection_id)
    provider_account = None
    if connection.provider_account_id:
        result = await db.execute(
            select(CalendarProviderAccount).where(CalendarProviderAccount.id == connection.provider_account_id),
        )
        provider_account = result.scalar_one_or_none()

    connection.color = body.color.upper()
    await db.commit()
    await db.refresh(connection)
    return connection_to_schema(connection, provider_account)


async def list_calendar_events_range(
    db: AsyncSession,
    user_id: str,
    *,
    date_from: date,
    date_to: date,
) -> CalendarEventsRangeOut:
    if date_to < date_from:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="date_to must be >= date_from")

    events = await list_connection_events_in_range(db, user_id, date_from, date_to)
    return CalendarEventsRangeOut(date_from=date_from, date_to=date_to, events=events)


async def import_event_into_planner(
    db: AsyncSession,
    user_id: str,
    event_id: str,
    payload: CalendarEventImportIn,
) -> CalendarEventImportOut:
    return await import_calendar_event_to_planner(db, user_id, event_id, payload)


async def list_task_feeds(
    db: AsyncSession,
    user_id: str,
) -> list[CalendarTaskFeedLinkOut]:
    return await list_task_export_feed_links(db, user_id)


async def read_task_feed_ics(
    db: AsyncSession,
    *,
    token: str,
    bucket: str | None,
) -> bytes:
    return await render_task_feed_ics(db, token=token, bucket=bucket)
