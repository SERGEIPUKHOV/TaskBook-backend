from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TaskStatus = Literal["done", "moved", "failed", "planned"]
TaskCalendarExportBucket = Literal["default", "work", "personal", "family"]


class TaskIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="", max_length=500)
    time_planned: int | None = Field(default=None, ge=0)
    time_actual: int | None = Field(default=None, ge=0)
    is_priority: bool = False
    start_day: int | None = Field(default=1, ge=1, le=7)
    calendar_export_enabled: bool = False
    calendar_export_bucket: TaskCalendarExportBucket | None = None


class TaskPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default=None, max_length=500)
    time_planned: int | None = Field(default=None, ge=0)
    time_actual: int | None = Field(default=None, ge=0)
    is_priority: bool | None = None
    start_day: int | None = Field(default=None, ge=1, le=7)
    calendar_export_enabled: bool | None = None
    calendar_export_bucket: TaskCalendarExportBucket | None = None


class TaskDayStatusIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: TaskStatus


class ReorderIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_ids: list[str] = Field(default_factory=list)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    time_planned: int | None
    time_actual: int | None
    is_priority: bool
    order: int
    start_day: int | None
    calendar_export_enabled: bool
    calendar_export_bucket: TaskCalendarExportBucket | None
    carried_from_task_id: str | None
    statuses: dict[str, TaskStatus] = Field(default_factory=dict)


class TaskDayStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    date: date
    status: TaskStatus
