"""Observed governed Semantica extraction and candidate submission tests.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

import ast
from contextlib import contextmanager
import json
from pathlib import Path
from typing import Any, Iterator
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from server.analysis.semantica_candidates import (
    CandidateSubmissionError,
    InMemoryCandidateRepository,
    PostgresCandidateRepository,
    submitted_tables,
)
from server.analysis.semantica_contracts import CandidateBatch, ExtractionBatch, ExtractionFailure
from server.analysis.semantica_worker import SemanticaPatternWorker
from server.vendored.semantica.semantica.semantic_extract.ner_extractor import Entity
from server.vendored.semantica.semantica.semantic_extract.relation_extractor import Relation


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/semantica_phase1_batch.json"


def _fixture() -> ExtractionBatch:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document.pop("_byline")
    return ExtractionBatch.model_validate(document)


def test_real_vendored_semantica_emits_candidates_and_provenance() -> None:
    result = SemanticaPatternWorker().extract(_fixture())

    assert result.ok is True
    assert result.extractor == "semantica"
    assert result.extractor_version.startswith("vendored-0.3.0-alpha+")
    assert len(result.entities) == 4
    assert {candidate.predicate for candidate in result.facts} == {"founded_by", "acquired_by"}
    assert len(result.events) == 1
    assert result.events[0].event_type == "acquisition"
    assert result.events[0].occurred_at is None
    assert result.events[0].valid_from is not None
    assert result.events[0].valid_from.year == 2024
    assert result.events[0].valid_to is not None
    assert result.events[0].valid_to.year == 2025
    assert all(candidate.predicate != "related_to" for candidate in result.facts)

    all_candidates = (*result.entities, *result.facts, *result.events)
    assert all(candidate.provenance.source_content_sha256 for candidate in all_candidates)
    assert all(candidate.provenance.source_provenance_ref.startswith("fixture://") for candidate in all_candidates)
    assert all(candidate.provenance.config_sha256 == result.config_sha256 for candidate in all_candidates)
    assert {rejection.reason for rejection in result.rejections} == {"non_identity_entity"}


def test_fixture_replay_is_deterministic() -> None:
    worker = SemanticaPatternWorker()
    first = worker.extract(_fixture()).model_dump(mode="json")
    second = worker.extract(_fixture()).model_dump(mode="json")
    assert first == second


def test_batch_is_immutable_horizon_blind_and_hash_attested() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document.pop("_byline")
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ExtractionBatch.model_validate({**document, "horizon_context": {"as_of": "2030-01-01"}})

    document["records"][0]["content"] += " tampered"
    with pytest.raises(ValidationError, match="content_sha256 does not match"):
        ExtractionBatch.model_validate(document)


def test_fabricated_adjacency_causes_visible_batch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from server.analysis import semantica_worker as module

    subject = Entity("Alpha", "ORG", 0, 5, 0.3)
    object_ = Entity("Beta", "ORG", 6, 10, 0.3)
    fabricated = Relation(
        subject=subject,
        predicate="related_to",
        object=object_,
        confidence=0.3,
        metadata={"extraction_method": "last_resort_adjacency"},
    )
    monkeypatch.setattr(module._methods, "extract_relations_pattern", lambda *_args, **_kwargs: [fabricated])

    result = SemanticaPatternWorker().extract(_fixture())

    assert result.ok is False
    assert len(result.failures) == 2
    assert all("fabricated adjacency" in failure.error for failure in result.failures)
    with pytest.raises(CandidateSubmissionError, match="failures"):
        InMemoryCandidateRepository().submit(result)


def test_disposable_submission_populates_only_named_pending_candidate_tables() -> None:
    result = SemanticaPatternWorker().extract(_fixture())
    repository = InMemoryCandidateRepository()

    receipt = repository.submit(result)

    assert receipt.status == "completed"
    assert set(repository.tables) == submitted_tables()
    assert len(repository.tables["working.extraction_run"]) == 1
    assert len(repository.tables["working.candidate_entity"]) == 4
    assert len(repository.tables["working.candidate_fact"]) == 2
    assert len(repository.tables["working.candidate_event"]) == 1
    candidate_rows = (
        repository.tables["working.candidate_entity"]
        + repository.tables["working.candidate_fact"]
        + repository.tables["working.candidate_event"]
    )
    assert all(row["review_state"] == "pending" for row in candidate_rows)
    assert all(row["attrs"]["provenance"]["source_raw_id"] for row in candidate_rows)
    assert all(
        row["subject_entity_id"] and row["object_entity_id"] for row in repository.tables["working.candidate_fact"]
    )


class _ScalarResult:
    def __init__(self, value: UUID | None = None) -> None:
        self.value = value

    def scalar_one(self) -> UUID:
        assert self.value is not None
        return self.value

    def scalar_one_or_none(self) -> UUID | None:
        return self.value


class _RecordingConnection:
    def __init__(self, calls: list[tuple[str, dict[str, Any]]], run_id: UUID) -> None:
        self.calls = calls
        self.run_id = run_id

    def execute(self, statement: Any, params: dict[str, Any]) -> _ScalarResult:
        sql = str(statement)
        self.calls.append((sql, params))
        if "INSERT INTO working.extraction_run" in sql:
            return _ScalarResult(self.run_id)
        if "INSERT INTO working.candidate_entity" in sql:
            return _ScalarResult(uuid4())
        return _ScalarResult()


class _RecordingEngine:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.run_id = uuid4()

    @contextmanager
    def begin(self) -> Iterator[_RecordingConnection]:
        yield _RecordingConnection(self.calls, self.run_id)


def test_postgres_adapter_executes_only_working_candidate_allowlist() -> None:
    engine = _RecordingEngine()
    receipt = PostgresCandidateRepository(engine).submit(SemanticaPatternWorker().extract(_fixture()))  # type: ignore[arg-type]

    assert receipt.run_id == str(engine.run_id)
    sql = "\n".join(statement for statement, _ in engine.calls).lower()
    assert "working.extraction_run" in sql
    assert "working.candidate_entity" in sql
    assert "working.candidate_fact" in sql
    assert "working.candidate_event" in sql
    for forbidden in ("evidence.", "analysis.", "neo4j", "weaviate", "surreal", "promotion"):
        assert forbidden not in sql


def test_worker_source_has_no_persistence_provider_or_projection_door() -> None:
    worker_source = (ROOT / "server/analysis/semantica_worker.py").read_text(encoding="utf-8").lower()
    contract_source = (ROOT / "server/analysis/semantica_contracts.py").read_text(encoding="utf-8").lower()
    imported: set[str] = set()
    for source in (worker_source, contract_source):
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
    for forbidden in ("sqlalchemy", "server.core.session", "neo4j", "weaviate", "surrealdb", "agno", "graphiti"):
        assert all(not module.startswith(forbidden) for module in imported)
    assert "server.vendored.semantica" not in contract_source
    assert "horizon_context" not in ExtractionBatch.model_fields
    assert "api_key" not in worker_source
    assert "database_url" not in worker_source


def test_repository_refuses_explicit_failed_batch() -> None:
    result = SemanticaPatternWorker().extract(_fixture())
    failed = result.model_copy(
        update={"failures": (ExtractionFailure(source_raw_id="fixture-record-1", stage="ner", error="boom"),)}
    )
    assert isinstance(failed, CandidateBatch)
    with pytest.raises(CandidateSubmissionError):
        InMemoryCandidateRepository().submit(failed)
