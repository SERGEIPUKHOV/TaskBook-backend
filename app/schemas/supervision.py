from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

ALLOWED_SUPERVISION_SECTIONS = {"week", "month", "day", "dashboard", "calendar"}
SupervisorSection = Literal["week", "month", "day", "dashboard", "calendar"]


class SupervisorGrantCreate(BaseModel):
    supervisor_email: EmailStr
    sections: list[SupervisorSection] = Field(default_factory=list)

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, value: list[SupervisorSection]) -> list[SupervisorSection]:
        normalized = list(dict.fromkeys(value))
        if not normalized:
            raise ValueError("Нужно выбрать хотя бы один раздел")
        invalid = [section for section in normalized if section not in ALLOWED_SUPERVISION_SECTIONS]
        if invalid:
            raise ValueError("Обнаружены недопустимые разделы")
        return normalized


class SupervisorGrantPatch(BaseModel):
    sections: list[SupervisorSection] = Field(default_factory=list)

    @field_validator("sections")
    @classmethod
    def validate_sections(cls, value: list[SupervisorSection]) -> list[SupervisorSection]:
        normalized = list(dict.fromkeys(value))
        if not normalized:
            raise ValueError("Нужно выбрать хотя бы один раздел")
        invalid = [section for section in normalized if section not in ALLOWED_SUPERVISION_SECTIONS]
        if invalid:
            raise ValueError("Обнаружены недопустимые разделы")
        return normalized


class SupervisorGrantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    supervisor_email: str
    supervisor_id: str | None
    sections: list[SupervisorSection]
    status: str
    created_at: datetime
    updated_at: datetime


class GrantedOwnerOut(BaseModel):
    owner_id: str
    owner_email: str
    sections: list[SupervisorSection]
