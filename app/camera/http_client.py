"""Bounded, DNS-pinned HTTP media access. Decoder processes never get network URLs."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
from urllib.parse import unquote, urlsplit

import httpx

from app.camera.source_security import validate_http_uri, validate_resolved_address
from app.core.config import settings


class SourceError(RuntimeError):
    """Only application-authored, non-sensitive messages may reach camera status."""


class _RedactHTTPURLs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # httpx emits request URLs at INFO, including query strings. Never retain them.
        record.msg = re.sub(r"https?://[^\s\"']+", "[media endpoint]", record.getMessage())
        record.args = ()
        return True


def _origin(uri: str) -> tuple[str, str | None, int]:
    p = urlsplit(uri)
    return p.scheme, p.hostname, p.port or (443 if p.scheme == "https" else 80)


class MediaHTTPClient:
    def __init__(self, root_uri: str, auth_mode: str = "basic") -> None:
        self.root_uri = root_uri
        root = urlsplit(root_uri)
        self.auth = None
        if root.username is not None:
            auth = httpx.DigestAuth if auth_mode == "digest" else httpx.BasicAuth
            self.auth = auth(unquote(root.username), unquote(root.password or ""))
        logger = logging.getLogger("httpx")
        if not any(isinstance(f, _RedactHTTPURLs) for f in logger.filters):
            logger.addFilter(_RedactHTTPURLs())
        # Raw HTTP protocol debugging can contain authentication headers.
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        self.client = httpx.AsyncClient(
            trust_env=False,
            follow_redirects=False,
            timeout=httpx.Timeout(
                settings.HTTP_SOURCE_READ_TIMEOUT_SECONDS,
                connect=settings.HTTP_SOURCE_OPEN_TIMEOUT_SECONDS,
            ),
            limits=httpx.Limits(max_connections=4, max_keepalive_connections=2),
        )

    async def _addresses(self, host: str, port: int) -> list[str]:
        try:
            return [str(ipaddress.ip_address(host))]
        except ValueError:
            answers = await asyncio.get_running_loop().getaddrinfo(
                host, port, type=socket.SOCK_STREAM
            )
            return list(dict.fromkeys(answer[4][0] for answer in answers))

    async def open(self, uri: str) -> httpx.Response:
        validate_http_uri(uri)  # recheck on every playlist, segment, init map and key
        parsed = urlsplit(uri)
        if _origin(uri) != _origin(self.root_uri) and parsed.username is not None:
            raise SourceError("لا تُقبل بيانات مصادقة داخل روابط HLS الفرعية.")
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        async with asyncio.timeout(settings.HTTP_SOURCE_OPEN_TIMEOUT_SECONDS):
            addresses = await self._addresses(parsed.hostname or "", port)
            if not addresses:
                raise SourceError("تعذّر حل عنوان كاميرا HTTP.")
            for address in addresses:
                validate_resolved_address(address, http=True)
            # Do not resolve a second time at connection time (DNS rebinding).
            target = httpx.URL(uri).copy_with(host=addresses[0], username=None, password=None)
            host = f"[{parsed.hostname}]" if ":" in (parsed.hostname or "") else parsed.hostname
            if parsed.port:
                host += f":{parsed.port}"
            request = self.client.build_request(
                "GET",
                target,
                headers={
                    "Host": host or "",
                    "Accept-Encoding": "identity",
                    "User-Agent": "Mantik-PPE/4",
                },
            )
            request.extensions["sni_hostname"] = parsed.hostname
            response = await self.client.send(
                request,
                stream=True,
                follow_redirects=False,
                auth=self.auth if _origin(uri) == _origin(self.root_uri) else None,
            )
        if response.status_code != 200:
            await response.aclose()
            if 300 <= response.status_code < 400:
                raise SourceError(
                    "إعادة توجيه HTTP غير مسموحة؛ استخدم الرابط النهائي ضمن القائمة المسموحة."
                )
            raise SourceError(
                f"تعذّر الاتصال بمصدر HTTP (رمز {response.status_code}). راجع المصادقة والعنوان."
            )
        return response

    async def fetch(self, uri: str, limit: int) -> bytes:
        response = await self.open(uri)
        try:
            length = response.headers.get("content-length", "")
            if length.isdigit() and int(length) > limit:
                raise SourceError("حجم مورد HLS يتجاوز الحد الآمن.")
            body = bytearray()
            async with asyncio.timeout(settings.HTTP_SOURCE_READ_TIMEOUT_SECONDS):
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > limit:
                        raise SourceError("حجم مورد HLS يتجاوز الحد الآمن.")
                    body.extend(chunk)
            return bytes(body)
        finally:
            await response.aclose()

    async def close(self) -> None:
        await self.client.aclose()
