"""One-shot setup, projection, evaluation, quarantine, and report command.

Only stable IDs, hashes, counts, and typed outcomes are emitted. Synthetic text,
embeddings, credentials, and tokens are never logged.

Byline: Codex · GPT-5 · 2026-08-17 (sanitized structured failure diagnostics)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from surrealdb import AsyncSurreal, Datetime, NotAllowedError

from .adapter import connect
from .contracts import source_available_from
from .identity import (
    APPROVED_RESTORE_TARGET,
    APPROVED_TARGET,
    TargetIdentity,
    sdk_endpoint,
    validate_target_identity,
)

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = "phase1-surreal-t0-slice-r1"
REVISION_1 = "projection-t0-r1"
REVISION_2 = "projection-t0-r2"
WALK_1 = "walk-t0-r1"
WALK_2 = "walk-t0-r2"
MATTER = "matter-synthetic-a"
POLICY_VERSION = "horizon-policy-v2"
POLICY_HASH = "sha256:349442c3f6b4f74e97f012fd1146c0bc4db5828ff46f43958b66aaf2535b698a"
QUERY_VECTOR = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
EXPORT_TABLES = (
    "context",
    "projection_revision",
    "projection_guard",
    "retrieval_chunk",
    "embedding_t0_v1",
    "third_party_conversation",
    "third_party_message",
    "third_party_realization_link",
    "walk",
    "walk_checkpoint",
    "walk_snapshot",
    "rewalk_of",
)
RESTORE_ID_FIELDS = {
    "context": "platform_id",
    "projection_revision": "platform_id",
    "projection_guard": "revision_id",
    "retrieval_chunk": "platform_id",
    "embedding_t0_v1": "platform_id",
    "third_party_conversation": "platform_id",
    "third_party_message": "platform_id",
    "third_party_realization_link": "platform_id",
    "walk": "walk_id",
    "walk_checkpoint": "platform_id",
    "walk_snapshot": "platform_id",
}
DATETIME_FIELDS = {
    "acquired_at",
    "captured_at",
    "checked_at",
    "created_at",
    "horizon_at",
    "occurred_at",
    "realized_at",
    "sealed_at",
    "source_available_from",
}


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _export_value(value: Any) -> Any:
    """Convert SDK-native values into stable, sanitized export values."""

    if isinstance(value, dict):
        return {key: _export_value(item) for key, item in value.items() if key != "id"}
    if isinstance(value, list):
        return [_export_value(item) for item in value]
    rendered = str(value)
    if rendered.startswith("walk:"):
        return rendered.removeprefix("walk:")
    if type(value).__module__.startswith("surrealdb"):
        return rendered
    return value


def _canonical_export(rows: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    """Strip native IDs and sort every table for deterministic parity hashing."""

    exported: dict[str, list[dict[str, Any]]] = {}
    for table, table_rows in sorted(rows.items()):
        sanitized = [_export_value(row) for row in table_rows]
        exported[table] = sorted(
            sanitized,
            key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")),
        )
    return exported


def _datetime(value: str) -> Datetime:
    return Datetime(value)


def _assert_statement_success(raw: Any, operation: str) -> None:
    """Reject any failed statement in a multi-statement SDK response."""

    if not isinstance(raw, dict):
        raise RuntimeError(f"{operation}:MALFORMED_RESPONSE")
    failures = []
    for index, item in enumerate(raw.get("result", [])):
        if isinstance(item, dict) and item.get("status") == "ERR":
            failures.append(f"{index}:{item.get('result', 'UNKNOWN')}")
    if failures:
        raise RuntimeError(f"{operation}:" + "|".join(failures[:3]))


def _safe_error_details(error: BaseException) -> dict[str, str]:
    """Return only non-sensitive structured Surreal denial identifiers."""

    current: BaseException | None = error
    for _ in range(8):
        if current is None:
            break
        details = {
            key: value
            for key, value in (
                ("kind", getattr(current, "kind", None)),
                ("method", getattr(current, "method_name", None)),
                ("function", getattr(current, "function_name", None)),
                ("target", getattr(current, "target_name", None)),
            )
            if isinstance(value, str) and value
        }
        if details:
            return details
        current = current.__cause__
    return {}


def _record_absent(value: Any) -> bool:
    """Recognize SDK result shapes for a permission-filtered missing record."""

    return value is None or value == []


def _keys() -> tuple[bytes, str]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return private_pem, public_pem.decode()


def _token(
    private_key: bytes,
    *,
    principal: str,
    role: str,
    projection_revision: str,
    mode: str = "as_lived_so_far",
    horizon_at: str = "2024-06-01T00:00:00Z",
    walk_id: str = "",
    target: TargetIdentity = APPROVED_TARGET,
) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": "horizon-phase1-runner",
        "aud": EXPERIMENT,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "jti": str(uuid.uuid4()),
        "ac": "phase1_record",
        "ns": target.namespace,
        "db": target.database,
        "id": f"service_principal:{principal}",
        "role": role,
        "matter_id": MATTER,
        "run_id": "run-t0-r1",
        "walk_id": walk_id,
        "horizon_id": f"horizon-{mode}-{horizon_at[:10]}",
        "horizon_at": horizon_at,
        "mode": mode,
        "projection_revision": projection_revision,
        "policy_version": POLICY_VERSION,
        "policy_hash": POLICY_HASH,
    }
    return jwt.encode(claims, private_key, algorithm="RS256")


async def _bootstrap(
    root_user: str,
    root_password: str,
    public_key: str,
    *,
    target: TargetIdentity = APPROVED_TARGET,
) -> None:
    validate_target_identity(target)
    database = AsyncSurreal(sdk_endpoint(target))
    async with database:
        await database.signin({"username": root_user, "password": root_password})
        await database.query_raw(
            f"DEFINE NAMESPACE IF NOT EXISTS {target.namespace}; "
            f"USE NS {target.namespace}; "
            f"DEFINE DATABASE IF NOT EXISTS {target.database};"
        )
        await database.use(target.namespace, target.database)
        schema = (ROOT / "schema" / "001_phase1_t0.surql").read_text(encoding="utf-8")
        schema = schema.replace("__PHASE1_JWT_PUBLIC_KEY__", public_key.strip())
        for definition in ("ACCESS", "TABLE", "FIELD", "INDEX"):
            schema = schema.replace(f"DEFINE {definition} ", f"DEFINE {definition} OVERWRITE ")
        schema_result = await database.query_raw(schema)
        _assert_statement_success(schema_result, "schema")
        for principal, role in (
            ("phase1_projector", "projector"),
            ("phase1_walk", "walk"),
            ("phase1_auditor", "auditor"),
        ):
            await database.query(
                "UPSERT type::record('service_principal', $principal) CONTENT $row;",
                {
                    "principal": principal,
                    "row": {
                        "experiment_id": EXPERIMENT,
                        "allowed_roles": [role],
                        "enabled": True,
                    },
                },
            )


async def _project(
    private_key: bytes,
    manifest: dict[str, Any],
    *,
    revision: str,
    target: TargetIdentity = APPROVED_TARGET,
    create_context: bool = False,
) -> dict[str, Any]:
    token = _token(
        private_key,
        principal="phase1_projector",
        role="projector",
        projection_revision=revision,
        target=target,
    )
    policy_hash = manifest["policy_hash"]
    if policy_hash != POLICY_HASH or manifest["policy_version"] != POLICY_VERSION:
        raise RuntimeError("MANIFEST_POLICY_MISMATCH")
    documents = [row for row in manifest["documents"] if row["matter_id"] == MATTER]
    for row in documents:
        source_available_from(row, subject_id=manifest["subject_id"])
    document_ids = sorted(row["id"] for row in documents)
    membership_hash = _canonical_hash(document_ids)
    content_hash = _canonical_hash(sorted(row["content_hash"] for row in documents))
    now = _datetime(datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    async with connect(target, token=token) as database:
        if create_context:
            created = await _query_checked(
                database,
                "CREATE ONLY type::record('context', $context_id) CONTENT $row;",
                {
                    "context_id": target.context_id,
                    "row": {
                        "platform_id": target.context_id,
                        "experiment_id": EXPERIMENT,
                        "environment": "phase1_t0_disposable",
                        "corpus_tier": "T0_SYNTHETIC",
                        "created_at": now,
                    },
                },
                "create_context",
            )
            if _record_absent(created):
                raise RuntimeError("CONTEXT_CREATE_DENIED")
        created = await _query_checked(
            database,
            "CREATE ONLY type::record('projection_revision', $revision) CONTENT $row;",
            {
                "revision": revision,
                "row": {
                    "platform_id": revision,
                    "matter_id": MATTER,
                    "context_id": target.context_id,
                    "membership_hash": membership_hash,
                    "content_hash": content_hash,
                    "policy_version": POLICY_VERSION,
                    "policy_hash": policy_hash,
                    "created_at": now,
                },
            },
            f"create_projection_{revision}",
        )
        if _record_absent(created):
            raise RuntimeError("PROJECTION_CREATE_DENIED")
        created = await _query_checked(
            database,
            "CREATE ONLY type::record('projection_guard', $revision) CONTENT $row;",
            {
                "revision": revision,
                "row": {
                    "revision_id": revision,
                    "matter_id": MATTER,
                    "status": "building",
                    "reconciled_hash": None,
                    "quarantine_reason": None,
                    "checked_at": now,
                },
            },
            f"create_guard_{revision}",
        )
        if _record_absent(created):
            raise RuntimeError("PROJECTION_GUARD_CREATE_DENIED")
        projected_conversations: set[str] = set()
        realization_count = 0
        for row in documents:
            acquired_at = _datetime(row["acquired_at"]) if row.get("acquired_at") else None
            common = {
                "platform_id": row["id"],
                "matter_id": MATTER,
                "projection_revision": revision,
                "policy_version": POLICY_VERSION,
                "policy_hash": policy_hash,
                "authority_state": row["authority_state"],
                "promotion_state": row["promotion_state"],
                "disclosure_tier": row["disclosure_tier"],
                "source_class": row["source_class"],
                "conversation_id": row["conversation_id"],
                "occurred_at": _datetime(row["occurred_at"]),
                "acquired_at": acquired_at,
                "source_available_from": _datetime(row["source_available_from"]),
                "sender_id": row["sender_id"],
                "recipient_ids": row["recipient_ids"],
                "participant_ids": row["participant_ids"],
            }
            created = await _query_checked(
                database,
                "CREATE ONLY type::record('retrieval_chunk', $id) CONTENT $row;",
                {
                    "id": f"{revision}--{row['id']}",
                    "row": {
                        **common,
                        "content_hash": row["content_hash"],
                        "chunker_version": "chonkie.semantic-1.7.0-t0",
                        "source_family_id": f"family-{row['id']}",
                        "created_at": now,
                    },
                },
                f"create_chunk_{row['id']}",
            )
            if _record_absent(created):
                raise RuntimeError(f"CHUNK_CREATE_DENIED:{row['id']}")
            created = await _query_checked(
                database,
                "CREATE ONLY type::record('embedding_t0_v1', $id) CONTENT $row;",
                {
                    "id": f"{revision}--{row['id']}",
                    "row": {
                        **common,
                        "chunk_id": row["id"],
                        "profile_id": manifest["embedding_profile"],
                        "input_hash": row["content_hash"],
                        "dimensions": 8,
                        "numeric_type": "f32",
                        "embedding": row["vector"],
                    },
                },
                f"create_embedding_{row['id']}",
            )
            if _record_absent(created):
                raise RuntimeError(f"EMBEDDING_CREATE_DENIED:{row['id']}")
            if row["source_class"] != "acquired_third_party":
                continue
            if manifest["subject_id"] in row["participant_ids"]:
                raise RuntimeError("THIRD_PARTY_SUBJECT_IS_PARTICIPANT")
            conversation_id = row["conversation_id"]
            if conversation_id not in projected_conversations:
                created = await _query_checked(
                    database,
                    "CREATE ONLY type::record('third_party_conversation', $id) CONTENT $row;",
                    {
                        "id": f"{revision}--{conversation_id}",
                        "row": {
                            "platform_id": conversation_id,
                            "matter_id": MATTER,
                            "projection_revision": revision,
                            "acquired_at": acquired_at,
                            "participant_ids": row["participant_ids"],
                            "subject_id": manifest["subject_id"],
                            "source_family_id": f"family-{conversation_id}",
                            "created_at": now,
                        },
                    },
                    f"create_third_party_conversation_{conversation_id}",
                )
                if _record_absent(created):
                    raise RuntimeError("THIRD_PARTY_CONVERSATION_CREATE_DENIED")
                projected_conversations.add(conversation_id)
            created = await _query_checked(
                database,
                "CREATE ONLY type::record('third_party_message', $id) CONTENT $row;",
                {
                    "id": f"{revision}--{row['id']}",
                    "row": {
                        "platform_id": row["id"],
                        "conversation_id": conversation_id,
                        "normalized_record_id": row["id"],
                        "matter_id": MATTER,
                        "projection_revision": revision,
                        "occurred_at": _datetime(row["occurred_at"]),
                        "acquired_at": acquired_at,
                        "sender_id": row["sender_id"],
                        "recipient_ids": row["recipient_ids"],
                        "participant_ids": row["participant_ids"],
                        "content_hash": row["content_hash"],
                        "created_at": now,
                    },
                },
                f"create_third_party_message_{row['id']}",
            )
            if _record_absent(created):
                raise RuntimeError("THIRD_PARTY_MESSAGE_CREATE_DENIED")
            for realization in row["realization_links"]:
                created = await _query_checked(
                    database,
                    "CREATE ONLY type::record('third_party_realization_link', $id) CONTENT $row;",
                    {
                        "id": f"{revision}--{realization['id']}",
                        "row": {
                            "platform_id": realization["id"],
                            "message_id": row["id"],
                            "matter_id": MATTER,
                            "projection_revision": revision,
                            "realized_at": _datetime(realization["realized_at"]),
                            "approval_state": realization["approval_state"],
                            "kind": realization["kind"],
                            "created_at": now,
                        },
                    },
                    f"create_realization_{realization['id']}",
                )
                if _record_absent(created):
                    raise RuntimeError("REALIZATION_LINK_CREATE_DENIED")
                realization_count += 1
        reconciled_hash = _canonical_hash({"membership": membership_hash, "content": content_hash})
        updated = await _query_checked(
            database,
            "UPDATE type::record('projection_guard', $revision) SET status = 'active', reconciled_hash = $hash, checked_at = $checked_at;",
            {"revision": revision, "hash": reconciled_hash, "checked_at": now},
            f"activate_guard_{revision}",
        )
        if _record_absent(updated):
            raise RuntimeError("PROJECTION_ACTIVATION_DENIED")
        observed = await _query_checked(
            database,
            "SELECT VALUE platform_id FROM retrieval_chunk WHERE matter_id = $matter AND projection_revision = $revision ORDER BY platform_id;",
            {"matter": MATTER, "revision": revision},
            f"projection_membership_{revision}",
        )
        if observed != document_ids:
            raise RuntimeError("PROJECTION_MEMBERSHIP_POSTCONDITION_FAILED")
    return {
        "membership_hash": membership_hash,
        "content_hash": content_hash,
        "reconciled_hash": reconciled_hash,
        "object_count": len(documents),
        "realization_link_count": realization_count,
    }


def _statement_results(raw: Any) -> list[Any]:
    if not isinstance(raw, dict):
        return []
    result = raw.get("result", [])
    if not isinstance(result, list):
        return []
    return [item.get("result") for item in result if isinstance(item, dict)]


def _last_statement_result(raw: Any, operation: str) -> Any:
    _assert_statement_success(raw, operation)
    results = _statement_results(raw)
    return results[-1] if results else None


async def _query_checked(
    database: AsyncSurreal,
    statement: str,
    variables: dict[str, Any] | None,
    operation: str,
) -> Any:
    """Execute one statement and return its checked result payload."""

    raw = await database.query_raw(statement, variables or {})
    return _last_statement_result(raw, operation)


async def _retrieve(
    private_key: bytes,
    *,
    mode: str,
    horizon_at: str,
    revision: str,
    target: TargetIdentity = APPROVED_TARGET,
) -> tuple[list[str], Any]:
    token = _token(
        private_key,
        principal="phase1_auditor",
        role="auditor",
        projection_revision=revision,
        mode=mode,
        horizon_at=horizon_at,
        target=target,
    )
    query = (ROOT / "queries" / "retrieve_exact.surql").read_text(encoding="utf-8")
    variables = {
        "matter_id": MATTER,
        "projection_revision": revision,
        "policy_version": POLICY_VERSION,
        "policy_hash": POLICY_HASH,
        "horizon_at": horizon_at,
        "mode": mode,
        "query_vector": QUERY_VECTOR,
        "top_k": 2,
    }
    async with connect(target, token=token) as database:
        raw = await database.query_raw(query, variables)
    results = _statement_results(raw)
    ranked = results[-1] if results else []
    ids = [str(item["platform_id"]) for item in ranked] if isinstance(ranked, list) else []
    plan = results[-2] if len(results) >= 2 else None
    return ids, plan


async def _negative_write(private_key: bytes) -> bool:
    token = _token(
        private_key,
        principal="phase1_auditor",
        role="auditor",
        projection_revision=REVISION_1,
    )
    async with connect(APPROVED_TARGET, token=token) as database:
        try:
            await database.query(
                "CREATE ONLY context:forbidden CONTENT $row;",
                {
                    "row": {
                        "platform_id": "forbidden",
                        "experiment_id": EXPERIMENT,
                        "environment": "phase1_t0_disposable",
                        "corpus_tier": "T0_SYNTHETIC",
                        "created_at": _datetime(datetime.now(UTC).isoformat()),
                    }
                },
            )
        except NotAllowedError:
            return True
        observed = await database.query("SELECT VALUE platform_id FROM ONLY context:forbidden;")
    return _record_absent(observed)


async def _quarantine(
    private_key: bytes,
    *,
    revision: str,
    target: TargetIdentity = APPROVED_TARGET,
) -> None:
    token = _token(
        private_key,
        principal="phase1_projector",
        role="projector",
        projection_revision=revision,
        target=target,
    )
    async with connect(target, token=token) as database:
        updated = await _query_checked(
            database,
            "UPDATE type::record('projection_guard', $revision) SET status = 'quarantined', quarantine_reason = 'SYNTHETIC_HASH_DRIFT', checked_at = $checked_at;",
            {
                "revision": revision,
                "checked_at": _datetime(datetime.now(UTC).isoformat()),
            },
            f"quarantine_{revision}",
        )
        if _record_absent(updated):
            raise RuntimeError("PROJECTION_QUARANTINE_DENIED")
        status = await _query_checked(
            database,
            "SELECT VALUE status FROM ONLY type::record('projection_guard', $revision);",
            {"revision": revision},
            f"quarantine_postcondition_{revision}",
        )
        if status != "quarantined":
            raise RuntimeError("PROJECTION_QUARANTINE_POSTCONDITION_FAILED")


async def _create_walk(private_key: bytes, *, walk_id: str, revision: str) -> None:
    token = _token(
        private_key,
        principal="phase1_walk",
        role="walk",
        projection_revision=revision,
        walk_id=walk_id,
    )
    now = _datetime(datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    async with connect(APPROVED_TARGET, token=token) as database:
        created = await _query_checked(
            database,
            "CREATE ONLY type::record('walk', $walk_id) CONTENT $row;",
            {
                "walk_id": walk_id,
                "row": {
                    "walk_id": walk_id,
                    "matter_id": MATTER,
                    "run_id": f"run-{walk_id}",
                    "mode": "as_lived_so_far",
                    "status": "active",
                    "projection_revision": revision,
                    "policy_version": POLICY_VERSION,
                    "policy_hash": POLICY_HASH,
                    "created_at": now,
                },
            },
            f"create_walk_{walk_id}",
        )
        if _record_absent(created):
            raise RuntimeError("WALK_CREATE_DENIED")


async def _pause_walk(
    private_key: bytes,
    *,
    walk_id: str,
    revision: str,
    eligible_ids: list[str],
) -> dict[str, Any]:
    token = _token(
        private_key,
        principal="phase1_walk",
        role="walk",
        projection_revision=revision,
        walk_id=walk_id,
    )
    now = _datetime(datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    checkpoint_id = f"checkpoint-{walk_id}-2024-06-01"
    eligible_manifest_hash = _canonical_hash(eligible_ids)
    belief_ids = [f"belief-{walk_id}-step-1"]
    retrieval_ids = list(eligible_ids)
    trace_hash = _canonical_hash({"walk_id": walk_id, "step": 1, "retrieval_ids": retrieval_ids})
    state_hash = _canonical_hash(
        {
            "walk_id": walk_id,
            "horizon_at": "2024-06-01T00:00:00Z",
            "belief_ids": belief_ids,
            "retrieval_ids": retrieval_ids,
            "trace_hash": trace_hash,
        }
    )
    async with connect(APPROVED_TARGET, token=token) as database:
        raw = await database.query_raw(
            "BEGIN TRANSACTION; "
            "UPDATE type::record('walk', $walk_id) SET status = 'paused' WHERE status = 'active'; "
            "CREATE ONLY type::record('walk_checkpoint', $checkpoint_id) CONTENT $row; "
            "COMMIT TRANSACTION;",
            {
                "walk_id": walk_id,
                "checkpoint_id": checkpoint_id,
                "row": {
                    "platform_id": checkpoint_id,
                    "walk_id": walk_id,
                    "matter_id": MATTER,
                    "current_step": 1,
                    "horizon_id": "horizon-as_lived_so_far-2024-06-01",
                    "horizon_at": _datetime("2024-06-01T00:00:00Z"),
                    "projection_revision": revision,
                    "eligible_manifest_hash": eligible_manifest_hash,
                    "state_hash": state_hash,
                    "trace_hash": trace_hash,
                    "belief_ids": belief_ids,
                    "retrieval_ids": retrieval_ids,
                    "captured_at": now,
                },
            },
        )
        _assert_statement_success(raw, "pause_walk_transaction")
        status_raw = await database.query_raw(
            "SELECT VALUE status FROM ONLY type::record('walk', $walk_id);",
            {"walk_id": walk_id},
        )
        if _last_statement_result(status_raw, "pause_walk_status") != "paused":
            raise RuntimeError("PAUSE_WALK_POSTCONDITION_FAILED")
        checkpoint_raw = await database.query_raw(
            "SELECT walk_id, projection_revision, current_step, state_hash, trace_hash, belief_ids, retrieval_ids FROM ONLY type::record('walk_checkpoint', $checkpoint_id);",
            {"checkpoint_id": checkpoint_id},
        )
        observed_checkpoint = _last_statement_result(checkpoint_raw, "pause_checkpoint_postcondition")
        if (
            not isinstance(observed_checkpoint, dict)
            or observed_checkpoint.get("walk_id") != walk_id
            or observed_checkpoint.get("projection_revision") != revision
            or observed_checkpoint.get("state_hash") != state_hash
            or observed_checkpoint.get("trace_hash") != trace_hash
            or observed_checkpoint.get("belief_ids") != belief_ids
            or observed_checkpoint.get("retrieval_ids") != retrieval_ids
        ):
            raise RuntimeError("CHECKPOINT_POSTCONDITION_FAILED")
    return {
        "checkpoint_id": checkpoint_id,
        "walk_id": walk_id,
        "projection_revision": revision,
        "status": "paused",
        "resumable": True,
        "state_hash": state_hash,
        "trace_hash": trace_hash,
        "current_step": 1,
        "belief_ids": belief_ids,
        "retrieval_ids": retrieval_ids,
    }


async def _resume_walk(
    private_key: bytes,
    *,
    walk_id: str,
    revision: str,
    checkpoint_id: str,
) -> dict[str, Any]:
    token = _token(
        private_key,
        principal="phase1_walk",
        role="walk",
        projection_revision=revision,
        walk_id=walk_id,
    )
    async with connect(APPROVED_TARGET, token=token) as database:
        status_raw = await database.query_raw(
            "SELECT VALUE status FROM ONLY type::record('walk', $walk_id);",
            {"walk_id": walk_id},
        )
        if _last_statement_result(status_raw, "resume_walk_precondition") != "paused":
            raise RuntimeError("RESUME_WALK_NOT_PAUSED")
        raw = await database.query_raw(
            "SELECT walk_id, projection_revision, current_step, state_hash, trace_hash, belief_ids, retrieval_ids FROM ONLY type::record('walk_checkpoint', $checkpoint_id);",
            {"checkpoint_id": checkpoint_id},
        )
        checkpoint = _last_statement_result(raw, "resume_checkpoint")
        if not isinstance(checkpoint, dict):
            raise RuntimeError("RESUME_CHECKPOINT_NOT_FOUND")
        if (
            checkpoint.get("walk_id") != walk_id
            or checkpoint.get("projection_revision") != revision
            or not checkpoint.get("state_hash")
            or not checkpoint.get("trace_hash")
            or int(checkpoint.get("current_step") or 0) < 1
        ):
            raise RuntimeError("RESUME_CHECKPOINT_INVALID")
        guard_raw = await database.query_raw(
            "SELECT VALUE status FROM ONLY type::record('projection_guard', $revision);",
            {"revision": revision},
        )
        if _last_statement_result(guard_raw, "resume_projection_guard") != "active":
            raise RuntimeError("RESUME_PROJECTION_NOT_ACTIVE")
        updated = await _query_checked(
            database,
            "UPDATE type::record('walk', $walk_id) SET status = 'active' WHERE status = 'paused';",
            {"walk_id": walk_id},
            "resume_walk_update",
        )
        if _record_absent(updated):
            raise RuntimeError("RESUME_WALK_UPDATE_DENIED")
        status_raw = await database.query_raw(
            "SELECT VALUE status FROM ONLY type::record('walk', $walk_id);",
            {"walk_id": walk_id},
        )
    return {
        "checkpoint_id": checkpoint_id,
        "walk_id": walk_id,
        "projection_revision": revision,
        "status": _last_statement_result(status_raw, "resume_walk_status"),
        "same_identity": checkpoint.get("walk_id") == walk_id,
        "current_step": checkpoint["current_step"],
        "state_hash": checkpoint["state_hash"],
        "trace_hash": checkpoint["trace_hash"],
        "belief_ids": checkpoint.get("belief_ids") or [],
        "retrieval_ids": checkpoint.get("retrieval_ids") or [],
    }


async def _seal_walk(
    private_key: bytes,
    *,
    walk_id: str,
    revision: str,
    eligible_ids: list[str],
) -> dict[str, Any]:
    token = _token(
        private_key,
        principal="phase1_walk",
        role="walk",
        projection_revision=revision,
        walk_id=walk_id,
    )
    now = _datetime(datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    snapshot_id = f"snapshot-{walk_id}"
    eligible_manifest_hash = _canonical_hash(eligible_ids)
    belief_ids = [f"belief-{walk_id}-step-1"]
    retrieval_ids = list(eligible_ids)
    trace_hash = _canonical_hash({"walk_id": walk_id, "step": 1, "retrieval_ids": retrieval_ids})
    state_hash = _canonical_hash(
        {
            "walk_id": walk_id,
            "horizon_at": "2024-06-01T00:00:00Z",
            "belief_ids": belief_ids,
            "retrieval_ids": retrieval_ids,
            "trace_hash": trace_hash,
        }
    )
    async with connect(APPROVED_TARGET, token=token) as database:
        guard_raw = await database.query_raw(
            "SELECT VALUE status FROM ONLY type::record('projection_guard', $revision);",
            {"revision": revision},
        )
        if _last_statement_result(guard_raw, "seal_projection_guard") != "quarantined":
            raise RuntimeError("SEAL_REQUIRES_QUARANTINED_PROJECTION")
        raw = await database.query_raw(
            "BEGIN TRANSACTION; "
            "UPDATE type::record('walk', $walk_id) SET status = 'sealed' WHERE status IN ['active', 'paused']; "
            "CREATE ONLY type::record('walk_snapshot', $snapshot_id) CONTENT $row; "
            "COMMIT TRANSACTION;",
            {
                "walk_id": walk_id,
                "snapshot_id": snapshot_id,
                "row": {
                    "platform_id": snapshot_id,
                    "walk_id": walk_id,
                    "matter_id": MATTER,
                    "current_step": 1,
                    "horizon_id": "horizon-as_lived_so_far-2024-06-01",
                    "horizon_at": _datetime("2024-06-01T00:00:00Z"),
                    "projection_revision": revision,
                    "eligible_manifest_hash": eligible_manifest_hash,
                    "state_hash": state_hash,
                    "trace_hash": trace_hash,
                    "belief_ids": belief_ids,
                    "retrieval_ids": retrieval_ids,
                    "failure_reason": "SYNTHETIC_HASH_DRIFT",
                    "sealed_at": now,
                    "resumable": False,
                },
            },
        )
        _assert_statement_success(raw, "seal_walk_transaction")
        walk_status_raw = await database.query_raw(
            "SELECT VALUE status FROM ONLY type::record('walk', $walk_id);",
            {"walk_id": walk_id},
        )
        snapshot_raw = await database.query_raw(
            "SELECT platform_id, resumable, failure_reason, state_hash, trace_hash, belief_ids, retrieval_ids FROM ONLY type::record('walk_snapshot', $snapshot_id);",
            {"snapshot_id": snapshot_id},
        )
        snapshot = _last_statement_result(snapshot_raw, "seal_snapshot_postcondition")
        if (
            not isinstance(snapshot, dict)
            or snapshot.get("resumable") is not False
            or snapshot.get("state_hash") != state_hash
            or snapshot.get("trace_hash") != trace_hash
            or snapshot.get("belief_ids") != belief_ids
            or snapshot.get("retrieval_ids") != retrieval_ids
        ):
            raise RuntimeError("SEALED_SNAPSHOT_POSTCONDITION_FAILED")
        recall_raw = await database.query_raw(
            "SELECT VALUE platform_id FROM walk_checkpoint WHERE walk_id = $walk_id AND type::record('walk', walk_id).status = 'paused' AND type::record('projection_guard', projection_revision).status = 'active';",
            {"walk_id": walk_id},
        )
    return {
        "snapshot_id": snapshot_id,
        "eligible_manifest_hash": eligible_manifest_hash,
        "state_hash": state_hash,
        "sealed": _last_statement_result(walk_status_raw, "seal_walk_status") == "sealed",
        "active_recall_ids": _last_statement_result(recall_raw, "sealed_active_recall") or [],
        "resumable": False,
        "trace_hash": trace_hash,
        "current_step": 1,
        "belief_ids": belief_ids,
        "retrieval_ids": retrieval_ids,
    }


async def _link_rewalk(private_key: bytes) -> dict[str, Any]:
    token = _token(
        private_key,
        principal="phase1_walk",
        role="walk",
        projection_revision=REVISION_2,
        walk_id=WALK_2,
    )
    now = _datetime(datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    change_manifest_hash = _canonical_hash(
        {
            "from_projection": REVISION_1,
            "to_projection": REVISION_2,
            "reason": "SYNTHETIC_HASH_DRIFT",
            "membership_change": "none",
            "content_change": "none",
        }
    )
    async with connect(APPROVED_TARGET, token=token) as database:
        created = await _query_checked(
            database,
            "RELATE type::record('walk', $new_walk) -> rewalk_of -> type::record('walk', $sealed_walk) CONTENT $row;",
            {
                "new_walk": WALK_2,
                "sealed_walk": WALK_1,
                "row": {
                    "matter_id": MATTER,
                    "reconciliation_id": "reconcile-t0-r1-r2",
                    "change_manifest_hash": change_manifest_hash,
                    "created_at": now,
                },
            },
            "create_rewalk_edge",
        )
        if _record_absent(created):
            raise RuntimeError("REWALK_EDGE_CREATE_DENIED")
        edges_raw = await database.query_raw(
            "SELECT in.walk_id AS new_walk_id, out.walk_id AS sealed_walk_id, reconciliation_id, change_manifest_hash FROM rewalk_of WHERE matter_id = $matter_id AND in = type::record('walk', $new_walk) AND out = type::record('walk', $sealed_walk);",
            {"matter_id": MATTER, "new_walk": WALK_2, "sealed_walk": WALK_1},
        )
        edges = _last_statement_result(edges_raw, "rewalk_edge")
        expected_edge = {
            "new_walk_id": WALK_2,
            "sealed_walk_id": WALK_1,
            "reconciliation_id": "reconcile-t0-r1-r2",
            "change_manifest_hash": change_manifest_hash,
        }
        if not isinstance(edges, list) or len(edges) != 1 or edges[0] != expected_edge:
            raise RuntimeError("REWALK_EDGE_POSTCONDITION_FAILED")
    return {
        "new_walk_id": WALK_2,
        "sealed_walk_id": WALK_1,
        "new_projection_revision": REVISION_2,
        "old_projection_revision": REVISION_1,
        "change_manifest_hash": change_manifest_hash,
        "edge_observed": True,
        "change_classification": "same canonical membership/content; rebuilt after guard drift",
    }


async def _export_database(
    root_user: str,
    root_password: str,
    *,
    target: TargetIdentity,
) -> dict[str, list[dict[str, Any]]]:
    validate_target_identity(target)
    rows: dict[str, list[dict[str, Any]]] = {}
    database = AsyncSurreal(sdk_endpoint(target))
    async with database:
        await database.signin({"username": root_user, "password": root_password})
        await database.use(target.namespace, target.database)
        for table in EXPORT_TABLES:
            raw = await database.query_raw(f"SELECT * FROM {table};")
            result = _last_statement_result(raw, f"export_{table}")
            rows[table] = result if isinstance(result, list) else []
    return _canonical_export(rows)


def _restore_row(row: dict[str, Any]) -> dict[str, Any]:
    restored = dict(row)
    for field in DATETIME_FIELDS:
        value = restored.get(field)
        if isinstance(value, str):
            restored[field] = _datetime(value)
    return restored


async def _import_database(
    root_user: str,
    root_password: str,
    exported: dict[str, list[dict[str, Any]]],
) -> int:
    database = AsyncSurreal(sdk_endpoint(APPROVED_RESTORE_TARGET))
    imported = 0
    async with database:
        await database.signin({"username": root_user, "password": root_password})
        await database.use(APPROVED_RESTORE_TARGET.namespace, APPROVED_RESTORE_TARGET.database)
        for table in EXPORT_TABLES:
            for exported_row in exported[table]:
                row = _restore_row(exported_row)
                if table == "rewalk_of":
                    raw = await database.query_raw(
                        "RELATE type::record('walk', $new_walk) -> rewalk_of -> type::record('walk', $old_walk) CONTENT $row;",
                        {
                            "new_walk": row.pop("in"),
                            "old_walk": row.pop("out"),
                            "row": row,
                        },
                    )
                else:
                    id_field = RESTORE_ID_FIELDS[table]
                    record_id = str(row[id_field])
                    if table in {
                        "embedding_t0_v1",
                        "retrieval_chunk",
                        "third_party_conversation",
                        "third_party_message",
                        "third_party_realization_link",
                    }:
                        record_id = f"{row['projection_revision']}--{record_id}"
                    raw = await database.query_raw(
                        "CREATE ONLY type::record($table, $record_id) CONTENT $row;",
                        {"table": table, "record_id": record_id, "row": row},
                    )
                result = _last_statement_result(raw, f"import_{table}_{imported}")
                if _record_absent(result):
                    raise RuntimeError(f"IMPORT_POSTCONDITION_FAILED:{table}:{imported}")
                imported += 1
    return imported


async def run() -> dict[str, Any]:
    validate_target_identity(APPROVED_TARGET)
    root_user = os.environ["SURREAL_PHASE1_ROOT_USER"]
    root_password = os.environ["SURREAL_PHASE1_ROOT_PASS"]
    manifest = json.loads((ROOT / "fixtures" / "t0_manifest.json").read_text(encoding="utf-8"))
    private_key, public_key = _keys()
    started = time.monotonic()
    stage = "bootstrap"
    try:
        await _bootstrap(root_user, root_password, public_key)
        stage = "projection_r1"
        receipt_r1 = await _project(
            private_key,
            manifest,
            revision=REVISION_1,
            create_context=True,
        )
        stage = "retrieve_early"
        early_ids, early_plan = await _retrieve(
            private_key,
            mode="as_lived_so_far",
            horizon_at="2024-06-01T00:00:00Z",
            revision=REVISION_1,
        )
        stage = "retrieve_late"
        late_ids, _ = await _retrieve(
            private_key,
            mode="as_lived_so_far",
            horizon_at="2026-06-01T00:00:00Z",
            revision=REVISION_1,
        )
        stage = "retrieve_hindsight"
        hindsight_ids, _ = await _retrieve(
            private_key,
            mode="hindsight",
            horizon_at="2024-06-01T00:00:00Z",
            revision=REVISION_1,
        )
        stage = "create_walk_r1"
        await _create_walk(private_key, walk_id=WALK_1, revision=REVISION_1)
        stage = "pause_walk_r1"
        checkpoint = await _pause_walk(
            private_key,
            walk_id=WALK_1,
            revision=REVISION_1,
            eligible_ids=early_ids,
        )
        stage = "resume_walk_r1"
        resumed = await _resume_walk(
            private_key,
            walk_id=WALK_1,
            revision=REVISION_1,
            checkpoint_id=checkpoint["checkpoint_id"],
        )
        stage = "negative_write"
        negative_write_denied = await _negative_write(private_key)
        stage = "quarantine_r1"
        await _quarantine(private_key, revision=REVISION_1)
        stage = "post_quarantine_read"
        after_quarantine_ids, _ = await _retrieve(
            private_key,
            mode="as_lived_so_far",
            horizon_at="2024-06-01T00:00:00Z",
            revision=REVISION_1,
        )
        stage = "seal_walk_r1"
        snapshot = await _seal_walk(
            private_key,
            walk_id=WALK_1,
            revision=REVISION_1,
            eligible_ids=early_ids,
        )
        stage = "projection_r2"
        receipt_r2 = await _project(private_key, manifest, revision=REVISION_2)
        stage = "create_walk_r2"
        await _create_walk(private_key, walk_id=WALK_2, revision=REVISION_2)
        stage = "link_rewalk"
        rewalk = await _link_rewalk(private_key)
        stage = "retrieve_r2"
        r2_ids, _ = await _retrieve(
            private_key,
            mode="as_lived_so_far",
            horizon_at="2024-06-01T00:00:00Z",
            revision=REVISION_2,
        )
        stage = "export_source"
        source_export = await _export_database(
            root_user,
            root_password,
            target=APPROVED_TARGET,
        )
        source_export_hash = _canonical_hash(source_export)
        stage = "bootstrap_restore"
        await _bootstrap(
            root_user,
            root_password,
            public_key,
            target=APPROVED_RESTORE_TARGET,
        )
        stage = "import_restore"
        imported_count = await _import_database(root_user, root_password, source_export)
        stage = "export_restore"
        restore_export = await _export_database(
            root_user,
            root_password,
            target=APPROVED_RESTORE_TARGET,
        )
        restore_export_hash = _canonical_hash(restore_export)
        stage = "retrieve_restore"
        restored_ids, _ = await _retrieve(
            private_key,
            mode="as_lived_so_far",
            horizon_at="2024-06-01T00:00:00Z",
            revision=REVISION_2,
            target=APPROVED_RESTORE_TARGET,
        )
    except Exception as exc:
        raise RuntimeError(f"stage={stage};{type(exc).__name__}:{exc}") from exc
    report = {
        "byline": "Codex · GPT-5 · 2026-08-16",
        "experiment_id": EXPERIMENT,
        "target_id": "data-surreal-phase1-t0-r1",
        "server_version": "3.2.3",
        "sdk_version": "2.0.0",
        "manifest_hash": _canonical_hash(manifest),
        "receipts": {"r1": receipt_r1, "r2": receipt_r2},
        "walk": {
            "checkpoint": checkpoint,
            "resumed": resumed,
            "snapshot": snapshot,
            "rewalk": rewalk,
        },
        "parity": {
            "source_export_hash": source_export_hash,
            "restore_export_hash": restore_export_hash,
            "source_row_count": sum(len(rows) for rows in source_export.values()),
            "imported_row_count": imported_count,
            "restored_ids": restored_ids,
        },
        "retrieval": {
            "early_ids": early_ids,
            "late_ids": late_ids,
            "hindsight_ids": hindsight_ids,
            "after_quarantine_ids": after_quarantine_ids,
            "r2_ids": r2_ids,
            "plan_observed": early_plan is not None,
        },
        "gates": {
            "early_exact_match": early_ids == manifest["expected"]["early_as_lived_ranked_ids"],
            "late_positive_control": late_ids == manifest["expected"]["late_as_lived_top_ids"],
            "hindsight_positive_control": hindsight_ids == manifest["expected"]["hindsight_top_ids"],
            "negative_write_denied": negative_write_denied,
            "quarantine_blocks_reads": after_quarantine_ids == [],
            "authorized_projection_count": receipt_r1["object_count"]
            == manifest["expected"]["authorized_projection_count"],
            "realizations_kept_separate": receipt_r1["realization_link_count"]
            == len(manifest["expected"]["third_party_realization_ids"]),
            "healthy_resume_same_identity": resumed["same_identity"]
            and resumed["walk_id"] == WALK_1
            and resumed["state_hash"] == checkpoint["state_hash"]
            and resumed["trace_hash"] == checkpoint["trace_hash"],
            "sealed_snapshot_terminal": snapshot["sealed"]
            and snapshot["resumable"] is False
            and snapshot["state_hash"] == checkpoint["state_hash"]
            and snapshot["trace_hash"] == checkpoint["trace_hash"]
            and snapshot["belief_ids"] == checkpoint["belief_ids"]
            and snapshot["retrieval_ids"] == checkpoint["retrieval_ids"]
            and snapshot["active_recall_ids"] == [],
            "linked_rewalk_exact": rewalk["edge_observed"]
            and rewalk["new_walk_id"] == WALK_2
            and rewalk["sealed_walk_id"] == WALK_1,
            "reconciled_membership_equal": receipt_r1["membership_hash"] == receipt_r2["membership_hash"]
            and receipt_r1["content_hash"] == receipt_r2["content_hash"],
            "r2_retrieval_equal": r2_ids == early_ids,
            "export_import_exact_parity": source_export_hash == restore_export_hash
            and imported_count == sum(len(rows) for rows in source_export.values()),
            "restored_retrieval_equal": restored_ids == r2_ids,
        },
        "duration_ms": round((time.monotonic() - started) * 1000, 2),
        "status": "PASS",
    }
    if not all(report["gates"].values()):
        report["status"] = "FAIL"
    return report


def main() -> None:
    try:
        report = asyncio.run(run())
    except Exception as exc:
        report = {
            "byline": "Codex · GPT-5 · 2026-08-16",
            "experiment_id": EXPERIMENT,
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "error_summary": str(exc)[:240],
            "error_details": _safe_error_details(exc),
        }
    print(json.dumps(report, sort_keys=True), flush=True)
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
