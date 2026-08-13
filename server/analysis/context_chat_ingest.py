"""PG-first AI-chat ingestion, selective routing, and Agno-compatible projection.

The canonical path is parse -> conversation/message -> message-safe chunks ->
multi-label classification -> selective HITL -> outbox projection. Raw AI-chat
rows are horizon-neutral and can never enter the evidence lane.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable
import uuid

from sqlalchemy import text

from server.analysis.chat_normalizer import compute_content_hash, normalize_many
from server.analysis.chat_parse import filter_conversations, parse_chat_export
from server.analysis.lane_classifier import classifier_id, classify_chunks
from server.contracts.records import ChatChunk, ChatConversation, ChatMessage, LaneClassification
from server.tools.registry import registry

__all__ = ["filter_conversations", "ingest_chat_file", "parse_chat_export", "registry"]

DEFAULT_MAX_CHARS = 6000
DEFAULT_EMBEDDER_ID = "nvidia/nv-embed-v1"

CONTEXT_BANNER = (
    "[UNVERIFIED LEAD -- AI-chat context, not primary evidence. "
    "Verify against primary evidence before relying on this.]"
)

LANE_COLLECTIONS = {
    "platform": "platform_knowledge",
    "legal": "legal_knowledge",
    "personal_history": "personal_history_knowledge",
    "context": "platform_context",
}

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine

        from server.core.url import build_db_url

        _engine = create_engine(build_db_url(), pool_pre_ping=True)
    return _engine


def create_lane_knowledge(lane: str):
    """Build the standard Agno Knowledge search handle for one chat lane."""

    from server.core.session import create_knowledge

    try:
        collection = LANE_COLLECTIONS[lane]
    except KeyError:
        raise ValueError(f"unknown AI-chat lane {lane!r}") from None
    return create_knowledge(lane, collection)


def create_all_lane_knowledge() -> dict[str, Any]:
    return {lane: create_lane_knowledge(lane) for lane in LANE_COLLECTIONS}


def _render_message(message: ChatMessage) -> str:
    return f"[{message.role}] {message.content.strip()}".strip()


def _window_groups(messages: list[ChatMessage], max_chars: int) -> list[list[ChatMessage]]:
    """Apply a hard cap only between messages; never cut through a turn."""

    groups: list[list[ChatMessage]] = []
    current: list[ChatMessage] = []
    current_size = 0
    for message in messages:
        rendered_size = len(_render_message(message)) + 2
        if current and current_size + rendered_size > max_chars:
            groups.append(current)
            current = []
            current_size = 0
        current.append(message)
        current_size += rendered_size
    if current:
        groups.append(current)
    return groups


def _segment_groups(
    messages: list[ChatMessage],
    *,
    chunker: str,
    max_chars: int,
) -> tuple[list[list[ChatMessage]], str]:
    if chunker == "message-window":
        return _window_groups(messages, max_chars), chunker

    rendered = "\n\n".join(_render_message(message) for message in messages)
    message_ends: list[int] = []
    cursor = 0
    for index, message in enumerate(messages):
        cursor += len(_render_message(message))
        message_ends.append(cursor)
        if index < len(messages) - 1:
            cursor += 2

    if chunker == "chonkie-semantic":
        from chonkie import SemanticChunker

        segments = SemanticChunker(chunk_size=400).chunk(rendered)
    elif chunker == "teraflopai":
        from chonkie import TeraflopAIChunker

        segments = TeraflopAIChunker().chunk(rendered)
    else:
        raise ValueError(f"unknown chunker {chunker!r}")

    boundary_indexes: list[int] = []
    for segment in segments:
        end = int(segment.end_index)
        completed = [index for index, message_end in enumerate(message_ends) if message_end <= end]
        if completed:
            boundary_indexes.append(completed[-1] + 1)
    boundary_indexes.append(len(messages))

    groups: list[list[ChatMessage]] = []
    start = 0
    for stop in sorted(set(boundary_indexes)):
        if stop > start:
            groups.extend(_window_groups(messages[start:stop], max_chars))
            start = stop
    if start < len(messages):
        groups.extend(_window_groups(messages[start:], max_chars))
    return groups, chunker


def chunk_chat_messages(
    messages: list[ChatMessage],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    chunker: str = "message-window",
) -> list[ChatChunk]:
    """Create canonical chunks before classification, preserving every role."""

    by_conversation: dict[str, list[ChatMessage]] = defaultdict(list)
    for message in messages:
        by_conversation[message.conversation_id].append(message)

    chunks: list[ChatChunk] = []
    for conversation_id, conversation_messages in by_conversation.items():
        ordered = sorted(conversation_messages, key=lambda message: message.message_index)
        groups, chunker_id = _segment_groups(ordered, chunker=chunker, max_chars=max_chars)
        for chunk_index, group in enumerate(groups):
            body = "\n\n".join(_render_message(message) for message in group)
            content = f"{CONTEXT_BANNER}\n\n{body}"
            indexes = [message.message_index for message in group]
            digest_input = f"{conversation_id}:{indexes}:{content}".encode()
            chunks.append(
                ChatChunk(
                    conversation_id=conversation_id,
                    chunk_index=chunk_index,
                    content=content,
                    content_hash=hashlib.sha256(digest_input).hexdigest(),
                    message_indexes=indexes,
                    chunker_id=chunker_id,
                    char_start=None,
                    char_end=None,
                )
            )
    return chunks


def _store_conversation(connection: Any, conversation: ChatConversation) -> str:
    row = (
        connection.execute(
            text(
                "INSERT INTO working.chat_conversation "
                "(source, external_id, title, source_path, created_at, attrs) "
                "VALUES (:source, :external_id, :title, :source_path, :created_at, CAST(:attrs AS jsonb)) "
                "ON CONFLICT (source, external_id) DO UPDATE SET "
                "title = COALESCE(EXCLUDED.title, working.chat_conversation.title), "
                "source_path = COALESCE(EXCLUDED.source_path, working.chat_conversation.source_path) "
                "RETURNING id"
            ),
            {
                "source": conversation.source,
                "external_id": conversation.conversation_id,
                "title": conversation.title,
                "source_path": conversation.file_path,
                "created_at": conversation.created_at,
                "attrs": json.dumps(conversation.attrs),
            },
        )
        .mappings()
        .one()
    )
    return str(row["id"])


def _store_messages(
    connection: Any,
    conversation_db_id: str,
    messages: list[ChatMessage],
) -> dict[int, str]:
    ids: dict[int, str] = {}
    for message in messages:
        row = (
            connection.execute(
                text(
                    "INSERT INTO working.chat_message "
                    "(conversation_id, message_index, role, content, sent_at, thinking, attachments, attrs, content_hash) "
                    "VALUES (CAST(:conversation_id AS uuid), :message_index, :role, :content, :sent_at, :thinking, "
                    "CAST(:attachments AS jsonb), CAST(:attrs AS jsonb), :content_hash) "
                    "ON CONFLICT (conversation_id, message_index) DO UPDATE SET "
                    "role = EXCLUDED.role, content = EXCLUDED.content, sent_at = EXCLUDED.sent_at, "
                    "thinking = EXCLUDED.thinking, attachments = EXCLUDED.attachments, attrs = EXCLUDED.attrs "
                    "RETURNING id"
                ),
                {
                    "conversation_id": conversation_db_id,
                    "message_index": message.message_index,
                    "role": message.role if message.role in {"user", "assistant", "system", "tool"} else "unknown",
                    "content": message.content,
                    "sent_at": message.timestamp,
                    "thinking": message.thinking,
                    "attachments": json.dumps(message.attachments),
                    "attrs": json.dumps(message.attrs),
                    "content_hash": compute_content_hash(message),
                },
            )
            .mappings()
            .one()
        )
        ids[message.message_index] = str(row["id"])
    return ids


def _store_chunks(
    connection: Any,
    conversation_db_id: str,
    chunks: list[ChatChunk],
    message_ids: dict[int, str],
) -> dict[str, str]:
    ids: dict[str, str] = {}
    for chunk in chunks:
        row = (
            connection.execute(
                text(
                    "INSERT INTO working.chat_chunk "
                    "(conversation_id, chunk_index, content, content_hash, chunker_id, token_count, char_start, char_end, attrs) "
                    "VALUES (CAST(:conversation_id AS uuid), :chunk_index, :content, :content_hash, :chunker_id, "
                    ":token_count, :char_start, :char_end, CAST(:attrs AS jsonb)) "
                    "ON CONFLICT (conversation_id, chunk_index) DO UPDATE SET "
                    "content = EXCLUDED.content, content_hash = EXCLUDED.content_hash, chunker_id = EXCLUDED.chunker_id "
                    "RETURNING id"
                ),
                {
                    "conversation_id": conversation_db_id,
                    "chunk_index": chunk.chunk_index,
                    "content": chunk.content,
                    "content_hash": chunk.content_hash,
                    "chunker_id": chunk.chunker_id,
                    "token_count": chunk.token_count,
                    "char_start": chunk.char_start,
                    "char_end": chunk.char_end,
                    "attrs": json.dumps(chunk.attrs),
                },
            )
            .mappings()
            .one()
        )
        chunk_id = str(row["id"])
        ids[chunk.content_hash] = chunk_id
        for ordinal, message_index in enumerate(chunk.message_indexes):
            connection.execute(
                text(
                    "INSERT INTO working.chat_chunk_message (chunk_id, message_id, ordinal) "
                    "VALUES (CAST(:chunk_id AS uuid), CAST(:message_id AS uuid), :ordinal) "
                    "ON CONFLICT (chunk_id, message_id) DO NOTHING"
                ),
                {"chunk_id": chunk_id, "message_id": message_ids[message_index], "ordinal": ordinal},
            )
    return ids


def _is_projection_eligible(classification: LaneClassification) -> bool:
    return classification.review_status in {"auto_accepted", "human_approved", "human_corrected"} or (
        classification.lane.value == "context"
        and classification.review_status in {"pending_review", "classification_failed"}
    )


def _store_classifications(
    connection: Any,
    chunk_ids: dict[str, str],
    classifications: dict[str, list[LaneClassification]],
    *,
    classifier_id: str,
) -> None:
    for content_hash, assignments in classifications.items():
        chunk_id = chunk_ids[content_hash]
        for assignment in assignments:
            connection.execute(
                text(
                    "INSERT INTO working.chat_chunk_lane "
                    "(chunk_id, lane, confidence, classifier_id, review_status, rationale) "
                    "VALUES (CAST(:chunk_id AS uuid), :lane, :confidence, :classifier_id, :review_status, :rationale) "
                    "ON CONFLICT (chunk_id, lane) DO UPDATE SET confidence = EXCLUDED.confidence, "
                    "classifier_id = EXCLUDED.classifier_id, review_status = EXCLUDED.review_status, "
                    "rationale = EXCLUDED.rationale"
                ),
                {
                    "chunk_id": chunk_id,
                    "lane": assignment.lane.value,
                    "confidence": assignment.confidence,
                    "classifier_id": classifier_id,
                    "review_status": assignment.review_status,
                    "rationale": assignment.rationale,
                },
            )
            if _is_projection_eligible(assignment):
                for sink in ("weaviate", "graphiti"):
                    connection.execute(
                        text(
                            "INSERT INTO working.chat_chunk_projection (chunk_id, lane, sink, embedder_id) "
                            "VALUES (CAST(:chunk_id AS uuid), :lane, :sink, :embedder_id) "
                            "ON CONFLICT (chunk_id, lane, sink) DO NOTHING"
                        ),
                        {
                            "chunk_id": chunk_id,
                            "lane": assignment.lane.value,
                            "sink": sink,
                            "embedder_id": DEFAULT_EMBEDDER_ID if sink == "weaviate" else None,
                        },
                    )


def store_chat_batch(
    conversation: ChatConversation,
    messages: list[ChatMessage],
    chunks: list[ChatChunk],
    classifications: dict[str, list[LaneClassification]],
    *,
    classifier_id_value: str,
) -> int:
    """Atomically persist one conversation and all derived routing state."""

    with _get_engine().begin() as connection:
        conversation_id = _store_conversation(connection, conversation)
        message_ids = _store_messages(connection, conversation_id, messages)
        chunk_ids = _store_chunks(connection, conversation_id, chunks, message_ids)
        _store_classifications(connection, chunk_ids, classifications, classifier_id=classifier_id_value)
    return len(messages)


@dataclass(frozen=True)
class PendingProjection:
    chunk_id: str
    content_hash: str
    content: str
    lane: str
    sink: str
    conversation_external_id: str
    conversation_title: str | None
    chunk_index: int


def load_pending_projections(sink: str) -> list[PendingProjection]:
    if sink not in {"weaviate", "graphiti"}:
        raise ValueError("sink must be 'weaviate' or 'graphiti'")
    with _get_engine().connect() as connection:
        rows = (
            connection.execute(
                text(
                    "SELECT p.chunk_id, c.content_hash, c.content, p.lane, p.sink, "
                    "v.external_id, v.title, c.chunk_index "
                    "FROM working.chat_chunk_projection p "
                    "JOIN working.chat_chunk c ON c.id = p.chunk_id "
                    "JOIN working.chat_conversation v ON v.id = c.conversation_id "
                    "WHERE p.sink = :sink AND p.projected_at IS NULL "
                    "ORDER BY c.id, p.lane"
                ),
                {"sink": sink},
            )
            .mappings()
            .all()
        )
    return [
        PendingProjection(
            chunk_id=str(row["chunk_id"]),
            content_hash=row["content_hash"],
            content=row["content"],
            lane=row["lane"],
            sink=row["sink"],
            conversation_external_id=row["external_id"],
            conversation_title=row["title"],
            chunk_index=row["chunk_index"],
        )
        for row in rows
    ]


def _mark_projected(item: PendingProjection, projection_ref: str) -> None:
    with _get_engine().begin() as connection:
        connection.execute(
            text(
                "UPDATE working.chat_chunk_projection SET projected_at = now(), projection_ref = :ref, "
                "attempts = attempts + 1, last_error = NULL "
                "WHERE chunk_id = CAST(:chunk_id AS uuid) AND lane = :lane AND sink = :sink"
            ),
            {"ref": projection_ref, "chunk_id": item.chunk_id, "lane": item.lane, "sink": item.sink},
        )


def _weaviate_uuid(chunk_id: str, lane: str) -> uuid.UUID:
    return uuid.UUID(hex=hashlib.md5(f"{chunk_id}:{lane}".encode(), usedforsecurity=False).hexdigest())


def _load_cached_embedding(chunk_id: str) -> list[float] | None:
    with _get_engine().connect() as connection:
        value = connection.execute(
            text(
                "SELECT embedding::text FROM working.chat_chunk_embedding "
                "WHERE chunk_id = CAST(:chunk_id AS uuid) AND embedder_id = :embedder_id"
            ),
            {"chunk_id": chunk_id, "embedder_id": DEFAULT_EMBEDDER_ID},
        ).scalar()
    return [float(item) for item in value.strip("[]").split(",")] if value else None


def _cache_embedding(item: PendingProjection, vector: list[float], usage: dict[str, Any] | None) -> None:
    with _get_engine().begin() as connection:
        connection.execute(
            text(
                "INSERT INTO working.chat_chunk_embedding "
                "(chunk_id, embedder_id, content_hash, embedding, embedding_dimension, "
                "vector_ref, embedded_at, attrs) "
                "VALUES (CAST(:chunk_id AS uuid), :embedder_id, :content_hash, "
                "CAST(:embedding AS vector), :dimension, :vector_ref, now(), CAST(:attrs AS jsonb)) "
                "ON CONFLICT (chunk_id, embedder_id) DO UPDATE SET embedded_at = EXCLUDED.embedded_at, "
                "embedding = EXCLUDED.embedding, embedding_dimension = EXCLUDED.embedding_dimension, "
                "vector_ref = EXCLUDED.vector_ref, attrs = EXCLUDED.attrs"
            ),
            {
                "chunk_id": item.chunk_id,
                "embedder_id": DEFAULT_EMBEDDER_ID,
                "content_hash": item.content_hash,
                "embedding": json.dumps(vector),
                "dimension": len(vector),
                "vector_ref": item.chunk_id,
                "attrs": json.dumps({"usage": usage or {}}),
            },
        )


async def _project_weaviate(items: list[PendingProjection]) -> tuple[int, int]:
    """Embed each canonical chunk once, then reuse its vector across lanes.

    Objects match Agno's Weaviate property shape, so ordinary Agno Knowledge
    search reads them without a parallel query implementation.
    """

    if not items:
        return 0, 0
    handles = create_all_lane_knowledge()
    by_chunk: dict[str, list[PendingProjection]] = defaultdict(list)
    for item in items:
        by_chunk[item.chunk_id].append(item)

    projected = 0
    for chunk_items in by_chunk.values():
        first = chunk_items[0]
        vector = _load_cached_embedding(first.chunk_id)
        if vector is None:
            embedder = handles[first.lane].vector_db.embedder
            vector, usage = embedder.get_embedding_and_usage(first.content)
            if vector is None:
                raise RuntimeError(f"embedding failed for chat chunk {first.chunk_id}")
            _cache_embedding(first, vector, usage)
        for item in chunk_items:
            handle = handles[item.lane]
            client = handle.vector_db.get_client()
            collection = client.collections.get(LANE_COLLECTIONS[item.lane])
            meta = {
                "lane": item.lane,
                "source": "ai_chat",
                "conversation_id": item.conversation_external_id,
                "conversation_title": item.conversation_title,
                "chunk_index": item.chunk_index,
                "content_hash": item.content_hash,
                "evidence_status": "unverified_lead",
            }
            object_id = _weaviate_uuid(item.chunk_id, item.lane)
            collection.data.insert(
                uuid=object_id,
                vector=vector,
                properties={
                    "name": f"chat-{item.conversation_external_id}-{item.chunk_index:04d}",
                    "content": item.content.replace("\x00", "\ufffd"),
                    "meta_data": json.dumps(meta),
                    "content_id": item.chunk_id,
                    "content_hash": item.content_hash,
                },
            )
            _mark_projected(item, str(object_id))
            projected += 1
    return projected, len(by_chunk)


def _project_graphiti(items: list[PendingProjection]) -> tuple[int, int]:
    from server.analysis.graphiti_case_client import GraphitiCaseClient

    client = GraphitiCaseClient()
    for item in items:
        client.add_memory(
            name=f"context-chat/{item.lane}/{item.conversation_external_id}/{item.chunk_index}",
            episode_body=item.content,
            source_description=f"AI chat {item.lane}; unverified lead",
        )
        _mark_projected(item, item.chunk_id)
    return len(items), len({item.chunk_id for item in items})


async def sync_pending_context(
    sink: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Drain projection rows; retained name is the registered tool contract."""

    del max_chars  # chunks are already canonical and persisted
    items = load_pending_projections(sink)
    if dry_run:
        return len(items), len({item.chunk_id for item in items})
    if sink == "weaviate":
        return await _project_weaviate(items)
    if sink == "graphiti":
        return _project_graphiti(items)
    raise ValueError("sink must be 'weaviate' or 'graphiti'")


