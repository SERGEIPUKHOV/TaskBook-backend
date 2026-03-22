from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.task import TaskStatus


class DayTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: TaskStatus
    time_planned: int | None
    time_actual: int | None
    is_priority: bool


class DayHabitOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    completed: bool


class DayStateSummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    health: int
    productivity: int
    anxiety: int


class DayReflectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key_event: str | None
    gratitude: str | None


class DayBundleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: date
    day_of_week: int
    iso_week: int
    tasks: list[DayTaskOut] = Field(default_factory=list)
    habits: list[DayHabitOut] = Field(default_factory=list)
    daily_state: DayStateSummaryOut | None
    key_event: str | None
    gratitude: str | None
