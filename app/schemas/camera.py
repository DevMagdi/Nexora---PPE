from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from app.core.ppe import sanitize_enabled_classes, Profile

CameraProfile = Literal["construction", "medical"]


class CameraCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    source_type: Literal["webcam", "rtsp", "file"]
    source_uri: str = Field(..., min_length=1, max_length=500)

    # optional: لو user.sector != both هنفرضها من السيرفر
    profile: Optional[CameraProfile] = None

    enabled_classes: Optional[list[str]] = None

    @field_validator("enabled_classes", mode="before")
    @classmethod
    def validate_enabled(cls, v, info: ValidationInfo):
        profile = info.data.get("profile") or "construction"
        return sanitize_enabled_classes(profile, v)


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    source_uri: Optional[str] = Field(None, min_length=1, max_length=500)
    enabled_classes: Optional[list[str]] = None

    @field_validator("enabled_classes", mode="before")
    @classmethod
    def validate_enabled(cls, v, info: ValidationInfo):
        # في update مش عندنا profile في الـ payload، السيرفر هيستخدم profile من DB
        return v


class CameraResponse(BaseModel):
    id: int
    name: str
    source_type: str
    source_uri: str
    profile: str
    enabled_classes: list[str]
    is_active: bool
    created_at: datetime
    is_running: bool = False

    model_config = {"from_attributes": True}