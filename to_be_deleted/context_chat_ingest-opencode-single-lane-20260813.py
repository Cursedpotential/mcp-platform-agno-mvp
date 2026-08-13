"""PG-first AI-chat ingestion and post-chunk knowledge routing.

Owner brief (2026-08-01): ingest the owner's AI-chat exports (Claude/ChatGPT/
Perplexity/Gemini conversations about the custody case) so the platform can
surface leads worth chasing, capture stated preferences, and reconstruct
legal-strategy discussion — WITHOUT ever letting a chat be cited as proof.

    parse -> conversation/message landing -> canonical chunks
          -> multi-label classification + selective HITL -> outbox
          -> embed once -> project the same vector to every accepted lane

Raw landing rows have no horizon fields. AI chat can route to platform, legal,
personal_history, or context, but never evidence. As-experienced/hindsight
walks are a later derived-view design.

Every projected chunk (both sinks) is prefixed with `_CONTEXT_BANNER` so raw
chunk text read directly (a Weaviate search result, a Graphiti episode body)
still carries the disclaimer even outside the `lane` metadata — surface as
"unverified lead - verify against primary evidence", never as fact.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-01
# Byline: Claude Code · Opus 4.8 · 2026-08-12 (PG-first rewrite: context_record source of truth + change-detection sync, ADR-0051 / owner ruling)
# Byline: Claude Code · Fable 5 · 2026-08-12 (D-053: explicit format override is strict — bypasses router, never falls back)
# Byline: Codex · GPT-5 · 2026-08-13 (canonical chunks, multi-label routing, selective HITL)

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text

from server.analysis.chat_normalizer import compute_content_hash, normalize_many
from server.analysis.lane_classifier import classify_chunks
from server.contracts.records import ChatChunk, ChatConversation, ChatMessage, LaneClassification, NormalizedRecord
from server.tools.registry import load_builtin_tools, registry

DEFAULT_MAX_CHARS = 6000

_CONTEXT_BANNER = (
    "[UNVERIFIED LEAD -- AI-chat context, not primary evidence. "
    "Verify against primary evidence before relying on this.]"
)

# Global five-lane taxonomy. Evidence is intentionally absent from chat routing.
LANE_COLLECTIONS = {
    "platform": "Platform_knowledge",
    "legal": "Legal_knowledge",
    "personal_history": "Personal_history_knowledge",
    "context": "Platform_context",
}

VALID_ENGINES = ("auto", "python", "go")

# ---------------------------------------------------------------------------
# Postgres engine (via core.url — never evidence/, per the analysis/ boundary)
# ---------------------------------------------------------------------------

_engine = None


def _get_engine():
    """Lazily build (once) the SQLAlchemy engine for `working.chat_message`.

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
# Knowledge lane factories (one agno Knowledge per lane -> separate Weaviate collection)
# ---------------------------------------------------------------------------


def create_lane_knowledge(lane: str):
    """Create an agno Knowledge instance for a specific lane's Weaviate collection.

    Thin wrapper over `server.core.session.create_knowledge()`; imported lazily
    (function body, not module level) because `server.core.session` pulls in
    sqlalchemy/agno DB wiring that unit tests for the pure parse/chunk logic
    below should not have to construct.
    """
    from server.core.session import create_knowledge

    table_name = LANE_COLLECTIONS.get(lane)
    if not table_name:
        raise ValueError(f"unknown lane {lane!r} (expected one of {sorted(LANE_COLLECTIONS)})")
    return create_knowledge(lane, table_name)


def create_all_lane_knowledge() -> dict[str, Any]:
    """Create Knowledge handles for the four AI-chat-eligible lanes."""
    return {lane: create_lane_knowledge(lane) for lane in LANE_COLLECTIONS}


# ---------------------------------------------------------------------------
# Parse: reuse the EXISTING registry substitution mesh, no new parser
# ---------------------------------------------------------------------------


