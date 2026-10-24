from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SiteKind = Literal["factory", "construction", "workshop", "warehouse", "industrial"]


class SiteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    kind: SiteKind
    location: str = Field(default="", max_length=200)


class SiteResponse(SiteCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
    created_at: datetime
