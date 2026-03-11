from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import Response
from app.schemas.task import ReorderIn, TaskIn, TaskOut
from app.schemas.week import WeekBundleOut, WeekOut, WeekPatch
from app.services.bundle_service import get_week_bundle
from app.services.task_service import create_task, list_week_tasks, reorder_tasks
from app.services.week_service import get_or_create_week, serialize_week, update_week

router = APIRouter()


@router.get("/{year}/{week_number}", response_model=Response[WeekOut])
async def read_week(
    year: int,
    week_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[WeekOut]:
    week = await get_or_create_week(db, current_user.id, year, week_number)
    return Response(data=serialize_week(week))


@router.patch("/{year}/{week_number}", response_model=Response[WeekOut])
async def patch_week(
    year: int,
    week_number: int,
    data: WeekPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[WeekOut]:
    return Response(data=await update_week(db, current_user.id, year, week_number, data))


@router.get("/{year}/{week_number}/tasks", response_model=Response[list[TaskOut]])
async def read_tasks(
    year: int,
    week_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[TaskOut]]:
    return Response(data=await list_week_tasks(db, current_user.id, year, week_number))


@router.post("/{year}/{week_number}/tasks", response_model=Response[TaskOut], status_code=201)
async def add_task(
    year: int,
    week_number: int,
    data: TaskIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[TaskOut]:
    return Response(
        data=await create_task(
            db,
            current_user.id,
            year,
            week_number,
            title=data.title,
            time_planned=data.time_planned,
            time_actual=data.time_actual,
            is_priority=data.is_priority,
            start_day=data.start_day,
        ),
    )


@router.post("/{year}/{week_number}/tasks/reorder", response_model=Response[list[TaskOut]])
async def reorder_week_tasks(
    year: int,
    week_number: int,
    data: ReorderIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[TaskOut]]:
    return Response(data=await reorder_tasks(db, current_user.id, year, week_number, data))


@router.get("/{year}/{week_number}/bundle", response_model=Response[WeekBundleOut])
async def read_bundle(
    year: int,
    week_number: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[WeekBundleOut]:
    return Response(data=await get_week_bundle(db, current_user.id, year, week_number))
