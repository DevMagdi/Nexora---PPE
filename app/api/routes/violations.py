from __future__ import annotations

import csv
import io
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import require_api_key
from app.db.models import Violation, utc_now
from app.db.session import get_db
from app.schemas.violation import ViolationListResponse, ViolationResponse

router = APIRouter(prefix="/violations", tags=["violations"])


def _normalize_frame_path(p: str) -> str:
    p = (p or "").replace("\\", "/").lstrip("/")
    frames_prefix = settings.FRAMES_DIR.replace("\\", "/").rstrip("/") + "/"
    if p.startswith(frames_prefix):
        p = p[len(frames_prefix):]
    return p.lstrip("/")


def _to_naive_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    يوحّد أي datetime وارد من الـ Query (سواء جاي بصيغة 'Z' أو tz-aware)
    إلى UTC بدون tzinfo، عشان يتطابق مع الصيغة المخزّنة فعليًا في العمود
    (utc_now() بترجع UTC من غير tzinfo). ده تأمين إضافي يحمينا من أي
    سلوك مختلف لو اتغير الـ DB backend مستقبلًا (SQLite -> Postgres/SQL Server).
    """
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


def _to_response(v: Violation) -> ViolationResponse:
    frame_url = None
    frame_path = v.frame_path

    if frame_path:
        norm = _normalize_frame_path(frame_path)
        frame_url = f"/frames/{norm}" if norm else None
        frame_path = norm

    return ViolationResponse(
        id=v.id,
        camera_id=v.camera_id,
        violation_type=v.violation_type,
        confidence=v.confidence,
        timestamp=v.timestamp,
        resolved_at=v.resolved_at,
        is_resolved=v.resolved_at is not None,
        frame_path=frame_path,
        frame_url=frame_url,
    )


def _apply_filters(
    q,
    camera_id: Optional[int],
    violation_type: Optional[str],
    from_dt: Optional[datetime],
    to_dt: Optional[datetime],
):
    """
    فلاتر موحّدة بين /violations و /violations/export.
    قبل كده كان التصدير بيتجاهل from/to/violation_type تمامًا، فالملف
    المُصدّر كان دايمًا فيه كل المخالفات المسجّلة بغض النظر عن الفلاتر
    الظاهرة فعليًا على الشاشة.
    """
    if camera_id is not None:
        q = q.where(Violation.camera_id == camera_id)
    if violation_type is not None:
        q = q.where(Violation.violation_type == violation_type)
    if from_dt is not None:
        q = q.where(Violation.timestamp >= _to_naive_utc(from_dt))
    if to_dt is not None:
        q = q.where(Violation.timestamp <= _to_naive_utc(to_dt))
    return q


@router.get("", response_model=ViolationListResponse)
async def list_violations(
    camera_id: Optional[int] = Query(None),
    violation_type: Optional[str] = Query(None),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    q = select(Violation).order_by(Violation.timestamp.desc())
    q = _apply_filters(q, camera_id, violation_type, from_dt, to_dt)

    count_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(count_q)).scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    items = (await db.execute(q)).scalars().all()

    return ViolationListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_response(v) for v in items],
    )


@router.get("/export")
async def export_violations(
    camera_id: Optional[int] = Query(None),
    violation_type: Optional[str] = Query(None),
    from_dt: Optional[datetime] = Query(None, alias="from"),
    to_dt: Optional[datetime] = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
):
    q = select(Violation).order_by(Violation.timestamp.desc())
    q = _apply_filters(q, camera_id, violation_type, from_dt, to_dt)
    violations = (await db.execute(q)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["id", "camera_id", "violation_type", "confidence", "timestamp", "resolved_at", "frame_path"]
    )
    for v in violations:
        writer.writerow(
            [v.id, v.camera_id, v.violation_type, v.confidence, v.timestamp, v.resolved_at, v.frame_path]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=violations.csv"},
    )


@router.get("/{violation_id}", response_model=ViolationResponse)
async def get_violation(
    violation_id: int,
    db: AsyncSession = Depends(get_db),
):
    v = await db.get(Violation, violation_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Violation not found")
    return _to_response(v)


@router.post(
    "/{violation_id}/resolve",
    response_model=ViolationResponse,
    dependencies=[Depends(require_api_key)],
)
async def resolve_violation(
    violation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """يعلّم المخالفة كـ 'تم التعامل معها'. كان العمود resolved_at موجود
    في الموديل من غير أي endpoint يستخدمه."""
    v = await db.get(Violation, violation_id)
    if v is None:
        raise HTTPException(status_code=404, detail="Violation not found")

    if v.resolved_at is None:
        v.resolved_at = utc_now()
        await db.commit()
        await db.refresh(v)

    return _to_response(v)