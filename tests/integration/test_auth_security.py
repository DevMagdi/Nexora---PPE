from __future__ import annotations

from sqlalchemy import select

from app.core.auth import access_cookie_name, create_access_token, hash_password, media_cookie_name
from app.db.models import AuditLog, User, utc_now


async def test_login_rate_limit_and_audits_failures(anon_client, test_user, db_session, caplog):
    for _ in range(5):
        response = await anon_client.post(
            "/api/v1/auth/login",
            data={"username": "admin", "password": "wrong-password"},
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"

    await db_session.refresh(test_user)
    assert test_user.locked_until is not None
    assert test_user.locked_until > utc_now()

    response = await anon_client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    assert response.status_code == 429
    assert int(response.headers["retry-after"]) > 0

    events = (await db_session.execute(select(AuditLog))).scalars().all()
    assert sum(event.action == "auth.login_failed" for event in events) == 5
    assert all("wrong-password" not in str(event.details) for event in events)
    assert "wrong-password" not in caplog.text


async def test_login_rate_limit_applies_to_unknown_user(anon_client):
    for index in range(6):
        response = await anon_client.post(
            "/api/v1/auth/login",
            data={"username": f"ghost-{index}", "password": "WrongPass!2026"},
        )
        assert response.status_code == (401 if index < 5 else 429)


async def test_initial_password_change_revokes_old_session(anon_client, db_session):
    user = User(
        username="temporary-user",
        password_hash=hash_password("TempPass!2026-First"),
        role="viewer",
        must_change_password=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    login = await anon_client.post(
        "/api/v1/auth/login",
        data={"username": user.username, "password": "TempPass!2026-First"},
    )
    assert login.status_code == 200
    assert login.json()["must_change_password"] is True
    old_cookie_token = anon_client.cookies.get(access_cookie_name())
    assert old_cookie_token

    blocked = await anon_client.get("/api/v1/cameras")
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "password_change_required"
    assert (await anon_client.post("/api/v1/auth/media-token")).status_code == 403

    me_before = await anon_client.get("/api/v1/auth/me")
    assert me_before.status_code == 200
    assert me_before.json()["must_change_password"] is True

    changed = await anon_client.post(
        "/api/v1/auth/change-password",
        json={
            "current_password": "TempPass!2026-First",
            "new_password": "NewSecurePass#2026-Work",
        },
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
    assert "HttpOnly" in changed.headers.get("set-cookie", "")

    await db_session.refresh(user)
    assert user.must_change_password is False
    assert user.token_version == 1
    allowed = await anon_client.get("/api/v1/violations")
    assert allowed.status_code == 200

    old_session = await anon_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {old_cookie_token}"},
    )
    assert old_session.status_code == 401


async def test_password_change_enforces_policy(anon_client, test_user):
    login = await anon_client.post(
        "/api/v1/auth/login",
        data={"username": test_user.username, "password": "admin123"},
    )
    assert login.status_code == 200

    too_short = await anon_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "admin123", "new_password": "short"},
    )
    assert too_short.status_code == 422

    same_password = await anon_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "admin123", "new_password": "admin123"},
    )
    assert same_password.status_code == 422

    wrong_current = await anon_client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "incorrect", "new_password": "NewSecurePass#2026"},
    )
    assert wrong_current.status_code == 400


async def test_logout_revokes_access_and_media_tokens(anon_client, test_user, db_session):
    access = create_access_token(str(test_user.id), token_version=test_user.token_version)
    media = create_access_token(
        str(test_user.id), token_type="media", token_version=test_user.token_version
    )
    anon_client.cookies.set(access_cookie_name(), access)
    anon_client.cookies.set(media_cookie_name(), media)

    logged_out = await anon_client.post(
        "/api/v1/auth/logout", headers={"Authorization": f"Bearer {access}"}
    )
    assert logged_out.status_code == 204
    assert any("Max-Age=0" in cookie for cookie in logged_out.headers.get_list("set-cookie"))

    await db_session.refresh(test_user)
    assert test_user.token_version == 1
    assert (
        await anon_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"})
    ).status_code == 401


async def test_query_string_does_not_authenticate_media(anon_client, test_user):
    media_token = create_access_token(
        str(test_user.id), token_type="media", token_version=test_user.token_version
    )
    response = await anon_client.get(f"/frames/camera_1/test.jpg?token={media_token}")
    assert response.status_code == 401


async def test_inactive_and_revoked_sessions_are_rejected(anon_client, db_session, test_user):
    token = create_access_token(str(test_user.id), token_version=test_user.token_version)
    test_user.token_version += 1
    await db_session.commit()
    response = await anon_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401

    test_user.is_active = False
    test_user.token_version += 1
    await db_session.commit()
    inactive_token = create_access_token(str(test_user.id), token_version=test_user.token_version)
    response = await anon_client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {inactive_token}"}
    )
    assert response.status_code == 401
