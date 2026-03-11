from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class KeyEventIn(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class KeyEventOut(KeyEventIn):
    id: str
    date: date
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GratitudeIn(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


class GratitudeOut(GratitudeIn):
    id: str
    date: date
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DayEntrySummaryOut(BaseModel):
    id: str
    content: str
