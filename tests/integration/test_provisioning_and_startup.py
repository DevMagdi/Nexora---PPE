from __future__ import annotations

import argparse
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app import cli, model_check
from app.core.auth import verify_password
from app.core.config import settings
from app.db.models import AuditLog, User
from app.db.repository import ensure_bootstrap_user


@pytest.fixture
async def provisioning_db(db_session, monkeypatch):
    import app.db.session as database

    factory = async_sessionmaker(db_session.bind, expire_on_commit=False)
    monkeypatch.setattr(database, "AsyncSessionLocal", factory)
    monkeypatch.setattr(cli, "AsyncSessionLocal", factory)
    return db_session


async def test_cli_can_recover_an_installation_without_a_usable_admin(provisioning_db):
    db = provisioning_db
    viewer = User(username="old.viewer", password_hash="unusable", role="viewer", is_active=False)
    db.add(viewer)
    await db.commit()
    user_id, password = await cli._create_user("  Site.Admin  ", "admin")
    user = await db.get(User, user_id)
    assert user.username == "site.admin"
    assert user.role == "admin" and user.is_active and user.must_change_password
    assert verify_password(password, user.password_hash)
    assert user.password_hash != password
    audit = (await db.execute(select(AuditLog))).scalar_one()
    assert audit.action == "user.created_from_cli"
    assert audit.details == {"role": "admin"}
    assert password not in str(audit.details)


@pytest.mark.parametrize(
    ("name", "role"), [("ab", "viewer"), ("bad/name", "viewer"), ("valid.name", "obsolete")]
)
async def test_cli_rejects_invalid_names_or_out_of_scope_roles(provisioning_db, name, role):
    with pytest.raises(ValueError):
        await cli._create_user(name, role)
    assert (await provisioning_db.execute(select(func.count(User.id)))).scalar_one() == 0


async def test_cli_rejects_duplicate_casefolded_username(provisioning_db):
    await cli._create_user("shift.viewer", "viewer")
    with pytest.raises(ValueError, match="already exists"):
        await cli._create_user("SHIFT.VIEWER", "supervisor")


async def test_cli_reset_rotates_credentials_revokes_sessions_and_clears_lockout(provisioning_db):
    db = provisioning_db
    user_id, old = await cli._create_user("shift.viewer", "viewer")
    user = await db.get(User, user_id)
    user.failed_login_attempts = 4
    user.must_change_password = False
    await db.commit()
    new = await cli._reset_password("SHIFT.VIEWER")
    await db.refresh(user)
    assert old != new
    assert verify_password(new, user.password_hash)
    assert not verify_password(old, user.password_hash)
    assert user.token_version == 1 and user.must_change_password
    assert user.failed_login_attempts == 0 and user.locked_until is None
    assert user.last_failed_login_at is None


async def test_cli_protects_the_last_admin_then_allows_disable_with_replacement(provisioning_db):
    db = provisioning_db
    first_id, _ = await cli._create_user("first.admin", "admin")
    with pytest.raises(ValueError, match="last active administrator"):
        await cli._disable_user("first.admin")
    await cli._create_user("backup.admin", "admin")
    await cli._disable_user("FIRST.ADMIN")
    first = await db.get(User, first_id)
    await db.refresh(first)
    assert not first.is_active and first.token_version == 1


@pytest.mark.parametrize("operation", [cli._reset_password, cli._disable_user])
async def test_cli_missing_user_is_actionable(provisioning_db, operation):
    with pytest.raises(ValueError, match="User not found"):
        await operation("does.not.exist")


async def test_cli_listing_never_exposes_password_hashes(provisioning_db, capsys):
    _, password = await cli._create_user("shift.viewer", "viewer")
    await cli._list_users()
    output = capsys.readouterr().out
    assert "shift.viewer" in output and "role=viewer" in output
    assert "must_change_password=True" in output
    assert password not in output and "pbkdf2" not in output


