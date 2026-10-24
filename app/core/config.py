from __future__ import annotations

import base64
import binascii
import ipaddress
import secrets
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.password_policy import generate_password, password_issues

# HS256 (RFC 7518, Section 3.2) needs a key of at least 32 bytes / 256 bits.
# PyJWT only emits InsecureKeyLengthWarning for short keys, so Nexora validates
# the secret at startup instead and fails fast with an actionable message.
JWT_SECRET_MIN_BYTES = 32
JWT_SECRET_MIN_UNIQUE_CHARS = 16


def jwt_secret_issues(secret: str) -> list[str]:
    """Return human-readable problems with a JWT HMAC secret (empty = strong)."""
    value = secret or ""
    issues: list[str] = []
    secret_len = len(value.encode("utf-8"))
    if secret_len < JWT_SECRET_MIN_BYTES:
        issues.append(
            f"it is {secret_len} bytes long but HS256 needs at least "
            f"{JWT_SECRET_MIN_BYTES} bytes (RFC 7518, Section 3.2)"
        )
    if len(set(value)) < JWT_SECRET_MIN_UNIQUE_CHARS:
        issues.append("it looks low-entropy (too few distinct characters for a random secret)")
    return issues


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True,
    )

    # Application
    APP_ENV: Literal["dev", "staging", "prod"] = "dev"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Exact origins/hostnames; production rejects wildcard values.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    ALLOWED_HOSTS: str = "*"
    # Only trust X-Forwarded-For from explicitly configured reverse proxies.
    TRUSTED_PROXIES: str = ""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ppe_detection.db"
    DB_SQL_ECHO: bool = False
    DB_MIGRATION_CONNECT_TIMEOUT_SECONDS: int = 15
    DB_MIGRATION_LOCK_TIMEOUT_MS: int = 15_000

    # Authentication & bootstrap account. Defaults are random and development-only.
    JWT_SECRET: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    JWT_ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 240
    MEDIA_TOKEN_EXPIRE_MINUTES: int = 10
    ACCESS_COOKIE_NAME: str = "nexora_access"
    MEDIA_COOKIE_NAME: str = "nexora_media"
    BOOTSTRAP_USERNAME: str = "admin"
    BOOTSTRAP_PASSWORD: str = Field(default_factory=generate_password)
    BACKUP_ENCRYPTION_KEY: str = ""
    BACKUP_DIR: str = "backups"

    # Source security (SSRF & path traversal protection)
    ALLOWED_RTSP_PREFIXES: str = ""
    ALLOWED_VIDEO_DIR: str = ""

    # Login defense
    LOGIN_RATE_LIMIT: int = 5
    LOGIN_RATE_WINDOW_SECONDS: int = 60
    LOGIN_LOCKOUT_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15

    # Exactly one deployment artifact; no fallback or secondary detector.
    PPE_MODEL_PATH: str = "Model/ppe_unified_best.pt"
    PPE_MODEL_SHA256: str = ""
    DETECTION_CONFIDENCE: float = Field(default=0.50, ge=0.45, le=0.95)
    UPLOADS_DIR: str = "videos/uploads"
    MAX_UPLOAD_MB: int = Field(default=100, ge=1, le=1024)
    MAX_IMAGE_PIXELS: int = Field(default=24_000_000, ge=1)
    MAX_UPLOAD_VIDEO_SECONDS: int = Field(default=120, ge=1, le=3600)

    # Violation frames storage
    FRAMES_DIR: str = "violation_frames"
    MAX_FRAME_AGE_DAYS: int = 30
    FRAME_CLEANUP_INTERVAL_HOURS: float = 6.0

    # Alert timing
    ALERT_COOLDOWN_SECONDS: int = 60
    VIOLATION_PERSIST_SECONDS: int = 8
    VIOLATION_PERSIST_FLOOR_SECONDS: int = 8
    ALERT_DISPLAY_SECONDS: float = 3.0

    # Camera loop timing
    FRAME_READ_RETRY_DELAY_SECONDS: float = 0.05
    STREAM_FPS_DELAY_SECONDS: float = 0.04
    # Best-effort OpenCV queue depth for live RTSP sources; 1 favors freshness.
    RTSP_OPEN_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0, le=60)
    RTSP_READ_TIMEOUT_SECONDS: float = Field(default=5.0, gt=0, le=30)
    CAMERA_CAPTURE_BUFFER_SIZE: int = 1
    CAMERA_FIRST_FRAME_TIMEOUT_SECONDS: float = 10.0
    CAMERA_FRAME_STALE_SECONDS: float = 15.0

    # Email alerts
    SENDER_EMAIL: str = ""
    RECEIVER_EMAIL: str = ""
    EMAIL_PASSWORD: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    ALERT_SMTP_TIMEOUT_SECONDS: float = 10.0

    # Optional webhook alerts
    SLACK_WEBHOOK_URL: str = ""
    WEBHOOK_URL: str = ""
    WEBHOOK_TIMEOUT_SECONDS: float = 10.0

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        from app.core.model_policy import validate_model_path

        validate_model_path(self.PPE_MODEL_PATH)
        if self.PPE_MODEL_SHA256 and (
            len(self.PPE_MODEL_SHA256) != 64
            or any(c not in "0123456789abcdef" for c in self.PPE_MODEL_SHA256.lower())
        ):
            raise ValueError("PPE_MODEL_SHA256 must be a 64-character SHA-256 hex digest")
        if self.VIOLATION_PERSIST_SECONDS < 1 or self.VIOLATION_PERSIST_FLOOR_SECONDS < 1:
            raise ValueError("Violation persistence settings must be positive")
        if self.ALERT_COOLDOWN_SECONDS < 1:
            raise ValueError("ALERT_COOLDOWN_SECONDS must be positive")
        for proxy in self.TRUSTED_PROXIES.split(","):
            if proxy.strip():
                ipaddress.ip_network(proxy.strip(), strict=False)
        if self.LOGIN_RATE_LIMIT < 1 or self.LOGIN_RATE_WINDOW_SECONDS < 1:
            raise ValueError("Login rate limit settings must be positive")
        if self.LOGIN_LOCKOUT_ATTEMPTS < 1 or self.LOGIN_LOCKOUT_MINUTES < 1:
            raise ValueError("Login lockout settings must be positive")
        if self.DB_MIGRATION_CONNECT_TIMEOUT_SECONDS < 1:
            raise ValueError("DB_MIGRATION_CONNECT_TIMEOUT_SECONDS must be positive")
        if self.DB_MIGRATION_LOCK_TIMEOUT_MS < 1:
            raise ValueError("DB_MIGRATION_LOCK_TIMEOUT_MS must be positive")
        if self.CAMERA_FIRST_FRAME_TIMEOUT_SECONDS <= 0 or self.CAMERA_FRAME_STALE_SECONDS <= 0:
            raise ValueError("Camera frame timeout settings must be positive")
        if self.CAMERA_CAPTURE_BUFFER_SIZE < 1:
            raise ValueError("CAMERA_CAPTURE_BUFFER_SIZE must be at least 1")

        # A short JWT secret triggers PyJWT's InsecureKeyLengthWarning at login
        # time and makes session/media tokens forgeable, so reject it in every
        # environment (dev included) instead of only warning in the request log.
        # The random dev default is strong; only an explicitly configured weak
        # value can reach this error.
        secret_issues = jwt_secret_issues(self.JWT_SECRET)
        if secret_issues:
            raise ValueError(
                "JWT_SECRET is too weak for HS256: "
                + "; ".join(secret_issues)
                + ". Generate a strong value with `python scripts/gen_jwt_secret.py` "
                "and set JWT_SECRET in your .env (or unset it in dev to use an "
                "ephemeral random key)."
            )

        if self.APP_ENV != "prod":
            return self

        missing_secrets = [
            name
            for name in ("JWT_SECRET", "BOOTSTRAP_PASSWORD", "BACKUP_ENCRYPTION_KEY")
            if name not in self.model_fields_set
        ]
        if missing_secrets:
            raise ValueError(
                "Production requires explicitly configured secrets: " + ", ".join(missing_secrets)
            )

        # JWT strength is already enforced for every environment above; production
        # additionally requires the secret to be explicitly configured (checked
        # via model_fields_set) instead of falling back to a random default.
        issues = password_issues(self.BOOTSTRAP_PASSWORD, self.BOOTSTRAP_USERNAME)
        if issues:
            raise ValueError("BOOTSTRAP_PASSWORD does not meet policy: " + "; ".join(issues))
        try:
            backup_key = base64.urlsafe_b64decode(
                self.BACKUP_ENCRYPTION_KEY + "=" * (-len(self.BACKUP_ENCRYPTION_KEY) % 4)
            )
        except (binascii.Error, ValueError) as exc:
            raise ValueError("BACKUP_ENCRYPTION_KEY must be a URL-safe base64 256-bit key") from exc
        if len(backup_key) != 32:
            raise ValueError("BACKUP_ENCRYPTION_KEY must decode to exactly 32 bytes")

        if not 60 <= self.ACCESS_TOKEN_EXPIRE_MINUTES <= 480:
            raise ValueError("Production access tokens must expire between 60 and 480 minutes")
        if not 5 <= self.MEDIA_TOKEN_EXPIRE_MINUTES <= 15:
            raise ValueError("MEDIA_TOKEN_EXPIRE_MINUTES must be between 5 and 15 minutes")
        if self.DB_SQL_ECHO:
            raise ValueError("DB_SQL_ECHO must be disabled in production")

        origins = self.cors_origins
        if not origins or any("*" in origin for origin in origins):
            raise ValueError(
                "Production CORS_ORIGINS must contain exact trusted origins; wildcards are forbidden"
            )
        for origin in origins:
            parsed = urlsplit(origin)
            try:
                port = parsed.port
                if port == 0:
                    raise ValueError("origin port cannot be zero")
            except ValueError as exc:
                raise ValueError(f"Invalid CORS origin: {origin!r}") from exc
            if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"}:
                raise ValueError(f"Invalid CORS origin: {origin!r}")
            if parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise ValueError(f"Invalid CORS origin: {origin!r}")

        hosts = self.allowed_hosts
        if not hosts or any("*" in host for host in hosts):
            raise ValueError(
                "Production ALLOWED_HOSTS must list exact hostnames; wildcards are forbidden"
            )
        for host in hosts:
            parsed_host = urlsplit(f"//{host}")
            try:
                port = parsed_host.port
                if port == 0:
                    raise ValueError("host port cannot be zero")
            except ValueError as exc:
                raise ValueError(f"Invalid ALLOWED_HOSTS entry: {host!r}") from exc
            if (
                not parsed_host.hostname
                or parsed_host.path
                or parsed_host.query
                or parsed_host.fragment
                or parsed_host.username
                or parsed_host.password
            ):
                raise ValueError(f"Invalid ALLOWED_HOSTS entry: {host!r}")

        if not self.rtsp_prefixes:
            raise ValueError("Production must set ALLOWED_RTSP_PREFIXES to camera network prefixes")
        for prefix in self.rtsp_prefixes:
            parsed = urlsplit(prefix)
            try:
                port = parsed.port
                if port == 0:
                    raise ValueError("camera port cannot be zero")
            except ValueError as exc:
                raise ValueError(f"Invalid ALLOWED_RTSP_PREFIXES entry: {prefix!r}") from exc
            if (
                "*" in prefix
                or parsed.scheme not in {"rtsp", "rtsps"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError(f"Invalid ALLOWED_RTSP_PREFIXES entry: {prefix!r}")

        if not self.ALLOWED_VIDEO_DIR or not self.ALLOWED_VIDEO_DIR.strip():
            raise ValueError("Production must set ALLOWED_VIDEO_DIR to a dedicated video directory")
        if not self.ALLOWED_VIDEO_DIR.startswith("/"):
            raise ValueError("Production ALLOWED_VIDEO_DIR must be an absolute path")
        if Path(self.ALLOWED_VIDEO_DIR).resolve() == Path("/"):
            raise ValueError("Production ALLOWED_VIDEO_DIR must not be the filesystem root")
        if not self.BACKUP_DIR.startswith("/"):
            raise ValueError("Production BACKUP_DIR must be an absolute path")

        return self

    @property
    def cors_origins(self) -> list[str]:
        return [
            origin.strip().rstrip("/") for origin in self.CORS_ORIGINS.split(",") if origin.strip()
        ]

    @property
    def allowed_hosts(self) -> list[str]:
        return [host.strip().lower() for host in self.ALLOWED_HOSTS.split(",") if host.strip()]

    @property
    def trusted_proxy_networks(self) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
        networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
        for value in self.TRUSTED_PROXIES.split(","):
            value = value.strip()
            if value:
                networks.append(ipaddress.ip_network(value, strict=False))
        return networks

    @property
    def rtsp_prefixes(self) -> list[str]:
        return [
            item.strip().rstrip("/")
            for item in self.ALLOWED_RTSP_PREFIXES.split(",")
            if item.strip()
        ]


settings = Settings()
