#!/usr/bin/env python3
"""Alembic CLI that installs the native-extension guard before importing Alembic.

``python -m alembic upgrade head`` imports SQLAlchemy inside Alembic's own entry
point — *before* ``migrations/env.py`` ever runs — so on a machine whose
Application Control policy blocks SQLAlchemy's compiled modules it dies with::

    ImportError: DLL load failed while importing _row_cy:
    An Application Control policy has blocked this file.

This wrapper runs the guard first (``app/native_compat.py``) and then hands the
same arguments over to Alembic::

    python scripts/alembic_cli.py upgrade head
    python scripts/alembic_cli.py current
    python scripts/alembic_cli.py revision --autogenerate -m "add widget table"

On a machine without such a policy it behaves exactly like ``python -m alembic``
run from the repository root. The API applies migrations by itself at startup, so
this is only needed for manual/ops runs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# A script's own directory lands on sys.path[0]; drop it so nothing in scripts/
# can shadow a real package (the file used to be called alembic.py, which made
# `from alembic.config import ...` import *this* file).
_script_dir = str(Path(__file__).resolve().parent)
sys.path[:] = [entry for entry in sys.path if entry not in ("", ".", _script_dir)]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.native_compat import ensure_sqlalchemy_importable  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    # Must happen before `import alembic`: Alembic pulls in SQLAlchemy at import.
    ensure_sqlalchemy_importable()

    from alembic.config import main as alembic_main
    from alembic.util import CommandError

    # Alembic resolves alembic.ini, `script_location = migrations` and relative
    # SQLite paths against the working directory, so match the documented
    # "everything runs from the repository root" setup.
    os.chdir(ROOT)
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        alembic_main(argv=args)
    except CommandError as exc:
        print(f"alembic: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
