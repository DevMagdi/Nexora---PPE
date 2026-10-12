"""
اختبارات ترحيل الأوزان الآمن (safe weight migration).

الأوزان المرفودة (``Model/bestMedicalModel2.pt``) ممنوع تحميلها تاني تحت أي
ظرف، وأي إعداد قديم في ``.env`` يشير إليها بيتحوّل تلقائيًا للبديل المعتمد،
وعتبات الثقة لكل فئة (class-conf thresholds) بتتنضّف من أي class id مش موجود
في الوزن الجديد.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

from app.core.detector import (
    MODEL_MIGRATIONS,
    RETIRED_MODEL_PATHS,
    PPEDetector,
    is_retired_model_path,
    migrate_model_path,
    resolve_model_path,
    sanitize_class_conf_thresholds,
)

RETIRED = "Model/bestMedicalModel2.pt"
REPLACEMENT = "Model/bestMedicalModel.pt"


def _make_model_dir(tmp_path, *filenames: str):
    model_dir = tmp_path / "Model"
    model_dir.mkdir(exist_ok=True)
    for name in filenames:
        (model_dir / name).write_bytes(b"weights")
    return model_dir


def test_retired_weights_are_listed_with_replacements():
    assert RETIRED in RETIRED_MODEL_PATHS
    assert MODEL_MIGRATIONS[RETIRED] == REPLACEMENT
    # البديل المعتمد نفسه لازم يكون نشط (مش مرفود)
    assert not is_retired_model_path(REPLACEMENT)
    assert not is_retired_model_path("Model/ppe.pt")


def test_is_retired_model_path_matches_normalized_variants():
    # الوزن نفسه هو المرفود — أي صيغة مسار بتوصل لنفس الملف مرفوضة
    assert is_retired_model_path("Model/bestMedicalModel2.pt")
    assert is_retired_model_path("./Model/bestMedicalModel2.pt")
    assert is_retired_model_path("Model//bestMedicalModel2.pt")
    assert is_retired_model_path("weights/bestMedicalModel2.pt")
    assert not is_retired_model_path("Model/bestMedicalModel.pt")
    assert not is_retired_model_path("")
    assert not is_retired_model_path(None)


def test_migrate_model_path_redirects_retired_and_keeps_active():
    assert migrate_model_path(RETIRED) == REPLACEMENT
    assert migrate_model_path("./Model/bestMedicalModel2.pt") == REPLACEMENT
    assert migrate_model_path(REPLACEMENT) == REPLACEMENT
    assert migrate_model_path("Model/ppe.pt") == "Model/ppe.pt"


def test_resolve_model_path_migrates_retired_configured(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _make_model_dir(tmp_path, "bestMedicalModel.pt")

    # إعداد قديم لسه ماسك الوزن المرفود => يتحول للبديل الموجود على الـ Disk
    assert resolve_model_path(RETIRED) == REPLACEMENT


def test_resolve_model_path_skips_retired_fallbacks(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # الوزن المرفود موجود على الـ Disk فعلًا — وبرضه ممنوع يرجع كـ fallback
    _make_model_dir(tmp_path, "bestMedicalModel2.pt", "ppe_medical.pt")

    resolved = resolve_model_path(
        "Model/does_not_exist.pt",
        fallbacks=(RETIRED, "Model/ppe_medical.pt"),
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
    # موك لـ ultralytics (الاختبارات كلها من غير torch/أوزان حقيقية)
    fake_ultralytics = MagicMock()
    fake_model = MagicMock()
    fake_model.names = {0: "mask", 1: "no mask"}
    fake_ultralytics.YOLO.return_value = fake_model
    monkeypatch.setitem(sys.modules, "ultralytics", fake_ultralytics)

    monkeypatch.chdir(tmp_path)
    _make_model_dir(tmp_path, "bestMedicalModel.pt")

    detector = PPEDetector(
        RETIRED,  # إعداد قديم يشير للوزن المرفود
        0.15,
        0.30,
        "0:0.55,9:0.70",  # class 9 مش موجود في الموديل الجديد
    )

    fake_ultralytics.YOLO.assert_called_once_with(REPLACEMENT)
    assert detector.class_conf == {0: 0.55}
