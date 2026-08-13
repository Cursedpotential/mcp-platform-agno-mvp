"""
evidence/custody.py — the single entry gate for ALL evidence and source material.

ingest_artifact(src, source_meta) -> ArtifactRef:
  1. sha256 the file (streaming — files can be large)
  2. dedupe against evidence.evidence_hash (same digest -> same artifact, no rewrite)
  3. copy the raw blob WRITE-ONCE to the R2 mount (default /r2/evidence/<aa>/<sha>/<name>)
  4. INSERT the hash row (BYTEA digest, blob key, source meta) — append-only

This module is the ONLY writer of the `evidence` schema (chain-of-custody
guarantee). Agent DB connections ride the read-only engine (ADR-0005) and
physically cannot write here; this code path is invoked by workflows/CLI,
which sit behind the HITL gate at the agent boundary.

Pattern proven in extracted-code/sbv/sbv-ingestion.ts (hash -> insert -> rollback).
"""

from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from os import getenv
from pathlib import Path

from sqlalchemy import create_engine, text

_engine = None

# evidence.source.source_type CHECK set (migration 0005). Anything unmapped
# falls back to 'other' so the source INSERT never aborts on a bad enum.
_SOURCE_TYPES = frozenset(
    {
        "device_dump",
        "chat_export",
        "screenshot",
        "call_log",
        "pdf",
        "media",
        "takeout",
        "social_export",
        "document",
        "other",
    }
)
# evidence.source.acquisition_method CHECK set (nullable).
_ACQUISITION_METHODS = frozenset(
    {
        "forensic_image",
        "manual_export",
        "cloud_pull",
        "photograph",
        "scan",
        "backup",
    }
)


def _source_fields(path: Path, size: int, meta: dict) -> dict:
    """Derive the evidence.source columns from the ingest source_meta.

    Only sha256/byte_size/source_type/acquisition_source are NOT NULL with no
    default; everything else is optional. source_type/acquisition_method are
    validated against their CHECK sets and coerced to safe values so the
    file-level source row always inserts.
    """
    stype = str(meta.get("source_type") or "chat_export")
    if stype not in _SOURCE_TYPES:
        stype = "other"
    method = meta.get("acquisition_method")
    if method is not None and method not in _ACQUISITION_METHODS:
        method = None
    md5_hex = meta.get("md5") or meta.get("md5_prefilter")
    return {
        "size": size,
        "mime": meta.get("mime_type"),
        "fname": meta.get("original_name") or path.name,
        "stype": stype,
        "splat": meta.get("source_platform"),
        "acq": str(meta.get("acquisition_source") or "manual_export"),
        "meth": method,
        "bucket": meta.get("r2_bucket"),
        "key": meta.get("r2_key"),
        "lpath": str(path),
        "md5": bytes.fromhex(md5_hex) if isinstance(md5_hex, str) and md5_hex else None,
    }


def _get_engine():
    global _engine
    if _engine is None:
        from server.core.url import db_url

        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def blob_root() -> Path:
    """Where write-once blobs land. R2 rclone mount in the container (/r2),
    overridable for local runs/tests via EVIDENCE_BLOB_ROOT."""
    return Path(getenv("EVIDENCE_BLOB_ROOT", "/r2/evidence"))


