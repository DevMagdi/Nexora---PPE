from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.core.ppe import ALLOWED_PPE_KEYS, DEFAULT_ENABLED_CLASSES


def _validate_enabled(v):
    if v is None:
        return None
    if not v:
        return DEFAULT_ENABLED_CLASSES.copy()
    if not isinstance(v, list):
        raise ValueError("enabled_classes must be a list")
    invalid = [x for x in v if x not in ALLOWED_PPE_KEYS]
    if invalid:
        raise ValueError(f"Invalid enabled_classes: {invalid}. Allowed: {ALLOWED_PPE_KEYS}")
    return v


class CameraCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    source_type: Literal["webcam", "rtsp", "file"]
    source_uri: str = Field(..., min_length=1, max_length=500)
    enabled_classes: list[str] = Field(default_factory=lambda: DEFAULT_ENABLED_CLASSES.copy())

    @field_validator("enabled_classes", mode="before")
    @classmethod
    def validate_enabled(cls, v):
        return _validate_enabled(v) or DEFAULT_ENABLED_CLASSES.copy()


class CameraUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    source_uri: Optional[str] = Field(None, min_length=1, max_length=500)
    enabled_classes: Optional[list[str]] = None

    @field_validator("enabled_classes", mode="before")
    @classmethod
    def validate_enabled(cls, v):
        return _validate_enabled(v)


class CameraResponse(BaseModel):
    id: int
    name: str
    source_type: str
    source_uri: str
    enabled_classes: list[str]
    is_active: bool
    created_at: datetime
    is_running: bool = False

    model_config = {"from_attributes": True}