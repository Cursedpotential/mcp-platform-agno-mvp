"""Native evidence projection outbox and retrieval contract tests.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from server.core.evidence_vector_store import EVIDENCE_EMBED_DIM, NativeEvidenceVectorStore
from server.evidence.retrieval import native_evidence_search
from server.evidence.vector_projection import NativeEvidenceProjector
from server.core.native_evidence_runtime import create_native_evidence_runtime, run_native_projection_worker
from server.evidence.vector_projection import ProjectionDrainResult


def test_projector_rejects_wrong_model_or_dimension() -> None:
    with pytest.raises(ValueError, match="nvidia/nv-embed-v1"):
        NativeEvidenceProjector(
            object(), MagicMock(), lambda text: [], embed_model="other", embedder_version="v1", worker_id="w"
        )
    with pytest.raises(ValueError, match="4096"):
        NativeEvidenceProjector(
            object(),
            MagicMock(),
            lambda text: [],
            embed_dimension=1024,
            embedder_version="v1",
            worker_id="w",
        )


def test_native_retrieval_passes_permission_tiers_to_prefilter_and_audits() -> None:
    query = MagicMock()
    query.hybrid.return_value = SimpleNamespace(objects=[SimpleNamespace(properties={"chunk_id": "c1"})])
    client = MagicMock()
    client.collections.use.return_value = SimpleNamespace(query=query)
    store = NativeEvidenceVectorStore(client)
    captured = {}

    result = native_evidence_search(
        store,
        lambda text: [0.1] * EVIDENCE_EMBED_DIM,
        "gaslighting",
        horizon=datetime(2024, 7, 1, tzinfo=timezone.utc),
        actor="ignorant-agent",
        disclosure_tiers=["contemporaneous", "discovered"],
        audit=lambda *args, **kwargs: captured.update(kwargs) or 91,
    )

    assert result.kept == 1 and result.audit_id == 91
    filters = query.hybrid.call_args.kwargs["filters"].filters
    assert filters[0].target == "case_id"
    assert filters[2].target == "authority_state" and filters[2].value == "active"
    assert filters[3].target == "source_available_from"
    assert captured["ctx"]["disclosure_tiers"] == ["contemporaneous", "discovered"]


def test_native_retrieval_rejects_empty_permission_tiers() -> None:
    client = MagicMock()
    client.collections.use.return_value = SimpleNamespace(query=MagicMock())
    store = NativeEvidenceVectorStore(client)
    with pytest.raises(ValueError, match="permission-derived"):
        native_evidence_search(
            store,
            lambda text: [0.1] * EVIDENCE_EMBED_DIM,
            "query",
            horizon=datetime.now(timezone.utc),
            actor="agent",
            disclosure_tiers=[],
        )


def test_held_sql_defines_durable_outbox_and_authority_requeue() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = (root / "sql/0026_realization_event.sql").read_text(encoding="utf-8")
    grants = (root / "sql/0029_pass_grants.sql").read_text(encoding="utf-8")

    assert "working.evidence_vector_projection_job" in migration
    assert "working.enqueue_evidence_vector_projection" in migration
    assert "evidence_vector_route_enqueue" in migration
    assert "evidence_vector_acquisition_enqueue" in migration
    assert "generation BIGINT NOT NULL DEFAULT 0" in migration
    assert "generation=working.evidence_vector_projection_job.generation+1" in migration
    assert "FOR UPDATE SKIP LOCKED" in Path(root / "server/evidence/vector_projection.py").read_text(encoding="utf-8")
    projector_source = Path(root / "server/evidence/vector_projection.py").read_text(encoding="utf-8")
    assert "job.locked_by=:worker AND job.generation=:generation" in projector_source
    assert "working.evidence_vector_projection_job" in grants


def test_production_runtime_separates_alias_reader_from_versioned_writer() -> None:
    client = MagicMock()
    engine = MagicMock()
    runtime = create_native_evidence_runtime(
        weaviate_client=client,
        engine=engine,
        embedding_client=MagicMock(),
        worker_id="test-worker",
        validate_activation=False,
    )

    assert client.collections.use.call_args_list[0].args == ("EvidenceChunks",)
    assert client.collections.use.call_args_list[1].args == ("EvidenceChunkV1",)
    assert runtime.projector is not None


def test_projection_worker_drains_on_startup_and_stops_cleanly() -> None:
    class Runtime:
        calls = 0

        def drain(self, *, limit: int):
            self.calls += 1
            return ProjectionDrainResult(0, 0, 0, 0)

    async def scenario() -> None:
        runtime = Runtime()
        stop = asyncio.Event()
        task = asyncio.create_task(run_native_projection_worker(runtime, stop, idle_interval_s=60, error_backoff_s=60))
        while runtime.calls == 0:
            await asyncio.sleep(0)
        stop.set()
        await asyncio.wait_for(task, timeout=1)
        assert runtime.calls == 1

    asyncio.run(scenario())


def test_projection_worker_retries_after_failure() -> None:
    class Runtime:
        calls = 0

        def drain(self, *, limit: int):
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("temporary")
            return ProjectionDrainResult(0, 0, 0, 0)

    async def scenario() -> None:
        runtime = Runtime()
        stop = asyncio.Event()
        task = asyncio.create_task(
            run_native_projection_worker(runtime, stop, idle_interval_s=60, error_backoff_s=0.001)
        )
        while runtime.calls < 2:
            await asyncio.sleep(0.001)
        stop.set()
        await asyncio.wait_for(task, timeout=1)

    asyncio.run(scenario())
