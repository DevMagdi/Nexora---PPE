"""Mantik PPE backend package.

Importing anything from ``app`` first runs :mod:`app.native_compat`: on machines
whose Application Control policy blocks SQLAlchemy's compiled ``_*_cy`` modules
it swaps in the pure-Python twins, so ``python -m uvicorn app.main:app`` and
``python -m app.cli`` start instead of dying with
``ImportError: DLL load failed while importing _row_cy``.

The guard must stay dependency-free (standard library only) because it runs
before pydantic/SQLAlchemy are known to be importable.
"""

from app.native_compat import ensure_sqlalchemy_importable

ensure_sqlalchemy_importable()
