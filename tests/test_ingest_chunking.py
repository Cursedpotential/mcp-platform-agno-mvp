"""Framework-neutral Chonkie runtime tests.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from server.contracts.records import NormalizedRecord
from server.core.chunking_identity import CHONKIE_PIN
from server.proffer.chunking import chunk_records


def test_real_recursive_chunker_preserves_source_provenance_and_temporal_fields() -> None:
    record = NormalizedRecord(
        source="fixture",
        content="Alpha beta gamma. Delta epsilon zeta. " * 100,
        role="owner",
        participants=["owner", "other"],
        attrs={"parser_id": "fixture-v1"},
    )

    result = chunk_records([record], chunk_size=64)

    assert result.chunker_id == f"chonkie.recursive@{CHONKIE_PIN}:64-chars"
    assert result.source_record_count == 1
    assert result.chunk_count > 1
    assert "".join(chunk.content for chunk in result.records) == record.content
    assert all(chunk.role == record.role for chunk in result.records)
    assert all(chunk.participants == record.participants for chunk in result.records)
    assert all(chunk.attrs["parser_id"] == "fixture-v1" for chunk in result.records)
    assert [chunk.attrs["chunk_index"] for chunk in result.records] == list(range(result.chunk_count))
    expected_hash = hashlib.sha256(record.content.encode("utf-8")).hexdigest()
    assert {chunk.attrs["source_record_content_sha256"] for chunk in result.records} == {expected_hash}
    assert {chunk.attrs["source_record_index"] for chunk in result.records} == {0}
    assert all(chunk.attrs["derived_materialization"] == "normalized-record-chunk" for chunk in result.records)


def test_empty_record_remains_visible_as_one_zero_length_chunk() -> None:
    result = chunk_records([NormalizedRecord(source="fixture", content="", attrs={"kind": "call"})])
    assert result.chunk_count == 1
    assert result.records[0].content == ""
    assert result.records[0].attrs["chunk_tokens"] == 0
    assert result.records[0].attrs["kind"] == "call"


def test_neutral_chunking_source_has_no_framework_imports() -> None:
    source = (Path(__file__).resolve().parents[1] / "server/proffer/chunking.py").read_text(encoding="utf-8").lower()
    for forbidden in ("import agno", "import graphiti", "import surreal", "vercel", "ai_sdk"):
        assert forbidden not in source


def test_production_dependency_pin_is_torch_free() -> None:
    root = Path(__file__).resolve().parents[1]
    requirements = (root / "requirements.txt").read_text(encoding="utf-8").lower().splitlines()
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8").lower()
    assert '"chonkie[semantic,code,table]==1.7.0"' in pyproject
    assert "chonkie==1.7.0" in requirements
    for forbidden in ("torch==", "torchvision==", "transformers==", "sentence-transformers=="):
        assert not any(line.startswith(forbidden) for line in requirements)
