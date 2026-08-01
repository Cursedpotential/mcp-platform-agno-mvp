"""server/analysis/context_chat_ingest.py — the AI-chat CONTEXT ingest lane.

Owner brief (2026-08-01): ingest the owner's AI-chat exports (Claude/ChatGPT/
Perplexity/Gemini conversations about the custody case) so the platform can
surface leads worth chasing, capture stated preferences, and reconstruct
legal-strategy discussion — WITHOUT ever letting a chat be cited as proof.

NON-NEGOTIABLE boundary (owner, verbatim): "AI chats are CONTEXT, never
EVIDENCE. They go to the `memory` Neo4j database ONLY." This module therefore
does **not** touch the evidence spine at all:
  * no `server.evidence.custody.ingest_artifact` (no custody chain)
  * no `server.evidence.store.store_records` (no `analysis.normalized_record`)
  * no `server.evidence.store.ingest_into_knowledge` (evidence-domain tags)
This is a deliberate, small duplication of `render_conversations_markdown`'s
shape (see server/evidence/store.py) rather than an import of it: `analysis/`
is documented (server/AGENTS.md) to depend on `contracts/`, `core/`, `tools/`
only — never `evidence/` — and that boundary is exactly what keeps chat
context from ever becoming reachable through the evidence-only surfaces.

Pipeline: chat export file -> detect format & parse (registry `parse.transcript`,
same try-next-candidate substitution mesh as `evidence/workflows.py`'s
chat-transcript workflow — reuses the EXISTING 12 ai-chat/messaging parsers,
writes none) -> group into per-conversation chunks -> dual write:
  (a) Weaviate collection `platform_context` (a SECOND, separate Knowledge
      instance from `platform_knowledge` — see `create_context_knowledge()`),
      every chunk tagged `tier: context` in metadata (-> both the `filters`
      object property and the `meta_data` text property, agno's own
      `Content.metadata` -> `Document.meta_data` + vector_db `filters=`
      plumbing — verified against agno 2.8.0 source, no new encoding needed).
  (b) Graphiti CASE lane (`server/analysis/graphiti_case_client.py`) via
      `add_memory` — Graphiti's own entity/relationship/temporal extraction
      IS the entity pipeline (GLiNER2-backed); this module does not
      extract entities itself.

Idempotency: Weaviate gets a second layer of safety for free (agno's
`Content.content_hash` + `upsert=True` default updates-in-place on a
re-insert with the same deterministic `name`), but Graphiti's `add_memory`
has NO such dedup — calling it twice with identical content creates two
episodes. `IngestLedger` (local SQLite, content-hash keyed) is therefore the
one source of truth for "already sent" on BOTH sinks, checked before every
write.

Every chunk (both sinks) is prefixed with `_CONTEXT_BANNER` so raw chunk text
read directly (Weaviate search result, Graphiti episode body) still carries
the disclaimer even outside the `tier: context` metadata — matching the
platform's existing `cb-vsearch` convention: surface as "unverified lead —
verify against primary evidence", never as fact.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01

from __future__ import annotations

import hashlib
import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from os import getenv
from pathlib import Path
from typing import Any, Iterator

from server.analysis.graphiti_case_client import GraphitiCaseClient
from server.contracts.records import NormalizedRecord, finalize
from server.tools.registry import load_builtin_tools, registry

CONTEXT_KNOWLEDGE_NAME = "context"
CONTEXT_TABLE_NAME = "platform_context"
DEFAULT_MAX_CHARS = 6000
DEFAULT_LEDGER_PATH = Path(getenv("CONTEXT_INGEST_LEDGER_PATH", "data/context_ingest/ledger.sqlite3"))

_CONTEXT_BANNER = (
    "[UNVERIFIED LEAD -- AI-chat context, not primary evidence. "
    "Verify against primary evidence before relying on this.]"
)


# ---------------------------------------------------------------------------
# Knowledge lane (Weaviate `platform_context`, separate from `platform_knowledge`)
# ---------------------------------------------------------------------------


def create_context_knowledge():
    """A SECOND agno Knowledge instance — separate Weaviate collection
    (`platform_context`), separate Postgres contents table
    (`platform_context_contents`) — so AI-chat context never mixes with
    platform build/design docs in the same collection.

    Thin wrapper over `server.core.session.create_knowledge()` (same
    contract, `VerifiedWeaviate` + nv-embed-v1 4096-d text embedder); the
    only new decision here is the name/table pair. Imported lazily (function
    body, not module level) because `server.core.session` pulls in
    sqlalchemy/agno DB wiring that unit tests for the pure parse/chunk logic
    below should not have to construct.
    """
    from server.core.session import create_knowledge

    return create_knowledge(CONTEXT_KNOWLEDGE_NAME, CONTEXT_TABLE_NAME)


# ---------------------------------------------------------------------------
# Parse: reuse the EXISTING registry substitution mesh, no new parser
# ---------------------------------------------------------------------------


def parse_chat_export(
    path: Path, source_meta: dict[str, Any] | None = None
) -> tuple[list[NormalizedRecord], str, list[dict[str, Any]]]:
    """Resolve `parse.transcript` candidates for `path` and try each in
    registration order until one succeeds — the identical pattern
    `evidence/workflows.py`'s `build_chat_transcript_workflow.parse_step`
    uses, minus the custody/store wiring. Returns (records, winning_tool_id,
    attempts_log). Raises ValueError if every candidate rejects the file.
    """
    load_builtin_tools()
    if not path.is_file():
        raise FileNotFoundError(path)
    candidates = registry.resolve("parse.transcript", media_hint=path.name.lower(), size_bytes=path.stat().st_size)
    if not candidates:
        raise ValueError(f"no parse.transcript tool accepts {path.name!r}")

    attempts: list[dict[str, Any]] = []
    last_err: Exception | None = None
    for tool in candidates:
        try:
            result = tool.run({"path": str(path), "source_meta": source_meta or {}})
            attempts.append({"tool": tool.id, "ok": True})
            records = [NormalizedRecord.model_validate(r) for r in result["records"]]
            return records, tool.id, attempts
        except Exception as exc:  # wrong format -> try next same-capability tool
            attempts.append({"tool": tool.id, "ok": False, "error": str(exc)})
            last_err = exc
    raise ValueError(f"all parse.transcript candidates failed for {path.name!r}: {attempts} (last: {last_err})")


def filter_conversations(records: list[NormalizedRecord], conversation_ids: set[str] | None) -> list[NormalizedRecord]:
    """Restrict to specific conversation_id(s) — used for the single-chat
    proof run so a giant multi-conversation export (e.g. a 58 MB claude.ai
    `conversations.json` covering an entire account) doesn't get bulk-written
    just to prove the pipeline on ONE small chat."""
    if conversation_ids is None:
        return records
    return [r for r in records if (r.conversation_id or "") in conversation_ids]


# ---------------------------------------------------------------------------
# Chunk: group by conversation, render, hash
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChatChunk:
    source: str
    conversation_id: str
    conversation_title: str
    chunk_index: int
    text: str
    occurred_at_start: datetime | None
    occurred_at_end: datetime | None
    message_count: int
    content_hash: str = field(compare=False)


def _render_chunk(
    source: str, conversation_id: str, title: str, chunk_index: int, recs: list[NormalizedRecord]
) -> ChatChunk:
    lines = [_CONTEXT_BANNER, "", f"# {title} (part {chunk_index + 1})", ""]
    for r in recs:
        stamp = f" — {r.occurred_at.isoformat()}" if r.occurred_at else ""
        lines += [f"**{(r.role or 'unknown').upper()}{stamp}:**", "", r.content, "", "---", ""]
    text = "\n".join(lines)
    content_hash = hashlib.sha256(f"{source}:{conversation_id}:{chunk_index}:{text}".encode("utf-8")).hexdigest()
    dated = [r.occurred_at for r in recs if r.occurred_at is not None]
    return ChatChunk(
        source=source,
        conversation_id=conversation_id,
        conversation_title=title,
        chunk_index=chunk_index,
        text=text,
        occurred_at_start=min(dated) if dated else None,
        occurred_at_end=max(dated) if dated else None,
        message_count=len(recs),
        content_hash=content_hash,
    )


def chunk_records(records: list[NormalizedRecord], max_chars: int = DEFAULT_MAX_CHARS) -> list[ChatChunk]:
    """Group by conversation_id (chronological within a conversation), then
    split each conversation into ~max_chars-budget chunks on message
    boundaries — never splits a single message's content (a chunk may
    exceed max_chars if one message alone is bigger; losing part of a
    message would silently drop context, which is worse than an oversized
    chunk)."""
    by_conv: dict[str, list[NormalizedRecord]] = defaultdict(list)
    for r in records:
        by_conv[r.conversation_id or "untitled"].append(r)

    chunks: list[ChatChunk] = []
    for conv_id, recs in by_conv.items():
        recs = sorted(recs, key=lambda r: r.occurred_at.isoformat() if r.occurred_at else "")
        title = recs[0].attrs.get("conversation_title") or conv_id
        source = recs[0].source

        bucket: list[NormalizedRecord] = []
        bucket_chars = 0
        idx = 0
        for r in recs:
            r_chars = len(r.content)
            if bucket and bucket_chars + r_chars > max_chars:
                chunks.append(_render_chunk(source, conv_id, title, idx, bucket))
                idx += 1
                bucket, bucket_chars = [], 0
            bucket.append(r)
            bucket_chars += r_chars
        if bucket:
            chunks.append(_render_chunk(source, conv_id, title, idx, bucket))
    return chunks


# ---------------------------------------------------------------------------
# Ledger: content-hash dedup, the ONLY thing making Graphiti writes idempotent
# ---------------------------------------------------------------------------


class IngestLedger:
    """SQLite-backed content-hash ledger. One row per chunk ever seen;
    `weaviate_written`/`graphiti_written` flags let a re-run skip exactly
    the sink(s) that already succeeded (e.g. a run that wrote Weaviate then
    crashed before Graphiti resumes cleanly on retry)."""

    def __init__(self, path: Path | str = DEFAULT_LEDGER_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_ingest_ledger (
                    content_hash TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    weaviate_written INTEGER NOT NULL DEFAULT 0,
                    graphiti_written INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.path))
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_row(self, conn: sqlite3.Connection, chunk: ChatChunk) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO context_ingest_ledger "
            "(content_hash, source, conversation_id, chunk_index) VALUES (?, ?, ?, ?)",
            (chunk.content_hash, chunk.source, chunk.conversation_id, chunk.chunk_index),
        )

    def weaviate_done(self, content_hash: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT weaviate_written FROM context_ingest_ledger WHERE content_hash = ?", (content_hash,)
            ).fetchone()
        return bool(row and row[0])

    def graphiti_done(self, content_hash: str) -> bool:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT graphiti_written FROM context_ingest_ledger WHERE content_hash = ?", (content_hash,)
            ).fetchone()
        return bool(row and row[0])

    def mark_weaviate(self, chunk: ChatChunk) -> None:
        with self._conn() as conn:
            self._ensure_row(conn, chunk)
            conn.execute(
                "UPDATE context_ingest_ledger SET weaviate_written = 1 WHERE content_hash = ?",
                (chunk.content_hash,),
            )

    def mark_graphiti(self, chunk: ChatChunk) -> None:
        with self._conn() as conn:
            self._ensure_row(conn, chunk)
            conn.execute(
                "UPDATE context_ingest_ledger SET graphiti_written = 1 WHERE content_hash = ?",
                (chunk.content_hash,),
            )


# ---------------------------------------------------------------------------
# Write: Weaviate (tier=context) + Graphiti (case lane)
# ---------------------------------------------------------------------------


def _weaviate_name(chunk: ChatChunk) -> str:
    safe_conv = "".join(c if c.isalnum() or c in "-_" else "-" for c in chunk.conversation_id)[:80] or "conv"
    return f"context-{chunk.source}-{safe_conv}-{chunk.chunk_index:04d}"


async def write_chunks_to_weaviate(
    knowledge: Any | None, chunks: list[ChatChunk], ledger: IngestLedger, *, dry_run: bool = False
) -> tuple[int, int]:
    """Returns (written, skipped_as_duplicate)."""
    written = skipped = 0
    for chunk in chunks:
        if ledger.weaviate_done(chunk.content_hash):
            skipped += 1
            continue
        if not dry_run:
            assert knowledge is not None, "knowledge must be provided when dry_run=False"
            await knowledge.ainsert(
                name=_weaviate_name(chunk),
                text_content=chunk.text,
                metadata={
                    "tier": "context",
                    "disclaimer": "unverified lead - verify against primary evidence",
                    "source": chunk.source,
                    "conversation_id": chunk.conversation_id,
                    "conversation_title": chunk.conversation_title,
                    "chunk_index": chunk.chunk_index,
                    "message_count": chunk.message_count,
                    "occurred_at_start": chunk.occurred_at_start.isoformat() if chunk.occurred_at_start else None,
                    "occurred_at_end": chunk.occurred_at_end.isoformat() if chunk.occurred_at_end else None,
                    "content_hash": chunk.content_hash,
                },
            )
            ledger.mark_weaviate(chunk)
        written += 1
    return written, skipped


def write_chunks_to_graphiti(
    chunks: list[ChatChunk], ledger: IngestLedger, client: GraphitiCaseClient | None, *, dry_run: bool = False
) -> tuple[int, int]:
    """Returns (written, skipped_as_duplicate). Case lane ONLY (never
    `evidence`, never the platform/dev graph) — see GraphitiCaseClient."""
    written = skipped = 0
    for chunk in chunks:
        if ledger.graphiti_done(chunk.content_hash):
            skipped += 1
            continue
        if not dry_run:
            assert client is not None, "client must be provided when dry_run=False"
            name = f"context-chat/{chunk.source}/{chunk.conversation_title}/chunk-{chunk.chunk_index}"[:200]
            client.add_memory(
                name=name,
                episode_body=chunk.text,
                source="text",
                source_description=(
                    f"context-chat-ingest ({chunk.source}) -- tier=context, unverified lead, "
                    "verify against primary evidence"
                ),
            )
            ledger.mark_graphiti(chunk)
        written += 1
    return written, skipped


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


@dataclass
class IngestReport:
    path: str
    parser_id: str
    parse_attempts: list[dict[str, Any]]
    record_count: int
    chunk_count: int
    weaviate_written: int
    weaviate_skipped_duplicate: int
    graphiti_written: int
    graphiti_skipped_duplicate: int
    dry_run: bool
    conversation_ids: list[str]


async def ingest_chat_file(
    path: str | Path,
    *,
    source_meta: dict[str, Any] | None = None,
    conversation_ids: set[str] | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    dry_run: bool = False,
    ledger_path: Path | str = DEFAULT_LEDGER_PATH,
    knowledge: Any | None = None,
    graphiti_client: GraphitiCaseClient | None = None,
) -> IngestReport:
    """The whole pipeline for ONE chat-export file: parse -> (optional
    conversation filter, for single-chat proof runs) -> chunk -> dual write.

    `knowledge`/`graphiti_client` are injectable for tests; when omitted and
    `dry_run=False` this constructs the real Weaviate Knowledge instance and
    the real Graphiti case-lane client (durable-infra side effects — callers
    outside tests should almost always pass `dry_run=True` first).
    """
    p = Path(path)
    records, parser_id, attempts = parse_chat_export(p, source_meta)
    records = filter_conversations(records, conversation_ids)
    records = finalize(records)
    chunks = chunk_records(records, max_chars=max_chars)
    ledger = IngestLedger(ledger_path)

    # write_chunks_to_{weaviate,graphiti} never dereference knowledge/client
    # when dry_run=True, so it's safe (and correct — dry-run counts must still
    # reflect ledger-skip state) to always call them; real clients are only
    # constructed when a live write is actually about to happen.
    if knowledge is None and not dry_run:
        knowledge = create_context_knowledge()
    w_written, w_skipped = await write_chunks_to_weaviate(knowledge, chunks, ledger, dry_run=dry_run)

    if graphiti_client is None and not dry_run:
        graphiti_client = GraphitiCaseClient()
    g_written, g_skipped = write_chunks_to_graphiti(chunks, ledger, graphiti_client, dry_run=dry_run)

    return IngestReport(
        path=str(p),
        parser_id=parser_id,
        parse_attempts=attempts,
        record_count=len(records),
        chunk_count=len(chunks),
        weaviate_written=w_written,
        weaviate_skipped_duplicate=w_skipped,
        graphiti_written=g_written,
        graphiti_skipped_duplicate=g_skipped,
        dry_run=dry_run,
        conversation_ids=sorted({r.conversation_id or "untitled" for r in records}),
    )
