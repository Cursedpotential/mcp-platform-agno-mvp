"""Tests for the AI-chat CONTEXT ingest lane (server/analysis/context_chat_ingest.py).

Pure unit-level: fakes stand in for Weaviate Knowledge and the Graphiti
case-lane client, no live Postgres/Weaviate/Neo4j required. Covers:
  * parsing reuses the EXISTING registry substitution mesh (no new parser)
  * chunking: per-conversation grouping, char-budget splitting, deterministic
    content hashing
  * the ledger makes BOTH sinks idempotent on a re-run (Graphiti has no
    native dedup — this is the only thing preventing duplicate episodes)
  * every chunk carries `tier: context` metadata + the unverified-lead banner
  * dry-run never calls a real sink but still reports accurate counts
"""

from __future__ import annotations

import asyncio
import json

import pytest

from server.analysis.context_chat_ingest import (
    ChatChunk,
    IngestLedger,
    _CONTEXT_BANNER,
    chunk_records,
    filter_conversations,
    ingest_chat_file,
    parse_chat_export,
    write_chunks_to_graphiti,
    write_chunks_to_weaviate,
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
# ledger: idempotency (the load-bearing property for Graphiti, which has no
# native dedup of its own)
# ---------------------------------------------------------------------------


def _sample_chunk(idx=0, conv="conv-1") -> ChatChunk:
    return ChatChunk(
        source="claude-ai-export",
        conversation_id=conv,
        conversation_title="t",
        chunk_index=idx,
        text=f"body {idx}",
        occurred_at_start=None,
        occurred_at_end=None,
        message_count=1,
        content_hash=f"hash-{conv}-{idx}",
    )


def test_ledger_tracks_weaviate_and_graphiti_independently(tmp_path):
    ledger = IngestLedger(tmp_path / "ledger.sqlite3")
    chunk = _sample_chunk()
    assert not ledger.weaviate_done(chunk.content_hash)
    assert not ledger.graphiti_done(chunk.content_hash)

    ledger.mark_weaviate(chunk)
    assert ledger.weaviate_done(chunk.content_hash)
    assert not ledger.graphiti_done(chunk.content_hash)  # independent flag

    ledger.mark_graphiti(chunk)
    assert ledger.graphiti_done(chunk.content_hash)


def test_write_chunks_to_weaviate_tags_tier_context_and_dedupes(tmp_path):
    ledger = IngestLedger(tmp_path / "ledger.sqlite3")
    knowledge = FakeKnowledge()
    chunk = _sample_chunk()

    written, skipped = asyncio.run(write_chunks_to_weaviate(knowledge, [chunk], ledger))
    assert (written, skipped) == (1, 0)
    assert len(knowledge.calls) == 1
    assert knowledge.calls[0]["metadata"]["tier"] == "context"
    assert knowledge.calls[0]["metadata"]["content_hash"] == chunk.content_hash

    # re-run: ledger must skip the duplicate, no second ainsert call
    written2, skipped2 = asyncio.run(write_chunks_to_weaviate(knowledge, [chunk], ledger))
    assert (written2, skipped2) == (0, 1)
    assert len(knowledge.calls) == 1


def test_write_chunks_to_graphiti_case_lane_and_dedupes(tmp_path):
    ledger = IngestLedger(tmp_path / "ledger.sqlite3")
    client = FakeGraphitiClient()
    chunk = _sample_chunk()

    written, skipped = write_chunks_to_graphiti([chunk], ledger, client)
    assert (written, skipped) == (1, 0)
    assert len(client.calls) == 1
    assert "tier=context" in client.calls[0]["source_description"]

    # re-run: must NOT call add_memory again (Graphiti has no native dedup)
    written2, skipped2 = write_chunks_to_graphiti([chunk], ledger, client)
    assert (written2, skipped2) == (0, 1)
    assert len(client.calls) == 1


# ---------------------------------------------------------------------------
# end-to-end: one file -> chunks -> both sinks -> idempotent re-run
# ---------------------------------------------------------------------------


def test_ingest_chat_file_end_to_end_with_fakes(tmp_path):
    f = _two_conversation_export(tmp_path)
    knowledge = FakeKnowledge()
    graphiti = FakeGraphitiClient()
    ledger_path = tmp_path / "ledger.sqlite3"

    report = asyncio.run(ingest_chat_file(f, ledger_path=ledger_path, knowledge=knowledge, graphiti_client=graphiti))
    assert report.record_count == 4
    assert report.chunk_count == 2
    assert report.weaviate_written == 2
    assert report.graphiti_written == 2
    assert report.weaviate_skipped_duplicate == 0
    assert report.graphiti_skipped_duplicate == 0
    assert len(knowledge.calls) == 2
    assert len(graphiti.calls) == 2

    # re-run against the SAME ledger: fully idempotent, zero new writes
    report2 = asyncio.run(ingest_chat_file(f, ledger_path=ledger_path, knowledge=knowledge, graphiti_client=graphiti))
    assert report2.weaviate_written == 0
    assert report2.graphiti_written == 0
    assert report2.weaviate_skipped_duplicate == 2
    assert report2.graphiti_skipped_duplicate == 2
    assert len(knowledge.calls) == 2  # unchanged
    assert len(graphiti.calls) == 2  # unchanged


def test_ingest_chat_file_single_conversation_proof_scope(tmp_path):
    f = _two_conversation_export(tmp_path)
    knowledge = FakeKnowledge()
    graphiti = FakeGraphitiClient()

    report = asyncio.run(
        ingest_chat_file(
            f,
            conversation_ids={"conv-1"},
            ledger_path=tmp_path / "ledger.sqlite3",
            knowledge=knowledge,
            graphiti_client=graphiti,
        )
    )
    assert report.conversation_ids == ["conv-1"]
    assert report.chunk_count == 1
    assert report.weaviate_written == 1
    assert report.graphiti_written == 1


def test_ingest_chat_file_dry_run_never_calls_sinks_but_counts_accurately(tmp_path):
    f = _two_conversation_export(tmp_path)
    report = asyncio.run(ingest_chat_file(f, dry_run=True, ledger_path=tmp_path / "ledger.sqlite3"))
    assert report.dry_run is True
    assert report.chunk_count == 2
    assert report.weaviate_written == 2  # "would write" count, no live client needed
    assert report.graphiti_written == 2
