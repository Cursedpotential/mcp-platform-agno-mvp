"""server/analysis/context_chat_ingest.py — the AI-chat CONTEXT ingest lane.

Owner brief (2026-08-01): ingest the owner's AI-chat exports (Claude/ChatGPT/
Perplexity/Gemini conversations about the custody case) so the platform can
surface leads worth chasing, capture stated preferences, and reconstruct
legal-strategy discussion — WITHOUT ever letting a chat be cited as proof.

ARCHITECTURE (owner ruling, 2026-08-12, verbatim): "it's all supposed to go
back into pg And then change detection will move it into vector db." This lane
is therefore **PG-first**:

    parse -> working.context_record (Postgres SOURCE OF TRUTH)
          -> change-detection -> Weaviate `platform_context` + Graphiti CASE lane

The relational rows in `working.context_record` are canonical; the Weaviate
collection and the Graphiti graph are DERIVED, rebuildable projections of them.
The `*_synced_at` columns on that table ARE the change-detection signal — NULL
means "not yet projected into that sink" — so `sync_pending_context()` is a
plain "find the pending rows, project them, stamp them" consumer. (This
replaced the pre-2026-08-12 design, which wrote chunks DIRECTLY to Weaviate +
Graphiti and deliberately never touched Postgres; the old local-SQLite
`IngestLedger` that tracked "already sent" is gone — Postgres is now that
authority, via the UNIQUE `content_hash` and the `*_synced_at` stamps.)

OPTION B (owner pick, 2026-08-12): context rows live in their OWN table
(`working.context_record`, sql/0021), NOT in `working.normalized_record`. That
separation is the CONTEXT-never-EVIDENCE boundary (owner, 2026-08-01: "AI chats
are CONTEXT, never EVIDENCE"): `normalized_record` REQUIRES a custody artifact
(`artifact_id -> evidence.evidence_hash`), and `context_record` has no evidence
FK and is referenced by no evidence surface, so a chat can never become
reachable through an evidence-only read path while PG still holds the canonical
copy. This module accordingly still does **not** import `server.evidence.*`
(server/AGENTS.md boundary: `analysis/` depends on `contracts/`, `core/`,
`tools/` only) — it reaches Postgres through `server.core.url` like every other
non-evidence writer.

Weaviate projection: agno Knowledge collection `platform_context` (a SECOND,
separate Knowledge instance from `platform_knowledge` — see
`create_context_knowledge()`), every chunk tagged `lane: context` /
`tier: context`. Graphiti projection: the CASE lane
(`server/analysis/graphiti_case_client.py`) via `add_memory` — Graphiti's own
entity/relationship/temporal extraction is the entity pipeline; this module
does not extract entities itself.

Every projected chunk (both sinks) is prefixed with `_CONTEXT_BANNER` so raw
chunk text read directly (a Weaviate search result, a Graphiti episode body)
still carries the disclaimer even outside the `tier: context` metadata —
surface as "unverified lead - verify against primary evidence", never as fact.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01
# Byline: Claude Code · Opus 4.8 · 2026-08-12 (PG-first rewrite: context_record source of truth + change-detection sync, ADR-0051 / owner ruling)

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

from server.analysis.graphiti_case_client import GraphitiCaseClient
from server.contracts.records import NormalizedRecord, finalize
from server.tools.registry import load_builtin_tools, registry

CONTEXT_KNOWLEDGE_NAME = "context"
CONTEXT_TABLE_NAME = "platform_context"
DEFAULT_MAX_CHARS = 6000

_CONTEXT_BANNER = (
    "[UNVERIFIED LEAD -- AI-chat context, not primary evidence. "
    "Verify against primary evidence before relying on this.]"
)

# The two projection sinks, matched to the `working.context_record.*_synced_at`
# columns that track them. Kept as a table so the sync consumer is generic over
# sink and a third projection later is one row, not a new code path.
_SYNC_COLUMNS = {"weaviate": "weaviate_synced_at", "graphiti": "graphiti_synced_at"}


# ---------------------------------------------------------------------------
# Postgres engine (via core.url — never evidence/, per the analysis/ boundary)
# ---------------------------------------------------------------------------

_engine = None


def _get_engine():
    """Lazily build (once) the SQLAlchemy engine for `working.context_record`.

    Uses `server.core.url.build_db_url()` — the same env-driven URL every other
    writer uses — so this lane hits the identical Postgres the evidence spine
    does, without importing `server.evidence.*` (boundary: analysis/ -> core/).
    """
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine

        from server.core.url import build_db_url

        _engine = create_engine(build_db_url(), pool_pre_ping=True)
    return _engine


# ---------------------------------------------------------------------------
# Knowledge lane (Weaviate `platform_context`, separate from `platform_knowledge`)
# ---------------------------------------------------------------------------


def create_context_knowledge():
    """A SECOND agno Knowledge instance — separate Weaviate collection
    (`platform_context`), separate Postgres contents table
    (`platform_context_contents`) — so AI-chat context never mixes with
    platform build/design docs in the same collection.

    Thin wrapper over `server.core.session.create_knowledge()`; imported lazily
    (function body, not module level) because `server.core.session` pulls in
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
    `evidence/workflows.py`'s chat-transcript workflow uses, minus the custody/
    store wiring. Returns (records, winning_tool_id, attempts_log). Raises
    ValueError if every candidate rejects the file.
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
    """Restrict to specific conversation_id(s) — used for the single-chat proof
    run so a giant multi-conversation export doesn't get bulk-written just to
    prove the pipeline on ONE small chat."""
    if conversation_ids is None:
        return records
    return [r for r in records if (r.conversation_id or "") in conversation_ids]


