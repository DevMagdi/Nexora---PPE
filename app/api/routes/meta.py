from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user
from app.core.ppe import ppe_meta
from app.db.models import User

router = APIRouter(prefix="/meta", tags=["meta"])


@router.get("/ppe-classes")
def ppe_classes(
    profile: str | None = Query(default=None),
    user: User = Depends(get_current_user),
):
    if user.sector != "both":
        profile = user.sector

    if profile not in ("construction", "medical"):
        raise HTTPException(status_code=400, detail="Invalid profile")

    return ppe_meta(profile)  # type: ignore[arg-type]
