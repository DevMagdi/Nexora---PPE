"""
اختبارات استدلال حقيقية على الوزن الطبي المعتمد (``Model/bestMedicalModel_FINAL.pt``).

الملف ده بيحمّل الموديل فعليًا (torch + ultralytics) وبيشغّل استدلال على إطارات
صناعية وفيديو الاختبار المرفق، للتأكد إن العقد البرمجي والنظام كله شغال مع
الأوزان المعتمدة. الفحوصات الثقيلة معلّمة بـ ``slow``:

```bash
pytest -q tests/integration/test_medical_model_inference.py -m "not slow"
pytest -q tests/integration/test_medical_model_inference.py
```

لو حزمة الـ ML أو ملف الأوزان مش موجودين، الاختبارات بتتخطى (skip) برسالة واضحة
بدل ما تفشل.
"""

from __future__ import annotations

import hashlib
import statistics
import threading
import time
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
cv2 = pytest.importorskip("cv2")
pytest.importorskip("torch")
pytest.importorskip("ultralytics")

REPO_ROOT = Path(__file__).resolve().parents[2]
APPROVED_WEIGHTS = REPO_ROOT / "Model" / "bestMedicalModel_FINAL.pt"
CONSTRUCTION_WEIGHTS = REPO_ROOT / "Model" / "ppe.pt"
SAMPLE_VIDEO = REPO_ROOT / "test_assets" / "sample.avi"

pytestmark = pytest.mark.skipif(
    not APPROVED_WEIGHTS.exists(),
    reason="approved medical weights are not present in this checkout",
)

MEDICAL_CLASS_NAMES = (
    "full cover",
    "goggle",
    "hand gloves",
    "head cap",
    "lab coat",
    "mask",
    "no goggle",
    "no hand gloves",
    "no head cap",
    "no mask",
    "shoe cover",
)

RNG_SEED = 20261012


