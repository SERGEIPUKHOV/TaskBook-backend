from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response as FastAPIResponse, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import Response
from app.schemas.task import TaskDayStatusIn, TaskDayStatusOut, TaskOut, TaskPatch
from app.services.task_service import delete_task, delete_task_status, set_task_status, update_task

router = APIRouter()


@router.patch("/{task_id}", response_model=Response[TaskOut])
async def patch_task(
    task_id: str,
    data: TaskPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[TaskOut]:
    return Response(data=await update_task(db, current_user.id, task_id, data))


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
