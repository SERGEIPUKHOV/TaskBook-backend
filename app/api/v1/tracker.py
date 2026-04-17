from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response as FastAPIResponse, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import Response
from app.schemas.tracker import (
    TrackerDeadlineOut,
    TrackerGoalCreate,
    TrackerGoalOut,
    TrackerGoalPatch,
    TrackerSprintCreate,
    TrackerSprintOut,
    TrackerSprintPatch,
)
from app.services.tracker_service import (
    create_goal,
    create_sprint,
    delete_goal,
    delete_sprint,
    get_deadlines_for_date,
    get_deadlines_for_week,
    list_goals,
    list_sprints,
    patch_goal,
    patch_sprint,
)

router = APIRouter(prefix="/tracker", tags=["tracker"])


def require_tasktracker(request: Request, current_user: User = Depends(get_current_user)) -> User:
    if getattr(request.state, "view_as_enabled", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещён")
    if not current_user.tasktracker_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="TaskTracker not enabled")
    return current_user


@router.get("/sprints", response_model=Response[list[TrackerSprintOut]])
async def read_sprints(
    current_user: User = Depends(require_tasktracker),
    db: AsyncSession = Depends(get_db),
) -> Response[list[TrackerSprintOut]]:
    return Response(data=await list_sprints(db, current_user.id))


@router.post("/sprints", response_model=Response[TrackerSprintOut], status_code=status.HTTP_201_CREATED)
async def add_sprint(
    data: TrackerSprintCreate,
    current_user: User = Depends(require_tasktracker),
    db: AsyncSession = Depends(get_db),
) -> Response[TrackerSprintOut]:
    return Response(data=await create_sprint(db, current_user.id, data))


@router.patch("/sprints/{sprint_id}", response_model=Response[TrackerSprintOut])
async def update_sprint(
    sprint_id: str,
    data: TrackerSprintPatch,
    current_user: User = Depends(require_tasktracker),
    db: AsyncSession = Depends(get_db),
) -> Response[TrackerSprintOut]:
    return Response(data=await patch_sprint(db, current_user.id, sprint_id, data))


@router.delete("/sprints/{sprint_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_sprint(
    sprint_id: str,
    current_user: User = Depends(require_tasktracker),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await delete_sprint(db, current_user.id, sprint_id)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sprints/{sprint_id}/goals", response_model=Response[list[TrackerGoalOut]])
async def read_goals(
    sprint_id: str,
    current_user: User = Depends(require_tasktracker),
    db: AsyncSession = Depends(get_db),
) -> Response[list[TrackerGoalOut]]:
    return Response(data=await list_goals(db, current_user.id, sprint_id))


@router.post("/sprints/{sprint_id}/goals", response_model=Response[TrackerGoalOut], status_code=status.HTTP_201_CREATED)
async def add_goal(
    sprint_id: str,
    data: TrackerGoalCreate,
    current_user: User = Depends(require_tasktracker),
    db: AsyncSession = Depends(get_db),
) -> Response[TrackerGoalOut]:
    return Response(data=await create_goal(db, current_user.id, sprint_id, data))


@router.patch("/goals/{goal_id}", response_model=Response[TrackerGoalOut])
async def update_goal(
    goal_id: str,
    data: TrackerGoalPatch,
    current_user: User = Depends(require_tasktracker),
    db: AsyncSession = Depends(get_db),
) -> Response[TrackerGoalOut]:
    return Response(data=await patch_goal(db, current_user.id, goal_id, data))


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_goal(
    goal_id: str,
    current_user: User = Depends(require_tasktracker),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await delete_goal(db, current_user.id, goal_id)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/deadlines/week", response_model=Response[list[TrackerDeadlineOut]])
async def read_week_deadlines(
    week_year: int = Query(...),
    week_num: int = Query(...),
    current_user: User = Depends(require_tasktracker),
    db: AsyncSession = Depends(get_db),
) -> Response[list[TrackerDeadlineOut]]:
    return Response(data=await get_deadlines_for_week(db, current_user.id, week_year, week_num))


@router.get("/deadlines/day", response_model=Response[list[TrackerDeadlineOut]])
async def read_day_deadlines(
    target_date: date = Query(..., alias="date"),
    current_user: User = Depends(require_tasktracker),
    db: AsyncSession = Depends(get_db),
) -> Response[list[TrackerDeadlineOut]]:
    return Response(data=await get_deadlines_for_date(db, current_user.id, target_date))