@dataclass(frozen=True)
class ArtifactRef:
    """Immutable reference to an ingested artifact."""

    artifact_id: str
    sha256: str  # hex
    source_ref: str  # original path / object key
    blob_key: str  # where the write-once copy lives (relative to blob root)
    size_bytes: int
    duplicate: bool  # True if this digest was already in custody
    ingested_at: str  # ISO timestamp
    # Two-tier custody (operator-console-requirements.md addendum 2, C2).
    # 'full' (default) — unchanged historical behavior. 'light' — same
    # sha256+blob+dedupe write here, but the caller (workflows.py's
    # custody_step) records custody_tier='light' on the run so no FUTURE
    # per-record H2/H3 hashing hook is ever invoked for this artifact. See
    # the `tier` docstring on ingest_artifact() below for why this call site
    # itself has nothing extra to skip today.
    custody_tier: str = "full"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_artifact(src: str | Path, source_meta: dict | None = None, *, tier: str = "full") -> ArtifactRef:
    """Take custody of one file. Returns an immutable ArtifactRef.

    Idempotent: re-ingesting the same bytes returns the EXISTING artifact
    (duplicate=True) — custody rows and blobs are never overwritten.

    tier ('full' default | 'light', C2 two-tier custody — addendum 2):
    the write path here is IDENTICAL for both tiers today — sha256, dedupe
    check against evidence.evidence_hash, write-once blob copy, one H1
    evidence_hash + source row. ingest_artifact() has never generated H2/H3
    per-record chain rows itself (that only happens in
    reconcile_sbv_import(), a separate SBV-reconciliation path this linear
    custody step does not call) — so 'light' has nothing extra to skip at
    THIS call site. tier is still threaded through and stamped into
    meta['custody_tier'] (-> evidence.source.original_metadata) so: (a) the
    workflow's custody stage output and ops.workflow_run.custody_tier
    column can report it, and (b) any FUTURE per-record hashing hook added
    here can branch on it — 'light' must never call such a hook, 'full' may.
    The sole-writer boundary is unchanged: this function is still the only
    evidence-schema writer for the linear ingest path either way.
    """
    if tier not in ("full", "light"):
        raise ValueError(f"custody tier must be 'full' or 'light', got {tier!r}")

    path = Path(src)
    if not path.is_file():
        raise FileNotFoundError(f"custody: source file not found: {path}")

    sha_hex = _sha256_file(path)
    digest = bytes.fromhex(sha_hex)
    size = path.stat().st_size
    meta = dict(source_meta or {})
    meta.setdefault("original_name", path.name)
    meta.setdefault("size_bytes", size)
    meta["custody_tier"] = tier

    engine = _get_engine()

    # Dedupe: same digest == same artifact (chain-of-custody identity).
    with engine.connect() as conn:
        row = (
            conn.execute(
                text(
                    "SELECT id, source_ref, blob_key, hashed_at FROM evidence.evidence_hash "
                    "WHERE digest = :d AND algo = 'sha256' LIMIT 1"
                ),
                {"d": digest},
            )
            .mappings()
            .first()
        )
    if row is not None:
        # A duplicate hit reuses the EXISTING artifact regardless of which
        # tier this call requested — the artifact was already in custody.
        # We report this call's requested tier (not whatever the original
        # ingest used), since that's what this run's custody stage output
        # and workflow_run.custody_tier should reflect for THIS run.
        return ArtifactRef(
            artifact_id=str(row["id"]),
            sha256=sha_hex,
            source_ref=row["source_ref"],
            blob_key=row["blob_key"] or "",
            size_bytes=size,
            duplicate=True,
            ingested_at=row["hashed_at"].isoformat(),
            custody_tier=tier,
        )

    # Write-once blob copy: <aa>/<sha256>/<original-name>. Atomic + verified:
    # copy to a temp name, re-hash the copy, os.replace() into place — a crash
    # can never leave a partial file at the canonical sha-named path, and the
    # post-copy hash proves the blob on disk IS the bytes the chain attests.
    blob_key = f"{sha_hex[:2]}/{sha_hex}/{path.name}"
    dest = blob_root() / blob_key
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".tmp-copy")
        shutil.copyfile(path, tmp)
        copied_hex = _sha256_file(tmp)
        if copied_hex != sha_hex:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(
                f"blob copy verification failed for {path.name}: source {sha_hex[:12]}… vs copy {copied_hex[:12]}…"
            )
        os.replace(tmp, dest)
    # If it exists, content is identical by construction (path contains the sha).

    import json

    sf = _source_fields(path, size, meta)

    with engine.begin() as conn:
        # 1) File-level SOURCE row FIRST. The evidence_hash_subject_ck CHECK
        #    (live DDL captured in sql/_manual/20260802_reconcile_evidence_ddl.sql
        #    — NOT in numbered migrations; the earlier "migration 0005" citation
        #    here was wrong, 0005 is the workflow-run ledger) requires every
        #    H1/H2 hash to carry source_id (or file_node_id); only H3 chain
        #    hashes may omit it. Dedupe on the UNIQUE(sha256) so re-ingest
        #    reuses the same source.
        source_id = conn.execute(
            text(
                "INSERT INTO evidence.source "
                "(sha256, md5_prefilter, byte_size, mime_type, original_filename, "
                " source_type, source_platform, acquisition_source, acquisition_method, "
                " r2_bucket, r2_key, local_path, original_metadata) "
                "VALUES (:sha, :md5, :size, :mime, :fname, :stype, :splat, :acq, :meth, "
                " :bucket, :key, :lpath, CAST(:meta AS jsonb)) "
                "ON CONFLICT (sha256) DO UPDATE SET sha256 = EXCLUDED.sha256 "
                "RETURNING id"
            ),
            {"sha": digest, "meta": json.dumps(meta), **sf},
        ).scalar()

        # 2) H1 file-level custody hash, now carrying level + source_id so the
        #    subject CHECK is satisfied. digest/blob_key/meta unchanged.
        new = (
            conn.execute(
                text(
                    "INSERT INTO evidence.evidence_hash "
                    "(source_ref, algo, digest, blob_key, meta, level, source_id, "
                    " canon_version, computed_by) "
                    "VALUES (:src, 'sha256', :d, :bk, CAST(:meta AS jsonb), 'H1', :sid, "
                    " 'h1-rawbytes-v1', 'evidence.custody.ingest_artifact') "
                    "RETURNING id, hashed_at"
                ),
                {
                    "src": str(path),
                    "d": digest,
                    "bk": blob_key,
                    "meta": json.dumps(meta),
                    "sid": source_id,
                },
            )
            .mappings()
            .first()
        )

    return ArtifactRef(
        artifact_id=str(new["id"]),
        sha256=sha_hex,
        source_ref=str(path),
        blob_key=blob_key,
        size_bytes=size,
        duplicate=False,
        ingested_at=new["hashed_at"].isoformat() if isinstance(new["hashed_at"], datetime) else str(new["hashed_at"]),
        custody_tier=tier,
    )


