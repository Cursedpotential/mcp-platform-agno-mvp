"""
evidence/store.py — persist normalized records + feed the knowledge engine.

Two sinks (P2 scope):
  1. working.normalized_record — the relational home of every canonical record,
     carrying the bitemporal fields (occurred_at / knowledge_time / disclosure_tier).
  2. The domain-partitioned KNOWLEDGE engine (Weaviate collection `Platform_knowledge`,
     ADR-0040 — vectors in Weaviate, contents in Postgres): transcripts are re-rendered
     as conversation markdown and inserted with a `domain` metadata tag
     (timeline_relationship | personal_history | platform_design | legal_strategy) so
     agents filter to their domains (native knowledge_filters — see docs/DEBT.md).

P3 extends this module with the Graphiti bitemporal episode writes; the
relational + vector sinks here are complete for P2.

C2.6 (resilience + observability, 2026-07-20/21) additions:
  - `load_records_for_artifact()` — the read-side counterpart to
    `store_records()`, used by the knowledge-from-store retry path
    (server/evidence/workflows.py's `run_knowledge_from_store`, wired off
    `POST /v1/runs/{id}/retry {"from_stage": "knowledge"}`) to rebuild
    NormalizedRecord objects from already-stored rows instead of re-parsing.
  - Bounded exponential-backoff retry (`_retry_async`/`_retry_sync`) around
    the knowledge-engine insert and the store insert, transient-errors-only
    (Milvus 503/timeout/connection, DB connection errors) — see
    `_is_transient_error`. Every attempt is recorded so the run ledger's
    stage output can show exactly what was retried and why.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-07-21 (C2.6: retry/backoff + load_records_for_artifact + logging)
# Byline: Claude Code · Fable 5 · 2026-07-31 (Milvus→Weaviate doc-drift cleanup (ADR-0040))

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Awaitable, Callable, TypeVar

from sqlalchemy import create_engine, text

from server.evidence.custody import ArtifactRef
from server.contracts.records import NormalizedRecord

_engine = None

logger = logging.getLogger("evidence.runs")

KNOWLEDGE_DOMAINS = (
    "timeline_relationship",
    "personal_history",
    "platform_design",
    "legal_strategy",
)

# ---------------------------------------------------------------------------
# Transient-aware retry (C2.6 requirement 2) — bounded exponential backoff
# around the knowledge stage's ingest call and store's DB writes, ONLY for
# transient failure classes. Non-transient errors (bad data, validation,
# programming errors) raise on the FIRST attempt with no retry and no delay
# — retrying those would just mask a real bug behind ~40s of pointless waits.
# ---------------------------------------------------------------------------

_T = TypeVar("_T")

# "3 attempts: ~2s/8s/30s" (task spec) read as 3 backoff delays -> up to 4
# total tries (1 initial + 3 backed-off retries), waiting 2s/8s/30s before
# retries 2/3/4 respectively. Every attempt (success or failure) is appended
# to the caller's `attempts_log` as {n, error, waited_s}.
_TRANSIENT_BACKOFFS_S: tuple[float, ...] = (2.0, 8.0, 30.0)
_MAX_ERROR_CHARS = 200


def _truncate_error(exc: BaseException) -> str:
    return str(exc)[:_MAX_ERROR_CHARS]


def _is_transient_error(exc: BaseException) -> bool:
    """Classify an exception as transient (worth retrying) vs. not.

    Transient: vector-store 503/UNAVAILABLE/timeout — Weaviate (v4 client's
    weaviate.exceptions, ADR-0040 cutover) and legacy pymilvus, both duck-typed
    by module+class name so this module never hard-imports either client (they
    may not be installed on every path that imports store.py) —
    plain connection/timeout errors, and SQLAlchemy's OperationalError/
    DBAPIError (DB connection drops, not data errors like IntegrityError).
    Deliberately does NOT treat bare OSError as transient — FileNotFoundError
    and PermissionError are OSError subclasses and are emphatically NOT
    retryable; only ConnectionError/TimeoutError (and their stdlib subtypes:
    ConnectionRefusedError, ConnectionResetError, BrokenPipeError) qualify.
    """
    module = type(exc).__module__ or ""
    name = type(exc).__name__
    if "weaviate" in module:
        # v4 client: WeaviateConnectionError / WeaviateTimeoutError /
        # WeaviateGRPCUnavailableError etc. are retryable; schema/query errors
        # (UnexpectedStatusCodeError 4xx, WeaviateInvalidInputError) are not.
        if any(marker in name for marker in ("Connection", "Timeout", "Unavailable", "GRPCUnavailable")):
            return True
        status = str(getattr(exc, "message", "") or exc).upper()
        if "UNAVAILABLE" in status or "DEADLINE_EXCEEDED" in status or "503" in status:
            return True
    if "pymilvus" in module and "Milvus" in name:
        code = getattr(exc, "code", None)
        if code in (503, "503"):
            return True
        status = str(getattr(exc, "status", "") or getattr(exc, "message", "") or "").upper()
        if "UNAVAILABLE" in status or "DEADLINE_EXCEEDED" in status or "503" in status:
            return True
        # fall through to the text-marker check below — many Milvus errors
        # carry a useful message but not a clean .code/.status attribute.
    if isinstance(exc, (ConnectionError, TimeoutError, asyncio.TimeoutError)):
        return True
    try:
        from sqlalchemy.exc import DBAPIError, OperationalError

        if isinstance(exc, (OperationalError, DBAPIError)):
            return True
    except ImportError:
        pass
    marker_text = str(exc).lower()
    markers = (
        "503",
        "unavailable",
        "timeout",
        "timed out",
        "connection refused",
        "connection reset",
        "broken pipe",
        "temporarily unavailable",
        "deadline exceeded",
    )
    return any(marker in marker_text for marker in markers)


async def _sleep_backoff_async(seconds: float) -> None:
    """Indirection over asyncio.sleep so tests can monkeypatch just this
    module's retry delay without mutating the real asyncio module (mirrors
    server/evidence/workflows.py's `_gate_sleep` pattern)."""
    await asyncio.sleep(seconds)


