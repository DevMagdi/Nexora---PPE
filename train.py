from __future__ import annotations

import argparse
import os
import sys

import cv2


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect YOLO detections and per-class confidence thresholds on a sample image."
    )
    parser.add_argument(
        "--model",
        default="Model/bestMedicalModel2.pt",
        help="Path to YOLO model weights (.pt)",
    )
    parser.add_argument(
        "--image",
        default="Visuals/ppe-public-view.png",
        help="Path to sample image to run inference on",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.05,
        help="Global YOLO confidence threshold",
    )
    parser.add_argument(
        "--default-class-conf",
        type=float,
        default=0.25,
        help="Default per-class confidence threshold",
    )
    args = parser.parse_args()

    if not os.path.exists(args.model):
        print(f"Error: Model file not found: {args.model}", file=sys.stderr)
        sys.exit(1)
    if not os.path.exists(args.image):
        print(f"Error: Image file not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    from ultralytics import YOLO

    class_conf = {
        2: 0.70,  # hand gloves
        5: 0.70,  # mask
        7: 0.15,  # no hand gloves
        8: 0.20,  # no head cap
        9: 0.30,  # no mask
    }

    focus_names = {
        "hand gloves",
        "no hand gloves",
        "mask",
        "no mask",
        "head cap",
        "no head cap",
        "goggle",
        "no goggle",
    }

    model = YOLO(args.model)
    img = cv2.imread(args.image)
    if img is None:
        print(f"Error: Could not decode image: {args.image}", file=sys.stderr)
        sys.exit(1)

    result = model.predict(img, conf=args.conf, verbose=False)[0]
    names = model.names

    raw = []
    for box in result.boxes or []:
        cls_id = int(box.cls[0])
        conf = float(box.conf[0])
        raw.append((names.get(cls_id, str(cls_id)), cls_id, conf))

    raw_sorted = sorted(raw, key=lambda x: -x[2])

    print("\n=== RAW (after YOLO conf filter only) top 30 ===")
    for item in raw_sorted[:30]:
        if item[0] in focus_names:
            print(item)

    filtered = []
    for name, cls_id, conf in raw_sorted:
        thr = class_conf.get(cls_id, args.default_class_conf)
        if conf >= thr:
            filtered.append((name, cls_id, conf, thr))

    print("\n=== FILTERED (like backend thresholds) ===")
    for name, cls_id, conf, thr in filtered:
        if name in focus_names:
            print(f"{name:14s} id={cls_id:2d} conf={conf:.3f} (thr={thr:.2f})")

    print("\n=== FILTERED top 30 (all classes) ===")
    for name, cls_id, conf, thr in filtered[:30]:
        print(f"{name:14s} id={cls_id:2d} conf={conf:.3f} (thr={thr:.2f})")


if __name__ == "__main__":
    main()