def verify_artifact(artifact_id: str, file_path: str | Path) -> bool:
    """Re-hash a file and compare against the custody row (integrity check)."""
    sha_hex = _sha256_file(Path(file_path))
    with _get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT digest FROM evidence.evidence_hash WHERE id = :id"),
            {"id": artifact_id},
        ).first()
    return row is not None and row[0] == bytes.fromhex(sha_hex)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# =====================================================================================
# SBV forensic reconciliation (Phase 4) — THIN append-only extension of the
# ingest_artifact() pattern. SBV (the Go forensic fork) computes H1/H2/H3 over the
# RAW source bytes and exposes them over its REST API; it holds NO DB credentials.
# This module is still the ONLY writer of the `evidence` schema. Here we:
#   1. re-compute H1 INDEPENDENTLY (ingest_artifact) and CROSS-CHECK it against
#      SBV's H1 — match -> 'verified' custody_event; mismatch -> 'integrity_violation'.
#   2. on a verified match, record SBV's per-record H2s + the H3 batch chain as
#      evidence_hash rows (append-only), each with a custody_event.
# The H1 canonicalization is byte-identical on both sides (plain sha256 of raw
# bytes, h1-rawbytes-v1), so the two independently-derived H1s MUST agree for an
# unaltered file. See vendored/sbv/CUSTODY.md for the full H1/H2/H3 spec.
# =====================================================================================

# Canonicalization tags. H1/H2 match vendored/sbv/internal/custody.go.
# H3 DIVERGES DELIBERATELY (2026-08-02 hashing audit): the bare "h3-chain-v1"
# tag is ambiguous — the Case Bible vault writes an equally-valid H1-genesis
# chain under the SAME tag. New rows written by THIS module carry a tag that
# names the construction (SBV fold, genesis = empty string). Rows already
# recorded with the legacy tag are NEVER relabelled (that would be tampering);
# disambiguate legacy rows by writer, per docs/DECISION_LOG.md 2026-08-02.
H1_CANON = "h1-rawbytes-v1"
H2_CANON = "h2-rawelement-v1"
H3_CANON = "h3-chain-sbv-genesisempty-v1"
H3_CANON_LEGACY = "h3-chain-v1"  # pre-2026-08-02 rows; ambiguous, read-only


def _source_id_for_hash(conn, evidence_hash_id: str) -> str | None:
    """Resolve the evidence.source id that an evidence_hash row points at."""
    row = conn.execute(
        text("SELECT source_id FROM evidence.evidence_hash WHERE id = :id"),
        {"id": evidence_hash_id},
    ).first()
    return str(row[0]) if row is not None and row[0] is not None else None


def record_custody_event(
    source_id: str,
    event_type: str,
    actor: str,
    detail: dict | None = None,
    evidence_hash_id: str | None = None,
    file_node_id: str | None = None,
) -> str:
    """Append one chain-of-custody event. The DB trigger (custody_event_chain)
    computes the hash-chained event_digest; we never set it here. Append-only."""
    import json

    engine = _get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO evidence.custody_event "
                "(source_id, file_node_id, evidence_hash_id, event_type, actor, detail) "
                "VALUES (:sid, :fnid, :ehid, :etype, :actor, CAST(:detail AS jsonb)) "
                "RETURNING id"
            ),
            {
                "sid": source_id,
                "fnid": file_node_id,
                "ehid": evidence_hash_id,
                "etype": event_type,
                "actor": actor,
                "detail": json.dumps(detail or {}),
            },
        ).first()
    return str(row[0])


