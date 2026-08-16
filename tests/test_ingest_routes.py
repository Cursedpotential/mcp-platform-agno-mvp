"""HTTP and folder-walk tests for the framework-neutral ingest boundary.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.api import ingest_routes
from server.contracts.ingest import IngestLane, IngestReceipt, IngestRequest, ProjectionResult


def _receipt(request: IngestRequest) -> IngestReceipt:
    now = datetime.now(timezone.utc)
    return IngestReceipt(
        receipt_id="receipt-1",
        status="completed",
        lane=request.lane,
        matter_id=request.matter_id,
        source_name=Path(request.staged_path).name,
        source_path=request.staged_path,
        source_sha256="a" * 64,
        artifact_id="artifact-1",
        parser_id="documents.text-v1",
        parser_engine="python",
        chunker_id="chonkie.recursive@1.7.0:1500-chars",
        record_count=1,
        chunk_count=1,
        projections=[ProjectionResult(sink="weaviate", status="skipped")],
        started_at=now,
        completed_at=now,
    )


def test_upload_route_stages_safely_and_returns_compatible_receipt(tmp_path, monkeypatch) -> None:
    seen: list[IngestRequest] = []
    monkeypatch.setenv("INGEST_STAGING_ROOT", str(tmp_path))
    monkeypatch.setenv("OS_SECURITY_KEY", "test-ingest-key")

    async def fake_submit(request: IngestRequest):
        seen.append(request)
        return "receipt-1"

    monkeypatch.setattr(ingest_routes, "_submit_ingest", fake_submit)
    app = FastAPI()
    ingest_routes.register_ingest_routes(app)
    response = TestClient(app).post(
        "/v1/ingest",
        files={"file": ("../../knowledge.md", b"canonical", "text/markdown")},
        data={
            "lane": "legal",
            "matter_id": "matter-a",
            "source_identity": '{"doc_type":"brief"}',
        },
        headers={"Authorization": "Bearer test-ingest-key"},
    )

    assert response.status_code == 202
    assert response.json()["run_id"] == "receipt-1"
    assert response.json()["status"] == "running"
    assert seen[0].lane is IngestLane.legal
    assert seen[0].source_identity == {"doc_type": "brief", "original_name": "knowledge.md"}
    assert Path(seen[0].staged_path).parent == tmp_path.resolve()
    assert Path(seen[0].staged_path).name.endswith("-knowledge.md")
    assert Path(seen[0].staged_path).read_bytes() == b"canonical"


def test_upload_route_rejects_non_object_source_identity(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("INGEST_STAGING_ROOT", str(tmp_path))
    monkeypatch.setenv("OS_SECURITY_KEY", "test-ingest-key")
    app = FastAPI()
    ingest_routes.register_ingest_routes(app)
    response = TestClient(app).post(
        "/v1/ingest",
        files={"file": ("knowledge.md", b"canonical", "text/markdown")},
        data={"source_identity": "[]"},
        headers={"Authorization": "Bearer test-ingest-key"},
    )
    assert response.status_code == 422


def test_ingest_and_knowledge_routes_fail_closed_without_bearer(monkeypatch) -> None:
    monkeypatch.setenv("OS_SECURITY_KEY", "test-ingest-key")
    app = FastAPI()
    ingest_routes.register_ingest_routes(app)
    client = TestClient(app)
    assert client.post("/v1/ingest").status_code == 401
    assert client.get("/v1/knowledge/items").status_code == 401


def test_ingest_routes_fail_closed_when_key_is_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("OS_SECURITY_KEY", raising=False)
    app = FastAPI()
    ingest_routes.register_ingest_routes(app)
    response = TestClient(app).get("/v1/knowledge/items", headers={"Authorization": "Bearer anything"})
    assert response.status_code == 503


def test_async_submission_reserves_receipt_before_worker(tmp_path, monkeypatch) -> None:
    source = tmp_path / "knowledge.md"
    source.write_text("canonical", encoding="utf-8")
    payload = IngestRequest(staged_path=str(source))
    seen = []

    class _Journal:
        def start(self, request, path):
            seen.append(("reserved", request, path))
            return "receipt-async"

    async def fake_worker(request, journal, receipt_id):
        seen.append(("worker", request, receipt_id))

    monkeypatch.setattr(ingest_routes, "PostgresReceiptJournal", _Journal)
    monkeypatch.setattr(ingest_routes, "_run_reserved_ingest", fake_worker)

    async def submit_and_wait():
        receipt_id = await ingest_routes._submit_ingest(payload)
        await asyncio.gather(*tuple(ingest_routes._INGEST_TASKS))
        return receipt_id

    assert asyncio.run(submit_and_wait()) == "receipt-async"
    assert [event[0] for event in seen] == ["reserved", "worker"]
    assert seen[0][2] == source.resolve()


def test_folder_walk_calls_neutral_port_without_framework_object(tmp_path, monkeypatch) -> None:
    from scripts import ingest_knowledge
    from server.ingest import service

    platform = tmp_path / "platform"
    platform.mkdir()
    (platform / "canon.md").write_text("horizon", encoding="utf-8")
    monkeypatch.setattr(ingest_knowledge, "KNOWLEDGE_ROOTS", {"platform": platform})
    seen: list[IngestRequest] = []

    def fake_ingest(request: IngestRequest):
        seen.append(request)
        return _receipt(request)

    monkeypatch.setattr(service, "ingest_file", fake_ingest)
    assert asyncio.run(ingest_knowledge.ingest_all()) == 1
    assert len(seen) == 1
    assert seen[0].lane is IngestLane.platform
    assert seen[0].source_identity["doc_type"] == "platform"


def test_folder_walk_source_has_no_agno_insert() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts/ingest_knowledge.py").read_text(encoding="utf-8")
    assert ".ainsert(" not in source
    assert "create_knowledge(" not in source
