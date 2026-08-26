"""GAP-008/P-09 — retired-Graphiti zero-caller path.

D-070 (owner-ruled 2026-08-25, ``docs/DECISION_LOG.md``): Graphiti is retired
for now. No replacement graph store is authorized here; the memory/graph lane
is an open choice (SurrealDB + n8n + Temporal, Cognee-or-Memgraph TBD).

This file proves, without any live network/DB dependency:

1. ``server.agents.providers.build_context`` never attaches a Graphiti MCP
   tool to ``source_tools`` — not even when ``GRAPHITI_MCP_URL`` is set in the
   environment (regression guard: the removed code path must stay removed,
   independent of any deploy manifest still exporting that variable).
2. ``server.analysis.context_chat_ingest``'s sink/outbox producer
   (``_store_classifications``) only ever writes ``sink='weaviate'``
   projection rows — no new ``sink='graphiti'`` row can be created.
3. ``_project_graphiti`` is a permanent no-op: it never imports or calls
   ``GraphitiCaseClient`` and always returns ``(0, 0)``.
4. ``sync_pending_context("graphiti", ...)`` routes through that no-op rather
   than any live call, for both the empty-pending and legacy-pending-rows
   cases.
5. ``ingest_chat_file`` no longer calls ``sync_pending_context("graphiti")``.

See ``docs/reviews/2026-08-25-schema-audit/AUDIT-GAP-REGISTER.md`` (GAP-008)
and ``docs/reviews/2026-08-25-schema-audit/GAP-008-IMPLEMENTATION-STATUS.md``.

Byline: Claude Code · Sonnet 5 · 2026-08-26
"""

from __future__ import annotations

import asyncio
import sys
from types import SimpleNamespace
from typing import Any

import server.analysis.context_chat_ingest as ingest_mod
from server.analysis.context_chat_ingest import _project_graphiti, _store_classifications, sync_pending_context
from server.contracts.records import ChatLane, LaneClassification


# ---------------------------------------------------------------------------
# 1. Agent roster: no Graphiti MCP tool reaches source_tools, ever.
# ---------------------------------------------------------------------------

_DUMMY_DB_URL = "postgresql+psycopg://u:p@localhost:5432/db"


def _tool_class_names(tools: list[Any]) -> set[str]:
    return {type(entry).__name__ for entry in tools}


def test_build_context_never_attaches_graphiti_even_with_url_set(monkeypatch):
    from server.agents.providers import build_context

    monkeypatch.setenv("GRAPHITI_MCP_URL", "http://100.91.190.107:8071/mcp")
    ctx = build_context(model=None, db=None, knowledge=None, learning=None, db_url=_DUMMY_DB_URL)

    assert "MCPTools" not in _tool_class_names(ctx.source_tools)
    assert not any("graphiti" in str(getattr(t, "tool_name_prefix", "")).lower() for t in ctx.source_tools)


def test_build_context_source_tools_unaffected_by_graphiti_env_var(monkeypatch):
    """Same tool roster whether or not GRAPHITI_MCP_URL is set — proves the
    former conditional attachment point is gone, not merely short-circuited."""
    from server.agents.providers import build_context

    monkeypatch.delenv("GRAPHITI_MCP_URL", raising=False)
    ctx_unset = build_context(model=None, db=None, knowledge=None, learning=None, db_url=_DUMMY_DB_URL)

    monkeypatch.setenv("GRAPHITI_MCP_URL", "http://100.91.190.107:8071/mcp")
    ctx_set = build_context(model=None, db=None, knowledge=None, learning=None, db_url=_DUMMY_DB_URL)

    assert len(ctx_unset.source_tools) == len(ctx_set.source_tools)


def test_providers_module_no_longer_imports_os():
    """``os.getenv("GRAPHITI_MCP_URL", ...)`` was the only ``os`` use in this
    module; regression guard that the attachment block (and its import) is
    fully gone, not merely dead-code-gated."""
    import server.agents.providers as providers_mod

    assert not hasattr(providers_mod, "os")