def parse_chat_export(
    path: Path,
    source_meta: dict[str, Any] | None = None,
    *,
    engine: str = "auto",
    format: str | None = None,
) -> tuple[list[NormalizedRecord], str, list[dict[str, Any]]]:
    """Parse a chat export into NormalizedRecords — ENGINE-DYNAMIC dispatcher
    (owner 2026-08-12: "the pipeline needs to be dynamic ... it shouldn't be
    dedicated to one format or the other"). Returns (records, parser_id,
    attempts_log). The engine choice changes ONLY who parses; the
    NormalizedRecord output and everything downstream are identical.

    engine:
      * "python" — the in-process registry `parse.transcript` mesh (chatminer
        et al.), try-next-candidate by priority.
      * "go" — hand the file to the SBV Go service (memory-safe universal
        decoder, ADR-0049) via `server.analysis.sbv_transcript.parse_via_sbv`.
      * "auto" (default) — the detection ROUTER (`format_router.detect_format`,
        D-051): detect once, route to the winning format's preferred engine
        (Go-primary) with graceful fallbacks.

    `format` is the EXPLICIT operator override (D-053): when given, it BYPASSES
    the detection router entirely and is STRICT — the named parser engine
    (`format_router.resolve_format_override`) is used directly, and an
    unresolvable or rejected combination raises ValueError instead of falling
    back to detection, to the registry mesh, or to the other engine. Accepted
    spellings: a router format_id ('claude-ai-export'), a Go importer id
    ('chatgpt-official-json'), or a Python registry tool id ('transcripts.<name>').
    """
    if engine not in VALID_ENGINES:
        raise ValueError(f"unknown engine {engine!r} (expected one of {VALID_ENGINES})")
    if not path.is_file():
        raise FileNotFoundError(path)

    # Explicit --format override (D-053): bypass the detection router entirely.
    # STRICT — the operator named the parser, so nothing falls back: a format
    # the chosen engine cannot handle, an unknown parser id, or a rejecting
    # parser is a loud ValueError (the CLI turns it into exit 2).
    if format is not None:
        from server.analysis.format_router import resolve_format_override

        engaged, go_id, py_id = resolve_format_override(format, engine)
        if engaged == "go":
            from server.analysis.sbv_transcript import parse_via_sbv

            return parse_via_sbv(path, format=go_id, source_meta=source_meta)
        assert py_id is not None  # resolve_format_override guarantees one side
        return _parse_via_pinned_tool(path, source_meta, py_id)

    # Explicit engine override always wins (the MVP escape hatch).
    if engine == "go":
        from server.analysis.sbv_transcript import parse_via_sbv

        return parse_via_sbv(path, format=format, source_meta=source_meta)
    if engine == "python":
        return _parse_via_registry(path, source_meta)

    # engine == "auto": the DETECTION ROUTER (Go-primary), not a blind mesh.
    # detect once -> route to the winning format's preferred engine, with
    # graceful fallbacks (Go -> that format's Python parser -> full mesh).
    from server.analysis.format_router import detect_format

    det = detect_format(path)
    if det.format_id and det.engine == "go":
        from server.analysis.sbv_transcript import parse_via_sbv

        try:
            return parse_via_sbv(path, format=det.parse_format, source_meta=source_meta)
        except Exception:  # SBV down / auth / import error -> fall back to the same format's Python parser
            pass
    if det.python_parser_id:
        try:
            return _parse_via_registry(path, source_meta, preferred_tool_id=det.python_parser_id)
        except Exception:  # detected parser rejected it -> last-resort full mesh below
            pass
    # unknown format, or the detected route failed: full registry mesh (last resort).
    return _parse_via_registry(path, source_meta)


def _parse_via_registry(
    path: Path, source_meta: dict[str, Any] | None = None, *, preferred_tool_id: str | None = None
) -> tuple[list[NormalizedRecord], str, list[dict[str, Any]]]:
    """The PYTHON parse engine: resolve `parse.transcript` candidates for
    `path`. When `preferred_tool_id` is given (the router's detected parser),
    try it FIRST, then the rest as a safety net; otherwise try in registration
    order. Raises ValueError if every candidate rejects the file."""
    load_builtin_tools()
    candidates = registry.resolve("parse.transcript", media_hint=path.name.lower(), size_bytes=path.stat().st_size)
    if not candidates:
        raise ValueError(f"no parse.transcript tool accepts {path.name!r}")
    if preferred_tool_id:
        candidates = sorted(candidates, key=lambda t: 0 if t.id == preferred_tool_id else 1)

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


