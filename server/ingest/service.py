"""Canonical ingest orchestration without framework-owned public objects.

The service composes existing custody, parser, and PostgreSQL writers. Optional
projections are downstream and cannot turn a committed canonical ingest into a
failure. SBV's SQLite databases are parser-local resumability state only.

Byline: Codex · GPT-5 · 2026-08-16
Byline amendment: Codex · GPT-5 · 2026-08-18 (source/acquisition clocks and chunk split)
Byline amendment: Codex · GPT-5 · 2026-08-18 (governed message projection transaction)
Byline amendment: Codex · GPT-5 · 2026-08-18 (duplicate acquisition relink)
Byline amendment: Codex · GPT-5 · 2026-08-18 (native vector outbox pending receipt)
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Literal, Protocol, cast

from server.contracts.ingest import IngestLane, IngestReceipt, IngestRejection, IngestRequest, ProjectionResult
from server.contracts.records import MessageCorpus, NormalizedRecord, finalize
from server.core.chunking_identity import chunker_id


CHUNKER_ID = chunker_id("recursive", 1500)
_GO_SUFFIXES = frozenset({".xml", ".eml", ".mbox", ".ndjson", ".csv"})
_TEXT_SUFFIXES = frozenset({".md", ".txt"})
_DOCUMENT_SUFFIXES = frozenset({".pdf", ".docx", ".pptx", ".xlsx", ".html", ".htm"})
_EVIDENCE_FORBIDDEN_PARSERS = frozenset({"transcripts.markdown", "documents.text-v1"})
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
                "acquisition": request.acquisition.model_dump(mode="json") if request.acquisition else None,
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


class IngestError(RuntimeError):
    """An ingest failed after a durable receipt ID was allocated."""

    def __init__(self, message: str, receipt: IngestReceipt):
        super().__init__(message)
        self.receipt = receipt


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
    """Ingest one staged file and return its durable receipt."""
    path = Path(request.staged_path).resolve(strict=True)
    if not path.is_file():
        raise FileNotFoundError(path)
    journal = journal or PostgresReceiptJournal()
    receipt_id = receipt_id or journal.start(request, path)
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

            persist_fn = cast(Callable[..., int], store_record_batch)
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
        from server.ingest.chunking import chunk_records

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
