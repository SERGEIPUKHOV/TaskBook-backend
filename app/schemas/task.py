from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.habit import LinkedEventTimeOut

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
    linked_event_time: LinkedEventTimeOut | None = None
    calendar_connection_id: str | None = None


class TaskCalendarExportBody(BaseModel):
    model_config = ConfigDict(extra="ignore")

    connection_id: str
    schedule_days: list[int] | None = None   # 1=Пн … 7=Вс (ISO weekday)
    starts_hhmm: str | None = None           # "HH:MM"
    ends_hhmm: str | None = None             # "HH:MM"


class TaskEventTimePatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    starts_hhmm: str = Field(pattern=r"^\d{2}:\d{2}$")
    ends_hhmm: str = Field(pattern=r"^\d{2}:\d{2}$")


class TaskDayStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    task_id: str
    date: date
    status: TaskStatus
