from __future__ import annotations

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from app.core.config import settings


class UploadLimitMiddleware:
    """Bound multipart bodies before the framework spools files to disk."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/v1/inference/"):
            return await self.app(scope, receive, send)
        limit = settings.MAX_UPLOAD_MB * 1024 * 1024 + 64 * 1024  # bounded multipart overhead
        headers = dict(scope.get("headers", []))
        try:
            size = int(headers.get(b"content-length", b"0"))
        except ValueError:
            return await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(
                scope, receive, send
            )
        if size < 0 or size > limit:
            return await JSONResponse(
                {"detail": "Upload exceeds the configured size limit"}, status_code=413
            )(scope, receive, send)
        received = 0

        async def bounded_receive():
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > limit:
                raise HTTPException(
                    status_code=413, detail="Upload exceeds the configured size limit"
                )
            return message

        return await self.app(scope, bounded_receive, send)
