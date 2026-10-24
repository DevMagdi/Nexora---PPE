from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.db.models import Camera, Site, Violation


@pytest.mark.parametrize("kind", ["factory", "construction", "workshop", "warehouse", "industrial"])
async def test_industrial_site_crud(test_client, kind):
    response = await test_client.post(
        "/api/v1/sites", json={"name": f"Site {kind}", "kind": kind, "location": "Industrial zone"}
    )
    assert response.status_code == 201
    site = response.json()
    assert site["kind"] == kind
    assert (await test_client.get("/api/v1/sites")).json()[0]["id"] == site["id"]
    assert (
        await test_client.put(f"/api/v1/sites/{site['id']}", json={"name": "Updated", "kind": kind})
    ).status_code == 200
    assert (await test_client.delete(f"/api/v1/sites/{site['id']}")).status_code == 204
    assert (await test_client.delete(f"/api/v1/sites/{site['id']}")).status_code == 404


async def test_site_validation_duplicate_names_and_assigned_delete(test_client):
    assert (
        await test_client.post("/api/v1/sites", json={"name": "Wrong", "kind": "out-of-scope"})
    ).status_code == 422
    assert (
        await test_client.post("/api/v1/sites", json={"name": "   ", "kind": "factory"})
    ).status_code == 422
    first = (
        await test_client.post("/api/v1/sites", json={"name": "Factory", "kind": "factory"})
    ).json()
    assert (
        await test_client.post("/api/v1/sites", json={"name": "Factory", "kind": "factory"})
    ).status_code == 409
    second = (
        await test_client.post("/api/v1/sites", json={"name": "Dock", "kind": "warehouse"})
    ).json()
    assert (
        await test_client.put(
            f"/api/v1/sites/{second['id']}", json={"name": "Factory", "kind": "factory"}
        )
    ).status_code == 409
    response = await test_client.post(
        "/api/v1/cameras",
        json={
            "name": "Gate",
            "source_type": "rtsp",
            "source_uri": "rtsp://192.168.10.20/live",
            "site_id": first["id"],
        },
    )
    assert response.status_code == 201
    camera = response.json()
    assert (await test_client.delete(f"/api/v1/sites/{first['id']}")).status_code == 409
    assert (
        await test_client.put(f"/api/v1/cameras/{camera['id']}", json={"site_id": None})
    ).status_code == 200
    assert (await test_client.delete(f"/api/v1/sites/{first['id']}")).status_code == 204
    assert (
        await test_client.put("/api/v1/sites/99999", json={"name": "Missing", "kind": "factory"})
    ).status_code == 404


async def test_camera_rejects_extra_scope_rules_and_unknown_site(test_client):
    payload = {"name": "Gate", "source_type": "rtsp", "source_uri": "rtsp://192.168.10.20/live"}
    for extra in [
        {"profile": "obsolete"},
        {"enabled_classes": ["unsupported"]},
        {"enabled_classes": []},
        {"site_id": 99999},
        {"source_type": "unsupported"},
        {"name": "  "},
    ]:
        assert (
            await test_client.post("/api/v1/cameras", json={**payload, **extra})
        ).status_code == 422
    response = await test_client.post("/api/v1/cameras", json=payload)
    assert response.status_code == 201
    camera = response.json()
    assert "profile" not in camera
    assert camera["enabled_classes"] == ["helmet", "vest"]
    assert (
        await test_client.put(
            f"/api/v1/cameras/{camera['id']}", json={"enabled_classes": ["unsupported"]}
        )
    ).status_code == 422
    assert (
        await test_client.put(f"/api/v1/cameras/{camera['id']}", json={"site_id": 99999})
    ).status_code == 422


async def test_source_change_stops_camera_and_keeps_credentials_private(test_client):
    camera = (
        await test_client.post(
            "/api/v1/cameras",
            json={"name": "Gate", "source_type": "rtsp", "source_uri": "rtsp://192.168.10.20/live"},
        )
    ).json()
    response = await test_client.put(
        f"/api/v1/cameras/{camera['id']}",
        json={"source_uri": "rtsp://user:secret@192.168.10.21/live"},
    )
    assert response.status_code == 200
    assert response.json()["is_active"] is False
    assert "secret" not in response.text
    test_client._transport.app.state.camera_manager.stop_camera.assert_awaited_once_with(
        camera["id"]
    )


