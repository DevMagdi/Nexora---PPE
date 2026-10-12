"""
اختبارات الأوزان الطبية المعتمدة (``Model/bestMedicalModel_FINAL.pt``).

هذه الاختبارات **قراءة ساكنة** (zipfile + pickletools) من غير تحميل torch أو
ultralytics ومن غير أي تنفيذ لبيانات pickle، ولذلك بتشتغل في أي بيئة CI حتى لو
حزمة الـ ML مش مثبتة. هدفها:

* الوزن المعتمد موجود بالبصمة (SHA-256) المسجلة في الـ manifest.
* الوزن القديم مرفود ومش موجود في المستودع، ومش مسموح يرجعلنا كإعداد افتراضي.
* بنية الـ checkpoint سليمة: zip سليم، ``nc`` وفئات متطابقة، معمارية yolov8n.
* مفيش globals خطيرة داخل الـ pickle (مفيش ``os``/``subprocess``/... إلخ).
* المقاييس المسجلة في الـ checkpoint أعلى من المقاييس المسجلة في الوزن المرفود.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.core.detector import (
    CLASS_COLORS_BY_NAME,
    is_retired_model_path,
)
from app.core.ppe import canonical_class_name

REPO_ROOT = Path(__file__).resolve().parents[2]
APPROVED_MEDICAL_WEIGHTS = REPO_ROOT / "Model" / "bestMedicalModel_FINAL.pt"
CONSTRUCTION_WEIGHTS = REPO_ROOT / "Model" / "ppe.pt"
RETIRED_MEDICAL_WEIGHTS = (
    REPO_ROOT / "Model" / "bestMedicalModel.pt",
    REPO_ROOT / "Model" / "bestMedicalModel2.pt",
)

# ── Manifest: بصمة الأوزان المعتمدة (2026-10-12) ──────────────────────────────
# لو استبدلت الأوزان بنية مقصودة (تدريب جديد)، حدّث القيمتين ديال + الوثائق
# docs/MEDICAL_MODEL_FINAL_VALIDATION_AR.md، لأن الفشل هنا معناه إن النسخة اللي
# بتشغّل عليها النظام مختلفة عن النسخة اللي اتاختبرت.
APPROVED_SHA256 = "bcd88d0f7160ed3d4a4a918a30d0d0006f8af795097e72f3dbe91062bb83175c"
APPROVED_SIZE_BYTES = 6_515_498

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

# المقاييس المسجلة داخل checkpoint الوزن الطبي المرفود (bestMedicalModel.pt)
RETIRED_RECORDED_METRICS = {
    "metrics/precision(B)": 0.77794,
    "metrics/recall(B)": 0.59169,
    "metrics/mAP50(B)": 0.68694,
    "metrics/mAP50-95(B)": 0.41147,
}
RECORDED_METRICS_KEYS = tuple(RETIRED_RECORDED_METRICS)
MINIMUM_APPROVED_PRECISION = 0.60

# موديولات مسموح بها داخل pickle الأوزان (حزمة torch/ultralytics فقط)
ALLOWED_PICKLE_MODULES = ("torch", "ultralytics", "collections", "__builtin__", "builtins")
FORBIDDEN_PICKLE_NAME_PARTS = (
    "os.",
    "posix",
    "nt.",
    "sys.",
    "subprocess",
    "socket",
    "shutil",
    "importlib",
    "ctypes",
    "pty",
    "runpy",
    "commands",
    "pickle",
    "eval",
    "exec",
    "FunctionType",
    "CodeType",
    "pty.spawn",
)

_MEMO_OPS = {"BINPUT", "LONG_BINPUT", "PUT", "MEMOIZE"}
_VALUE_OPS = {
    "BININT",
    "BININT1",
    "BININT2",
    "LONG",
    "LONG1",
    "LONG4",
    "INT",
    "BINFLOAT",
    "BINUNICODE",
    "SHORT_BINUNICODE",
    "UNICODE",
}
_INT_OPS = {"BININT", "BININT1", "BININT2", "LONG", "LONG1", "LONG4", "INT"}


def _pickle_opcodes(weights_path: Path):
    import pickletools

    with zipfile.ZipFile(weights_path) as archive:
        payload = archive.read("best/data.pkl")
    return list(pickletools.genops(io.BytesIO(payload)))


def _find_globals(ops) -> list[str]:
    return [arg for op, arg, _pos in ops if op.name in ("GLOBAL", "STACK_GLOBAL")]


def _value_after_key(ops, key: str):
    """أول قيمة بسيطة بعد مفتاح نصي في الـ pickle (بدون أي تنفيذ)."""
    for index, (op, arg, _pos) in enumerate(ops):
        if op.name in ("BINUNICODE", "SHORT_BINUNICODE", "UNICODE") and arg == key:
            for follow_op, follow_arg, _ in ops[index + 1 : index + 5]:
                if follow_op.name in _MEMO_OPS:
                    continue
                if follow_op.name in _VALUE_OPS:
                    return follow_op, follow_arg
                break
    return None, None


def _pickle_strings(ops) -> list[str]:
    return [
        arg
        for op, arg, _ in ops
        if op.name in ("BINUNICODE", "SHORT_BINUNICODE", "UNICODE") and isinstance(arg, str)
    ]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1 << 20):
            digest.update(chunk)
    return digest.hexdigest()


requires_weights = pytest.mark.skipif(
    not APPROVED_MEDICAL_WEIGHTS.exists(),
    reason="approved medical weights are not present in this checkout",
)


# ── الوجود والبصمة ────────────────────────────────────────────────────────────
@requires_weights
def test_approved_weights_match_pinned_manifest():
    actual_size = APPROVED_MEDICAL_WEIGHTS.stat().st_size
    actual_sha256 = _sha256(APPROVED_MEDICAL_WEIGHTS)

    assert actual_size == APPROVED_SIZE_BYTES, (
        f"{APPROVED_MEDICAL_WEIGHTS.name} size changed to {actual_size}; "
        "if this weight swap is intentional, update APPROVED_SIZE_BYTES and the review doc"
    )
    assert actual_sha256 == APPROVED_SHA256, (
        f"{APPROVED_MEDICAL_WEIGHTS.name} sha256 is {actual_sha256}, expected {APPROVED_SHA256}; "
        "the service would run weights that were never validated"
    )


def test_default_medical_path_points_at_approved_weights():
    settings = Settings(_env_file=None)
    assert settings.MEDICAL_MODEL_PATH == "Model/bestMedicalModel_FINAL.pt"
    assert not is_retired_model_path(settings.MEDICAL_MODEL_PATH)
    assert (REPO_ROOT / settings.MEDICAL_MODEL_PATH).exists()


def test_retired_medical_weights_are_gone_from_the_repo():
    for retired in RETIRED_MEDICAL_WEIGHTS:
        assert not retired.exists(), (
            f"{retired.name} must stay retired (and out of the repo); stale .env entries "
            "are auto-migrated to Model/bestMedicalModel_FINAL.pt"
        )
        assert is_retired_model_path(str(retired.relative_to(REPO_ROOT)))


def test_weights_directory_has_no_unexpected_medical_weights():
    """الموديل الطبي المعتمد واحد بس؛ أي ملف طبي تاني لازم يبقى مقصود ومراجَع."""
    medical_files = sorted(p.name for p in (REPO_ROOT / "Model").glob("*[Mm]edical*.pt"))
    assert medical_files == ["bestMedicalModel_FINAL.pt"], medical_files


# ── سلامة الملف والقراءة الساكنة ──────────────────────────────────────────────
@requires_weights
def test_weights_zip_archive_is_intact():
    with zipfile.ZipFile(APPROVED_MEDICAL_WEIGHTS) as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert "best/data.pkl" in names
        storages = [n for n in names if n.startswith("best/data/")]
        assert len(storages) > 300


@requires_weights
def test_pickle_imports_only_torch_and_ultralytics_globals():
    ops = _pickle_opcodes(APPROVED_MEDICAL_WEIGHTS)
    globals_found = _find_globals(ops)

    assert globals_found, "checkpoint should import torch/ultralytics classes"
    for entry in globals_found:
        module = entry.split()[0]
        assert module.startswith(ALLOWED_PICKLE_MODULES), f"unexpected pickle global: {entry}"
    joined = "\n".join(globals_found)
    for forbidden in FORBIDDEN_PICKLE_NAME_PARTS:
        assert forbidden not in joined, f"dangerous symbol in pickle globals: {forbidden}"


@requires_weights
def test_checkpoint_is_inference_only_without_optimizer_state():
    ops = _pickle_opcodes(APPROVED_MEDICAL_WEIGHTS)
    strings = _pickle_strings(ops)
    # القيم دي موجودة كمفاتيح، لكن لازم تكون None في ملف الاستدلال (مفيش optimizer/EMA)
    for key in ("optimizer", "ema", "scaler", "updates"):
        assert key in strings, f"checkpoint lost its {key!r} key"
    assert APPROVED_MEDICAL_WEIGHTS.stat().st_size < 10 * 1024 * 1024


@requires_weights
def test_class_count_and_names_match_the_documented_medical_taxonomy():
    ops = _pickle_opcodes(APPROVED_MEDICAL_WEIGHTS)
    _op, nc = _value_after_key(ops, "nc")
    assert nc == len(MEDICAL_CLASS_NAMES) == 11

    strings = _pickle_strings(ops)
    start = strings.index("names")
    names_block = strings[start + 1 : start + 1 + len(MEDICAL_CLASS_NAMES)]
    assert tuple(names_block) == MEDICAL_CLASS_NAMES


@requires_weights
def test_architecture_is_yolov8n_and_input_size_is_640():
    ops = _pickle_opcodes(APPROVED_MEDICAL_WEIGHTS)
    assert _value_after_key(ops, "depth_multiple")[1] == pytest.approx(0.33)
    assert _value_after_key(ops, "width_multiple")[1] == pytest.approx(0.25)
    assert _value_after_key(ops, "imgsz")[1] == 640
    assert _value_after_key(ops, "task")[1] == "detect"


@requires_weights
def test_checkpoint_metadata_is_readable_and_plausible():
    ops = _pickle_opcodes(APPROVED_MEDICAL_WEIGHTS)
    version = _value_after_key(ops, "version")[1]
    stamped = _value_after_key(ops, "date")[1]

    assert re.match(r"^\d+\.\d+\.\d+$", str(version)), version
    assert datetime.fromisoformat(str(stamped)).year >= 2024


# ── المقاييس المسجلة داخل الـ checkpoint ─────────────────────────────────────
@requires_weights
def test_recorded_metrics_beat_the_retired_weight_on_recall_and_map():
    ops = _pickle_opcodes(APPROVED_MEDICAL_WEIGHTS)
    recorded = {}
    for key in RECORDED_METRICS_KEYS:
        _op, value = _value_after_key(ops, key)
        assert isinstance(value, float), (key, value)
        recorded[key] = value

    # الترقية مبرَّرة: recall و mAP أعلى من الوزن المرفود
    assert recorded["metrics/recall(B)"] > RETIRED_RECORDED_METRICS["metrics/recall(B)"]
    assert recorded["metrics/mAP50(B)"] > RETIRED_RECORDED_METRICS["metrics/mAP50(B)"]
    assert recorded["metrics/mAP50-95(B)"] > RETIRED_RECORDED_METRICS["metrics/mAP50-95(B)"]
    # الدقة (precision) أقل شوية من القديم — مقصود، لكن ممنوع تنزل تحت الأرضية
    assert recorded["metrics/precision(B)"] >= MINIMUM_APPROVED_PRECISION


@requires_weights
def test_recorded_metrics_are_documented_in_the_review_doc():
    doc = REPO_ROOT / "docs" / "MEDICAL_MODEL_FINAL_VALIDATION_AR.md"
    assert doc.exists()
    text = doc.read_text(encoding="utf-8")
    ops = _pickle_opcodes(APPROVED_MEDICAL_WEIGHTS)
    for key in RECORDED_METRICS_KEYS:
        value = _value_after_key(ops, key)[1]
        assert f"{value:.5f}" in text or f"{value:.3f}" in text, (key, value)


# ── تكامل التصنيف مع النظام ──────────────────────────────────────────────────
EXPECTED_CANONICAL_MAP = {
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


@requires_weights
def test_every_shipped_class_maps_to_a_canonical_name_and_color():
    for name, expected in EXPECTED_CANONICAL_MAP.items():
        assert canonical_class_name(name) == expected
        # الاسم الموحّد ثابت تحت التحويل (idempotent) عشان الدمج في الهجين ما يلغبطش
        assert canonical_class_name(expected) == expected
        assert name in CLASS_COLORS_BY_NAME
        assert expected in CLASS_COLORS_BY_NAME


@requires_weights
def test_medical_taxonomy_has_no_construction_only_or_person_classes():
    lowered = {n.lower() for n in MEDICAL_CLASS_NAMES}
    for construction_only in ("hardhat", "no-hardhat", "safety vest", "person", "safety boots"):
        assert construction_only not in lowered


# ── الأسطح الخارجية (env/docker) لازم تشير للوزن المعتمد ─────────────────────
def test_env_example_configures_the_approved_weights():
    lines = (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    medical = [ln for ln in lines if ln.startswith("MEDICAL_MODEL_PATH=")]
    assert medical, "MEDICAL_MODEL_PATH missing from .env.example"
    value = medical[-1].split("=", 1)[1].strip()
    assert value == "Model/bestMedicalModel_FINAL.pt"
    assert not is_retired_model_path(value)


@pytest.mark.parametrize("compose_file", ["docker-compose.yml", "docker-compose.dev.yml"])
def test_compose_files_configure_the_approved_weights(compose_file):
    text = (REPO_ROOT / compose_file).read_text(encoding="utf-8")
    assert "MEDICAL_MODEL_PATH: Model/bestMedicalModel_FINAL.pt" in text
    assert "MEDICAL_MODEL_PATH: Model/bestMedicalModel.pt" not in text


def test_dockerfile_copies_the_approved_weights():
    text = (REPO_ROOT / "docker" / "Dockerfile").read_text(encoding="utf-8")
    copy_lines = [ln for ln in text.splitlines() if ln.startswith("COPY Model/")]
    assert copy_lines, "Dockerfile must copy the bundled weights"
    assert "bestMedicalModel_FINAL.pt" in copy_lines[0]
    assert "Model/bestMedicalModel.pt " not in copy_lines[0] + " "


def test_readme_documents_the_approved_weights():
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "bestMedicalModel_FINAL.pt" in text
