from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response as FastAPIResponse, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.common import Response
from app.schemas.supervision import GrantedOwnerOut, SupervisorGrantCreate, SupervisorGrantOut, SupervisorGrantPatch
from app.services.supervision_service import add_grant, list_granted_owners, list_my_grants, patch_grant, revoke_grant

router = APIRouter(prefix="/supervision", tags=["supervision"])


@router.get("/grants", response_model=Response[list[SupervisorGrantOut]])
async def read_grants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[SupervisorGrantOut]]:
    return Response(data=await list_my_grants(db, current_user.id))


@router.post("/grants", response_model=Response[SupervisorGrantOut])
async def create_grant(
    data: SupervisorGrantCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[SupervisorGrantOut]:
    try:
        grant = await add_grant(
            db,
            owner_id=current_user.id,
            owner_email=current_user.email,
            supervisor_email=data.supervisor_email,
            sections=data.sections,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return Response(data=grant)


@router.patch("/grants/{grant_id}", response_model=Response[SupervisorGrantOut])
async def update_grant(
    grant_id: str,
    data: SupervisorGrantPatch,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[SupervisorGrantOut]:
    grant = await patch_grant(db, grant_id=grant_id, owner_id=current_user.id, sections=data.sections)
    if grant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Доступ не найден")
    return Response(data=grant)


@router.delete("/grants/{grant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_grant(
    grant_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FastAPIResponse:
    deleted = await revoke_grant(db, grant_id=grant_id, owner_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Доступ не найден")
    return FastAPIResponse(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/owners", response_model=Response[list[GrantedOwnerOut]])
async def read_granted_owners(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response[list[GrantedOwnerOut]]:
    rows = await list_granted_owners(db, current_user.id)
    return Response(
        data=[
            GrantedOwnerOut(
                owner_id=row["owner"].id,
                owner_email=row["owner"].email,
                sections=row["grant"].sections,
            )
            for row in rows
        ]
    )
