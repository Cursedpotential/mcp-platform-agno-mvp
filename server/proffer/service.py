"""Canonical ingest orchestration without framework-owned public objects.

The service composes existing custody, parser, and PostgreSQL writers. Optional
projections are downstream and cannot turn a committed canonical ingest into a
failure. SBV's SQLite databases are parser-local resumability state only.

Byline: Codex · GPT-5 · 2026-08-16
Byline amendment: Codex · GPT-5 · 2026-08-18 (source/acquisition clocks and chunk split)
Byline amendment: Codex · GPT-5 · 2026-08-18 (governed message projection transaction)
Byline amendment: Codex · GPT-5 · 2026-08-18 (duplicate acquisition relink)
Byline amendment: Codex · GPT-5 · 2026-08-18 (native vector outbox pending receipt)
Byline amendment: Codex · GPT-5 · 2026-08-29 (startup recovery for incomplete ingests)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, ContextManager, Iterator, Literal, Protocol, cast

from server.contracts.ingest import IngestLane, IngestReceipt, IngestRejection, IngestRequest, ProjectionResult
from server.contracts.records import MessageCorpus, NormalizedRecord, NormalizedRecordChunk, finalize
from server.core.chunking_identity import chunker_id
from server.evidence.custody import ArtifactRef


CHUNKER_ID = chunker_id("recursive", 1500)
_GO_SUFFIXES = frozenset({".xml", ".eml", ".mbox", ".ndjson", ".csv"})
_TEXT_SUFFIXES = frozenset({".md", ".txt"})
_DOCUMENT_SUFFIXES = frozenset({".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm"})
_EVIDENCE_FORBIDDEN_PARSERS = frozenset({"transcripts.markdown", "documents.text-v1"})
_RECOVERY_WORKFLOW = "framework-neutral-ingest"
_RECOVERY_STAGE_NAMES = ("custody", "parse", "store", "projection")
_RECOVERY_MIN_AGE = timedelta(minutes=15)
_RECOVERY_MAX_CANDIDATES = 100
_RECOVERY_SCAN_LIMIT = 1000
_RECOVERY_MAX_CONCURRENCY = 8
_DB_DOMAIN = {
    IngestLane.platform: "platform_design",
    IngestLane.legal: "legal",
    IngestLane.personal_history: "behavioral",
    IngestLane.context: "context",
    IngestLane.evidence: "evidence",
}


class Artifact(Protocol):
    artifact_id: str
    sha256: str
    duplicate: bool
    acquisition_id: str | None
    acquired_at: datetime | None


class ReceiptJournal(Protocol):
    def start(self, request: IngestRequest, path: Path) -> str: ...

    def finish(self, receipt: IngestReceipt, error: str | None = None) -> None: ...


class PostgresReceiptJournal:
    """Persist receipts in the existing durable workflow-run ledger."""

    def start(self, request: IngestRequest, path: Path) -> str:
        from server.evidence.run_ledger import create_run, seed_stages

        receipt_id = create_run(
            workflow="framework-neutral-ingest",
            mode="auto",
            source_name=path.name,
            source_path=str(path),
            domain=request.lane.value,
            custody_tier=request.custody_tier,
            source_context={
                "source_identity": request.source_identity,
                "message_corpus": request.message_corpus,
                "source_principal": request.source_principal,
                "caller_owns_conversation": request.caller_owns_conversation,
                "acquisition": request.acquisition.model_dump(mode="json") if request.acquisition else None,
                "coverage_hint": request.coverage_hint,
                "lane": request.lane.value,
                "classification_target": request.classification_target,
                "matter_id": request.matter_id,
                "engine": request.engine,
                "allow_fallback": request.allow_fallback,
            },
        )
        seed_stages(receipt_id, ["custody", "parse", "store", "projection"])
        return receipt_id

    def stage_start(self, receipt_id: str, seq: int) -> None:
        from server.evidence.run_ledger import stage_start

        stage_start(receipt_id, seq)

    def stage_finish(self, receipt_id: str, seq: int, status: str, output: dict[str, Any]) -> None:
        from server.evidence.run_ledger import stage_finish

        stage_finish(receipt_id, seq, status, output=output)

    def skip_after(self, receipt_id: str, seq: int, detail: str) -> None:
        from server.evidence.run_ledger import skip_remaining_stages

        skip_remaining_stages(receipt_id, from_seq=seq, reason_code="ingest_failed", reason_detail=detail)

    def finish(self, receipt: IngestReceipt, error: str | None = None) -> None:
        from server.evidence.run_ledger import finish_run

        finish_run(
            receipt.receipt_id,
            "completed" if receipt.status == "completed" else "failed",
            summary=receipt.model_dump(mode="json"),
            error=error,
            sha256=receipt.source_sha256,
            artifact_id=receipt.artifact_id,
        )

    @contextmanager
    def run_guard(self, receipt_id: str) -> Iterator[bool]:
        """Hold one session-level PostgreSQL lock for the receipt's execution.

        The same guard is used by freshly submitted and recovered runs. A
        second API replica therefore observes ``False`` instead of executing
        the same durable receipt concurrently. PostgreSQL releases the lock if
        the connection or process dies.
        """
        from sqlalchemy import text

        from server.evidence.run_ledger import _get_engine

        connection = _get_engine().connect()
        key = f"{_RECOVERY_WORKFLOW}:{receipt_id}"
        acquired = False
        try:
            acquired = bool(
                connection.execute(
                    text("SELECT pg_try_advisory_lock(hashtextextended(:key, 0))"),
                    {"key": key},
                ).scalar()
            )
            yield acquired
        finally:
            if acquired:
                connection.execute(
                    text("SELECT pg_advisory_unlock(hashtextextended(:key, 0))"),
                    {"key": key},
                )
            connection.close()


class IngestError(RuntimeError):
    """An ingest failed after a durable receipt ID was allocated."""

    def __init__(self, message: str, receipt: IngestReceipt):
        super().__init__(message)
        self.receipt = receipt


class IngestRunAlreadyActive(RuntimeError):
    """Another process currently owns this durable ingest receipt."""


def _stage_start(journal: ReceiptJournal, receipt_id: str, seq: int) -> None:
    callback = getattr(journal, "stage_start", None)
    if callback is not None:
        callback(receipt_id, seq)


def _stage_finish(journal: ReceiptJournal, receipt_id: str, seq: int, status: str, output: dict[str, Any]) -> None:
    callback = getattr(journal, "stage_finish", None)
    if callback is not None:
        callback(receipt_id, seq, status, output)


ParserEngine = Literal["go", "python", "none"]


def _whole_file_text(
    path: Path, request: IngestRequest
) -> tuple[list[NormalizedRecord], str, Literal["python"], list[dict[str, Any]]]:
    if request.lane is IngestLane.evidence:
        raise ValueError("whole-file text fallback is forbidden for the evidence lane (ADR-0044)")
    if path.suffix.lower() not in _TEXT_SUFFIXES:
        raise ValueError(f"no covered parser for {path.name!r}; supply a supported coverage_hint")
    content = path.read_text(encoding="utf-8")
    record = NormalizedRecord(
        source="documents.text-v1",
        content=content,
        attrs={"source_path": str(path), "source_name": path.name, **request.source_identity},
    )
    return [record], "documents.text-v1", "python", [{"tool": "documents.text-v1", "ok": True}]


def _extract_document(
    path: Path, request: IngestRequest
) -> tuple[list[NormalizedRecord], str, Literal["python"], list[dict[str, Any]]]:
    """Extract a general knowledge document without treating it as a chat export."""
    attempts: list[dict[str, Any]] = []
    extractors: list[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]] = []
    try:
        from server.tools.extractors.docling_extract import extract_docling

        extractors.append(("documents.extract-docling", extract_docling))
    except ImportError:
        pass
    if path.suffix.lower() == ".pdf":
        from server.tools.extractors.extract_text import parse as extract_text

        extractors.append(("documents.extract-text", extract_text))

    for parser_id, extractor in extractors:
        try:
            result = extractor({"path": str(path)})
            content = str(result.get("text") or "").strip()
            if not content:
                raise ValueError("extractor returned no text")
            stats = result.get("stats") if isinstance(result.get("stats"), dict) else {}
            record = NormalizedRecord(
                source=parser_id,
                content=content,
                attrs={
                    "source_path": str(path),
                    "source_name": path.name,
                    "extraction": stats,
                    **request.source_identity,
                },
            )
            attempts.append({"tool": parser_id, "ok": True})
            return [record], parser_id, "python", attempts
        except Exception as error:
            attempts.append({"tool": parser_id, "ok": False, "error": str(error)[:300]})
    detail = "; ".join(str(item.get("error")) for item in attempts) or "no document extractor registered"
    raise ValueError(f"document extraction failed for {path.name!r}: {detail}")


def _parse(
    path: Path, request: IngestRequest
) -> tuple[list[NormalizedRecord], str, Literal["go", "python"], list[dict[str, Any]]]:
    from server.analysis.chat_parse import parse_chat_export

    source_meta = {
        **request.source_identity,
        "source_principal": request.source_principal,
        "message_corpus": request.message_corpus,
    }

    hint = request.coverage_hint
    if request.lane is not IngestLane.evidence and hint is None and path.suffix.lower() in _DOCUMENT_SUFFIXES:
        return _extract_document(path, request)
    if hint is None and path.suffix.lower() == ".xml":
        head = path.read_bytes()[:4096].lower()
        if b"<smses" in head or b"<sms " in head or b"<mms " in head:
            hint = "smsbackuprestore-xml"

    use_go = request.engine == "go" or (hint is None and path.suffix.lower() in _GO_SUFFIXES)
    if hint is not None:
        from server.analysis.format_router import resolve_format_override

        engaged, _go_id, _python_id = resolve_format_override(hint, request.engine)
        use_go = engaged == "go"
    if use_go:
        try:
            records, parser_id, attempts = parse_chat_export(path, source_meta, engine="go", format=hint)
            return records, parser_id, "go", attempts
        except Exception as primary_error:
            if not request.allow_fallback:
                raise
            records, parser_id, attempts = parse_chat_export(path, source_meta, engine="python")
            return (
                records,
                parser_id,
                "python",
                [{"tool": "sbv.go", "ok": False, "error": str(primary_error)}, *attempts],
            )

    try:
        records, parser_id, attempts = parse_chat_export(
            path,
            source_meta,
            engine=request.engine,
            format=hint,
        )
        if request.lane is IngestLane.evidence and parser_id in _EVIDENCE_FORBIDDEN_PARSERS:
            raise ValueError(f"parser {parser_id!r} is forbidden for the evidence lane (ADR-0044)")
        return records, parser_id, "python", attempts
    except Exception:
        return _whole_file_text(path, request)


def _enrich(
    records: list[NormalizedRecord], request: IngestRequest, path: Path, parser_id: str
) -> list[NormalizedRecord]:
    return finalize(
        record.model_copy(
            update={
                "message_corpus": MessageCorpus(request.message_corpus)
                if request.message_corpus
                else record.message_corpus,
                "attrs": {
                    **record.attrs,
                    "lane": request.lane.value,
                    "matter_id": request.matter_id,
                    "source_path": str(path),
                    "source_name": path.name,
                    "parser_id": parser_id,
                    "message_corpus": request.message_corpus,
                    "source_principal": request.source_principal,
                },
            }
        )
        for record in records
    )


def ingest_file(
    request: IngestRequest,
    *,
    journal: ReceiptJournal | None = None,
    receipt_id: str | None = None,
    custody: Callable[..., Artifact] | None = None,
    persist: Callable[..., int] | None = None,
    records_exist: Callable[[str], bool] | None = None,
    projector: Any | None = None,
) -> IngestReceipt:
    """Ingest one staged file under a cross-process receipt guard."""
    path = Path(request.staged_path).resolve(strict=True)
    if not path.is_file():
        raise FileNotFoundError(path)
    journal = journal or PostgresReceiptJournal()
    receipt_id = receipt_id or journal.start(request, path)
    guard_factory = cast(
        Callable[[str], ContextManager[bool]] | None,
        getattr(journal, "run_guard", None),
    )
    guard = guard_factory(receipt_id) if guard_factory is not None else nullcontext(True)
    with guard as acquired:
        if not acquired:
            raise IngestRunAlreadyActive(f"ingest receipt {receipt_id} is already executing")
        return _ingest_file_once(
            request,
            journal=journal,
            receipt_id=receipt_id,
            custody=custody,
            persist=persist,
            records_exist=records_exist,
            projector=projector,
        )


def _ingest_file_once(
    request: IngestRequest,
    *,
    journal: ReceiptJournal,
    receipt_id: str,
    custody: Callable[..., Artifact] | None,
    persist: Callable[..., int] | None,
    records_exist: Callable[[str], bool] | None,
    projector: Any | None,
) -> IngestReceipt:
    """Execute a receipt after its caller has acquired the run guard."""
    path = Path(request.staged_path).resolve(strict=True)
    started = datetime.now(timezone.utc)
    artifact: Artifact | None = None
    parser_id: str | None = None
    parser_engine: ParserEngine = "none"
    attempts: list[dict[str, Any]] = []
    active_stage = 0
    try:
        if custody is None:
            from server.evidence.custody import ingest_artifact

            custody_fn = cast(Callable[..., Artifact], ingest_artifact)
        else:
            custody_fn = custody
        if persist is None:
            from server.evidence.store import records_exist_for_artifact, store_record_batch

            # Use a wrapper that passes retry=True for the framework-neutral ingest path
            # (Temporal activities use store_records which explicitly disables retry)
            def persist_with_retry(
                records: list[NormalizedRecord],
                chunks: list[NormalizedRecordChunk],
                artifact: ArtifactRef,
                *args: Any,
                **kwargs: Any,
            ) -> int:
                return store_record_batch(records, chunks, artifact, *args, retry=True, **kwargs)

            persist_fn = cast(Callable[..., int], persist_with_retry)
            records_exist_fn = records_exist or records_exist_for_artifact
        else:
            persist_fn = persist
            records_exist_fn = records_exist or (lambda _artifact_id: False)

        active_stage = 1
        _stage_start(journal, receipt_id, active_stage)
        artifact = custody_fn(
            path,
            request.source_identity,
            tier=request.custody_tier,
            acquisition=request.acquisition.model_dump(mode="python") if request.acquisition else None,
        )
        _stage_finish(
            journal,
            receipt_id,
            active_stage,
            "success",
            {"artifact_id": artifact.artifact_id, "sha256": artifact.sha256, "duplicate": artifact.duplicate},
        )
        active_stage = 2
        _stage_start(journal, receipt_id, active_stage)
        source_records, parser_id, parser_engine, attempts = _parse(path, request)
        source_records = _enrich(source_records, request, path, parser_id)
        from server.proffer.chunking import chunk_records

        chunked = chunk_records(source_records)
        projection_records = chunked.records
        chunk_count = chunked.chunk_count
        _stage_finish(
            journal,
            receipt_id,
            active_stage,
            "success",
            {
                "parser_id": parser_id,
                "parser_engine": parser_engine,
                "record_count": chunked.source_record_count,
                "chunk_count": chunk_count,
                "chunker_id": chunked.chunker_id,
                "attempts": attempts,
            },
        )
        active_stage = 3
        _stage_start(journal, receipt_id, active_stage)
        canonical_duplicate = artifact.duplicate and records_exist_fn(artifact.artifact_id)
        duplicate_acquisition_links = 0
        if (
            canonical_duplicate
            and persist is None
            and request.message_corpus == "acquired_third_party"
            and artifact.acquisition_id is not None
        ):
            from server.evidence.store import link_duplicate_artifact_acquisition

            duplicate_acquisition_links = link_duplicate_artifact_acquisition(
                artifact,
                asserted_by=request.acquisition.asserted_by if request.acquisition is not None else "owner",
            )
        stored = (
            0
            if canonical_duplicate
            else (
                persist_fn(
                    source_records,
                    chunked.chunks,
                    artifact,
                    case_id=request.matter_id,
                    domain=_DB_DOMAIN[request.lane],
                    projection_request=request,
                )
                if persist is None
                else persist_fn(
                    source_records,
                    artifact,
                    case_id=request.matter_id,
                    domain=_DB_DOMAIN[request.lane],
                )
            )
        )
        _stage_finish(
            journal,
            receipt_id,
            active_stage,
            "skipped" if canonical_duplicate else "success",
            {
                "stored": stored,
                "custody_duplicate": artifact.duplicate,
                "canonical_duplicate": canonical_duplicate,
                "matter_id": request.matter_id,
                "duplicate_acquisition_links": duplicate_acquisition_links,
            },
        )
        active_stage = 4
        _stage_start(journal, receipt_id, active_stage)
        projections: list[ProjectionResult]
        if request.message_corpus == "acquired_third_party":
            projections = [
                ProjectionResult(
                    sink="weaviate",
                    status="skipped",
                    detail="awaiting approved PostgreSQL source_available_from",
                )
            ]
        elif projector is None:
            pending_jobs: int | None = None
            if persist is None and not canonical_duplicate:
                from server.evidence.store import native_projection_jobs_for_artifact

                pending_jobs = native_projection_jobs_for_artifact(artifact.artifact_id)
            if pending_jobs:
                projections = [
                    ProjectionResult(
                        sink="weaviate",
                        status="pending",
                        detail=f"{pending_jobs} native projection job(s) durably enqueued",
                    )
                ]
            elif pending_jobs == 0 and chunk_count:
                projections = [
                    ProjectionResult(
                        sink="weaviate",
                        status="failed",
                        detail="native outbox exists but no projection job was committed",
                    )
                ]
            else:
                projections = [
                    ProjectionResult(
                        sink="weaviate",
                        status="skipped",
                        detail="native outbox not applied or custom persistence path; projector not attached",
                    )
                ]
        else:
            try:
                from server.evidence.vector_projection import NativeEvidenceProjector

                if isinstance(projector, NativeEvidenceProjector):
                    drained = projector.drain()
                    if drained.failed:
                        raise RuntimeError(f"native vector projection failed for {drained.failed} queued chunk(s)")
                    projections = [
                        ProjectionResult(
                            sink="weaviate",
                            status="completed",
                            detail=(
                                f"native outbox drained {drained.completed} chunk(s) "
                                f"({drained.deactivated} authority-deactivated)"
                            ),
                        )
                    ]
                else:
                    detail = projector(projection_records, artifact, request)
                    projections = [ProjectionResult(sink="weaviate", status="completed", detail=detail)]
            except Exception as projection_error:
                projections = [ProjectionResult(sink="weaviate", status="failed", detail=str(projection_error)[:300])]
        projection = projections[0]
        _stage_finish(
            journal,
            receipt_id,
            active_stage,
            "success" if projection.status in {"completed", "pending"} else "skipped",
            projection.model_dump(mode="json"),
        )
        active_stage = 0
        receipt = IngestReceipt(
            receipt_id=receipt_id,
            status="completed",
            lane=request.lane,
            matter_id=request.matter_id,
            source_name=path.name,
            source_path=str(path),
            source_sha256=artifact.sha256,
            artifact_id=artifact.artifact_id,
            duplicate=artifact.duplicate,
            parser_id=parser_id,
            parser_engine=parser_engine,
            chunker_id=chunked.chunker_id,
            record_count=chunked.source_record_count,
            chunk_count=chunk_count,
            attempts=attempts,
            projections=projections,
            started_at=started,
            completed_at=datetime.now(timezone.utc),
        )
        journal.finish(receipt)
        return receipt
    except Exception as error:
        if active_stage:
            try:
                _stage_finish(
                    journal,
                    receipt_id,
                    active_stage,
                    "failed",
                    {"error": str(error)[:500]},
                )
                callback = getattr(journal, "skip_after", None)
                if callback is not None:
                    callback(receipt_id, active_stage, str(error)[:500])
            except Exception:
                pass
        receipt = IngestReceipt(
            receipt_id=receipt_id,
            status="failed",
            lane=request.lane,
            matter_id=request.matter_id,
            source_name=path.name,
            source_path=str(path),
            source_sha256=getattr(artifact, "sha256", None),
            artifact_id=getattr(artifact, "artifact_id", None),
            duplicate=bool(getattr(artifact, "duplicate", False)),
            parser_id=parser_id,
            parser_engine=parser_engine,
            chunker_id=CHUNKER_ID,
            rejections=[IngestRejection(code="ingest_failed", detail=str(error)[:500])],
            attempts=attempts,
            projections=[ProjectionResult(sink="weaviate", status="skipped", detail="canonical ingest failed")],
            started_at=started,
            completed_at=datetime.now(timezone.utc),
        )
        journal.finish(receipt, error=str(error)[:500])
        raise IngestError(str(error), receipt) from error


log = logging.getLogger("ingest.recovery")


def _latest_activity_at(run: dict[str, Any]) -> datetime | None:
    values = [run.get("updated_at"), run.get("created_at")]
    for stage in run.get("stages", []):
        values.extend((stage.get("started_at"), stage.get("finished_at")))
    aware = [value for value in values if isinstance(value, datetime) and value.tzinfo is not None]
    return max(aware) if aware else None


def _eligible_for_recovery(run: dict[str, Any], *, now: datetime, min_age: timedelta) -> bool:
    """Return whether one detailed ledger row is a stale, resumable run."""
    if run.get("workflow") != _RECOVERY_WORKFLOW or run.get("status") != "running":
        return False
    if run.get("gate_state") not in {None, "released"}:
        return False
    stages = run.get("stages")
    if not isinstance(stages, list) or [stage.get("name") for stage in stages] != list(_RECOVERY_STAGE_NAMES):
        return False
    statuses = [stage.get("status") for stage in stages]
    if any(status not in {"pending", "running", "success", "skipped"} for status in statuses):
        return False
    if not any(status in {"pending", "running"} for status in statuses):
        return False
    latest = _latest_activity_at(run)
    return latest is not None and now - latest >= min_age


def _request_from_run(run: dict[str, Any]) -> IngestRequest:
    context = run.get("source_context")
    if not isinstance(context, dict):
        raise ValueError("source_context is not an object")
    source_path = run.get("source_path")
    if not isinstance(source_path, str) or not source_path.strip():
        raise ValueError("source_path is missing")
    return IngestRequest(
        staged_path=source_path,
        source_identity=context.get("source_identity") or {},
        message_corpus=context.get("message_corpus"),
        source_principal=context.get("source_principal"),
        caller_owns_conversation=bool(context.get("caller_owns_conversation", False)),
        acquisition=context.get("acquisition"),
        coverage_hint=context.get("coverage_hint"),
        lane=context.get("lane", "context"),
        classification_target=context.get("classification_target", "context"),
        matter_id=context.get("matter_id", "primary"),
        engine=context.get("engine", "auto"),
        allow_fallback=bool(context.get("allow_fallback", False)),
        custody_tier=run.get("custody_tier", "light"),
    )


def _mark_recovery_unrecoverable(run: dict[str, Any], detail: str) -> None:
    """Terminalize a stale run whose durable inputs cannot be replayed."""
    from server.evidence.run_ledger import finish_run, skip_remaining_stages, stage_finish

    run_id = cast(str, run["run_id"])
    active = next(
        (stage for stage in run["stages"] if stage.get("status") in {"pending", "running"}),
        None,
    )
    if active is not None:
        seq = int(active["seq"])
        stage_finish(
            run_id,
            seq,
            "failed",
            output={"error": detail},
            reason_code="recovery_input_unavailable",
            reason_detail=detail,
        )
        skip_remaining_stages(
            run_id,
            from_seq=seq,
            reason_code="recovery_input_unavailable",
            reason_detail=detail,
        )
    finish_run(
        run_id,
        "failed",
        summary={"recovery": "unrecoverable", "detail": detail},
        error=detail,
    )


async def recover_incomplete_ingests(
    *,
    projector: Any | None = None,
    concurrency: int = 4,
    min_age: timedelta = _RECOVERY_MIN_AGE,
    max_candidates: int = _RECOVERY_MAX_CANDIDATES,
    list_runs_fn: Callable[..., list[dict[str, Any]]] | None = None,
    get_run_fn: Callable[[str], dict[str, Any] | None] | None = None,
    ingest_fn: Callable[..., IngestReceipt] | None = None,
    journal_factory: Callable[[], ReceiptJournal] = PostgresReceiptJournal,
    mark_unrecoverable_fn: Callable[[dict[str, Any], str], None] = _mark_recovery_unrecoverable,
    now: datetime | None = None,
) -> int:
    """Replay stale running ingests with bounded, cross-process-safe workers.

    Paused and terminal runs are never inferred to be recoverable. Each replay
    executes the original receipt ID and request semantics; ``ingest_file``
    supplies the PostgreSQL advisory lock and idempotent custody/store behavior.
    One failure is logged and isolated from the other candidates.
    """
    if not 1 <= concurrency <= _RECOVERY_MAX_CONCURRENCY:
        raise ValueError(f"concurrency must be between 1 and {_RECOVERY_MAX_CONCURRENCY}")
    if min_age < timedelta(0):
        raise ValueError("min_age must not be negative")
    if not 1 <= max_candidates <= _RECOVERY_MAX_CANDIDATES:
        raise ValueError(f"max_candidates must be between 1 and {_RECOVERY_MAX_CANDIDATES}")

    if list_runs_fn is None or get_run_fn is None:
        from server.evidence.run_ledger import get_run, list_runs

        list_runs_fn = list_runs_fn or list_runs
        get_run_fn = get_run_fn or get_run
    execute = ingest_fn or ingest_file
    observed_at = now or datetime.now(timezone.utc)
    if observed_at.tzinfo is None:
        raise ValueError("now must be timezone-aware")

    summaries = await asyncio.to_thread(list_runs_fn, limit=_RECOVERY_SCAN_LIMIT, status="running")
    detailed: list[dict[str, Any]] = []
    for summary in summaries:
        if summary.get("workflow") != _RECOVERY_WORKFLOW:
            continue
        run_id = summary.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            log.warning("Skipping recovery candidate without a run_id")
            continue
        run = await asyncio.to_thread(get_run_fn, run_id)
        if run is not None and _eligible_for_recovery(run, now=observed_at, min_age=min_age):
            detailed.append(run)
            if len(detailed) >= max_candidates:
                break

    semaphore = asyncio.Semaphore(concurrency)

    async def recover_one(run: dict[str, Any]) -> bool:
        run_id = cast(str, run["run_id"])
        try:
            payload = _request_from_run(run)
            path = Path(payload.staged_path).resolve(strict=True)
            if not path.is_file():
                raise FileNotFoundError(path)
            payload = payload.model_copy(update={"staged_path": str(path)})
        except (FileNotFoundError, OSError, ValueError) as error:
            detail = f"durable ingest recovery cannot replay source: {error}"[:500]
            log.error("Ingest recovery %s is not replayable: %s", run_id, error)
            try:
                await asyncio.to_thread(mark_unrecoverable_fn, run, detail)
            except Exception:
                log.exception("Ingest recovery %s could not record its unrecoverable state", run_id)
            return False

        async with semaphore:
            try:
                await asyncio.to_thread(
                    execute,
                    payload,
                    journal=journal_factory(),
                    receipt_id=run_id,
                    projector=projector,
                )
            except IngestRunAlreadyActive:
                log.info("Ingest recovery %s is already owned by another process", run_id)
                return False
            except Exception:
                log.exception("Ingest recovery %s failed", run_id)
                return False
        log.info("Ingest recovery %s completed", run_id)
        return True

    results = await asyncio.gather(*(recover_one(run) for run in detailed))
    return sum(results)
