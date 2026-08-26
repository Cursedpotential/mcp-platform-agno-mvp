"""Resumable operator workflow for activating native evidence vectors.

Every mutating phase is explicit.  Collection creation, frozen-watermark
enqueue, drain, reconciliation/canaries, and alias creation are separate
commands so a crash can resume without guessing which gate completed.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from uuid import UUID, uuid4

from sqlalchemy import text
from weaviate.classes.query import Filter

from server.core.evidence_vector_store import (
    EVIDENCE_EMBED_DIM,
    EVIDENCE_PROJECTION_VERSION,
    EVIDENCE_VECTOR_ALIAS,
    EVIDENCE_VECTOR_COLLECTION,
    ensure_evidence_vector_collection,
    validate_evidence_vector_activation,
    validate_evidence_vector_collection,
)

ACTIVATION_REASON_PREFIX = "native-evidence-activation:"
MANIFEST_FIELDS = (
    "chunk_id",
    "artifact_id",
    "source_sha256",
    "case_id",
    "disclosure_tier",
    "source_kind",
    "projection_kind",
    "authority_state",
    "source_availability_complete",
    "source_available_from",
    "normalized_record_id",
    "conversation_id",
    "chunker_id",
    "embed_model",
    "embed_dimension",
    "embedder_version",
    "projection_version",
    "projection_hash",
    "content_hash",
    "source_content_hash",
    "observed_content_sha256",
    "vector_dimension",
)


@dataclass(frozen=True, slots=True)
class ActivationState:
    """Frozen backfill boundary and durable queue identity."""

    activation_id: str
    reason: str
    watermark: str
    projection_version: str
    eligible_chunks: int
    queued_chunks: int


def create_collection(client: Any) -> dict[str, Any]:
    """Create or validate the inactive versioned collection."""

    created = ensure_evidence_vector_collection(client)
    validate_evidence_vector_collection(client)
    return {"collection": EVIDENCE_VECTOR_COLLECTION, "created": created, "validated": True}


def enqueue_frozen_backfill(engine: Any, *, state_path: Path) -> ActivationState:
    """Enqueue every eligible chunk at one frozen database timestamp.

    Re-running with the same state file is read-only and returns the exact
    original boundary.  The queue reason is the resumable cursor identity.
    """

    if state_path.exists():
        return _read_state(state_path)
    activation_id = str(uuid4())
    reason = f"{ACTIVATION_REASON_PREFIX}{activation_id}"
    with engine.begin() as connection:
        watermark = connection.execute(text("SELECT transaction_timestamp() AT TIME ZONE 'UTC'")).scalar_one()
        if watermark.tzinfo is None:
            watermark = watermark.replace(tzinfo=timezone.utc)
        eligible = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM working.normalized_record_chunk chunk "
                    "JOIN working.normalized_record nr ON nr.id=chunk.normalized_record_id "
                    "WHERE chunk.derived_at<=:watermark "
                    "AND working.source_available_from(nr.id) IS NOT NULL"
                ),
                {"watermark": watermark},
            ).scalar_one()
        )
        queued = int(
            connection.execute(
                text(
                    "INSERT INTO working.evidence_vector_projection_job"
                    "(chunk_id,projection_version,reason,status,next_attempt_at,updated_at) "
                    "SELECT chunk.id,:projection_version,:reason,'pending',now(),now() "
                    "FROM working.normalized_record_chunk chunk "
                    "JOIN working.normalized_record nr ON nr.id=chunk.normalized_record_id "
                    "WHERE chunk.derived_at<=:watermark "
                    "AND working.source_available_from(nr.id) IS NOT NULL "
                    "ON CONFLICT (chunk_id,projection_version) DO UPDATE SET "
                    "reason=EXCLUDED.reason,status='pending',generation="
                    "working.evidence_vector_projection_job.generation+1,next_attempt_at=now(),"
                    "locked_at=NULL,locked_by=NULL,completed_at=NULL,last_error=NULL,updated_at=now() "
                    "RETURNING 1"
                ),
                {
                    "watermark": watermark,
                    "projection_version": EVIDENCE_PROJECTION_VERSION,
                    "reason": reason,
                },
            ).rowcount
        )
        if queued != eligible:
            raise RuntimeError(f"frozen enqueue mismatch: eligible={eligible}, queued={queued}")
    state = ActivationState(
        activation_id=activation_id,
        reason=reason,
        watermark=_timestamp(watermark),
        projection_version=EVIDENCE_PROJECTION_VERSION,
        eligible_chunks=eligible,
        queued_chunks=queued,
    )
    _write_json(state_path, {"byline": _byline(), **asdict(state)})
    return state


def drain_frozen_backfill(
    engine: Any,
    projector: Any,
    *,
    state: ActivationState,
    batch_limit: int = 100,
    retry_failed_now: bool = False,
) -> dict[str, int]:
    """Drain only this activation's queue and stop on durable failures."""

    if batch_limit < 1:
        raise ValueError("batch_limit must be positive")
    if retry_failed_now:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE working.evidence_vector_projection_job SET next_attempt_at=now(),updated_at=now() "
                    "WHERE reason=:reason AND status='failed'"
                ),
                {"reason": state.reason},
            )
    totals = {"claimed": 0, "completed": 0, "deactivated": 0, "failed": 0}
    while True:
        result = projector.drain(limit=batch_limit, reason=state.reason)
        for key in totals:
            totals[key] += int(getattr(result, key))
        if result.claimed == 0:
            break
    statuses = _queue_statuses(engine, state.reason)
    incomplete = sum(value for key, value in statuses.items() if key != "completed")
    if incomplete:
        raise RuntimeError(f"activation queue is not complete: {statuses}")
    if statuses.get("completed", 0) != state.eligible_chunks:
        raise RuntimeError(
            f"activation completion count mismatch: expected={state.eligible_chunks}, statuses={statuses}"
        )
    return {**totals, **{f"status_{key}": value for key, value in statuses.items()}}


