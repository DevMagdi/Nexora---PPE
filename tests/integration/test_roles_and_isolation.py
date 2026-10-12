from __future__ import annotations

from app.core.auth import create_access_token, hash_password, media_cookie_name
from app.db.models import Camera, User, Violation


def _token(user: User, *, media: bool = False) -> str:
    return create_access_token(
        str(user.id),
        token_type="media" if media else "access",
        token_version=user.token_version,
    )


async def _user(db_session, username: str, role: str, sector: str) -> User:
    user = User(
        username=username,
        password_hash=hash_password("StrongPass!2026-Local"),
        sector=sector,
        role=role,
        is_active=True,
        must_change_password=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_admin_issues_one_time_users_and_audits(test_client, db_session, test_user):
    created = await test_client.post(
        "/api/v1/auth/users",
        json={"username": "paid-viewer", "sector": "construction", "role": "viewer"},
    )
    assert created.status_code == 201
    data = created.json()
    assert data["role"] == "viewer"
    assert data["must_change_password"] is True
    assert len(data["initial_password"]) >= 12

    listed = await test_client.get("/api/v1/auth/users")
    assert listed.status_code == 200
    assert any(item["username"] == "paid-viewer" for item in listed.json())
    assert all("password" not in item for item in listed.json())

    reset = await test_client.post(f"/api/v1/auth/users/{data['id']}/reset-password")
    assert reset.status_code == 200
    assert reset.json()["must_change_password"] is True
    assert reset.json()["initial_password"] != data["initial_password"]

    audit = await test_client.get("/api/v1/auth/audit-log")
    assert audit.status_code == 200
    actions = [event["action"] for event in audit.json()]
    assert "user.created" in actions
    assert "user.password_reset" in actions
    assert all("initial_password" not in str(event["details"]) for event in audit.json())


async def test_admin_update_deactivates_user_and_revokes_issued_session(test_client, db_session):
    admin = await _user(db_session, "system-admin", "admin", "both")
    target = await _user(db_session, "managed-operator", "operator", "medical")
    target_token = _token(target)
    old_token_version = target.token_version
    headers = {"Authorization": f"Bearer {_token(admin)}"}

    updated = await test_client.patch(
        f"/api/v1/auth/users/{target.id}",
        headers=headers,
        json={"is_active": False},
    )
    assert updated.status_code == 200
    assert updated.json()["is_active"] is False
    assert (await db_session.get(User, target.id)).token_version == old_token_version + 1
    rejected = await test_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {target_token}"}
    )
    assert rejected.status_code == 401


async def test_admin_audit_pagination_is_validated(test_client):
    assert (await test_client.get("/api/v1/auth/audit-log?page=0")).status_code == 422
    assert (await test_client.get("/api/v1/auth/audit-log?page_size=201")).status_code == 422


async def test_viewer_is_read_only_and_cannot_manage_users(test_client, db_session):
    viewer = await _user(db_session, "readonly", "viewer", "construction")
    camera = Camera(
        name="Fence camera",
        source_type="webcam",
        source_uri="0",
        profile="construction",
        enabled_classes=["helmet"],
    )
    db_session.add(camera)
    await db_session.commit()
    await db_session.refresh(camera)
    headers = {"Authorization": f"Bearer {_token(viewer)}"}

    assert (await test_client.get("/api/v1/cameras", headers=headers)).status_code == 200
    assert (await test_client.get("/api/v1/violations", headers=headers)).status_code == 200
    assert (await test_client.get("/api/v1/auth/users", headers=headers)).status_code == 403
    assert (
        await test_client.post(
            "/api/v1/cameras",
            headers=headers,
            json={"name": "new", "source_type": "webcam", "source_uri": "0"},
        )
    ).status_code == 403
    assert (await test_client.post(f"/api/v1/cameras/{camera.id}/start", headers=headers)).status_code == 403
    assert (await test_client.delete(f"/api/v1/cameras/{camera.id}", headers=headers)).status_code == 403
    assert (await test_client.get("/api/v1/metrics", headers=headers)).status_code == 403


