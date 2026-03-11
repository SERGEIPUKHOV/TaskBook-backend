from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HabitIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class HabitPatch(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class HabitOut(BaseModel):
    id: str
    name: str
    order: int

    model_config = ConfigDict(from_attributes=True)


class HabitGridOut(BaseModel):
    habits: list[HabitOut]
    logs: dict[str, list[int]]
    days_in_month: int