def _sleep_backoff_sync(seconds: float) -> None:
    """Sync counterpart to `_sleep_backoff_async`, same indirection reason."""
    time.sleep(seconds)


async def _retry_async(
    label: str,
    fn: Callable[[], Awaitable[_T]],
    attempts_log: list[dict[str, Any]] | None = None,
) -> _T:
    """Call an async zero-arg callable with bounded exponential backoff on
    TRANSIENT errors only. A non-transient error, or a transient error past
    the last backoff slot, raises immediately (no further retry). Every
    attempt is appended to `attempts_log` (when given) as
    {n, error (None on success, else truncated to 200 chars), waited_s}."""
    delay = 0.0
    n = 1
    while True:
        if delay:
            logger.warning("%s: retrying after transient error, waiting %ss (attempt %s)", label, delay, n)
            await _sleep_backoff_async(delay)
        try:
            result = await fn()
        except Exception as exc:
            if attempts_log is not None:
                attempts_log.append({"n": n, "error": _truncate_error(exc), "waited_s": delay})
            transient = _is_transient_error(exc)
            if not transient or n > len(_TRANSIENT_BACKOFFS_S):
                logger.error(
                    "%s: failed on attempt %s (%s): %s",
                    label,
                    n,
                    "retries exhausted" if transient else "non-transient error",
                    exc,
                )
                raise
            delay = _TRANSIENT_BACKOFFS_S[n - 1]
            n += 1
            continue
        if attempts_log is not None:
            attempts_log.append({"n": n, "error": None, "waited_s": delay})
        return result


