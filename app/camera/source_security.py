from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from app.core.config import settings

_NETWORK_SCHEMES = {"rtsp", "rtsps"}
_DEFAULT_PORTS = {"rtsp": 554, "rtsps": 322}
_BLOCKED_HOSTS = {"localhost", "localhost.localdomain", "metadata.google.internal"}


def _host_matches_prefix(host: str, allowed_host: str) -> bool:
    allowed_host = allowed_host.lower()
    if allowed_host.endswith("."):
        prefix = allowed_host[:-1]
        if all(part.isdigit() for part in prefix.split(".")):
            try:
                candidate = ipaddress.ip_address(host)
            except ValueError:
                return False
            return candidate.version == 4 and str(candidate).split(".")[
                : len(prefix.split("."))
            ] == prefix.split(".")
        return host.startswith(allowed_host)
    return host == allowed_host.rstrip(".")


def validate_rtsp_uri(uri: str) -> None:
    value = (uri or "").strip()
    parsed = urlsplit(value)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").rstrip(".").lower()
    if scheme not in _NETWORK_SCHEMES or not host:
        raise ValueError("Network camera URI must use rtsp or rtsps with a hostname")
    if parsed.port is not None and not 1 <= parsed.port <= 65535:
        raise ValueError("Invalid camera port")
    if parsed.query and any(
        key.lower() in {"token", "access_token", "jwt"}
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise ValueError("Camera source URI must not contain authentication tokens in its query")
    if host in _BLOCKED_HOSTS or host.endswith(".localhost"):
        raise ValueError("Localhost and metadata service URLs are not valid camera sources")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and (
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
    ):
        raise ValueError(
            "Loopback, link-local, multicast, and unspecified camera addresses are forbidden"
        )

    allowed = settings.rtsp_prefixes
    if not allowed:
        raise ValueError(
            "Network camera sources are disabled: configure ALLOWED_RTSP_PREFIXES first"
        )

    for prefix in allowed:
        allow = urlsplit(prefix)
        allow_host = (allow.hostname or "").lower()
        if allow.scheme.lower() != scheme or not allow_host:
            continue
        host_matches = _host_matches_prefix(host, allow_host)
        if not host_matches:
            continue
        try:
            allow_port = allow.port or _DEFAULT_PORTS[scheme]
            source_port = parsed.port or _DEFAULT_PORTS[scheme]
        except ValueError:
            continue
        if source_port != allow_port:
            continue
        if allow.path not in {"", "/"} and not parsed.path.startswith(allow.path):
            continue
        return

    raise ValueError("Network camera source is outside ALLOWED_RTSP_PREFIXES")


def validate_file_uri(uri: str) -> str:
    cleaned = (uri or "").strip()
    if not cleaned or "\x00" in cleaned:
        raise ValueError("Invalid video file path")
    if not settings.ALLOWED_VIDEO_DIR:
        raise ValueError("Video file sources are disabled: configure ALLOWED_VIDEO_DIR first")

    base_dir = Path(settings.ALLOWED_VIDEO_DIR).resolve()
    if not base_dir.is_dir():
        raise ValueError("ALLOWED_VIDEO_DIR must exist and be a directory")
    candidate = Path(cleaned)
    resolved = (candidate if candidate.is_absolute() else base_dir / candidate).resolve()
    try:
        resolved.relative_to(base_dir)
    except ValueError:
        raise ValueError("Video file path is outside ALLOWED_VIDEO_DIR") from None
    if not resolved.is_file():
        raise ValueError("Video file must exist inside ALLOWED_VIDEO_DIR")
    return os.fspath(resolved)


def validate_camera_source(source_type: str, source_uri: str) -> str:
    if source_type == "rtsp":
        validate_rtsp_uri(source_uri)
        return source_uri.strip()
    if source_type == "file":
        return validate_file_uri(source_uri)
    raise ValueError(f"Unknown source_type: {source_type!r}")
