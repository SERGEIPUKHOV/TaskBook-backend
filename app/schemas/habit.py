from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

ScheduleDay = Annotated[int, Field(ge=1, le=7)]


def normalize_schedule_days(value: list[int] | None) -> list[int] | None:
    if value is None:
        return None

    normalized = sorted(set(value))
    if not normalized:
        return None

    return normalized


class HabitIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(min_length=1, max_length=255)


class HabitPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, min_length=1, max_length=255)
    schedule_days: list[ScheduleDay] | None = None

    @field_validator("schedule_days")
    @classmethod
    def normalize_patch_schedule_days(cls, value: list[int] | None) -> list[int] | None:
        return normalize_schedule_days(value)


class LinkedEventTimeOut(BaseModel):
    starts_at: str
    ends_at: str


class HabitOut(BaseModel):
    id: str
    name: str
    order: int
    schedule_days: list[ScheduleDay] = Field(default_factory=list)
    linked_event_time: LinkedEventTimeOut | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_validator("schedule_days", mode="before")
    @classmethod
    def default_schedule_days(cls, value: list[int] | None) -> list[int]:
        return normalize_schedule_days(value) or []


class HabitGridOut(BaseModel):
    habits: list[HabitOut] = Field(default_factory=list)
    logs: dict[str, list[int]] = Field(default_factory=dict)
    days_in_month: int
