from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import PyJWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import jwt_secret_issues, settings
from app.db.models import User
from app.db.session import get_db

pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__default_rounds=600_000,
)
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

TokenType = Literal["access", "media"]


def ensure_jwt_secret_strength() -> None:
    """Fail closed when the configured JWT secret is too weak for HS256.

    Settings validation already rejects weak values at startup; this guard also
    covers a secret weakened at runtime (tests, embedding) and replaces PyJWT's
    cryptic InsecureKeyLengthWarning with an actionable error.
    """
    issues = jwt_secret_issues(settings.JWT_SECRET)
    if issues:
        raise RuntimeError(
            "JWT_SECRET is too weak for HS256: "
            + "; ".join(issues)
            + ". Set a strong JWT_SECRET (at least 32 random bytes) — generate one "
            "with `python scripts/gen_jwt_secret.py`. See docs/LOCAL_RUN_TROUBLESHOOTING_AR.md."
        )


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return pwd_context.verify(password, password_hash)
    except (ValueError, TypeError):
        return False


def create_access_token(
    sub: str,
    expires_minutes: int | None = None,
    *,
    token_type: TokenType = "access",
    token_version: int = 0,
) -> str:
    ensure_jwt_secret_strength()
    if expires_minutes is not None:
        minutes = expires_minutes
    elif token_type == "media":
        minutes = settings.MEDIA_TOKEN_EXPIRE_MINUTES
    else:
        minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expires_at = datetime.now(UTC) + timedelta(minutes=minutes)
    payload = {
        "sub": sub,
        "exp": expires_at,
        "iat": datetime.now(UTC),
        "token_type": token_type,
        "ver": token_version,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token_payload(token: str, expected_type: TokenType = "access") -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    ensure_jwt_secret_strength()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("token_type") != expected_type:
            raise credentials_exception
        if not payload.get("sub") or not payload.get("exp"):
            raise credentials_exception
        int(payload["sub"])
        if int(payload.get("ver", 0)) < 0:
            raise credentials_exception
        return payload
    except (PyJWTError, KeyError, TypeError, ValueError) as exc:
        raise credentials_exception from exc


def decode_token_user_id(token: str, expected_type: TokenType = "access") -> int:
    return int(decode_token_payload(token, expected_type)["sub"])


def access_cookie_name() -> str:
    name = settings.ACCESS_COOKIE_NAME
    return f"__Host-{name}" if settings.APP_ENV == "prod" else name


def media_cookie_name() -> str:
    name = settings.MEDIA_COOKIE_NAME
    return f"__Host-{name}" if settings.APP_ENV == "prod" else name


def _set_cookie(
    response: Response,
    *,
    name: str,
    value: str,
    max_age: int,
) -> None:
    response.set_cookie(
        key=name,
        value=value,
        max_age=max_age,
        httponly=True,
        secure=settings.APP_ENV in {"staging", "prod"},
        samesite="strict",
        path="/",
    )


def set_session_cookies(response: Response, user: User) -> None:
    access_token = create_access_token(
        str(user.id),
        settings.ACCESS_TOKEN_EXPIRE_MINUTES,
        token_type="access",
        token_version=user.token_version,
    )
    media_token = create_access_token(
        str(user.id),
        settings.MEDIA_TOKEN_EXPIRE_MINUTES,
        token_type="media",
        token_version=user.token_version,
    )
    _set_cookie(
        response,
        name=access_cookie_name(),
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
    _set_cookie(
        response,
        name=media_cookie_name(),
        value=media_token,
        max_age=settings.MEDIA_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"


def set_media_cookie(response: Response, user: User) -> None:
    token = create_access_token(
        str(user.id),
        settings.MEDIA_TOKEN_EXPIRE_MINUTES,
        token_type="media",
        token_version=user.token_version,
    )
    _set_cookie(
        response,
        name=media_cookie_name(),
        value=token,
        max_age=settings.MEDIA_TOKEN_EXPIRE_MINUTES * 60,
    )
    response.headers["Cache-Control"] = "no-store"


def clear_session_cookies(response: Response) -> None:
    secure = settings.APP_ENV in {"staging", "prod"}
    for name in (access_cookie_name(), media_cookie_name()):
        response.delete_cookie(
            key=name,
            path="/",
            secure=secure,
            httponly=True,
            samesite="strict",
        )
    response.headers["Cache-Control"] = "no-store"


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _load_user_from_token(
    token: str,
    *,
    expected_type: TokenType,
    db: AsyncSession,
) -> User:
    payload = decode_token_payload(token, expected_type)
    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active or user.token_version != int(payload.get("ver", 0)):
        raise _unauthorized()
    return user


async def get_authenticated_user(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authenticate a browser session cookie or an explicitly supplied bearer token."""
    token = bearer_token or request.cookies.get(access_cookie_name(), "")
    return await _load_user_from_token(token, expected_type="access", db=db)


async def get_current_user(
    request: Request,
    user: User = Depends(get_authenticated_user),
) -> User:
    if user.must_change_password and request.url.path not in {
        "/api/v1/auth/change-password",
        "/api/v1/auth/me",
        "/api/v1/auth/logout",
    }:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "password_change_required",
                "message": "Change the temporary password before using the application",
            },
        )
    return user


async def get_current_user_media(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Require a short-lived media cookie/token; media credentials never go in URLs."""
    token = request.cookies.get(media_cookie_name(), "") or bearer_token or ""
    payload = decode_token_payload(token, expected_type="media")
    user = await _load_user_from_token(token, expected_type="media", db=db)
    if user.must_change_password:
        raise HTTPException(status_code=403, detail="Password change required")
    request.state.media_expires_at = datetime.fromtimestamp(float(payload["exp"]), UTC)
    return user


def require_roles(*roles: str):
    allowed = set(roles)

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions"
            )
        return user

    return dependency
