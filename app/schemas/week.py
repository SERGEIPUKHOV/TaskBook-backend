from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from app.schemas.day_entry import DayEntrySummaryOut
from app.schemas.task import TaskOut


class WeekPatch(BaseModel):
    focus: str | None = None
    reward: str | None = None


class WeekOut(BaseModel):
    id: str
    year: int
    week_number: int
    focus: str | None
    reward: str | None
    date_from: date
    date_to: date

    model_config = ConfigDict(from_attributes=True)


class WeekBundleOut(BaseModel):
    week: WeekOut
    tasks: list[TaskOut]
    key_events: dict[str, DayEntrySummaryOut | None]
    gratitudes: dict[str, DayEntrySummaryOut | None]
