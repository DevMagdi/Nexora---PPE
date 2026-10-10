from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Application
    APP_ENV: Literal["dev", "staging", "prod"] = "dev"
    LOG_LEVEL: str = "INFO"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # CORS — عدّلها في الإنتاج لتحدد origins بعينها بدل "*"
    CORS_ORIGINS: list[str] = ["*"]

    # Security
    # ⚠️ سيبها فاضية يفعّل "وضع dev" (مفيش حماية على الـ endpoints
    # الحساسة) مع تحذير في اللوج. لازم تتحدد قبل أي نشر production.
    API_KEY: str = ""

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ppe_detection.db"

    # Model
    MODEL_PATH: str = "Model/ppe.pt"
    DETECTION_CONFIDENCE: float = 0.5

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

    # RTSP allowlist (SSRF protection) — قائمة مفصولة بفواصل مثل:
    # "rtsp://192.168.1.,rtsp://localhost" — فاضية = بدون قيود (الافتراضي).
    ALLOWED_RTSP_PREFIXES: str = ""


settings = Settings()