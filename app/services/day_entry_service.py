from __future__ import annotations

from datetime import date
from typing import TypeVar

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.day_entry import Gratitude, KeyEvent
from app.schemas.day_entry import DayEntrySummaryOut, GratitudeOut, KeyEventOut
from app.services.cache_service import invalidate_dashboard

EntryModel = TypeVar("EntryModel", KeyEvent, Gratitude)


async def _list_entries(
    db: AsyncSession,
    user_id: str,
    target_date: date,
    model: type[EntryModel],
) -> list[EntryModel]:
    result = await db.execute(
        select(model)
        .where(model.user_id == user_id, model.date == target_date)
        .order_by(model.created_at.asc()),
    )
    return list(result.scalars().all())


async def list_key_events(db: AsyncSession, user_id: str, target_date: date) -> list[KeyEventOut]:
    return [KeyEventOut.model_validate(item) for item in await _list_entries(db, user_id, target_date, KeyEvent)]


async def list_gratitudes(db: AsyncSession, user_id: str, target_date: date) -> list[GratitudeOut]:
    return [GratitudeOut.model_validate(item) for item in await _list_entries(db, user_id, target_date, Gratitude)]


async def _create_entry(
    db: AsyncSession,
    user_id: str,
    target_date: date,
    content: str,
    model: type[EntryModel],
) -> EntryModel:
    record = model(user_id=user_id, date=target_date, content=content)
    db.add(record)
    await db.commit()
    await db.refresh(record)
    await invalidate_dashboard(user_id)
    return record


async def create_key_event(db: AsyncSession, user_id: str, target_date: date, content: str) -> KeyEventOut:
    return KeyEventOut.model_validate(await _create_entry(db, user_id, target_date, content, KeyEvent))


async def create_gratitude(db: AsyncSession, user_id: str, target_date: date, content: str) -> GratitudeOut:
    return GratitudeOut.model_validate(await _create_entry(db, user_id, target_date, content, Gratitude))


async def _get_entry_for_user(db: AsyncSession, user_id: str, entry_id: str, model: type[EntryModel]) -> EntryModel:
    result = await db.execute(select(model).where(model.id == entry_id, model.user_id == user_id))
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entry not found")
    return record


async def update_key_event(db: AsyncSession, user_id: str, entry_id: str, content: str) -> KeyEventOut:
    record = await _get_entry_for_user(db, user_id, entry_id, KeyEvent)
    record.content = content
    db.add(record)
    await db.commit()
    await db.refresh(record)
    await invalidate_dashboard(user_id)
    return KeyEventOut.model_validate(record)


async def update_gratitude(db: AsyncSession, user_id: str, entry_id: str, content: str) -> GratitudeOut:
    record = await _get_entry_for_user(db, user_id, entry_id, Gratitude)
    record.content = content
    db.add(record)
    await db.commit()
    await db.refresh(record)
    await invalidate_dashboard(user_id)
    return GratitudeOut.model_validate(record)


async def delete_key_event(db: AsyncSession, user_id: str, entry_id: str) -> None:
    record = await _get_entry_for_user(db, user_id, entry_id, KeyEvent)
    await db.delete(record)
    await db.commit()
    await invalidate_dashboard(user_id)


async def delete_gratitude(db: AsyncSession, user_id: str, entry_id: str) -> None:
    record = await _get_entry_for_user(db, user_id, entry_id, Gratitude)
    await db.delete(record)
    await db.commit()
    await invalidate_dashboard(user_id)


async def get_week_entry_summary(
    db: AsyncSession,
    user_id: str,
    date_from: date,
    date_to: date,
    model: type[EntryModel],
) -> dict[str, DayEntrySummaryOut | None]:
    result = await db.execute(
        select(model)
        .where(
            model.user_id == user_id,
            model.date >= date_from,
            model.date <= date_to,
        )
        .order_by(model.date.asc(), model.created_at.asc()),
    )
    items = result.scalars().all()
    summary: dict[str, DayEntrySummaryOut | None] = {}
    for item in items:
        key = item.date.isoformat()
        summary.setdefault(key, DayEntrySummaryOut(id=item.id, content=item.content))
    return summary
