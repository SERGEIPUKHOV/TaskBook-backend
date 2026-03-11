from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class DayTaskOut(BaseModel):
    id: str
    title: str
    status: Literal["planned", "done", "moved", "failed"]
    time_planned: int | None
    time_actual: int | None
    is_priority: bool


class DayHabitOut(BaseModel):
    id: str
    title: str
    completed: bool


class DayStateSummaryOut(BaseModel):
    health: int
    productivity: int
    anxiety: int


class DayReflectionOut(BaseModel):
    key_event: str | None
    gratitude: str | None


class DayBundleOut(BaseModel):
    date: date
    day_of_week: int
    iso_week: int
    tasks: list[DayTaskOut]
    habits: list[DayHabitOut]
    daily_state: DayStateSummaryOut | None
    key_event: str | None
    gratitude: str | None
