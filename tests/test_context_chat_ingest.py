"""Tests for the AI-chat CONTEXT ingest lane (server/analysis/context_chat_ingest.py).

Pure unit-level: fakes stand in for Postgres, Weaviate Knowledge, and the
Graphiti case-lane client — no live Postgres/Weaviate/Neo4j required. Covers:
  * parsing reuses the EXISTING registry substitution mesh (no new parser)
  * chunking: per-conversation grouping, char-budget splitting, deterministic
    content hashing
  * PG-first flow (owner ruling 2026-08-12): store to working.context_record
    FIRST, then change-detection (`sync_pending_context`) projects pending rows
    to Weaviate + Graphiti and stamps them synced
  * idempotency now lives in Postgres: the UNIQUE content_hash makes a re-ingest
    a no-op, and the `*_synced_at` stamps make a re-projection find nothing
    pending (Graphiti has no native dedup — this is what prevents dup episodes)
  * every projected chunk carries `tier: context` metadata + the unverified-lead
    banner; dry-run never calls a real sink but still previews accurate counts
"""

from __future__ import annotations

import asyncio
import json

import pytest

import server.analysis.context_chat_ingest as mod
from server.analysis.context_chat_ingest import (
    PendingRecord,
    _CONTEXT_BANNER,
    _record_content_hash,
    chunk_records,
    filter_conversations,
    ingest_chat_file,
    parse_chat_export,
    sync_pending_context,
)
from server.contracts.records import finalize
from server.tools.registry import load_builtin_tools


@pytest.fixture(autouse=True)
def _builtins():
    load_builtin_tools()


def _claude_export(tmp_path, conversations):
    f = tmp_path / "conversations.json"
    f.write_text(json.dumps(conversations), encoding="utf-8")
    return f


def _two_conversation_export(tmp_path):
    return _claude_export(
        tmp_path,
        [
            {
                "uuid": "conv-1",
                "name": "pickup schedule",
                "chat_messages": [
                    {"sender": "human", "text": "she moved pickup again", "created_at": "2026-01-01T10:00:00Z"},
                    {"sender": "assistant", "text": "log the time and date.", "created_at": "2026-01-01T10:00:05Z"},
                ],
            },
            {
                "uuid": "conv-2",
                "name": "school records",
                "chat_messages": [
                    {"sender": "human", "text": "need the enrollment letter", "created_at": "2026-01-02T09:00:00Z"},
                    {
                        "sender": "assistant",
                        "text": "ask the registrar directly.",
                        "created_at": "2026-01-02T09:00:05Z",
                    },
                ],
            },
        ],
    )


class FakeKnowledge:
    """Records every ainsert() call instead of touching Weaviate."""

    def __init__(self):
        self.calls: list[dict] = []

    async def ainsert(self, **kwargs):
        self.calls.append(kwargs)


class FakeGraphitiClient:
    """Records every add_memory() call instead of touching the MCP endpoint."""

    def __init__(self):
        self.calls: list[dict] = []

    def add_memory(self, **kwargs):
        self.calls.append(kwargs)
        return {"message": "queued"}


class FakePG:
    """In-memory stand-in for working.context_record — models exactly the three
    behaviours the lane depends on: UNIQUE content_hash dedup on store, the
    "*_synced_at IS NULL" pending query, and the stamp-on-project update.
    Patched over the module's store/load/mark functions so the whole PG-first
    flow runs with zero live database."""

    def __init__(self):
        self.rows: list[dict] = []
        self._n = 0

    def store(self, records):
        inserted = 0
        seen = {r["content_hash"] for r in self.rows}
        for rec in records:
            ch = _record_content_hash(rec)
            if ch in seen:
                continue
            seen.add(ch)
            self._n += 1
            self.rows.append({"id": f"id-{self._n}", "content_hash": ch, "record": rec, "weaviate": None, "graphiti": None})
            inserted += 1
        return inserted

    def load_pending(self, sink):
        return [PendingRecord(id=r["id"], record=r["record"]) for r in self.rows if r[sink] is None]

    def mark(self, sink, ids):
        idset = set(ids)
        for r in self.rows:
            if r["id"] in idset and r[sink] is None:
                r[sink] = "stamped"


@pytest.fixture
def fake_pg(monkeypatch):
    pg = FakePG()
    monkeypatch.setattr(mod, "store_context_records", pg.store)
    monkeypatch.setattr(mod, "load_pending_context", pg.load_pending)
    monkeypatch.setattr(mod, "mark_synced", pg.mark)
    return pg


