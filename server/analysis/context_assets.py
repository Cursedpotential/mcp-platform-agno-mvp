"""server/analysis/context_assets.py — materialize a chat-export archive's
generated documents / code / images into the CONTEXT asset store.

The whole-unit half of the archive pipeline (owner 2026-08-12: "whether or not
it's zipped or unzipped it's processed as a whole unit and ... the data within
it is properly parsed and saved"). `chat_archive.py` handles the conversation
logs; this module handles everything else the archive carries:

  * a `working.context_archive` manifest row per archive (dedup by the zip's
    own sha256), holding the sidecar metadata (users/projects/memories.json);
  * one `working.context_asset` row per non-log/non-metadata payload, wherever
    the provider placed it — classified
    document | code | image | data | other (owner: docs -> a document store,
    code snippets -> a code store), bytes written to R2, small text assets also
    stored INLINE so they are queryable without a fetch.

CONTEXT tier, Option B (sql/0022): these are context tables, NOT the
evidence-tier `working.artifact_registry` — no evidence coupling. Idempotent:
`context_asset.content_hash` (sha256 of bytes) is UNIQUE, so re-materializing an
archive re-uploads nothing already present.

R2 is reached the SAME way the evidence spine reaches it — the rclone MOUNT
(`server/evidence/custody.py::blob_root` writes write-once blobs to `/r2/...`),
NOT the boto3 S3 API — so this adds no new dependency and behaves identically
in-cluster. The context blob root is `CONTEXT_BLOB_ROOT` (default
`/r2/context-assets`); off-box it can point at a local dir or a mounted R2
drive. `dry_run=True` classifies + counts + sizes WITHOUT hashing or writing —
the cost-scope preview (R2 writes are billable).
"""
# Byline: Claude Code · Opus 4.8 · 2026-08-12
# Byline: Codex · GPT-5 · 2026-08-13 (whole-archive multimodal extraction)

from __future__ import annotations

import hashlib
import json
import mimetypes
import zipfile
from dataclasses import dataclass, field
from os import getenv
from pathlib import Path
from typing import Any

from sqlalchemy import text

from server.tools.registry import load_builtin_tools, registry

