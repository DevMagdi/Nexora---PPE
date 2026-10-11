from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ViolationResponse(BaseModel):
    id: int
    camera_id: int
    violation_type: str
    confidence: float
    timestamp: datetime
    resolved_at: datetime | None = None
    is_resolved: bool = False
    frame_path: str | None
    frame_url: str | None = None

    model_config = {"from_attributes": True}


class ViolationListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ViolationResponse]
