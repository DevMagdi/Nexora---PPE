from __future__ import annotations

import ipaddress
import os
from pathlib import Path
from urllib.parse import parse_qsl, quote, unquote, urlsplit, urlunsplit

from app.camera.types import NETWORK_TYPES
from app.core.config import settings

_DEFAULT_PORTS = {"rtsp": 554, "rtsps": 322, "http": 80, "https": 443}
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
        return host == allowed_host.rstrip(".")
    return host == allowed_host.rstrip(".")


def loopback_http_enabled() -> bool:
    return settings.APP_ENV == "dev" and settings.ALLOW_LOOPBACK_HTTP_SOURCES


def validate_resolved_address(host: str, *, http: bool = False) -> None:
    """Called on every HTTP DNS answer before connecting to the pinned IP."""
    address = ipaddress.ip_address(host)
    if str(address) in {"100.100.100.200", "168.63.129.16", "fd00:ec2::254"}:
        raise ValueError("Metadata service addresses are forbidden")
    if address.version == 4 and address in ipaddress.ip_network("0.0.0.0/8"):
        raise ValueError("The current-network address range is forbidden")
    if address.is_loopback and http and loopback_http_enabled():
        return
    if (
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
    ):
        raise ValueError(
            "Loopback, link-local, multicast, reserved and unspecified camera addresses are forbidden"
        )
    if address.version == 6 and address.ipv4_mapped:
        validate_resolved_address(str(address.ipv4_mapped), http=http)


def _safe_path(path: str) -> str:
    decoded = path
    for _ in range(3):
        decoded = unquote(decoded)
        if "\\" in decoded or any(part in {".", ".."} for part in decoded.split("/")):
            raise ValueError("Ambiguous camera paths are forbidden")
    if unquote(decoded) != decoded:
        raise ValueError("Excessive camera path encoding is forbidden")
    return decoded


def _validate_network_uri(uri: str, schemes: set[str], *, http: bool) -> None:
    value = (uri or "").strip()
    if not value or any(ord(c) < 32 or ord(c) == 127 for c in value) or "\\" in value:
        raise ValueError("Invalid camera URI")
    try:
        parsed = urlsplit(value)
        scheme, host = parsed.scheme.lower(), (parsed.hostname or "").rstrip(".").lower()
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid camera hostname or port") from None
    if scheme not in schemes or not host:
        raise ValueError(f"Camera URI must use {'/'.join(sorted(schemes))} with a hostname")
    if port is not None and not 1 <= port <= 65535:
        raise ValueError("Invalid camera port")
    if parsed.fragment:
        raise ValueError("Camera URI fragments are not supported")
    if parsed.query and any(
        key.lower()
        in {"token", "access_token", "jwt", "password", "passwd", "pwd", "user", "username"}
        for key, _ in parse_qsl(parsed.query, keep_blank_values=True)
    ):
        raise ValueError(
            "Camera source URI must not contain authentication tokens in its query; use credentials fields or a restricted relay"
        )
    if (host in _BLOCKED_HOSTS or host.endswith(".localhost")) and not (
        http and loopback_http_enabled() and host in {"localhost", "localhost.localdomain"}
    ):
        raise ValueError("Localhost and metadata service URLs are not valid camera sources")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address:
        validate_resolved_address(str(address), http=http)
    allowed = settings.http_camera_prefixes if http else settings.rtsp_prefixes
    key = "ALLOWED_HTTP_CAMERA_PREFIXES" if http else "ALLOWED_RTSP_PREFIXES"
    if not allowed:
        raise ValueError(f"Network camera sources are disabled: configure {key} first")
    source_path = _safe_path(parsed.path) if http else parsed.path
    for prefix in allowed:
        try:
            allow = urlsplit(prefix)
            allow_host = (allow.hostname or "").lower()
            if allow.scheme.lower() != scheme or not allow_host or "*" in prefix:
                continue
            if not _host_matches_prefix(host, allow_host):
                continue
            if (allow.port or _DEFAULT_PORTS[scheme]) != (port or _DEFAULT_PORTS[scheme]):
                continue
            allow_path = (_safe_path(allow.path) if http else allow.path).rstrip("/")
            if (
                allow_path
                and source_path != allow_path
                and not source_path.startswith(allow_path + "/")
            ):
                continue
            return
        except ValueError:
            continue
    raise ValueError(f"Network camera source is outside {key}")


def validate_rtsp_uri(uri: str) -> None:
    # Kept for callers of the existing RTSP adapter; typed API validation is stricter.
    _validate_network_uri(uri, {"rtsp", "rtsps"}, http=False)


