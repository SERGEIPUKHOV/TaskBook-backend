from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Response as FastAPIResponse, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import Response
from app.schemas.habit import HabitGridOut, HabitIn, HabitOut, HabitPatch
from app.services.habit_service import (
    create_habit,
    delete_habit_for_month,
    get_month_habit_grid,
    list_month_habits,
    log_habit_completion,
    unlog_habit_completion,
    update_habit,
)

router = APIRouter()


@router.get("/months/{year}/{month}/habits", response_model=Response[list[HabitOut]])
async def read_habits(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[HabitOut]]:
    return Response(data=await list_month_habits(db, current_user.id, year, month))


@router.post("/months/{year}/{month}/habits", response_model=Response[HabitOut], status_code=status.HTTP_201_CREATED)
async def add_habit(
    year: int,
    month: int,
    data: HabitIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[HabitOut]:
    return Response(data=await create_habit(db, current_user.id, year, month, data.name))


@router.patch("/habits/{habit_id}", response_model=Response[HabitOut])
async def rename_habit(
    habit_id: str,
    data: HabitPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[HabitOut]:
    return Response(data=await update_habit(db, current_user.id, habit_id, data.name))


@router.delete("/habits/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_habit(
    habit_id: str,
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await delete_habit_for_month(db, current_user.id, habit_id, year, month)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/habits/{habit_id}/logs/{target_date}", response_model=Response[HabitOut], status_code=status.HTTP_201_CREATED)
async def mark_habit(
    habit_id: str,
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[HabitOut]:
    await log_habit_completion(db, current_user.id, habit_id, target_date)
    habits = await list_month_habits(db, current_user.id, target_date.year, target_date.month)
    habit = next(item for item in habits if item.id == habit_id)
    return Response(data=habit)


@router.delete("/habits/{habit_id}/logs/{target_date}", status_code=status.HTTP_204_NO_CONTENT)
async def unmark_habit(
    habit_id: str,
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await unlog_habit_completion(db, current_user.id, habit_id, target_date)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/months/{year}/{month}/habits/grid", response_model=Response[HabitGridOut])
async def read_habit_grid(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[HabitGridOut]:
    return Response(data=await get_month_habit_grid(db, current_user.id, year, month))