sync_pending_chat = sync_pending_context


@dataclass
class IngestReport:
    parser_id: str
    attempts: list[dict[str, Any]]
    record_count: int
    records_stored: int
    conversation_ids: list[str]
    dry_run: bool
    classified: bool
    classifier_id: str | None = None
    lane_counts: dict[str, int] = field(default_factory=dict)
    weaviate_chunks: int = 0
    weaviate_records_synced: int = 0
    graphiti_chunks: int = 0
    graphiti_records_synced: int = 0


def _lane_counts(classifications: Iterable[list[LaneClassification]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for assignments in classifications:
        for assignment in assignments:
            counts[assignment.lane.value] += 1
    return dict(counts)


async def ingest_chat_file(
    path: Path,
    *,
    source_meta: dict[str, Any] | None = None,
    conversation_ids: set[str] | None = None,
    max_chars: int = DEFAULT_MAX_CHARS,
    dry_run: bool = False,
    project: bool = False,
    engine: str = "auto",
    format: str | None = None,
    classify: bool = True,
    classify_mode: str = "hybrid",
    classify_model: str | None = None,
    chunker: str = "message-window",
) -> IngestReport:
    """Run the complete PG-first path for one export file."""

    records, parser_id, attempts = parse_chat_export(path, source_meta, engine=engine, format=format)
    records = filter_conversations(records, conversation_ids)
    batches = normalize_many(records, file_path=str(path))
    stored = 0
    all_classifications: list[list[LaneClassification]] = []
    conversation_external_ids: list[str] = []
    prepared: list[tuple[ChatConversation, list[ChatMessage], list[ChatChunk]]] = []

    for conversation, messages in batches:
        conversation_external_ids.append(conversation.conversation_id)
        chunks = chunk_chat_messages(messages, max_chars=max_chars, chunker=chunker)
        prepared.append((conversation, messages, chunks))

    all_chunks = [chunk for _, _, chunks in prepared for chunk in chunks]
    classifications = (
        classify_chunks(all_chunks, mode=classify_mode, model_id=classify_model)
        if classify
        else {
            chunk.content_hash: [
                LaneClassification(
                    lane="context",
                    confidence=1.0,
                    review_status="pending_review",
                    rationale="classification deferred",
                )
            ]
            for chunk in all_chunks
        }
    )
    all_classifications.extend(classifications.values())

    for conversation, messages, chunks in prepared:
        batch_classifications = {chunk.content_hash: classifications[chunk.content_hash] for chunk in chunks}
        if not dry_run:
            stored += store_chat_batch(
                conversation,
                messages,
                chunks,
                batch_classifications,
                classifier_id_value=classifier_id(classify_mode, classify_model) if classify else "deferred",
            )

    weaviate_objects = weaviate_chunks = graphiti_objects = graphiti_chunks = 0
    if project and not dry_run:
        weaviate_objects, weaviate_chunks = await sync_pending_context("weaviate")
        graphiti_objects, graphiti_chunks = await sync_pending_context("graphiti")

    return IngestReport(
        parser_id=parser_id,
        attempts=attempts,
        record_count=len(records),
        records_stored=stored,
        conversation_ids=conversation_external_ids,
        dry_run=dry_run,
        classified=classify,
        classifier_id=classifier_id(classify_mode, classify_model) if classify else None,
        lane_counts=_lane_counts(all_classifications),
        weaviate_chunks=weaviate_chunks,
        weaviate_records_synced=weaviate_objects,
        graphiti_chunks=graphiti_chunks,
        graphiti_records_synced=graphiti_objects,
    )
