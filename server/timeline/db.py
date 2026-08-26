# Byline: Claude Code · Sonnet 5 · 2026-08-26
"""One lazily-constructed SQLAlchemy engine for the `timeline` schema.

Deliberately separate from `server.core.session` (which wires the Agno-facing
`PostgresDb`/Weaviate/Knowledge stack) — this package only needs plain SQL against the
`timeline.*` tables, so it stays off that heavier import chain.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from server.core.url import db_url

_ENGINE: Engine | None = None


def get_engine() -> Engine:
    """The shared engine. `pool_pre_ping` matches `server.core.session.ensure_duckdb_r2_secret`."""
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = create_engine(db_url, pool_pre_ping=True)
    return _ENGINE