def validate_http_uri(uri: str) -> None:
    _validate_network_uri(uri, {"http", "https"}, http=True)


def validate_file_uri(uri: str) -> str:
    cleaned = (uri or "").strip()
    if not cleaned or "\x00" in cleaned or "://" in cleaned:
        raise ValueError("Invalid video file path")
    if not settings.ALLOWED_VIDEO_DIR:
        raise ValueError("Video file sources are disabled: configure ALLOWED_VIDEO_DIR first")
    base_dir = Path(settings.ALLOWED_VIDEO_DIR).resolve()
    if not base_dir.is_dir():
        raise ValueError("ALLOWED_VIDEO_DIR must exist and be a directory")
    candidate = Path(cleaned)
    resolved = (candidate if candidate.is_absolute() else base_dir / candidate).resolve()
    if not resolved.is_relative_to(base_dir):
        raise ValueError("Video file path is outside ALLOWED_VIDEO_DIR")
    if resolved.suffix.lower() not in {".mp4", ".avi"}:
        raise ValueError("Only MP4 and AVI file sources are supported")
    if not resolved.is_file():
        raise ValueError("Video file must exist inside ALLOWED_VIDEO_DIR")
    return os.fspath(resolved)


def validate_usb_index(index: int | None) -> int:
    if settings.APP_ENV != "dev" or not settings.ENABLE_USB_SOURCES:
        raise ValueError(
            "USB sources are development-only; explicitly enable ENABLE_USB_SOURCES in dev"
        )
    if index is None or isinstance(index, bool) or index not in settings.usb_device_indices:
        raise ValueError("USB device index is outside ALLOWED_USB_DEVICE_INDICES")
    return index


def validate_camera_source(
    source_type: str, source_uri: str, *, device_index: int | None = None
) -> str:
    if source_type in {"rtsp", "rtsps"}:
        validate_rtsp_uri(source_uri)
        if urlsplit(source_uri).scheme != source_type:
            raise ValueError("Camera source type must match the URI scheme")
        return source_uri.strip()
    if source_type in {"http_mjpeg", "hls"}:
        validate_http_uri(source_uri)
        is_playlist = unquote(urlsplit(source_uri).path).lower().endswith(".m3u8")
        if source_type == "hls" and not is_playlist:
            raise ValueError("HLS source URI must point to an HTTP(S) .m3u8 playlist")
        if source_type == "http_mjpeg" and is_playlist:
            raise ValueError("Select HLS for .m3u8 playlists, not HTTP MJPEG")
        return source_uri.strip()
    if source_type == "file":
        return validate_file_uri(source_uri)
    if source_type == "usb":
        return str(validate_usb_index(device_index))
    raise ValueError(f"Unknown source_type: {source_type!r}")


def apply_network_credentials(
    uri: str,
    *,
    port: int | None = None,
    username: str | None = None,
    password: str | None = None,
    clear: bool = False,
    replace_port: bool = False,
) -> str:
    """Write-only credentials. Never inherit old credentials into a replacement URI."""
    parsed = urlsplit(uri)
    if not parsed.hostname:
        raise ValueError("Camera URI requires a hostname")
    if port is None and username is None and password is None and not clear:
        return uri
    if port is not None and parsed.port is not None and port != parsed.port and not replace_port:
        raise ValueError("Port field conflicts with the URI port")
    if (username is None) != (password is None):
        raise ValueError("Supply both username and password when replacing credentials")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    selected_port = port or parsed.port
    if selected_port:
        host += f":{selected_port}"
    if not clear:
        if username is not None:
            if not username or any(ord(c) < 32 for c in username + (password or "")):
                raise ValueError("Invalid camera credentials")
            host = f"{quote(username, safe='')}:{quote(password or '', safe='')}@{host}"
        elif parsed.username is not None:
            host = f"{quote(unquote(parsed.username), safe='')}:{quote(unquote(parsed.password or ''), safe='')}@{host}"
    result = urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))
    if len(result) > 500:
        raise ValueError("Camera URI including credentials exceeds its length limit")
    return result


def validate_onvif_device_uri(uri: str | None, source_type: str) -> str | None:
    if not uri:
        return None
    if source_type not in NETWORK_TYPES:
        raise ValueError("ONVIF metadata is only available for network cameras")
    parsed = urlsplit(uri)
    if parsed.username or parsed.password or parsed.query:
        raise ValueError("ONVIF device address must not contain credentials or query parameters")
    validate_http_uri(uri)
    return uri.strip()