# ---------------------------------------------------------------------------
# parse: reuses the existing registry mesh
# ---------------------------------------------------------------------------


def test_parse_chat_export_uses_existing_claude_ai_export_parser(tmp_path):
    f = _two_conversation_export(tmp_path)
    records, parser_id, attempts = parse_chat_export(f)
    assert parser_id == "transcripts.claude-ai-export"
    assert len(records) == 4
    assert {r.conversation_id for r in records} == {"conv-1", "conv-2"}
    assert any(a["ok"] for a in attempts)


def test_parse_chat_export_no_candidate_raises(tmp_path):
    f = tmp_path / "not-a-chat.bin"
    f.write_bytes(b"\x00\x01binary junk")
    with pytest.raises(ValueError):
        parse_chat_export(f)


def test_filter_conversations_restricts_to_ids(tmp_path):
    f = _two_conversation_export(tmp_path)
    records, _, _ = parse_chat_export(f)
    restricted = filter_conversations(records, {"conv-1"})
    assert {r.conversation_id for r in restricted} == {"conv-1"}
    assert filter_conversations(records, None) == records


# ---------------------------------------------------------------------------
# chunk: grouping, char budget, deterministic hash
# ---------------------------------------------------------------------------


def test_chunk_records_one_chunk_per_small_conversation(tmp_path):
    f = _two_conversation_export(tmp_path)
    records, _, _ = parse_chat_export(f)
    records = finalize(records)
    chunks = chunk_records(records, max_chars=6000)
    assert len(chunks) == 2
    by_conv = {c.conversation_id: c for c in chunks}
    assert by_conv["conv-1"].conversation_title == "pickup schedule"
    assert by_conv["conv-1"].message_count == 2
    assert by_conv["conv-1"].chunk_index == 0
    assert _CONTEXT_BANNER in by_conv["conv-1"].text
    assert "she moved pickup again" in by_conv["conv-1"].text


def test_chunk_records_splits_on_char_budget(tmp_path):
    conversations = [
        {
            "uuid": "conv-long",
            "name": "long thread",
            "chat_messages": [
                {"sender": "human", "text": "x" * 100, "created_at": f"2026-01-01T10:00:{i:02d}Z"} for i in range(10)
            ],
        }
    ]
    f = _claude_export(tmp_path, conversations)
    records, _, _ = parse_chat_export(f)
    records = finalize(records)
    # 10 messages * 100 chars = 1000 chars total; budget 250 forces multiple chunks.
    chunks = chunk_records(records, max_chars=250)
    assert len(chunks) > 1
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))
    # every message must appear in exactly one chunk (no drops, no dupes)
    total_messages = sum(c.message_count for c in chunks)
    assert total_messages == 10


def test_chunk_content_hash_is_deterministic(tmp_path):
    f = _two_conversation_export(tmp_path)
    records, _, _ = parse_chat_export(f)
    records = finalize(records)
    chunks_a = chunk_records(records)
    chunks_b = chunk_records(records)
    assert [c.content_hash for c in chunks_a] == [c.content_hash for c in chunks_b]
    # distinct conversations must not collide
    assert len({c.content_hash for c in chunks_a}) == len(chunks_a)


# ---------------------------------------------------------------------------
# record-grain content hash: the PG UNIQUE dedup key
# ---------------------------------------------------------------------------


def test_record_content_hash_deterministic_and_distinct(tmp_path):
    f = _two_conversation_export(tmp_path)
    records, _, _ = parse_chat_export(f)
    records = finalize(records)
    hashes = [_record_content_hash(r) for r in records]
    # deterministic
    assert hashes == [_record_content_hash(r) for r in records]
    # 4 distinct messages -> 4 distinct hashes (no collisions across role/time/content)
    assert len(set(hashes)) == 4


# ---------------------------------------------------------------------------
# change-detection projection: pending rows -> sink, then stamped synced
# ---------------------------------------------------------------------------


def test_sync_pending_weaviate_tags_tier_context_and_stamps(fake_pg, tmp_path):
    f = _two_conversation_export(tmp_path)
    records, _, _ = parse_chat_export(f)
    fake_pg.store(finalize(records))

    knowledge = FakeKnowledge()
    chunks, stamped = asyncio.run(sync_pending_context("weaviate", knowledge=knowledge))
    assert chunks == 2  # one per conversation
    assert stamped == 4  # all four records stamped
    assert len(knowledge.calls) == 2
    assert all(c["metadata"]["tier"] == "context" for c in knowledge.calls)
    assert all(c["metadata"]["lane"] == "context" for c in knowledge.calls)

    # re-run: everything already weaviate-synced -> nothing pending, no new calls
    chunks2, stamped2 = asyncio.run(sync_pending_context("weaviate", knowledge=knowledge))
    assert (chunks2, stamped2) == (0, 0)
    assert len(knowledge.calls) == 2


