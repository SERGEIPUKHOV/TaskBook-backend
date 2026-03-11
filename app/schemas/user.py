from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, computed_field


class UserOut(BaseModel):
    id: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field(return_type=Literal["admin", "user"])
    @property
    def role(self) -> Literal["admin", "user"]:
        return "admin" if self.is_admin else "user"
