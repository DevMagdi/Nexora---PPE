"""
اختبارات ترحيل الأوزان الآمن (safe weight migration).

الأوزان المرفودة ممنوع تحميلها تاني تحت أي ظرف، وأي إعداد قديم في ``.env``
يشير إليها بيتحوّل تلقائيًا للبديل المعتمد:

* ``Model/bestMedicalModel2.pt`` (ترتيب فئات مختلف) -> ``bestMedicalModel_FINAL.pt``
  وخريطة عتبات الثقة القديمة بتتشال بالكامل.
* ``Model/bestMedicalModel.pt`` (نفس ترتيب الفئات) -> ``bestMedicalModel_FINAL.pt``
  وعتبات الثقة اللي المستخدم ضبطها تفضل سارية.
"""

from __future__ import annotations

import hashlib
import sys
from unittest.mock import MagicMock

import pytest

from app.core.detector import (
    CLASS_ID_COMPATIBLE_RETIRED_PATHS,
    MODEL_MIGRATIONS,
    RETIRED_MODEL_PATHS,
    PPEDetector,
    is_retired_model_path,
    migrate_model_path,
    migration_preserves_class_ids,
    resolve_model_path,
    sanitize_class_conf_thresholds,
    weight_fingerprint,
)

RETIRED_INCOMPATIBLE = "Model/bestMedicalModel2.pt"
RETIRED_COMPATIBLE = "Model/bestMedicalModel.pt"
REPLACEMENT = "Model/bestMedicalModel_FINAL.pt"

MEDICAL_CLASSES = {
    0: "full cover",
    1: "goggle",
    2: "hand gloves",
    3: "head cap",
    4: "lab coat",
    5: "mask",
    6: "no goggle",
    7: "no hand gloves",
    8: "no head cap",
    9: "no mask",
    10: "shoe cover",
}


def _make_model_dir(tmp_path, *filenames: str):
    model_dir = tmp_path / "Model"
    model_dir.mkdir(exist_ok=True)
    for name in filenames:
        (model_dir / name).write_bytes(b"weights")
    return model_dir


def _fake_ultralytics(monkeypatch):
    fake_ultralytics = MagicMock()
    fake_model = MagicMock()
    fake_model.names = dict(MEDICAL_CLASSES)
    fake_ultralytics.YOLO.return_value = fake_model
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)
    return fake_ultralytics


def test_retired_weights_are_listed_with_replacements():
    assert RETIRED_INCOMPATIBLE in RETIRED_MODEL_PATHS
    assert RETIRED_COMPATIBLE in RETIRED_MODEL_PATHS
    assert MODEL_MIGRATIONS[RETIRED_INCOMPATIBLE] == REPLACEMENT
    assert MODEL_MIGRATIONS[RETIRED_COMPATIBLE] == REPLACEMENT
    # البديل المعتمد نفسه لازم يكون نشط (مش مرفود)
    assert not is_retired_model_path(REPLACEMENT)
    assert not is_retired_model_path("Model/ppe.pt")


def test_migration_never_points_back_to_a_retired_weight():
    """كل بدائل الترحيل لازم تكون أوزان نشطة (مش سلسلة مرفودة)."""
    for retired, replacement in MODEL_MIGRATIONS.items():
        assert not is_retired_model_path(replacement), (retired, replacement)
        assert replacement in MODEL_MIGRATIONS.values()


def test_is_retired_model_path_matches_normalized_variants():
    # الوزن نفسه هو المرفود — أي صيغة مسار بتوصل لنفس الملف مرفوضة
    for retired in (RETIRED_INCOMPATIBLE, RETIRED_COMPATIBLE):
        assert is_retired_model_path(retired)
        assert is_retired_model_path(f"./{retired}")
        assert is_retired_model_path(retired.replace("Model/", "Model//"))
        assert is_retired_model_path(f"weights/{retired.split('/')[-1]}")
        assert is_retired_model_path(retired.replace("/", "\\"))
    # البديل المعتمد مايتلغبطش مع القديم (اسم مختلف بالكامل)
    assert not is_retired_model_path("Model/bestMedicalModel_FINAL.pt")
    assert not is_retired_model_path("Model/bestMedicalModel2_FINAL.pt")
    assert not is_retired_model_path("")
    assert not is_retired_model_path(None)


def test_migrate_model_path_redirects_retired_and_keeps_active():
    assert migrate_model_path(RETIRED_INCOMPATIBLE) == REPLACEMENT
    assert migrate_model_path(RETIRED_COMPATIBLE) == REPLACEMENT
    assert migrate_model_path("./Model/bestMedicalModel.pt") == REPLACEMENT
    assert migrate_model_path(REPLACEMENT) == REPLACEMENT
    assert migrate_model_path("Model/ppe.pt") == "Model/ppe.pt"


def test_migration_preserves_class_ids_only_for_known_compatible_weights():
    assert migration_preserves_class_ids(RETIRED_COMPATIBLE)
    assert migration_preserves_class_ids("./Model/bestMedicalModel.pt")
    assert migration_preserves_class_ids("weights/bestMedicalModel.pt")
    # ترتيب فئات bestMedicalModel2.pt كان مختلف — العتبات القديمة تشوّه النتيجة
    assert not migration_preserves_class_ids(RETIRED_INCOMPATIBLE)
    assert not migration_preserves_class_ids(REPLACEMENT)
    assert not migration_preserves_class_ids("")
    assert not migration_preserves_class_ids(None)
    assert CLASS_ID_COMPATIBLE_RETIRED_PATHS <= set(RETIRED_MODEL_PATHS)


