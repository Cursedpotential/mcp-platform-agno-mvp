"""Governed candidate submission after isolated Semantica extraction.

The worker never imports this module. The PostgreSQL adapter can write only the
existing ``working.extraction_run`` and ``working.candidate_*`` tables. It has
no custody, Neo4j, Weaviate, Surreal, or promotion operation.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import Engine

from server.analysis.semantica_contracts import CandidateBatch, SubmissionReceipt


_RUN_INSERT = """
INSERT INTO working.extraction_run
    (extractor, extractor_version, model_id, source_summary, status, stats)
VALUES
    (:extractor, :extractor_version, NULL, :source_summary, 'running', CAST(:stats AS jsonb))
RETURNING id
"""

_ENTITY_INSERT = """
INSERT INTO working.candidate_entity
    (extraction_run_id, source_raw_table, source_raw_id, entity_type, name,
     normalized_name, confidence, attrs, content_sha256)
VALUES
    (:run_id, :source_raw_table, :source_raw_id, :entity_type, :name,
     :normalized_name, :confidence, CAST(:attrs AS jsonb), :content_sha256)
ON CONFLICT (source_raw_table, source_raw_id, content_sha256) DO NOTHING
RETURNING id
"""

_ENTITY_LOOKUP = """
SELECT id FROM working.candidate_entity
WHERE source_raw_table = :source_raw_table
  AND source_raw_id = :source_raw_id
  AND content_sha256 = :content_sha256
"""

_FACT_INSERT = """
INSERT INTO working.candidate_fact
    (extraction_run_id, source_raw_table, source_raw_id, subject_entity_id,
     object_entity_id, predicate, statement, evidence_quote, confidence, attrs,
     content_sha256)
VALUES
    (:run_id, :source_raw_table, :source_raw_id, :subject_entity_id,
     :object_entity_id, :predicate, :statement, :evidence_quote, :confidence,
     CAST(:attrs AS jsonb), :content_sha256)
ON CONFLICT (source_raw_table, source_raw_id, content_sha256) DO NOTHING
"""

_EVENT_INSERT = """
INSERT INTO working.candidate_event
    (extraction_run_id, source_raw_table, source_raw_id, event_type, summary,
     occurred_at, validity, temporal_confidence, confidence, attrs, content_sha256)
VALUES
    (:run_id, :source_raw_table, :source_raw_id, :event_type, :summary,
     :occurred_at,
     CASE WHEN :valid_from IS NULL THEN NULL
          ELSE tstzrange(:valid_from, :valid_to, '[)') END,
     :temporal_confidence, :confidence, CAST(:attrs AS jsonb), :content_sha256)
