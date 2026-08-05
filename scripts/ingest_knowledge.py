"""
Knowledge ingestion — scan the knowledge roots, normalize, knowledge.ainsert()
==============================================================================

Deterministic normalize + manifest, then hand PATHS to Agno's native insert
(handoff §7.1/§9.1 — do NOT write a custom loader; Agno reads/chunks/embeds).

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
"""

import asyncio
import re
from os import getenv
from pathlib import Path

ALLOWED_EXT = {".md", ".txt", ".json", ".csv", ".pdf", ".docx"}
MAX_SIZE = 50 * 1024 * 1024  # 50 MB

# domain -> root. KNOWLEDGE_BASE_PATH still overrides the platform root so the
# existing env contract keeps working; KNOWLEDGE_LEGAL_PATH does the same for
# legal. A root that does not exist is skipped, not fatal.
KNOWLEDGE_ROOTS: dict[str, Path] = {
    "platform": Path(getenv("KNOWLEDGE_BASE_PATH", "/app/knowledge/platform")),
    "legal": Path(getenv("KNOWLEDGE_LEGAL_PATH", "/app/knowledge/legal")),
}

_SAFE = re.compile(r"[^a-z0-9\-_.]+")


def _safe_name(stem: str) -> str:
    """Lowercase kebab-case, max 127 chars (handoff §9.1 filename regex)."""
    name = _SAFE.sub("-", stem.lower()).strip("-.")
    return (name or "unnamed")[:127]


async def ingest_all(knowledge, bases: dict | None = None) -> int:
    """Ingest every knowledge root.

    ``bases`` maps a domain to ITS OWN Knowledge instance (2026-08-04). Without
    it, every domain lands in the single ``knowledge`` argument — which is how
    the legal rubrics ended up inside the platform collection, and why "legal"
    read as empty the moment it became a selectable base. A domain absent from
    ``bases`` falls back to ``knowledge``, so single-base callers are unchanged.
    """
    count = 0
    skipped: list[str] = []
    for domain, root in KNOWLEDGE_ROOTS.items():
        target = (bases or {}).get(domain) or knowledge
        if target is None:
            print(f"  no knowledge base available for [{domain}], skipping")
            continue
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
            print(f"  inserting [{domain}/{category}] {name} -> base {getattr(target, 'name', '?')!r}")
            await target.ainsert(
                name=name,
                path=str(path),
                metadata={
                    "domain": domain,
                    "category": category,
                    "source_path": str(path),
                },
            )
            count += 1
    if skipped:
        print(f"{len(skipped)} file(s) need manual review (size).")
    return count


async def main() -> None:
    from server.core import create_knowledge

    knowledge = create_knowledge("platform", "platform_knowledge")
    # Route each domain to its own base (registered in server/api/main.py).
    bases = {"legal": create_knowledge("legal", "legal_knowledge")}
    roots = ", ".join(f"{d}={p}" for d, p in KNOWLEDGE_ROOTS.items())
    print(f"Ingesting from {roots} ...")
    n = await ingest_all(knowledge, bases=bases)
    print(f"Done. {n} document(s) indexed.")


if __name__ == "__main__":
    asyncio.run(main())
