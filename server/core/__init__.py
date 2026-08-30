"""Lazy compatibility exports for core runtime construction.

Importing :mod:`server.core` must not eagerly load Agno's session, Knowledge,
provider, or vector stack.  The production Platform API imports neutral core
submodules during route registration, so eager package exports would silently
restore AgentOS-era startup coupling even when no Agno capability is used.

Byline: Codex · GPT-5.6-Sol · 2026-08-29
"""

from __future__ import annotations

from typing import Any

__all__ = ["create_knowledge", "db_url", "ensure_duckdb_r2_secret", "get_agno_db", "get_postgres_db"]


def __getattr__(name: str) -> Any:
    """Resolve legacy exports only when a caller explicitly requests one."""

    if name == "db_url":
        from server.core.url import db_url

        return db_url
    if name in {"create_knowledge", "ensure_duckdb_r2_secret", "get_agno_db", "get_postgres_db"}:
        from server.core import session

        return getattr(session, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
