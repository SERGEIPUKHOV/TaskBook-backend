from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class DailyStateIn(BaseModel):
    health: int | None = Field(default=None, ge=1, le=10)
    productivity: int | None = Field(default=None, ge=1, le=10)
    anxiety: int | None = Field(default=None, ge=1, le=10)


class DailyStateOut(BaseModel):
    id: str
    date: date
    health: int
    productivity: int
    anxiety: int

    model_config = ConfigDict(from_attributes=True)
