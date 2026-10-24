from __future__ import annotations

from pathlib import Path

MODEL_FILENAME = "ppe_unified_best.pt"
REPO_ROOT = Path(__file__).resolve().parents[2]


def validate_model_path(value: str) -> Path:
    """Restrict every entry point to the one approved local checkpoint."""
    path = Path(value)
    if path.name != MODEL_FILENAME or "://" in value:
        raise ValueError(f"PPE_MODEL_PATH must point only to {MODEL_FILENAME}")
    if not path.is_absolute():
        path = REPO_ROOT / path
    resolved = path.resolve()
    if resolved.name != MODEL_FILENAME:
        raise ValueError(f"The resolved weight file must be named {MODEL_FILENAME}")
    return resolved
