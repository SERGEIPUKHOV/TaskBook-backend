from __future__ import annotations

from fastapi import APIRouter, Depends, Response as FastAPIResponse, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import Response
from app.schemas.daily_state import DailyStateIn, DailyStateOut
from app.schemas.month import MonthBundleOut, MonthPlanIn, MonthPlanOut
from app.services.bundle_service import get_month_bundle
from app.services.daily_state_service import delete_daily_state, get_month_states, upsert_daily_state
from app.services.month_service import get_month_plan, upsert_month_plan

router = APIRouter()


@router.get("/{year}/{month}/plan", response_model=Response[MonthPlanOut | None])
async def read_plan(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[MonthPlanOut | None]:
    return Response(data=await get_month_plan(db, current_user.id, year, month))


@router.post("/{year}/{month}/plan", response_model=Response[MonthPlanOut])
async def write_plan(
    year: int,
    month: int,
    data: MonthPlanIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[MonthPlanOut]:
    return Response(data=await upsert_month_plan(db, current_user.id, year, month, data))


@router.get("/{year}/{month}/states", response_model=Response[list[DailyStateOut]])
async def read_states(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[DailyStateOut]]:
    return Response(data=await get_month_states(db, current_user.id, year, month))


@router.put("/{year}/{month}/states/{day}", response_model=Response[DailyStateOut])
async def write_state(
    year: int,
    month: int,
    day: int,
    data: DailyStateIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[DailyStateOut]:
    return Response(data=await upsert_daily_state(db, current_user.id, year, month, day, data))


@router.delete("/{year}/{month}/states/{day}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_state(
    year: int,
    month: int,
    day: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await delete_daily_state(db, current_user.id, year, month, day)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{year}/{month}/bundle", response_model=Response[MonthBundleOut])
async def read_bundle(
    year: int,
    month: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[MonthBundleOut]:
    return Response(data=await get_month_bundle(db, current_user.id, year, month))