# extension -> routed category (owner's document-store / code-store split)
_CATEGORY: dict[str, str] = {
    **{e: "document" for e in ("pdf", "md", "txt", "doc", "docx", "rtf", "html", "htm")},
    **{
        e: "code"
        for e in (
            "py",
            "sql",
            "js",
            "ts",
            "tsx",
            "jsx",
            "sh",
            "go",
            "rs",
            "java",
            "c",
            "cpp",
            "h",
            "css",
            "yaml",
            "yml",
            "toml",
            "ipynb",
        )
    },
    **{e: "image" for e in ("png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "tiff")},
    **{e: "data" for e in ("csv", "xlsx", "xls", "parquet", "json", "ndjson")},
}
# small text categories worth storing inline (queryable without an R2 fetch)
_INLINE_EXTS = frozenset({"md", "txt", "py", "sql", "js", "ts", "sh", "go", "rs", "csv", "yaml", "yml", "html", "htm"})
_INLINE_MAX_BYTES = 100_000

_ASSET_DIRS = ("assets/", "dalle-generations/")
_METADATA_BASENAMES = frozenset(
    {
        "users.json",
        "user.json",
        "projects.json",
        "memories.json",
        "message_feedback.json",
        "model_comparisons.json",
        "shared_conversations.json",
    }
)


def _ext(member: str) -> str:
    base = member.rsplit("/", 1)[-1]
    return base.rsplit(".", 1)[-1].lower() if "." in base else ""


def categorize(member: str) -> str:
    return _CATEGORY.get(_ext(member), "other")


def _is_asset(member: str) -> bool:
    return any(seg in member.replace("\\", "/").lower() for seg in _ASSET_DIRS)


def _is_conversation_log(member: str) -> bool:
    base = member.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return base.startswith("conversations") and base.endswith(".json") and not _is_asset(member)


def modality(member: str) -> str:
    ext = _ext(member)
    if categorize(member) == "code":
        return "code"
    if categorize(member) in {"document", "data"}:
        return "text"
    if categorize(member) == "image":
        return "image"
    if ext in {"mp3", "wav", "m4a", "aac", "flac", "ogg"}:
        return "audio"
    if ext in {"mp4", "mov", "mkv", "webm", "avi"}:
        return "video"
    return "binary"


def origin_kind(member: str) -> str:
    norm = member.replace("\\", "/").lower()
    return "generated_work" if "dalle-generations/" in norm else "export_asset"


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def context_blob_root() -> Path:
    """Where context asset blobs land — the R2 rclone mount, mirroring
    `custody.blob_root()`. Overridable via CONTEXT_BLOB_ROOT for local
    runs/tests or a mounted R2 drive."""
    return Path(getenv("CONTEXT_BLOB_ROOT", "/r2/context-assets"))


@dataclass
class AssetPlan:
    """What WOULD be materialized (dry-run) or was (real run)."""

    member: str
    category: str
    ext: str
    byte_size: int


@dataclass
class MaterializeReport:
    archive_path: str
    archive_sha256: str
    provider: str | None
    metadata_files: list[str]
    asset_total: int
    asset_bytes: int
    by_category: dict[str, int] = field(default_factory=dict)
    uploaded: int = 0
    deduped: int = 0
    dry_run: bool = True
    r2_bucket: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


def _r2_key(content_hash: str, ext: str) -> str:
    # sharded by hash prefix; content-addressed so identical bytes dedupe
    return f"context-assets/{content_hash[:2]}/{content_hash}{('.' + ext) if ext else ''}"


def materialize_archive(
    zip_path: str | Path,
    *,
    provider: str | None = None,
    engine: Any | None = None,
    dry_run: bool = True,
    blob_root: str | Path | None = None,
) -> MaterializeReport:
    """Save the archive manifest + metadata to `working.context_archive` and
    materialize its `assets/` into `working.context_asset` (+ blobs under the
    R2 mount). `engine` is the SQLAlchemy engine (defaults to the context
    lane's); `blob_root` defaults to `context_blob_root()`. `dry_run=True`
    (default) only classifies/counts/sizes — no hashing, no write, no rows — so
    the R2 cost scope can be reviewed first.
    """
    zp = Path(zip_path)
    if engine is None:
        from server.analysis.context_chat_ingest import _get_engine

        engine = _get_engine()
    root = Path(blob_root) if blob_root is not None else context_blob_root()

    with zipfile.ZipFile(zp) as zf:
        infos = [i for i in zf.infolist() if not i.filename.endswith("/")]
        # Every non-log, non-metadata payload is a created work or attachment,
        # regardless of whether the provider placed it under assets/.
        assets = [
            i
            for i in infos
            if not _is_conversation_log(i.filename) and i.filename.rsplit("/", 1)[-1].lower() not in _METADATA_BASENAMES
        ]
        metadata_members = [
            i.filename
            for i in infos
            if i.filename.rsplit("/", 1)[-1].lower() in ("users.json", "user.json", "projects.json", "memories.json")
        ]
        by_cat: dict[str, int] = {}
        asset_bytes = 0
        for i in assets:
            by_cat[categorize(i.filename)] = by_cat.get(categorize(i.filename), 0) + 1
            asset_bytes += i.file_size

        report = MaterializeReport(
            archive_path=str(zp),
            archive_sha256="(dry-run)" if dry_run else "",
            provider=provider,
            metadata_files=metadata_members,
            asset_total=len(assets),
            asset_bytes=asset_bytes,
            by_category=by_cat,
            dry_run=dry_run,
            r2_bucket=str(root),
        )
        if dry_run:
            return report

        # --- real run ---
        archive_sha = _sha256_file(zp)
        report.archive_sha256 = archive_sha
        metadata_blob: dict[str, Any] = {}
        for m in metadata_members:
            try:
                metadata_blob[m.rsplit("/", 1)[-1]] = json.loads(zf.read(m).decode("utf-8", "replace"))
            except Exception:  # noqa: BLE001 - metadata is best-effort context, never fatal
                metadata_blob[m.rsplit("/", 1)[-1]] = {"_unparsed": True}

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO working.context_archive "
                    "(archive_path, archive_sha256, provider, conversation_log_count, asset_count, metadata, manifest) "
                    "VALUES (:p, :sha, :prov, :logs, :assets, CAST(:meta AS jsonb), CAST(:man AS jsonb)) "
                    "ON CONFLICT (archive_sha256) DO UPDATE SET asset_count = EXCLUDED.asset_count "
                    "RETURNING id"
                ),
                {
                    "p": str(zp),
                    "sha": archive_sha,
                    "prov": provider,
                    "logs": sum(1 for i in infos if i.filename.rsplit("/", 1)[-1].lower().startswith("conversations")),
                    "assets": len(assets),
                    "meta": json.dumps(metadata_blob),
                    "man": json.dumps({"by_category": by_cat, "asset_bytes": asset_bytes}),
                },
            )
            archive_id = conn.execute(
                text("SELECT id FROM working.context_archive WHERE archive_sha256 = :sha"), {"sha": archive_sha}
            ).scalar()

        for i in assets:
            data = zf.read(i.filename)
            chash = _sha256_bytes(data)
            ext = _ext(i.filename)
            category = categorize(i.filename)
            asset_modality = modality(i.filename)
            media_type = mimetypes.guess_type(i.filename)[0]
            asset_origin = origin_kind(i.filename)
            key = _r2_key(chash, ext)
            inline = None
            if ext in _INLINE_EXTS and len(data) <= _INLINE_MAX_BYTES:
                inline = data.decode("utf-8", "replace")

            # idempotency: skip if this content_hash already indexed
            with engine.begin() as conn:
                exists = conn.execute(
                    text("SELECT 1 FROM working.context_asset WHERE content_hash = :h"), {"h": chash}
                ).scalar()
                if exists:
                    report.deduped += 1
                    continue

            # write-once blob to the R2 mount (content-addressed; skip if present)
            blob_path = root / key
            blob_path.parent.mkdir(parents=True, exist_ok=True)
            if not blob_path.exists():
                blob_path.write_bytes(data)
            with engine.begin() as conn:
                conn.execute(
                    text(
                        "INSERT INTO working.context_asset "
                        "(archive_id, member_path, asset_category, file_ext, content_hash, byte_size, r2_bucket, r2_key, "
                        "content_inline, origin_kind, media_type, modality) "
                        "VALUES (:aid, :mp, :cat, :ext, :h, :sz, :bkt, :key, :inline, :origin_kind, :media_type, :modality) "
                        "ON CONFLICT (content_hash) DO NOTHING"
                    ),
                    {
                        "aid": archive_id,
                        "mp": i.filename,
                        "cat": category,
                        "ext": ext,
                        "h": chash,
                        "sz": len(data),
                        "bkt": str(root),
                        "key": key,
                        "inline": inline,
                        "media_type": media_type,
                        "modality": asset_modality,
                        "origin_kind": asset_origin,
                    },
                )
                asset_id = conn.execute(
                    text("SELECT id FROM working.context_asset WHERE content_hash = :h"), {"h": chash}
                ).scalar_one()
                basename = i.filename.replace("\\", "/").rsplit("/", 1)[-1]
                linked = conn.execute(
                    text(
                        "INSERT INTO working.context_asset_message (asset_id, message_id, relationship) "
                        "SELECT CAST(:asset_id AS uuid), m.id, 'attached_to' "
                        "FROM working.chat_message m "
                        "WHERE m.attrs->>'archive' = :archive "
                        "AND (m.attachments ? :member OR m.attachments ? :basename) "
                        "ON CONFLICT DO NOTHING RETURNING message_id"
                    ),
                    {
                        "asset_id": asset_id,
                        "archive": str(zp),
                        "member": i.filename,
                        "basename": basename,
                    },
                ).first()
                if linked and asset_origin == "export_asset":
                    conn.execute(
                        text(
                            "UPDATE working.context_asset SET origin_kind = 'attachment' WHERE id = CAST(:id AS uuid)"
                        ),
                        {"id": asset_id},
                    )
            report.uploaded += 1

    return report