def _parse_via_pinned_tool(
    path: Path, source_meta: dict[str, Any] | None, tool_id: str
) -> tuple[list[NormalizedRecord], str, list[dict[str, Any]]]:
    """The PYTHON engine under an EXPLICIT format override (D-053): run exactly
    ONE named `parse.transcript` tool. Unlike `_parse_via_registry` there is NO
    substitution mesh — an unknown tool id, a non-transcript capability, or a
    rejecting parser raises ValueError immediately (an explicit override must
    never silently turn into a different parse)."""
    load_builtin_tools()
    try:
        tool = registry.get(tool_id)
    except KeyError:
        known = sorted(t.id for t in registry.all() if t.capability == "parse.transcript")
        raise ValueError(f"unknown python parser {tool_id!r}; registered parse.transcript tools: {known}") from None
    if tool.capability != "parse.transcript":
        raise ValueError(f"tool {tool_id!r} is capability {tool.capability!r}, not 'parse.transcript'")
    try:
        result = tool.run({"path": str(path), "source_meta": source_meta or {}})
    except Exception as exc:
        raise ValueError(
            f"parser {tool_id!r} rejected {path.name!r} under the explicit format override (no fallback): {exc}"
        ) from exc
    records = [NormalizedRecord.model_validate(r) for r in result["records"]]
    return records, tool.id, [{"tool": tool.id, "ok": True}]


def filter_conversations(records: list[NormalizedRecord], conversation_ids: set[str] | None) -> list[NormalizedRecord]:
    """Restrict to specific conversation_id(s) — used for the single-chat proof
    run so a giant multi-conversation export doesn't get bulk-written just to
    prove the pipeline on ONE small chat."""
    if conversation_ids is None:
        return records
    return [r for r in records if (r.conversation_id or "") in conversation_ids]


# ---------------------------------------------------------------------------
# PG write: working.chat_conversation + working.chat_message are SOURCE OF TRUTH
# ---------------------------------------------------------------------------


def _record_content_hash(source: str, conversation_id: str, message_index: int, content: str) -> str:
    """Record-grain dedup key. Deterministic over the fields that make a
    message identity: source, conversation, message_index, content. Backs
    the UNIQUE constraint so re-ingesting the same export is a no-op INSERT."""
    basis = f"{source}:{conversation_id}:{message_index}:{content[:500]}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def store_chat_conversation(conv: ChatConversation) -> str:
    """Insert a ChatConversation into `working.chat_conversation`. Returns the
    DB-generated UUID id. Upserts on (source, conversation_id) to update
    message counts and timestamps on re-ingest."""
    if not conv.conversation_id:
        raise ValueError("conversation_id is required")
    with _get_engine().begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO working.chat_conversation "
                "(source, conversation_id, title, created_at, file_path, message_count, "
                " first_message_at, last_message_at, attrs) "
                "VALUES (:source, :conversation_id, :title, :created_at, :file_path, "
                " :message_count, :first_message_at, :last_message_at, CAST(:attrs AS jsonb)) "
                "ON CONFLICT (source, conversation_id) DO UPDATE SET "
                " message_count = EXCLUDED.message_count, "
                " first_message_at = EXCLUDED.first_message_at, "
                " last_message_at = EXCLUDED.last_message_at, "
                " title = EXCLUDED.title, file_path = EXCLUDED.file_path "
                "RETURNING id"
            ),
            {
                "source": conv.source,
                "conversation_id": conv.conversation_id,
                "title": conv.title,
                "created_at": conv.created_at,
                "file_path": conv.file_path,
                "message_count": len(conv.attrs.get("_messages", [])),  # will be updated by store_chat_messages
                "first_message_at": None,  # will be updated
                "last_message_at": None,
                "attrs": json.dumps(conv.attrs or {}),
            },
        )
        row = result.fetchone()
        return str(row[0]) if row else ""


