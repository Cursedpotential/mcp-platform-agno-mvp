"""server/tools/ingest/context_drain.py — registered tool: drain pending
`working.context_record` rows into their vector/graph sinks.

This is the BATCH PROJECTION step of the PG-first context lane (D-048,
ADR-0051): Postgres is the source of truth, and this tool is the
change-detection consumer — it reads the rows still pending for a sink
(`<sink>_synced_at IS NULL`), projects them to the Weaviate `platform_context`
collection and/or the Graphiti CASE lane, and stamps them synced.

WHY IT'S A TOOL (owner, 2026-08-12): "make sure it's written as a tool or
something so that we can easily trigger that batch process easily and quickly
until we do get the full workflow built out." Registering it here makes the
drain callable the same three ways every platform capability is (invariant 7,
ADR-0023/0046): the CLI (`scripts/drain_context.py`), an agent, and MCP — one
implementation, three front doors. It stands in for the always-on CDC worker
(the trigger/outbox/cursor spine, still deferred) with a manual/scriptable
pull.

Idempotent: projects ONLY rows still pending for the requested sink and stamps
them, so re-running drains just what arrived since — never a duplicate.

Payload:
  { "sink": "weaviate" | "graphiti" | "both" (default "both"),
    "dry_run": bool (default False — count what WOULD project, touch nothing),
    "max_chars": int (default 6000 — per-chunk budget) }
Returns:
  { "dry_run": bool, "sinks": [...],
    "results": { "<sink>": {"chunks_projected": int, "records_synced": int} } }
"""
# Byline: Claude Code · Opus 4.8 · 2026-08-12

from __future__ import annotations

import asyncio
from typing import Any

from server.tools.registry import register

_PROVENANCE = "server/analysis/context_chat_ingest.py::sync_pending_context (D-048, ADR-0051)"
_SINKS = ("weaviate", "graphiti")


@register(
    id="ingest.context-drain",
    capability="ingest.context-drain",
    description=(
        "Drain pending working.context_record rows into Weaviate platform_context + the Graphiti "
        "CASE lane (PG-first change-detection projection, D-048). Idempotent; the manual stand-in "
        "for the CDC worker."
    ),
    provenance=_PROVENANCE,
    execution_policy="manual_or_auto",
    side_effect="derived_write",
)
def context_drain(payload: dict[str, Any]) -> dict[str, Any]:
    # lazy: pulls in sqlalchemy + agno/weaviate + the Graphiti client, which the
    # dep-light facade container lacks and which the pure-registry import must not require.
    from server.analysis.context_chat_ingest import sync_pending_context

    sink = str(payload.get("sink", "both")).lower()
    dry_run = bool(payload.get("dry_run", False))
    max_chars = int(payload.get("max_chars", 6000))

    if sink in ("both", "all", ""):
        sinks = list(_SINKS)
    elif sink in _SINKS:
        sinks = [sink]
    else:
        raise ValueError(f"unknown sink {sink!r} (expected 'weaviate', 'graphiti', or 'both')")

    async def _drain() -> dict[str, Any]:
        out: dict[str, Any] = {}
        for s in sinks:
            chunks, records = await sync_pending_context(s, max_chars=max_chars, dry_run=dry_run)
            out[s] = {"chunks_projected": chunks, "records_synced": records}
        return out

    results = asyncio.run(_drain())
    return {"dry_run": dry_run, "sinks": sinks, "results": results}
