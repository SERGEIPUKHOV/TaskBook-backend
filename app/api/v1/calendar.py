from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, Response as FastAPIResponse, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_subject_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.calendar import (
    AppleIcsConnectionIn,
    CalendarConnectionOut,
    CalendarEventImportIn,
    CalendarEventImportOut,
    CalendarEventsRangeOut,
    CalendarTaskFeedLinkOut,
    GoogleAuthSessionIn,
    GoogleAuthSessionOut,
    GoogleCalendarOptionsOut,
    GoogleCalendarSelectionIn,
    UpdateConnectionColorIn,
)
from app.schemas.common import Response
from app.schemas.task import TaskCalendarExportBucket
from app.services.calendar_service import (
    complete_google_auth_callback,
    create_google_auth_redirect,
    create_or_sync_apple_connection,
    delete_calendar_connection,
    disconnect_google_provider_account,
    import_event_into_planner,
    list_calendar_connections,
    list_calendar_events_range,
    list_task_feeds,
    read_google_calendar_options,
    read_task_feed_ics,
    sync_calendar_connection,
    sync_all_google_calendar_connections,
    update_google_calendar_selections,
    update_calendar_connection_color,
)

router = APIRouter()


@router.get("/connections", response_model=Response[list[CalendarConnectionOut]])
async def read_connections(
    current_user: User = Depends(get_subject_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[CalendarConnectionOut]]:
    return Response(data=await list_calendar_connections(db, current_user.id))


@router.post("/google/auth-session", response_model=Response[GoogleAuthSessionOut])
async def start_google_auth_session(
    data: GoogleAuthSessionIn,
    current_user: User = Depends(get_current_user),
) -> Response[GoogleAuthSessionOut]:
    authorize_url, ttl = await create_google_auth_redirect(current_user.id, data.return_to)
    return Response(data=GoogleAuthSessionOut(authorize_url=authorize_url, state_expires_in=ttl))


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    return RedirectResponse(url=await complete_google_auth_callback(db, code, state), status_code=status.HTTP_302_FOUND)


@router.get("/google/calendars", response_model=Response[GoogleCalendarOptionsOut])
async def read_google_calendars(
    current_user: User = Depends(get_subject_user),
    db: AsyncSession = Depends(get_db),
) -> Response[GoogleCalendarOptionsOut]:
    return Response(data=await read_google_calendar_options(db, current_user.id))


@router.put("/google/selections", response_model=Response[list[CalendarConnectionOut]])
async def save_google_selections(
    data: GoogleCalendarSelectionIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[CalendarConnectionOut]]:
    return Response(data=await update_google_calendar_selections(db, current_user.id, data.calendar_ids))


@router.post("/google/sync-all", response_model=Response[list[CalendarConnectionOut]])
async def sync_all_google_connections(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[CalendarConnectionOut]]:
    return Response(data=await sync_all_google_calendar_connections(db, current_user.id))


@router.delete("/google/account", status_code=status.HTTP_204_NO_CONTENT)
async def remove_google_account(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await disconnect_google_provider_account(db, current_user.id)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/apple-ics/connections", response_model=Response[CalendarConnectionOut])
async def create_apple_connection(
    data: AppleIcsConnectionIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[CalendarConnectionOut]:
    return Response(
        data=await create_or_sync_apple_connection(
            db,
            current_user.id,
            ics_url=data.ics_url,
            account_label=data.account_label,
        ),
    )


@router.post("/connections/{connection_id}/sync", response_model=Response[CalendarConnectionOut])
async def sync_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[CalendarConnectionOut]:
    return Response(data=await sync_calendar_connection(db, current_user.id, connection_id))


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_connection(
    connection_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await delete_calendar_connection(db, current_user.id, connection_id)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/connections/{connection_id}/color", response_model=Response[CalendarConnectionOut])
async def patch_connection_color(
    connection_id: str,
    data: UpdateConnectionColorIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[CalendarConnectionOut]:
    return Response(data=await update_calendar_connection_color(db, current_user.id, connection_id, data))


@router.get("/events", response_model=Response[CalendarEventsRangeOut])
async def read_events(
    date_from: date = Query(...),
    date_to: date = Query(...),
    current_user: User = Depends(get_subject_user),
    db: AsyncSession = Depends(get_db),
) -> Response[CalendarEventsRangeOut]:
    return Response(data=await list_calendar_events_range(db, current_user.id, date_from=date_from, date_to=date_to))


@router.post("/events/{event_id}/import", response_model=Response[CalendarEventImportOut])
async def import_event(
    event_id: str,
    data: CalendarEventImportIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[CalendarEventImportOut]:
    return Response(data=await import_event_into_planner(db, current_user.id, event_id, data))


@router.get("/feeds/tasks/links", response_model=Response[list[CalendarTaskFeedLinkOut]])
async def read_task_feed_links(
    current_user: User = Depends(get_subject_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[CalendarTaskFeedLinkOut]]:
    return Response(data=await list_task_feeds(db, current_user.id))


@router.get("/feeds/tasks/{token}.ics")
async def read_tasks_feed(
    token: str,
    bucket: TaskCalendarExportBucket | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    payload = await read_task_feed_ics(db, token=token, bucket=bucket)
    filename = f"taskbook-tasks{f'-{bucket}' if bucket else ''}.ics"
    return FastAPIResponse(
        content=payload,
        media_type="text/calendar; charset=utf-8",
        headers={
            "Cache-Control": "private, max-age=300",
            "Content-Disposition": f'inline; filename="{filename}"',
        },
    )