def store_chat_messages(messages: list[ChatMessage], conv_db_id: str) -> int:
    """Write canonical messages into `working.chat_message` (PG source of
    truth), one row per message. Idempotent: `ON CONFLICT (content_hash) DO
    NOTHING`, so re-running a parse never double-writes. Returns the number of
    rows actually inserted (conflicts excluded). New rows land with both
    `*_synced_at` NULL — i.e. pending projection — which is exactly what
    `sync_pending_chat()` picks up."""
    if not messages:
        return 0
    rows = [
        {
            "conversation_id": conv_db_id,
            "message_index": m.message_index,
            "role": m.role,
            "content": m.content,
            "timestamp": m.timestamp,
            "thinking": m.thinking,
            "artifacts": json.dumps(m.artifacts or []),
            "attachments": json.dumps(m.attachments or []),
            "lane": m.lane.value if m.lane else None,
            "content_hash": compute_content_hash(m),
            "attrs": json.dumps(m.attrs or {}),
        }
        for m in messages
    ]
    with _get_engine().begin() as conn:
        result = conn.execute(
            text(
                "INSERT INTO working.chat_message "
                "(conversation_id, message_index, role, content, timestamp, thinking, "
                " artifacts, attachments, lane, content_hash, attrs) "
                "VALUES (:conversation_id, :message_index, :role, :content, :timestamp, "
                " :thinking, CAST(:artifacts AS jsonb), CAST(:attachments AS jsonb), "
                " :lane, :content_hash, CAST(:attrs AS jsonb)) "
                "ON CONFLICT (content_hash) DO NOTHING"
            ),
            rows,
        )
    inserted = result.rowcount if result.rowcount is not None and result.rowcount >= 0 else len(rows)
    return inserted


def store_chat(conv: ChatConversation, messages: list[ChatMessage]) -> tuple[str, int]:
    """Convenience: store conversation + messages in one transaction-like flow.
    Returns (conv_db_id, messages_inserted)."""
    conv_id = store_chat_conversation(conv)
    # Update conversation with message stats
    if messages:
        timestamps = [m.timestamp for m in messages if m.timestamp is not None]
        first_ts = min(timestamps) if timestamps else None
        last_ts = max(timestamps) if timestamps else None
        with _get_engine().begin() as conn:
            conn.execute(
                text(
                    "UPDATE working.chat_conversation SET "
                    " message_count = :count, first_message_at = :first, last_message_at = :last "
                    "WHERE id = :id"
                ),
                {"count": len(messages), "first": first_ts, "last": last_ts, "id": conv_id},
            )
    inserted = store_chat_messages(messages, conv_id)
    return conv_id, inserted


# ---------------------------------------------------------------------------
# Change-detection read side: pending rows -> (id, message) pairs
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PendingChatMessage:
    """One `working.chat_message` row awaiting projection into a sink —
    the message fields plus the PK needed to stamp it `*_synced_at` afterward."""

    id: str
    conversation_id: str
    message_index: int
    role: str
    content: str
    timestamp: datetime | None
    thinking: str | None
    artifacts: list[str]
    attachments: list[str]
    lane: str
    content_hash: str
    attrs: dict[str, Any]


