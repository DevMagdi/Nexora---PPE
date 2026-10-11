from __future__ import annotations


async def test_health_ok(test_client):
    r = await test_client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert "detectors_loaded" in data
    assert "model_loaded" in data
    assert "cameras_active" in data


async def test_metrics_ok(test_client):
    r = await test_client.get("/api/v1/metrics")
    assert r.status_code == 200
    assert "cameras" in r.json()


async def test_auth_login_and_me(anon_client, test_user):
    r = await anon_client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]

    me_resp = await anon_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "admin"


async def test_meta_ppe_classes(test_client):
    r_c = await test_client.get("/api/v1/meta/ppe-classes", params={"profile": "construction"})
    assert r_c.status_code == 200
    assert r_c.json()["profile"] == "construction"

    r_m = await test_client.get("/api/v1/meta/ppe-classes", params={"profile": "medical"})
    assert r_m.status_code == 200
    assert r_m.json()["profile"] == "medical"
