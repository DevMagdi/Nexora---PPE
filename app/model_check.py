"""Deployment preflight: python -m app.model_check [--smoke].

Only the approved ``Model/ppe.pt`` weight is accepted. Any unified reference
(``ppe_unified_best.pt`` or any name containing ``unified``) fails the preflight
with a single, explicit message.
"""

from __future__ import annotations

import argparse
import json
import sys

from app.core.model_policy import UNIFIED_REJECTION_MESSAGE


def _error_message(exc: BaseException) -> str:
    """Collapse pydantic/loader wrappers to the actionable policy sentence."""
    text = str(exc)
    if UNIFIED_REJECTION_MESSAGE in text:
        return UNIFIED_REJECTION_MESSAGE
    return text


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the single approved industrial PPE checkpoint (Model/ppe.pt)"
    )
    parser.add_argument(
        "--smoke", action="store_true", help="Also infer a blank frame to verify the runtime"
    )
    args = parser.parse_args()
    try:
        from app.core.config import settings

        # Re-assert the name policy on the configured path before loading anything.
        from app.core.model_policy import validate_model_path
        from app.core.ppe import EXPECTED_MODEL_CLASSES, IGNORED_MODEL_CLASSES

        validate_model_path(settings.PPE_MODEL_PATH)

        from app.core.detector import PPEDetector

        detector = PPEDetector()
        if args.smoke:
            import numpy as np

            detector.detect(np.zeros((640, 640, 3), dtype=np.uint8))
        loaded = set(detector.class_names.values())
        print(
            json.dumps(
                {
                    "status": "ready",
                    "weights": detector.weights_fingerprint,
                    "model_path": f"Model/{detector.weights_fingerprint['filename']}",
                    "classes": detector.class_names,
                    "loaded_classes": sorted(loaded),
                    "ignored_classes": [name for name in IGNORED_MODEL_CLASSES if name in loaded],
                    "expected_checkpoint_classes": list(EXPECTED_MODEL_CLASSES),
                    "sha256_pin_enforced": bool(settings.PPE_MODEL_SHA256),
                },
                indent=2,
            )
        )
        return 0
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Preflight failed: {_error_message(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