def extract_asset_text(asset_id: str, *, engine: Any | None = None) -> dict[str, Any]:
    """Run the registered native-text/OCR tool for one stored image or PDF.

    OCR is a lossy derived representation. The original R2 object is unchanged;
    low-confidence output is retained and marked for vision-model escalation.
    """

    if engine is None:
        from server.analysis.context_chat_ingest import _get_engine

        engine = _get_engine()
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "SELECT id, r2_bucket, r2_key, byte_size, member_path "
                    "FROM working.context_asset WHERE id = CAST(:id AS uuid)"
                ),
                {"id": asset_id},
            )
            .mappings()
            .one()
        )
    asset_path = Path(row["r2_bucket"]) / row["r2_key"]
    load_builtin_tools()
    tools = reference.resolve("extract.text", media_hint=row["member_path"], size_bytes=row["byte_size"] or 0)
    tools = sorted(
        tools,
        key=lambda candidate: (
            0 if candidate.id == "documents.extract-text" else 1 if candidate.id == "documents.extract-docling" else 2
        ),
    )
    if not tools:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE working.context_asset SET extraction_status = 'unsupported' WHERE id = CAST(:id AS uuid)"),
                {"id": asset_id},
            )
        return {"asset_id": asset_id, "status": "unsupported"}

    failures: list[str] = []
    for tool in tools:
        try:
            result = tool.run({"path": str(asset_path)})
        except Exception as exc:
            failures.append(f"{tool.id}: {exc}")
            continue
        low_confidence = bool(result.get("stats", {}).get("low_confidence"))
        status = "low_confidence" if low_confidence else "completed"
        with engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE working.context_asset SET extracted_text = :content, extraction_tool_id = :tool_id, "
                    "extraction_status = :status WHERE id = CAST(:id AS uuid)"
                ),
                {"content": result.get("text", ""), "tool_id": tool.id, "status": status, "id": asset_id},
            )
        return {"asset_id": asset_id, "status": status, "tool_id": tool.id, **result}
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE working.context_asset SET extraction_status = 'failed' WHERE id = CAST(:id AS uuid)"),
            {"id": asset_id},
        )
    raise RuntimeError(f"asset text extraction failed for {asset_id}: {'; '.join(failures)}")
