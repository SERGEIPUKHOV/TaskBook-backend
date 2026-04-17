from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TrackerSection = Literal["money", "health", "state", "communications", "relations"]
TrackerStatus = Literal["done", "not_done", "done_with_delay"]


class TrackerSprintCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field(min_length=1, max_length=255)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self) -> "TrackerSprintCreate":
        if self.end_date < self.start_date:
            raise ValueError("Sprint end date must not be before start date")
        return self


class TrackerSprintPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    start_date: date | None = None
    end_date: date | None = None
    is_active: bool | None = None


class TrackerSprintOut(BaseModel):
    id: str
    title: str
    start_date: date
    end_date: date
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrackerGoalCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    section: TrackerSection
    level: Literal[1, 2, 3]
    parent_id: str | None = None
    title: str = Field(min_length=1, max_length=2000)
    hypothesis: str | None = None
    deadline_date: date | None = None
    sort_order: int = 0


class TrackerGoalPatch(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str | None = Field(default=None, min_length=1, max_length=2000)
    hypothesis: str | None = None
    deadline_date: date | None = None
    status: TrackerStatus | None = None
    sort_order: int | None = None


class TrackerGoalOut(BaseModel):
    id: str
    sprint_id: str
    section: TrackerSection
    level: int
    parent_id: str | None
    title: str
    hypothesis: str | None
    deadline_date: date | None
    status: TrackerStatus | None
    sort_order: int
    children: list["TrackerGoalOut"] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TrackerDeadlineOut(BaseModel):
    goal_id: str
    sprint_id: str
    section: TrackerSection
    title: str
    deadline_date: date
    status: TrackerStatus | None
    breadcrumb: list[str] = Field(default_factory=list)


class TrackerDeadlinesWeekQuery(BaseModel):
    week_year: int
    week_num: int


class TrackerDeadlinesDayQuery(BaseModel):
    date: date


TrackerGoalOut.model_rebuild()
