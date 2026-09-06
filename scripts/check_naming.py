"""Naming gate: fail if a retired product/lane name reappears outside the allowlist.

This is the balancing loop the rename needs (docs/reviews/2026-09-05-rename-as-a-system.md
§3, Meadows level 5). Five naming passes in a week happened because nothing detected a
second name appearing; a human noticed weeks later. This script makes a second name a
build failure instead.

Canon: docs/NAMING.md (D-137..D-142). Retired names and where they are still allowed:

  * docs/** except the CANON_DOCS list (README, AGENTS.md, INDEX, PROJECT_CANON, REPO_STRUCTURE,
    CONVENTIONS, COORDINATION, DEBT, reference/, the two living plans, consolidated/) — history
  * docs/DECISION_LOG.md, docs/NAMING.md, docs/registers/**                       — decisions and glossary
  * lines carrying strike-through (~~old~~) or the literal "(formerly"           — visible corrections
  * knowledge/**                                                                  — archived transcripts, never rewritten
  * server/vendored/**, modules/engine/vendor/**, modules/forks/**, node_modules  — not ours
  * .memsearch/**, .remember/**, .cnf/**, .claude/**                              — recall stores alias, never replace (D-142)

Run:  uv run python scripts/check_naming.py            (exit 1 on any hit)
      uv run python scripts/check_naming.py --report   (list hits, exit 0)

Byline: Claude Code · Fable 5.1 · 2026-09-06.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Retired token -> replacement (for the message only). Word-boundary, case-insensitive
# where the old name was a brand; exact for identifiers.
RETIRED: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"mcp-platform-agno-mvp"), "Cursedpotential/probata"),
    (re.compile(r"Agno-MCP-Platform(?!-alpha)"), "probata (Indicia Probata)"),
    (re.compile(r"\bUniversal Import Workflow\b", re.I), "proffer"),
    (re.compile(r"\buniversal-import\b"), "proffer"),
    (re.compile(r"\bUniversalImport\w*"), "Proffer*"),
    (re.compile(r"\buiw\b"), "proffer"),
    (re.compile(r"\bUIW_[A-Z_]+"), "PROFFER_*"),
    (re.compile(r"N8N_UNIVERSAL_IMPORT_[A-Z_]+"), "N8N_PROFFER_*"),
    (re.compile(r"\bopenspine\b", re.I), "(rejected name, D-138)"),
]

ALLOW_DIRS = (
    "docs/archive/",
    "docs/registers/",
    "knowledge/",
    "server/vendored/",
    "modules/engine/vendor/",
    "modules/forks/",
    "modules/apps/",
    "modules/custom/",
    "modules/Legal-Workspace/",
    "modules/advocatio/",   # nested independent repo (its own sweep, own commit root)
    "modules/traceIQ/",
    "modules/vestigia/",
    ".memsearch/",
    ".remember/",
    ".cnf/",
    ".claude/",
    ".git/",
    ".venv/",
    "node_modules/",
    "tests/_reports/",
    "docs/reports/_stale/",
    "to_be_deleted/",
    ".review_hold/",
    # build output and tool caches
    ".ruff_cache/",
    ".codelens/",
    ".agents/",
    "modules/workbench/web/.next/",
    "modules/workbench/web/out/",
    "modules/workbench/web/dist/",
    "deploy/docker/surreal-phase1-runner/.venv/",
    # applied migrations are immutable history; new migrations use the proffer names
    "sql/",
    # wave-0/1 validation scripts are dated one-shot runs keyed by absolute path
    "scripts/_wave",
    "scripts/_cnf_",
    "scripts/_e14.txt",
)
ALLOW_FILES = {
    "deploy/teracopy-report-2026-08-Agno-MCP-Platform.html",  # a TeraCopy transfer receipt, historical
    "modules/workbench/api/.env",  # local, gitignored
    "docs/DECISION_LOG.md",
    "docs/NAMING.md",
    "scripts/check_naming.py",
    "scripts/rename_routers_2026_09_06.py",  # carries the old names as search strings by design
    "scripts/rename_siblings_2026_09_06.py",  # same: sibling-repo sweep, old names are its search strings
}
# Historical review/planning docs are annotated, not rewritten (D-142 alias rule for
# history). A file is exempt if it carries the naming note.
HISTORY_NOTE = "written before the 2026-09-05 rename"
STRIKE = re.compile(r"~~[^~]*~~")
TEXT_EXT = {
    ".md",
    ".py",
    ".go",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
    ".txt",
    ".sh",
    ".ps1",
    ".sql",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".html",
    ".css",
    ".env",
    ".hujson",
    ".cfg",
    ".ini",
    ".mod",
    ".sum",
    "",
    ".dockerfile",
}


# docs/** is HISTORY by default: historical reviews, handoffs, and plans are annotated or
# archived by the consolidation manifest, never rewritten (D-142). Only the CANON docs
# below are gated, because they assert current truth.
CANON_DOCS = (
    "README.md",
    "AGENTS.md",
    "AGENT_MEMORY.md",
    "docs/INDEX.md",
    "docs/PROJECT_CANON.md",
    "docs/REPO_STRUCTURE.md",
    "docs/CONVENTIONS.md",
    "docs/COORDINATION.md",
    "docs/DEBT.md",
    "docs/reference/",
    "docs/adr/README.md",
    "docs/planning/2026-09-03-ingest-simplification-plan.md",
    "docs/planning/2026-09-03-ingest-redesign-plan-and-sequential-guide.md",
    "docs/consolidated/",
)


def _is_gated_doc(rel: str) -> bool:
    return any(rel == c or rel.startswith(c) for c in CANON_DOCS)


def _iter_files() -> list[Path]:
    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = Path(dirpath).relative_to(ROOT).as_posix()
        rel_dir = "" if rel_dir == "." else rel_dir + "/"
        if any(rel_dir.startswith(a) for a in ALLOW_DIRS):
            dirnames[:] = []
            continue
        # prune allowed subdirs early
        dirnames[:] = [
            d
            for d in dirnames
            if d not in {"node_modules", ".venv", "__pycache__", ".git"}
            and not any((rel_dir + d + "/").startswith(a) for a in ALLOW_DIRS)
        ]
        for name in filenames:
            p = Path(dirpath) / name
            rel = p.relative_to(ROOT).as_posix()
            if any(rel.startswith(a) for a in ALLOW_DIRS):  # file-prefix entries (e.g. scripts/_wave)
                continue
            if rel.startswith("docs/") and not _is_gated_doc(rel):
                continue
            if p.suffix.lower() in TEXT_EXT or name == "Dockerfile":
                out.append(p)
    return out


def scan() -> list[tuple[str, int, str, str]]:
    hits: list[tuple[str, int, str, str]] = []
    for path in _iter_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in ALLOW_FILES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if HISTORY_NOTE in text:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if "(formerly" in line or STRIKE.search(line):
                continue
            # an explicit rename note naming the new name is a visible correction, not drift
            if re.search(r"renam", line, re.I) and re.search(r"proffer|probata|Proffer", line):
                continue
            for pat, repl in RETIRED:
                m = pat.search(line)
                if m:
                    hits.append((rel, lineno, m.group(0), repl))
                    break
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="list hits, exit 0")
    args = ap.parse_args()
    hits = scan()
    by_file: dict[str, int] = {}
    for rel, _, _, _ in hits:
        by_file[rel] = by_file.get(rel, 0) + 1
    for rel, lineno, tok, repl in hits[:400]:
        print(f"{rel}:{lineno}: retired name {tok!r} -> {repl}")
    if len(hits) > 400:
        print(f"... {len(hits) - 400} more")
    print(f"\n{len(hits)} hit(s) in {len(by_file)} file(s)")
    if hits and not args.report:
        print("FAIL: retired names present outside the allowlist. See docs/NAMING.md.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