async def test_dashboard_counts_are_exact_beyond_page_limit_and_site_filtered(
    test_client, db_session, monkeypatch
):
    now = datetime(2026, 10, 24, 12, 30)
    monkeypatch.setattr("app.api.routes.dashboard.utc_now", lambda: now)
    site = Site(name="Factory", kind="factory")
    other = Site(name="Warehouse", kind="warehouse")
    db_session.add_all([site, other])
    await db_session.flush()
    first = Camera(
        name="Gate",
        source_type="rtsp",
        source_uri="rtsp://192.168.10.20/live",
        site_id=site.id,
        enabled_classes=["helmet"],
    )
    second = Camera(
        name="Dock",
        source_type="rtsp",
        source_uri="rtsp://192.168.10.21/live",
        site_id=other.id,
        enabled_classes=["vest"],
    )
    db_session.add_all([first, second])
    await db_session.flush()
    for index in range(250):
        db_session.add(
            Violation(
                camera_id=first.id,
                violation_type="NO-Hardhat",
                confidence=0.9,
                timestamp=now - timedelta(hours=index % 12),
                resolved_at=now if index < 50 else None,
            )
        )
    db_session.add(
        Violation(
            camera_id=second.id, violation_type="NO-Safety Vest", confidence=0.8, timestamp=now
        )
    )
    db_session.add(
        Violation(
            camera_id=first.id,
            violation_type="NO-Hardhat",
            confidence=0.9,
            timestamp=now - timedelta(days=2),
        )
    )
    db_session.add(
        Violation(
            camera_id=first.id,
            violation_type="NO-Hardhat",
            confidence=0.9,
            timestamp=now + timedelta(hours=2),
        )
    )
    await db_session.commit()
    manager = test_client._transport.app.state.camera_manager
    manager.is_running.side_effect = lambda cid: cid == first.id
    manager.counts_snapshot.return_value = {
        str(first.id): {"person": 3},
        str(second.id): {"person": 10},
    }
    result = (
        await test_client.get("/api/v1/dashboard", params={"range": "24h", "site_id": site.id})
    ).json()
    assert result["total_events"] == 250
    assert result["open_events"] == 200
    assert result["resolved_events"] == 50
    assert result["total_cameras"] == result["running_cameras"] == result["sites"] == 1
    assert result["live_people"] == 3
    assert len(result["series"]) == 24
    assert sum(item["count"] for item in result["series"]) == 250
    assert result["breakdown"] == [{"type": "NO-Hardhat", "count": 250}]
    week = (await test_client.get("/api/v1/dashboard", params={"range": "7d"})).json()
    assert week["total_events"] == 252
    assert len(week["series"]) == 7


async def test_event_filters_status_dates_and_export_match(test_client, db_session):
    site = Site(name="Workshop", kind="workshop")
    db_session.add(site)
    await db_session.flush()
    camera = Camera(
        name="Bay",
        source_type="rtsp",
        source_uri="rtsp://192.168.10.20/live",
        site_id=site.id,
        enabled_classes=["helmet"],
    )
    db_session.add(camera)
    await db_session.flush()
    now = datetime(2026, 10, 24, 12)
    db_session.add_all(
        [
            Violation(
                camera_id=camera.id, violation_type="NO-Hardhat", confidence=0.9, timestamp=now
            ),
            Violation(
                camera_id=camera.id,
                violation_type="NO-Gloves",
                confidence=0.9,
                timestamp=now,
                resolved_at=now,
            ),
        ]
    )
    await db_session.commit()
    params = {
        "site_id": site.id,
        "camera_id": camera.id,
        "status": "open",
        "from": "2026-10-24T00:00:00Z",
        "to": "2026-10-24T20:00:00Z",
        "violation_type": "NO-Hardhat",
    }
    result = (await test_client.get("/api/v1/violations", params=params)).json()
    assert result["total"] == 1
    exported = await test_client.get("/api/v1/violations/export", params=params)
    assert exported.status_code == 200
    assert "NO-Hardhat" in exported.text and "NO-Gloves" not in exported.text
    resolved = (await test_client.get("/api/v1/violations", params={"status": "resolved"})).json()
    assert resolved["total"] == 1
    for invalid in [
        {"status": "unsupported"},
        {"violation_type": "unsupported"},
        {"from": "2026-10-25", "to": "2026-10-20"},
        {"site_id": 0},
        {"page_size": 201},
    ]:
        assert (await test_client.get("/api/v1/violations", params=invalid)).status_code == 422
