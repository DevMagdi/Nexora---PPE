#!/usr/bin/env python3
"""Diagnose the native (compiled) Python modules this machine refuses to load.

Windows machines that enforce an Application Control policy (WDAC, Smart App
Control or AppLocker) block native modules they do not trust, which reaches
Nexora as::

    ImportError: DLL load failed while importing _row_cy:
    An Application Control policy has blocked this file.

Every dependency is imported in a throw-away subprocess, so this script reports
what the OS really allows — including modules that would crash the interpreter —
and then prints the fix for each finding.

Usage:
    python scripts/check_native_deps.py            # full check (includes torch)
    python scripts/check_native_deps.py --quick    # skip the heavy ML imports
    python scripts/check_native_deps.py --json     # machine-readable output

Exit code: 0 when everything Nexora needs can run (the automatic pure-Python
SQLAlchemy fallback in ``app/native_compat.py`` counts as "can run"), 1 when a
required module is blocked or missing.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Captured before importing `app`: importing the package installs the pure-Python
# SQLAlchemy fallback, which sets DISABLE_SQLALCHEMY_CEXT_RUNTIME. Probes must not
# inherit that, otherwise a healthy machine would look like a blocked one.
_ENV_BEFORE_GUARD = dict(os.environ)

from app.native_compat import (  # noqa: E402
    FORCE_PURE_PYTHON_ENV_VARS,
    extension_status,
    is_blocked_native_error_text,
    is_policy_blocked_error_text,
)


@dataclass(frozen=True)
class Probe:
    module: str
    group: str
    distribution: str = ""
    required: bool = True
    note: str = ""
    # True when Nexora can work around a block by itself (app/native_compat.py).
    fallback: bool = False


PROBES: tuple[Probe, ...] = (
    # ── API / core ────────────────────────────────────────────────────────
    Probe("fastapi", "API / core"),
    Probe("starlette", "API / core"),
    Probe("pydantic", "API / core"),
    Probe("pydantic_core", "API / core", distribution="pydantic-core"),
    Probe("pydantic_settings", "API / core", distribution="pydantic-settings"),
    Probe("uvicorn", "API / core"),
    Probe("jwt", "API / core", distribution="PyJWT"),
    Probe("cryptography", "API / core"),
    Probe("passlib", "API / core"),
    Probe("multipart", "API / core", distribution="python-multipart"),
    Probe("anyio", "API / core"),
    Probe("httpx", "API / core"),
    Probe("aiosmtplib", "API / core"),
    Probe("dotenv", "API / core", distribution="python-dotenv"),
    # ── Database ──────────────────────────────────────────────────────────
    Probe("sqlalchemy", "Database", fallback=True, note="pure-Python fallback available"),
    Probe("alembic", "Database"),
    Probe("greenlet", "Database", note="required by the async engine, no pure-Python fallback"),
    Probe("aiosqlite", "Database"),
    Probe("asyncpg", "Database", required=False, note="PostgreSQL runtime driver"),
    Probe("psycopg2", "Database", required=False, note="PostgreSQL migrations"),
    Probe("aioodbc", "Database", required=False, note="SQL Server runtime driver"),
    Probe("pyodbc", "Database", required=False, note="SQL Server migrations"),
    # ── Uvicorn extras (--reload / websockets) ────────────────────────────
    Probe("watchfiles", "Uvicorn extras", required=False, note="used by --reload"),
    Probe("httptools", "Uvicorn extras", required=False),
    Probe("websockets", "Uvicorn extras", required=False),
    Probe("uvloop", "Uvicorn extras", required=False, note="POSIX only"),
    # ── Detection stack ───────────────────────────────────────────────────
    Probe("numpy", "Detection stack"),
    Probe("cv2", "Detection stack", distribution="opencv-python-headless"),
    Probe("torch", "Detection stack", note="large import, use --quick to skip"),
    Probe("torchvision", "Detection stack", note="large import, use --quick to skip"),
    Probe("ultralytics", "Detection stack", note="large import, use --quick to skip"),
)

HEAVY_MODULES = frozenset({"torch", "torchvision", "ultralytics"})

STATUS_LABELS = {
    "ok": "OK",
    "blocked": "BLOCKED",
    "blocked-policy": "BLOCKED (policy)",
    "blocked-damaged": "BLOCKED (damaged)",
    "missing": "not installed",
    "error": "ERROR",
    "crashed": "CRASHED",
    "skipped": "skipped",
}

# Runs in the probe subprocess: imports each module, prints one JSON line each.
_PROBE_SCRIPT = r"""
import importlib
import importlib.machinery
import json
import os
import sys

EXTENSION_SUFFIXES = tuple(importlib.machinery.EXTENSION_SUFFIXES)


