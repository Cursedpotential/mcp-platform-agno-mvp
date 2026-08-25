"""docs/schema/catalog.json must match the LIVE ai database, column for column.

Byline: Claude Code · Fable 5 · 2026-08-25.

Owner directive 2026-08-25: the schema docs under docs/schema/ are canonical, a hard
requirement, and must always be current. This test is the enforcement: it re-reads
pg_catalog from the live PG18 on ovh-files and diffs relation names + column
(name, type) sets against the committed catalog. Any difference fails.

Live-only by policy (no fixtures, no mocks). Skips only when the env file that
holds DB_PASS is absent (e.g. CI without tailnet), and says so loudly.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

REPO = Path(__file__).resolve().parents[1]
CATALOG = REPO / "docs" / "schema" / "catalog.json"
ENV = Path.home() / ".secrets" / "Agno-MCP-Platform.env"
HOST, PORT, DB, USER = "100.91.190.107", 5432, "ai", "ai"


def _password() -> str | None:
    if not ENV.exists():
        return None
    for line in ENV.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^\s*(?:export\s+)?DB_PASS\s*=\s*['\"]?(.+?)['\"]?\s*$", line)
        if m:
            return m.group(1)
    return None


def _live() -> dict[str, list[tuple[str, str]]]:
    import psycopg

    pw = _password()
    if pw is None:
        pytest.skip(f"DB_PASS not resolvable from {ENV} — cannot verify live schema (this is a real gap, not a pass)")
    with psycopg.connect(host=HOST, port=PORT, dbname=DB, user=USER, password=pw, connect_timeout=15) as c:
        cur = c.cursor()
        cur.execute(
            """
            select n.nspname||'.'||c.relname,
                   array_agg(a.attname||':'||format_type(a.atttypid,a.atttypmod) order by a.attnum)
            from pg_class c
            join pg_namespace n on n.oid=c.relnamespace
            join pg_attribute a on a.attrelid=c.oid and a.attnum>0 and not a.attisdropped
            where c.relkind in ('r','p','v','m')
              and n.nspname not in ('pg_catalog','information_schema','pg_toast')
            group by 1
            """
        )
        return {name: [tuple(x.split(":", 1)) for x in cols] for name, cols in cur.fetchall()}


def _committed() -> dict[str, list[tuple[str, str]]]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))["ai"]
    return {f"{d['schema']}.{d['table']}": [(c["name"], c["type"]) for c in d["columns"]] for d in data}


def test_catalog_json_exists() -> None:
    assert CATALOG.exists(), "docs/schema/catalog.json is missing — regenerate with scripts/schema_report/catalog.py"


def test_live_relations_match_committed_catalog() -> None:
    live, doc = _live(), _committed()
    only_live = sorted(set(live) - set(doc))
    only_doc = sorted(set(doc) - set(live))
    assert not only_live, f"relations in LIVE ai but not in docs/schema/catalog.json (regenerate, or an out-of-band CREATE happened): {only_live}"
    assert not only_doc, f"relations in docs/schema/catalog.json but gone from LIVE (regenerate): {only_doc}"


def test_live_columns_match_committed_catalog() -> None:
    live, doc = _live(), _committed()
    drift = {k: (doc[k], live[k]) for k in set(live) & set(doc) if doc[k] != live[k]}
    assert not drift, "column drift between LIVE and docs/schema/catalog.json for: " + ", ".join(sorted(drift))
