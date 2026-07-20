# Byline: Claude Code · Sonnet (agent) · 2026-07-19
"""LanceDB repo layer — connection to the LOCAL whole-file staging store.

Unlike the donor kit (which pointed LanceDB at an S3/B2 URI and mapped B2
credentials into AWS_* env vars for it), the workbench always uses a local
on-disk path (LANCEDB_PATH) — no S3, no AWS env mapping, no vector search.
repo/staging.py builds the `staged_files` table on top of this connection.
"""

from __future__ import annotations

import functools
import logging

import lancedb

from app.config import settings

logger = logging.getLogger(__name__)


@functools.lru_cache(maxsize=1)
def get_db():
    """Connect to the local LanceDB path."""
    logger.info("Connecting to LanceDB at %s", settings.lancedb_path)
    db = lancedb.connect(settings.lancedb_path)
    logger.info("LanceDB connected, existing tables: %s", db.table_names())
    return db


def check_lancedb_connectivity() -> bool:
    """Check if LanceDB is reachable by listing tables."""
    try:
        db = get_db()
        db.table_names()
        return True
    except Exception:
        logger.warning("LanceDB connectivity check failed", exc_info=True)
        return False