# ---------------------------------------------------------------------------
# PG write: working.context_record is the SOURCE OF TRUTH (owner ruling)
# ---------------------------------------------------------------------------


def _record_content_hash(rec: NormalizedRecord) -> str:
    """Record-grain dedup key. Deterministic over the fields that make a
    message identity: source, conversation, role, valid-time, content. Backs
    the UNIQUE constraint so re-ingesting the same export is a no-op INSERT."""
    occurred = rec.occurred_at.isoformat() if rec.occurred_at else ""
    basis = f"{rec.source}:{rec.conversation_id or ''}:{rec.role or ''}:{occurred}:{rec.content}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def store_context_records(records: list[NormalizedRecord]) -> int:
    """Write canonical records into `working.context_record` (PG source of
    truth), one row per message. Idempotent: `ON CONFLICT (content_hash) DO
    NOTHING`, so re-running a parse never double-writes. Returns the number of
    rows actually inserted (conflicts excluded). New rows land with both
    `*_synced_at` NULL — i.e. pending projection — which is exactly what
    `sync_pending_context()` picks up.
    """
    if not records:
        return 0
    rows = [
        {
            "record_type": r.record_type.value,
            "source": r.source,
            "conversation_id": r.conversation_id,
            "conversation_title": r.attrs.get("conversation_title"),
            "role": r.role,
            "participants": json.dumps(r.participants),
            "content": r.content,
            "occurred_at": r.occurred_at,
            "knowledge_time": r.knowledge_time,
            "disclosure_tier": r.disclosure_tier.value,
            "content_hash": _record_content_hash(r),
            "attrs": json.dumps(r.attrs),
        }
        for r in records
    ]
    with _get_engine().begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO working.context_record "
                "(record_type, source, conversation_id, conversation_title, role, participants, "
                " content, occurred_at, knowledge_time, disclosure_tier, content_hash, attrs) "
                "VALUES (:record_type, :source, :conversation_id, :conversation_title, :role, "
                " CAST(:participants AS jsonb), :content, :occurred_at, :knowledge_time, "
                " :disclosure_tier, :content_hash, CAST(:attrs AS jsonb)) "
                "ON CONFLICT (content_hash) DO NOTHING"
            ),
            rows,
        )
    # rowcount reflects rows actually inserted for a multi-values INSERT with
    # ON CONFLICT DO NOTHING (psycopg reports affected rows); fall back to len
    # if the driver returns -1 (unknown).
    inserted = result.rowcount if result.rowcount is not None and result.rowcount >= 0 else len(rows)
    return inserted


