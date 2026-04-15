from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response as FastAPIResponse, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import Response
from app.schemas.habit import LinkedEventTimeOut
from app.schemas.task import TaskCalendarExportBody, TaskDayStatusIn, TaskDayStatusOut, TaskEventTimePatch, TaskOut, TaskPatch
from app.services.calendar_sync_service import CalendarSyncError
from app.services.calendar_write_service import (
    push_task_event_time_to_google,
    push_task_title_to_google,
    push_task_to_google,
    unlink_task_from_google,
)
from app.services.task_service import delete_task, delete_task_status, set_task_status, update_task, update_task_event_time

router = APIRouter()


@router.patch("/{task_id}", response_model=Response[TaskOut])
async def patch_task(
    task_id: str,
    data: TaskPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[TaskOut]:
    task = await update_task(db, current_user.id, task_id, data)
    if data.title is not None:
        try:
            await push_task_title_to_google(db, current_user.id, task_id, task.title)
        except Exception:
            pass
    return Response(data=task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await delete_task(db, current_user.id, task_id)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/{task_id}/status/{target_date}", response_model=Response[TaskDayStatusOut])
async def put_task_status(
    task_id: str,
    target_date: date,
    data: TaskDayStatusIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[TaskDayStatusOut]:
    return Response(data=await set_task_status(db, current_user.id, task_id, target_date, data.status))


@router.delete("/{task_id}/status/{target_date}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_task_status(
    task_id: str,
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await delete_task_status(db, current_user.id, task_id, target_date)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{task_id}/calendar-export", response_model=Response[dict])
async def export_task_to_calendar(
    task_id: str,
    body: TaskCalendarExportBody,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[dict]:
    try:
        external_event_id = await push_task_to_google(db, current_user.id, task_id, body.connection_id)
    except CalendarSyncError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return Response(data={"external_event_id": external_event_id, "linked_event_time": None})


@router.delete("/{task_id}/calendar-export", status_code=status.HTTP_204_NO_CONTENT)
async def unlink_task_from_calendar(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await unlink_task_from_google(db, current_user.id, task_id)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{task_id}/event-time", response_model=Response[LinkedEventTimeOut])
async def patch_task_event_time(
    task_id: str,
    body: TaskEventTimePatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[LinkedEventTimeOut]:
    linked_time = await update_task_event_time(db, current_user.id, task_id, body.starts_hhmm, body.ends_hhmm)
    if linked_time is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No linked calendar event found")
    try:
        await push_task_event_time_to_google(db, current_user.id, task_id, body.starts_hhmm, body.ends_hhmm)
    except Exception:
        pass
    return Response(data=linked_time)