async def test_operator_can_operate_but_cannot_administer_users(test_client, db_session):
    operator = await _user(db_session, "operator-user", "operator", "construction")
    headers = {"Authorization": f"Bearer {_token(operator)}"}
    created = await test_client.post(
        "/api/v1/cameras",
        headers=headers,
        json={"name": "operator camera", "source_type": "webcam", "source_uri": "0"},
    )
    assert created.status_code == 201
    camera_id = created.json()["id"]
    assert (await test_client.post(f"/api/v1/cameras/{camera_id}/start", headers=headers)).status_code == 200
    assert (await test_client.get("/api/v1/auth/users", headers=headers)).status_code == 403
    assert (await test_client.get("/api/v1/auth/audit-log", headers=headers)).status_code == 403


async def test_sector_isolation_for_cameras_violations_and_frames(test_client, db_session):
    medical_user = await _user(db_session, "medical-viewer", "viewer", "medical")
    construction = Camera(
        name="Construction camera",
        source_type="webcam",
        source_uri="0",
        profile="construction",
        enabled_classes=["helmet"],
    )
    medical = Camera(
        name="Medical camera",
        source_type="webcam",
        source_uri="0",
        profile="medical",
        enabled_classes=["mask"],
    )
    db_session.add_all([construction, medical])
    await db_session.commit()
    await db_session.refresh(construction)
    await db_session.refresh(medical)
    violation = Violation(
        camera_id=construction.id,
        violation_type="NO-Hardhat",
        confidence=0.9,
    )
    db_session.add(violation)
    await db_session.commit()
    await db_session.refresh(violation)

    headers = {"Authorization": f"Bearer {_token(medical_user)}"}
    camera_list = await test_client.get("/api/v1/cameras", headers=headers)
    assert camera_list.status_code == 200
    assert {camera["id"] for camera in camera_list.json()} == {medical.id}
    assert (await test_client.get(f"/api/v1/cameras/{construction.id}", headers=headers)).status_code == 403
    assert (await test_client.get(f"/api/v1/violations/{violation.id}", headers=headers)).status_code == 404
    test_client.cookies.set(media_cookie_name(), _token(medical_user, media=True))
    assert (
        await test_client.get("/frames/camera_1/violation.jpg", headers=headers)
    ).status_code == 403


async def test_sector_admin_cannot_expand_user_scope(test_client, db_session):
    sector_admin = await _user(db_session, "construction-admin", "admin", "construction")
    medical_user = await _user(db_session, "medical-user", "viewer", "medical")
    headers = {"Authorization": f"Bearer {_token(sector_admin)}"}

    outside = await test_client.post(
        "/api/v1/auth/users",
        headers=headers,
        json={"username": "outside-sector", "sector": "both", "role": "viewer"},
    )
    assert outside.status_code == 403
    hidden = await test_client.patch(
        f"/api/v1/auth/users/{medical_user.id}",
        headers=headers,
        json={"is_active": False},
    )
    assert hidden.status_code == 404
    assert (await test_client.get("/api/v1/auth/audit-log", headers=headers)).status_code == 403
    assert (await test_client.get("/api/v1/metrics", headers=headers)).status_code == 403


async def test_user_admin_cannot_create_another_admin_or_remove_last_admin(test_client, test_user):
    promoted = await test_client.post(
        "/api/v1/auth/users",
        json={"username": "new-admin", "sector": "both", "role": "admin"},
    )
    assert promoted.status_code == 422

    demote = await test_client.patch(
        f"/api/v1/auth/users/{test_user.id}", json={"role": "viewer"}
    )
    assert demote.status_code == 400

    disable = await test_client.patch(
        f"/api/v1/auth/users/{test_user.id}", json={"is_active": False}
    )
    assert disable.status_code == 400