def reconcile(
    engine: Any,
    client: Any,
    *,
    state: ActivationState,
    output_dir: Path,
) -> dict[str, Any]:
    """Emit independent PG and Weaviate manifests and require exact parity."""

    validate_evidence_vector_collection(client)
    pg_rows = _postgres_manifest(engine, state)
    vector_rows = _weaviate_manifest(client)
    pg_hash = _manifest_hash(pg_rows)
    vector_hash = _manifest_hash(vector_rows)
    passed = (
        len(pg_rows) == state.eligible_chunks
        and len(pg_rows) == len(vector_rows)
        and pg_hash == vector_hash
        and all(row["vector_dimension"] == EVIDENCE_EMBED_DIM for row in vector_rows)
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "postgres-manifest.json", {"byline": _byline(), "rows": pg_rows})
    _write_json(output_dir / "weaviate-manifest.json", {"byline": _byline(), "rows": vector_rows})
    receipt = {
        "byline": _byline(),
        "activation_id": state.activation_id,
        "watermark": state.watermark,
        "collection": EVIDENCE_VECTOR_COLLECTION,
        "postgres_count": len(pg_rows),
        "weaviate_count": len(vector_rows),
        "postgres_manifest_sha256": pg_hash,
        "weaviate_manifest_sha256": vector_hash,
        "passed": passed,
    }
    _write_json(output_dir / "reconciliation.json", receipt)
    if not passed:
        raise RuntimeError(f"native evidence reconciliation failed: {receipt}")
    return receipt


