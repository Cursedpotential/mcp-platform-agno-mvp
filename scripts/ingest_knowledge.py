"""Framework-neutral folder-walk ingestion into canonical PostgreSQL.
=====================================================================

Every accepted path enters the same Horizon ingest port used by Workbench.
Agno may later project committed rows, but it does not own this contract.

Run inside the container:
    docker exec agentos-api python -m scripts.ingest_knowledge

Rules (handoff §9.1):
  - allowlist extensions; reject binaries/archives/media
  - files > 50 MB -> skipped, flagged for manual review
  - category derived from parent folder (conversations / docs / notes)
  - original source path preserved in metadata
  - Secrets/ and case-data dirs are NEVER under the knowledge roots

MULTI-ROOT (2026-08-01)
-----------------------
This walked ONLY ``/app/knowledge/platform`` for months, so
``/app/knowledge/legal/`` — which holds the coercive-control classification
rubrics — was never indexed and no agent could retrieve it. The rubrics are the
analytical core of Part 2 (PROJECT_CANON §1), so that was the single largest
retrieval gap in the platform.

Roots are now explicit and each carries a ``domain`` tag, matching the canon's
domain-separation requirement (§3): agents filter on ``domain`` to pull only
the lanes relevant to them, instead of one undifferentiated corpus.

Byline: Codex · GPT-5 · 2026-08-16
"""

import asyncio
import re
from os import getenv
from pathlib import Path

ALLOWED_EXT = {".md", ".txt", ".json", ".csv", ".pdf", ".docx"}
MAX_SIZE = 50 * 1024 * 1024  # 50 MB

# lane -> root (ADR-0050 six-lane vocabulary). KNOWLEDGE_BASE_PATH still
# overrides the platform root so the existing env contract keeps working;
# KNOWLEDGE_LEGAL_PATH does the same for legal. A root that does not exist is
# skipped, not fatal. NOTE deliberate absences: `evidence` has NO folder-walk
# root, ever — its only writer is the custody path (ADR-0050 §4); `context`
# ingests via server/analysis/context_chat_ingest.py, not a folder walk.
KNOWLEDGE_ROOTS: dict[str, Path] = {
    "platform": Path(getenv("KNOWLEDGE_BASE_PATH", "/app/knowledge/platform")),
    "legal": Path(getenv("KNOWLEDGE_LEGAL_PATH", "/app/knowledge/legal")),
    "personal_history": Path(getenv("KNOWLEDGE_PERSONAL_HISTORY_PATH", "/app/knowledge/personal_history")),
    "relationship_timeline": Path(
        getenv("KNOWLEDGE_RELATIONSHIP_TIMELINE_PATH", "/app/knowledge/relationship_timeline")
    ),
}

_SAFE = re.compile(r"[^a-z0-9\-_.]+")


def _safe_name(stem: str) -> str:
    """Lowercase kebab-case, max 127 chars (handoff §9.1 filename regex)."""
    name = _SAFE.sub("-", stem.lower()).strip("-.")
    return (name or "unnamed")[:127]


async def ingest_all(_knowledge=None, bases: dict | None = None) -> int:
    """Ingest every knowledge root through the platform-owned port.

    The legacy arguments remain temporarily source-compatible for callers, but
    are deliberately ignored. No framework object crosses the ingest contract.
    """
    from server.contracts.ingest import IngestLane, IngestRequest
    from server.ingest.service import ingest_file

    del bases
    count = 0
    skipped: list[str] = []
    for domain, root in KNOWLEDGE_ROOTS.items():
        if not root.is_dir():
            print(f"  root missing, skipping: [{domain}] {root}")
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in ALLOWED_EXT:
                continue
            if path.stat().st_size > MAX_SIZE:
                skipped.append(str(path))
                print(f"  SKIP (>50MB, manual review): {path}")
                continue
            # For a flat root the parent IS the root, so category falls back to
            # the domain rather than repeating the folder name.
            category = path.parent.name if path.parent != root else domain
            name = _safe_name(path.stem)
            lane = IngestLane.personal_history if domain == "relationship_timeline" else IngestLane(domain)
            print(f"  ingesting [{domain}/{category}] {name} -> canonical PostgreSQL")
            await asyncio.to_thread(
                ingest_file,
                IngestRequest(
                    staged_path=str(path),
                    lane=lane,
                    matter_id="primary",
                    custody_tier="light",
                    source_identity={
                        "name": name,
                        "lane": lane.value,
                        "doc_type": category,
                        "source": str(path),
                        "case_id": "primary",
                        "legacy_root": domain,
                    },
                ),
            )
            count += 1
    if skipped:
        print(f"{len(skipped)} file(s) need manual review (size).")
    return count


async def main() -> None:
    roots = ", ".join(f"{d}={p}" for d, p in KNOWLEDGE_ROOTS.items())
    print(f"Ingesting from {roots} ...")
    n = await ingest_all()
    print(f"Done. {n} document(s) committed to canonical PostgreSQL.")


if __name__ == "__main__":
    asyncio.run(main())
