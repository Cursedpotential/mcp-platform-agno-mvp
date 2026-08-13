"""CPU-first hybrid lane-classification contract tests.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

import pytest

from server.analysis.cpu_lane_classifier import CpuSemanticPolicy, _windows, classify_chunk_cpu
from server.analysis.lane_classifier import classifier_id, classify_chunks
from server.contracts.records import ChatChunk, ChatLane


class SemanticFake:
    """Tiny normalized encoder that makes lane intent mechanically testable."""

    def encode(self, sentences, **kwargs):
        del kwargs
        vectors = []
        for sentence in sentences:
            lowered = sentence.lower()
            vector = [0.0, 0.0, 0.0, 0.0]
            if any(word in lowered for word in ("software", "database", "technical", "retrieval")):
                vector[0] = 1.0
            if any(word in lowered for word in ("law", "court", "custody", "legal")):
                vector[1] = 1.0
            if any(word in lowered for word in ("personal", "relationship", "family", "trauma")):
                vector[2] = 1.0
            if any(word in lowered for word in ("general", "ambiguous", "miscellaneous")):
                vector[3] = 1.0
            norm = sum(component * component for component in vector) ** 0.5 or 1.0
            vectors.append([component / norm for component in vector])
        return vectors


class ZeroEncoder:
    def encode(self, sentences, **kwargs):
        del kwargs
        return [[0.0, 0.0] for _ in sentences]


def _chunk(content: str) -> ChatChunk:
    return ChatChunk(
        conversation_id="c1",
        chunk_index=0,
        content=content,
        content_hash="a" * 64,
        message_indexes=[0],
        chunker_id="message-window",
    )


def test_cpu_semantic_is_multilabel_pending_and_never_evidence():
    assignments = classify_chunk_cpu(
        _chunk("database architecture for a custody court workflow"),
        encoder=SemanticFake(),
        model_id="test-encoder",
        policy=CpuSemanticPolicy(include_lane=0.7),
    )
    lanes = {assignment.lane for assignment in assignments}
    assert {ChatLane.platform, ChatLane.legal, ChatLane.context} <= lanes
    assert ChatLane.evidence not in lanes
    assert all(assignment.review_status == "pending_review" for assignment in assignments)


def test_cpu_windows_prevent_encoder_truncation():
    windows = _windows("x" * 4000, max_chars=1400)
    assert len(windows) == 3
    assert max(map(len, windows)) <= 1400
    assert "".join(windows) == "x" * 4000


def test_cpu_below_threshold_returns_context_only():
    assignments = classify_chunk_cpu(_chunk("opaque material"), encoder=ZeroEncoder())
    assert [assignment.lane for assignment in assignments] == [ChatLane.context]


def test_hybrid_keeps_keyword_and_adds_cpu_candidates():
    chunk = _chunk("database schema and custody court procedure")
    assignments = classify_chunks([chunk], mode="hybrid", encoder=SemanticFake())[chunk.content_hash]
    lanes = {assignment.lane for assignment in assignments}
    assert ChatLane.platform in lanes
    assert ChatLane.legal in lanes
    assert ChatLane.evidence not in lanes


def test_uncalibrated_semantic_score_cannot_downgrade_clear_keyword_acceptance():
    chunk = _chunk("database postgres schema migration sql database postgres schema migration")
    assignments = classify_chunks([chunk], mode="hybrid", encoder=SemanticFake())[chunk.content_hash]
    platform = next(assignment for assignment in assignments if assignment.lane is ChatLane.platform)
    assert platform.review_status == "auto_accepted"
    assert platform.rationale == "keyword-v1"


def test_cpu_mode_fails_open_when_optional_runtime_is_missing(monkeypatch):
    def unavailable(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("runtime missing")

    monkeypatch.setattr("server.analysis.cpu_lane_classifier.load_cpu_encoder", unavailable)
    [assignment] = classify_chunks([_chunk("anything")], mode="cpu")["a" * 64]
    assert assignment.lane is ChatLane.context
    assert assignment.review_status == "classification_failed"


def test_unknown_mode_rejected_and_ids_are_versioned():
    with pytest.raises(ValueError, match="keyword.*cpu.*hybrid"):
        classify_chunks([], mode="remote")
    assert classifier_id("keyword") == "keyword-v1"
    assert classifier_id("cpu", "local/model") == "cpu-v1:local/model"


def test_classifier_id_honors_environment_model(monkeypatch):
    monkeypatch.setenv("CPU_CLASSIFIER_MODEL", "owner/local-model")
    assert classifier_id("hybrid") == "hybrid-v1:owner/local-model"
