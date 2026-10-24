from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import (
    clear_session_cookies,
    get_authenticated_user,
    hash_password,
    require_roles,
    set_media_cookie,
    set_session_cookies,
    verify_password,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.core.password_policy import generate_password, validate_password
from app.core.rate_limit import get_client_ip
from app.db.audit import add_audit_event, hash_identifier
from app.db.models import AuditLog, User, utc_now
from app.db.session import get_db
from app.schemas.auth import (
    AuditLogResponse,
    LoginResponse,
    MeResponse,
    PasswordChangeRequest,
    UserCreateRequest,
    UserIssuedResponse,
    UserResponse,
    UserUpdateRequest,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)
DUMMY_PASSWORD_HASH = hash_password("Nexora dummy password not used for an account 2026!")


def _now():
    return utc_now()


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        must_change_password=user.must_change_password,
        created_at=user.created_at,
    )


def _generate_user_password(username: str) -> str:
    for _ in range(10):
        password = generate_password()
        try:
            validate_password(password, username)
            return password
        except ValueError:
            continue
    raise RuntimeError("Unable to generate a valid initial password")


def _audit(
    db: AsyncSession,
    request: Request,
    action: str,
    *,
    actor_user_id: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    details: dict | None = None,
) -> None:
    add_audit_event(
        db,
        action,
        actor_user_id=actor_user_id,
        target_type=target_type,
        target_id=target_id,
        ip_hash=hash_identifier(get_client_ip(request)),
        details=details,
    )


def _log_failed_login(username_hash: str, ip_hash: str, reason: str) -> None:
    # Never log usernames, passwords, cookies, or complete camera URIs.
    logger.warning(
        "Authentication rejected ip_hash=%s username_hash=%s reason=%s",
        ip_hash,
        username_hash,
        reason,
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    request: Request,
    response: Response,
    form: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    client_ip = get_client_ip(request)
    ip_hash = hash_identifier(client_ip)
    rate_limiter = request.app.state.login_rate_limiter
    retry_after = await rate_limiter.check(client_ip)
    username = form.username.strip().casefold()[:100]
    username_hash = hash_identifier(username)

    if retry_after is not None:
        # A request rejected by the limiter is not written to the audit table;
        # otherwise a flood of already-blocked attempts could exhaust DB storage.
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )

    result = await db.execute(
        select(User).where(func.lower(User.username) == username).with_for_update()
    )
    user = result.scalar_one_or_none()
    now = _now()

    if user and user.locked_until and user.locked_until > now:
        # Keep locked-account and unknown-account failures externally indistinguishable.
        verify_password("invalid", DUMMY_PASSWORD_HASH)
        _audit(
            db,
            request,
            "auth.login_failed",
            actor_user_id=user.id,
            target_type="user",
            target_id=user.id,
            details={"reason": "locked"},
        )
        await db.commit()
        _log_failed_login(username_hash, ip_hash, "locked")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    password_is_valid = False
    if len(form.password) <= 128:
        password_is_valid = verify_password(
            form.password,
            user.password_hash if user else DUMMY_PASSWORD_HASH,
        )
    else:
        verify_password("invalid", DUMMY_PASSWORD_HASH)

    if user is None or not user.is_active or not password_is_valid:
        if user is not None:
            recent_failure = (
                user.last_failed_login_at is not None
                and now - user.last_failed_login_at
                <= timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
            )
            user.failed_login_attempts = user.failed_login_attempts + 1 if recent_failure else 1
            user.last_failed_login_at = now
            if user.failed_login_attempts >= settings.LOGIN_LOCKOUT_ATTEMPTS:
                user.locked_until = now + timedelta(minutes=settings.LOGIN_LOCKOUT_MINUTES)
                user.failed_login_attempts = 0
        _audit(
            db,
            request,
            "auth.login_failed",
            actor_user_id=user.id if user else None,
            target_type="user" if user else None,
            target_id=user.id if user else None,
            details={"username_hash": username_hash, "reason": "invalid_credentials"},
        )
        await db.commit()
        _log_failed_login(username_hash, ip_hash, "invalid_credentials")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )

    user.failed_login_attempts = 0
    user.last_failed_login_at = None
    user.locked_until = None
    _audit(
        db,
        request,
        "auth.login_succeeded",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
    )
    await db.commit()
    set_session_cookies(response, user)
    return LoginResponse(must_change_password=user.must_change_password)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_authenticated_user),
):
    # Revoke all tokens for the account, including any copied media session.
    user.token_version += 1
    _audit(
        db,
        request,
        "auth.logout",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
    )
    await db.commit()
    clear_session_cookies(response)


