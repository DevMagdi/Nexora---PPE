from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_warned_no_api_key = False


async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """
    Dependency بيحمي الـ endpoints الحساسة (إنشاء/تعديل/حذف/تشغيل الكاميرات،
    حل المخالفات...).

    لو settings.API_KEY فاضي، بنسمح بالمرور (وضع dev) لكن بنسجل تحذير
    *مرة واحدة بس* في اللوج عشان نفكّر المطور إنه لازم يحط API_KEY
    قبل أي نشر production. ده أفضل من ما نكسر التطبيق فجأة لمين مستخدمه
    محليًا من غير ما يظبط .env، لكن برضه منسيبوش يمر بصمت.
    """
    global _warned_no_api_key

    if not settings.API_KEY:
        if not _warned_no_api_key:
            logger.warning(
                "API_KEY is not set — sensitive endpoints are UNPROTECTED. "
                "Set API_KEY in your environment before deploying to production."
            )
            _warned_no_api_key = True
        return

    if x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key (expected header 'X-API-Key')",
        )