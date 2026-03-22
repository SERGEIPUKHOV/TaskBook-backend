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

# BLOCK-START: HABITS_API_MODULE
# Description: Habit CRUD and logging endpoints for authenticated users.
router = APIRouter()


# BLOCK-START: HABITS_CRUD_ENDPOINTS
# Description: Month-scoped habit listing and create/update/delete operations.
@router.get("/months/{year}/{month}/habits", response_model=Response[list[HabitOut]])
async def read_habits(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[HabitOut]]:
    """
    function_contracts:
      read_habits:
        description: "Lists habits configured for one month for the current user."
        preconditions:
          - "year/month identify a calendar month"
          - "current_user is authenticated"
        postconditions:
          - "Returns zero or more HabitOut items for the selected month"
    """
    return Response(data=await list_month_habits(db, current_user.id, year, month))


@router.post("/months/{year}/{month}/habits", response_model=Response[HabitOut], status_code=status.HTTP_201_CREATED)
async def add_habit(
    year: int,
    month: int,
    data: HabitIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[HabitOut]:
    """
    function_contracts:
      add_habit:
        description: "Creates a new month-scoped habit for the current user."
        preconditions:
          - "year/month identify a calendar month"
          - "data.name contains validated habit name"
        postconditions:
          - "Returns the created HabitOut"
          - "Persists the new habit for the selected month"
    """
    return Response(data=await create_habit(db, current_user.id, year, month, data.name))


@router.patch("/habits/{habit_id}", response_model=Response[HabitOut])
async def rename_habit(
    habit_id: str,
    data: HabitPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[HabitOut]:
    """
    function_contracts:
      rename_habit:
        description: "Renames one existing habit owned by the current user."
        preconditions:
          - "habit_id identifies an existing user-owned habit"
          - "data.name contains validated replacement habit name"
        postconditions:
          - "Returns the updated HabitOut"
          - "404 when the habit is missing"
    """
    return Response(data=await update_habit(db, current_user.id, habit_id, data.name))


@router.delete("/habits/{habit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_habit(
    habit_id: str,
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    """
    function_contracts:
      remove_habit:
        description: "Deletes one month-scoped habit owned by the current user."
        preconditions:
          - "habit_id identifies an existing user-owned habit"
          - "year/month identify the month context for deletion"
        postconditions:
          - "Deletes the habit entry for the selected month"
          - "Returns empty HTTP 204 response"
    """
    await delete_habit_for_month(db, current_user.id, habit_id, year, month)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)
# BLOCK-END: HABITS_CRUD_ENDPOINTS


# BLOCK-START: HABIT_LOG_ENDPOINTS
# Description: Mark and unmark habit completion for a concrete date.
@router.post("/habits/{habit_id}/logs/{target_date}", response_model=Response[HabitOut], status_code=status.HTTP_201_CREATED)
async def mark_habit(
    habit_id: str,
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[HabitOut]:
    """
    function_contracts:
      mark_habit:
        description: "Marks one habit as completed for a concrete date and returns refreshed month habit state."
        preconditions:
          - "habit_id identifies an existing user-owned habit"
          - "target_date is a valid ISO date"
        postconditions:
          - "Stores completion log for the target date"
          - "Returns HabitOut reflecting the updated completion state"
    """
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
    """
    function_contracts:
      unmark_habit:
        description: "Removes one habit completion log for a concrete date."
        preconditions:
          - "habit_id identifies an existing user-owned habit"
          - "target_date is a valid ISO date"
        postconditions:
          - "Deletes the completion log when present"
          - "Returns empty HTTP 204 response"
    """
    await unlog_habit_completion(db, current_user.id, habit_id, target_date)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)
# BLOCK-END: HABIT_LOG_ENDPOINTS


# BLOCK-START: HABIT_GRID_ENDPOINT
# Description: Returns month habit grid projection for frontend consumption.
@router.get("/months/{year}/{month}/habits/grid", response_model=Response[HabitGridOut])
async def read_habit_grid(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[HabitGridOut]:
    """
    function_contracts:
      read_habit_grid:
        description: "Returns month habit grid projection for frontend board rendering."
        preconditions:
          - "year/month identify a calendar month"
          - "current_user is authenticated"
        postconditions:
          - "Returns HabitGridOut with month days and habit completion matrix"
    """
    return Response(data=await get_month_habit_grid(db, current_user.id, year, month))
# BLOCK-END: HABIT_GRID_ENDPOINT
# BLOCK-END: HABITS_API_MODULE
