"""One-shot setup, projection, evaluation, quarantine, and report command.

Only stable IDs, hashes, counts, and typed outcomes are emitted. Synthetic text,
embeddings, credentials, and tokens are never logged.

Byline: Codex · GPT-5 · 2026-08-16
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
from surrealdb import AsyncSurreal, Datetime

from .adapter import connect
from .identity import APPROVED_TARGET, sdk_endpoint, validate_target_identity

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = "phase1-surreal-t0-slice-r1"
REVISION_1 = "projection-t0-r1"
REVISION_2 = "projection-t0-r2"
MATTER = "matter-synthetic-a"
POLICY_VERSION = "horizon-policy-v1"
QUERY_VECTOR = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _datetime(value: str) -> Datetime:
    return Datetime(value)


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
        "ns": APPROVED_TARGET.namespace,
        "db": APPROVED_TARGET.database,
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
        "policy_hash": "sha256:5f36a9ebd0be02dbf8fc55c526480e49c3c9fc60a8d5a55540cbb87e4da550e5",
    }
    return jwt.encode(claims, private_key, algorithm="RS256")


async def _bootstrap(root_user: str, root_password: str, public_key: str) -> None:
    database = AsyncSurreal(sdk_endpoint(APPROVED_TARGET))
    async with database:
        await database.signin({"username": root_user, "password": root_password})
        await database.query_raw(
            "DEFINE NAMESPACE IF NOT EXISTS phase1_surreal; "
            "USE NS phase1_surreal; "
            "DEFINE DATABASE IF NOT EXISTS t0_slice_r1;"
        )
        await database.use(APPROVED_TARGET.namespace, APPROVED_TARGET.database)
        schema = (ROOT / "schema" / "001_phase1_t0.surql").read_text(encoding="utf-8")
        schema = schema.replace("__PHASE1_JWT_PUBLIC_KEY__", public_key.strip())
        await database.query(schema)
        for principal, role in (
            ("phase1_projector", "projector"),
            ("phase1_walk", "walk"),
            ("phase1_auditor", "auditor"),
        ):
            await database.query(
                "CREATE ONLY type::record('service_principal', $principal) CONTENT $row;",
                {
                    "principal": principal,
                    "row": {
                        "experiment_id": EXPERIMENT,
                        "allowed_roles": [role],
                        "enabled": True,
                    },
                },
            )


async def _project(private_key: bytes, manifest: dict[str, Any]) -> dict[str, Any]:
    token = _token(
        private_key,
        principal="phase1_projector",
        role="projector",
        projection_revision=REVISION_1,
    )
    policy_hash = manifest["policy_hash"]
    document_ids = sorted(row["id"] for row in manifest["documents"])
    membership_hash = _canonical_hash(document_ids)
    content_hash = _canonical_hash(sorted(row["content_hash"] for row in manifest["documents"]))
    now = _datetime(datetime.now(UTC).isoformat().replace("+00:00", "Z"))
    async with connect(APPROVED_TARGET, token=token) as database:
        await database.query(
            "CREATE ONLY context:phase1_surreal_t0_slice_r1 CONTENT $row;",
            {
                "row": {
                    "platform_id": APPROVED_TARGET.context_id,
                    "experiment_id": EXPERIMENT,
                    "environment": "phase1_t0_disposable",
                    "corpus_tier": "T0_SYNTHETIC",
                    "created_at": now,
                }
            },
        )
        await database.query(
            "CREATE ONLY type::record('projection_revision', $revision) CONTENT $row;",
            {
                "revision": REVISION_1,
                "row": {
                    "platform_id": REVISION_1,
                    "matter_id": MATTER,
                    "context_id": APPROVED_TARGET.context_id,
                    "membership_hash": membership_hash,
                    "content_hash": content_hash,
                    "policy_version": POLICY_VERSION,
                    "policy_hash": policy_hash,
                    "created_at": now,
                },
            },
        )
        await database.query(
            "CREATE ONLY type::record('projection_guard', $revision) CONTENT $row;",
            {
                "revision": REVISION_1,
                "row": {
                    "revision_id": REVISION_1,
                    "matter_id": MATTER,
                    "status": "building",
                    "reconciled_hash": None,
                    "quarantine_reason": None,
                    "checked_at": now,
                },
            },
        )
        for row in manifest["documents"]:
            visible_from = _datetime(row["visible_from"]) if row.get("visible_from") else None
            common = {
                "platform_id": row["id"],
                "matter_id": row["matter_id"],
                "projection_revision": row["projection_revision"],
                "policy_version": row["policy_version"],
                "policy_hash": policy_hash,
                "authority_state": row["authority_state"],
                "promotion_state": row["promotion_state"],
                "disclosure_tier": row["disclosure_tier"],
                "visible_from": visible_from,
            }
            await database.query(
                "CREATE ONLY type::record('retrieval_chunk', $id) CONTENT $row;",
                {
                    "id": row["id"],
                    "row": {
                        **common,
                        "content_hash": row["content_hash"],
                        "chunker_version": "chonkie.semantic-1.7.0-t0",
                        "source_family_id": f"family-{row['id']}",
                        "created_at": now,
                    },
                },
            )
            await database.query(
                "CREATE ONLY type::record('embedding_t0_v1', $id) CONTENT $row;",
                {
                    "id": row["id"],
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
            )
        reconciled_hash = _canonical_hash({"membership": membership_hash, "content": content_hash})
        await database.query(
            "UPDATE type::record('projection_guard', $revision) SET status = 'active', reconciled_hash = $hash, checked_at = $checked_at;",
            {"revision": REVISION_1, "hash": reconciled_hash, "checked_at": now},
        )
    return {
        "membership_hash": membership_hash,
        "content_hash": content_hash,
        "reconciled_hash": reconciled_hash,
        "object_count": len(manifest["documents"]),
    }


def _statement_results(raw: Any) -> list[Any]:
    if not isinstance(raw, dict):
        return []
    result = raw.get("result", [])
    if not isinstance(result, list):
        return []
    return [item.get("result") for item in result if isinstance(item, dict)]


async def _retrieve(
    private_key: bytes,
    *,
    mode: str,
    horizon_at: str,
) -> tuple[list[str], Any]:
    token = _token(
        private_key,
        principal="phase1_auditor",
        role="auditor",
        projection_revision=REVISION_1,
        mode=mode,
        horizon_at=horizon_at,
    )
    query = (ROOT / "queries" / "retrieve_exact.surql").read_text(encoding="utf-8")
    variables = {
        "matter_id": MATTER,
        "projection_revision": REVISION_1,
        "policy_version": POLICY_VERSION,
        "policy_hash": "sha256:5f36a9ebd0be02dbf8fc55c526480e49c3c9fc60a8d5a55540cbb87e4da550e5",
        "horizon_at": horizon_at,
        "mode": mode,
        "query_vector": QUERY_VECTOR,
        "top_k": 2,
    }
    async with connect(APPROVED_TARGET, token=token) as database:
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
        except Exception:
            return True
    return False


async def _quarantine(private_key: bytes) -> None:
    token = _token(
        private_key,
        principal="phase1_projector",
        role="projector",
        projection_revision=REVISION_1,
    )
    async with connect(APPROVED_TARGET, token=token) as database:
        await database.query(
            "UPDATE type::record('projection_guard', $revision) SET status = 'quarantined', quarantine_reason = 'SYNTHETIC_HASH_DRIFT', checked_at = $checked_at;",
            {
                "revision": REVISION_1,
                "checked_at": _datetime(datetime.now(UTC).isoformat()),
            },
        )


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
        stage = "projection"
        receipt = await _project(private_key, manifest)
        stage = "retrieve_early"
        early_ids, early_plan = await _retrieve(private_key, mode="as_lived_so_far", horizon_at="2024-06-01T00:00:00Z")
        stage = "retrieve_late"
        late_ids, _ = await _retrieve(private_key, mode="as_lived_so_far", horizon_at="2026-06-01T00:00:00Z")
        stage = "retrieve_hindsight"
        hindsight_ids, _ = await _retrieve(private_key, mode="hindsight", horizon_at="2024-06-01T00:00:00Z")
        stage = "negative_write"
        negative_write_denied = await _negative_write(private_key)
        stage = "quarantine"
        await _quarantine(private_key)
        stage = "post_quarantine_read"
        after_quarantine_ids, _ = await _retrieve(
            private_key, mode="as_lived_so_far", horizon_at="2024-06-01T00:00:00Z"
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
        "receipt": receipt,
        "retrieval": {
            "early_ids": early_ids,
            "late_ids": late_ids,
            "hindsight_ids": hindsight_ids,
            "after_quarantine_ids": after_quarantine_ids,
            "plan_observed": early_plan is not None,
        },
        "gates": {
            "early_exact_match": early_ids == manifest["expected"]["early_as_lived_ranked_ids"],
            "late_positive_control": late_ids == manifest["expected"]["late_as_lived_top_ids"],
            "hindsight_positive_control": hindsight_ids == manifest["expected"]["hindsight_top_ids"],
            "negative_write_denied": negative_write_denied,
            "quarantine_blocks_reads": after_quarantine_ids == [],
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
        }
    print(json.dumps(report, sort_keys=True), flush=True)
    if report["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
