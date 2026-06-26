"""
Shared pytest fixtures and path setup for the first-party test suite.

These tests are deliberately *unit*-level: they exercise pure logic (URL
building, record normalization, parser auto-detection, custody hashing) with
no live Postgres / Neo4j / R2 dependency. Integration tests that need real
services should live under a separate marker (see pyproject ``[tool.pytest]``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable when pytest is invoked from anywhere.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


@pytest.fixture
def clean_db_env(monkeypatch):
    """Strip every DB_* / PLATFORM_DB_URL var so db.url tests start from defaults."""
    for var in (
        "PLATFORM_DB_URL",
        "DB_DRIVER",
        "DB_USER",
        "DB_PASS",
        "DB_HOST",
        "DB_PORT",
        "DB_DATABASE",
    ):
        monkeypatch.delenv(var, raising=False)
    return monkeypatch
