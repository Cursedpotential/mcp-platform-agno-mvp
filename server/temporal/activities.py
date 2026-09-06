"""
server/temporal/activities.py — the four chat-transcript Activities.

INERT (see the package docstring): registered on a worker, never dispatched to
by the live path yet.

Each Activity is a THIN WRAPPER. It lazily imports the existing pipeline
function inside its own body and returns a JSON-serializable dataclass. No
pipeline logic is reimplemented here, and nothing from ``server.*`` is imported
at module scope — that keeps this module safe to import from workflow code (for
the dataclass types) and keeps env/DB coupling out of import time, exactly as
``server/evidence/run_ledger.py:31`` already does for ``db_url``.

The 1:1 mapping onto the live steps (``server/evidence/workflows.py:588-679``,
``build_chat_transcript_workflow``):

    custody_step   -> custody_activity   -> custody.py::ingest_artifact (:173)
    parse_step     -> parse_activity     -> registry "parse.transcript" chain
    store_step     -> store_activity     -> workflows.py::_store_step_impl (:385)
    knowledge_step -> knowledge_activity -> knowledge_harness -> _knowledge_step_impl (:483)

Byline: Claude Code · Opus 5 · 2026-08-23
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from temporalio import activity

from server.temporal.knowledge_harness import KnowledgeResult, RecordsRef, get_harness

__all__ = [
    "CustodyParams",
    "CustodyResult",
    "ParseParams",
    "ParseResult",
    "StoreParams",
    "StoreResult",
    "KnowledgeParams",
    "KnowledgeResult",
    "RecordsRef",
    "custody_activity",
    "parse_activity",
    "store_activity",
    "knowledge_activity",
    "ALL_ACTIVITIES",
]


# ---------------------------------------------------------------------------
# Payload types. Temporal's default payload converter serializes dataclasses,
# so these are the wire format between the workflow and its Activities. Keep
# every field a JSON scalar / list / dict — no pydantic models, no ArtifactRef,
# no datetime objects.
# ---------------------------------------------------------------------------


@dataclass
class CustodyParams:
    """Inputs to ``ingest_artifact`` (``server/evidence/custody.py:173``)."""

    path: str
    source_meta: dict[str, Any] = field(default_factory=dict)
    custody_tier: str = "full"


@dataclass
class CustodyResult:
    """Flattened ``ArtifactRef`` (``custody.py:110``) — the frozen dataclass is
    not itself a payload type because it carries a ``datetime`` field."""

    artifact_id: str
    sha256: str
    source_ref: str
    blob_key: str
    size_bytes: int
    duplicate: bool
    ingested_at: str
    custody_tier: str


@dataclass
class ParseParams:
    path: str
    source_meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class ParseResult:
    """``records`` are the RAW parser dicts the live ``parse_step`` puts in
    ``ctx['raw_records']`` — ``_store_step_impl`` is what validates them into
    ``NormalizedRecord``, so the shape crossing this boundary matches the shape
    crossing the same boundary today.

    PAYLOAD SIZE: Temporal caps a single payload (~2 MiB by default). A large
    transcript export can exceed that. This mirrors the live in-memory ctx
    handoff faithfully, which is the P1 goal; if it bites on real inputs the fix
    is to hand off by ``artifact_id`` and re-read from Postgres inside
    ``store_activity`` — not to silently shrink the records here."""

    parser_id: str | None
    record_count: int
    records: list[dict[str, Any]] = field(default_factory=list)
    attempts: list[dict[str, Any]] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class StoreParams:
    artifact_id: str
    records: list[dict[str, Any]] = field(default_factory=list)
    parser_id: str | None = None
    parent_run_id: str | None = None
    # ctx defaults set by build_chat_transcript_workflow (workflows.py:610-618).
    message_corpus: str | None = "first_party"
    caller_owns_conversation: bool = True
    source_principal: str | None = None


@dataclass
class StoreResult:
    stored: int
    record_count: int
    dedupe_noop: bool
    detail: str
    attempts: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class KnowledgeParams:
    """The knowledge step reads its records back out of Postgres by
    ``artifact_id`` rather than taking them on the wire — that is exactly what
    ``run_knowledge_from_store`` (``workflows.py:1024``) does, and it keeps the
    largest payload out of workflow history."""

    artifact_id: str
    lane: str = "context"
    run_meta: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Activities
# ---------------------------------------------------------------------------


@activity.defn(name="custody_activity")
def custody_activity(params: CustodyParams) -> CustodyResult:
    """Take custody of the source file. Calls ``ingest_artifact`` unchanged.

    RETRY SEMANTICS: safe to retry. ``ingest_artifact`` is documented idempotent
    at ``custody.py:180-183`` — re-ingesting the same bytes returns the EXISTING
    artifact with ``duplicate=True``, and custody rows and blobs are never
    overwritten — so a retried attempt yields the same ``artifact_id`` instead of
    a second custody row.

    THE TRAP THIS INHERITS: ``duplicate=True`` is also what produced the real
    prod false-success documented at ``workflows.py:36-44`` (knowledge fails ->
    operator retries -> custody dedupes -> store sees 0 new rows -> the run
    reports completed with ``docs_ingested=0``). That trap lives in the STORE
    step's dedupe branch, and ``store_activity`` below reuses the same
    ``_store_step_impl`` guard rather than re-deriving it.

    D-082 permanent AI-chat evidence fence (GAP-032/WP-C01): this activity
    hardcodes ``workflow="chat-transcript"`` into ``source_meta`` just above
    the ``ingest_artifact`` call, same as ``workflows.py``'s custody_step —
    ``ingest_artifact`` denies that marker unconditionally before any write,
    so this activity raises ``AIChatEvidenceDenied`` (an activity failure,
    handled by Temporal's normal retry/failure policy) on every real call.
    Not caught here deliberately: Temporal activities are expected to raise
    on failure, and this Activity is not yet wired to any live HTTP trigger
    (repository census 2026-08-26 — see docs/reviews/2026-08-25-schema-audit/
    reconciliation-domains/R02-context-ingest-parser-boundary.md).
    """
    from server.evidence.custody import ingest_artifact

    artifact = ingest_artifact(
        params.path,
        {**params.source_meta, "workflow": "chat-transcript"},
        tier=params.custody_tier,
    )
    return CustodyResult(
        artifact_id=artifact.artifact_id,
        sha256=artifact.sha256,
        source_ref=artifact.source_ref,
        blob_key=artifact.blob_key,
        size_bytes=artifact.size_bytes,
        duplicate=artifact.duplicate,
        ingested_at=artifact.ingested_at,
        custody_tier=artifact.custody_tier,
    )


@activity.defn(name="parse_activity")
def parse_activity(params: ParseParams) -> ParseResult:
    """Resolve the best-fit ``parse.transcript`` tool and run it, falling
    through same-capability candidates on rejection — the substitution mechanic
    the tool mesh is built around (``workflows.py:633-660``).

    RETRY SEMANTICS: deterministic over a fixed file, so a retry only helps for
    transient IO. The in-tool fallback chain already covers "wrong format"; the
    ``ValueError`` raised once every candidate has failed is a real failure and
    must not be retried into oblivion, so the workflow declares a small
    ``maximum_attempts`` for this stage.

    NOTE on the task brief: the brief named
    ``server/analysis/chat_parse.py::parse_chat_export`` plus the
    ``server/proffer/service.py::_parse`` fallback chain. That is the ingest
    facade's parse path, not this workflow's. ``build_chat_transcript_workflow``'s
    own ``parse_step`` resolves through ``server/tools/reference.py``, and the P1
    rule is 1:1 with the workflow's actual steps — so this mirrors the registry
    chain. ``parse_chat_export`` remains reachable underneath: it is what the
    registered ``parse.transcript`` tools call.
    """
    from pathlib import Path

    from server.tools.registry import load_builtin_tools, registry

    load_builtin_tools()
    p = Path(params.path)
    candidates = registry.resolve(
        "parse.transcript",
        media_hint=p.name.lower(),
        size_bytes=p.stat().st_size,
    )
    if not candidates:
        raise ValueError(f"parse: NO tool accepts {p.name}")

    attempts: list[dict[str, Any]] = []
    last_err: Exception | None = None
    for tool in candidates:
        try:
            result = tool.run({"path": str(p), "source_meta": params.source_meta})
        except Exception as exc:  # wrong format -> try next same-capability tool
            attempts.append({"tool": tool.id, "ok": False, "error": str(exc)})
            last_err = exc
            continue
        attempts.append({"tool": tool.id, "ok": True})
        records = [_as_payload(record) for record in result["records"]]
        return ParseResult(
            parser_id=tool.id,
            record_count=len(records),
            records=records,
            attempts=attempts,
            stats=dict(result.get("stats", {}) or {}),
        )
    raise ValueError(f"parse: ALL candidates failed for {p.name}: {attempts} (last: {last_err})")


def _as_payload(record: Any) -> dict[str, Any]:
    """Coerce one raw parser record to a JSON-safe dict.

    Registered tools return either plain dicts or pydantic records; the live
    store step accepts both because ``NormalizedRecord.model_validate`` does
    (``workflows.py:445``). Only the wire needs the narrowing."""
    dump = getattr(record, "model_dump", None)
    if callable(dump):
        return dump(mode="json")
    return dict(record)


@activity.defn(name="store_activity")
def store_activity(params: StoreParams) -> StoreResult:
    """Normalize + persist into ``working.normalized_record``.

    Delegates the ENTIRE body to ``workflows.py::_store_step_impl`` (:385) by
    rebuilding the ctx dict that function reads. That is deliberate: the dedupe /
    parent-knowledge-failed auto-route lives in exactly one place today
    (:385-444) and must not be forked into a second copy here. The ``ArtifactRef``
    it needs is reloaded from custody via ``store.py::load_artifact_ref`` (:548)
    rather than rebuilt from the wire, so custody stays the source of those
    coordinates.

    RETRY SEMANTICS: ``store_records`` writes the whole batch inside one
    ``engine.begin()`` transaction per attempt, so a retry after a transient DB
    failure cannot half-apply (``store.py:262-270``). This Activity's declared
    ``RetryPolicy`` is what replaces the hand-rolled ``store.py:206 _retry_sync``
    loop; the ``attempts_log`` survives only as reporting.
    """
    from server.evidence.store import load_artifact_ref
    from server.evidence.workflows import _store_step_impl

    ctx: dict[str, Any] = {
        "artifact": load_artifact_ref(params.artifact_id),
        "raw_records": params.records,
        "parser_id": params.parser_id,
        "parent_run_id": params.parent_run_id,
        "message_corpus": params.message_corpus,
        "caller_owns_conversation": params.caller_owns_conversation,
        "source_principal": params.source_principal,
    }
    output = _store_step_impl(ctx)
    if not getattr(output, "success", True):
        raise RuntimeError(str(getattr(output, "content", "store step failed")))
    return StoreResult(
        stored=int(ctx.get("stored") or 0),
        record_count=len(ctx.get("records") or []),
        dedupe_noop=bool(ctx.get("dedupe_noop")),
        detail=str(getattr(output, "content", "")),
        attempts=list(ctx.get("store_attempts") or []),
    )


@activity.defn(name="knowledge_activity")
async def knowledge_activity(params: KnowledgeParams) -> KnowledgeResult:
    """Project the stored records into the knowledge lane.

    THIS FUNCTION CONTAINS NO PROJECTION LOGIC. It reads ``KNOWLEDGE_HARNESS``
    (``agno`` default | ``pydantic_ai``) and dispatches to the bake
    implementations in ``server/temporal/knowledge_harness/``, both of which call
    the same governed door. See ``knowledge_harness/BAKE.md``.

    RETRY SEMANTICS: this is the stage that actually fails in production — a
    Weaviate outage (historically a Milvus 503 pre-ADR-0040) fails knowledge
    after custody/parse/store already succeeded (``workflows.py:36-44``). Its
    declared ``RetryPolicy`` replaces ``store.py:167 _retry_async``'s bounded
    backoff, and the workflow gives it the longest ``start_to_close_timeout``.
    Retry is safe because the records are re-read from Postgres on each attempt
    rather than carried on the wire; re-projecting the same records is the same
    operation ``run_knowledge_from_store`` (``workflows.py:1024``) performs
    deliberately.
    """
    harness_name = os.getenv("KNOWLEDGE_HARNESS", "agno")
    harness = get_harness(harness_name)
    return await harness(
        RecordsRef(artifact_id=params.artifact_id),
        params.lane,
        dict(params.run_meta),
    )


ALL_ACTIVITIES = [custody_activity, parse_activity, store_activity, knowledge_activity]
