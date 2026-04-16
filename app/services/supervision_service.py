from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supervisor_grant import SupervisorGrant
from app.models.user import User


async def list_my_grants(db: AsyncSession, owner_id: str) -> list[SupervisorGrant]:
    result = await db.execute(
        select(SupervisorGrant)
        .where(SupervisorGrant.owner_id == owner_id)
        .order_by(SupervisorGrant.created_at.desc())
    )
    return list(result.scalars().all())


async def list_granted_owners(db: AsyncSession, supervisor_id: str) -> list[dict[str, object]]:
    result = await db.execute(
        select(SupervisorGrant, User)
        .join(User, User.id == SupervisorGrant.owner_id)
        .where(
            SupervisorGrant.supervisor_id == supervisor_id,
            SupervisorGrant.status == "active",
            SupervisorGrant.owner_id != supervisor_id,
            User.is_active.is_(True),
        )
        .order_by(User.email.asc())
    )
    return [{"grant": grant, "owner": owner} for grant, owner in result.all()]


async def add_grant(
    db: AsyncSession,
    *,
    owner_id: str,
    owner_email: str,
    supervisor_email: str,
    sections: list[str],
) -> SupervisorGrant:
    normalized_email = supervisor_email.strip().lower()
    if normalized_email == owner_email.strip().lower():
        raise ValueError("Нельзя добавить себя как супервайзера")

    supervisor_result = await db.execute(select(User).where(User.email == normalized_email))
    supervisor = supervisor_result.scalar_one_or_none()

    existing_result = await db.execute(
        select(SupervisorGrant).where(
            SupervisorGrant.owner_id == owner_id,
            SupervisorGrant.supervisor_email == normalized_email,
        )
    )
    grant = existing_result.scalar_one_or_none()

    if grant is None:
        grant = SupervisorGrant(
            owner_id=owner_id,
            supervisor_email=normalized_email,
        )
        db.add(grant)

    grant.sections = list(dict.fromkeys(sections))
    grant.supervisor_id = supervisor.id if supervisor and supervisor.is_active else None
    grant.status = "active" if supervisor and supervisor.is_active else "pending"
    await db.commit()
    await db.refresh(grant)
    return grant


async def patch_grant(
    db: AsyncSession,
    *,
    grant_id: str,
    owner_id: str,
    sections: list[str],
) -> SupervisorGrant | None:
    result = await db.execute(
        select(SupervisorGrant).where(
            SupervisorGrant.id == grant_id,
            SupervisorGrant.owner_id == owner_id,
        )
    )
    grant = result.scalar_one_or_none()
    if grant is None:
        return None

    grant.sections = list(dict.fromkeys(sections))
    await db.commit()
    await db.refresh(grant)
    return grant


async def revoke_grant(db: AsyncSession, *, grant_id: str, owner_id: str) -> bool:
    result = await db.execute(
        select(SupervisorGrant).where(
            SupervisorGrant.id == grant_id,
            SupervisorGrant.owner_id == owner_id,
        )
    )
    grant = result.scalar_one_or_none()
    if grant is None:
        return False

    await db.delete(grant)
    await db.commit()
    return True


async def get_active_grant_for_view(
    db: AsyncSession,
    *,
    owner_id: str,
    supervisor_id: str,
) -> SupervisorGrant | None:
    result = await db.execute(
        select(SupervisorGrant).where(
            SupervisorGrant.owner_id == owner_id,
            SupervisorGrant.supervisor_id == supervisor_id,
            SupervisorGrant.status == "active",
        )
    )
    return result.scalar_one_or_none()


async def resolve_pending_grants_for_new_user(db: AsyncSession, user: User) -> None:
    result = await db.execute(
        select(SupervisorGrant).where(
            SupervisorGrant.supervisor_email == user.email,
            SupervisorGrant.status == "pending",
        )
    )
    grants = list(result.scalars().all())
    if not grants:
        return

    for grant in grants:
        grant.supervisor_id = user.id
        grant.status = "active"

    await db.commit()


async def get_subject_owner_for_view(
    db: AsyncSession,
    *,
    owner_id: str,
    supervisor_id: str,
) -> User:
    grant = await get_active_grant_for_view(db, owner_id=owner_id, supervisor_id=supervisor_id)
    if grant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещён")

    result = await db.execute(
        select(User).where(
            and_(User.id == owner_id, User.is_active.is_(True)),
        )
    )
    owner = result.scalar_one_or_none()
    if owner is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Доступ запрещён")

    return owner