def test_sync_pending_graphiti_case_lane_and_stamps(fake_pg, tmp_path):
    f = _two_conversation_export(tmp_path)
    records, _, _ = parse_chat_export(f)
    fake_pg.store(finalize(records))

    client = FakeGraphitiClient()
    chunks, stamped = asyncio.run(sync_pending_context("graphiti", graphiti_client=client))
    assert (chunks, stamped) == (2, 4)
    assert len(client.calls) == 2
    assert all("tier=context" in c["source_description"] for c in client.calls)

    # re-run: no native dedup in Graphiti, but PG stamps mean nothing is pending
    chunks2, stamped2 = asyncio.run(sync_pending_context("graphiti", graphiti_client=client))
    assert (chunks2, stamped2) == (0, 0)
    assert len(client.calls) == 2


def test_sync_pending_dry_run_counts_without_sink_or_stamp(fake_pg, tmp_path):
    f = _two_conversation_export(tmp_path)
    records, _, _ = parse_chat_export(f)
    fake_pg.store(finalize(records))

    chunks, stamped = asyncio.run(sync_pending_context("weaviate", dry_run=True))
    assert (chunks, stamped) == (2, 4)
    # dry-run stamped nothing, so a real projection still sees all four pending
    assert len(fake_pg.load_pending("weaviate")) == 4


def test_sync_pending_unknown_sink_raises(fake_pg):
    with pytest.raises(ValueError):
        asyncio.run(sync_pending_context("milvus"))


# ---------------------------------------------------------------------------
# end-to-end: one file -> PG (source of truth) -> both projections -> idempotent
# ---------------------------------------------------------------------------


def test_ingest_chat_file_end_to_end_pg_first(fake_pg, tmp_path):
    f = _two_conversation_export(tmp_path)
    knowledge = FakeKnowledge()
    graphiti = FakeGraphitiClient()

    report = asyncio.run(ingest_chat_file(f, knowledge=knowledge, graphiti_client=graphiti))
    assert report.record_count == 4
    assert report.records_stored == 4  # PG-first write
    assert report.weaviate_chunks == 2
    assert report.weaviate_records_synced == 4
    assert report.graphiti_chunks == 2
    assert report.graphiti_records_synced == 4
    assert len(knowledge.calls) == 2
    assert len(graphiti.calls) == 2

    # re-run: content_hash dedup stores 0, and everything already synced -> 0 projected
    report2 = asyncio.run(ingest_chat_file(f, knowledge=knowledge, graphiti_client=graphiti))
    assert report2.records_stored == 0
    assert report2.weaviate_chunks == 0
    assert report2.graphiti_chunks == 0
    assert len(knowledge.calls) == 2  # unchanged
    assert len(graphiti.calls) == 2  # unchanged


def test_ingest_chat_file_single_conversation_proof_scope(fake_pg, tmp_path):
    f = _two_conversation_export(tmp_path)
    knowledge = FakeKnowledge()
    graphiti = FakeGraphitiClient()

    report = asyncio.run(
        ingest_chat_file(
            f,
            conversation_ids={"conv-1"},
            knowledge=knowledge,
            graphiti_client=graphiti,
        )
    )
    assert report.conversation_ids == ["conv-1"]
    assert report.records_stored == 2
    assert report.weaviate_chunks == 1
    assert report.graphiti_chunks == 1


def test_ingest_chat_file_project_false_writes_pg_only(fake_pg, tmp_path):
    f = _two_conversation_export(tmp_path)
    report = asyncio.run(ingest_chat_file(f, project=False))
    assert report.records_stored == 4
    assert report.weaviate_chunks == 0
    assert report.graphiti_chunks == 0
    # rows are in PG, still pending both sinks for a later worker to drain
    assert len(fake_pg.load_pending("weaviate")) == 4
    assert len(fake_pg.load_pending("graphiti")) == 4


def test_ingest_chat_file_dry_run_previews_without_writing(fake_pg, tmp_path):
    f = _two_conversation_export(tmp_path)
    report = asyncio.run(ingest_chat_file(f, dry_run=True))
    assert report.dry_run is True
    assert report.records_stored == 0
    assert report.weaviate_chunks == 2  # "would project" preview, no client needed
    assert report.graphiti_chunks == 2
    # nothing was actually stored
    assert len(fake_pg.rows) == 0
