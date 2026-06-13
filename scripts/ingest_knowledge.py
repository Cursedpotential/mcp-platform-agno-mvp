"""
Knowledge ingestion — scan knowledge/platform/, normalize, knowledge.ainsert()
==============================================================================

Deterministic normalize + manifest, then hand PATHS to Agno's native insert
(handoff §7.1/§9.1 — do NOT write a custom loader; Agno reads/chunks/embeds).

Run inside the container:
    docker exec agentos-api python -m agents.ingestion

Rules (handoff §9.1):
  - allowlist extensions; reject binaries/archives/media
  - files > 50 MB -> skipped, flagged for manual review
  - category derived from parent folder (conversations / docs / notes)
  - original source path preserved in metadata
  - Secrets/ and case-data dirs are NEVER under knowledge/platform
"""

import asyncio
import re
from os import getenv
from pathlib import Path

ALLOWED_EXT = {".md", ".txt", ".json", ".csv", ".pdf", ".docx"}
MAX_SIZE = 50 * 1024 * 1024  # 50 MB
BASE_PATH = Path(getenv("KNOWLEDGE_BASE_PATH", "/app/knowledge/platform"))

_SAFE = re.compile(r"[^a-z0-9\-_.]+")


def _safe_name(stem: str) -> str:
    """Lowercase kebab-case, max 127 chars (handoff §9.1 filename regex)."""
    name = _SAFE.sub("-", stem.lower()).strip("-.")
    return (name or "unnamed")[:127]


async def ingest_all(knowledge) -> int:
    count = 0
    skipped: list[str] = []
    for path in sorted(BASE_PATH.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in ALLOWED_EXT:
            continue
        if path.stat().st_size > MAX_SIZE:
            skipped.append(str(path))
            print(f"  SKIP (>50MB, manual review): {path}")
            continue
        category = path.parent.name  # conversations / docs / notes
        name = _safe_name(path.stem)
        print(f"  inserting [{category}] {name}")
        await knowledge.ainsert(
            name=name,
            path=str(path),
            metadata={"category": category, "source_path": str(path)},
        )
        count += 1
    if skipped:
        print(f"{len(skipped)} file(s) need manual review (size).")
    return count


async def main() -> None:
    from db import create_knowledge

    knowledge = create_knowledge("platform", "platform_knowledge")
    print(f"Ingesting from {BASE_PATH} ...")
    n = await ingest_all(knowledge)
    print(f"Done. {n} document(s) indexed.")


if __name__ == "__main__":
    asyncio.run(main())