def _retry_sync(
    label: str,
    fn: Callable[[], _T],
    attempts_log: list[dict[str, Any]] | None = None,
) -> _T:
    """Sync counterpart to `_retry_async` — same semantics, `time.sleep`."""
    delay = 0.0
    n = 1
    while True:
        if delay:
            logger.warning("%s: retrying after transient error, waiting %ss (attempt %s)", label, delay, n)
            _sleep_backoff_sync(delay)
        try:
            result = fn()
        except Exception as exc:
            if attempts_log is not None:
                attempts_log.append({"n": n, "error": _truncate_error(exc), "waited_s": delay})
            transient = _is_transient_error(exc)
            if not transient or n > len(_TRANSIENT_BACKOFFS_S):
                logger.error(
                    "%s: failed on attempt %s (%s): %s",
                    label,
                    n,
                    "retries exhausted" if transient else "non-transient error",
                    exc,
                )
                raise
            delay = _TRANSIENT_BACKOFFS_S[n - 1]
            n += 1
            continue
        if attempts_log is not None:
            attempts_log.append({"n": n, "error": None, "waited_s": delay})
        return result


def _get_engine():
    global _engine
    if _engine is None:
        from server.core.url import db_url

        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def store_records(
    records: list[NormalizedRecord],
    artifact: ArtifactRef,
    attempts_log: list[dict[str, Any]] | None = None,
) -> int:
    """Batch-insert canonical records into working.normalized_record.

    `attempts_log` (C2.6 requirement 2, optional — default None preserves
    the exact pre-C2.6 behavior for any other caller): when given, the
    insert is retried with bounded exponential backoff on a transient DB
    error (connection drop, not a data/constraint error) and every attempt
    is appended to it. The whole `rows` batch is one statement inside one
    `engine.begin()` transaction per attempt, so a retry after a transient
    failure never risks a partial/duplicate insert — the prior attempt's
    transaction was already rolled back by the failure.
    """
    if not records:
        return 0
    rows = [
        {
            "artifact_id": artifact.artifact_id,
            "record_type": r.record_type.value,
            "source": r.source,
            "conversation_id": r.conversation_id,
            "role": r.role,
            "participants": json.dumps(r.participants),
            "content": r.content,
            "occurred_at": r.occurred_at,
            "knowledge_time": r.knowledge_time,
            "disclosure_tier": r.disclosure_tier.value,
            "attrs": json.dumps(r.attrs),
        }
        for r in records
    ]

    def _do_insert() -> None:
        with _get_engine().begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO working.normalized_record "
                    "(artifact_id, record_type, source, conversation_id, role, participants, "
                    " content, occurred_at, knowledge_time, disclosure_tier, attrs) "
                    "VALUES (:artifact_id, :record_type, :source, :conversation_id, :role, "
                    " CAST(:participants AS jsonb), :content, :occurred_at, :knowledge_time, "
                    " :disclosure_tier, CAST(:attrs AS jsonb))"
                ),
                rows,
            )

    _retry_sync(f"store_records[{artifact.artifact_id}]", _do_insert, attempts_log)
    return len(rows)


def load_records_for_artifact(artifact_id: str) -> list[NormalizedRecord]:
    """Rebuild NormalizedRecord objects from working.normalized_record for
    one artifact — the read-side counterpart to `store_records()`.

    Used by the knowledge-from-store retry path (C2.6 requirement 1,
    server/evidence/workflows.py's `run_knowledge_from_store` and the
    dedupe-auto-route in `store_step`) to re-run the knowledge stage over
    records that are ALREADY in Postgres, without re-parsing or re-storing
    anything. Ordered by occurred_at so `render_conversations_markdown`'s
    per-conversation chronological sort sees the same order store_records
    would have produced originally (NULLS LAST — undated records sort after
    dated ones, matching Python's `sort(key=...)` treatment of "" as low).
    """
    with _get_engine().connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT record_type, source, conversation_id, role, participants, "
                    "content, occurred_at, knowledge_time, disclosure_tier, attrs "
                    "FROM working.normalized_record WHERE artifact_id = :a "
                    "ORDER BY occurred_at NULLS LAST"
                ),
                {"a": artifact_id},
            )
            .mappings()
            .all()
        )

    records: list[NormalizedRecord] = []
    for row in rows:
        participants = row["participants"]
        if isinstance(participants, str):
            participants = json.loads(participants)
        attrs = row["attrs"]
        if isinstance(attrs, str):
            attrs = json.loads(attrs)
        records.append(
            NormalizedRecord(
                record_type=row["record_type"],
                source=row["source"],
                conversation_id=row["conversation_id"],
                role=row["role"],
                participants=participants or [],
                content=row["content"] or "",
                occurred_at=row["occurred_at"],
                knowledge_time=row["knowledge_time"],
                disclosure_tier=row["disclosure_tier"],
                attrs=attrs or {},
            )
        )
    return records


