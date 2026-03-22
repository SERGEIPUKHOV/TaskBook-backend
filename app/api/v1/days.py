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

# BLOCK-START: DAYS_API_MODULE
# Description: Day bundle, key events, and gratitude endpoints for authenticated users.
router = APIRouter()


# BLOCK-START: DAY_BUNDLE_ENDPOINT
# Description: Returns a day bundle for a concrete calendar date.
@router.get("/{year}/{month}/{day}/bundle", response_model=Response[DayBundleOut])
async def read_day_bundle(
    year: int,
    month: int,
    day: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[DayBundleOut]:
    """
    function_contracts:
      read_day_bundle:
        description: "Returns the aggregated day bundle for one calendar date owned by the current user."
        preconditions:
          - "year/month/day compose a valid calendar date"
          - "current_user is authenticated"
        postconditions:
          - "Returns DayBundleOut for the requested date"
          - "422 when the provided date is invalid"
    """
    try:
        target_date = date(year, month, day)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid date") from exc

    return Response(data=await get_day_bundle(db, current_user.id, target_date))
# BLOCK-END: DAY_BUNDLE_ENDPOINT


# BLOCK-START: DAY_KEY_EVENTS_ENDPOINTS
# Description: CRUD endpoints for key events attached to a specific day.
@router.get("/{target_date}/events", response_model=Response[list[KeyEventOut]])
async def read_events(
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[KeyEventOut]]:
    """
    function_contracts:
      read_events:
        description: "Lists key events recorded by the current user for one day."
        preconditions:
          - "target_date is a valid ISO date from the route"
          - "current_user is authenticated"
        postconditions:
          - "Returns zero or more KeyEventOut items for the target date"
    """
    return Response(data=await list_key_events(db, current_user.id, target_date))


@router.post("/{target_date}/events", response_model=Response[KeyEventOut], status_code=201)
async def add_event(
    target_date: date,
    data: KeyEventIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[KeyEventOut]:
    """
    function_contracts:
      add_event:
        description: "Creates one key event for the current user on the given date."
        preconditions:
          - "target_date is a valid ISO date"
          - "data.content contains validated event text"
        postconditions:
          - "Returns the created KeyEventOut"
          - "Persists the new event for the current user only"
    """
    return Response(data=await create_key_event(db, current_user.id, target_date, data.content))


@router.patch("/events/{event_id}", response_model=Response[KeyEventOut])
async def patch_event(
    event_id: str,
    data: KeyEventIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[KeyEventOut]:
    """
    function_contracts:
      patch_event:
        description: "Updates one existing key event owned by the current user."
        preconditions:
          - "event_id identifies an existing user-owned key event"
          - "data.content contains replacement event text"
        postconditions:
          - "Returns the updated KeyEventOut"
          - "404 when the event is missing"
    """
    return Response(data=await update_key_event(db, current_user.id, event_id, data.content))


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_event(
    event_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    """
    function_contracts:
      remove_event:
        description: "Deletes one key event owned by the current user."
        preconditions:
          - "event_id identifies an existing user-owned key event"
        postconditions:
          - "Deletes the event when found"
          - "Returns empty HTTP 204 response"
    """
    await delete_key_event(db, current_user.id, event_id)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)
# BLOCK-END: DAY_KEY_EVENTS_ENDPOINTS


# BLOCK-START: DAY_GRATITUDES_ENDPOINTS
# Description: CRUD endpoints for gratitude entries attached to a specific day.
@router.get("/{target_date}/gratitudes", response_model=Response[list[GratitudeOut]])
async def read_gratitudes(
    target_date: date,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[GratitudeOut]]:
    """
    function_contracts:
      read_gratitudes:
        description: "Lists gratitude entries recorded by the current user for one day."
        preconditions:
          - "target_date is a valid ISO date from the route"
          - "current_user is authenticated"
        postconditions:
          - "Returns zero or more GratitudeOut items for the target date"
    """
    return Response(data=await list_gratitudes(db, current_user.id, target_date))


@router.post("/{target_date}/gratitudes", response_model=Response[GratitudeOut], status_code=201)
async def add_gratitude(
    target_date: date,
    data: GratitudeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[GratitudeOut]:
    """
    function_contracts:
      add_gratitude:
        description: "Creates one gratitude entry for the current user on the given date."
        preconditions:
          - "target_date is a valid ISO date"
          - "data.content contains validated gratitude text"
        postconditions:
          - "Returns the created GratitudeOut"
          - "Persists the new gratitude for the current user only"
    """
    return Response(data=await create_gratitude(db, current_user.id, target_date, data.content))


@router.patch("/gratitudes/{gratitude_id}", response_model=Response[GratitudeOut])
async def patch_gratitude(
    gratitude_id: str,
    data: GratitudeIn,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[GratitudeOut]:
    """
    function_contracts:
      patch_gratitude:
        description: "Updates one existing gratitude entry owned by the current user."
        preconditions:
          - "gratitude_id identifies an existing user-owned gratitude entry"
          - "data.content contains replacement gratitude text"
        postconditions:
          - "Returns the updated GratitudeOut"
          - "404 when the gratitude entry is missing"
    """
    return Response(data=await update_gratitude(db, current_user.id, gratitude_id, data.content))


@router.delete("/gratitudes/{gratitude_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_gratitude(
    gratitude_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    """
    function_contracts:
      remove_gratitude:
        description: "Deletes one gratitude entry owned by the current user."
        preconditions:
          - "gratitude_id identifies an existing user-owned gratitude entry"
        postconditions:
          - "Deletes the gratitude entry when found"
          - "Returns empty HTTP 204 response"
    """
    await delete_gratitude(db, current_user.id, gratitude_id)
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)
# BLOCK-END: DAY_GRATITUDES_ENDPOINTS
# BLOCK-END: DAYS_API_MODULE
