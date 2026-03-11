from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class TaskIn(BaseModel):
    title: str = Field(default="", max_length=500)
    time_planned: int | None = Field(default=None, ge=0)
    time_actual: int | None = Field(default=None, ge=0)
    is_priority: bool = False
    start_day: int | None = Field(default=1, ge=1, le=7)


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    time_planned: int | None = Field(default=None, ge=0)
    time_actual: int | None = Field(default=None, ge=0)
    is_priority: bool | None = None
    start_day: int | None = Field(default=None, ge=1, le=7)


class TaskDayStatusIn(BaseModel):
    status: Literal["done", "moved", "failed", "planned"]


class ReorderIn(BaseModel):
    task_ids: list[str]


class TaskOut(BaseModel):
    id: str
    title: str
    time_planned: int | None
    time_actual: int | None
    is_priority: bool
    order: int
    start_day: int | None
    carried_from_task_id: str | None
    statuses: dict[str, str]


class TaskDayStatusOut(BaseModel):
    task_id: str
    date: date
    status: str
