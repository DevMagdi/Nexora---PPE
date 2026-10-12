from __future__ import annotations

import base64
import io
import stat

import pytest
from dotenv import dotenv_values

import scripts.setup_onprem as setup_onprem


def test_setup_writes_literal_secrets_to_a_private_environment_file(tmp_path, monkeypatch):
    root = tmp_path / "install"
    root.mkdir()
    env_file = root / ".env"
    env_example = root / ".env.example"
    env_example.write_text(
        "APP_ENV=dev\nCORS_ORIGINS=http://localhost:5173\nALLOWED_HOSTS=*\n"
        "TRUSTED_PROXIES=\nJWT_SECRET=\nBOOTSTRAP_PASSWORD=\n"
        "ALLOWED_RTSP_PREFIXES=\nALLOWED_VIDEO_DIR=\nBACKUP_ENCRYPTION_KEY=\nBACKUP_DIR=backups\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(setup_onprem, "ROOT", root)
    monkeypatch.setattr(setup_onprem, "ENV_FILE", env_file)
    monkeypatch.setattr(setup_onprem, "ENV_EXAMPLE", env_example)
    monkeypatch.setattr(setup_onprem, "_password", lambda: "T3st$#'PassExample")

    password = setup_onprem.setup("Nexora.Customer.LAN.", ["rtsp://192.168.10."], "127.0.0.1")

    values = dotenv_values(env_file)
    assert stat.S_IMODE(env_file.stat().st_mode) == 0o600
    assert values["APP_ENV"] == "prod"
    assert values["CORS_ORIGINS"] == "https://nexora.customer.lan"
    assert values["ALLOWED_HOSTS"] == "nexora.customer.lan"
    assert values["TRUSTED_PROXIES"] == "172.30.100.2/32"
    assert values["EDGE_DOCKER_SUBNET"] == "172.30.100.0/24"
    assert values["DATA_DOCKER_SUBNET"] == "172.30.101.0/24"
    assert values["CADDY_CONTAINER_IP"] == "172.30.100.2"
    assert values["APP_EDGE_CONTAINER_IP"] == "172.30.100.3"
    assert values["DB_CONTAINER_IP"] == "172.30.101.2"
    assert values["BOOTSTRAP_PASSWORD"] == password
    assert len(base64.urlsafe_b64decode(values["BACKUP_ENCRYPTION_KEY"] + "==")) == 32
    assert values["ALLOWED_RTSP_PREFIXES"] == "rtsp://192.168.10."
    assert values["ALLOWED_VIDEO_DIR"] == "/var/nexora/videos"
    assert values["BACKUP_DIR"] == "/var/nexora/backups"
    assert (root / "videos").is_dir()
    assert stat.S_IMODE((root / "backups").stat().st_mode) == 0o700


def test_setup_will_not_overwrite_existing_environment_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("KEEP=me\n", encoding="utf-8")
    example = tmp_path / ".env.example"
    example.write_text("APP_ENV=dev\n", encoding="utf-8")
    monkeypatch.setattr(setup_onprem, "ROOT", tmp_path)
    monkeypatch.setattr(setup_onprem, "ENV_FILE", env_file)
    monkeypatch.setattr(setup_onprem, "ENV_EXAMPLE", example)

    with pytest.raises(FileExistsError):
        setup_onprem.setup("nexora.example", ["rtsp://192.168.10."], "0.0.0.0")

    assert env_file.read_text(encoding="utf-8") == "KEEP=me\n"


@pytest.mark.parametrize(
    ("host", "prefixes", "bind"),
    [
        ("https://nexora.example", ["rtsp://192.168.10."], "0.0.0.0"),
        ("nexora..example", ["rtsp://192.168.10."], "0.0.0.0"),
        ("nexora.example", ["rtsp://192.168.*"], "0.0.0.0"),
        ("nexora.example", ["http://user@192.168.10.5"], "0.0.0.0"),
        ("nexora.example", ["rtsp://192.168.10."], "localhost"),
    ],
)
def test_setup_rejects_unsafe_host_prefix_or_bind_address(host, prefixes, bind):
    with pytest.raises(ValueError):
        setup_onprem.setup(host, prefixes, bind)


@pytest.mark.parametrize(
    ("edge", "data"),
    [
        ("172.30.100.0/24", "172.30.100.0/25"),
        ("8.8.8.0/24", "172.30.101.0/24"),
        ("172.30.100.0/30", "172.30.101.0/24"),
        ("2001:db8::/64", "172.30.101.0/24"),
    ],
)
def test_setup_rejects_overlapping_public_small_or_non_ipv4_docker_subnets(edge, data):
    with pytest.raises(ValueError):
        setup_onprem._valid_docker_subnets(edge, data)


def test_dotenv_literal_preserves_dollar_hash_and_quote_characters():
    secret = "cash$after#payment'quoted\\path"
    parsed = dotenv_values(stream=io.StringIO(f"TEST={setup_onprem._dotenv_literal(secret)}\n"))
    assert parsed["TEST"] == secret
