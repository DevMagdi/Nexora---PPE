"""Compatibility guard for compiled (native) Python extensions.

Why this module exists
----------------------
Managed Windows machines usually enforce an Application Control policy (WDAC,
Smart App Control or AppLocker) that refuses to load native modules it does not
trust. SQLAlchemy >= 2.1 ships its optional Cython accelerators as ``_*_cy``
modules where a compiled ``.pyd`` shadows the pure-Python ``.py`` file of the
same name, and the import is unconditional — so a single blocked ``.pyd`` kills
the whole import chain before FastAPI or Alembic ever start::

    File "...\\app\\main.py", line 10, in <module>
        from alembic import command
    ...
    File "...\\sqlalchemy\\engine\\row.py", line 27, in <module>
        from ._row_cy import BaseRow as BaseRow
    ImportError: DLL load failed while importing _row_cy:
    An Application Control policy has blocked this file.

SQLAlchemy works fine without those accelerators (that is exactly what a source
install without Cython produces), so when they cannot be loaded Nexora installs
an import hook that serves the pure-Python twin of every blocked module instead.
Nothing else changes: the ORM, Alembic migrations and the async engine all keep
working, only row processing gets slightly slower.

SQLAlchemy 2.0.x does not need the hook — it catches ``ImportError`` around
``sqlalchemy.cyextension`` and honours ``DISABLE_SQLALCHEMY_CEXT_RUNTIME`` — but
this module handles that layout too, so the behaviour is the same on both.

Usage
-----
The guard only uses the standard library and must run *before* the first
``import sqlalchemy``. It is therefore called from ``app/__init__.py`` (which
covers ``app.main``, ``app.cli``, ``app.backup`` and the test suite),
``migrations/env.py``, ``scripts/alembic_cli.py`` (Alembic's own entry point
imports SQLAlchemy before ``env.py`` runs, so ``python -m alembic`` cannot be
guarded from inside the project) and ``tests/conftest.py``.

Set ``DISABLE_SQLALCHEMY_CEXT=1`` in the environment (or in ``.env`` before
starting the process) to force the pure-Python path without waiting for a
failure. Run ``python scripts/check_native_deps.py`` to list every native module
this machine blocks.
"""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.machinery
import importlib.metadata
import importlib.util
import logging
import os
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

logger = logging.getLogger(__name__)

PACKAGE_NAME = "sqlalchemy"

# ``DISABLE_SQLALCHEMY_CEXT`` is the flag SQLAlchemy's own setup.py uses at build
# time; ``DISABLE_SQLALCHEMY_CEXT_RUNTIME`` is the one SQLAlchemy 2.0.x reads at
# runtime. Nexora accepts both so the documented names keep working.
FORCE_PURE_PYTHON_ENV_VARS = ("DISABLE_SQLALCHEMY_CEXT", "DISABLE_SQLALCHEMY_CEXT_RUNTIME")

# Error text that specifically identifies an Application Control policy
# (WDAC / Smart App Control / AppLocker) refusing to load an unsigned module.
POLICY_NATIVE_MARKERS = (
    "dll load failed",
    "application control policy",
    "smart app control",
    "applocker",
    "code integrity",
    "not a valid win32 application",
    "operation not permitted",
)

# Error text produced when a compiled module exists but cannot be loaded: either
# the OS refuses it (Application Control policy) or the binary itself is damaged
# (half-copied venv, wheel built for another ABI). Both mean the same thing for
# this guard: use the pure-Python module instead.
BLOCKED_NATIVE_MARKERS = (
    # ── the OS refuses to load the file ────────────────────────────────────
    *POLICY_NATIVE_MARKERS,
    # ── the binary cannot be mapped at all ─────────────────────────────────
    "cannot load library",
    "can't load library",
    "image not found",
    "undefined symbol",
    "cannot open shared object file",
    "file too short",
    "invalid elf header",
    "wrong elf class",
    "failed to map segment",
)

_CY_SOURCE_SUFFIX = "_cy.py"
_CYEXTENSION_PACKAGE = "cyextension"
_FALSEY_VALUES = {"", "0", "false", "no", "off"}

_installed_finder: PurePythonExtensionFinder | None = None
_redirected_count = 0

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_dotenv_cache: dict[str, str] | None = None


def _is_falsey(value: str | None) -> bool:
    return (value or "").strip().lower() in _FALSEY_VALUES


def _parse_dotenv(path: Path) -> dict[str, str]:
    """Minimal ``.env`` reader (``KEY=value``, ``#`` comments, optional quotes)."""
    values: dict[str, str] = {}
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return values
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        key = key.strip().removeprefix("export").strip()
        if not key:
            continue
        values[key] = value.strip().strip("\"'")
    return values