def synthetic(kind: str, height: int = 640, width: int = 640, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    if kind == "noise":
        return rng.integers(0, 256, (height, width, 3), dtype=np.uint8)
    if kind == "black":
        return np.zeros((height, width, 3), np.uint8)
    if kind == "white":
        return np.full((height, width, 3), 255, np.uint8)
    if kind == "gray":
        return np.full((height, width, 3), 127, np.uint8)
    if kind == "gradient":
        column = np.linspace(0, 255, width, dtype=np.uint8)
        grid = np.tile(column, (height, 1))
        return cv2.merge([grid, np.fliplr(grid), grid])
    if kind == "blocks":
        image = np.zeros((height, width, 3), np.uint8)
        for _ in range(6):
            x1, y1 = int(rng.integers(0, width - 1)), int(rng.integers(0, height - 1))
            x2, y2 = int(rng.integers(x1 + 1, width)), int(rng.integers(y1 + 1, height))
            image[y1:y2, x1:x2] = rng.integers(0, 256, 3)
        return image
    if kind == "figure":
        image = np.full((height, width, 3), 235, np.uint8)
        cv2.rectangle(
            image, (width // 4, height // 6), (3 * width // 4, height), (90, 110, 150), -1
        )
        cv2.circle(image, (width // 2, height // 5), max(1, width // 14), (190, 160, 140), -1)
        return image
    raise ValueError(kind)


def boxes_of(result) -> list[tuple[int, float, tuple[float, float, float, float]]]:
    boxes = result.boxes
    if boxes is None or len(boxes) == 0:
        return []
    xyxy = boxes.xyxy.cpu().numpy()
    conf = boxes.conf.cpu().numpy()
    cls = boxes.cls.cpu().numpy().astype(int)
    return [
        (int(c), float(p), tuple(float(v) for v in box))
        for c, p, box in zip(cls, conf, xyxy, strict=True)
    ]


def assert_boxes_are_sane(boxes, frame_shape) -> None:
    height, width = frame_shape[:2]
    for _cls_id, confidence, (x1, y1, x2, y2) in boxes:
        assert 0.0 <= confidence <= 1.0
        assert all(np.isfinite([x1, y1, x2, y2]))
        assert x2 >= x1 and y2 >= y1
        assert -1 <= x1 <= x2 <= width + 1
        assert -1 <= y1 <= y2 <= height + 1


@pytest.fixture(scope="session")
def medical_model():
    from ultralytics import YOLO

    return YOLO(str(APPROVED_WEIGHTS))


@pytest.fixture(scope="session")
def detector():
    from app.core.detector import PPEDetector

    return PPEDetector(
        "Model/bestMedicalModel_FINAL.pt",
        0.25,
        0.35,
        "",
        fallbacks=("Model/ppe_medical.pt",),
        setting_name="MEDICAL_MODEL_PATH",
    )


# ── العقد الأساسي ────────────────────────────────────────────────────────────
def test_approved_weights_load_with_documented_classes(medical_model):
    assert tuple(medical_model.names.values()) == MEDICAL_CLASS_NAMES
    assert medical_model.model.nc == len(MEDICAL_CLASS_NAMES) == 11
    assert medical_model.task == "detect"


def test_detector_reports_weights_fingerprint(detector):
    digest = hashlib.sha256(APPROVED_WEIGHTS.read_bytes()).hexdigest()
    assert detector.weights_fingerprint["sha256"] == digest
    assert detector.weights_fingerprint["size_bytes"] == APPROVED_WEIGHTS.stat().st_size


def test_raw_forward_contract_is_15x_anchors(medical_model):
    import torch

    with torch.no_grad():
        prediction = medical_model.model(torch.zeros(1, 3, 640, 640))
    tensor = prediction[0] if isinstance(prediction, (list, tuple)) else prediction
    assert tuple(tensor.shape) == (1, 4 + len(MEDICAL_CLASS_NAMES), 8400)
    assert torch.isfinite(tensor).all()


def test_predictions_are_deterministic(medical_model):
    frame = synthetic("figure", seed=1)
    first = medical_model.predict(frame, conf=0.05, verbose=False, device="cpu")[0]
    second = medical_model.predict(frame, conf=0.05, verbose=False, device="cpu")[0]

    first_boxes, second_boxes = boxes_of(first), boxes_of(second)
    assert len(first_boxes) == len(second_boxes)
    for (cls_a, conf_a, box_a), (cls_b, conf_b, box_b) in zip(
        first_boxes, second_boxes, strict=True
    ):
        assert cls_a == cls_b
        assert conf_a == pytest.approx(conf_b, abs=1e-6)
        assert box_a == pytest.approx(box_b, abs=1e-6)


@pytest.mark.parametrize(
    "kind,height,width",
    [
        ("black", 640, 640),
        ("white", 640, 640),
        ("gray", 640, 640),
        ("noise", 640, 640),
        ("gradient", 1080, 1920),
        ("blocks", 101, 4097),
        ("figure", 480, 640),
        ("noise", 1, 1),
        ("noise", 3, 7),
    ],
)
def test_synthetic_frames_never_produce_invalid_boxes(medical_model, kind, height, width):
    frame = synthetic(kind, height, width, seed=hash((kind, height, width)) % 10_000)
    result = medical_model.predict(frame, conf=0.25, verbose=False, device="cpu")[0]
    assert_boxes_are_sane(boxes_of(result), result.orig_shape)


def test_batch_inference_matches_single_image_calls(medical_model):
    frames = [synthetic("blocks", seed=seed) for seed in range(4)]
    singles = [
        boxes_of(medical_model.predict(f, conf=0.05, verbose=False, device="cpu")[0])
        for f in frames
    ]
    batched = [
        boxes_of(r) for r in medical_model.predict(frames, conf=0.05, verbose=False, device="cpu")
    ]

    assert [len(s) for s in singles] == [len(b) for b in batched]
    for single, batch in zip(singles, batched, strict=True):
        for (_c1, conf_a, box_a), (_c2, conf_b, box_b) in zip(single, batch, strict=True):
            assert conf_a == pytest.approx(conf_b, abs=1e-4)
            assert box_a == pytest.approx(box_b, abs=1e-3)


def test_grayscale_and_float_inputs_are_accepted(medical_model):
    base = synthetic("gradient")
    variants = {
        "grayscale_2d": cv2.cvtColor(base, cv2.COLOR_BGR2GRAY),
        "float32_0_1": base.astype(np.float32) / 255.0,
        "uint16": (base.astype(np.uint16) * 257),
        "bgra": cv2.cvtColor(base, cv2.COLOR_BGR2BGRA),
        "non_contiguous": base[::2, ::2][:, :, ::-1],
    }
    for label, frame in variants.items():
        result = medical_model.predict(frame, conf=0.25, verbose=False, device="cpu")[0]
        assert_boxes_are_sane(boxes_of(result), result.orig_shape), label


def test_confidence_threshold_is_monotonic(medical_model):
    frame = synthetic("figure", seed=3)
    counts = [
        len(boxes_of(medical_model.predict(frame, conf=conf, verbose=False, device="cpu")[0]))
        for conf in (0.05, 0.1, 0.25, 0.5, 0.75, 0.9)
    ]
    assert counts == sorted(counts, reverse=True), counts


def test_sample_video_frames_are_processed(medical_model):
    if not SAMPLE_VIDEO.exists():
        pytest.skip("bundled sample video is missing")
    capture = cv2.VideoCapture(str(SAMPLE_VIDEO))
    processed = 0
    while processed < 10:
        ok, frame = capture.read()
        if not ok:
            break
        result = medical_model.predict(frame, conf=0.25, verbose=False, device="cpu")[0]
        assert_boxes_are_sane(boxes_of(result), result.orig_shape)
        processed += 1
    capture.release()
    assert processed == 10


# ── تكامل النظام ─────────────────────────────────────────────────────────────
def test_detector_maps_every_class_to_a_canonical_name(detector):
    from app.core.ppe import canonical_class_name

    mapping = {name: canonical_class_name(name) for name in detector.class_names.values()}
    assert mapping == {
        "full cover": "Full Cover",
        "goggle": "Goggles",
        "hand gloves": "Gloves",
        "head cap": "Head Cap",
        "lab coat": "Lab Coat",
        "mask": "Mask",
        "no goggle": "NO-Goggles",
        "no hand gloves": "NO-Gloves",
        "no head cap": "NO-Head Cap",
        "no mask": "NO-Mask",
        "shoe cover": "Shoe Cover",
    }


def test_detector_detections_are_valid_frames(detector):
    frame = synthetic("figure", seed=5)
    detections = detector.detect(frame)
    assert_boxes_are_sane(
        [(d.class_id, d.confidence, (d.x1, d.y1, d.x2, d.y2)) for d in detections], frame.shape
    )
    for detection in detections:
        assert 0 <= detection.class_id < len(MEDICAL_CLASS_NAMES)
        assert detection.class_name in detector.class_names.values()


def test_class_specific_thresholds_shrink_the_result_set():
    from app.core.detector import PPEDetector

    frame = synthetic("figure", seed=6)
    strict = PPEDetector("Model/bestMedicalModel_FINAL.pt", 0.25, 0.35, "9:0.9,5:0.9")
    loose = PPEDetector("Model/bestMedicalModel_FINAL.pt", 0.05, 0.35, "9:0.3,5:0.3")

    strict_hits = [d for d in strict.detect(frame) if d.class_id in (5, 9)]
    loose_hits = [d for d in loose.detect(frame) if d.class_id in (5, 9)]
    assert len(strict_hits) <= len(loose_hits)
    assert all(d.confidence >= 0.9 for d in strict_hits)


def test_hybrid_pipeline_runs_with_real_weights(detector):
    if not CONSTRUCTION_WEIGHTS.exists():
        pytest.skip("construction weights are missing")
    from app.core.detector import PPEDetector
    from app.core.hybrid_detector import HybridPPEDetector

    construction = PPEDetector(
        "Model/ppe.pt", 0.25, 0.35, "", setting_name="CONSTRUCTION_MODEL_PATH"
    )
    hybrid = HybridPPEDetector(construction, detector, primary_profile="medical")
    frame = synthetic("figure", seed=7)

    detections = hybrid.detect(frame)
    assert isinstance(detections, list)
    for detection in detections:
        assert detection.confidence > 0
        assert detection.source

    # ملف الإنشاءات لازم يتصرف بنفس الشكل مع نفس الأوزان
    hybrid_construction = HybridPPEDetector(construction, detector, primary_profile="construction")
    assert isinstance(hybrid_construction.detect(frame), list)


def test_corrupt_weights_fail_fast_with_actionable_message(tmp_path, monkeypatch):
    from app.core.detector import PPEDetector

    model_dir = tmp_path / "Model"
    model_dir.mkdir()
    (model_dir / "empty.pt").write_bytes(b"")
    (model_dir / "truncated.pt").write_bytes(APPROVED_WEIGHTS.read_bytes()[: 64 * 1024])

    monkeypatch.chdir(tmp_path)
    for name, expected in (("Model/empty.pt", "empty"), ("Model/truncated.pt", "corrupt")):
        with pytest.raises(RuntimeError) as exc_info:
            PPEDetector(name, 0.25, 0.35, "", setting_name="MEDICAL_MODEL_PATH")
        message = str(exc_info.value)
        # الرسالة لازم تقول اسم الملف + الإعداد + إن الملف تالف/ناقص
        assert name in message
        assert "MEDICAL_MODEL_PATH" in message
        assert expected in message.lower() or "truncated" in message.lower()


def test_missing_weights_raise_clear_file_error(tmp_path, monkeypatch):
    from app.core.detector import PPEDetector

    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError, match="MEDICAL_MODEL_PATH"):
        PPEDetector(
            "Model/bestMedicalModel_FINAL.pt",
            fallbacks=("Model/ppe_medical.pt",),
            confidence=0.25,
            default_class_conf=0.35,
            setting_name="MEDICAL_MODEL_PATH",
        )


# ── الفحوصات الثقيلة (slow) ──────────────────────────────────────────────────
@pytest.mark.slow
def test_adversarial_transforms_keep_boxes_valid(medical_model):
    frame = synthetic("figure", seed=8)
    kernel = np.zeros((25, 25))
    kernel[12, :] = 1 / 25
    transforms = {
        "overexposed": np.clip(frame.astype(np.int16) + 120, 0, 255).astype(np.uint8),
        "underexposed": (frame.astype(np.int16) // 6).astype(np.uint8),
        "gamma_3": (np.power(frame / 255.0, 3.0) * 255).astype(np.uint8),
        "blurred": cv2.GaussianBlur(frame, (61, 61), 30),
        "jpeg_q5": cv2.imdecode(
            cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 5])[1], cv2.IMREAD_COLOR
        ),
        "rotated_90": cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE),
        "rotated_180": cv2.rotate(frame, cv2.ROTATE_180),
        "flipped": cv2.flip(frame, 1),
        "binarized": (frame > 127).astype(np.uint8) * 255,
        "upscaled_x3": cv2.resize(frame, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST),
        "downscaled_8x": cv2.resize(frame, None, fx=0.125, fy=0.125),
        "motion_blur": cv2.filter2D(frame, -1, kernel),
        "shot_noise": np.clip(
            frame.astype(np.int16)
            + np.random.default_rng(RNG_SEED).normal(0, 45, frame.shape).astype(np.int16),
            0,
            255,
        ).astype(np.uint8),
        "occluded_90pct": cv2.rectangle(
            frame.copy(),
            (0, 0),
            (int(frame.shape[1] * 0.95), int(frame.shape[0] * 0.95)),
            (0, 0, 0),
            -1,
        ),
    }
    for label, variant in transforms.items():
        result = medical_model.predict(variant, conf=0.05, verbose=False, device="cpu")[0]
        assert_boxes_are_sane(boxes_of(result), result.orig_shape), label


@pytest.mark.slow
def test_fuzz_random_frames(medical_model):
    rng = np.random.default_rng(RNG_SEED + 1)
    for seed in range(20):
        height = int(rng.integers(8, 900))
        width = int(rng.integers(8, 1200))
        kind = str(rng.choice(["noise", "blocks", "gradient", "black", "white"]))
        frame = synthetic(kind, height, width, seed)
        result = medical_model.predict(frame, conf=0.25, verbose=False, device="cpu")[0]
        assert_boxes_are_sane(boxes_of(result), result.orig_shape)


@pytest.mark.slow
def test_endurance_loop_keeps_results_identical(medical_model):
    frame = synthetic("figure", seed=9)
    baseline = boxes_of(medical_model.predict(frame, conf=0.05, verbose=False, device="cpu")[0])
    for index in range(60):
        mix = synthetic("noise", 480, 640, seed=index) if index % 2 else frame
        result = medical_model.predict(mix, conf=0.3, verbose=False, device="cpu")[0]
        assert_boxes_are_sane(boxes_of(result), result.orig_shape)
    after = boxes_of(medical_model.predict(frame, conf=0.05, verbose=False, device="cpu")[0])
    assert len(after) == len(baseline)
    for (_c1, conf_a, box_a), (_c2, conf_b, box_b) in zip(baseline, after, strict=True):
        assert conf_a == pytest.approx(conf_b, abs=1e-6)
        assert box_a == pytest.approx(box_b, abs=1e-6)


@pytest.mark.slow
def test_concurrent_detector_usage_is_consistent(detector):
    frame = synthetic("figure", seed=10)
    counts: list[int] = []
    errors: list[str] = []
    lock_times: list[float] = []

    def worker() -> None:
        try:
            for _ in range(5):
                started = time.time()
                counts.append(len(detector.detect(frame)))
                lock_times.append(time.time() - started)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert len(set(counts)) == 1, counts
    assert statistics.median(lock_times) < 5.0


@pytest.mark.slow
def test_latency_budget_on_cpu(medical_model):
    frames = [synthetic("blocks", 720, 1280, seed=seed) for seed in range(8)]
    latencies = []
    for frame in frames:
        started = time.time()
        medical_model.predict(frame, conf=0.25, verbose=False, device="cpu")
        latencies.append(time.time() - started)

    median = statistics.median(latencies)
    p95 = sorted(latencies)[int(0.95 * (len(latencies) - 1))]
    # حد فضفاض لبيئات CI البطيئة: إطار واحد لازم يخلص تحت ثانية واحدة
    assert median < 1.0, median
    assert p95 < 2.0, p95


@pytest.mark.slow
def test_large_batch_inference(medical_model):
    frames = [synthetic("noise", seed=seed) for seed in range(16)]
    results = medical_model.predict(frames, conf=0.3, verbose=False, device="cpu")
    assert len(results) == 16
    for result in results:
        assert_boxes_are_sane(boxes_of(result), result.orig_shape)


@pytest.mark.slow
def test_scale_and_nms_variants_do_not_break(medical_model):
    frame = synthetic("figure", seed=11)
    for scale in (0.5, 0.75, 1.0, 1.5, 2.0):
        interpolation = cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        resized = cv2.resize(frame, None, fx=scale, fy=scale, interpolation=interpolation)
        result = medical_model.predict(resized, conf=0.05, verbose=False, device="cpu")[0]
        assert_boxes_are_sane(boxes_of(result), result.orig_shape)

    for kwargs in (
        {"iou": 0.1},
        {"iou": 0.95},
        {"max_det": 1},
        {"agnostic_nms": True},
        {"rect": True},
    ):
        result = medical_model.predict(frame, conf=0.05, verbose=False, device="cpu", **kwargs)[0]
        assert_boxes_are_sane(boxes_of(result), result.orig_shape)
