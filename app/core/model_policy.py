"""The single approved weight policy for Mantik PPE.

There is exactly one accepted artifact: ``Model/ppe.pt``. Any path that still
carries the historical "unified" naming (``ppe_unified_best.pt`` or any name
containing ``unified``) is rejected before the process can start, so a renamed
or substituted checkpoint can never silently become the production model.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

MODEL_FILENAME = "ppe.pt"
MODEL_DIRNAME = "Model"
DEFAULT_MODEL_PATH = f"{MODEL_DIRNAME}/{MODEL_FILENAME}"
REPO_ROOT = Path(__file__).resolve().parents[2]

# Recommended pin for the approved export; verified only when configured through
# PPE_MODEL_SHA256 (see app/core/config.py).
APPROVED_MODEL_SHA256 = "15c758c669eeb557d9439bd18c5a3929680238122a95286210ca69e11af8218a"

UNIFIED_REJECTION_MESSAGE = (
    f"Only approved weight {DEFAULT_MODEL_PATH} is allowed; unified weights are rejected."
)

# Any of these fragments marks a forbidden (unified) weight reference.
FORBIDDEN_MODEL_MARKERS: tuple[str, ...] = ("unified", "ppe_unified_best")


def is_forbidden_model_reference(value: str | Path) -> bool:
    haystack = str(value or "").casefold()
    return any(marker in haystack for marker in FORBIDDEN_MODEL_MARKERS)


def validate_model_path(value: str) -> Path:
    """Restrict every entry point to the one approved local checkpoint."""
    text = str(value or "").strip()
    if is_forbidden_model_reference(text):
        raise ValueError(UNIFIED_REJECTION_MESSAGE)
    if not text or "://" in text:
        raise ValueError(
            f"PPE_MODEL_PATH must point to the approved weight {DEFAULT_MODEL_PATH}; "
            "downloads and remote checkpoints are not permitted"
        )
    path = Path(text)
    if path.name.casefold() != MODEL_FILENAME.casefold() or path.name != MODEL_FILENAME:
        raise ValueError(
            f"Only approved weight {DEFAULT_MODEL_PATH} is allowed; "
            f"the file must be named exactly {MODEL_FILENAME}"
        )
    if not path.is_absolute():
        path = REPO_ROOT / path
    resolved = path.resolve()
    if is_forbidden_model_reference(resolved):
        raise ValueError(UNIFIED_REJECTION_MESSAGE)
    if resolved.name != MODEL_FILENAME:
        raise ValueError(
            f"The resolved weight file must be named {MODEL_FILENAME}; refusing {resolved.name!r}"
        )
    return resolved


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
