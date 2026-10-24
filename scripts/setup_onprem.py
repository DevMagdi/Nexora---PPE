#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ipaddress
import os
import re
import secrets
import string
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENV_EXAMPLE = ROOT / ".env.example"
ENV_FILE = ROOT / ".env"
HOST_LABEL_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")


def _password(length: int = 32) -> str:
    groups = (string.ascii_lowercase, string.ascii_uppercase, string.digits, "!@#$%^&*()-_=+")
    alphabet = "".join(groups)
    for _ in range(10):
        chars = [secrets.choice(group) for group in groups]
        chars.extend(secrets.choice(alphabet) for _ in range(length - len(chars)))
        secrets.SystemRandom().shuffle(chars)
        password = "".join(chars)
        if "admin" not in password.casefold():
            return password
    raise RuntimeError("Unable to generate a bootstrap password without the username")


def _valid_host(host: str) -> str:
    value = host.strip().lower().rstrip(".")
    labels = value.split(".")
    if (
        not value
        or len(value) > 253
        or any(
            not label or len(label) > 63 or not HOST_LABEL_RE.fullmatch(label) for label in labels
        )
    ):
        raise ValueError(
            "--host must be a valid DNS name or IPv4 address without a scheme, port, or path"
        )
    return value


def _valid_https_bind_address(address: str) -> str:
    try:
        return str(ipaddress.IPv4Address(address))
    except ipaddress.AddressValueError as exc:
        raise ValueError("--https-bind-address must be an IPv4 address") from exc


def _valid_docker_subnets(
    edge_subnet: str, data_subnet: str
) -> tuple[ipaddress.IPv4Network, ipaddress.IPv4Network]:
    try:
        edge = ipaddress.ip_network(edge_subnet, strict=True)
        data = ipaddress.ip_network(data_subnet, strict=True)
    except ValueError as exc:
        raise ValueError(
            "Docker network subnets must be valid IPv4 CIDRs with aligned network addresses"
        ) from exc
    if not isinstance(edge, ipaddress.IPv4Network) or not isinstance(data, ipaddress.IPv4Network):
        raise ValueError("Docker network subnets must use IPv4")
    if not edge.is_private or not data.is_private or edge.prefixlen > 29 or data.prefixlen > 29:
        raise ValueError(
            "Docker network subnets must be private IPv4 CIDRs with room for service addresses"
        )
    if edge.overlaps(data):
        raise ValueError("The isolated edge and data Docker subnets must not overlap")
    return edge, data