def record_evidence_hash(
    *,
    level: str,
    digest_hex: str,
    canon_version: str,
    computed_by: str,
    source_id: str | None = None,
    file_node_id: str | None = None,
    record_locator: dict | None = None,
    meta: dict | None = None,
) -> str:
    """Append one H2/H3 evidence_hash row (append-only). digest_hex is a sha256
    hex string; stored as the 32-byte BYTEA the schema's CHECK requires."""
    import json

    engine = _get_engine()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO evidence.evidence_hash "
                "(source_ref, algo, digest, level, source_id, file_node_id, "
                " record_locator, canon_version, computed_by, meta) "
                "VALUES (:src, 'sha256', :dig, :level, :sid, :fnid, "
                " CAST(:rl AS jsonb), :canon, :by, CAST(:meta AS jsonb)) "
                "RETURNING id"
            ),
            {
                "src": computed_by,
                "dig": bytes.fromhex(digest_hex),
                "level": level,
                "sid": source_id,
                "fnid": file_node_id,
                "rl": json.dumps(record_locator) if record_locator is not None else None,
                "canon": canon_version,
                "by": computed_by,
                "meta": json.dumps(meta or {}),
            },
        ).first()
    return str(row[0])


def reconcile_sbv_import(
    src: str | Path,
    source_meta: dict | None,
    *,
    sbv_file_hash: str | None,
    sbv_record_hashes: list[str] | None = None,
    sbv_chain_hash: str | None = None,
    # Audit-trail actor tag persisted to evidence.custody_event rows. Renamed
    # from "server.evidence.tools.sbv_sms" 2026-07-11 after ADR-0033/0035 moved
    # the module; live table held 0 rows at rename time (verified), so no
    # historical event carries the old label (append-only chain unaffected).
    actor: str = "server.tools.parsers.messaging.sbv_sms",
) -> dict:
    """Cross-check SBV's H1 against our own, then record H2/H3 evidence + events.

    Returns a summary dict. On an H1 mismatch we emit ONLY the integrity_violation
    event and deliberately do NOT record SBV's derived H2/H3 (they cannot be
    trusted if the file itself disagrees).
    """
    ref = ingest_artifact(src, source_meta)  # our INDEPENDENT H1 (+ write-once blob)
    our_h1 = ref.sha256
    sbv_h1 = (sbv_file_hash or "").strip().lower()
    verified = bool(sbv_h1) and sbv_h1 == our_h1.lower()

    with _get_engine().connect() as conn:
        source_id = _source_id_for_hash(conn, ref.artifact_id)

    event_type = "verified" if verified else "integrity_violation"
    detail = {
        "our_h1": our_h1,
        "sbv_h1": sbv_file_hash,
        "canon": H1_CANON,
        "sbv_chain_hash": sbv_chain_hash,
        "record_count": len(sbv_record_hashes or []),
        "artifact_id": ref.artifact_id,
        "duplicate": ref.duplicate,
    }
    if source_id is not None:
        record_custody_event(source_id, event_type, actor, detail=detail, evidence_hash_id=ref.artifact_id)

    h2_ids: list[str] = []
    h3_id: str | None = None
    if verified and source_id is not None:
        for i, h2 in enumerate(sbv_record_hashes or []):
            if not h2:
                continue
            h2_ids.append(
                record_evidence_hash(
                    level="H2",
                    digest_hex=h2,
                    canon_version=H2_CANON,
                    computed_by="sbv:internal.custody.HashRecordH2",
                    source_id=source_id,
                    record_locator={"record_index": i},
                )
            )
        if sbv_chain_hash:
            h3_id = record_evidence_hash(
                level="H3",
                digest_hex=sbv_chain_hash,
                canon_version=H3_CANON,
                computed_by="sbv:internal.custody.ChainH3",
                source_id=source_id,
                meta={"record_count": len(sbv_record_hashes or [])},
            )

    return {
        "verified": verified,
        "event": event_type,
        "artifact_id": ref.artifact_id,
        "our_h1": our_h1,
        "sbv_h1": sbv_file_hash,
        "source_id": source_id,
        "h2_hash_ids": h2_ids,
        "h3_hash_id": h3_id,
        "record_count": len(sbv_record_hashes or []),
    }
