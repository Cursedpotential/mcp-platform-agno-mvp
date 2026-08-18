"""Durable PostgreSQL-outbox projector into native Weaviate evidence vectors.

PostgreSQL remains projection authority.  Every drain re-evaluates
``working.source_available_from(record_id)``; handoff timestamps are never
trusted as authority.  No Agno knowledge object participates in this path.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, Sequence

from sqlalchemy import text

from server.core.evidence_vector_store import (
    EVIDENCE_EMBED_DIM,
    EVIDENCE_EMBED_MODEL,
    EVIDENCE_PROJECTION_VERSION,
    EvidenceVectorDocument,
    NativeEvidenceVectorStore,
)


class EvidenceEmbedder(Protocol):
    """Injected embedding boundary; implementations must fail, never return None."""

    def __call__(self, content: str) -> Sequence[float]: ...


@dataclass(frozen=True, slots=True)
class ProjectionDrainResult:
    claimed: int
    completed: int
    deactivated: int
    failed: int


class ProjectionLeaseLost(RuntimeError):
    """The outbox generation/owner changed while an external write ran."""


def enqueue_projection_records(connection: Any, record_ids: Sequence[str], *, reason: str) -> int:
    """Atomically enqueue all chunks for records when the HELD function exists.

    The existence guard preserves pre-migration compatibility.  Once migration
    0026 is applied, missing queue writes are errors rather than silent no-ops.
    """

    ids = sorted(set(record_ids))
    if not ids:
        return 0
    available = connection.execute(
        text("SELECT to_regprocedure('working.enqueue_evidence_vector_projection(uuid[],text)') IS NOT NULL")
    ).scalar_one()
    if not available:
        return 0
    return int(
        connection.execute(
            text("SELECT working.enqueue_evidence_vector_projection(CAST(:record_ids AS uuid[]), :reason)"),
            {"record_ids": ids, "reason": reason},
        ).scalar_one()
    )


class NativeEvidenceProjector:
    """Explicit drain worker for the durable evidence-vector projection queue."""

    def __init__(
        self,
        engine: Any,
        store: NativeEvidenceVectorStore,
        embed: EvidenceEmbedder,
        *,
        embed_model: str = EVIDENCE_EMBED_MODEL,
        embed_dimension: int = EVIDENCE_EMBED_DIM,
        embedder_version: str,
        worker_id: str,
    ) -> None:
        if embed_model != EVIDENCE_EMBED_MODEL:
            raise ValueError(f"native evidence projection requires {EVIDENCE_EMBED_MODEL}")
        if embed_dimension != EVIDENCE_EMBED_DIM:
            raise ValueError(f"native evidence projection requires {EVIDENCE_EMBED_DIM} dimensions")
        if not embedder_version or not worker_id:
            raise ValueError("embedder_version and worker_id are required")
        self._engine = engine
        self._store = store
        self._embed = embed
        self._embed_model = embed_model
        self._embed_dimension = embed_dimension
        self._embedder_version = embedder_version
        self._worker_id = worker_id

    def drain(self, *, limit: int = 100, reason: str | None = None) -> ProjectionDrainResult:
        """Claim a bounded batch and project each job with durable outcomes."""

        if limit < 1:
            raise ValueError("limit must be positive")
        job_ids = self._claim(limit, reason=reason)
        completed = deactivated = failed = 0
        for job_id, generation in job_ids:
            try:
                active = self._project(job_id, generation)
                completed += 1
                deactivated += int(not active)
            except Exception as exc:
                failed += 1
                self._fail(job_id, generation, exc)
        return ProjectionDrainResult(len(job_ids), completed, deactivated, failed)

    def enqueue(self, record_ids: Sequence[str], *, reason: str) -> int:
        """Explicit retry/handoff enqueue using the durable PostgreSQL function."""

        with self._engine.begin() as connection:
            return enqueue_projection_records(connection, record_ids, reason=reason)

    def source_projection_exists(self, source_sha256: str) -> bool:
        """Return whether a structured custody-source projection is present."""

        return bool(self._store.find_by_source_sha256(source_sha256, limit=1).objects)

    def _claim(self, limit: int, *, reason: str | None = None) -> list[tuple[str, int]]:
        with self._engine.begin() as connection:
            return [
                (str(row["id"]), int(row["generation"]))
                for row in connection.execute(
                    text(
                        "WITH claim AS (SELECT id FROM working.evidence_vector_projection_job "
                        "WHERE ((status IN ('pending','failed') AND next_attempt_at<=now()) "
                        "OR (status='processing' AND locked_at<now()-interval '15 minutes')) "
                        "AND (:reason IS NULL OR reason=:reason) "
                        "ORDER BY created_at, id FOR UPDATE SKIP LOCKED LIMIT :limit) "
                        "UPDATE working.evidence_vector_projection_job job SET status='processing', "
                        "locked_at=now(), locked_by=:worker, attempts=job.attempts+1, updated_at=now() "
                        "FROM claim WHERE job.id=claim.id RETURNING job.id, job.generation"
                    ),
                    {"limit": limit, "worker": self._worker_id, "reason": reason},
                ).mappings()
            ]

    def _project(self, job_id: str, generation: int) -> bool:
        with self._engine.connect() as connection:
            row = (
                connection.execute(
                    text(
                        "SELECT job.id AS job_id, chunk.id AS chunk_id, chunk.normalized_record_id, "
                        "nr.artifact_id, encode(custody.digest,'hex') AS source_sha256, "
                        "nr.case_id, nr.disclosure_tier, nr.occurred_at, nr.conversation_id, "
                        "COALESCE(nr.message_corpus,'authored_evidence') AS source_kind, "
                        "COALESCE(route.projection_kind,'normalized_record_chunk') AS projection_kind, "
                        "route.decision_state, working.source_available_from(nr.id) AS source_available_from, "
                        "chunk.chunker_id, chunk.content, encode(chunk.content_sha256,'hex') AS content_hash, "
                        "encode(chunk.source_content_sha256,'hex') AS source_content_hash "
                        "FROM working.evidence_vector_projection_job job "
                        "JOIN working.normalized_record_chunk chunk ON chunk.id=job.chunk_id "
                        "JOIN working.normalized_record nr ON nr.id=chunk.normalized_record_id "
                        "JOIN evidence.evidence_hash custody ON custody.id=nr.artifact_id "
                        "LEFT JOIN working.message_projection_route route ON route.normalized_record_id=nr.id "
                        "WHERE job.id=CAST(:job_id AS uuid) AND job.status='processing' "
                        "AND job.locked_by=:worker AND job.generation=:generation"
                    ),
                    {"job_id": job_id, "worker": self._worker_id, "generation": generation},
                )
                .mappings()
                .first()
            )
        if row is None:
            raise ProjectionLeaseLost(f"projection lease lost for job {job_id}")

        available = row["source_available_from"]
        if available is None:
            self._store.deactivate(str(row["chunk_id"]), authority_state="revoked")
            if not self._complete(job_id, generation, authority_state="revoked", projection_hash=None):
                raise ProjectionLeaseLost(f"projection lease lost while deactivating job {job_id}")
            return False

        vector = self._embed(str(row["content"]))
        if vector is None or len(vector) != self._embed_dimension:
            actual = "none" if vector is None else str(len(vector))
            raise RuntimeError(
                f"embedder {self._embedder_version} returned dimension {actual}; expected {self._embed_dimension}"
            )
        projection_hash = _projection_hash(row, available, self._embedder_version)
        document = EvidenceVectorDocument(
            chunk_id=str(row["chunk_id"]),
            artifact_id=str(row["artifact_id"]),
            source_sha256=str(row["source_sha256"]),
            case_id=str(row["case_id"]),
            disclosure_tier=str(row["disclosure_tier"]),  # type: ignore[arg-type]
            source_kind=str(row["source_kind"]),
            projection_kind=str(row["projection_kind"]),
            authority_state="active",
            source_available_from=available,
            normalized_record_id=str(row["normalized_record_id"]),
            chunker_id=str(row["chunker_id"]),
            embed_model=self._embed_model,
            embed_dimension=self._embed_dimension,
            embedder_version=self._embedder_version,
            projection_version=EVIDENCE_PROJECTION_VERSION,
            projection_hash=projection_hash,
            content_hash=str(row["content_hash"]),
            source_content_hash=str(row["source_content_hash"]),
            content=str(row["content"]),
            vector=vector,
            occurred_at=row["occurred_at"],
            conversation_id=str(row["conversation_id"]) if row["conversation_id"] else None,
        )
        if not self._lease_current(job_id, generation):
            raise ProjectionLeaseLost(f"projection lease changed before write for job {job_id}")
        self._store.replace(document)
        if not self._complete(job_id, generation, authority_state="active", projection_hash=projection_hash):
            self._store.deactivate(str(row["chunk_id"]), authority_state="revoked")
            raise ProjectionLeaseLost(f"projection lease changed during write for job {job_id}")
        return True

    def _lease_current(self, job_id: str, generation: int) -> bool:
        with self._engine.connect() as connection:
            return bool(
                connection.execute(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM working.evidence_vector_projection_job "
                        "WHERE id=CAST(:job_id AS uuid) AND status='processing' "
                        "AND locked_by=:worker AND generation=:generation)"
                    ),
                    {"job_id": job_id, "worker": self._worker_id, "generation": generation},
                ).scalar_one()
            )

    def _complete(self, job_id: str, generation: int, *, authority_state: str, projection_hash: str | None) -> bool:
        with self._engine.begin() as connection:
            changed = connection.execute(
                text(
                    "UPDATE working.evidence_vector_projection_job SET status='completed', "
                    "authority_state=:authority_state, projection_hash=:projection_hash, "
                    "completed_at=now(), last_error=NULL, locked_at=NULL, locked_by=NULL, updated_at=now() "
                    "WHERE id=CAST(:job_id AS uuid) AND status='processing' "
                    "AND locked_by=:worker AND generation=:generation"
                ),
                {
                    "job_id": job_id,
                    "authority_state": authority_state,
                    "projection_hash": projection_hash,
                    "worker": self._worker_id,
                    "generation": generation,
                },
            ).rowcount
        return changed == 1

    def _fail(self, job_id: str, generation: int, exc: Exception) -> None:
        with self._engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE working.evidence_vector_projection_job SET status='failed', "
                    "last_error=:error, next_attempt_at=now()+"
                    "(LEAST(attempts,10)*interval '1 minute'), locked_at=NULL, locked_by=NULL, updated_at=now() "
                    "WHERE id=CAST(:job_id AS uuid) AND status='processing' "
                    "AND locked_by=:worker AND generation=:generation"
                ),
                {
                    "job_id": job_id,
                    "error": str(exc)[:1000],
                    "worker": self._worker_id,
                    "generation": generation,
                },
            )


def _projection_hash(row: Any, available: datetime, embedder_version: str) -> str:
    payload = json.dumps(
        {
            "chunk_id": str(row["chunk_id"]),
            "normalized_record_id": str(row["normalized_record_id"]),
            "content_hash": str(row["content_hash"]),
            "source_available_from": available.isoformat(),
            "disclosure_tier": str(row["disclosure_tier"]),
            "source_kind": str(row["source_kind"]),
            "projection_kind": str(row["projection_kind"]),
            "chunker_id": str(row["chunker_id"]),
            "embed_model": EVIDENCE_EMBED_MODEL,
            "embed_dimension": EVIDENCE_EMBED_DIM,
            "embedder_version": embedder_version,
            "projection_version": EVIDENCE_PROJECTION_VERSION,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