def version_of(module, distribution):
    for candidate in (getattr(module, "__version__", ""), getattr(module, "VERSION", "")):
        if isinstance(candidate, str) and candidate:
            return candidate
    if distribution:
        try:
            import importlib.metadata as metadata

            return metadata.version(distribution)
        except Exception:
            return ""
    try:
        import importlib.metadata as metadata

        return metadata.version(module.__name__)
    except Exception:
        return ""


def kind_of(module):
    path = getattr(module, "__file__", "") or ""
    if path.endswith(EXTENSION_SUFFIXES):
        return "native"
    directory = os.path.dirname(path)
    if directory and os.path.isdir(directory):
        for root, dirnames, filenames in os.walk(directory):
            dirnames[:] = [name for name in dirnames if name != "__pycache__"]
            if any(name.endswith(EXTENSION_SUFFIXES) for name in filenames):
                return "python + native helpers"
    return "pure-python"


def sqlalchemy_kind():
    for flag_module in ("sqlalchemy.util._has_cython", "sqlalchemy.util._has_cy"):
        try:
            flags = importlib.import_module(flag_module)
        except ImportError:
            continue
        active = bool(getattr(flags, "HAS_CYEXTENSION", False))
        detail = str(getattr(flags, "_CYEXTENSION_MSG", ""))
        state = "Cython accelerators ACTIVE" if active else "pure-Python accelerators"
        return f"{state} ({detail})" if detail else state
    return "accelerator state unknown"


for entry in json.loads(sys.argv[1]):
    name = entry["module"]
    record = {
        "module": name,
        "distribution": entry["distribution"],
        "status": "ok",
        "version": "",
        "kind": "",
        "error": "",
        "error_name": "",
    }
    try:
        module = importlib.import_module(name)
    except BaseException as exc:  # report everything, never crash the probe
        record["status"] = "error"
        record["error"] = f"{type(exc).__name__}: {exc}"
        record["error_name"] = str(getattr(exc, "name", "") or "")
    else:
        record["version"] = version_of(module, entry["distribution"])
        record["kind"] = sqlalchemy_kind() if name == "sqlalchemy" else kind_of(module)
    print(json.dumps(record), flush=True)
"""


@dataclass
class Result:
    probe: Probe
    status: str
    version: str = ""
    kind: str = ""
    detail: str = ""
    caused_by: str = ""  # set when another (already blocked) module is the real cause
    cause: str = ""  # "policy" (OS refused it) or "damaged" (binary cannot be mapped)

    @property
    def label(self) -> str:
        if self.status == "blocked" and self.cause:
            return STATUS_LABELS[f"blocked-{self.cause}"]
        return STATUS_LABELS[self.status]

    @property
    def package(self) -> str:
        return self.probe.distribution or self.probe.module


def probe_environment() -> dict[str, str]:
    """Environment for probe subprocesses, without the guard's own overrides."""
    env = dict(os.environ)
    for key in (*FORCE_PURE_PYTHON_ENV_VARS, "DISABLE_SQLALCHEMY_CEXT_RUNTIME"):
        if key in _ENV_BEFORE_GUARD:
            env[key] = _ENV_BEFORE_GUARD[key]
        else:
            env.pop(key, None)
    return env


def run_probe(entries: list[dict[str, str]], timeout: int) -> tuple[list[dict], str]:
    """Import ``entries`` in a subprocess; returns (records, stderr tail)."""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter, no shell
        [sys.executable, "-X", "utf8", "-c", _PROBE_SCRIPT, json.dumps(entries)],
        capture_output=True,
        text=True,
        timeout=timeout,
        env=probe_environment(),
        cwd=str(ROOT),
        check=False,
    )
    records: list[dict] = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    stderr_tail = "\n".join(completed.stderr.strip().splitlines()[-4:])
    return records, stderr_tail


def collect(quick: bool, timeout: int) -> list[Result]:
    selected = [probe for probe in PROBES if not (quick and probe.module in HEAVY_MODULES)]
    entries = [{"module": p.module, "distribution": p.distribution} for p in selected]

    results: list[Result] = []
    try:
        records, stderr_tail = run_probe(entries, timeout)
    except subprocess.TimeoutExpired:
        records, stderr_tail = [], f"probe timed out after {timeout}s"
    except OSError as exc:
        records, stderr_tail = [], f"probe could not start: {exc}"

    by_module = {record["module"]: record for record in records}
    pending: list[Probe] = []
    for probe in selected:
        record = by_module.get(probe.module)
        if record is None:
            # The probe process died (or timed out) before reporting this module.
            pending.append(probe)
            continue
        results.append(classify(probe, record))

    if pending:
        crashed = pending[0]
        results.append(
            Result(crashed, "crashed", detail=stderr_tail or "probe process exited unexpectedly")
        )
        for probe in pending[1:]:
            # Re-probe one by one: a hard crash only condemns the module before it.
            try:
                records, stderr_tail = run_probe(
                    [{"module": probe.module, "distribution": probe.distribution}], timeout
                )
            except (subprocess.TimeoutExpired, OSError) as exc:
                results.append(Result(probe, "error", detail=str(exc)))
                continue
            if records:
                results.append(classify(probe, records[0]))
            else:
                results.append(Result(probe, "crashed", detail=stderr_tail or "probe process died"))

    order = {probe.module: index for index, probe in enumerate(selected)}
    results.sort(key=lambda item: order.get(item.probe.module, len(order)))
    return results


