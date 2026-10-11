from __future__ import annotations

from fastapi import Request

from app.camera.manager import CameraManager


def get_camera_manager(request: Request) -> CameraManager:
    return request.app.state.camera_manager