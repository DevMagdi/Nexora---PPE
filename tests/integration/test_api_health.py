from __future__ import annotations


async def test_health_is_minimal_and_public(test_client, anon_client):
    response = await anon_client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "detectors_loaded" not in response.json()
    assert "database" not in response.json()


async def test_metrics_requires_admin(test_client, anon_client):
    authorized = await test_client.get("/api/v1/metrics")
    assert authorized.status_code == 200
    assert "cameras" in authorized.json()
    unauthorized = await anon_client.get("/api/v1/metrics")
    assert unauthorized.status_code == 401


async def test_auth_login_sets_httponly_cookies_and_me(anon_client, test_user):
    response = await anon_client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "must_change_password": False}
    assert "access_token" not in response.json()
    cookies = response.headers.get_list("set-cookie")
    assert any("nexora_access=" in value and "HttpOnly" in value for value in cookies)
    assert any("nexora_media=" in value and "HttpOnly" in value for value in cookies)
    assert all("SameSite=strict" in value for value in cookies)

    me_resp = await anon_client.get("/api/v1/auth/me")
    assert me_resp.status_code == 200
    assert me_resp.json()["username"] == "admin"
    assert me_resp.json()["role"] == "admin"


async def test_meta_ppe_classes(test_client):
    result = await test_client.get("/api/v1/meta/ppe-classes")
    assert result.status_code == 200
    data = result.json()
    assert data["scope"] == "industrial"
    assert set(data["allowed"]) == {"helmet", "vest", "gloves", "boots", "goggles"}
    model = await test_client.get("/api/v1/meta/system")
    assert model.json()["model"] == "ppe.pt"
    assert model.json()["confidence"] == 0.5


async def test_frames_requires_auth_and_blocks_traversal(anon_client, test_client):
    unauth = await anon_client.get("/frames/camera_1/test.jpg")
    assert unauth.status_code == 401

    missing = await test_client.get("/frames/camera_1/nonexistent.jpg")
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Frame not found"
