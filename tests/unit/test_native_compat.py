"""Tests for the native-extension guard (app/native_compat.py).

The scenario these tests protect is a Windows machine whose Application Control
policy (WDAC / Smart App Control / AppLocker) refuses to load SQLAlchemy's
compiled ``_*_cy`` modules::

    ImportError: DLL load failed while importing _row_cy:
    An Application Control policy has blocked this file.

SQLAlchemy >= 2.1 imports those modules unconditionally, so without the guard the
API dies before FastAPI starts. The end-to-end tests below reproduce the failure
with a copy of the installed package whose compiled modules are unreadable, then
prove the guard falls back to SQLAlchemy's pure-Python modules.
"""

from __future__ import annotations

import importlib
import importlib.machinery
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from app import native_compat

ROOT = Path(__file__).resolve().parents[2]
EXTENSION_SUFFIX = importlib.machinery.EXTENSION_SUFFIXES[0]
PROBE_PACKAGE = "nexora_probe_pkg"

# The exact message from the field report (Windows 11 + Smart App Control/WDAC).
WINDOWS_APP_CONTROL_ERROR = (
    "DLL load failed while importing _row_cy: An Application Control policy has blocked this file."
)

GUARD_ENV_VARS = (*native_compat.FORCE_PURE_PYTHON_ENV_VARS, "DISABLE_SQLALCHEMY_CEXT_RUNTIME")


def _write(path: Path, content: str = "") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _installed_sqlalchemy_dir() -> Path | None:
    directory = native_compat.package_directory()
    return Path(directory) if directory else None


def _compiled_sqlalchemy_files(package_dir: Path) -> list[Path]:
    suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    return [
        path
        for path in sorted(package_dir.rglob("*"))
        if path.is_file() and path.name.endswith(suffixes)
    ]


def _has_compiled_sqlalchemy(package_dir: Path) -> bool:
    return bool(
        native_compat.discover_pure_python_modules(str(package_dir))
        or native_compat.discover_compiled_cyextension_modules(str(package_dir))
    )