# ---------------------------------------------------------------------------
# Change-detection read side: pending rows -> (id, record) pairs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PendingRecord:
    """One `working.context_record` row awaiting projection into a sink —
    the record plus the PK needed to stamp it `*_synced_at` afterward."""

    id: str
    record: NormalizedRecord


def load_pending_context(sink: str) -> list[PendingRecord]:
    """Load the rows still pending projection into `sink` ('weaviate' |
    'graphiti') — the change-detection query. Ordered by conversation then
    valid-time so chunking sees each conversation contiguous and chronological
    (NULLS LAST — undated records sort after dated ones, matching the pure-path
    `chunk_records` sort)."""
    col = _SYNC_COLUMNS[sink]
    with _get_engine().connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT id, record_type, source, conversation_id, conversation_title, role, "
                    "participants, content, occurred_at, knowledge_time, disclosure_tier, attrs "
                    f"FROM working.context_record WHERE {col} IS NULL "
                    "ORDER BY conversation_id NULLS LAST, occurred_at NULLS LAST"
                )
            )
            .mappings()
            .all()
        )

    pending: list[PendingRecord] = []
    for row in rows:
        participants = row["participants"]
        if isinstance(participants, str):
            participants = json.loads(participants)
        attrs = row["attrs"]
        if isinstance(attrs, str):
            attrs = json.loads(attrs)
        pending.append(
            PendingRecord(
                id=str(row["id"]),
                record=NormalizedRecord(
                    record_type=row["record_type"],
                    source=row["source"],
                    conversation_id=row["conversation_id"],
                    role=row["role"],
                    participants=participants or [],
                    content=row["content"] or "",
                    occurred_at=row["occurred_at"],
                    knowledge_time=row["knowledge_time"],
                    disclosure_tier=row["disclosure_tier"],
                    attrs={**(attrs or {}), "conversation_title": row["conversation_title"]}
                    if row["conversation_title"]
                    else (attrs or {}),
                ),
            )
        )
    return pending


def mark_synced(sink: str, ids: list[str]) -> None:
    """Stamp `<sink>_synced_at = now()` on the given rows — the projection is
    done for that sink. Only stamps rows still NULL (a concurrent re-run can't
    move the timestamp backward)."""
    if not ids:
        return
    col = _SYNC_COLUMNS[sink]
    with _get_engine().begin() as conn:
        conn.execute(
            text(
                f"UPDATE working.context_record SET {col} = NOW() "
                f"WHERE id = ANY(CAST(:ids AS uuid[])) AND {col} IS NULL"
            ),
            {"ids": "{" + ",".join(ids) + "}"},
        )


# ---------------------------------------------------------------------------
# Chunk: group by conversation, render, hash (a property of PROJECTION, not
# of the relational source of truth — the DB stores records, we chunk on read)
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
    record_ids: tuple[str, ...] = field(default=(), compare=False)


def _render_chunk(
    source: str,
    conversation_id: str,
    title: str,
    chunk_index: int,
    recs: list[NormalizedRecord],
    record_ids: tuple[str, ...] = (),
) -> ChatChunk:
    lines = [_CONTEXT_BANNER, "", f"# {title} (part {chunk_index + 1})", ""]
    for r in recs:
        stamp = f" — {r.occurred_at.isoformat()}" if r.occurred_at else ""
        lines += [f"**{(r.role or 'unknown').upper()}{stamp}:**", "", r.content, "", "---", ""]
    text_body = "\n".join(lines)
    content_hash = hashlib.sha256(f"{source}:{conversation_id}:{chunk_index}:{text_body}".encode("utf-8")).hexdigest()
    dated = [r.occurred_at for r in recs if r.occurred_at is not None]
    return ChatChunk(
        source=source,
        conversation_id=conversation_id,
        conversation_title=title,
        chunk_index=chunk_index,
        text=text_body,
        occurred_at_start=min(dated) if dated else None,
        occurred_at_end=max(dated) if dated else None,
        message_count=len(recs),
        content_hash=content_hash,
        record_ids=record_ids,
    )