# ---------------------------------------------------------------------------
# 2. Outbox producer: only "weaviate" projection rows are ever written.
# ---------------------------------------------------------------------------


class _CapturingConnection:
    def __init__(self) -> None:
        self.insert_params: list[dict[str, Any]] = []

    def execute(self, _stmt: Any, params: dict[str, Any] | None = None) -> SimpleNamespace:
        if params is not None:
            self.insert_params.append(params)
        return SimpleNamespace()


def test_store_classifications_never_writes_graphiti_sink_row():
    conn = _CapturingConnection()
    chunk_ids = {"hash-1": "chunk-1"}
    classifications = {
        "hash-1": [LaneClassification(lane=ChatLane.platform, confidence=0.9, review_status="auto_accepted")]
    }

    _store_classifications(conn, chunk_ids, classifications, classifier_id="test-classifier")

    projection_inserts = [p for p in conn.insert_params if "sink" in p]
    assert projection_inserts, "expected at least one projection-row insert for an eligible classification"
    sinks_written = {p["sink"] for p in projection_inserts}
    assert sinks_written == {"weaviate"}
    assert "graphiti" not in sinks_written


# ---------------------------------------------------------------------------
# 3 + 4. _project_graphiti / sync_pending_context("graphiti") are inert.
# ---------------------------------------------------------------------------


def test_project_graphiti_is_a_permanent_noop_and_never_imports_client(monkeypatch):
    # Guarantee no accidental import: fail loudly if anything tries to import
    # the (still-present, otherwise-unused) Graphiti client module.
    monkeypatch.setitem(sys.modules, "server.analysis.graphiti_case_client", None)

    result = _project_graphiti(items=["not-a-real-PendingProjection-but-unused"])  # type: ignore[list-item]

    assert result == (0, 0)


def test_sync_pending_context_graphiti_routes_to_noop_with_pending_legacy_rows(monkeypatch):
    """Even if legacy sink='graphiti' rows exist from before this change,
    draining them performs zero live calls and reports zero-synced."""

    fake_pending = [object(), object(), object()]
    monkeypatch.setattr(ingest_mod, "load_pending_projections", lambda sink: fake_pending)

    synced, chunks = asyncio.run(sync_pending_context("graphiti"))

    assert (synced, chunks) == (0, 0)


def test_sync_pending_context_graphiti_dry_run_still_counts_pending_without_syncing(monkeypatch):
    fake_pending = [SimpleNamespace(chunk_id="a"), SimpleNamespace(chunk_id="b")]
    monkeypatch.setattr(ingest_mod, "load_pending_projections", lambda sink: fake_pending)

    count, distinct_chunks = asyncio.run(sync_pending_context("graphiti", dry_run=True))

    assert (count, distinct_chunks) == (2, 2)


# ---------------------------------------------------------------------------
# 5. ingest_chat_file no longer calls sync_pending_context("graphiti").
# ---------------------------------------------------------------------------


def test_ingest_chat_file_never_requests_graphiti_sink(monkeypatch, tmp_path):
    calls: list[str] = []

    async def _fake_sync(sink: str, **_kwargs: Any) -> tuple[int, int]:
        calls.append(sink)
        return (0, 0)

    monkeypatch.setattr(ingest_mod, "sync_pending_context", _fake_sync)
    monkeypatch.setattr(ingest_mod, "store_chat_batch", lambda *a, **k: 1)

    import json

    path = tmp_path / "conversations.json"
    path.write_text(
        json.dumps(
            [
                {
                    "uuid": "conv-1",
                    "name": "t",
                    "chat_messages": [
                        {"sender": "human", "text": "hello there", "created_at": "2026-01-01T10:00:00Z"},
                    ],
                }
            ]
        )
    )

    asyncio.run(ingest_mod.ingest_chat_file(path, project=True, dry_run=False, classify=False))

    assert "graphiti" not in calls
    assert calls == ["weaviate"]