ON CONFLICT (source_raw_table, source_raw_id, content_sha256) DO NOTHING
"""

_RUN_COMPLETE = """
UPDATE working.extraction_run
SET status = 'completed', finished_at = now(), stats = CAST(:stats AS jsonb)
WHERE id = :run_id
"""

_RUN_FAILED = """
UPDATE working.extraction_run
SET status = 'failed', finished_at = now(), error = :error, stats = CAST(:stats AS jsonb)
WHERE id = :run_id
"""


class CandidateSubmissionError(RuntimeError):
    """A non-promoting candidate submission failed or was refused."""


def _stats(batch: CandidateBatch) -> dict[str, Any]:
    return {
        "batch_id": batch.batch_id,
        "matter_id": batch.matter_id,
        "source_count": batch.source_count,
        "entity_count": len(batch.entities),
        "fact_count": len(batch.facts),
        "event_count": len(batch.events),
        "rejection_count": len(batch.rejections),
        "failure_count": len(batch.failures),
        "config_sha256": batch.config_sha256,
    }


def _attrs(batch: CandidateBatch, provenance: Any, extra: dict[str, Any] | None = None) -> str:
    payload = {
        "matter_id": batch.matter_id,
        "batch_id": batch.batch_id,
        "provenance": provenance.model_dump(mode="json"),
        **(extra or {}),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


class InMemoryCandidateRepository:
    """Observed disposable sink with the exact canonical table names."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def submit(self, batch: CandidateBatch) -> SubmissionReceipt:
        if not batch.ok:
            raise CandidateSubmissionError("refusing to submit an extraction batch with failures")
        run_id = str(uuid4())
        now = datetime.now(timezone.utc)
        self.tables["working.extraction_run"].append(
            {
                "id": run_id,
                "extractor": batch.extractor,
                "extractor_version": batch.extractor_version,
                "source_summary": batch.batch_id,
                "status": "completed",
                "finished_at": now.isoformat(),
                "stats": _stats(batch),
            }
        )
        entity_ids: dict[str, str] = {}
        for entity_candidate in batch.entities:
            candidate_id = str(uuid4())
            entity_ids[entity_candidate.key] = candidate_id
            provenance = entity_candidate.provenance
            self.tables["working.candidate_entity"].append(
                {
                    "id": candidate_id,
                    "extraction_run_id": run_id,
                    "source_raw_table": provenance.source_raw_table,
                    "source_raw_id": provenance.source_raw_id,
                    "entity_type": entity_candidate.entity_type,
                    "name": entity_candidate.name,
                    "normalized_name": entity_candidate.normalized_name,
                    "confidence": entity_candidate.confidence,
                    "attrs": json.loads(_attrs(batch, provenance, {"candidate_key": entity_candidate.key})),
                    "content_sha256": entity_candidate.content_sha256,
                    "review_state": "pending",
                }
            )
        for fact_candidate in batch.facts:
            provenance = fact_candidate.provenance
            self.tables["working.candidate_fact"].append(
                {
                    "id": str(uuid4()),
                    "extraction_run_id": run_id,
                    "source_raw_table": provenance.source_raw_table,
                    "source_raw_id": provenance.source_raw_id,
                    "subject_entity_id": entity_ids.get(fact_candidate.subject_key),
                    "object_entity_id": entity_ids.get(fact_candidate.object_key),
                    "predicate": fact_candidate.predicate,
                    "statement": fact_candidate.statement,
                    "evidence_quote": provenance.evidence_quote,
                    "confidence": fact_candidate.confidence,
                    "attrs": json.loads(
                        _attrs(
                            batch,
                            provenance,
                            {
                                "candidate_key": fact_candidate.key,
                                "subject_key": fact_candidate.subject_key,
                                "object_key": fact_candidate.object_key,
                            },
                        )
                    ),
                    "content_sha256": fact_candidate.content_sha256,
                    "review_state": "pending",
                }
            )
        for event_candidate in batch.events:
            provenance = event_candidate.provenance
            self.tables["working.candidate_event"].append(
                {
                    "id": str(uuid4()),
                    "extraction_run_id": run_id,
                    "source_raw_table": provenance.source_raw_table,
                    "source_raw_id": provenance.source_raw_id,
                    "event_type": event_candidate.event_type,
                    "summary": event_candidate.summary,
                    "occurred_at": event_candidate.occurred_at,
                    "valid_from": event_candidate.valid_from,
                    "valid_to": event_candidate.valid_to,
                    "temporal_confidence": event_candidate.temporal_confidence,
                    "confidence": event_candidate.confidence,
                    "attrs": json.loads(_attrs(batch, provenance, {"candidate_key": event_candidate.key})),
                    "content_sha256": event_candidate.content_sha256,
                    "review_state": "pending",
                }
            )
        return SubmissionReceipt(
            run_id=run_id,
            batch_id=batch.batch_id,
            status="completed",
            entity_count=len(batch.entities),
            fact_count=len(batch.facts),
            event_count=len(batch.events),
        )


