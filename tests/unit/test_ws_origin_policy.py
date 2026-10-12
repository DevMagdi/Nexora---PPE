from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.api.routes import stream


def make_websocket(origin: str | None, host: str | None, scheme: str = "ws") -> SimpleNamespace:
    headers: dict[str, str] = {}
    if origin is not None:
        headers["origin"] = origin
    if host is not None:
        headers["host"] = host
    return SimpleNamespace(headers=headers, url=SimpleNamespace(scheme=scheme))


ALLOWED_CASES = [
    # صفحة Dashboard بتتخدم من FastAPI نفسه — نفس الأصل بالظبط
    ("http://localhost:8000", "localhost:8000"),
    ("http://127.0.0.1:8000", "127.0.0.1:8000"),
    ("https://dashboard.nexora.example", "dashboard.nexora.example"),
    # alias اللوك باك: الصفحة على localhost والمتصفح بيوصل الـ API على 127.0.0.1
    # (ده بالظبط السيناريو اللي كان بيوجع في اللوج: 403 untrusted origin)
    ("http://localhost:8000", "127.0.0.1:8000"),
    ("http://127.0.0.1:8000", "localhost:8000"),
    ("https://localhost", "[::1]:8000"),
    ("http://[::1]:5173", "localhost:8000"),
    # أصول Vite المصرّح بيها صراحةً في CORS_ORIGINS
    ("http://localhost:5173", "localhost:8000"),
    ("http://127.0.0.1:5173", "127.0.0.1:8000"),
    # تطبيع الحالة والميل تريلينج سلاش
    ("HTTP://LocalHost:8000/", "LOCALHOST:8000"),
    # البورت الافتراضي المختفي لسه نفس الهوست
    ("http://localhost", "localhost:8000"),
]

REJECTED_CASES = [
    # دومينات خارجية
    ("https://attacker.invalid", "localhost:8000"),
    ("http://evil.example", "127.0.0.1:8000"),
    # هجمات اللاحقة/الانتحال
    ("http://localhost.attacker.invalid", "localhost:8000"),
    ("http://127.0.0.1.evil.com", "127.0.0.1:8000"),
    ("http://localhost:8000.attacker.invalid", "localhost:8000"),
    # origin غير صالح أو غريب
    ("null", "localhost:8000"),
    ("ftp://localhost", "localhost:8000"),
    ("", "localhost:8000"),
    ("http://", "localhost:8000"),
    # نفس الاسم لكن كأصلاً مكسور بروتوكوليًا
    ("javascript://localhost", "localhost:8000"),
]

NO_HOST_HEADER_CASES = [
    # أصلاً مصرّح بيها في CORS تفضل مسموحة حتى لو الهيدر مفقود
    ("http://localhost:5173", None, True),
    # أي أصل تاني من غير Host مرفوض
    ("http://localhost:8000", None, False),
    ("https://attacker.invalid", None, False),
]


@pytest.mark.parametrize(("origin", "host"), ALLOWED_CASES)
def test_allowed_origins(origin: str, host: str) -> None:
    websocket = make_websocket(origin, host)
    assert stream._websocket_origin_is_allowed(websocket, origin) is True


@pytest.mark.parametrize(("origin", "host"), REJECTED_CASES)
def test_rejected_origins(origin: str, host: str) -> None:
    websocket = make_websocket(origin, host)
    assert stream._websocket_origin_is_allowed(websocket, origin) is False


@pytest.mark.parametrize(("origin", "host", "expected"), NO_HOST_HEADER_CASES)
def test_missing_host_header_falls_back_to_cors_list(origin: str, host: str | None, expected: bool) -> None:
    websocket = make_websocket(origin, host)
    assert stream._websocket_origin_is_allowed(websocket, origin) is expected


def test_missing_origin_header_is_not_checked_by_policy() -> None:
    # غير المتصفحات (curl / health probes) مبتبعتش Origin أصلاً —
    # الحماية بتبقى على الـ media cookie والتحقق من الجلسة.
    websocket = make_websocket(None, "localhost:8000")
    assert websocket.headers.get("origin") is None


def test_loopback_alias_is_symmetric() -> None:
    a = make_websocket("http://localhost:8000", "127.0.0.1:8000")
    b = make_websocket("http://127.0.0.1:8000", "localhost:8000")
    assert stream._websocket_origin_is_allowed(a, "http://localhost:8000")
    assert stream._websocket_origin_is_allowed(b, "http://127.0.0.1:8000")


def test_origin_parts_normalizes_ipv6_brackets() -> None:
    scheme, hostname = stream._origin_parts("wss://[::1]:8000/api")
    assert scheme == "wss"
    assert hostname == "::1"


def test_host_header_hostname_handles_all_shapes() -> None:
    assert stream._host_header_hostname(make_websocket(None, "localhost:8000")) == "localhost"
    assert stream._host_header_hostname(make_websocket(None, "[::1]:8000")) == "::1"
    assert stream._host_header_hostname(make_websocket(None, "[::1]")) == "::1"
    assert stream._host_header_hostname(make_websocket(None, "example.com")) == "example.com"
    assert stream._host_header_hostname(make_websocket(None, "")) == ""
