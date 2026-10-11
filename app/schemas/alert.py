from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AlertLogResponse(BaseModel):
    id: int
    violation_id: int | None
    handler_type: str
    sent_at: datetime
    success: bool
    error_msg: str | None

    model_config = {"from_attributes": True}
