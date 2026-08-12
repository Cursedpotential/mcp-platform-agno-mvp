"""Tests for the registered batch-projection tool (server/tools/ingest/context_drain.py).

DB-free: monkeypatches the analysis-layer `sync_pending_context` so the tool's
payload contract, sink selection, and result shape are exercised without a live
Postgres/Weaviate/Graphiti.
"""

from __future__ import annotations

import pytest

import server.analysis.context_chat_ingest as ingest_mod
from server.tools.registry import load_builtin_tools, registry


@pytest.fixture(autouse=True)
def _builtins():
    load_builtin_tools()


@pytest.fixture
def fake_sync(monkeypatch):
    calls: list[tuple[str, bool, int]] = []

    async def _fake(sink, *, max_chars=6000, dry_run=False):
        calls.append((sink, dry_run, max_chars))
        # deterministic fake counts per sink so assertions can tell them apart
        return ({"weaviate": 3, "graphiti": 2}[sink], {"weaviate": 7, "graphiti": 5}[sink])

    monkeypatch.setattr(ingest_mod, "sync_pending_context", _fake)
    return calls


def test_tool_is_registered_with_write_side_effect():
    tool = registry.get("ingest.context-drain")
    assert tool.capability == "ingest.context-drain"
    assert tool.side_effect == "derived_write"


def test_drain_both_sinks(fake_sync):
    tool = registry.get("ingest.context-drain")
    out = tool.run({})  # default sink = both
    assert out["sinks"] == ["weaviate", "graphiti"]
    assert out["results"]["weaviate"] == {"chunks_projected": 3, "records_synced": 7}
    assert out["results"]["graphiti"] == {"chunks_projected": 2, "records_synced": 5}
    assert [c[0] for c in fake_sync] == ["weaviate", "graphiti"]


def test_drain_single_sink(fake_sync):
    tool = registry.get("ingest.context-drain")
    out = tool.run({"sink": "weaviate"})
    assert out["sinks"] == ["weaviate"]
    assert set(out["results"]) == {"weaviate"}
    assert [c[0] for c in fake_sync] == ["weaviate"]


def test_drain_dry_run_propagates(fake_sync):
    tool = registry.get("ingest.context-drain")
    out = tool.run({"sink": "graphiti", "dry_run": True, "max_chars": 1234})
    assert out["dry_run"] is True
    assert fake_sync == [("graphiti", True, 1234)]


def test_drain_unknown_sink_raises(fake_sync):
    tool = registry.get("ingest.context-drain")
    with pytest.raises(ValueError):
        tool.run({"sink": "milvus"})