def run_canaries(engine: Any, client: Any, *, state: ActivationState, output_path: Path) -> dict[str, Any]:
    """Execute exact-object horizon, case, and disclosure-tier leakage canaries."""

    validate_evidence_vector_collection(client)
    samples = _postgres_canary_samples(engine, state)
    if not samples:
        raise RuntimeError("cannot run native evidence canaries without an eligible active chunk")
    collection = client.collections.use(EVIDENCE_VECTOR_COLLECTION)
    results: list[dict[str, Any]] = []
    for row in samples:
        available = row["source_available_from"]
        common = [
            Filter.by_property("chunk_id").equal(UUID(row["chunk_id"])),
            Filter.by_property("authority_state").equal("active"),
            Filter.by_property("source_availability_complete").equal(True),
        ]
        visible = _count(
            collection,
            [
                *common,
                Filter.by_property("case_id").equal(row["case_id"]),
                Filter.by_property("disclosure_tier").equal(row["disclosure_tier"]),
                Filter.by_property("source_available_from").less_or_equal(available),
            ],
        )
        hidden_before = _count(
            collection,
            [
                *common,
                Filter.by_property("case_id").equal(row["case_id"]),
                Filter.by_property("disclosure_tier").equal(row["disclosure_tier"]),
                Filter.by_property("source_available_from").less_or_equal(available - timedelta(microseconds=1)),
            ],
        )
        wrong_case = _count(collection, [*common, Filter.by_property("case_id").equal("__canary_wrong_case__")])
        wrong_tier = _count(
            collection,
            [*common, Filter.by_property("disclosure_tier").equal(_different_tier(row["disclosure_tier"]))],
        )
        passed = visible == 1 and hidden_before == 0 and wrong_case == 0 and wrong_tier == 0
        results.append(
            {
                "source_kind": row["source_kind"],
                "chunk_id": row["chunk_id"],
                "visible_at_boundary": visible,
                "hidden_before_boundary": hidden_before,
                "wrong_case": wrong_case,
                "wrong_tier": wrong_tier,
                "passed": passed,
            }
        )
    receipt = {
        "byline": _byline(),
        "activation_id": state.activation_id,
        "collection": EVIDENCE_VECTOR_COLLECTION,
        "results": results,
        "passed": all(item["passed"] for item in results),
    }
    _write_json(output_path, receipt)
    if not receipt["passed"]:
        raise RuntimeError(f"native evidence canaries failed: {receipt}")
    return receipt


def create_and_verify_alias(client: Any, *, reconciliation_path: Path, canary_path: Path) -> dict[str, Any]:
    """Create the stable alias only after both receipts prove successful."""

    reconciliation = _read_json(reconciliation_path)
    canaries = _read_json(canary_path)
    if not reconciliation.get("passed") or reconciliation.get("collection") != EVIDENCE_VECTOR_COLLECTION:
        raise RuntimeError("valid successful reconciliation receipt is required before alias creation")
    if not canaries.get("passed") or canaries.get("activation_id") != reconciliation.get("activation_id"):
        raise RuntimeError("matching successful canary receipt is required before alias creation")
    validate_evidence_vector_collection(client)
    alias = client.alias.get(alias_name=EVIDENCE_VECTOR_ALIAS)
    if alias is None:
        client.alias.create(alias_name=EVIDENCE_VECTOR_ALIAS, target_collection=EVIDENCE_VECTOR_COLLECTION)
    elif alias.collection != EVIDENCE_VECTOR_COLLECTION:
        raise RuntimeError(f"refusing to repoint existing {EVIDENCE_VECTOR_ALIAS} alias from {alias.collection!r}")
    validate_evidence_vector_activation(client)
    return {"alias": EVIDENCE_VECTOR_ALIAS, "collection": EVIDENCE_VECTOR_COLLECTION, "verified": True}


def _queue_statuses(engine: Any, reason: str) -> dict[str, int]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT status,count(*)::int AS count FROM working.evidence_vector_projection_job "
                "WHERE reason=:reason GROUP BY status ORDER BY status"
            ),
            {"reason": reason},
        ).mappings()
        return {str(row["status"]): int(row["count"]) for row in rows}