def _valid_prefixes(values: list[str], schemes: set[str] | None = None) -> list[str]:
    schemes = schemes or {"rtsp", "rtsps"}
    result: list[str] = []
    for item in values:
        value = item.strip().rstrip("/")
        parsed = urlsplit(value)
        try:
            port = parsed.port
            if port == 0:
                raise ValueError("camera port cannot be zero")
        except ValueError as exc:
            raise ValueError(f"Invalid camera network prefix: {item!r}") from exc
        if (
            "*" in value
            or parsed.scheme not in schemes
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(f"Invalid camera network prefix: {item!r}")
        result.append(value)
    if not result:
        raise ValueError("At least one actual camera network prefix is required")
    return result


def _dotenv_literal(value: str) -> str:
    """Quote a generated value so Compose and python-dotenv parse it literally."""
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _set_env(contents: str, key: str, value: str) -> str:
    lines = contents.splitlines()
    pattern = re.compile(rf"^\s*#?\s*{re.escape(key)}\s*=")
    replacement = f"{key}={value}"
    matches = [index for index, line in enumerate(lines) if pattern.match(line)]
    if matches:
        lines[matches[0]] = replacement
        for index in reversed(matches[1:]):
            lines.pop(index)
    else:
        lines.append(replacement)
    return "\n".join(lines) + "\n"


def setup(
    host: str,
    prefixes: list[str],
    https_bind_address: str,
    edge_subnet: str = "172.30.100.0/24",
    data_subnet: str = "172.30.101.0/24",
    http_prefixes: list[str] | None = None,
) -> str:
    host = _valid_host(host)
    prefixes = _valid_prefixes(prefixes) if prefixes else []
    http_prefixes = _valid_prefixes(http_prefixes, {"http", "https"}) if http_prefixes else []
    if not prefixes and not http_prefixes:
        raise ValueError("At least one actual camera network prefix is required")
    https_bind_address = _valid_https_bind_address(https_bind_address)
    edge_network, data_network = _valid_docker_subnets(edge_subnet, data_subnet)
    if ENV_FILE.exists():
        raise FileExistsError(
            ".env already exists; back it up and remove it only if you intend to rotate all generated secrets"
        )
    if not ENV_EXAMPLE.is_file():
        raise FileNotFoundError(".env.example is missing")

    values = {
        "APP_ENV": "prod",
        "LOG_LEVEL": "INFO",
        "DB_SQL_ECHO": "false",
        "CORS_ORIGINS": f"https://{host}",
        "ALLOWED_HOSTS": host,
        # Caddy has a pinned address; Uvicorn and app trust only this proxy.
        "TRUSTED_PROXIES": f"{edge_network.network_address + 2}/32",
        "EDGE_DOCKER_SUBNET": str(edge_network),
        "DATA_DOCKER_SUBNET": str(data_network),
        "CADDY_CONTAINER_IP": str(edge_network.network_address + 2),
        "APP_EDGE_CONTAINER_IP": str(edge_network.network_address + 3),
        "DB_CONTAINER_IP": str(data_network.network_address + 2),
        "JWT_SECRET": secrets.token_urlsafe(48),
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "240",
        "MEDIA_TOKEN_EXPIRE_MINUTES": "10",
        "BOOTSTRAP_USERNAME": "admin",
        "BOOTSTRAP_PASSWORD": _password(),
        "ALLOWED_RTSP_PREFIXES": ",".join(prefixes),
        "ALLOWED_HTTP_CAMERA_PREFIXES": ",".join(http_prefixes),
        "ENABLE_USB_SOURCES": "false",
        "ALLOW_LOOPBACK_HTTP_SOURCES": "false",
        "ALLOWED_VIDEO_DIR": "/var/nexora/videos",
        "UPLOADS_DIR": "/var/nexora/videos/uploads",
        "BACKUP_ENCRYPTION_KEY": secrets.token_urlsafe(32),
        "BACKUP_DIR": "/var/nexora/backups",
        "POSTGRES_USER": "nexora",
        "POSTGRES_DB": "ppe_detection",
        "POSTGRES_PASSWORD": secrets.token_urlsafe(32),
        "NEXORA_HOST": host,
        "HTTPS_BIND_ADDRESS": https_bind_address,
    }

    contents = ENV_EXAMPLE.read_text(encoding="utf-8")
    for key, value in values.items():
        contents = _set_env(contents, key, _dotenv_literal(value))

    file_descriptor = os.open(ENV_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(file_descriptor, "w", encoding="utf-8") as env_file:
        env_file.write(contents)
        env_file.flush()
        os.fsync(env_file.fileno())
    os.chmod(ENV_FILE, 0o600)
    (ROOT / "videos").mkdir(exist_ok=True)
    (ROOT / "backups").mkdir(mode=0o700, exist_ok=True)
    os.chmod(ROOT / "backups", 0o700)
    return values["BOOTSTRAP_PASSWORD"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a production .env for one isolated Mantik on-prem installation."
    )
    parser.add_argument(
        "--host", required=True, help="DNS name used by Caddy, e.g. mantik.site.lan"
    )
    parser.add_argument(
        "--rtsp-prefix",
        action="append",
        default=[],
        help="Recommended RTSP/RTSPS origin or host prefix; repeat per trusted camera network",
    )
    parser.add_argument(
        "--http-prefix",
        action="append",
        default=[],
        help="Explicit HTTP(S) camera/relay origin and path root; repeat per trusted source",
    )
    parser.add_argument(
        "--https-bind-address",
        default="0.0.0.0",
        help="Host interface used for HTTPS (default: all interfaces; restrict with the site firewall)",
    )
    parser.add_argument(
        "--edge-subnet",
        default="172.30.100.0/24",
        help="Private Docker subnet for Caddy and the API; choose a non-overlapping range",
    )
    parser.add_argument(
        "--data-subnet",
        default="172.30.101.0/24",
        help="Private Docker subnet for the API and PostgreSQL; choose a non-overlapping range",
    )
    args = parser.parse_args()
    try:
        initial_password = setup(
            args.host,
            args.rtsp_prefix,
            args.https_bind_address,
            args.edge_subnet,
            args.data_subnet,
            http_prefixes=args.http_prefix,
        )
    except (FileExistsError, FileNotFoundError, ValueError) as exc:
        print(f"Setup failed: {exc}", file=sys.stderr)
        return 2

    print(f"Created {ENV_FILE} with mode 0600")
    print("Initial administrator username: admin")
    print(f"Initial temporary password (shown once): {initial_password}")
    print("The admin must change this password on first sign-in. Deliver credentials privately.")
    print(
        "Trust the Caddy internal CA on approved client devices; do not expose the database or app port directly."
    )
    print(
        "Review .env camera allowlists and permit only the customer's actual source origins and path roots."
    )
    print("Keep the generated backup key and .env backup in separate, access-controlled storage.")
    print("Start the stack with: docker compose up --build -d")
    return 0


if __name__ == "__main__":
    sys.exit(main())
