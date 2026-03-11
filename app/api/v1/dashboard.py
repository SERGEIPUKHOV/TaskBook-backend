from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import Response
from app.schemas.dashboard import DashboardOut
from app.services.dashboard_service import get_dashboard

router = APIRouter()


@router.get("", response_model=Response[DashboardOut])
async def read_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[DashboardOut]:
    return Response(data=await get_dashboard(db, current_user.id))
