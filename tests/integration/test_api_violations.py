from __future__ import annotations

from app.db.models import Camera, Violation


async def _seed_camera(db_session):
    cam = Camera(
        name="Test Cam",
        source_type="rtsp",
        source_uri="rtsp://192.168.10.20/live",
        enabled_classes=["helmet", "vest"],
    )
    db_session.add(cam)
    await db_session.commit()
    await db_session.refresh(cam)
    return cam


async def _seed_violation(db_session, camera_id: int):
    v = Violation(
        camera_id=camera_id,
        violation_type="NO-Hardhat",
        confidence=0.9,
    )
    db_session.add(v)
    await db_session.commit()
    await db_session.refresh(v)
    return v


async def test_unauthenticated_violations_rejected(anon_client):
    r = await anon_client.get("/api/v1/violations")
    assert r.status_code == 401


async def test_list_violations_empty(test_client):
    r = await test_client.get("/api/v1/violations")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 0
    assert data["items"] == []


async def test_list_violations_with_data(test_client, db_session):
    cam = await _seed_camera(db_session)
    await _seed_violation(db_session, cam.id)

    r = await test_client.get("/api/v1/violations")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["violation_type"] == "NO-Hardhat"


async def test_get_violation_not_found(test_client):
    r = await test_client.get("/api/v1/violations/9999")
    assert r.status_code == 404


async def test_get_and_resolve_violation(test_client, db_session):
    cam = await _seed_camera(db_session)
    v = await _seed_violation(db_session, cam.id)

    r = await test_client.get(f"/api/v1/violations/{v.id}")
    assert r.status_code == 200
    assert r.json()["id"] == v.id
    assert r.json()["is_resolved"] is False

    res = await test_client.post(f"/api/v1/violations/{v.id}/resolve")
    assert res.status_code == 200
    assert res.json()["is_resolved"] is True
    assert res.json()["resolved_at"] is not None


async def test_export_csv(test_client, db_session):
    cam = await _seed_camera(db_session)
    await _seed_violation(db_session, cam.id)

    r = await test_client.get("/api/v1/violations/export")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert "NO-Hardhat" in r.text


async def test_camera_crud_lifecycle(test_client):
    create_resp = await test_client.post(
        "/api/v1/cameras",
        json={
            "name": "Gate Camera",
            "source_type": "rtsp",
            "source_uri": "rtsp://192.168.10.20/live",
            "enabled_classes": ["helmet", "vest"],
        },
    )
    assert create_resp.status_code == 201
    cam_id = create_resp.json()["id"]

    list_resp = await test_client.get("/api/v1/cameras")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    update_resp = await test_client.put(
        f"/api/v1/cameras/{cam_id}",
        json={"name": "Updated Gate Camera", "enabled_classes": ["helmet"]},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "Updated Gate Camera"
    assert update_resp.json()["enabled_classes"] == ["helmet"]

    start_resp = await test_client.post(f"/api/v1/cameras/{cam_id}/start")
    assert start_resp.status_code == 200

    stop_resp = await test_client.post(f"/api/v1/cameras/{cam_id}/stop")
    assert stop_resp.status_code == 200

    del_resp = await test_client.delete(f"/api/v1/cameras/{cam_id}")
    assert del_resp.status_code == 204
