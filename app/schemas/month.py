from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.daily_state import DailyStateOut
from app.schemas.habit import HabitGridOut, HabitOut


class MonthPlanIn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    main_goal: str | None = None
    focuses: list[str] = Field(default_factory=list)
    innovations: list[str] = Field(default_factory=list)
    rejections: list[str] = Field(default_factory=list)
    other: str | None = None

    @field_validator("focuses", "innovations", "rejections")
    @classmethod
    def validate_top_lists(cls, value: list[str]) -> list[str]:
        if len(value) > 3:
            raise ValueError("maximum 3 items")
        return value


class MonthPlanOut(MonthPlanIn):
    id: str
    year: int
    month: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MonthBundleOut(BaseModel):
    plan: MonthPlanOut | None
    states: list[DailyStateOut] = Field(default_factory=list)
    habits: list[HabitOut] = Field(default_factory=list)
    grid: HabitGridOut
