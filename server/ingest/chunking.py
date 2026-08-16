"""Framework-neutral Chonkie runtime for canonical ingest records.

The parser emits source-grain :class:`NormalizedRecord` objects. This module
materializes deterministic, version-pinned child records for storage and
retrieval while preserving every temporal field and a content hash back to the
source record. It deliberately imports no Agno, vector, graph, or agent type.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from importlib.metadata import version
from typing import Any

from server.contracts.records import NormalizedRecord
from server.core.chunking_identity import CHONKIE_PIN, chunker_id


DEFAULT_CHUNK_CHARS = 1500


@dataclass(frozen=True)
class ChunkedRecords:
    """One executed chunking result, including logical and materialized counts."""

    records: list[NormalizedRecord]
    chunker_id: str
    source_record_count: int

    @property
    def chunk_count(self) -> int:
        return len(self.records)


def _runtime_version() -> str:
    installed = version("chonkie")
    if installed != CHONKIE_PIN:
        raise RuntimeError(f"Chonkie version drift: installed {installed}, required {CHONKIE_PIN}")
    return installed


def _chunk_attrs(
    record: NormalizedRecord,
    *,
    chunker: str,
    source_record_index: int,
    source_record_hash: str,
    chunk_index: int,
    chunk_count: int,
    chunk: Any,
) -> dict[str, Any]:
    return {
        **record.attrs,
        "chunker_id": chunker,
        "source_record_index": source_record_index,
        "source_record_content_sha256": source_record_hash,
        "chunk_index": chunk_index,
        "chunk_count": chunk_count,
        "chunk_start": getattr(chunk, "start_index", None),
        "chunk_end": getattr(chunk, "end_index", None),
        "chunk_tokens": getattr(chunk, "token_count", None),
        "derived_materialization": "normalized-record-chunk",
    }


def chunk_records(
    records: list[NormalizedRecord],
    *,
    chunk_size: int = DEFAULT_CHUNK_CHARS,
) -> ChunkedRecords:
    """Chunk records with Chonkie RecursiveChunker and preserve provenance.

    The deterministic recursive policy is the neutral file-ingest baseline.
    Conversation ingestion has a separate message-boundary-preserving semantic
    policy; this function must not combine independent normalized records.
    """
    _runtime_version()
    from chonkie import RecursiveChunker

    durable_id = chunker_id("recursive", chunk_size)
    chunker = RecursiveChunker(tokenizer="character", chunk_size=chunk_size)
    materialized: list[NormalizedRecord] = []
    for source_index, record in enumerate(records):
        source_hash = hashlib.sha256(record.content.encode("utf-8")).hexdigest()
        chunks: list[Any] = list(chunker.chunk(record.content)) if record.content else []
        if not chunks:
            # Metadata-only call/media records remain canonical and visible.
            chunks = [_EmptyChunk()]
        for index, chunk in enumerate(chunks):
            materialized.append(
                record.model_copy(
                    update={
                        "content": chunk.text,
                        "attrs": _chunk_attrs(
                            record,
                            chunker=durable_id,
                            source_record_index=source_index,
                            source_record_hash=source_hash,
                            chunk_index=index,
                            chunk_count=len(chunks),
                            chunk=chunk,
                        ),
                    }
                )
            )
    return ChunkedRecords(
        records=materialized,
        chunker_id=durable_id,
        source_record_count=len(records),
    )


@dataclass(frozen=True)
class _EmptyChunk:
    text: str = ""
    start_index: int = 0
    end_index: int = 0
    token_count: int = 0