def classify(probe: Probe, record: dict) -> Result:
    if record["status"] == "ok":
        return Result(probe, "ok", record.get("version", ""), record.get("kind", ""))
    error = record.get("error", "")
    if is_blocked_native_error_text(error, record.get("error_name", "")):
        cause = "policy" if is_policy_blocked_error_text(error) else "damaged"
        return Result(probe, "blocked", detail=error, cause=cause)
    if "No module named" in error or "ModuleNotFoundError" in error:
        return Result(probe, "missing", detail=error)
    return Result(probe, "error", detail=error)


def mark_indirect_blocks(results: list[Result]) -> list[Result]:
    """Flag modules that only failed because another blocked module failed first.

    ``alembic`` imports SQLAlchemy, so a blocked ``_row_cy.pyd`` shows up twice;
    reporting alembic as its own problem would send the user after the wrong fix.
    """
    blocked_names = [item.probe.module for item in results if item.status == "blocked"]
    for item in results:
        if item.status != "blocked":
            continue
        for name in blocked_names:
            if name != item.probe.module and name in item.detail:
                item.caused_by = name
                break
    return results


def describe_sqlalchemy(results: list[Result], status: dict[str, object]) -> list[str]:
    version = str(status.get("version") or "") or "?"
    item = next((entry for entry in results if entry.probe.module == "sqlalchemy"), None)
    if item is None:
        return []
    if item.status == "ok":
        return [f"  SQLAlchemy: {version} — {item.kind}"]
    if item.status == "blocked":
        return [
            f"  SQLAlchemy: {version} — compiled (Cython) modules BLOCKED by the OS",
            "              Nexora runs on SQLAlchemy's pure-Python modules automatically",
            "              (app/native_compat.py); behaviour is identical, queries slightly slower",
        ]
    return [f"  SQLAlchemy: {version} — {STATUS_LABELS[item.status]}: {item.detail}"]


def print_report(results: list[Result], status: dict[str, object]) -> int:
    """Print the table + verdict. ``results`` must already be through
    :func:`mark_indirect_blocks`."""
    print("Nexora native dependency check")
    print(f"  python    : {platform.python_version()} ({sys.executable})")
    print(f"  platform  : {platform.platform()}")
    print(f"  project   : {ROOT}")
    for line in describe_sqlalchemy(results, status):
        print(line)
    if status.get("pure_python_fallback_installed"):
        print(
            "  note      : this process already switched SQLAlchemy to pure-Python modules;\n"
            "              the subprocess probes below still report what the OS blocks."
        )
    print()
    print(f"  {'module':<18} {'status':<14} {'version':<12} kind / detail")

    blocked: list[Result] = []
    missing_required: list[Result] = []
    broken: list[Result] = []
    current_group = ""
    for item in results:
        if item.probe.group != current_group:
            current_group = item.probe.group
            print()
            print(current_group)
        label = item.label
        if item.status == "ok":
            print(f"  {item.probe.module:<18} {label:<14} {item.version:<12} {item.kind}")
            continue
        detail = item.detail.splitlines()[0] if item.detail else label
        if item.caused_by:
            detail = f"blocked through {item.caused_by}: {detail}"
        print(f"  {item.probe.module:<18} {label:<14} {'':<12} {detail}")
        if item.status == "blocked" and not item.caused_by:
            blocked.append(item)
        elif item.status == "missing" and item.probe.required:
            missing_required.append(item)
        elif item.status in {"error", "crashed"}:
            broken.append(item)
        if item.status == "missing" and not item.probe.required:
            print(f"  {'':<18} {'':<14} {'':<12} optional - {item.probe.note}")
    print()

    print_verdict(blocked, missing_required, broken)
    hard_blocked = [item for item in blocked if not item.probe.fallback]
    return 1 if (hard_blocked or missing_required or broken) else 0


