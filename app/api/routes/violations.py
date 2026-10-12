from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.core.rate_limit import get_client_ip
from app.db.audit import add_audit_event, hash_identifier
from app.db.models import Camera, User, Violation, utc_now
from app.db.session import get_db
from app.schemas.violation import ViolationListResponse, ViolationResponse

router = APIRouter(prefix="/violations", tags=["violations"])


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(UTC).replace(tzinfo=None)
    return dt


def _to_response(v: Violation) -> ViolationResponse:
    frame_url = f"/frames/{v.frame_path}" if v.frame_path else None
    return ViolationResponse(
        id=v.id,
        camera_id=v.camera_id,
        violation_type=v.violation_type,
        confidence=v.confidence,
        timestamp=v.timestamp,
        resolved_at=v.resolved_at,
        is_resolved=v.resolved_at is not None,
        frame_path=v.frame_path,
        frame_url=frame_url,
    )


def _apply_filters(q, camera_id, violation_type, from_dt, to_dt):
    if camera_id is not None:
        q = q.where(Violation.camera_id == camera_id)
    if violation_type is not None:
        q = q.where(Violation.violation_type == violation_type)
    if from_dt is not None:
        q = q.where(Violation.timestamp >= _to_naive_utc(from_dt))
    if to_dt is not None:
        q = q.where(Violation.timestamp <= _to_naive_utc(to_dt))
    return q


def _apply_sector(q, user: User):
    if user.sector != "both":
        q = q.where(Camera.profile == user.sector)
    return q


def _spreadsheet_safe(value):
    if isinstance(value, str) and value[:1] in {"=", "+", "-", "@", "\t", "\r"}:
        return "'" + value
    return value


@router.get("", response_model=ViolationListResponse)
async def list_violations(
    camera_id: int | None = Query(None),
    violation_type: str | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = _apply_sector(select(Violation).join(Camera, Camera.id == Violation.camera_id), user)
    q = q.order_by(Violation.timestamp.desc())
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
    camera_id: int | None = Query(None),
    violation_type: str | None = Query(None),
    from_dt: datetime | None = Query(None, alias="from"),
    to_dt: datetime | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = _apply_sector(select(Violation).join(Camera, Camera.id == Violation.camera_id), user)
    q = q.order_by(Violation.timestamp.desc())
    q = _apply_filters(q, camera_id, violation_type, from_dt, to_dt)
    violations = (await db.execute(q)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["id", "camera_id", "violation_type", "confidence", "timestamp", "resolved_at", "frame_path"]
    )
    for violation in violations:
        writer.writerow(
            [
                violation.id,
                violation.camera_id,
                _spreadsheet_safe(violation.violation_type),
                violation.confidence,
                violation.timestamp,
                violation.resolved_at,
                _spreadsheet_safe(violation.frame_path or ""),
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=violations.csv",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


async def _get_scoped_violation(violation_id: int, db: AsyncSession, user: User) -> Violation:
    violation = await db.get(Violation, violation_id)
    if violation is None:
        raise HTTPException(status_code=404, detail="Violation not found")
    camera = await db.get(Camera, violation.camera_id)
    if camera is None:
        raise HTTPException(status_code=404, detail="Violation not found")
    if user.sector != "both" and camera.profile != user.sector:
        raise HTTPException(status_code=404, detail="Violation not found")
    return violation


@router.get("/{violation_id}", response_model=ViolationResponse)
async def get_violation(
    violation_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _to_response(await _get_scoped_violation(violation_id, db, user))


@router.post("/{violation_id}/resolve", response_model=ViolationResponse)
async def resolve_violation(
    violation_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin", "operator")),
):
    violation = await _get_scoped_violation(violation_id, db, user)
    if violation.resolved_at is None:
        violation.resolved_at = utc_now()
        add_audit_event(
            db,
            "violation.resolved",
            actor_user_id=user.id,
            target_type="violation",
            target_id=violation.id,
            ip_hash=hash_identifier(get_client_ip(request)),
            details={"camera_id": violation.camera_id},
        )
        await db.commit()
        await db.refresh(violation)
    return _to_response(violation)
