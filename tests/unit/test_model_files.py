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


def test_fingerprint_is_sha256_of_actual_file(tmp_path):
    path = tmp_path / MODEL_FILENAME
    path.write_bytes(b"approved-artifact-fixture")
    fingerprint = weight_fingerprint(path)
    assert fingerprint["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert fingerprint["size_bytes"] == path.stat().st_size


def test_pin_mismatch_never_imports_inference_runtime(tmp_path, monkeypatch):
    path = tmp_path / MODEL_FILENAME
    path.write_bytes(b"fixture")
    monkeypatch.setattr(settings, "PPE_MODEL_PATH", str(path))
    monkeypatch.setattr(settings, "PPE_MODEL_SHA256", "0" * 64)
    with pytest.raises(RuntimeError, match="SHA-256"):
        PPEDetector()


@pytest.mark.parametrize(
    "names",
    [
        list(CANONICAL_CLASS_NAMES) + ["Out of scope"],
        ["Hardhat"],
        list(CANONICAL_CLASS_NAMES) + ["worker"],
    ],
)
def test_checkpoint_class_contract_is_closed(names):
    with pytest.raises(RuntimeError):
        validate_class_names(names)


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
    with pytest.raises(RuntimeError, match="ppe_unified_best.pt"):
        PPEDetector()