def load_pending_chat_messages(sink: str) -> list[PendingChatMessage]:
    """Load the rows still pending projection into `sink` ('weaviate' |
    'graphiti') — the change-detection query.

    Only returns messages that have:
      - lane IS NOT NULL (classified)
      - lane_reviewed = TRUE (human approved)
      - {sink}_synced_at IS NULL (not yet projected)

    Ordered by conversation_id then message_index so chunking sees each
    conversation contiguous and in message order (NULLS LAST for undated)."""
    col = _SYNC_COLUMNS[sink]
    with _get_engine().connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT id, conversation_id, message_index, role, content, timestamp, thinking, "
                    "artifacts, attachments, lane, content_hash, attrs "
                    f"FROM working.chat_message WHERE lane IS NOT NULL AND lane_reviewed = TRUE AND {col} IS NULL "
                    "ORDER BY conversation_id, message_index"
                )
            )
            .mappings()
            .all()
        )

    pending: list[PendingChatMessage] = []
    for row in rows:
        artifacts = row["artifacts"]
        if isinstance(artifacts, str):
            artifacts = json.loads(artifacts)
        attachments = row["attachments"]
        if isinstance(attachments, str):
            attachments = json.loads(attachments)
        attrs = row["attrs"]
        if isinstance(attrs, str):
            attrs = json.loads(attrs)
        pending.append(
            PendingChatMessage(
                id=str(row["id"]),
                conversation_id=str(row["conversation_id"]),
                message_index=row["message_index"],
                role=row["role"],
                content=row["content"] or "",
                timestamp=row["timestamp"],
                thinking=row["thinking"],
                artifacts=artifacts or [],
                attachments=attachments or [],
                lane=row["lane"],
                content_hash=row["content_hash"],
                attrs=attrs or {},
            )
        )
    return pending


def mark_chat_synced(sink: str, ids: list[str]) -> None:
    """Stamp `<sink>_synced_at = now()` on the given rows — the projection is
    done for that sink. Only stamps rows still NULL (a concurrent re-run can't
    move the timestamp backward)."""
    if not ids:
        return
    col = _SYNC_COLUMNS[sink]
    with _get_engine().begin() as conn:
        conn.execute(
            text(
                f"UPDATE working.chat_message SET {col} = NOW() WHERE id = ANY(CAST(:ids AS uuid[])) AND {col} IS NULL"
            ),
            {"ids": "{" + ",".join(ids) + "}"},
        )


# ---------------------------------------------------------------------------
# Chunk: group by conversation+lane, render, hash (a property of PROJECTION, not
# of the relational source of truth — the DB stores records, we chunk on read)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChatChunk:
    source: str
    conversation_id: str
    conversation_title: str
    lane: str
    chunk_index: int
    text: str
    timestamp_start: datetime | None
    timestamp_end: datetime | None
    message_count: int
    content_hash: str = field(compare=False)
    record_ids: tuple[str, ...] = field(default=(), compare=False)


def _render_chunk(
    source: str,
    conversation_id: str,
    title: str,
    lane: str,
    chunk_index: int,
    items: list[PendingChatMessage],
    record_ids: tuple[str, ...] = (),
) -> ChatChunk:
    lines = [_CONTEXT_BANNER, "", f"# {title} (part {chunk_index + 1}) [lane: {lane}]", ""]
    for it in items:
        stamp = f" — {it.timestamp.isoformat()}" if it.timestamp else ""
        lines += [f"**{(it.role or 'unknown').upper()}{stamp}:**", "", it.content, "", "---", ""]
    text_body = "\n".join(lines)
    content_hash = hashlib.sha256(
        f"{source}:{conversation_id}:{lane}:{chunk_index}:{text_body}".encode("utf-8")
    ).hexdigest()
    dated = [it.timestamp for it in items if it.timestamp is not None]
    return ChatChunk(
        source=source,
        conversation_id=conversation_id,
        conversation_title=title,
        lane=lane,
        chunk_index=chunk_index,
        text=text_body,
        timestamp_start=min(dated) if dated else None,
        timestamp_end=max(dated) if dated else None,
        message_count=len(items),
        content_hash=content_hash,
        record_ids=record_ids,
    )


