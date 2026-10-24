from __future__ import annotations

from app.core.auth import create_access_token, hash_password
from app.db.models import Camera, User


def _token(user):
    return {
        "Authorization": f"Bearer {create_access_token(str(user.id), token_version=user.token_version)}"
    }


async def _user(db, name, role):
    user = User(
        username=name,
        role=role,
        password_hash=hash_password("StrongPass!2026-Local"),
        is_active=True,
        must_change_password=False,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def test_admin_issues_one_time_users_and_audits(test_client):
    response = await test_client.post(
        "/api/v1/auth/users", json={"username": "site-viewer", "role": "viewer"}
    )
    assert response.status_code == 201
    issued = response.json()
    assert issued["must_change_password"] is True
    assert len(issued["initial_password"]) >= 12
    users = (await test_client.get("/api/v1/auth/users")).json()
    assert any(user["username"] == "site-viewer" for user in users)
    assert all("initial_password" not in user and "password_hash" not in user for user in users)
    reset = await test_client.post(f"/api/v1/auth/users/{issued['id']}/reset-password")
    assert reset.status_code == 200
    assert reset.json()["initial_password"] != issued["initial_password"]
    audit = (await test_client.get("/api/v1/auth/audit-log")).json()
    assert {"user.created", "user.password_reset"}.issubset({event["action"] for event in audit})
    assert all("initial_password" not in str(event["details"]) for event in audit)


async def test_disable_or_role_change_revokes_tokens(test_client, db_session):
    target = await _user(db_session, "managed-supervisor", "supervisor")
    old_headers = _token(target)
    response = await test_client.patch(f"/api/v1/auth/users/{target.id}", json={"is_active": False})
    assert response.status_code == 200
    assert not response.json()["is_active"]
    assert (await test_client.get("/api/v1/auth/me", headers=old_headers)).status_code == 401


async def test_viewer_is_read_only(test_client, db_session):
    user = await _user(db_session, "readonly", "viewer")
    headers = _token(user)
    camera = Camera(
        name="Factory gate",
        source_type="rtsp",
        source_uri="rtsp://192.168.10.20/live",
        enabled_classes=["helmet"],
    )
    db_session.add(camera)
    await db_session.commit()
    for endpoint in ["/cameras", "/violations", "/dashboard", "/sites", "/meta/system"]:
        assert (await test_client.get("/api/v1" + endpoint, headers=headers)).status_code == 200
    for endpoint in ["/auth/users", "/auth/audit-log", "/metrics"]:
        assert (await test_client.get("/api/v1" + endpoint, headers=headers)).status_code == 403
    for endpoint, payload in [
        (
            "/cameras",
            {"name": "new", "source_type": "rtsp", "source_uri": "rtsp://192.168.10.20/live"},
        ),
        ("/sites", {"name": "Factory", "kind": "factory"}),
    ]:
        assert (
            await test_client.post("/api/v1" + endpoint, headers=headers, json=payload)
        ).status_code == 403
    assert (
        await test_client.post(f"/api/v1/cameras/{camera.id}/start", headers=headers)
    ).status_code == 403
    assert (
        await test_client.delete(f"/api/v1/cameras/{camera.id}", headers=headers)
    ).status_code == 403
    assert (
        await test_client.post(
            "/api/v1/inference/image",
            headers=headers,
            files={"file": ("test.jpg", b"fixture", "image/jpeg")},
        )
    ).status_code == 403


async def test_supervisor_operates_but_cannot_administer(test_client, db_session):
    user = await _user(db_session, "safety-supervisor", "supervisor")
    headers = _token(user)
    response = await test_client.post(
        "/api/v1/cameras",
        headers=headers,
        json={
            "name": "Loading bay",
            "source_type": "rtsp",
            "source_uri": "rtsp://192.168.10.20/live",
        },
    )
    assert response.status_code == 201
    assert (
        await test_client.post(f"/api/v1/cameras/{response.json()['id']}/start", headers=headers)
    ).status_code == 200
    assert (await test_client.get("/api/v1/auth/users", headers=headers)).status_code == 403
    assert (
        await test_client.post(
            "/api/v1/sites", headers=headers, json={"name": "Warehouse", "kind": "warehouse"}
        )
    ).status_code == 403


async def test_admin_cannot_promote_through_api_or_disable_self(test_client, test_user):
    assert (
        await test_client.post(
            "/api/v1/auth/users", json={"username": "new-admin", "role": "admin"}
        )
    ).status_code == 422
    assert (
        await test_client.post(
            "/api/v1/auth/users", json={"username": "new-user", "sector": "obsolete"}
        )
    ).status_code == 422
    for body in [{"role": "viewer"}, {"is_active": False}]:
        assert (
            await test_client.patch(f"/api/v1/auth/users/{test_user.id}", json=body)
        ).status_code == 400


async def test_audit_pagination_validation(test_client):
    for params in [{"page": 0}, {"page_size": 201}]:
        assert (await test_client.get("/api/v1/auth/audit-log", params=params)).status_code == 422