def dotenv_values() -> dict[str, str]:
    """Values from the project's ``.env`` — the guard runs before settings load.

    ``pydantic-settings`` reads ``.env`` itself, but it does that long after
    SQLAlchemy has been imported, so the override would arrive too late. Reading
    the two keys here keeps ``DISABLE_SQLALCHEMY_CEXT=1`` working from ``.env``
    exactly like every other Nexora setting. Real environment variables win.
    """
    global _dotenv_cache
    if _dotenv_cache is None:
        for candidate in (Path.cwd() / ".env", _PROJECT_ROOT / ".env"):
            if candidate.is_file():
                _dotenv_cache = _parse_dotenv(candidate)
                break
        else:
            _dotenv_cache = {}
    return _dotenv_cache


def configured_value(name: str) -> str | None:
    """Value of ``name`` from the environment, falling back to ``.env``."""
    value = os.environ.get(name)
    if value is not None:
        return value
    return dotenv_values().get(name)


def pure_python_requested() -> bool:
    """True when an env var (or ``.env``) asks to skip SQLAlchemy's compiled modules."""
    return any(not _is_falsey(configured_value(name)) for name in FORCE_PURE_PYTHON_ENV_VARS)


def is_policy_blocked_error_text(text: str) -> bool:
    """True when the OS (not a damaged file) refused to load a native module."""
    lowered = (text or "").lower()
    return any(marker in lowered for marker in POLICY_NATIVE_MARKERS)


def is_blocked_native_error_text(text: str, module: str = "") -> bool:
    """True when an error string looks like the OS refusing to load a native module.

    Shared by :func:`is_blocked_native_extension_error` and
    ``scripts/check_native_deps.py`` (which classifies errors raised in a probe
    subprocess and therefore only has the message text).
    """
    lowered = (text or "").lower()
    if any(marker in lowered for marker in BLOCKED_NATIVE_MARKERS):
        return True
    if "no module named" in lowered:
        return False  # genuinely absent (not installed) — not an OS block
    failed_module = (module or "").lower()
    return failed_module.endswith("_cy") or f".{_CYEXTENSION_PACKAGE}." in failed_module


def is_blocked_native_extension_error(exc: BaseException) -> bool:
    """True when ``exc`` looks like the OS refusing to load a compiled module.

    A genuinely missing dependency (``No module named 'sqlalchemy'``) must stay
    an ordinary error, so it is deliberately *not* matched here.
    """
    if not isinstance(exc, ImportError):
        return False
    return is_blocked_native_error_text(
        f"{type(exc).__name__}: {exc}",
        str(getattr(exc, "name", "") or ""),
    )


def package_directory(package: str = PACKAGE_NAME) -> str | None:
    """Locate an installed package on disk without importing (executing) it."""
    try:
        spec = importlib.util.find_spec(package)
    except (ImportError, ValueError):
        return None
    if spec is None or not spec.submodule_search_locations:
        return None
    for location in spec.submodule_search_locations:
        if location and os.path.isdir(location):
            return location
    return None


def discover_pure_python_modules(
    package_dir: str,
    package: str = PACKAGE_NAME,
) -> dict[str, str]:
    """Map every compiled ``*_cy`` module to the absolute path of its ``.py`` twin.

    SQLAlchemy >= 2.1 keeps both files side by side (``engine/_row_cy.py`` plus
    ``engine/_row_cy.cp312-win_amd64.pyd``); only modules that actually have a
    compiled twin are listed, because the others already import as pure Python.
    """
    extension_suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    sources: dict[str, str] = {}
    for root, dirnames, filenames in os.walk(package_dir):
        dirnames[:] = [name for name in dirnames if name != "__pycache__"]
        for filename in filenames:
            if not filename.endswith(_CY_SOURCE_SUFFIX):
                continue
            stem = filename[: -len(".py")]
            has_compiled_twin = any(
                other.startswith(stem) and other.endswith(extension_suffixes) for other in filenames
            )
            if not has_compiled_twin:
                continue
            relative = os.path.relpath(os.path.join(root, stem), package_dir)
            module_name = f"{package}.{relative.replace(os.sep, '.')}"
            sources[module_name] = os.path.join(root, filename)
    return sources


