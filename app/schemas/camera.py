from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.ppe import sanitize_enabled_classes


class CameraCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    source_type: Literal["rtsp", "file"]
    source_uri: str = Field(min_length=1, max_length=500)
    site_id: int | None = Field(default=None, gt=0)
    enabled_classes: list[str] | None = None

    @field_validator("enabled_classes")
    @classmethod
    def validate_enabled(cls, value):
        return sanitize_enabled_classes(value)


class CameraUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(None, min_length=1, max_length=100)
    source_uri: str | None = Field(None, min_length=1, max_length=500)
    site_id: int | None = Field(default=None, gt=0)
    enabled_classes: list[str] | None = None

    @field_validator("enabled_classes")
    @classmethod
    def validate_enabled(cls, value):
        return sanitize_enabled_classes(value)


class CameraResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    source_type: Literal["rtsp", "file"]
    source_uri: str
    site_id: int | None
    enabled_classes: list[str]
    is_active: bool
    created_at: datetime
    is_running: bool = False
