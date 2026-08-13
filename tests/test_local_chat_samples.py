r"""Privacy-safe acceptance tests for an owner-supplied local AI-chat corpus.

The corpus is intentionally not checked into Git. Set ``CHAT_SAMPLE_DIR`` to
the directory containing exports, created works, and attachments, then run::

    $env:CHAT_SAMPLE_DIR = "$env:USERPROFILE\OneDrive\Desktop\chat sample"
    uv run pytest -q -m local_samples tests/test_local_chat_samples.py

Every ingest call is a dry run: no PostgreSQL, R2, Weaviate, or Graphiti write
is possible. Test failures identify samples by a short content hash rather than
printing private filenames or conversation text.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

import asyncio
import hashlib
import os
from pathlib import Path

import pytest

from server.analysis.chat_archive import ingest_chat_archive, inventory_archive
from server.analysis.chat_normalizer import normalize_many
from server.analysis.context_assets import categorize, modality
from server.analysis.context_chat_ingest import chunk_chat_messages, parse_chat_export
from server.analysis.lane_classifier import classify_chunks
from server.contracts.records import ChatLane
from server.tools.registry import load_builtin_tools

pytestmark = pytest.mark.local_samples

_TRANSCRIPT_EXTENSIONS = frozenset({".json", ".md"})
_ARCHIVE_EXTENSIONS = frozenset({".zip"})
_LOOSE_ASSET_EXTENSIONS = frozenset(
    {
        ".csv",
        ".doc",
        ".docx",
        ".htm",
        ".html",
        ".jpeg",
        ".jpg",
        ".jsonl",
        ".pdf",
        ".png",
        ".txt",
        ".webp",
        ".xml",
        ".xlsx",
    }
)


def _sample_id(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()[:12]


def _corpus() -> tuple[Path, list[Path]]:
    configured = os.environ.get("CHAT_SAMPLE_DIR")
    if not configured:
        pytest.skip("set CHAT_SAMPLE_DIR to run the private local chat-corpus tests")
    root = Path(configured).expanduser().resolve()
    if not root.is_dir():
        pytest.fail("CHAT_SAMPLE_DIR does not name a readable directory")
    files = sorted(path for path in root.rglob("*") if path.is_file())
    if not files:
        pytest.fail("CHAT_SAMPLE_DIR contains no files")
    return root, files


def _is_loose_transcript(path: Path) -> bool:
    if path.suffix.lower() == ".md":
        return True
    return path.suffix.lower() == ".json" and path.name.lower().startswith("conversations")


def test_every_local_sample_is_accounted_for() -> None:
    """Reject silent omissions when a new kind of sample is added."""

    _, files = _corpus()
    supported = _TRANSCRIPT_EXTENSIONS | _ARCHIVE_EXTENSIONS | _LOOSE_ASSET_EXTENSIONS
    unsupported = [(_sample_id(path), path.suffix.lower()) for path in files if path.suffix.lower() not in supported]
    assert not unsupported, f"unaccounted sample types: {unsupported}"

    # Loose created works/attachments must have an explicit downstream shape,
    # even though only archives currently have a materialization front door.
    loose_assets = [path for path in files if not _is_loose_transcript(path) and path.suffix.lower() != ".zip"]
    for path in loose_assets:
        assert categorize(path.name) in {"document", "code", "image", "data", "other"}, _sample_id(path)
        assert modality(path.name) in {"text", "code", "image", "audio", "video", "binary"}, _sample_id(path)


def test_local_archives_complete_dry_run() -> None:
    """Exercise real ZIP structure, transcript parsing, chunking, and routing."""

    _, files = _corpus()
    archives = [path for path in files if path.suffix.lower() in _ARCHIVE_EXTENSIONS]
    assert archives, "local corpus contains no chat-export archives"
    for path in archives:
        sample_id = _sample_id(path)
        inventory = inventory_archive(path)
        assert inventory.conversation_logs, f"{sample_id}: no conversations*.json member"
        report = asyncio.run(
            ingest_chat_archive(
                path,
                dry_run=True,
                project=False,
                materialize_assets=True,
                chunker="message-window",
            )
        )
        assert report.logs_ingested, f"{sample_id}: no logs exercised"
        assert all(item["record_count"] > 0 for item in report.logs_ingested), f"{sample_id}: empty parse"
        assert all(item["records_stored"] == 0 for item in report.logs_ingested), f"{sample_id}: dry-run wrote rows"
        assert report.assets_materialized is not None
        assert report.assets_materialized["dry_run"] is True
        assert report.assets_materialized["asset_total"] == report.deferred_assets


def test_loose_transcripts_parse_and_chunk_deterministically() -> None:
    """Validate real loose exports without retaining any of their content."""

    load_builtin_tools()
    _, files = _corpus()
    transcripts = [path for path in files if _is_loose_transcript(path)]
    assert transcripts, "local corpus contains no loose transcript files"

    for path in transcripts:
        sample_id = _sample_id(path)
        records, parser_id, attempts = parse_chat_export(path, engine="python")
        assert parser_id, f"{sample_id}: no parser selected"
        assert records, f"{sample_id}: parser emitted no records; attempts={attempts}"
        batches = normalize_many(records, file_path=None)
        assert batches, f"{sample_id}: normalization emitted no conversations"

        for conversation, messages in batches:
            assert conversation.conversation_id
            assert messages
            assert [message.message_index for message in messages] == list(range(len(messages)))
            unexpected_roles = sorted(
                {message.role for message in messages} - {"user", "assistant", "system", "tool", "unknown"}
            )
            assert not unexpected_roles, f"{sample_id}: unexpected normalized roles {unexpected_roles}"

            first = chunk_chat_messages(messages, chunker="message-window")
            second = chunk_chat_messages(messages, chunker="message-window")
            assert [chunk.content_hash for chunk in first] == [chunk.content_hash for chunk in second]
            assert [index for chunk in first for index in chunk.message_indexes] == list(range(len(messages)))

            classifications = classify_chunks(first)
            lanes = {assignment.lane for assignments in classifications.values() for assignment in assignments}
            assert ChatLane.evidence not in lanes