def _chunk_pending(items: list[PendingRecord], max_chars: int = DEFAULT_MAX_CHARS) -> list[ChatChunk]:
    """Group PendingRecords by conversation (chronological within), split each
    conversation into ~max_chars chunks on message boundaries, and carry the
    source-row ids into each chunk (so the sync step can stamp exactly the rows
    it projected). Never splits a single message's content."""
    by_conv: dict[str, list[PendingRecord]] = defaultdict(list)
    for it in items:
        by_conv[it.record.conversation_id or "untitled"].append(it)

    chunks: list[ChatChunk] = []
    for conv_id, conv_items in by_conv.items():
        conv_items = sorted(
            conv_items, key=lambda it: it.record.occurred_at.isoformat() if it.record.occurred_at else ""
        )
        title = conv_items[0].record.attrs.get("conversation_title") or conv_id
        source = conv_items[0].record.source

        bucket: list[NormalizedRecord] = []
        bucket_ids: list[str] = []
        bucket_chars = 0
        idx = 0
        for it in conv_items:
            r_chars = len(it.record.content)
            if bucket and bucket_chars + r_chars > max_chars:
                chunks.append(_render_chunk(source, conv_id, title, idx, bucket, tuple(bucket_ids)))
                idx += 1
                bucket, bucket_ids, bucket_chars = [], [], 0
            bucket.append(it.record)
            bucket_ids.append(it.id)
            bucket_chars += r_chars
        if bucket:
            chunks.append(_render_chunk(source, conv_id, title, idx, bucket, tuple(bucket_ids)))
    return chunks


def chunk_records(records: list[NormalizedRecord], max_chars: int = DEFAULT_MAX_CHARS) -> list[ChatChunk]:
    """Pure-path chunker (no PG): same bucketing as `_chunk_pending`, for
    callers/tests that hold in-memory records with no row ids. Delegates so the
    grouping logic lives in exactly one place."""
    return _chunk_pending([PendingRecord(id="", record=r) for r in records], max_chars=max_chars)


# ---------------------------------------------------------------------------
# Projection: write chunks to a sink, then stamp their source rows synced
# ---------------------------------------------------------------------------


def _weaviate_name(chunk: ChatChunk) -> str:
    safe_conv = "".join(c if c.isalnum() or c in "-_" else "-" for c in chunk.conversation_id)[:80] or "conv"
    return f"context-{chunk.source}-{safe_conv}-{chunk.chunk_index:04d}"