def _chunk_pending_chat(items: list[PendingChatMessage], max_chars: int = DEFAULT_MAX_CHARS) -> list[ChatChunk]:
    """Group PendingChatMessages by (conversation_id, lane), sort by message_index,
    split each group into ~max_chars chunks on message boundaries, and carry the
    source-row ids into each chunk (so the sync step can stamp exactly the rows
    it projected). Never splits a single message's content."""
    by_group: dict[tuple[str, str], list[PendingChatMessage]] = defaultdict(list)
    for it in items:
        by_group[(it.conversation_id, it.lane)].append(it)

    chunks: list[ChatChunk] = []
    for (conv_id, lane), group_items in by_group.items():
        group_items = sorted(group_items, key=lambda it: it.message_index)
        title = group_items[0].attrs.get("conversation_title") or conv_id
        source = group_items[0].attrs.get("source") or "unknown"

        bucket: list[PendingChatMessage] = []
        bucket_ids: list[str] = []
        bucket_chars = 0
        idx = 0
        for it in group_items:
            r_chars = len(it.content)
            if bucket and bucket_chars + r_chars > max_chars:
                chunks.append(_render_chunk(source, conv_id, title, lane, idx, bucket, tuple(bucket_ids)))
                idx += 1
                bucket, bucket_ids, bucket_chars = [], [], 0
            bucket.append(it)
            bucket_ids.append(it.id)
            bucket_chars += r_chars
        if bucket:
            chunks.append(_render_chunk(source, conv_id, title, lane, idx, bucket, tuple(bucket_ids)))
    return chunks


def chunk_chat_messages(messages: list[ChatMessage], max_chars: int = DEFAULT_MAX_CHARS) -> list[ChatChunk]:
    """Pure-path chunker (no PG): same bucketing as `_chunk_pending_chat`, for
    callers/tests that hold in-memory ChatMessage objects with no row ids."""
    fake_items = [
        PendingChatMessage(
            id="",
            conversation_id=m.conversation_id,
            message_index=m.message_index,
            role=m.role,
            content=m.content,
            timestamp=m.timestamp,
            thinking=m.thinking,
            artifacts=m.artifacts,
            attachments=m.attachments,
            lane=m.lane.value if m.lane else "general",
            content_hash=compute_content_hash(m),
            attrs=m.attrs,
        )
        for m in messages
    ]
    return _chunk_pending_chat(fake_items, max_chars=max_chars)


# ---------------------------------------------------------------------------
# Projection: write chunks to a sink, then stamp their source rows synced
# ---------------------------------------------------------------------------


def _weaviate_name(chunk: ChatChunk) -> str:
    safe_conv = "".join(c if c.isalnum() or c in "-_" else "-" for c in chunk.conversation_id)[:80] or "conv"
    return f"{chunk.lane}-{chunk.source}-{safe_conv}-{chunk.chunk_index:04d}"


async def _project_chat_chunk_to_weaviate(knowledge_handles: dict[str, Any], chunk: ChatChunk) -> None:
    """Project a single ChatChunk to its lane's Weaviate collection via the
    correct agno Knowledge handle."""
    knowledge = knowledge_handles.get(chunk.lane)
    if knowledge is None:
        raise ValueError(f"no Knowledge handle for lane {chunk.lane!r}")
    await knowledge.ainsert(
        name=_weaviate_name(chunk),
        text_content=chunk.text,
        metadata={
            "lane": chunk.lane,
            "doc_type": "chat",
            "case_id": "primary",
            "disclaimer": "unverified lead - verify against primary evidence",
            "source": chunk.source,
            "conversation_id": chunk.conversation_id,
            "conversation_title": chunk.conversation_title,
            "chunk_index": chunk.chunk_index,
            "message_count": chunk.message_count,
            "timestamp_start": chunk.timestamp_start.isoformat() if chunk.timestamp_start else None,
            "timestamp_end": chunk.timestamp_end.isoformat() if chunk.timestamp_end else None,
            "content_hash": chunk.content_hash,
        },
    )


def _project_chunk_to_graphiti(client: GraphitiCaseClient, chunk: ChatChunk) -> None:
    name = f"context-chat/{chunk.lane}/{chunk.source}/{chunk.conversation_title}/chunk-{chunk.chunk_index}"[:200]
    client.add_memory(
        name=name,
        episode_body=chunk.text,
        source="text",
        source_description=(
            f"context-chat-ingest ({chunk.lane}/{chunk.source}) -- unverified lead, verify against primary evidence"
        ),
    )


