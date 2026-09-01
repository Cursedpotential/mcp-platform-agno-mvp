# Byline: Claude Code · Sonnet (agent) · 2026-07-19 · updated 2026-08-03 (Codex · GPT-5)
"""Repo layer facade.

`staging` (the staged_files CRUD module) is deliberately NOT re-exported by
name here — `get`/`list` would shadow Python builtins for any caller that did
`from app.repo import get, list`. Import the submodule instead:
`from app.repo import staging` then `staging.get(...)` / `staging.list(...)`.
Same reasoning applies to `mcp_client` (`list_tools`/`call_tool` would be
generic enough names to invite accidental shadowing too) — import it as
`from app.repo import mcp_client`.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "check_connectivity",
    "check_lancedb_connectivity",
    "get_db",
    "get_object",
    "object_exists",
    "presigned_get",
    "put_object",
]


def __getattr__(name: str) -> Any:
    """Load heavy staging/object-store SDKs only when their export is used."""
    if name in {"check_lancedb_connectivity", "get_db"}:
        from app.repo import lancedb_client

        return getattr(lancedb_client, name)
    if name in {"check_connectivity", "get_object", "object_exists", "presigned_get", "put_object"}:
        from app.repo import object_store_client

        return getattr(object_store_client, name)
    raise AttributeError(name)
