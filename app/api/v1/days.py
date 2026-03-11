from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response as FastAPIResponse, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import Response
from app.schemas.day import DayBundleOut
from app.schemas.day_entry import GratitudeIn, GratitudeOut, KeyEventIn, KeyEventOut
from app.services.day_service import get_day_bundle
from app.services.day_entry_service import (
    create_gratitude,
    create_key_event,
    delete_gratitude,
    delete_key_event,
    list_gratitudes,
    list_key_events,
    update_gratitude,
    update_key_event,
)

router = APIRouter()


@router.get("/{year}/{month}/{day}/bundle", response_model=Response[DayBundleOut])
async def read_day_bundle(
    year: int,
    month: int,
    day: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[DayBundleOut]:
    try:
        target_date = date(year, month, day)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid date") from exc

    return Response(data=await get_day_bundle(db, current_user.id, target_date))


@router.get("/{target_date}/events", response_model=Response[list[KeyEventOut]])
async def read_events(
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[KeyEventOut]]:
    return Response(data=await list_key_events(db, current_user.id, target_date))


@router.post("/{target_date}/events", response_model=Response[KeyEventOut], status_code=201)
async def add_event(
    target_date: date,
    data: KeyEventIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[KeyEventOut]:
    return Response(data=await create_key_event(db, current_user.id, target_date, data.content))


@router.patch("/events/{event_id}", response_model=Response[KeyEventOut])
async def patch_event(
    event_id: str,
    data: KeyEventIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[KeyEventOut]:
    return Response(data=await update_key_event(db, current_user.id, event_id, data.content))


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await delete_key_event(db, current_user.id, event_id)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{target_date}/gratitudes", response_model=Response[list[GratitudeOut]])
async def read_gratitudes(
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[GratitudeOut]]:
    return Response(data=await list_gratitudes(db, current_user.id, target_date))


@router.post("/{target_date}/gratitudes", response_model=Response[GratitudeOut], status_code=201)
async def add_gratitude(
    target_date: date,
    data: GratitudeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[GratitudeOut]:
    return Response(data=await create_gratitude(db, current_user.id, target_date, data.content))


@router.patch("/gratitudes/{gratitude_id}", response_model=Response[GratitudeOut])
async def patch_gratitude(
    gratitude_id: str,
    data: GratitudeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[GratitudeOut]:
    return Response(data=await update_gratitude(db, current_user.id, gratitude_id, data.content))


@router.delete("/gratitudes/{gratitude_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_gratitude(
    gratitude_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    await delete_gratitude(db, current_user.id, gratitude_id)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)
