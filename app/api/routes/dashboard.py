from __future__ import annotations

from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_camera_manager
from app.core.auth import get_current_user
from app.db.models import Camera, Site, User, Violation, utc_now
from app.db.session import get_db

router = APIRouter(tags=["industrial dashboard"])


@router.get("/dashboard")
async def dashboard(
    request: Request,
    range_key: Literal["24h", "7d"] = Query(default="24h", alias="range"),
    site_id: int | None = Query(default=None, gt=0),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    now = utc_now()
    step = timedelta(hours=1) if range_key == "24h" else timedelta(days=1)
    slots = 24 if range_key == "24h" else 7
    end = (
        now.replace(minute=0, second=0, microsecond=0)
        if range_key == "24h"
        else now.replace(hour=0, minute=0, second=0, microsecond=0)
    ) + step
    start = end - slots * step
    camera_query = select(Camera.id)
    if site_id is not None:
        camera_query = camera_query.where(Camera.site_id == site_id)
    camera_ids = list((await db.execute(camera_query)).scalars().all())
    filters = [
        Violation.camera_id.in_(camera_ids),
        Violation.timestamp >= start,
        Violation.timestamp <= now,
    ]
    total = (await db.execute(select(func.count(Violation.id)).where(*filters))).scalar_one()
    open_count = (
        await db.execute(
            select(func.count(Violation.id)).where(*filters, Violation.resolved_at.is_(None))
        )
    ).scalar_one()
    breakdown = (
        await db.execute(
            select(Violation.violation_type, func.count(Violation.id))
            .where(*filters)
            .group_by(Violation.violation_type)
        )
    ).all()
    # One exact aggregate query: charts never depend on a capped/paginated event list.
    columns = [
        func.sum(
            case(
                (
                    and_(
                        Violation.timestamp >= start + i * step,
                        Violation.timestamp < start + (i + 1) * step,
                    ),
                    1,
                ),
                else_=0,
            )
        )
        for i in range(slots)
    ]
    counts = (await db.execute(select(*columns).where(*filters))).one()
    manager = get_camera_manager(request)
    snapshots = manager.counts_snapshot()
    live = [
        snapshots.get(str(camera_id), {})
        for camera_id in camera_ids
        if manager.is_running(camera_id)
    ]
    return {
        "range": range_key,
        "from": start.isoformat() + "Z",
        "to": now.isoformat() + "Z",
        "total_events": total,
        "open_events": open_count,
        "resolved_events": total - open_count,
        "total_cameras": len(camera_ids),
        "running_cameras": len(live),
        "sites": (
            await db.execute(
                select(func.count(Site.id)).where(*([Site.id == site_id] if site_id else []))
            )
        ).scalar_one(),
        "live_people": sum(item.get("person", 0) for item in live),
        "series": [
            {"timestamp": (start + i * step).isoformat() + "Z", "count": int(counts[i] or 0)}
            for i in range(slots)
        ],
        "breakdown": [
            {"type": name, "count": count}
            for name, count in sorted(breakdown, key=lambda item: (-item[1], item[0]))
        ],
    }