class PostgresCandidateRepository:
    """Host-side PostgreSQL adapter; an Engine is injected outside the worker."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def submit(self, batch: CandidateBatch) -> SubmissionReceipt:
        if not batch.ok:
            raise CandidateSubmissionError("refusing to submit an extraction batch with failures")
        stats = _stats(batch)
        with self._engine.begin() as connection:
            run_id = connection.execute(
                text(_RUN_INSERT),
                {
                    "extractor": batch.extractor,
                    "extractor_version": batch.extractor_version,
                    "source_summary": f"batch={batch.batch_id}; sources={batch.source_count}",
                    "stats": json.dumps(stats),
                },
            ).scalar_one()

        try:
            entity_ids: dict[str, Any] = {}
            with self._engine.begin() as connection:
                for entity_candidate in batch.entities:
                    provenance = entity_candidate.provenance
                    params = {
                        "run_id": run_id,
                        "source_raw_table": provenance.source_raw_table,
                        "source_raw_id": provenance.source_raw_id,
                        "entity_type": entity_candidate.entity_type,
                        "name": entity_candidate.name,
                        "normalized_name": entity_candidate.normalized_name,
                        "confidence": entity_candidate.confidence,
                        "attrs": _attrs(batch, provenance, {"candidate_key": entity_candidate.key}),
                        "content_sha256": bytes.fromhex(entity_candidate.content_sha256),
                    }
                    entity_id = connection.execute(text(_ENTITY_INSERT), params).scalar_one_or_none()
                    if entity_id is None:
                        entity_id = connection.execute(text(_ENTITY_LOOKUP), params).scalar_one()
                    entity_ids[entity_candidate.key] = entity_id

                for fact_candidate in batch.facts:
                    provenance = fact_candidate.provenance
                    connection.execute(
                        text(_FACT_INSERT),
                        {
                            "run_id": run_id,
                            "source_raw_table": provenance.source_raw_table,
                            "source_raw_id": provenance.source_raw_id,
                            "subject_entity_id": entity_ids.get(fact_candidate.subject_key),
                            "object_entity_id": entity_ids.get(fact_candidate.object_key),
                            "predicate": fact_candidate.predicate,
                            "statement": fact_candidate.statement,
                            "evidence_quote": provenance.evidence_quote,
                            "confidence": fact_candidate.confidence,
                            "attrs": _attrs(
                                batch,
                                provenance,
                                {
                                    "candidate_key": fact_candidate.key,
                                    "subject_key": fact_candidate.subject_key,
                                    "object_key": fact_candidate.object_key,
                                },
                            ),
                            "content_sha256": bytes.fromhex(fact_candidate.content_sha256),
                        },
                    )

                for event_candidate in batch.events:
                    provenance = event_candidate.provenance
                    connection.execute(
                        text(_EVENT_INSERT),
                        {
                            "run_id": run_id,
                            "source_raw_table": provenance.source_raw_table,
                            "source_raw_id": provenance.source_raw_id,
                            "event_type": event_candidate.event_type,
                            "summary": event_candidate.summary,
                            "occurred_at": event_candidate.occurred_at,
                            "valid_from": event_candidate.valid_from,
                            "valid_to": event_candidate.valid_to,
                            "temporal_confidence": event_candidate.temporal_confidence,
                            "confidence": event_candidate.confidence,
                            "attrs": _attrs(batch, provenance, {"candidate_key": event_candidate.key}),
                            "content_sha256": bytes.fromhex(event_candidate.content_sha256),
                        },
                    )
                connection.execute(text(_RUN_COMPLETE), {"run_id": run_id, "stats": json.dumps(stats)})
        except Exception as error:
            with self._engine.begin() as connection:
                connection.execute(
                    text(_RUN_FAILED),
                    {"run_id": run_id, "error": str(error)[:1000], "stats": json.dumps(stats)},
                )
            raise CandidateSubmissionError(f"candidate submission failed for run {run_id}") from error

        return SubmissionReceipt(
            run_id=str(run_id),
            batch_id=batch.batch_id,
            status="completed",
            entity_count=len(batch.entities),
            fact_count=len(batch.facts),
            event_count=len(batch.events),
        )


def submitted_tables() -> frozenset[str]:
    """Machine-checkable write allowlist for the host submission adapter."""
    return frozenset(
        {
            "working.extraction_run",
            "working.candidate_entity",
            "working.candidate_fact",
            "working.candidate_event",
        }
    )
