"""Deployment preflight: python -m app.model_check [--smoke]."""

from __future__ import annotations

import argparse
import json
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate the single approved industrial PPE checkpoint"
    )
    parser.add_argument(
        "--smoke", action="store_true", help="Also infer a blank frame to verify the runtime"
    )
    args = parser.parse_args()
    try:
        from app.core.detector import PPEDetector

        detector = PPEDetector()
        if args.smoke:
            import numpy as np

            detector.detect(np.zeros((640, 640, 3), dtype=np.uint8))
        print(
            json.dumps(
                {
                    "status": "ready",
                    "weights": detector.weights_fingerprint,
                    "classes": detector.class_names,
                },
                indent=2,
            )
        )
        return 0
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Preflight failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
