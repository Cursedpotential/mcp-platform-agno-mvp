"""audit_dump.py — the owner's "on my call" retrieval surface for ops.audit_ledger.

ADR-0047 / D-042 (docs/adr/0047-audit-everything-ledger.md), decision 5:
"Retrieval on demand: scripts/audit_dump.py — filterable (time/actor/action/
object) + chain verification."

Filters (AND'd together, all optional):
    --since ISO8601      ts >= this (e.g. 2026-08-01 or 2026-08-01T00:00:00Z)
    --until ISO8601      ts <  this
    --actor STR          exact match on actor
    --action {decision,write,read,tool_call,approval,derivation}
    --object STR         substring match against "object_schema.object_ref"
    --limit N            most recent N rows after filtering (default 100; 0 = no cap)

Verification:
    --verify             walk the WHOLE chain (ignores every other filter —
                          verification must see every row) via
                          server.core.audit.verify_chain(); prints "chain OK
                          (<n> rows)" and exits 0, or prints the
                          AuditChainError and exits 1. Combine with a dump
                          filter in the same invocation and --verify still
                          only verifies the full chain; the filtered dump
                          prints separately below it.

Output:
    --format {table,jsonl}   default table (human-readable, aligned columns).
                              jsonl is one compact JSON object per row —
                              ``horizon_context`` stays a nested object, every
                              other value passes through ``str()`` if it is
                              not already JSON-native (covers ``datetime``).

CONTAINERIZED INVOCATION (this repo has no local Python environment — see
AGENTS.md / the S5 handoff's ENVIRONMENT note):

    docker compose run --rm agentos-api python scripts/audit_dump.py --verify

    docker compose run --rm agentos-api python scripts/audit_dump.py \\
        --since 2026-08-01 --action tool_call --format jsonl

Against a scratch/local Postgres (tests, or a one-off outside compose), set
the usual DB_* env vars (or PLATFORM_DB_URL) that server/core/url.py reads —
this script uses the SAME db_url the rest of the platform uses, so a dump
run against the live compose network and a dump run against a scratch
container use identical plumbing:

    DB_HOST=localhost DB_PORT=5433 DB_USER=ai DB_PASS=ai DB_DATABASE=ai \\
        python scripts/audit_dump.py --verify
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-09 (ADR-0047 / D-042 — S5 handoff)

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Make `server` importable when this script is run directly (not via `-m`),
# matching tests/conftest.py's repo-root sys.path convention.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

from server.core.audit import ACTION_TYPES, AuditChainError, verify_chain  # noqa: E402
from server.core.url import db_url  # noqa: E402

_COLUMNS = (
    "id",
    "ts",
    "actor",
    "action_type",
    "object_schema",
    "object_ref",
    "horizon_context",
    "base_version",
    "payload_hash",
    "prev_hash",
    "entry_hash",
)


def _parse_ts(value: str) -> datetime:
    """Accept a bare date (2026-08-01) or a full ISO8601 timestamp, with or
    without a trailing Z (Python's fromisoformat doesn't accept 'Z' before
    3.11's relaxed parser landed everywhere this might run)."""
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(v)
    except ValueError:
        raise SystemExit(f"audit_dump: could not parse timestamp {value!r} (want ISO8601, e.g. 2026-08-01T00:00:00Z)")


def fetch_rows(
    engine: Any,
    *,
    since: datetime | None,
    until: datetime | None,
    actor: str | None,
    action: str | None,
    obj: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {}
    if since is not None:
        clauses.append("ts >= :since")
        params["since"] = since
    if until is not None:
        clauses.append("ts < :until")
        params["until"] = until
    if actor is not None:
        clauses.append("actor = :actor")
        params["actor"] = actor
    if action is not None:
        clauses.append("action_type = :action")
        params["action"] = action
    if obj is not None:
        clauses.append("(coalesce(object_schema, '') || '.' || coalesce(object_ref, '')) ILIKE :obj")
        params["obj"] = f"%{obj}%"

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    limit_sql = "" if limit == 0 else "LIMIT :limit"
    if limit != 0:
        params["limit"] = limit

    sql = (
        f"SELECT {', '.join(_COLUMNS)} FROM ops.audit_ledger {where} "
        f"ORDER BY id DESC {limit_sql}"
    )
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params).mappings().all()
    # Re-ascend to id order for display (we fetched DESC to get the most
    # RECENT `limit` rows, but a chronological read is easier to scan).
    return [dict(r) for r in reversed(rows)]


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    return str(value)


def render_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "(no rows matched)"
    display_cols = ("id", "ts", "actor", "action_type", "object_schema", "object_ref", "payload_hash", "entry_hash")
    widths = {c: max(len(c), *(len(_fmt_cell(r.get(c))) for r in rows)) for c in display_cols}
    lines = ["  ".join(c.ljust(widths[c]) for c in display_cols)]
    lines.append("  ".join("-" * widths[c] for c in display_cols))
    for r in rows:
        lines.append("  ".join(_fmt_cell(r.get(c)).ljust(widths[c]) for c in display_cols))
    return "\n".join(lines)


def _fmt_cell(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, datetime):
        return v.isoformat()
    s = str(v)
    # entry_hash/payload_hash/prev_hash are full sha256 hex (64 chars) —
    # truncate for table readability; jsonl output keeps the full value.
    return s if len(s) <= 16 else s[:12] + "…"


def render_jsonl(rows: list[dict[str, Any]]) -> str:
    lines = []
    for r in rows:
        obj = {c: _jsonable(r.get(c)) for c in _COLUMNS}
        lines.append(json.dumps(obj, sort_keys=True, default=str))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=_parse_ts, default=None, help="ts >= this (ISO8601)")
    ap.add_argument("--until", type=_parse_ts, default=None, help="ts < this (ISO8601)")
    ap.add_argument("--actor", default=None, help="exact actor match")
    ap.add_argument("--action", choices=sorted(ACTION_TYPES), default=None, help="exact action_type match")
    ap.add_argument("--object", default=None, help="substring match on 'object_schema.object_ref'")
    ap.add_argument("--limit", type=int, default=100, help="most recent N rows after filtering (0 = no cap; default 100)")
    ap.add_argument("--format", choices=("table", "jsonl"), default="table")
    ap.add_argument("--verify", action="store_true", help="walk and re-hash the WHOLE chain; ignores the other filters")
    args = ap.parse_args(argv)

    engine = create_engine(db_url, pool_pre_ping=True)

    exit_code = 0
    if args.verify:
        try:
            n = verify_chain(engine=engine)
        except AuditChainError as exc:
            print(f"CHAIN VERIFICATION FAILED: {exc}", file=sys.stderr)
            exit_code = 1
        else:
            print(f"chain OK ({n} row{'s' if n != 1 else ''})")

    any_filter_set = any(
        v is not None for v in (args.since, args.until, args.actor, args.action, args.object)
    )
    if not args.verify or any_filter_set or args.limit != 100:
        rows = fetch_rows(
            engine,
            since=args.since,
            until=args.until,
            actor=args.actor,
            action=args.action,
            obj=args.object,
            limit=args.limit,
        )
        print(render_table(rows) if args.format == "table" else render_jsonl(rows))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
