"""Convenience launcher for the Celery worker.

Equivalent to invoking::

    celery -A app.worker.celery_app worker --loglevel=info --pool=<pool>

Pool selection is platform-dependent and matters for production:

    Windows (development):
        --pool=solo   (Celery prefork pool is not supported on Windows)

    Linux / macOS (production):
        --pool=prefork  (default; lets the OS fork one child per CPU for
                        real parallel execution of resume parsing tasks)

This script defaults to ``--pool=solo`` ONLY on Windows; on Linux/macOS it
defaults to ``--pool=prefork``. Pass ``--pool=...`` explicitly to override.

Run from the project root::

    python scripts/start_celery_worker.py

Stage 6 deliverable: any ops dashboard / Dockerfile that needs to run a
worker should invoke this script (or the equivalent ``celery -A ...``
command) instead of importing the app stack directly. Task registration
happens lazily inside :mod:`app.worker.celery_app` via the ``include``
list when the worker boots.
"""

from __future__ import annotations

import sys


def _default_pool() -> str:
    # sys.platform values: 'win32', 'linux', 'darwin', ...
    if sys.platform.startswith("win"):
        return "solo"
    return "prefork"


def main() -> int:
    from app.worker.celery_app import celery_app as app

    user_args = sys.argv[1:]
    args = ["worker", "--loglevel=info"]

    has_pool_override = any(a.startswith("--pool=") for a in user_args)
    if not has_pool_override:
        args.append(f"--pool={_default_pool()}")

    args.extend(user_args)
    # Celery's worker command parses its argv from sys.argv — emulate the
    # CLI surface so app.start() sees the args we want.
    sys.argv = ["celery"] + args
    app.start(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
