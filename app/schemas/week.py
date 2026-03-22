from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.day_entry import DayEntrySummaryOut
from app.schemas.task import TaskOut


class WeekPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

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
    tasks: list[TaskOut] = Field(default_factory=list)
    key_events: dict[str, DayEntrySummaryOut | None] = Field(default_factory=dict)
    gratitudes: dict[str, DayEntrySummaryOut | None] = Field(default_factory=dict)