@router.post("/media-token", status_code=204)
async def renew_media_token(
    response: Response,
    user: User = Depends(get_authenticated_user),
):
    if user.must_change_password:
        raise HTTPException(status_code=403, detail="Password change required")
    set_media_cookie(response, user)


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_authenticated_user)):
    return MeResponse(
        id=user.id,
        username=user.username,
        role=user.role,
        must_change_password=user.must_change_password,
    )


@router.post("/change-password", response_model=LoginResponse)
async def change_password(
    body: PasswordChangeRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_authenticated_user),
):
    if not verify_password(body.current_password, user.password_hash):
        _audit(
            db,
            request,
            "auth.password_change_failed",
            actor_user_id=user.id,
            target_type="user",
            target_id=user.id,
            details={"reason": "current_password_mismatch"},
        )
        await db.commit()
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    try:
        validate_password(body.new_password, user.username)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if verify_password(body.new_password, user.password_hash):
        raise HTTPException(
            status_code=422, detail="New password must be different from the current password"
        )

    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.token_version += 1
    user.failed_login_attempts = 0
    user.last_failed_login_at = None
    user.locked_until = None
    _audit(
        db,
        request,
        "auth.password_changed",
        actor_user_id=user.id,
        target_type="user",
        target_id=user.id,
    )
    await db.commit()
    await db.refresh(user)
    set_session_cookies(response, user)
    return LoginResponse(must_change_password=False)


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    query = select(User)
    result = await db.execute(query.order_by(User.id))
    return [_user_response(user) for user in result.scalars().all()]


@router.post("/users", response_model=UserIssuedResponse, status_code=201)
async def create_user(
    body: UserCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    username = body.username.strip().casefold()
    existing = await db.execute(select(User.id).where(func.lower(User.username) == username))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail="Username already exists")

    password = _generate_user_password(username)
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=body.role,
        is_active=True,
        must_change_password=True,
    )
    db.add(user)
    await db.flush()
    _audit(
        db,
        request,
        "user.created",
        actor_user_id=admin.id,
        target_type="user",
        target_id=user.id,
        details={"role": user.role},
    )
    await db.commit()
    await db.refresh(user)
    issued = _user_response(user).model_dump()
    return UserIssuedResponse(**issued, initial_password=password)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id and (body.is_active is False or body.role not in (None, "admin")):
        raise HTTPException(
            status_code=400, detail="You cannot deactivate or demote your own admin account"
        )

    was_admin = user.role == "admin"
    changes: list[str] = []
    if body.role is not None and body.role != user.role:
        user.role = body.role
        changes.append("role")
    if body.is_active is not None and body.is_active != user.is_active:
        user.is_active = body.is_active
        changes.append("is_active")

    if was_admin and (user.role != "admin" or not user.is_active):
        admins = await db.execute(
            select(func.count(User.id)).where(
                User.role == "admin",
                User.is_active.is_(True),
                User.id != user.id,
            )
        )
        if admins.scalar_one() < 1:
            raise HTTPException(
                status_code=409, detail="At least one active administrator must remain"
            )

    if changes:
        user.token_version += 1
        _audit(
            db,
            request,
            "user.updated",
            actor_user_id=admin.id,
            target_type="user",
            target_id=user.id,
            details={"changed_fields": changes},
        )
        await db.commit()
        await db.refresh(user)
    return _user_response(user)


@router.post("/users/{user_id}/reset-password", response_model=UserIssuedResponse)
async def reset_user_password(
    user_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    user = await db.get(User, user_id, with_for_update=True)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    password = _generate_user_password(user.username)
    user.password_hash = hash_password(password)
    user.must_change_password = True
    user.token_version += 1
    user.failed_login_attempts = 0
    user.last_failed_login_at = None
    user.locked_until = None
    _audit(
        db,
        request,
        "user.password_reset",
        actor_user_id=admin.id,
        target_type="user",
        target_id=user.id,
    )
    await db.commit()
    await db.refresh(user)
    issued = _user_response(user).model_dump()
    return UserIssuedResponse(**issued, initial_password=password)


@router.get("/audit-log", response_model=list[AuditLogResponse])
async def get_audit_log(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_roles("admin")),
):
    if page < 1 or page_size < 1 or page_size > 200:
        raise HTTPException(status_code=422, detail="Invalid pagination values")
    result = await db.execute(
        select(AuditLog)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return [
        AuditLogResponse(
            id=event.id,
            actor_user_id=event.actor_user_id,
            action=event.action,
            target_type=event.target_type,
            target_id=event.target_id,
            ip_hash=event.ip_hash,
            details=event.details,
            created_at=event.created_at,
        )
        for event in result.scalars().all()
    ]