def print_verdict(
    blocked: list[Result],
    missing_required: list[Result],
    broken: list[Result],
) -> None:
    if not blocked and not missing_required and not broken:
        print("Verdict: every module Nexora needs loads on this machine.")
        print("Start the API with:")
        print("  python -m uvicorn app.main:app --reload --reload-dir app")
        return

    for item in missing_required:
        print(f"MISSING (required): {item.probe.module}")
        print(f"  {item.detail}")
    for item in broken:
        print(f"FAILED to import: {item.probe.module}")
        print(f"  {item.detail}")

    automatic = [item for item in blocked if item.probe.fallback]
    hard = [item for item in blocked if not item.probe.fallback]
    for item in automatic + hard:
        suffix = (
            "Nexora works around this" if item.probe.fallback else "no fallback - must be fixed"
        )
        print(f"{item.label}: {item.probe.module} ({suffix})")
        print(f"  {item.detail}")
        if item.probe.note:
            print(f"  note: {item.probe.note}")

    if missing_required:
        print()
        print("Fix missing packages:")
        print("  pip install -r requirements.txt          # API + detection stack")
        print("  pip install -r requirements/mssql.txt    # only when using SQL Server")

    if automatic:
        print()
        print("SQLAlchemy needs no action: app/native_compat.py already falls back to the")
        print("pure-Python modules. To get the compiled accelerators back (faster queries),")
        print("have the policy allow the .pyd files, or install a build without them:")
        print('  pip install --force-reinstall --no-binary sqlalchemy "sqlalchemy>=2.0.50,<2.1"')

    damaged = [item for item in hard if item.cause == "damaged"]
    if damaged:
        names = " ".join(item.package for item in damaged)
        print()
        print("Damaged or mismatched native modules (the file exists but cannot be mapped).")
        print("This usually means a half-finished copy/download, or a venv that was moved")
        print("between machines or Python versions. Reinstall them:")
        print(f"  pip install --force-reinstall {names}")
        print("If that does not help, recreate the virtualenv from scratch:")
        print("  py -3.12 -m venv .venv")
        print("  .venv\\Scripts\\Activate.ps1        (Linux/macOS: source .venv/bin/activate)")
        print("  pip install -r requirements.txt")

    policy_blocked = [item for item in hard if item.cause != "damaged"]
    if policy_blocked:
        lines = [
            "",
            "Modules an Application Control policy refuses to load:",
            "  1. Windows Security -> App & browser control -> Smart App Control: when it is",
            '     "On", Windows blocks every unsigned module it does not recognise. Turning',
            "     it off is permanent until Windows is reset, so on a managed machine ask IT.",
            "  2. Corporate WDAC / AppLocker: have IT allow-list the virtualenv folder",
            "     (.venv\\Lib\\site-packages) or the Python publisher. What fired is logged in",
            "     Event Viewer -> Applications and Services Logs -> Microsoft -> Windows ->",
            "     CodeIntegrity (and AppLocker).",
            "  3. If the venv was copied from another machine or unpacked from an archive,",
            "     the files may carry a Mark-of-the-Web block:",
            "     Get-ChildItem -Recurse .venv | Unblock-File",
            "  4. Otherwise recreate the venv in a plain local folder (not OneDrive, not a",
            "     network share) and reinstall:",
            "     py -3.12 -m venv C:\\dev\\Nexora---PPE\\.venv",
            "     C:\\dev\\Nexora---PPE\\.venv\\Scripts\\Activate.ps1",
            "     pip install -r requirements.txt",
            "  5. Re-run: python scripts/check_native_deps.py",
        ]
        print("\n".join(lines))

    print()
    if hard or missing_required or broken:
        print("Verdict: Nexora cannot run until the problems above are fixed.")
    else:
        print("Verdict: Nexora runs on this machine (see the notes above).")
        print("Start the API with:")
        print("  python -m uvicorn app.main:app --reload --reload-dir app")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Check which native Python modules this machine blocks (Application Control).",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Skip the heavy ML imports (torch, torchvision, ultralytics).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Seconds to wait for the probe subprocess (default: 300).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Print machine-readable JSON instead of the report.",
    )
    args = parser.parse_args()

    results = mark_indirect_blocks(collect(quick=args.quick, timeout=args.timeout))
    status = extension_status()

    if args.as_json:
        payload = {
            "python": platform.python_version(),
            "executable": sys.executable,
            "platform": platform.platform(),
            "project": str(ROOT),
            "sqlalchemy": status,
            "results": [
                {
                    "module": item.probe.module,
                    "group": item.probe.group,
                    "required": item.probe.required,
                    "status": item.status,
                    "version": item.version,
                    "kind": item.kind,
                    "detail": item.detail,
                    "caused_by": item.caused_by,
                    "cause": item.cause,
                    "fallback": item.probe.fallback,
                }
                for item in results
            ],
        }
        print(json.dumps(payload, indent=2))
        unresolved = [
            item
            for item in results
            if item.status in {"error", "crashed"}
            or (item.status == "missing" and item.probe.required)
            or (item.status == "blocked" and not item.caused_by and not item.probe.fallback)
        ]
        return 1 if unresolved else 0

    return print_report(results, status)


if __name__ == "__main__":
    raise SystemExit(main())