def _run_probe(
    script: str,
    extra_pythonpath: Path | None = None,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``script`` in a fresh interpreter, the way uvicorn/alembic would."""
    parts = [str(extra_pythonpath)] if extra_pythonpath else []
    parts.append(str(ROOT))
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(parts)}
    for name in GUARD_ENV_VARS:
        env.pop(name, None)
    env.update(env_overrides or {})
    return subprocess.run(  # noqa: S603 - fixed interpreter, no shell
        [sys.executable, "-X", "utf8", "-c", script],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        cwd=str(ROOT),
        check=False,
    )


@pytest.fixture
def no_dotenv(monkeypatch):
    """Ignore any real `.env` in the working directory for the duration of a test."""
    monkeypatch.setattr(native_compat, "_dotenv_cache", {})
    return monkeypatch


@pytest.fixture
def isolated_imports(monkeypatch):
    """Restore sys.path/sys.meta_path and drop the synthetic probe package."""
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "meta_path", list(sys.meta_path))
    yield monkeypatch
    for name in [imported for imported in sys.modules if imported.startswith(PROBE_PACKAGE)]:
        del sys.modules[name]


@pytest.fixture
def guard_state(monkeypatch):
    """Reset the guard's module state and protect the real SQLAlchemy import.

    Two things need care here:

    * ``install_pure_python_fallback`` sets ``DISABLE_SQLALCHEMY_CEXT_RUNTIME``,
      and ``monkeypatch.delenv`` does not undo a key that was *absent* — so the
      original values are restored by hand, otherwise the flag leaks into later
      tests and switches the whole session to pure-Python SQLAlchemy.
    * it also refuses to run once ``sqlalchemy`` is imported, and purges the
      ``sqlalchemy*`` entries from ``sys.modules``; both are reverted here so no
      test ever mixes two copies of the library.
    """
    saved_modules = {
        name: module
        for name, module in sys.modules.items()
        if name == "sqlalchemy" or name.startswith("sqlalchemy.")
    }
    saved_env = {name: os.environ.get(name) for name in GUARD_ENV_VARS}
    monkeypatch.setattr(native_compat, "_dotenv_cache", {})
    monkeypatch.setattr(native_compat, "_installed_finder", None)
    monkeypatch.setattr(native_compat, "_redirected_count", 0)
    monkeypatch.setattr(sys, "meta_path", list(sys.meta_path))
    monkeypatch.delitem(sys.modules, "sqlalchemy", raising=False)
    yield monkeypatch
    for name, value in saved_env.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    for name in [imported for imported in sys.modules if imported.startswith("sqlalchemy")]:
        del sys.modules[name]
    sys.modules.update(saved_modules)


@pytest.fixture
def blocked_sqlalchemy(tmp_path: Path) -> Path:
    """A copy of the installed SQLAlchemy whose compiled modules cannot be loaded.

    Truncating the binaries is the portable stand-in for an OS that refuses to
    load them: CPython raises ``ImportError`` while loading the extension either
    way, and — this is the whole point — does *not* fall back to the ``.py`` twin.
    """
    package_dir = _installed_sqlalchemy_dir()
    if package_dir is None:
        pytest.skip("SQLAlchemy is not installed")
    if not native_compat.discover_pure_python_modules(str(package_dir)):
        pytest.skip("this SQLAlchemy build has no compiled *_cy twins to block")

    target = tmp_path / "sqlalchemy"
    shutil.copytree(package_dir, target, ignore=shutil.ignore_patterns("__pycache__"))
    corrupted = _compiled_sqlalchemy_files(target)
    assert corrupted, "expected compiled modules in the copied package"
    for path in corrupted:
        path.write_bytes(b"XX")
    return tmp_path


# ── error classification ──────────────────────────────────────────────────────


def test_detects_the_windows_application_control_import_error():
    exc = ImportError(WINDOWS_APP_CONTROL_ERROR, name="sqlalchemy.engine._row_cy")
    assert native_compat.is_blocked_native_extension_error(exc)


@pytest.mark.parametrize(
    ("message", "module"),
    [
        ("ImportError: DLL load failed while importing _result_cy:Access is denied.", ""),
        ("ImportError: cannot load library 'libsqlalchemy.so': image not found", ""),
        ("ImportError: /site-packages/sqlalchemy/engine/_row_cy.so: undefined symbol: x", ""),
        ("ModuleNotFoundError: blocked", "sqlalchemy.cyextension.resultproxy"),
        ("ModuleNotFoundError: blocked", "sqlalchemy.engine._row_cy"),
    ],
)
def test_detects_other_native_load_failures(message: str, module: str):
    assert native_compat.is_blocked_native_error_text(message, module)


@pytest.mark.parametrize(
    ("message", "module"),
    [
        ("ModuleNotFoundError: No module named 'sqlalchemy'", "sqlalchemy"),
        ("ModuleNotFoundError: No module named 'greenlet'", "greenlet"),
        ("ModuleNotFoundError: No module named 'aiosqlite'", "aiosqlite"),
        ("ImportError: cannot import name 'Column' from 'sqlalchemy'", ""),
    ],
)
def test_missing_dependencies_are_not_mistaken_for_policy_blocks(message: str, module: str):
    assert not native_compat.is_blocked_native_error_text(message, module)


def test_only_import_errors_are_treated_as_native_failures():
    assert not native_compat.is_blocked_native_extension_error(ValueError("DLL load failed"))


# ── environment flags ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", True), ("true", True), ("yes", True), ("0", False), ("false", False), ("", False)],
)
def test_pure_python_requested_honours_the_documented_flags(no_dotenv, value: str, expected: bool):
    for name in native_compat.FORCE_PURE_PYTHON_ENV_VARS:
        no_dotenv.delenv(name, raising=False)
    no_dotenv.setenv("DISABLE_SQLALCHEMY_CEXT", value)
    assert native_compat.pure_python_requested() is expected


def test_pure_python_requested_accepts_the_sqlalchemy_2_0_flag(no_dotenv):
    for name in native_compat.FORCE_PURE_PYTHON_ENV_VARS:
        no_dotenv.delenv(name, raising=False)
    no_dotenv.setenv("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")
    assert native_compat.pure_python_requested() is True


def test_pure_python_requested_reads_the_project_dotenv(tmp_path: Path, no_dotenv):
    """`.env` is where every other Nexora setting lives, so the flag works there too."""
    for name in native_compat.FORCE_PURE_PYTHON_ENV_VARS:
        no_dotenv.delenv(name, raising=False)
    no_dotenv.chdir(tmp_path)
    no_dotenv.setattr(native_compat, "_dotenv_cache", None)
    (tmp_path / ".env").write_text(
        "# Nexora local config\nDATABASE_URL=sqlite+aiosqlite:///./ppe_detection.db\n"
        'DISABLE_SQLALCHEMY_CEXT="1"\n',
        encoding="utf-8",
    )

    assert native_compat.dotenv_values()["DISABLE_SQLALCHEMY_CEXT"] == "1"
    assert native_compat.pure_python_requested() is True


def test_real_environment_wins_over_dotenv(tmp_path: Path, no_dotenv):
    for name in native_compat.FORCE_PURE_PYTHON_ENV_VARS:
        no_dotenv.delenv(name, raising=False)
    no_dotenv.chdir(tmp_path)
    no_dotenv.setattr(native_compat, "_dotenv_cache", None)
    (tmp_path / ".env").write_text("DISABLE_SQLALCHEMY_CEXT=1\n", encoding="utf-8")
    no_dotenv.setenv("DISABLE_SQLALCHEMY_CEXT", "0")

    assert native_compat.configured_value("DISABLE_SQLALCHEMY_CEXT") == "0"
    assert native_compat.pure_python_requested() is False


def test_dotenv_parser_ignores_comments_and_blank_lines(tmp_path: Path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n# DISABLE_SQLALCHEMY_CEXT=1\n   \nexport OTHER=2\nQUOTED='yes'\nNOEQUALS\n",
        encoding="utf-8",
    )

    values = native_compat._parse_dotenv(env_file)

    assert values == {"OTHER": "2", "QUOTED": "yes"}


# ── discovery ─────────────────────────────────────────────────────────────────


def test_discovery_only_lists_modules_with_a_compiled_twin(tmp_path: Path):
    package = tmp_path / "sqlalchemy"
    _write(package / "engine" / "_row_cy.py", "class BaseRow: ...\n")
    _write(package / "engine" / f"_row_cy{EXTENSION_SUFFIX}", "pretend this is a binary")
    _write(package / "engine" / "row.py")  # ordinary module: nothing to redirect
    _write(package / "engine" / "_row_cy.pyi")  # type stub, not an extension
    _write(package / "util" / "__pycache__" / "_collections_cy.py")
    _write(package / "util" / "__pycache__" / f"_collections_cy{EXTENSION_SUFFIX}")

    sources = native_compat.discover_pure_python_modules(str(package))

    assert sources == {"sqlalchemy.engine._row_cy": str(package / "engine" / "_row_cy.py")}


def test_discovery_finds_the_sqlalchemy_2_0_cyextension_layout(tmp_path: Path):
    package = tmp_path / "sqlalchemy"
    _write(package / "cyextension" / "__init__.py")
    _write(package / "cyextension" / "resultproxy.pyx")
    _write(package / "cyextension" / f"resultproxy{EXTENSION_SUFFIX}")
    _write(package / "cyextension" / "util.pyx")  # source only: not compiled

    assert native_compat.discover_compiled_cyextension_modules(str(package)) == [
        "sqlalchemy.cyextension.resultproxy"
    ]
    assert native_compat.discover_compiled_cyextension_modules(str(tmp_path)) == []


def test_package_directory_finds_sqlalchemy_without_importing_it():
    package_dir = _installed_sqlalchemy_dir()
    if package_dir is None:
        pytest.skip("SQLAlchemy is not installed")
    assert (package_dir / "__init__.py").is_file()
    assert native_compat.package_directory("definitely_not_installed_nexora") is None


# ── import hook ───────────────────────────────────────────────────────────────


def test_finder_serves_the_pure_python_twin(tmp_path: Path, isolated_imports):
    package = tmp_path / PROBE_PACKAGE
    _write(package / "__init__.py")
    source = _write(package / "_demo_cy.py", "VALUE = 'pure-python'\n")
    _write(package / f"_demo_cy{EXTENSION_SUFFIX}", "pretend this is a blocked binary")
    isolated_imports.setattr(sys, "path", [str(tmp_path), *sys.path])

    finder = native_compat.PurePythonExtensionFinder({f"{PROBE_PACKAGE}._demo_cy": str(source)})
    sys.meta_path.insert(0, finder)

    module = importlib.import_module(f"{PROBE_PACKAGE}._demo_cy")

    assert module.VALUE == "pure-python"
    assert Path(module.__file__) == source
    # Anything else still goes through the regular finders.
    assert finder.find_spec(f"{PROBE_PACKAGE}") is None


def test_finder_hides_modules_that_cannot_be_replaced(tmp_path: Path, isolated_imports):
    package = tmp_path / PROBE_PACKAGE
    _write(package / "__init__.py")
    isolated_imports.setattr(sys, "path", [str(tmp_path), *sys.path])

    finder = native_compat.PurePythonExtensionFinder(
        {}, blocked=[f"{PROBE_PACKAGE}._demo_cy"], reason="blocked by policy"
    )
    sys.meta_path.insert(0, finder)

    with pytest.raises(ModuleNotFoundError, match="blocked by policy"):
        importlib.import_module(f"{PROBE_PACKAGE}._demo_cy")


def test_finder_ignores_a_pure_python_twin_that_disappeared(tmp_path: Path, isolated_imports):
    finder = native_compat.PurePythonExtensionFinder(
        {f"{PROBE_PACKAGE}._demo_cy": str(tmp_path / "gone.py")}
    )
    assert finder.find_spec(f"{PROBE_PACKAGE}._demo_cy") is None


def test_install_pure_python_fallback_redirects_and_is_idempotent(tmp_path: Path, guard_state):
    package = tmp_path / "sqlalchemy"
    source = _write(package / "engine" / "_row_cy.py", "class BaseRow: ...\n")
    _write(package / "engine" / f"_row_cy{EXTENSION_SUFFIX}", "pretend this is a binary")
    guard_state.setattr(native_compat, "package_directory", lambda *args, **kwargs: str(package))

    assert native_compat.install_pure_python_fallback("unit test") == 1
    assert native_compat.install_pure_python_fallback("unit test") == 1
    assert native_compat.fallback_active() is True
    # SQLAlchemy 2.0.x reads this flag itself; the hook covers 2.1.x.
    assert os.environ["DISABLE_SQLALCHEMY_CEXT_RUNTIME"] == "1"

    finder = sys.meta_path[0]
    assert isinstance(finder, native_compat.PurePythonExtensionFinder)
    spec = finder.find_spec("sqlalchemy.engine._row_cy")
    assert spec is not None
    assert spec.origin == str(source)


def test_install_pure_python_fallback_is_a_noop_without_sqlalchemy(guard_state):
    guard_state.setattr(native_compat, "package_directory", lambda *args, **kwargs: None)
    meta_path_before = list(sys.meta_path)

    assert native_compat.install_pure_python_fallback() == 0
    assert native_compat.fallback_active() is False
    assert sys.meta_path == meta_path_before


def test_install_refuses_to_rebase_a_live_sqlalchemy_import(guard_state, caplog):
    """Switching modules under an already-imported SQLAlchemy would mix two copies."""
    guard_state.setitem(sys.modules, "sqlalchemy", object())

    with caplog.at_level("WARNING", logger="app.native_compat"):
        assert native_compat.install_pure_python_fallback("requested too late") == 0

    assert native_compat.fallback_active() is False
    assert "already imported" in caplog.text


def test_install_pure_python_fallback_clears_half_imported_modules(tmp_path: Path, guard_state):
    package = tmp_path / "sqlalchemy"
    _write(package / "engine" / "_row_cy.py", "class BaseRow: ...\n")
    _write(package / "engine" / f"_row_cy{EXTENSION_SUFFIX}", "pretend this is a binary")
    guard_state.setattr(native_compat, "package_directory", lambda *args, **kwargs: str(package))
    sys.modules["sqlalchemy.half_imported"] = object()

    native_compat.install_pure_python_fallback("unit test")

    assert "sqlalchemy.half_imported" not in sys.modules


def test_extension_status_reports_the_fallback(tmp_path: Path, guard_state):
    package = tmp_path / "sqlalchemy"
    _write(package / "engine" / "_row_cy.py", "class BaseRow: ...\n")
    _write(package / "engine" / f"_row_cy{EXTENSION_SUFFIX}", "pretend this is a binary")
    guard_state.setattr(native_compat, "package_directory", lambda *args, **kwargs: str(package))

    native_compat.install_pure_python_fallback("unit test")
    status = native_compat.extension_status()

    assert status["pure_python_fallback_installed"] is True
    assert status["redirected_modules"] == ("sqlalchemy.engine._row_cy",)


# ── end to end: the reported failure and the recovery ─────────────────────────


def test_blocked_compiled_modules_break_a_plain_sqlalchemy_import(blocked_sqlalchemy: Path):
    completed = _run_probe("import sqlalchemy\nprint(sqlalchemy.__version__)", blocked_sqlalchemy)

    assert completed.returncode != 0, completed.stdout
    assert "ImportError" in completed.stderr


def test_guard_recovers_from_blocked_compiled_modules(blocked_sqlalchemy: Path):
    script = "\n".join(
        [
            "from app.native_compat import ensure_sqlalchemy_importable",
            "assert ensure_sqlalchemy_importable() is True",
            "import sqlalchemy",
            "from sqlalchemy import create_engine, text",
            "with create_engine('sqlite://').connect() as connection:",
            "    row = connection.execute(text('select 7 as lucky')).first()",
            "assert tuple(row) == (7,), row",
            "assert row._mapping['lucky'] == 7",
            "assert row.__getitem__(0) == 7",
            "print('PURE_PYTHON_OK', sqlalchemy.__version__)",
        ]
    )

    completed = _run_probe(script, blocked_sqlalchemy)

    assert completed.returncode == 0, completed.stderr
    assert "PURE_PYTHON_OK" in completed.stdout


def test_importing_the_app_package_installs_the_guard(blocked_sqlalchemy: Path):
    """`import app.*` must protect the process before any `import sqlalchemy`."""
    script = "\n".join(
        [
            "import app.native_compat as guard",
            "assert guard.fallback_active(), 'app/__init__.py did not install the fallback'",
            "import sqlalchemy",
            "print('APP_PACKAGE_GUARD_OK', sqlalchemy.__version__)",
        ]
    )

    completed = _run_probe(script, blocked_sqlalchemy)

    assert completed.returncode == 0, completed.stderr
    assert "APP_PACKAGE_GUARD_OK" in completed.stdout


def test_force_flag_runs_sqlalchemy_on_pure_python_modules():
    package_dir = _installed_sqlalchemy_dir()
    if package_dir is None or not _has_compiled_sqlalchemy(package_dir):
        pytest.skip("this environment has no compiled SQLAlchemy modules to bypass")

    script = "\n".join(
        [
            "from app.native_compat import ensure_sqlalchemy_importable, fallback_active",
            "assert ensure_sqlalchemy_importable() is True",
            "assert fallback_active() is True",
            "import sqlalchemy",
            "from sqlalchemy import create_engine, text",
            "with create_engine('sqlite://').connect() as connection:",
            "    assert connection.execute(text('select 1')).scalar_one() == 1",
            "try:",
            "    from sqlalchemy.util._has_cython import HAS_CYEXTENSION",
            "except ImportError:",
            "    from sqlalchemy.util._has_cy import HAS_CYEXTENSION",
            "assert HAS_CYEXTENSION is False, 'compiled modules should be bypassed'",
            "print('FORCED_PURE_PYTHON_OK', sqlalchemy.__version__)",
        ]
    )

    completed = _run_probe(script, env_overrides={"DISABLE_SQLALCHEMY_CEXT": "1"})

    assert completed.returncode == 0, completed.stderr
    assert "FORCED_PURE_PYTHON_OK" in completed.stdout


def test_unrecoverable_message_points_at_the_doctor_script():
    message = native_compat.unrecoverable_native_error(ImportError("DLL load failed"))

    assert "scripts/check_native_deps.py" in message
    assert "no-binary sqlalchemy" in message
    assert "docs/LOCAL_RUN_TROUBLESHOOTING_AR.md" in message


def test_alembic_cli_wrapper_migrates_with_blocked_compiled_modules(
    blocked_sqlalchemy: Path, tmp_path: Path
):
    """`python -m alembic` imports SQLAlchemy before migrations/env.py can guard it."""
    database = tmp_path / "cli.db"
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(blocked_sqlalchemy), str(ROOT)])}
    for name in GUARD_ENV_VARS:
        env.pop(name, None)
    env.update(
        {
            "APP_ENV": "dev",
            "DATABASE_URL": f"sqlite+aiosqlite:///{database}",
            "JWT_SECRET": "unit-test-secret-long-enough-for-hs256-0123456789",
        }
    )

    completed = subprocess.run(  # noqa: S603 - fixed interpreter, no shell
        [sys.executable, str(ROOT / "scripts" / "alembic_cli.py"), "upgrade", "head"],
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        cwd=str(ROOT),
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "pure-Python modules" in completed.stderr + completed.stdout

    import sqlite3

    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute("select name from sqlite_master where type='table'")
        }
        revisions = list(connection.execute("select version_num from alembic_version"))

    assert {"alembic_version", "users", "cameras", "violations"} <= tables
    assert revisions, "no migration revision was stamped"
