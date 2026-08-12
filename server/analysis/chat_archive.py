"""server/analysis/chat_archive.py — the ZIP front door for chat exports.

Real AI-chat exports do NOT arrive as a bare `conversations.json` — they come
as a ZIP with multiple files (owner, 2026-08-12: "the real ones come in a zip
file with multiple different folders and json logs and files"). Two real
shapes seen on disk:

  * Claude   `data-*.zip` → conversations.json + users.json + projects.json + memories.json
  * ChatGPT/Perplexity `user_data_export_*.zip` → conversations-*.json + a
    spreadsheet + an `assets/` folder of PDFs / PNGs / .md (generated docs,
    images, code snippets).

This module is the front door: open the archive WITHOUT extracting the whole
thing (memory- and disk-safe — an `assets/` folder can be hundreds of files),
find the conversation log(s), extract ONLY those to a temp file, and hand each
to the engine-dynamic `ingest_chat_file`. Everything else (metadata jsons, the
`assets/` payload) is INVENTORIED and reported, never silently dropped — the
`assets/` materialization into a document/code store is a deliberate later
stage (owner's Stage-2 requirement), and this module surfaces exactly what is
waiting for it.

Downstream is unchanged: each conversation log flows parse → PG
`working.context_record` → change-detection → Weaviate/Graphiti, exactly as a
bare file would.
"""
# Byline: Claude Code · Opus 4.8 · 2026-08-12

from __future__ import annotations

import posixpath
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# A member is a conversation LOG if its basename matches one of these and it is
# NOT inside an assets/ payload folder. Providers vary the exact name
# (conversations.json, conversations-<stamp>.json), so match on prefix+suffix.
_CONV_PREFIXES = ("conversations",)
_CONV_SUFFIX = ".json"
# Sidecar metadata we recognise but do NOT parse as a transcript (routed later).
_METADATA_BASENAMES = frozenset(
    {"users.json", "user.json", "projects.json", "memories.json", "message_feedback.json", "model_comparisons.json", "shared_conversations.json"}
)
_ASSET_DIRS = ("assets/", "dalle-generations/")


def _basename(member: str) -> str:
    return posixpath.basename(member.replace("\\", "/"))


def _is_conversation_log(member: str) -> bool:
    norm = member.replace("\\", "/")
    if any(seg in norm.lower() for seg in _ASSET_DIRS):
        return False
    base = _basename(norm).lower()
    return base.endswith(_CONV_SUFFIX) and any(base.startswith(p) for p in _CONV_PREFIXES)


def _is_asset(member: str) -> bool:
    return any(seg in member.replace("\\", "/").lower() for seg in _ASSET_DIRS)


@dataclass
class ArchiveInventory:
    """What a chat-export archive contains, classified — so the deferred parts
    (assets, sidecar metadata) are visible, never silently dropped."""

    zip_path: str
    conversation_logs: list[str] = field(default_factory=list)
    metadata_files: list[str] = field(default_factory=list)
    asset_files: list[str] = field(default_factory=list)
    other_files: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "zip_path": self.zip_path,
            "conversation_logs": self.conversation_logs,
            "metadata_files": self.metadata_files,
            "asset_count": len(self.asset_files),
            "asset_sample": self.asset_files[:10],
            "other_files": self.other_files,
        }


def inventory_archive(zip_path: str | Path) -> ArchiveInventory:
    """Classify every member of the archive WITHOUT extracting anything."""
    zp = Path(zip_path)
    inv = ArchiveInventory(zip_path=str(zp))
    with zipfile.ZipFile(zp) as zf:
        for info in zf.infolist():
            name = info.filename
            if name.endswith("/"):
                continue  # directory entry
            if _is_conversation_log(name):
                inv.conversation_logs.append(name)
            elif _is_asset(name):
                inv.asset_files.append(name)
            elif _basename(name).lower() in _METADATA_BASENAMES:
                inv.metadata_files.append(name)
            else:
                inv.other_files.append(name)
    return inv


def _safe_extract_member(zf: zipfile.ZipFile, member: str, dest_dir: Path) -> Path:
    """Extract ONE member to dest_dir with a zip-slip guard (never let a
    crafted member escape the destination). Returns the written path."""
    dest_dir = dest_dir.resolve()
    target = (dest_dir / _basename(member)).resolve()
    if not str(target).startswith(str(dest_dir)):
        raise ValueError(f"zip member {member!r} escapes extraction dir (zip-slip)")
    with zf.open(member) as src, open(target, "wb") as out:
        while True:
            chunk = src.read(1024 * 1024)  # stream — never load the whole log into memory
            if not chunk:
                break
            out.write(chunk)
    return target


@dataclass
class ArchiveIngestReport:
    inventory: dict[str, Any]
    logs_ingested: list[dict[str, Any]]  # one IngestReport-as-dict per conversation log
    deferred_assets: int
    deferred_metadata: list[str]
    assets_materialized: dict[str, Any] | None = None  # MaterializeReport-as-dict when materialize_assets=True


async def ingest_chat_archive(
    zip_path: str | Path,
    *,
    engine: str = "auto",
    format: str | None = None,
    conversation_ids: set[str] | None = None,
    max_chars: int | None = None,
    dry_run: bool = False,
    project: bool = True,
    materialize_assets: bool = False,
    knowledge: Any | None = None,
    graphiti_client: Any | None = None,
) -> ArchiveIngestReport:
    """Ingest every conversation log inside a chat-export ZIP through the
    engine-dynamic pipeline. Extracts ONLY the log file(s) — the `assets/`
    payload and sidecar metadata are inventoried and reported for a later
    materialization stage, not touched here.

    Raises ValueError if the archive contains no recognisable conversation log
    (so a wrong/empty zip fails loudly instead of silently ingesting nothing).
    """
    from dataclasses import asdict

    from server.analysis.context_chat_ingest import DEFAULT_MAX_CHARS, ingest_chat_file

    inv = inventory_archive(zip_path)
    if not inv.conversation_logs:
        raise ValueError(
            f"no conversation log (conversations*.json) found in {zip_path!r}; "
            f"members classified: {len(inv.metadata_files)} metadata, {len(inv.asset_files)} assets, "
            f"{len(inv.other_files)} other"
        )

    logs_out: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path) as zf, tempfile.TemporaryDirectory(prefix="chatzip_") as tmp:
        tmp_dir = Path(tmp)
        for member in inv.conversation_logs:
            extracted = _safe_extract_member(zf, member, tmp_dir)
            report = await ingest_chat_file(
                extracted,
                source_meta={"archive": str(zip_path), "archive_member": member},
                conversation_ids=conversation_ids,
                max_chars=max_chars if max_chars is not None else DEFAULT_MAX_CHARS,
                dry_run=dry_run,
                project=project,
                engine=engine,
                format=format,
                knowledge=knowledge,
                graphiti_client=graphiti_client,
            )
            logs_out.append({"member": member, **asdict(report)})

    # Whole-unit: optionally materialize the archive's assets + metadata too
    # (owner: "the data within it is properly parsed and saved"). Off by default
    # so a conversation-only ingest doesn't trigger blob writes; always
    # runs a dry-run preview so the report shows what WOULD/DID materialize.
    from server.analysis.context_assets import materialize_archive

    mat = materialize_archive(zip_path, dry_run=dry_run or not materialize_assets)
    return ArchiveIngestReport(
        inventory=inv.as_dict(),
        logs_ingested=logs_out,
        deferred_assets=len(inv.asset_files),
        deferred_metadata=inv.metadata_files,
        assets_materialized=mat.as_dict(),
    )
