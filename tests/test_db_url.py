"""Unit tests for db.url.build_db_url — connection-string assembly.

A bug here breaks *every* database connection in the platform, yet the
function is pure (env in, string out) and trivially testable.

db.url has zero third-party dependencies, but importing it via the ``db``
package would eagerly pull in ``agno`` (db/__init__.py). We load the module
directly from its file so this stays a dependency-free unit test.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_URL_PATH = Path(__file__).resolve().parents[1] / "server" / "core" / "url.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("_db_url_under_test", _URL_PATH)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _build(monkeypatch, **env):
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
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return _load_module().build_db_url()


def test_defaults_when_no_env(clean_db_env):
    assert _load_module().build_db_url() == "postgresql+psycopg://ai:ai@localhost:5432/ai"


def test_platform_db_url_takes_precedence(monkeypatch):
    # Explicit connection string wins even when granular DB_* vars are set.
    url = _build(
        monkeypatch,
        PLATFORM_DB_URL="postgresql://explicit/url",
        DB_USER="ignored",
        DB_HOST="ignored-host",
    )
    assert url == "postgresql://explicit/url"


def test_granular_vars_compose(monkeypatch):
    url = _build(
        monkeypatch,
        DB_DRIVER="postgresql+psycopg",
        DB_USER="bob",
        DB_PASS="secret",
        DB_HOST="db.internal",
        DB_PORT="6543",
        DB_DATABASE="platform",
    )
    assert url == "postgresql+psycopg://bob:secret@db.internal:6543/platform"


def test_password_is_url_quoted(monkeypatch):
    # Special characters in the password must be percent-encoded or the URL
    # parser will choke / mis-route the host. '@' -> %40, ':' -> %3A, '/' -> %2F.
    url = _build(monkeypatch, DB_PASS="p@ss:w/rd")
    assert "p%40ss%3Aw%2Frd" in url
    # The raw, unquoted password must NOT appear.
    assert "p@ss:w/rd" not in url


def test_module_level_db_url_matches_builder(clean_db_env):
    # db.url caches db_url at import time and db/session.py consumes that cached
    # value — so later env changes must NOT mutate it, while build_db_url()
    # reflects the new env.
    mod = _load_module()
    baseline = mod.db_url
    assert baseline == mod.build_db_url()

    clean_db_env.setenv("DB_HOST", "changed-host")
    assert mod.db_url == baseline
    assert mod.build_db_url() != baseline
