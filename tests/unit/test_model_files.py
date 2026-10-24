from __future__ import annotations

import hashlib
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.core.config import settings
from app.core.detector import (
    PPEDetector,
    require_model_file,
    validate_class_names,
    weight_fingerprint,
)
from app.core.model_policy import MODEL_FILENAME, REPO_ROOT, validate_model_path
from app.core.ppe import CANONICAL_CLASS_NAMES


def test_relative_model_path_is_independent_of_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert validate_model_path(f"Model/{MODEL_FILENAME}") == REPO_ROOT / "Model" / MODEL_FILENAME


def test_missing_weights_fail_before_import_or_download(tmp_path, monkeypatch):
    path = tmp_path / MODEL_FILENAME
    monkeypatch.setattr(settings, "PPE_MODEL_PATH", str(path))
    with pytest.raises(FileNotFoundError, match="no fallback"):
        PPEDetector()
    assert not path.exists()


def test_empty_weights_fail_fast(tmp_path):
    path = tmp_path / MODEL_FILENAME
    path.touch()
    with pytest.raises(RuntimeError, match="empty"):
        require_model_file(str(path))


def test_symlink_cannot_redirect_to_another_weight(tmp_path):
    target = tmp_path / "unapproved.bin"
    target.write_bytes(b"unapproved")
    path = tmp_path / MODEL_FILENAME
    path.symlink_to(target)
    with pytest.raises(ValueError, match="resolved"):
        require_model_file(str(path))


def test_symlink_to_unified_weight_is_rejected_as_unified(tmp_path):
    target = tmp_path / "ppe_unified_best.pt"
    target.write_bytes(b"unified")
    path = tmp_path / MODEL_FILENAME
    path.symlink_to(target)
    with pytest.raises(ValueError, match="unified weights are rejected"):
        require_model_file(str(path))


@pytest.mark.parametrize(
    "value",
    [
        "Model/ppe_unified_best.pt",
        "Model/unified/ppe.pt",
        "ppe_unified_best.pt",
        "/opt/weights/PPE_UNIFIED.pt",
    ],
)
def test_unified_references_are_rejected_before_any_filesystem_access(value):
    with pytest.raises(ValueError, match="unified weights are rejected") as error:
        validate_model_path(value)
    assert (
        str(error.value)
        == "Only approved weight Model/ppe.pt is allowed; unified weights are rejected."
    )


def test_approved_filename_is_exact_after_case_insensitive_names_fail(tmp_path):
    with pytest.raises(ValueError, match="must be named exactly ppe.pt"):
        validate_model_path(str(tmp_path / "PPE.PT"))


def test_fingerprint_is_sha256_of_actual_file(tmp_path):
    path = tmp_path / MODEL_FILENAME
    path.write_bytes(b"approved-artifact-fixture")
    fingerprint = weight_fingerprint(path)
    assert fingerprint["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert fingerprint["size_bytes"] == path.stat().st_size


def test_recommended_pin_constant_matches_the_approved_artifact():
    from app.core.model_policy import APPROVED_MODEL_SHA256

    assert (
        APPROVED_MODEL_SHA256 == "15c758c669eeb557d9439bd18c5a3929680238122a95286210ca69e11af8218a"
    )


def test_pin_match_accepts_the_approved_artifact(tmp_path, monkeypatch):
    payload = b"approved-ppe-artifact"
    path = tmp_path / MODEL_FILENAME
    path.write_bytes(payload)
    monkeypatch.setattr(settings, "PPE_MODEL_PATH", str(path))
    monkeypatch.setattr(settings, "PPE_MODEL_SHA256", hashlib.sha256(payload).hexdigest())
    assert require_model_file() == path.resolve()


def test_pin_mismatch_never_imports_inference_runtime(tmp_path, monkeypatch):
    path = tmp_path / MODEL_FILENAME
    path.write_bytes(b"fixture")
    monkeypatch.setattr(settings, "PPE_MODEL_PATH", str(path))
    monkeypatch.setattr(settings, "PPE_MODEL_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="SHA-256"):
        PPEDetector()


@pytest.mark.parametrize("extra", ["Out of scope", "worker"])
def test_checkpoint_class_mapping_stays_industrial_when_extra_names_are_ignored(extra):
    mapping = validate_class_names(list(CANONICAL_CLASS_NAMES) + [extra])
    assert set(mapping.values()) == set(CANONICAL_CLASS_NAMES)
    assert len(mapping) == len(CANONICAL_CLASS_NAMES)
    assert len(CANONICAL_CLASS_NAMES) not in mapping


@pytest.mark.parametrize("missing", ["Person", "Hardhat", "NO-Hardhat", "Safety Vest"])
def test_checkpoint_requires_each_class_in_the_current_main_minimum(missing):
    with pytest.raises(RuntimeError, match="missing required classes"):
        validate_class_names([name for name in CANONICAL_CLASS_NAMES if name != missing])


def test_current_checkpoint_minimum_does_not_invent_absent_violation_classes():
    mapping = validate_class_names(["person", "helmet", "no_helmet", "vest"])
    assert set(mapping.values()) == {"Person", "Hardhat", "NO-Hardhat", "Safety Vest"}
    assert "NO-Safety Vest" not in mapping.values()


def test_class_aliases_are_normalized_without_id_assumptions():
    names = {
        4: "worker",
        12: "helmet",
        2: "no_helmet",
        9: "vest",
        0: "no_vest",
        8: "Boot",
        7: "NO-Boot",
    }
    canonical = validate_class_names(names)
    assert canonical[8] == "Safety Boots"
    assert canonical[7] == "NO-Boot"
    assert canonical[4] == "Person"


@pytest.fixture
def mock_checkpoint(tmp_path, monkeypatch):
    path = tmp_path / MODEL_FILENAME
    path.write_bytes(b"mocked-loader-fixture-not-deployment-weights")
    monkeypatch.setattr(settings, "PPE_MODEL_PATH", str(path))
    monkeypatch.setattr(settings, "PPE_MODEL_SHA256", "")
    model = MagicMock()
    model.task = "detect"
    model.names = dict(enumerate(CANONICAL_CLASS_NAMES))
    model.return_value = [SimpleNamespace(boxes=[])]
    factory = MagicMock(return_value=model)
    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=factory))
    return path, model, factory