def _postgres_manifest(engine: Any, state: ActivationState) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT chunk.id AS chunk_id,nr.artifact_id,encode(custody.digest,'hex') AS source_sha256,"
                "nr.case_id,nr.disclosure_tier,COALESCE(nr.message_corpus,'authored_evidence') AS source_kind,"
                "COALESCE(route.projection_kind,'normalized_record_chunk') AS projection_kind,"
                "job.authority_state,TRUE AS source_availability_complete,"
                "working.source_available_from(nr.id) AS source_available_from,nr.id AS normalized_record_id,"
                "nr.conversation_id,chunk.chunker_id,'nvidia/nv-embed-v1' AS embed_model,"
                ":dimension AS embed_dimension,:embedder_version AS embedder_version,"
                "job.projection_version,job.projection_hash,encode(chunk.content_sha256,'hex') AS content_hash,"
                "encode(chunk.source_content_sha256,'hex') AS source_content_hash,chunk.content "
                "FROM working.evidence_vector_projection_job job "
                "JOIN working.normalized_record_chunk chunk ON chunk.id=job.chunk_id "
                "JOIN working.normalized_record nr ON nr.id=chunk.normalized_record_id "
                "JOIN evidence.evidence_hash custody ON custody.id=nr.artifact_id "
                "LEFT JOIN working.message_projection_route route ON route.normalized_record_id=nr.id "
                "WHERE job.reason=:reason AND chunk.derived_at<=:watermark AND job.status='completed' "
                "AND job.authority_state='active' AND working.source_available_from(nr.id) IS NOT NULL "
                "ORDER BY chunk.id"
            ),
            {
                "reason": state.reason,
                "watermark": _parse_timestamp(state.watermark),
                "dimension": EVIDENCE_EMBED_DIM,
                "embedder_version": "nvidia/nv-embed-v1@openai-compatible-v1",
            },
        ).mappings()
        return [_canonical_manifest_row(row, vector_dimension=EVIDENCE_EMBED_DIM) for row in rows]


def _weaviate_manifest(client: Any) -> list[dict[str, Any]]:
    collection = client.collections.use(EVIDENCE_VECTOR_COLLECTION)
    rows = []
    for obj in collection.iterator(include_vector=True, return_properties=list(MANIFEST_FIELDS[:-2]) + ["content"]):
        vector = obj.vector.get("default", []) if isinstance(obj.vector, Mapping) else obj.vector
        rows.append(_canonical_manifest_row(obj.properties, vector_dimension=len(vector or [])))
    return sorted(rows, key=lambda row: row["chunk_id"])


def _postgres_canary_samples(engine: Any, state: ActivationState) -> list[dict[str, Any]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT DISTINCT ON (COALESCE(nr.message_corpus,'authored_evidence')) "
                "chunk.id AS chunk_id,nr.case_id,nr.disclosure_tier,"
                "COALESCE(nr.message_corpus,'authored_evidence') AS source_kind,"
                "working.source_available_from(nr.id) AS source_available_from "
                "FROM working.evidence_vector_projection_job job "
                "JOIN working.normalized_record_chunk chunk ON chunk.id=job.chunk_id "
                "JOIN working.normalized_record nr ON nr.id=chunk.normalized_record_id "
                "WHERE job.reason=:reason AND job.status='completed' AND job.authority_state='active' "
                "AND working.source_available_from(nr.id) IS NOT NULL "
                "ORDER BY COALESCE(nr.message_corpus,'authored_evidence'),chunk.id"
            ),
            {"reason": state.reason},
        ).mappings()
        return [{**dict(row), "chunk_id": str(row["chunk_id"])} for row in rows]


def _count(collection: Any, predicates: list[Any]) -> int:
    result = collection.query.fetch_objects(filters=Filter.all_of(predicates), limit=2, return_properties=["chunk_id"])
    return len(result.objects)


def _canonical_manifest_row(row: Mapping[str, Any], *, vector_dimension: int) -> dict[str, Any]:
    result = {
        field: _json_value(row.get(field))
        for field in MANIFEST_FIELDS
        if field not in {"observed_content_sha256", "vector_dimension"}
    }
    content = str(row.get("content") or "")
    result["observed_content_sha256"] = hashlib.sha256(content.encode("utf-8")).hexdigest()
    result["vector_dimension"] = vector_dimension
    return result


def _manifest_hash(rows: Iterable[Mapping[str, Any]]) -> str:
    payload = json.dumps(list(rows), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _different_tier(tier: str) -> str:
    return next(value for value in ("contemporaneous", "discovered", "hindsight") if value != tier)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("activation watermark must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return _timestamp(value)
    if isinstance(value, UUID):
        return str(value)
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=_json_value) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_state(path: Path) -> ActivationState:
    payload = _read_json(path)
    return ActivationState(**{field: payload[field] for field in ActivationState.__dataclass_fields__})


def _byline() -> str:
    return "Codex · GPT-5 · 2026-08-18"
