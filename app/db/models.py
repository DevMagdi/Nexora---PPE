from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(
        String(20), default="construction", nullable=False
    )  # construction|medical|both
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Camera(Base):
    __tablename__ = "cameras"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # webcam | rtsp | file
    source_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    profile: Mapped[str] = mapped_column(
        String(20), default="construction", nullable=False
    )  # construction|medical
    enabled_classes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    violations: Mapped[list[Violation]] = relationship(
        "Violation",
        back_populates="camera",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Violation(Base):
    __tablename__ = "violations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    camera_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cameras.id", ondelete="CASCADE"), nullable=False, index=True
    )
    violation_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=utc_now, index=True)
    frame_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    camera: Mapped[Camera] = relationship("Camera", back_populates="violations")
    alert_logs: Mapped[list[AlertLog]] = relationship(
        "AlertLog",
        back_populates="violation",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class AlertLog(Base):
    __tablename__ = "alert_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    violation_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("violations.id", ondelete="CASCADE"), nullable=True
    )
    handler_type: Mapped[str] = mapped_column(String(50), nullable=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    error_msg: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    violation: Mapped[Violation | None] = relationship("Violation", back_populates="alert_logs")