def test_one_loader_uses_only_the_approved_file_and_default_confidence(mock_checkpoint):
    path, model, factory = mock_checkpoint
    detector = PPEDetector()
    assert detector.detect(np.zeros((64, 64, 3), dtype=np.uint8)) == []
    factory.assert_called_once_with(str(path), task="detect")
    assert model.call_args.kwargs["conf"] == 0.50
    assert set(detector.class_names.values()) == set(CANONICAL_CLASS_NAMES)


def test_corrupt_checkpoint_has_actionable_error(mock_checkpoint):
    _, _, factory = mock_checkpoint
    factory.side_effect = OSError("truncated")
    with pytest.raises(RuntimeError, match="ppe.pt"):
        PPEDetector()


def test_ignored_and_duplicate_checkpoint_ids_never_escape_inference(mock_checkpoint):
    _, model, _ = mock_checkpoint
    model.names = dict(enumerate([*CANONICAL_CLASS_NAMES, "Out of scope", "worker"]))

    def box(class_id):
        return SimpleNamespace(cls=[class_id], conf=[0.99], xyxy=[[0, 0, 20, 20]])

    person_id = list(CANONICAL_CLASS_NAMES).index("Person")
    model.return_value = [
        SimpleNamespace(
            boxes=[
                box(len(CANONICAL_CLASS_NAMES)),
                box(len(CANONICAL_CLASS_NAMES) + 1),
                box(person_id),
            ]
        )
    ]
    result = PPEDetector().detect(np.zeros((64, 64, 3), dtype=np.uint8))
    assert len(result) == 1 and result[0].class_name == "Person"


def test_approved_checkpoint_vocabulary_is_the_thirteen_ppe_classes():
    from app.core.ppe import EXPECTED_MODEL_CLASSES, IGNORED_MODEL_CLASSES

    assert EXPECTED_MODEL_CLASSES == (
        "Hardhat",
        "NO-Hardhat",
        "Safety Vest",
        "NO-Safety Vest",
        "Mask",
        "NO-Mask",
        "Person",
        "Gloves",
        "NO-Gloves",
        "Safety Boots",
        "NO-Safety Boots",
        "Goggles",
        "NO-Goggles",
    )
    assert len(EXPECTED_MODEL_CLASSES) == 13
    assert set(IGNORED_MODEL_CLASSES) == {"Mask", "NO-Mask"}
    for absent in ("Ladder", "Cone", "Excavator"):
        assert absent not in EXPECTED_MODEL_CLASSES


def test_full_ppe_checkpoint_loads_and_only_mask_is_ignored():
    from app.core.ppe import EXPECTED_MODEL_CLASSES

    canonical = validate_class_names(list(EXPECTED_MODEL_CLASSES))
    loaded = set(canonical.values())
    assert "Mask" not in loaded and "NO-Mask" not in loaded
    assert loaded == {
        "Person",
        "Hardhat",
        "NO-Hardhat",
        "Safety Vest",
        "NO-Safety Vest",
        "Gloves",
        "NO-Gloves",
        "Safety Boots",
        "NO-Boot",
        "Goggles",
        "NO-Goggles",
    }
    assert canonical[EXPECTED_MODEL_CLASSES.index("NO-Safety Boots")] == "NO-Boot"


def test_checkpoint_without_mask_still_starts(mock_checkpoint):
    _, model, _ = mock_checkpoint
    from app.core.ppe import EXPECTED_MODEL_CLASSES

    model.names = dict(
        enumerate([name for name in EXPECTED_MODEL_CLASSES if name not in {"Mask", "NO-Mask"}])
    )
    detector = PPEDetector()
    assert "Mask" not in detector.class_names.values()
    assert detector.supported_negative_rules == frozenset(
        {"helmet", "vest", "gloves", "boots", "goggles"}
    )
