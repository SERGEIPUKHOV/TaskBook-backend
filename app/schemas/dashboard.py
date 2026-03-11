from __future__ import annotations

from pydantic import BaseModel

from app.schemas.daily_state import DailyStateOut
from app.schemas.month import MonthPlanOut
from app.schemas.task import TaskOut
from app.schemas.week import WeekOut


class DashboardOut(BaseModel):
    current_week: WeekOut
    tasks: list[TaskOut]
    month_states: list[DailyStateOut]
    current_month_plan: MonthPlanOut | None