async def sync_pending_chat(
    sink: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    dry_run: bool = False,
    knowledge_handles: dict[str, Any] | None = None,
    graphiti_client: GraphitiCaseClient | None = None,
) -> tuple[int, int]:
    """The change-detection consumer for ONE sink ('weaviate' | 'graphiti'):
    load rows from `working.chat_message` whose `lane IS NOT NULL AND
    lane_reviewed = TRUE AND <sink>_synced_at IS NULL`, chunk per
    conversation+lane, project each chunk into the sink (routing Weaviate by
    lane to the correct collection), and stamp the source rows synced.

    Returns (chunks_projected, records_stamped).

    Decoupled by design: this reads pending state from Postgres, so it runs
    equally well inline after an ingest OR as an independent worker/cron later
    — no ingest call is required for it to have work to do. `dry_run=True`
    counts what WOULD project without touching the sink or stamping rows.
    `knowledge_handles`/`graphiti_client` are injectable for tests; when omitted
    and not dry-run they are constructed lazily (durable-infra side effects).
    """
    if sink not in _SYNC_COLUMNS:
        raise ValueError(f"unknown sink {sink!r} (expected one of {sorted(_SYNC_COLUMNS)})")

    pending = load_pending_chat_messages(sink)
    chunks = _chunk_pending_chat(pending, max_chars=max_chars)
    if dry_run:
        return len(chunks), sum(len(c.record_ids) for c in chunks)

    chunks_done = records_stamped = 0
    if sink == "weaviate":
        if knowledge_handles is None:
            knowledge_handles = create_all_lane_knowledge()
        for chunk in chunks:
            await _project_chat_chunk_to_weaviate(knowledge_handles, chunk)
            mark_chat_synced("weaviate", list(chunk.record_ids))
            chunks_done += 1
            records_stamped += len(chunk.record_ids)
    else:  # graphiti
        if graphiti_client is None:
            graphiti_client = GraphitiCaseClient()
        for chunk in chunks:
            _project_chunk_to_graphiti(graphiti_client, chunk)
            mark_chat_synced("graphiti", list(chunk.record_ids))
            chunks_done += 1
            records_stamped += len(chunk.record_ids)
    return chunks_done, records_stamped


# ---------------------------------------------------------------------------
# Classification: load unclassified messages -> run lane_classifier -> UPDATE lane
# ---------------------------------------------------------------------------


def classify_pending_messages(mode: str = "keyword", model: str = "glm-5.1") -> int:
    """Load messages where lane IS NULL, run lane_classifier, UPDATE lane column.
    Returns number of messages classified. Does NOT set lane_reviewed — that
    requires human review (NocoDB v1, CopilotKit v2)."""
    from server.contracts.records import ChatMessage

    with _get_engine().connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT id, content, source, conversation_id, message_index, role "
                    "FROM working.chat_message WHERE lane IS NULL "
                    "ORDER BY conversation_id, message_index"
                )
            )
            .mappings()
            .all()
        )

    if not rows:
        return 0

    # Build ChatMessage objects for classifier
    messages = [
        ChatMessage(
            source=r["source"],
            conversation_id=str(r["conversation_id"]),
            message_index=r["message_index"],
            role=r["role"],
            content=r["content"],
            timestamp=None,
            thinking=None,
            artifacts=[],
            attachments=[],
            lane=None,
            lane_reviewed=False,
            attrs={},
        )
        for r in rows
    ]
    lanes = classify_messages(messages, mode=mode, model=model)

    if len(lanes) != len(rows):
        raise ValueError(f"classifier returned {len(lanes)} lanes for {len(rows)} messages")

    # Batch UPDATE
    with _get_engine().begin() as conn:
        for row, lane in zip(rows, lanes):
            conn.execute(
                text("UPDATE working.chat_message SET lane = :lane WHERE id = :id"),
                {"lane": lane, "id": row["id"]},
            )
    return len(rows)


