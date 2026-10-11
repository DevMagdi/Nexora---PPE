from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    APP_ENV: Literal["dev", "staging", "prod"] = "dev"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS — عدّلها في الإنتاج لتحدد origins بعينها بدل "*"
    CORS_ORIGINS: list[str] = ["*"]

    # Security
    API_KEY: str = ""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ppe_detection.db"

    # Model
    MODEL_PATH: str = "Model/ppe.pt"

    # Global YOLO confidence passed to model(...) before per-class filtering
    DETECTION_CONFIDENCE: float = 0.5

    # Per-class confidence thresholds (post-filtering)
    # Example:
    # DEFAULT_CLASS_CONF=0.25
    # CLASS_CONF_THRESHOLDS="10:0.40,8:0.20"
    DEFAULT_CLASS_CONF: float = 0.25
    CLASS_CONF_THRESHOLDS: str = ""

    # Violation frames storage
    FRAMES_DIR: str = "violation_frames"
    MAX_FRAME_AGE_DAYS: int = 30  # 0 أو أقل = تعطيل التنظيف التلقائي
    FRAME_CLEANUP_INTERVAL_HOURS: float = 6.0

    # Alert timing
    ALERT_COOLDOWN_SECONDS: int = 10
    VIOLATION_PERSIST_SECONDS: int = 10
    ALERT_DISPLAY_SECONDS: float = 3.0  # مدة ظهور "Alert Sent" على الفريم

    # Camera loop timing
    FRAME_READ_RETRY_DELAY_SECONDS: float = 0.05
    STREAM_FPS_DELAY_SECONDS: float = 0.04  # ~25 fps لبث MJPEG

    # Email
    SENDER_EMAIL: str = ""
    RECEIVER_EMAIL: str = ""
    EMAIL_PASSWORD: str = ""
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    ALERT_SMTP_TIMEOUT_SECONDS: float = 10.0

    # Optional webhook alerts
    SLACK_WEBHOOK_URL: str = ""
    WEBHOOK_URL: str = ""
    WEBHOOK_TIMEOUT_SECONDS: float = 10.0

    # RTSP allowlist (SSRF protection)
    ALLOWED_RTSP_PREFIXES: str = ""

    def parse_class_thresholds(self) -> dict[int, float]:
        """
        Parses CLASS_CONF_THRESHOLDS string like:
        "10:0.40,8:0.20" into {10: 0.40, 8: 0.20}
        """
        out: dict[int, float] = {}
        s = (self.CLASS_CONF_THRESHOLDS or "").strip()
        if not s:
            return out

        for part in s.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            try:
                out[int(k.strip())] = float(v.strip())
            except ValueError:
                continue
        return out


settings = Settings()