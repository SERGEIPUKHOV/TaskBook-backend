from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import Response
from app.schemas.user import UserOut

router = APIRouter()


@router.get("/me", response_model=Response[UserOut])
async def get_me(current_user: User = Depends(get_current_user)) -> Response[UserOut]:
    return Response(data=UserOut.model_validate(current_user))
