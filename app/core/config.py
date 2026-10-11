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

    # CORS
    CORS_ORIGINS: str = "*"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ppe_detection.db"

    # JWT Auth
    JWT_SECRET: str = "CHANGE_ME_SUPER_SECRET"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    BOOTSTRAP_USERNAME: str = "admin"
    BOOTSTRAP_PASSWORD: str = "admin123"
    BOOTSTRAP_SECTOR: Literal["construction", "medical", "both"] = "construction"

    # Source security (SSRF & Path Traversal protection)
    ALLOWED_RTSP_PREFIXES: str = ""
    ALLOWED_VIDEO_DIR: str = ""

    # Construction Model
    CONSTRUCTION_MODEL_PATH: str = "Model/ppe.pt"
    CONSTRUCTION_DETECTION_CONFIDENCE: float = 0.10
    CONSTRUCTION_DEFAULT_CLASS_CONF: float = 0.25
    CONSTRUCTION_CLASS_CONF_THRESHOLDS: str = ""

    # Medical Model
    MEDICAL_MODEL_PATH: str = "Model/bestMedicalModel2.pt"
    MEDICAL_DETECTION_CONFIDENCE: float = 0.15
    MEDICAL_DEFAULT_CLASS_CONF: float = 0.30
    MEDICAL_CLASS_CONF_THRESHOLDS: str = ""

    # Violation frames storage
    FRAMES_DIR: str = "violation_frames"
    MAX_FRAME_AGE_DAYS: int = 30
    FRAME_CLEANUP_INTERVAL_HOURS: float = 6.0

    # Alert timing
    ALERT_COOLDOWN_SECONDS: int = 60
    VIOLATION_PERSIST_SECONDS: int = 8
    MEDICAL_VIOLATION_PERSIST_SECONDS: int = 3
    ALERT_DISPLAY_SECONDS: float = 3.0

    # Camera loop timing
    FRAME_READ_RETRY_DELAY_SECONDS: float = 0.05
    STREAM_FPS_DELAY_SECONDS: float = 0.04  # ~25 fps

    # Email alerts
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

    @staticmethod
    def parse_class_thresholds_str(s: str) -> dict[int, float]:
        """Parses '10:0.40,8:0.20' into {10: 0.40, 8: 0.20}."""
        out: dict[int, float] = {}
        s = (s or "").strip()
        if not s:
            return out
        for part in s.split(","):
            part = part.strip()
            if not part or ":" not in part:
                continue
            k, v = part.split(":", 1)
            try:
                out[int(k.strip())] = float(v.strip())
            except ValueError:
                continue
        return out


settings = Settings()