async def _project_chunk_to_weaviate(knowledge: Any, chunk: ChatChunk) -> None:
    await knowledge.ainsert(
        name=_weaviate_name(chunk),
        text_content=chunk.text,
        metadata={
            "lane": "context",  # ADR-0050 §3 unified vocabulary
            "doc_type": "chat",
            "case_id": "primary",
            "tier": "context",  # legacy key retained — docs/filters reference it
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


def _project_chunk_to_graphiti(client: GraphitiCaseClient, chunk: ChatChunk) -> None:
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


async def sync_pending_context(
    sink: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    dry_run: bool = False,
    knowledge: Any | None = None,
    graphiti_client: GraphitiCaseClient | None = None,
) -> tuple[int, int]:
    """The change-detection consumer for ONE sink ('weaviate' | 'graphiti'):
    load rows from `working.context_record` whose `<sink>_synced_at IS NULL`,
    chunk per conversation, project each chunk into the sink, and stamp the
    source rows synced. Returns (chunks_projected, records_stamped).

    Decoupled by design: this reads pending state from Postgres, so it runs
    equally well inline after an ingest OR as an independent worker/cron later
    — no ingest call is required for it to have work to do. `dry_run=True`
    counts what WOULD project without touching the sink or stamping rows.
    `knowledge`/`graphiti_client` are injectable for tests; when omitted and
    not dry-run they are constructed lazily (durable-infra side effects).
    """
    if sink not in _SYNC_COLUMNS:
        raise ValueError(f"unknown sink {sink!r} (expected one of {sorted(_SYNC_COLUMNS)})")

    pending = load_pending_context(sink)
    chunks = _chunk_pending(pending, max_chars=max_chars)
    if dry_run:
        return len(chunks), sum(len(c.record_ids) for c in chunks)

    chunks_done = records_stamped = 0
    if sink == "weaviate":
        if knowledge is None:
            knowledge = create_context_knowledge()
        for chunk in chunks:
            await _project_chunk_to_weaviate(knowledge, chunk)
            mark_synced("weaviate", list(chunk.record_ids))
            chunks_done += 1
            records_stamped += len(chunk.record_ids)
    else:  # graphiti
        if graphiti_client is None:
            graphiti_client = GraphitiCaseClient()
        for chunk in chunks:
            _project_chunk_to_graphiti(graphiti_client, chunk)
            mark_synced("graphiti", list(chunk.record_ids))
            chunks_done += 1
            records_stamped += len(chunk.record_ids)
    return chunks_done, records_stamped


# ---------------------------------------------------------------------------
# Orchestrator: parse -> PG (source of truth) -> change-detection projection
# ---------------------------------------------------------------------------


@dataclass
class IngestReport:
    path: str
    parser_id: str
    parse_attempts: list[dict[str, Any]]
    record_count: int
    records_stored: int
    weaviate_chunks: int
    weaviate_records_synced: int
    graphiti_chunks: int
    graphiti_records_synced: int
    dry_run: bool
    conversation_ids: list[str]


async def ingest_chat_file(
    path: str | Path,
    *,
    source_meta: dict[str, Any] | None = None,
    conversation_ids: set[str] | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    dry_run: bool = False,
    project: bool = True,
    knowledge: Any | None = None,
    graphiti_client: GraphitiCaseClient | None = None,
) -> IngestReport:
    """The whole pipeline for ONE chat-export file, PG-first:

        parse -> (optional conversation filter) -> finalize
              -> store_context_records()   [Postgres SOURCE OF TRUTH]
              -> sync_pending_context('weaviate' / 'graphiti')   [projection]

    The projection step reads PENDING rows from Postgres, so it naturally
    projects anything left pending by a prior crashed run too, not only this
    file's rows — that is the change-detection contract, not a quirk. Pass
    `project=False` to write Postgres only and let a separate worker drain the
    projections. `dry_run=True` stores nothing and only counts.
    """
    p = Path(path)
    records, parser_id, attempts = parse_chat_export(p, source_meta)
    records = filter_conversations(records, conversation_ids)
    records = finalize(records)

    w_chunks = w_synced = g_chunks = g_synced = 0

    if dry_run:
        # Preview THIS file's own records (nothing is written, so reading
        # "pending" back from PG would reflect unrelated pre-existing rows).
        records_stored = 0
        preview = chunk_records(records, max_chars=max_chars)
        if project:
            w_chunks = g_chunks = len(preview)
            w_synced = g_synced = len(records)
    else:
        records_stored = store_context_records(records)
        if project:
            w_chunks, w_synced = await sync_pending_context("weaviate", max_chars=max_chars, knowledge=knowledge)
            g_chunks, g_synced = await sync_pending_context(
                "graphiti", max_chars=max_chars, graphiti_client=graphiti_client
            )

    return IngestReport(
        path=str(p),
        parser_id=parser_id,
        parse_attempts=attempts,
        record_count=len(records),
        records_stored=records_stored,
        weaviate_chunks=w_chunks,
        weaviate_records_synced=w_synced,
        graphiti_chunks=g_chunks,
        graphiti_records_synced=g_synced,
        dry_run=dry_run,
        conversation_ids=sorted({r.conversation_id or "untitled" for r in records}),
    )
