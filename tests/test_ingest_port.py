"""Contract tests for the framework-neutral canonical ingest port.

Byline: Codex · GPT-5 · 2026-08-16
Byline amendment: Codex · GPT-5 · 2026-08-18 (authored records vs derived chunks)
Byline amendment: Codex · GPT-5 · 2026-08-18 (native projection outbox receipt)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest

from server.contracts.ingest import AcquisitionAssertion, IngestLane, IngestRequest
from server.contracts.records import NormalizedRecord
from server.ingest import service


@dataclass
class _Artifact:
    artifact_id: str = "artifact-1"
    sha256: str = "a" * 64
    duplicate: bool = False
    acquisition_id: str | None = None
    acquired_at: object | None = None


class _Journal:
    def __init__(self) -> None:
        self.finished = []
        self.stages = []

    def start(self, request: IngestRequest, path: Path) -> str:
        return "receipt-1"

    def finish(self, receipt, error: str | None = None) -> None:
        self.finished.append((receipt, error))

    def stage_start(self, receipt_id: str, seq: int) -> None:
        self.stages.append(("start", seq, None))

    def stage_finish(self, receipt_id: str, seq: int, status: str, output: dict) -> None:
        self.stages.append(("finish", seq, status))

    def skip_after(self, receipt_id: str, seq: int, detail: str) -> None:
        self.stages.append(("skip_after", seq, detail))


def _request(path: Path, **updates) -> IngestRequest:
    values = {"staged_path": str(path), "lane": IngestLane.platform, **updates}
    return IngestRequest(**values)


def test_acquired_third_party_requires_acquisition_and_source_principal(tmp_path: Path) -> None:
    source = tmp_path / "friends.json"
    source.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="acquisition assertion"):
        _request(source, message_corpus="acquired_third_party", source_principal="alex")
    with pytest.raises(ValueError, match="source account/device principal"):
        _request(
            source,
            message_corpus="acquired_third_party",
            acquisition=AcquisitionAssertion(acquired_at=datetime(2025, 3, 4, 12, tzinfo=timezone.utc)),
        )


def test_enrichment_keeps_acquisition_separate_from_occurrence(tmp_path: Path) -> None:
    source = tmp_path / "friends.json"
    source.write_text("{}", encoding="utf-8")
    request = _request(
        source,
        lane=IngestLane.evidence,
        message_corpus="acquired_third_party",
        source_principal="alex",
        acquisition=AcquisitionAssertion(acquired_at=datetime(2025, 3, 4, 12, tzinfo=timezone.utc)),
    )
    occurred = datetime(2023, 1, 2, tzinfo=timezone.utc)
    record = service._enrich(
        [NormalizedRecord(source="fixture", occurred_at=occurred, sender="alex", participants=["alex", "jordan"])],
        request,
        source,
        "fixture",
    )[0]
    assert record.occurred_at == occurred
    assert record.message_corpus.value == "acquired_third_party"
    assert "acquired_at" not in record.attrs
    assert "owner" not in record.participants


def test_public_ingest_modules_have_no_framework_imports() -> None:
    root = Path(__file__).resolve().parents[1]
    combined = "\n".join(
        (root / relative).read_text(encoding="utf-8")
        for relative in (
            "server/contracts/ingest.py",
            "server/ingest/service.py",
            "server/api/ingest_routes.py",
        )
    ).lower()
    for forbidden in ("import agno", "import graphiti", "import surreal", "vercel", "ai_sdk"):
        assert forbidden not in combined


def test_whole_file_fallback_is_unreachable_from_evidence(tmp_path: Path) -> None:
    source = tmp_path / "note.md"
    source.write_text("not evidence", encoding="utf-8")
    with pytest.raises(ValueError, match="forbidden for the evidence lane"):
        service._whole_file_text(source, _request(source, lane=IngestLane.evidence))


def test_projection_failure_does_not_fail_canonical_ingest(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "knowledge.md"
    source.write_text("canonical text", encoding="utf-8")
    journal = _Journal()
    persisted = []
    projected = []

    monkeypatch.setattr(
        service,
        "_parse",
        lambda path, request: (
            [NormalizedRecord(source="documents.text-v1", content="canonical text")],
            "documents.text-v1",
            "python",
            [{"tool": "documents.text-v1", "ok": True}],
        ),
    )

    def persist(records, artifact, **kwargs):
        persisted.append((records, artifact, kwargs))
        return len(records)

    def failed_projection(records, artifact, request):
        projected.extend(records)
        raise RuntimeError("vector unavailable")

    receipt = service.ingest_file(
        _request(source, matter_id="matter-a"),
        journal=journal,
        custody=lambda *args, **kwargs: _Artifact(),
        persist=persist,
        projector=failed_projection,
    )

    assert receipt.status == "completed"
    assert receipt.parser_id == "documents.text-v1"
    assert receipt.chunker_id == service.CHUNKER_ID
    assert receipt.record_count == 1
    assert receipt.chunk_count == 1
    assert "chunker_id" not in persisted[0][0][0].attrs
    assert projected[0].attrs["chunker_id"] == service.CHUNKER_ID
    assert projected[0].attrs["derived_materialization"] == "normalized-record-chunk"
    assert receipt.projections[0].status == "failed"
    assert persisted[0][2] == {"case_id": "matter-a", "domain": "platform_design"}
    assert journal.finished[0][0].status == "completed"
    assert [(event[0], event[1], event[2]) for event in journal.stages] == [
        ("start", 1, None),
        ("finish", 1, "success"),
        ("start", 2, None),
        ("finish", 2, "success"),
        ("start", 3, None),
        ("finish", 3, "success"),
        ("start", 4, None),
        ("finish", 4, "skipped"),
    ]


def test_acquired_third_party_vector_projection_waits_for_pg_approval(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "friends.json"
    source.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        service,
        "_parse",
        lambda path, request: (
            [NormalizedRecord(source="fixture", content="message")],
            "fixture",
            "python",
            [],
        ),
    )
    projected = []
    receipt = service.ingest_file(
        _request(
            source,
            message_corpus="acquired_third_party",
            source_principal="source-account",
            acquisition=AcquisitionAssertion(acquired_at=datetime(2025, 3, 4, tzinfo=timezone.utc)),
        ),
        journal=_Journal(),
        custody=lambda *args, **kwargs: _Artifact(
            acquisition_id="22222222-2222-2222-2222-222222222222",
            acquired_at=datetime(2025, 3, 4, tzinfo=timezone.utc),
        ),
        persist=lambda records, artifact, **kwargs: len(records),
        projector=lambda records, artifact, request: projected.extend(records) or "should not run",
    )
    assert projected == []
    assert receipt.projections[0].status == "skipped"
    assert receipt.projections[0].detail == "awaiting approved PostgreSQL source_available_from"


def test_default_store_receives_projection_request_for_same_transaction(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "thread.txt"
    source.write_text("fixture", encoding="utf-8")
    request = _request(
        source,
        message_corpus="first_party",
        source_principal="source-account",
        caller_owns_conversation=True,
    )
    monkeypatch.setattr(
        service,
        "_parse",
        lambda path, ingest_request: (
            [
                NormalizedRecord(
                    source="fixture",
                    sender="source-account",
                    recipients=[{"identity": "friend", "role": "to"}],
                    message_corpus="first_party",
                )
            ],
            "fixture",
            "python",
            [],
        ),
    )
    captured = {}

    def fake_store(records, chunks, artifact, **kwargs):
        captured.update(kwargs)
        return len(records)

    monkeypatch.setattr("server.evidence.store.store_record_batch", fake_store)
    monkeypatch.setattr("server.evidence.store.records_exist_for_artifact", lambda artifact_id: False)
    monkeypatch.setattr("server.evidence.store.native_projection_jobs_for_artifact", lambda artifact_id: 1)
    receipt = service.ingest_file(
        request,
        journal=_Journal(),
        custody=lambda *args, **kwargs: _Artifact(),
    )
    assert captured["projection_request"] is request
    assert receipt.projections[0].status == "pending"
    assert receipt.projections[0].detail == "1 native projection job(s) durably enqueued"


def test_pre_0026_default_ingest_keeps_legacy_projection_skip(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "pre-outbox.txt"
    source.write_text("fixture", encoding="utf-8")
    monkeypatch.setattr(
        service,
        "_parse",
        lambda path, request: ([NormalizedRecord(source="fixture", content="message")], "fixture", "python", []),
    )
    monkeypatch.setattr("server.evidence.store.store_record_batch", lambda *args, **kwargs: 1)
    monkeypatch.setattr("server.evidence.store.records_exist_for_artifact", lambda artifact_id: False)
    monkeypatch.setattr("server.evidence.store.native_projection_jobs_for_artifact", lambda artifact_id: None)

    receipt = service.ingest_file(
        _request(source),
        journal=_Journal(),
        custody=lambda *args, **kwargs: _Artifact(),
    )

    assert receipt.projections[0].status == "skipped"
    assert "native outbox not applied" in (receipt.projections[0].detail or "")


def test_receipt_reports_logical_records_and_actual_chonkie_chunks(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "long-knowledge.md"
    source.write_text("fixture", encoding="utf-8")
    content = "Alpha beta gamma. Delta epsilon zeta. " * 1000
    monkeypatch.setattr(
        service,
        "_parse",
        lambda path, request: (
            [NormalizedRecord(source="documents.text-v1", content=content)],
            "documents.text-v1",
            "python",
            [],
        ),
    )
    persisted = []
    projected = []

    def persist(records, artifact, **kwargs):
        persisted.extend(records)
        return len(records)

    receipt = service.ingest_file(
        _request(source),
        journal=_Journal(),
        custody=lambda *args, **kwargs: _Artifact(),
        persist=persist,
        projector=lambda records, artifact, request: projected.extend(records) or "ok",
    )

    assert receipt.record_count == 1
    assert len(persisted) == receipt.record_count == 1
    assert receipt.chunk_count == len(projected) > 1
    assert receipt.chunker_id == "chonkie.recursive@1.7.0:1500-chars"
    assert [record.attrs["chunk_index"] for record in projected] == list(range(len(projected)))


def test_duplicate_artifact_does_not_duplicate_postgres_rows(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "knowledge.md"
    source.write_text("same bytes", encoding="utf-8")
    monkeypatch.setattr(
        service,
        "_parse",
        lambda path, request: (
            [NormalizedRecord(source="documents.text-v1", content="same bytes")],
            "documents.text-v1",
            "python",
            [],
        ),
    )

    def should_not_persist(*args, **kwargs):
        raise AssertionError("duplicate artifact reached canonical insert")

    receipt = service.ingest_file(
        _request(source),
        journal=_Journal(),
        custody=lambda *args, **kwargs: _Artifact(duplicate=True),
        persist=should_not_persist,
        records_exist=lambda artifact_id: True,
    )
    assert receipt.duplicate is True
    assert receipt.record_count == 1


def test_custody_duplicate_without_canonical_rows_is_recovered(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "knowledge.md"
    source.write_text("same bytes", encoding="utf-8")
    monkeypatch.setattr(
        service,
        "_parse",
        lambda path, request: (
            [NormalizedRecord(source="documents.text-v1", content="same bytes")],
            "documents.text-v1",
            "python",
            [],
        ),
    )
    persisted = []

    def persist(records, artifact, **kwargs):
        persisted.extend(records)
        return len(records)

    receipt = service.ingest_file(
        _request(source),
        journal=_Journal(),
        custody=lambda *args, **kwargs: _Artifact(duplicate=True),
        persist=persist,
        records_exist=lambda artifact_id: False,
    )

    assert receipt.status == "completed"
    assert receipt.duplicate is True
    assert receipt.record_count == 1
    assert len(persisted) == 1


def test_duplicate_third_party_adds_acquisition_link_without_rewriting(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "friends.json"
    source.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        service,
        "_parse",
        lambda path, request: ([NormalizedRecord(source="fixture", content="same")], "fixture", "python", []),
    )
    linked = []
    monkeypatch.setattr(
        "server.evidence.store.link_duplicate_artifact_acquisition",
        lambda artifact, *, asserted_by: linked.append((artifact.acquisition_id, asserted_by)) or 2,
    )
    monkeypatch.setattr("server.evidence.store.records_exist_for_artifact", lambda artifact_id: True)
    receipt = service.ingest_file(
        _request(
            source,
            message_corpus="acquired_third_party",
            source_principal="source-account",
            acquisition=AcquisitionAssertion(acquired_at=datetime(2025, 3, 4, tzinfo=timezone.utc)),
        ),
        journal=_Journal(),
        custody=lambda *args, **kwargs: _Artifact(
            duplicate=True,
            acquisition_id="new-acquisition-id",
            acquired_at=datetime(2025, 3, 4, tzinfo=timezone.utc),
        ),
    )
    assert receipt.record_count == 1
    assert linked == [("new-acquisition-id", "owner")]


def test_explicit_sbv_coverage_uses_go(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sms.xml"
    source.write_text("<smses count='0'></smses>", encoding="utf-8")
    seen = {}

    def fake_parse(path, source_meta, *, engine, format):
        seen.update(engine=engine, format=format)
        return [NormalizedRecord(source="sbv-go", content="message")], "sbv.smsbackuprestore-xml", []

    monkeypatch.setattr("server.analysis.chat_parse.parse_chat_export", fake_parse)
    records, parser_id, parser_engine, _attempts = service._parse(
        source,
        _request(source, lane=IngestLane.evidence, coverage_hint="smsbackuprestore-xml", custody_tier="full"),
    )
    assert len(records) == 1
    assert parser_id == "sbv.smsbackuprestore-xml"
    assert parser_engine == "go"
    assert seen == {"engine": "go", "format": "smsbackuprestore-xml"}


def test_general_pdf_uses_document_extractor_not_chat_parser(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "brief.pdf"
    source.write_bytes(b"%PDF synthetic fixture")
    monkeypatch.setattr(
        "server.tools.extractors.docling_extract.extract_docling",
        lambda payload: {"text": "extracted brief", "stats": {"method": "fixture"}},
    )

    records, parser_id, parser_engine, attempts = service._parse(source, _request(source))

    assert records[0].content == "extracted brief"
    assert parser_id == "documents.extract-docling"
    assert parser_engine == "python"
    assert attempts == [{"tool": "documents.extract-docling", "ok": True}]


def test_canonical_failure_finishes_a_failed_receipt(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "knowledge.md"
    source.write_text("canonical text", encoding="utf-8")
    journal = _Journal()
    monkeypatch.setattr(
        service,
        "_parse",
        lambda path, request: (
            [NormalizedRecord(source="documents.text-v1", content="canonical text")],
            "documents.text-v1",
            "python",
            [],
        ),
    )

    with pytest.raises(service.IngestError) as caught:
        service.ingest_file(
            _request(source),
            journal=journal,
            custody=lambda *args, **kwargs: _Artifact(),
            persist=lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("postgres unavailable")),
        )

    assert caught.value.receipt.status == "failed"
    assert caught.value.receipt.rejections[0].code == "ingest_failed"
    assert journal.finished[0][0].status == "failed"
    assert journal.finished[0][1] == "postgres unavailable"
    assert journal.stages[-2] == ("finish", 3, "failed")
    assert journal.stages[-1][0:2] == ("skip_after", 3)