def test_resolve_model_path_migrates_retired_configured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_model_dir(tmp_path, "bestMedicalModel_FINAL.pt")

    # إعداد قديم لسه ماسك وزن مرفود => يتحول للبديل الموجود على الـ Disk
    assert resolve_model_path(RETIRED_COMPATIBLE) == REPLACEMENT
    assert resolve_model_path(RETIRED_INCOMPATIBLE) == REPLACEMENT


def test_resolve_model_path_skips_retired_fallbacks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # الأوزان المرفودة موجودة على الـ Disk فعلًا — وبرضه ممنوعة كـ fallback
    _make_model_dir(tmp_path, "bestMedicalModel2.pt", "bestMedicalModel.pt", "ppe_medical.pt")

    resolved = resolve_model_path(
        "Model/does_not_exist.pt",
        fallbacks=(RETIRED_INCOMPATIBLE, RETIRED_COMPATIBLE, "Model/ppe_medical.pt"),
    )
    assert resolved == "Model/ppe_medical.pt"


def test_resolve_model_path_prefers_existing_configured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_model_dir(tmp_path, "custom.pt", "ppe.pt")

    assert resolve_model_path("Model/custom.pt", fallbacks=("Model/ppe.pt",)) == "Model/custom.pt"


def test_sanitize_class_conf_thresholds_drops_unknown_class_ids():
    names = {0: "mask", 1: "no mask"}
    # بعد ترحيل الأوزان class ids القديمة (9 و -1) مش موجودة في الموديل الجديد
    assert sanitize_class_conf_thresholds(names, {0: 0.55, 1: 0.40, 9: 0.70, -1: 0.90}) == {
        0: 0.55,
        1: 0.40,
    }
    assert sanitize_class_conf_thresholds(names, {}) == {}


def test_ppedetector_drops_stale_thresholds_after_migration(tmp_path, monkeypatch):
    fake_ultralytics = _fake_ultralytics(monkeypatch)

    monkeypatch.chdir(tmp_path)
    _make_model_dir(tmp_path, "bestMedicalModel_FINAL.pt")

    detector = PPEDetector(
        RETIRED_INCOMPATIBLE,  # إعداد قديم يشير للوزن المرفود bestMedicalModel2.pt
        0.05,
        0.35,
        "2:0.7,5:0.7,7:0.15,8:0.15,9:0.3",  # خريطة الموديل القديم التي كانت تشوّه hand gloves و mask
    )

    fake_ultralytics.YOLO.assert_called_once_with(REPLACEMENT)
    # لأن الموديل ترحّل من وزن مرفود بترتيب فئات مختلف، تُسقط الخريطة القديمة بالكامل
    assert detector.class_conf == {}


def test_ppedetector_keeps_thresholds_when_migration_preserves_class_ids(tmp_path, monkeypatch):
    """
    ``bestMedicalModel.pt`` -> ``bestMedicalModel_FINAL.pt`` بنفس أرقام الفئات،
    فالعتبات اللي المستخدم ضبطها تفضل شغالة بدل ما تتشال.
    """
    fake_ultralytics = _fake_ultralytics(monkeypatch)

    monkeypatch.chdir(tmp_path)
    _make_model_dir(tmp_path, "bestMedicalModel_FINAL.pt")

    detector = PPEDetector(
        RETIRED_COMPATIBLE,
        0.25,
        0.35,
        "3:0.30,9:0.40",
    )

    fake_ultralytics.YOLO.assert_called_once_with(REPLACEMENT)
    assert detector.class_conf == {3: 0.30, 9: 0.40}


def test_ppedetector_clamps_inverted_positive_thresholds_on_active_model(tmp_path, monkeypatch):
    """حتى لو عدّل المستخدم المسار إلى bestMedicalModel_FINAL.pt ونسي مسح العتبات القديمة المنعكسة."""
    _fake_ultralytics(monkeypatch)

    monkeypatch.chdir(tmp_path)
    _make_model_dir(tmp_path, "bestMedicalModel_FINAL.pt")

    detector = PPEDetector(
        REPLACEMENT,
        0.25,
        0.35,
        "2:0.7,5:0.7,7:0.25,8:0.25,9:0.3",
    )

    # الفئات الموجبة (2=hand gloves, 5=mask) ممنوع تبقى أعلى من السالبة المقابلة (7=0.25, 9=0.30)
    assert detector.class_conf[2] <= detector.class_conf[7]
    assert detector.class_conf[5] <= detector.class_conf[9]


def test_ppedetector_records_weights_fingerprint(tmp_path, monkeypatch):
    _fake_ultralytics(monkeypatch)

    monkeypatch.chdir(tmp_path)
    model_dir = _make_model_dir(tmp_path, "bestMedicalModel_FINAL.pt")
    payload = b"weights"
    (model_dir / "bestMedicalModel_FINAL.pt").write_bytes(payload)

    detector = PPEDetector(REPLACEMENT, 0.25, 0.35, "")

    fingerprint = detector.weights_fingerprint
    assert fingerprint["path"] == REPLACEMENT
    assert fingerprint["size_bytes"] == len(payload)
    assert fingerprint["sha256"] == hashlib.sha256(payload).hexdigest()


def test_weight_fingerprint_reads_chunked_and_is_stable(tmp_path):
    weights = tmp_path / "big.pt"
    blob = bytes(range(256)) * 8192  # 2 MiB > chunk size
    weights.write_bytes(blob)

    first = weight_fingerprint(str(weights))
    second = weight_fingerprint(str(weights))

    assert first == second
    assert first["size_bytes"] == len(blob)
    assert first["sha256"] == hashlib.sha256(blob).hexdigest()
    import os

    assert first["real_path"] == os.path.realpath(str(weights))


def test_weight_fingerprint_missing_file_is_oserror(tmp_path):
    with pytest.raises(OSError):
        weight_fingerprint(str(tmp_path / "missing.pt"))
