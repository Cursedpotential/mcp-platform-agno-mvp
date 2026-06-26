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
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from os import getenv
from pathlib import Path

from sqlalchemy import create_engine, text

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from db.url import db_url

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


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ingest_artifact(src: str | Path, source_meta: dict | None = None) -> ArtifactRef:
    """Take custody of one file. Returns an immutable ArtifactRef.

    Idempotent: re-ingesting the same bytes returns the EXISTING artifact
    (duplicate=True) — custody rows and blobs are never overwritten.
    """
    path = Path(src)
    if not path.is_file():
        raise FileNotFoundError(f"custody: source file not found: {path}")

    sha_hex = _sha256_file(path)
    digest = bytes.fromhex(sha_hex)
    size = path.stat().st_size
    meta = dict(source_meta or {})
    meta.setdefault("original_name", path.name)
    meta.setdefault("size_bytes", size)

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
        return ArtifactRef(
            artifact_id=str(row["id"]),
            sha256=sha_hex,
            source_ref=row["source_ref"],
            blob_key=row["blob_key"] or "",
            size_bytes=size,
            duplicate=True,
            ingested_at=row["hashed_at"].isoformat(),
        )

    # Write-once blob copy: <aa>/<sha256>/<original-name>
    blob_key = f"{sha_hex[:2]}/{sha_hex}/{path.name}"
    dest = blob_root() / blob_key
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
    # If it exists, content is identical by construction (path contains the sha).

    import json

    with engine.begin() as conn:
        new = (
            conn.execute(
                text(
                    "INSERT INTO evidence.evidence_hash (source_ref, algo, digest, blob_key, meta) "
                    "VALUES (:src, 'sha256', :d, :bk, CAST(:meta AS jsonb)) "
                    "RETURNING id, hashed_at"
                ),
                {"src": str(path), "d": digest, "bk": blob_key, "meta": json.dumps(meta)},
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
