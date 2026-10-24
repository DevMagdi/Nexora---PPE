from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user, require_roles
from app.db.audit import add_audit_event
from app.db.models import Camera, Site, User
from app.db.session import get_db
from app.schemas.site import SiteCreate, SiteResponse

router = APIRouter(prefix="/sites", tags=["industrial sites"])


@router.get("", response_model=list[SiteResponse])
async def list_sites(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return (await db.execute(select(Site).order_by(Site.name))).scalars().all()


@router.post("", response_model=SiteResponse, status_code=201)
async def create_site(
    body: SiteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    site = Site(**body.model_dump())
    db.add(site)
    try:
        await db.flush()
        add_audit_event(
            db, "site.created", actor_user_id=user.id, target_type="site", target_id=site.id
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A site with this name already exists") from exc
    await db.refresh(site)
    return site


@router.put("/{site_id}", response_model=SiteResponse)
async def update_site(
    site_id: int,
    body: SiteCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    site = await db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    for key, value in body.model_dump().items():
        setattr(site, key, value)
    add_audit_event(
        db, "site.updated", actor_user_id=user.id, target_type="site", target_id=site.id
    )
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="A site with this name already exists") from exc
    await db.refresh(site)
    return site


@router.delete("/{site_id}", status_code=204)
async def delete_site(
    site_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_roles("admin")),
):
    site = await db.get(Site, site_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site not found")
    count = (
        await db.execute(select(func.count(Camera.id)).where(Camera.site_id == site_id))
    ).scalar_one()
    if count:
        raise HTTPException(
            status_code=409, detail="Reassign this site's cameras before deleting it"
        )
    add_audit_event(
        db, "site.deleted", actor_user_id=user.id, target_type="site", target_id=site.id
    )
    try:
        await db.delete(site)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Site is still assigned to cameras") from exc
