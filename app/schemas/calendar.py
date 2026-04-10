from __future__ import annotations

from datetime import date, datetime

from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.task import TaskCalendarExportBucket

ScheduleDay = Annotated[int, Field(ge=1, le=7)]


class GoogleAuthSessionIn(BaseModel):
    return_to: str | None = None


class GoogleAuthSessionOut(BaseModel):
    authorize_url: str
    state_expires_in: int


class GoogleCalendarOptionOut(BaseModel):
    id: str
    summary: str
    access_role: str | None = None
    primary: bool = False
    selected: bool = False


class GoogleCalendarOptionsOut(BaseModel):
    connected: bool
    provider_account_label: str | None = None
    options: list[GoogleCalendarOptionOut] = Field(default_factory=list)


class GoogleCalendarSelectionIn(BaseModel):
    calendar_ids: list[str] = Field(default_factory=list)


class AppleIcsConnectionIn(BaseModel):
    ics_url: str = Field(min_length=1)
    account_label: str | None = None


class UpdateConnectionColorIn(BaseModel):
    color: str = Field(pattern=r"^#[0-9A-Fa-f]{6}$")


class CalendarConnectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    status: str
    external_account_id: str
    account_label: str | None
    provider_account_label: str | None = None
    last_synced_at: datetime | None
    last_error: str | None
    color: str | None = None
    token_expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CalendarEventOut(BaseModel):
    planner_link: "PlannerLinkOut | None" = None
    suggested_target_type: Literal["task", "habit"]
    recurrence: list[str] = Field(default_factory=list)
    id: str
    connection_id: str
    provider: str
    account_label: str | None
    external_event_id: str
    external_calendar_id: str | None
    title: str
    description: str | None
    location: str | None
    starts_at: datetime
    ends_at: datetime
    source_timezone: str | None
    is_all_day: bool
    status: str
    recurring_event_id: str | None = None


class PlannerLinkOut(BaseModel):
    id: str
    link_mode: Literal["import_copy"]
    open_path: str
    target_id: str
    target_kind: Literal["task", "habit"]


class CalendarEventImportIn(BaseModel):
    is_priority: bool = False
    month: int | None = Field(default=None, ge=1, le=12)
    schedule_days: list[ScheduleDay] | None = None
    start_day: int | None = Field(default=None, ge=1, le=7)
    target_type: Literal["task", "habit"]
    time_planned: int | None = Field(default=None, ge=0, le=999)
    title: str | None = Field(default=None, max_length=500)
    week: int | None = Field(default=None, ge=1, le=53)
    year: int


class CalendarEventImportOut(BaseModel):
    planner_link: PlannerLinkOut
    status: Literal["created", "existing"]


class CalendarTaskFeedLinkOut(BaseModel):
    bucket: TaskCalendarExportBucket
    feed_path: str
    task_count: int


class CalendarEventsRangeOut(BaseModel):
    date_from: date
    date_to: date
    events: list[CalendarEventOut] = Field(default_factory=list)
