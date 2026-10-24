from __future__ import annotations

import ast
import re
from pathlib import Path

from app.core.config import Settings
from app.core.model_policy import MODEL_FILENAME
from app.core.ppe import CANONICAL_CLASS_NAMES, PPE_CLASSES
from app.schemas.auth import UserCreateRequest
from app.schemas.camera import CameraCreate, CameraResponse

ROOT = Path(__file__).resolve().parents[2]


def test_one_model_constructor_and_no_bundled_alternative_checkpoints():
    constructors = []
    for path in (ROOT / "app").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "YOLO"
            ):
                constructors.append(path.relative_to(ROOT).as_posix())
    assert constructors == ["app/core/detector.py"]
    assert all(path.name == MODEL_FILENAME for path in (ROOT / "Model").glob("*.pt"))
    assert 0.45 <= Settings().DETECTION_CONFIDENCE <= 0.55
    assert Settings().PPE_MODEL_PATH == "Model/ppe_unified_best.pt"


def test_schema_and_runtime_are_one_industrial_scope():
    assert set(PPE_CLASSES) == {"helmet", "vest", "gloves", "boots", "goggles"}
    assert len(CANONICAL_CLASS_NAMES) == 11
    assert "profile" not in CameraCreate.model_fields
    assert "profile" not in CameraResponse.model_fields
    assert "sector" not in UserCreateRequest.model_fields
    assert CameraCreate.model_config["extra"] == "forbid"
    assert UserCreateRequest.model_config["extra"] == "forbid"


def test_mantik_identity_is_central_and_has_no_alternate_palette():
    css = (ROOT / "frontend/src/theme/mantik.css").read_text()
    expected = {
        "navy": "#16283F",
        "navy-deep": "#111B2B",
        "navy-panel": "#1C2B40",
        "gold": "#C9A227",
        "gold-soft": "#D4AF37",
        "text": "#F5F5F5",
        "text-soft": "#E8E8E8",
        "text-muted": "#A8B0BC",
    }
    for token, value in expected.items():
        match = re.search(rf"--{token}:\s*(#[0-9a-f]+);", css, re.I)
        assert match and match.group(1).upper() == value
    assert "rgba(201, 162, 39, 0.25)" in css
    assert "[data-theme" not in css and ".light" not in css
    assert '@import "./theme/mantik.css"' in (ROOT / "frontend/src/index.css").read_text()
    styles = (ROOT / "frontend/src/index.css").read_text()
    transition = styles.split("@keyframes pageEnter", 1)[1].split("@keyframes skeletonPulse", 1)[0]
    assert "opacity" not in transition  # text contrast must also hold during navigation


def test_browser_fixtures_are_not_imported_by_production_code():
    for path in (ROOT / "frontend/src").rglob("*"):
        if path.suffix in {".ts", ".tsx"}:
            source = path.read_text()
            assert "tests/e2e/fixtures" not in source
            assert "mockApi(" not in source
