"""Admin API — one router aggregated from per-domain modules.

Historically this was a single ~1.6k-line ``admin.py``. It's now a package with
one module per concern (analytics, users, and per-module content CRUD), stitched
back into a single ``/admin`` router here so ``app.main`` is unchanged.

``require_admin`` is re-exported because callers import it from this package
(e.g. ``affiliates``).
"""
from fastapi import APIRouter

from .deps import require_admin  # noqa: F401  (re-exported for external importers)
from . import (
    analytics,
    users,
    listening,
    reading,
    writing,
    speaking,
    ielts_tests,
    pricing,
)

router = APIRouter(prefix="/admin", tags=["admin"])

for _mod in (analytics, users, listening, reading, writing, speaking, ielts_tests, pricing):
    router.include_router(_mod.router)

__all__ = ["router", "require_admin"]
