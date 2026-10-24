from __future__ import annotations

from pathlib import Path

import yaml

import scripts.setup_onprem as installer
from app.core.config import Settings
from app.core.model_policy import MODEL_FILENAME

ROOT = Path(__file__).resolve().parents[2]


def test_deployment_mounts_fail_closed_without_creating_a_fake_checkpoint_directory():
    for filename in ("docker-compose.yml", "docker-compose.dev.yml"):
        compose = yaml.safe_load((ROOT / filename).read_text())
        app = compose["services"]["app"]
        assert app["environment"]["PPE_MODEL_PATH"] == f"/app/Model/{MODEL_FILENAME}"
        assert app["environment"]["DETECTION_CONFIDENCE"] == "0.50"
        weights = [
            item
            for item in app["volumes"]
            if isinstance(item, dict) and item["target"].endswith(".pt")
        ]
        assert len(weights) == 1
        assert weights[0]["source"] == f"./Model/{MODEL_FILENAME}"
        assert weights[0]["read_only"] is True
        assert weights[0]["bind"]["create_host_path"] is False
    production = yaml.safe_load((ROOT / "docker-compose.yml").read_text())
    assert "ports" not in production["services"]["app"]
    assert "ports" not in production["services"]["db"]
    assert production["networks"]["data"]["internal"]
    assert production["networks"]["edge"]["internal"]


def test_real_environment_template_generates_a_valid_industrial_configuration(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(installer, "ROOT", tmp_path)
    monkeypatch.setattr(installer, "ENV_EXAMPLE", ROOT / ".env.example")
    monkeypatch.setattr(installer, "ENV_FILE", tmp_path / ".env")
    installer.setup("nexora.site.lan", ["rtsp://192.168.10."], "0.0.0.0")
    config = Settings(_env_file=tmp_path / ".env")
    assert config.APP_ENV == "prod"
    assert config.PPE_MODEL_PATH == f"Model/{MODEL_FILENAME}"
    assert config.DETECTION_CONFIDENCE == 0.50
    assert config.UPLOADS_DIR.startswith(config.ALLOWED_VIDEO_DIR + "/")
    assert config.RTSP_OPEN_TIMEOUT_SECONDS == 10
    assert config.RTSP_READ_TIMEOUT_SECONDS == 5
    assert config.cors_origins == ["https://nexora.site.lan"]
    assert config.allowed_hosts == ["nexora.site.lan"]


def test_ci_has_backend_and_real_browser_gates_without_deployment_weights():
    workflow = yaml.safe_load((ROOT / ".github/workflows/industrial-ci.yml").read_text())
    backend = "\n".join(step.get("run", "") for step in workflow["jobs"]["backend"]["steps"])
    browser = "\n".join(step.get("run", "") for step in workflow["jobs"]["frontend"]["steps"])
    assert "requirements/test.txt" in backend and "--cov-fail-under=75" in backend
    assert "npm run build" in browser and "npm run test:e2e" in browser
    assert "playwright install --with-deps chromium" in browser
    assert "ppe_unified_best.pt" not in backend  # no download/substitution in CI