def discover_compiled_cyextension_modules(
    package_dir: str,
    package: str = PACKAGE_NAME,
) -> list[str]:
    """SQLAlchemy <= 2.0 keeps its accelerators in ``sqlalchemy.cyextension``.

    Those modules have no ``.py`` twin, so they are reported as *blocked* here:
    hiding them makes SQLAlchemy 2.0 take its own documented pure-Python path
    (``sqlalchemy/engine/_py_row.py`` and friends).
    """
    extension_suffixes = tuple(importlib.machinery.EXTENSION_SUFFIXES)
    cyextension_dir = os.path.join(package_dir, _CYEXTENSION_PACKAGE)
    if not os.path.isdir(cyextension_dir):
        return []
    return sorted(
        f"{package}.{_CYEXTENSION_PACKAGE}.{filename.split('.', 1)[0]}"
        for filename in os.listdir(cyextension_dir)
        if filename.endswith(extension_suffixes)
    )


class _BlockedExtensionLoader(importlib.abc.Loader):
    """Makes an unusable compiled module look simply absent."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> None:
        return None

    def exec_module(self, module) -> None:  # noqa: ANN001 - importlib typeshed shape
        raise ModuleNotFoundError(self._reason, name=module.__name__)


class PurePythonExtensionFinder(importlib.abc.MetaPathFinder):
    """Import hook serving pure-Python twins for blocked compiled modules."""

    def __init__(
        self,
        sources: Mapping[str, str],
        blocked: Iterable[str] = (),
        reason: str = "",
    ) -> None:
        self.sources = dict(sources)
        self.blocked = frozenset(blocked)
        self.reason = reason

    def find_spec(
        self,
        fullname: str,
        path: object = None,
        target: object = None,
    ) -> importlib.machinery.ModuleSpec | None:
        source = self.sources.get(fullname)
        if source is not None:
            if os.path.isfile(source):
                return importlib.util.spec_from_file_location(fullname, source)
            return None
        if fullname in self.blocked:
            return importlib.machinery.ModuleSpec(
                fullname,
                _BlockedExtensionLoader(self.reason or f"{fullname} is disabled"),
            )
        return None


def install_pure_python_fallback(reason: str = "") -> int:
    """Force SQLAlchemy's pure-Python modules; returns how many were redirected.

    Idempotent, and a no-op (returning ``0``) when SQLAlchemy is not installed,
    already ships without compiled accelerators, or has *already been imported
    successfully* — swapping the modules underneath a live import would mix two
    copies of the library, which fails in confusing ways (empty ``CREATE TABLE``
    statements, ``isinstance`` checks against the wrong class). In that case the
    flag has to be set before the process starts.
    """
    global _installed_finder, _redirected_count
    if _installed_finder is not None:
        return _redirected_count

    if PACKAGE_NAME in sys.modules:
        logger.warning(
            "Not switching %s to its pure-Python modules (%s): the package is already "
            "imported in this process. Set DISABLE_SQLALCHEMY_CEXT=1 in the environment "
            "before starting uvicorn/alembic, then restart.",
            PACKAGE_NAME,
            reason or "pure-Python mode requested",
        )
        return 0

    # SQLAlchemy 2.0.x reads this flag itself; for 2.1.x the import hook below is
    # what does the work, and the flag documents the intent for any other tool.
    # Child processes (uvicorn --reload workers) inherit it and skip the probe.
    os.environ.setdefault("DISABLE_SQLALCHEMY_CEXT_RUNTIME", "1")

    package_dir = package_directory()
    if package_dir is None:
        return 0

    sources = discover_pure_python_modules(package_dir)
    blocked = discover_compiled_cyextension_modules(package_dir)
    if not sources and not blocked:
        return 0

    detail = f" ({reason})" if reason else ""
    finder = PurePythonExtensionFinder(
        sources,
        blocked,
        reason=f"{PACKAGE_NAME} native extensions are disabled{detail}",
    )
    # Position 0: the hook answers only for the modules above and returns None
    # for everything else, so the regular PathFinder still handles the rest.
    sys.meta_path.insert(0, finder)
    _installed_finder = finder
    _redirected_count = len(sources)

    # Drop half-imported SQLAlchemy modules so the retry starts from a clean,
    # consistent state (nothing else can hold references yet: the import failed).
    for name in [
        imported
        for imported in sys.modules
        if imported == PACKAGE_NAME or imported.startswith(f"{PACKAGE_NAME}.")
    ]:
        del sys.modules[name]

    logger.warning(
        "SQLAlchemy compiled (Cython) modules are unavailable%s — falling back to "
        "SQLAlchemy's pure-Python modules (%d redirected, %d hidden). Behaviour is "
        "unchanged; row processing is slightly slower. "
        "See docs/LOCAL_RUN_TROUBLESHOOTING_AR.md.",
        detail,
        len(sources),
        len(blocked),
    )
    return _redirected_count


def unrecoverable_native_error(exc: BaseException) -> str:
    """Actionable message for the (rare) case the pure-Python fallback also fails."""
    return "\n".join(
        [
            f"SQLAlchemy could not be imported even with the pure-Python fallback: {exc}",
            "This machine's Application Control policy (WDAC / Smart App Control / AppLocker)",
            "is blocking compiled Python modules. Checklist:",
            "  1. python scripts/check_native_deps.py   -> lists every blocked module",
            "  2. Reinstall SQLAlchemy without compiled wheels:",
            '     pip install --force-reinstall --no-binary sqlalchemy "sqlalchemy>=2.0.50,<2.1"',
            "     (2.0.x falls back to pure Python on its own, no import hook needed)",
            "  3. Or ask IT to allow the files under",
            r"     .venv\Lib\site-packages\sqlalchemy (engine\*_cy*.pyd, sql\*_cy*.pyd,",
            r"     util\*_cy*.pyd) in the Application Control policy.",
            "See docs/LOCAL_RUN_TROUBLESHOOTING_AR.md for the full explanation.",
        ]
    )


def fallback_active() -> bool:
    """True when the pure-Python import hook is installed."""
    return _installed_finder is not None


def ensure_sqlalchemy_importable() -> bool:
    """Import SQLAlchemy, degrading to pure Python when native modules are blocked.

    Returns ``True`` when SQLAlchemy ends up running on its pure-Python modules.
    Idempotent, and safe to call when SQLAlchemy is not installed at all (the real
    import site then reports that error itself).
    """
    if pure_python_requested():
        install_pure_python_fallback("requested via DISABLE_SQLALCHEMY_CEXT")
        return fallback_active()

    if fallback_active():
        return True

    try:
        importlib.import_module(PACKAGE_NAME)
    except ImportError as exc:
        if not is_blocked_native_extension_error(exc):
            return False
        if install_pure_python_fallback(str(exc)) == 0:
            return False
        try:
            importlib.import_module(PACKAGE_NAME)
        except ImportError as retry_exc:
            raise RuntimeError(unrecoverable_native_error(retry_exc)) from retry_exc
        logger.info(
            "SQLAlchemy imported with pure-Python modules — startup can continue "
            "(run scripts/check_native_deps.py to see what this machine blocks)."
        )
    return fallback_active()


def installed_version() -> str:
    """Version of the installed SQLAlchemy distribution (without importing it)."""
    module = sys.modules.get(PACKAGE_NAME)
    version = getattr(module, "__version__", "") if module is not None else ""
    if isinstance(version, str) and version:
        return version
    try:
        return importlib.metadata.version(PACKAGE_NAME)
    except importlib.metadata.PackageNotFoundError:
        return ""


def extension_status() -> dict[str, object]:
    """Snapshot of SQLAlchemy's native-accelerator state (startup logs / doctor).

    Reporting helper: it never imports SQLAlchemy itself, it only describes what
    is on disk plus what this process already loaded.
    """
    status: dict[str, object] = {
        "installed": False,
        "version": installed_version(),
        "package_dir": "",
        "compiled_twins_on_disk": (),
        "cyextension_modules_on_disk": (),
        "compiled_modules_active": None,  # None: SQLAlchemy not imported yet
        "compiled_modules_detail": "",
        "pure_python_fallback_installed": fallback_active(),
        "redirected_modules": tuple(sorted(_installed_finder.sources)) if _installed_finder else (),
        "hidden_modules": tuple(sorted(_installed_finder.blocked)) if _installed_finder else (),
    }

    package_dir = package_directory()
    if package_dir is None:
        return status

    status["installed"] = True
    status["package_dir"] = package_dir
    status["compiled_twins_on_disk"] = tuple(sorted(discover_pure_python_modules(package_dir)))
    status["cyextension_modules_on_disk"] = tuple(
        discover_compiled_cyextension_modules(package_dir)
    )

    if PACKAGE_NAME not in sys.modules:
        return status

    # 2.1.x reports the flag from sqlalchemy.util._has_cython, 2.0.x from _has_cy.
    for flag_module in ("sqlalchemy.util._has_cython", "sqlalchemy.util._has_cy"):
        try:
            flags = importlib.import_module(flag_module)
        except ImportError:
            continue
        status["compiled_modules_active"] = bool(getattr(flags, "HAS_CYEXTENSION", False))
        status["compiled_modules_detail"] = str(getattr(flags, "_CYEXTENSION_MSG", ""))
        break
    return status