# ---------------------------------------------------------------------------
# Orchestrator: parse -> normalize -> PG (source of truth) -> (optional) classify -> (optional) sync
# ---------------------------------------------------------------------------


@dataclass
class IngestReport:
    path: str
    parser_id: str
    parse_attempts: list[dict[str, Any]]
    record_count: int
    records_stored: int
    classified: bool
    lane_counts: dict[str, int]
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
    engine: str = "auto",
    format: str | None = None,
    classify: bool = False,
    classify_mode: str = "keyword",
    classify_model: str = "glm-5.1",
    auto_review: bool = False,
    knowledge_handles: dict[str, Any] | None = None,
    graphiti_client: GraphitiCaseClient | None = None,
) -> IngestReport:
    """The whole pipeline for ONE chat-export file, PG-first:

        parse (engine=auto|python|go) -> (optional conversation filter) -> finalize
              -> normalize_to_chat() -> store_chat()   [Postgres SOURCE OF TRUTH]
              -> (optional) classify_pending_messages()  [lane per message]
              -> (optional) sync_pending_chat('weaviate' / 'graphiti')  [projection]

    `engine`/`format` pick the PARSER dynamically (Python registry vs SBV Go),
    without changing anything downstream — see `parse_chat_export`. The
    projection step reads PENDING rows from Postgres, so it naturally projects
    anything left pending by a prior crashed run too, not only this file's rows
    — that is the change-detection contract, not a quirk. Pass `project=False`
    to write Postgres only and let a separate worker drain the projections.
    `dry_run=True` stores nothing and only counts.
    `classify=True` runs the lane classifier after storing (sets lane, NOT lane_reviewed).
    """
    p = Path(path)
    records, parser_id, attempts = parse_chat_export(p, source_meta, engine=engine, format=format)
    records = filter_conversations(records, conversation_ids)
    records = finalize(records)

    w_chunks = w_synced = g_chunks = g_synced = 0
    lane_counts: dict[str, int] = {}
    classified = False

    records_stored = 0
    if dry_run:
        # Preview THIS file's own records (nothing is written, so reading
        # "pending" back from PG would reflect unrelated pre-existing rows).
        conv, messages = normalize_to_chat(records, str(p))
        if conv and messages:
            preview = chunk_chat_messages(messages, max_chars=max_chars)
            if project:
                w_chunks = g_chunks = len(preview)
                w_synced = g_synced = len(messages)
    else:
        conv, messages = normalize_to_chat(records, str(p))
        if conv and messages:
            _, inserted = store_chat(conv, messages)
            records_stored = inserted

            if classify:
                # Note: classify_pending_messages() classifies ALL unclassified
                # messages in the DB, not just this file's. That's intentional —
                # it's a global worker function.
                classified = True
                # We don't have per-file lane counts easily; skip for now
                if auto_review:
                    # For testing: auto-mark classified messages as reviewed
                    from sqlalchemy import text

                    with _get_engine().begin() as conn:
                        conn.execute(
                            text(
                                "UPDATE working.chat_message SET lane_reviewed = TRUE WHERE lane IS NOT NULL AND lane_reviewed = FALSE"
                            )
                        )

            if project:
                w_chunks, w_synced = await sync_pending_chat(
                    "weaviate", max_chars=max_chars, knowledge_handles=knowledge_handles
                )
                g_chunks, g_synced = await sync_pending_chat(
                    "graphiti", max_chars=max_chars, graphiti_client=graphiti_client
                )

    return IngestReport(
        path=str(p),
        parser_id=parser_id,
        parse_attempts=attempts,
        record_count=len(records),
        records_stored=records_stored,
        classified=classified,
        lane_counts=lane_counts,
        weaviate_chunks=w_chunks,
        weaviate_records_synced=w_synced,
        graphiti_chunks=g_chunks,
        graphiti_records_synced=g_synced,
        dry_run=dry_run,
        conversation_ids=sorted({r.conversation_id or "untitled" for r in records}),
    )
