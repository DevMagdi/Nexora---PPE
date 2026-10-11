from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import User
from app.db.session import get_db

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def create_access_token(sub: str, expires_minutes: int | None = None) -> str:
    minutes = expires_minutes if expires_minutes is not None else settings.ACCESS_TOKEN_EXPIRE_MINUTES
    exp = datetime.now(UTC) + timedelta(minutes=minutes)
    payload = {"sub": sub, "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_token_user_id(token: str) -> int:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        sub = payload.get("sub")
        if not sub:
            raise credentials_exception
        return int(sub)
    except (JWTError, ValueError) as exc:
        raise credentials_exception from exc


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_token_user_id(token)
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_current_user_media(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme_optional),
    query_token: str = Query(default="", alias="token"),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Authenticates via Bearer header or ?token= query parameter (for <img> / MJPEG streams)."""
    raw_token = bearer_token or query_token
    user_id = decode_token_user_id(raw_token)
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return user
