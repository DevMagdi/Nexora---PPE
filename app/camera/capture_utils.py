from __future__ import annotations

from typing import Any

import cv2

from app.core.logging import get_logger

logger = get_logger(__name__)


def configure_capture_buffer(capture: Any, *, source_name: str, buffer_size: int) -> bool:
    """Ask OpenCV to retain only a small number of live frames.

    OpenCV backends differ: some webcams and FFmpeg/RTSP builds honor
    ``CAP_PROP_BUFFERSIZE`` while others ignore it. The setting is therefore a
    best-effort latency hint, never a reason to fail camera startup.
    """
    if buffer_size < 1:
        return False

    try:
        configured = bool(capture.set(cv2.CAP_PROP_BUFFERSIZE, buffer_size))
    except Exception as exc:  # backend-specific OpenCV failures are intentionally non-fatal
        logger.debug(
            "Could not configure low-latency buffer for %s capture (%s)",
            source_name,
            type(exc).__name__,
        )
        return False

    if not configured:
        logger.debug(
            "Capture backend does not support CAP_PROP_BUFFERSIZE for %s; "
            "continuing with backend defaults",
            source_name,
        )
    return configured