def render_conversations_markdown(records: list[NormalizedRecord]) -> dict[str, str]:
    """Group records by conversation and render readable markdown per conversation
    (the document shape the knowledge engine chunks/embeds best)."""
    by_conv: dict[str, list[NormalizedRecord]] = defaultdict(list)
    for r in records:
        by_conv[r.conversation_id or "untitled"].append(r)

    docs: dict[str, str] = {}
    for conv_id, recs in by_conv.items():
        recs.sort(key=lambda r: r.occurred_at.isoformat() if r.occurred_at else "")
        title = recs[0].attrs.get("conversation_title") or conv_id
        lines = [f"# {title}", ""]
        if recs[0].occurred_at:
            lines += [f"_First message: {recs[0].occurred_at.isoformat()}_", ""]
        for r in recs:
            stamp = f" — {r.occurred_at.isoformat()}" if r.occurred_at else ""
            lines += [f"**{(r.role or 'unknown').upper()}{stamp}:**", "", r.content, "", "---", ""]
        docs[conv_id] = "\n".join(lines)
    return docs


async def ingest_into_knowledge(
    knowledge,
    records: list[NormalizedRecord],
    artifact: ArtifactRef,
    domain: str,
    derived_dir: str | Path = "knowledge/platform/transcripts",
    attempts_log: list[dict[str, Any]] | None = None,
) -> int:
    """Render per-conversation markdown, persist under knowledge/, and ainsert
    into the engine with the domain tag (agents filter on metadata.domain).

    `attempts_log` (C2.6 requirement 2, optional): when given, each
    document's `knowledge.ainsert()` call is retried with bounded
    exponential backoff on a transient error (Milvus 503/timeout/connection
    — see `_is_transient_error`), and every attempt across every document is
    appended to it (shared across documents when a run has more than one
    conversation — `n` restarts at 1 for each document's own retry loop, so
    a multi-doc run's attempts_log can show more than one entry with the
    same `n`; the task's stage-output contract is exactly
    `{n, error, waited_s}` with no per-document key, so this stays literal
    to that shape rather than inventing an extra field)."""
    if domain not in KNOWLEDGE_DOMAINS:
        raise ValueError(f"unknown knowledge domain {domain!r}; expected one of {KNOWLEDGE_DOMAINS}")
    docs = render_conversations_markdown(records)
    out_dir = Path(derived_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for conv_id, markdown in docs.items():
        safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in conv_id)[:80] or "conv"
        doc_path = out_dir / f"{artifact.sha256[:12]}-{safe}.md"
        doc_path.write_text(markdown, encoding="utf-8")

        async def _do_insert(doc_path: Path = doc_path, conv_id: str = conv_id) -> None:
            await knowledge.ainsert(
                name=doc_path.stem,
                path=str(doc_path),
                metadata={
                    "domain": domain,
                    "category": "transcripts",
                    "artifact_id": artifact.artifact_id,
                    "sha256": artifact.sha256,
                    "conversation_id": conv_id,
                },
            )

        await _retry_async(f"knowledge.ainsert[{artifact.artifact_id}:{conv_id}]", _do_insert, attempts_log)
        count += 1
    return count


def record_counts(artifact_id: str) -> dict[str, Any]:
    """Quick verification helper: counts for one artifact."""
    with _get_engine().connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT count(*) AS records, count(DISTINCT conversation_id) AS conversations "
                    "FROM working.normalized_record WHERE artifact_id = :a"
                ),
                {"a": artifact_id},
            )
            .mappings()
            .first()
        )
    return dict(row) if row else {"records": 0, "conversations": 0}