async def test_bootstrap_only_runs_for_a_completely_empty_user_table(provisioning_db):
    db = provisioning_db
    await ensure_bootstrap_user("site.admin", "SecureBootstrap!2026")
    admin = (await db.execute(select(User))).scalar_one()
    assert admin.role == "admin" and admin.must_change_password and admin.is_active
    await ensure_bootstrap_user("renamed.admin", "SecureBootstrap!2026")
    assert (await db.execute(select(func.count(User.id)))).scalar_one() == 1
    # Never silently re-enable old credentials; recovery is an explicit local CLI operation.
    admin.is_active = False
    await db.commit()
    await ensure_bootstrap_user("renamed.admin", "SecureBootstrap!2026")
    assert (await db.execute(select(func.count(User.id)))).scalar_one() == 1
    await db.refresh(admin)
    assert not admin.is_active


async def test_real_lifespan_shares_one_detector_and_stops_manager_cleanly(
    provisioning_db, monkeypatch, tmp_path
):
    import app.main as main

    detector = MagicMock()
    detector.detect.return_value = []
    factory = MagicMock(return_value=detector)
    monkeypatch.setattr("app.core.detector.PPEDetector", factory)
    monkeypatch.setattr(main, "upgrade_database", AsyncMock())
    monkeypatch.setattr(main, "init_db", AsyncMock())
    monkeypatch.setattr(settings, "FRAMES_DIR", str(tmp_path / "frames"))
    application = main.create_app()
    async with main.lifespan(application):
        assert application.state.detector is detector
        assert application.state.camera_manager.detector is detector
        assert application.state.camera_manager._cleanup_task is not None
        assert not application.state.camera_manager._cleanup_task.done()
        factory.assert_called_once_with()
        main.upgrade_database.assert_awaited_once()
        main.init_db.assert_awaited_once()
        assert (await provisioning_db.execute(select(func.count(User.id)))).scalar_one() == 1
    assert application.state.camera_manager._cleanup_task is None
    assert application.state.camera_manager._entries == {}


async def test_missing_checkpoint_stops_real_lifespan_before_database_mutation(
    provisioning_db, monkeypatch, tmp_path
):
    import app.main as main

    monkeypatch.setattr(settings, "PPE_MODEL_PATH", str(tmp_path / "ppe_unified_best.pt"))
    upgrade = AsyncMock()
    monkeypatch.setattr(main, "upgrade_database", upgrade)
    with pytest.raises(FileNotFoundError, match="no fallback"):
        async with main.lifespan(main.create_app()):
            pytest.fail("Missing approved weights must never reach ready state")
    upgrade.assert_not_awaited()
    assert (await provisioning_db.execute(select(func.count(User.id)))).scalar_one() == 0


def test_preflight_fails_clearly_without_creating_or_downloading_weights(
    monkeypatch, tmp_path, capsys
):
    path = tmp_path / "ppe_unified_best.pt"
    monkeypatch.setattr(settings, "PPE_MODEL_PATH", str(path))
    monkeypatch.setattr("sys.argv", ["app.model_check", "--smoke"])
    assert model_check.main() == 1
    error = capsys.readouterr().err
    assert "Preflight failed" in error and "ppe_unified_best.pt" in error
    assert "no fallback" in error and not path.exists()


@pytest.mark.parametrize("command", ["create-user", "reset-password", "disable-user", "list-users"])
async def test_cli_command_dispatches_and_displays_secrets_only_when_issuing(
    monkeypatch, capsys, command
):
    prepare = AsyncMock()
    monkeypatch.setattr(cli, "_prepare_database", prepare)
    monkeypatch.setattr(cli, "_create_user", AsyncMock(return_value=(7, "OnceOnly!2026")))
    monkeypatch.setattr(cli, "_reset_password", AsyncMock(return_value="OnceOnly!2026"))
    monkeypatch.setattr(cli, "_disable_user", AsyncMock())
    monkeypatch.setattr(cli, "_list_users", AsyncMock())
    args = argparse.Namespace(command=command, username="site.viewer", role="viewer")
    assert await cli._run(args) == 0
    prepare.assert_awaited_once()
    output = capsys.readouterr().out
    assert ("OnceOnly!2026" in output) is (command in {"create-user", "reset-password"})
