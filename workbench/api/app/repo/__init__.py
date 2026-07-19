# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""Repo layer facade.

`staging` (the staged_files CRUD module) is deliberately NOT re-exported by
name here — `get`/`list` would shadow Python builtins for any caller that did
`from app.repo import get, list`. Import the submodule instead:
`from app.repo import staging` then `staging.get(...)` / `staging.list(...)`.
"""

from app.repo.lancedb_client import check_lancedb_connectivity, get_db
from app.repo.object_store_client import (
    check_connectivity,
    get_object,
    object_exists,
    presigned_get,
    put_object,
)

__all__ = [
    "check_connectivity",
    "check_lancedb_connectivity",
    "get_db",
    "get_object",
    "object_exists",
    "presigned_get",
    "put_object",
]
