"""Intended-behavior tests for the AI-chat ingestion pipeline.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import pytest

import server.analysis.context_chat_ingest as ingest_mod
from server.analysis.chat_normalizer import normalize_chat_role, normalize_many
from server.analysis.context_chat_ingest import (
    CONTEXT_BANNER,
    chunk_chat_messages,
    filter_conversations,
    ingest_chat_file,
    parse_chat_export,
)
from server.analysis.lane_classifier import classify_chunks, classification_failure
from server.contracts.records import ChatLane, LaneClassification
from server.tools.registry import load_builtin_tools


@pytest.fixture(autouse=True)
def _builtins():
    load_builtin_tools()


def _export(tmp_path):
    path = tmp_path / "conversations.json"
    path.write_text(
        json.dumps(
            [
                {
                    "uuid": "conv-1",
                    "name": "cross-domain design",
                    "chat_messages": [
                        {
                            "sender": "human",
                            "text": "Design the Postgres schema for my custody motion and MCL 722.23 notes.",
                            "created_at": "2026-01-01T10:00:00Z",
                        },
                        {
                            "sender": "assistant",
                            "text": "Keep the legal claims separate from the database migration.",
                            "created_at": "2026-01-01T10:00:05Z",
                        },
                    ],
                },
                {
                    "uuid": "conv-2",
                    "name": "personal history",
                    "chat_messages": [
                        {
                            "sender": "human",
                            "text": "I felt afraid during that relationship.",
                            "created_at": "2026-01-02T09:00:00Z",
                        }
                    ],
                },
            ]
        ),
        encoding="utf-8",
    )
    return path


def test_parse_reuses_existing_parser_and_filter(tmp_path):
    path = _export(tmp_path)
    records, parser_id, attempts = parse_chat_export(path)
    assert parser_id == "transcripts.claude-ai-export"
    assert len(records) == 3
    assert any(attempt["ok"] for attempt in attempts)
    assert {record.conversation_id for record in filter_conversations(records, {"conv-1"})} == {"conv-1"}


def test_chunking_preserves_roles_messages_and_hashes(tmp_path):
    path = _export(tmp_path)
    records, _, _ = parse_chat_export(path)
    batches = normalize_many(records, str(path))
    messages = [message for _, batch in batches for message in batch]

    first = chunk_chat_messages(messages, max_chars=6000)
    second = chunk_chat_messages(messages, max_chars=6000)
    assert [chunk.content_hash for chunk in first] == [chunk.content_hash for chunk in second]
    assert sum(len(chunk.message_indexes) for chunk in first) == len(messages)
    assert CONTEXT_BANNER in first[0].content
    assert "[user]" in first[0].content and "[assistant]" in first[0].content


def test_hard_cap_never_splits_a_message(tmp_path):
    path = _export(tmp_path)
    records, _, _ = parse_chat_export(path)
    messages = normalize_many(records, str(path))[0][1]
    chunks = chunk_chat_messages(messages, max_chars=80)
    flattened = [index for chunk in chunks for index in chunk.message_indexes]
    assert flattened == [0, 1]
    assert all(chunk.message_indexes for chunk in chunks)


def test_cross_domain_chunk_gets_multiple_lanes(tmp_path):
    path = _export(tmp_path)
    records, _, _ = parse_chat_export(path)
    messages = normalize_many(records, str(path))[0][1]
    chunk = chunk_chat_messages(messages)[0]
    assignments = classify_chunks([chunk])[chunk.content_hash]
    lanes = {assignment.lane for assignment in assignments}
    assert ChatLane.platform in lanes
    assert ChatLane.legal in lanes
    assert ChatLane.evidence not in lanes


def test_ambiguous_and_failed_classification_remain_searchable(tmp_path):
    path = _export(tmp_path)
    records, _, _ = parse_chat_export(path)
    personal_messages = normalize_many(records, str(path))[1][1]
    chunk = chunk_chat_messages(personal_messages)[0]
    assignments = classify_chunks([chunk])[chunk.content_hash]
    if any(assignment.review_status == "pending_review" for assignment in assignments):
        assert ChatLane.context in {assignment.lane for assignment in assignments}

    failed = classification_failure("model unavailable")
    assert failed[0].lane is ChatLane.context
    assert failed[0].review_status == "classification_failed"


def test_chat_contract_rejects_evidence_lane():
    with pytest.raises(ValueError, match="cannot be routed to the evidence"):
        LaneClassification(lane=ChatLane.evidence, confidence=0.9, review_status="auto_accepted")


def test_normalizer_closes_provider_role_vocabulary():
    assert normalize_chat_role("user") == "user"
    assert normalize_chat_role(" Assistant ") == "assistant"
    assert normalize_chat_role("transcript") == "unknown"
    assert normalize_chat_role(None) == "unknown"


def test_two_lane_projection_embeds_once_and_reuses_vector(monkeypatch):
    class Embedder:
        calls = 0

        def get_embedding_and_usage(self, content):
            self.calls += 1
            return [0.1, 0.2, 0.3], {"tokens": 4}

    class Data:
        def __init__(self):
            self.inserts = []

        def insert(self, **kwargs):
            self.inserts.append(kwargs)

    embedder = Embedder()
    data = Data()
    collection = SimpleNamespace(data=data)
    client = SimpleNamespace(collections=SimpleNamespace(get=lambda name: collection))
    vector_db = SimpleNamespace(embedder=embedder, get_client=lambda: client)
    handles = {lane: SimpleNamespace(vector_db=vector_db) for lane in ("platform", "legal")}
    cached = []
    marked = []
    monkeypatch.setattr(ingest_mod, "create_all_lane_knowledge", lambda: handles)
    monkeypatch.setattr(ingest_mod, "_load_cached_embedding", lambda chunk_id: None)
    monkeypatch.setattr(ingest_mod, "_cache_embedding", lambda item, vector, usage: cached.append(vector))
    monkeypatch.setattr(ingest_mod, "_mark_projected", lambda item, ref: marked.append((item.lane, ref)))
    base = {
        "chunk_id": "chunk-1",
        "content_hash": "a" * 64,
        "content": "[user] database schema and court motion",
        "sink": "weaviate",
        "conversation_external_id": "conv-1",
        "conversation_title": "mixed",
        "chunk_index": 0,
    }
    items = [
        ingest_mod.PendingProjection(lane="platform", **base),
        ingest_mod.PendingProjection(lane="legal", **base),
    ]

    projected, chunks = asyncio.run(ingest_mod._project_weaviate(items))

    assert (projected, chunks) == (2, 1)
    assert embedder.calls == 1
    assert cached == [[0.1, 0.2, 0.3]]
    assert len(data.inserts) == 2
    assert data.inserts[0]["vector"] is data.inserts[1]["vector"]
    assert {lane for lane, _ in marked} == {"platform", "legal"}


def test_dry_run_exercises_parse_chunk_classify_without_database(tmp_path):
    report = asyncio.run(ingest_chat_file(_export(tmp_path), dry_run=True))
    assert report.record_count == 3
    assert report.records_stored == 0
    assert report.classified is True
    assert report.classifier_id is not None and report.classifier_id.startswith("hybrid-v1:")
    assert report.dry_run is True
    assert {"platform", "legal", "personal_history"}.intersection(report.lane_counts)
