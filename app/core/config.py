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
    MEDICAL_MODEL_PATH: str = "Model/bestMedicalModel.pt"
    MEDICAL_DETECTION_CONFIDENCE: float = 0.15
    MEDICAL_DEFAULT_CLASS_CONF: float = 0.30
    MEDICAL_CLASS_CONF_THRESHOLDS: str = ""

    # Hybrid detector (Medical + Construction models fused on one frame)
    HYBRID_DETECTION_ENABLED: bool = True
    # الموديل الإنشائي بيدّي فئة Person + ربط القطع للأشخاص لكاميرات القطاع الطبي
    HYBRID_CONSTRUCTION_ON_MEDICAL: bool = True
    # الموديل الطبي يقدر يضيف تحقق الكمامة/النظارة لكاميرات الإنشاءات (أثقل)
    HYBRID_MEDICAL_ON_CONSTRUCTION: bool = False
    HYBRID_MERGE_IOU: float = 0.55
    HYBRID_CONFLICT_IOU: float = 0.30
    HYBRID_OVERRIDE_MIN_CONTAINMENT: float = 0.45
    HYBRID_HEAD_REGION_RATIO: float = 0.32

    # Skin filter heuristics (calc_skin_ratio / distanceTransform / eye bridge)
    SKIN_FILTER_ENABLED: bool = True
    SKIN_BARE_HAND_ENABLED: bool = True
    SKIN_EYE_BRIDGE_ENABLED: bool = True
    SKIN_MIN_RATIO: float = 0.18
    SKIN_STRONG_RATIO: float = 0.32
    # نسبة رفض القفاز: لو 24% أو أكتر من بوكس "Gloves" جلد مكشوف => قفاز وهمي => NO-Gloves
    SKIN_GLOVE_REJECT_RATIO: float = 0.24
    SKIN_BARE_HAND_MIN_THICKNESS: float = 0.12
    SKIN_BARE_HAND_MIN_AREA: float = 0.10
    SKIN_EYE_BRIDGE_MIN_SKIN_RATIO: float = 0.22
    SKIN_GLASS_CONFIRM_MIN_RATIO: float = 0.05
    SKIN_SYNTHETIC_MIN_CONF: float = 0.45

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
