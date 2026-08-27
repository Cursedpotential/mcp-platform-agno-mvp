"""llm_probe/db.py — async Postgres access for the `casebible.llm_eval` schema.

Same tables the original one-off harness wrote to by hand (`probe_run`,
`probe_result`); this module just formalizes that into a real connection
pool + schema-init-on-startup instead of a script run manually each time.

Connects via the `DATABASE_URL` env var (postgresql://user:pass@host:5432/casebible)
— set as a Coolify env var on this app, pointed at the same casebible DB the
liveboard data lives in. Nothing here reads local secrets files.

Byline: Claude Code · Sonnet 5 · 2026-08-27
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from psycopg_pool import AsyncConnectionPool

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS llm_eval;

CREATE TABLE IF NOT EXISTS llm_eval.probe_run (
    id            bigserial PRIMARY KEY,
    tier          text NOT NULL,
    started_at    timestamptz NOT NULL DEFAULT now(),
    note          text
);

CREATE TABLE IF NOT EXISTS llm_eval.probe_result (
    id            bigserial PRIMARY KEY,
    run_id        bigint NOT NULL REFERENCES llm_eval.probe_run(id) ON DELETE CASCADE,
    provider      text NOT NULL,
    model         text NOT NULL,
    probe         text NOT NULL,
    ok            boolean NOT NULL,
    http_status   int,
    latency_s     numeric(6,2),
    detail        jsonb,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS probe_result_run_idx ON llm_eval.probe_result(run_id);
CREATE INDEX IF NOT EXISTS probe_result_provider_model_idx ON llm_eval.probe_result(provider, model);

-- ad-hoc playground runs (custom prompts, not one of the named scored probes)
CREATE TABLE IF NOT EXISTS llm_eval.playground_run (
    id                      bigserial PRIMARY KEY,
    provider                text NOT NULL,
    model                   text NOT NULL,
    prompt                  text NOT NULL,
    max_tokens              int NOT NULL,
    temperature             numeric(3,2) NOT NULL,
    reasoning_effort        text,
    ok                      boolean NOT NULL,
    http_status             int,
    latency_s               numeric(6,2),
    content                 text,
    reasoning_overhead_tokens int,
    usage                   jsonb,
    error                   text,
    label                   text,
    created_at              timestamptz NOT NULL DEFAULT now()
);
"""

_pool: Optional[AsyncConnectionPool] = None


def _dsn() -> str:
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("DATABASE_URL env var is not set")
    return dsn


async def get_pool() -> AsyncConnectionPool:
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(_dsn(), min_size=1, max_size=10, open=False)
        await _pool.open()
    return _pool


async def init_schema() -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(SCHEMA_SQL)


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def insert_probe_run(tier: str, note: str) -> int:
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            "INSERT INTO llm_eval.probe_run (tier, note) VALUES (%s, %s) RETURNING id", (tier, note)
        )
        row = await cur.fetchone()
        return row[0]


async def insert_probe_result(run_id: int, provider: str, model: str, probe: str, ok: bool,
                               http_status: Optional[int], latency_s: Optional[float], detail: dict[str, Any]) -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        await conn.execute(
            """INSERT INTO llm_eval.probe_result (run_id, provider, model, probe, ok, http_status, latency_s, detail)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (run_id, provider, model, probe, ok, http_status, latency_s, json.dumps(detail, default=str)),
        )


async def insert_playground_run(**kwargs: Any) -> int:
    pool = await get_pool()
    cols = ["provider", "model", "prompt", "max_tokens", "temperature", "reasoning_effort",
            "ok", "http_status", "latency_s", "content", "reasoning_overhead_tokens", "usage", "error", "label"]
    values = [kwargs.get(c) for c in cols]
    if "usage" in cols:
        idx = cols.index("usage")
        values[idx] = json.dumps(values[idx]) if values[idx] is not None else None
    placeholders = ",".join(["%s"] * len(cols))
    async with pool.connection() as conn:
        cur = await conn.execute(
            f"INSERT INTO llm_eval.playground_run ({','.join(cols)}) VALUES ({placeholders}) RETURNING id",
            values,
        )
        row = await cur.fetchone()
        return row[0]


async def fetch_results(limit: int = 5000) -> list[dict]:
    """All probe_result rows joined to their run, newest first — the same
    shape the liveboard's export script used to hand-query."""
    pool = await get_pool()
    async with pool.connection() as conn:
        cur = await conn.execute(
            """SELECT pr.run_id, r.tier, pr.provider, pr.model, pr.probe, pr.ok, pr.http_status,
                      pr.latency_s, pr.detail, pr.created_at
               FROM llm_eval.probe_result pr
               JOIN llm_eval.probe_run r ON r.id = pr.run_id
               ORDER BY pr.created_at DESC
               LIMIT %s""",
            (limit,),
        )
        cols = [d.name for d in cur.description]
        rows = await cur.fetchall()
    return [dict(zip(cols, row)) for row in rows]


async def fetch_playground_history(provider: Optional[str] = None, model: Optional[str] = None, limit: int = 200) -> list[dict]:
    pool = await get_pool()
    where, params = [], []
    if provider:
        where.append("provider = %s"); params.append(provider)
    if model:
        where.append("model = %s"); params.append(model)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    async with pool.connection() as conn:
        cur = await conn.execute(
            f"SELECT * FROM llm_eval.playground_run {clause} ORDER BY created_at DESC LIMIT %s",
            (*params, limit),
        )
        cols = [d.name for d in cur.description]
        rows = await cur.fetchall()
    return [dict(zip(cols, row)) for row in rows]
