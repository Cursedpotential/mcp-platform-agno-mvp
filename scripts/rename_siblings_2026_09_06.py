"""One-shot: naming sweep for the two nested sibling repos (advocatio, vestigia) under D-137..D-150.

Canon files (README, AGENTS.md, AGENT_MEMORY.md, pyproject) get the new product name with the old
name kept beside it; every other doc that mentions an old name gets a one-line naming note
(historical docs are annotated, never rewritten - D-142). Code identifiers (python package
`legal_workspace`, dist name `legal-workspace`) are NOT renamed here: that is a code change with
its own tests, and the GitHub repo names are not ruled.

Run from the probata repo root:  uv run python scripts/rename_siblings_2026_09_06.py
Byline: Claude Code · Fable 5.1 · 2026-09-06.
"""

from __future__ import annotations

import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1] / "modules"
OLD_RX = re.compile(r"Agno-MCP-Platform|mcp-platform-agno-mvp|Legal-Workspace|Legal Workspace|traceIQ|TraceIQ")
SKIP = ("node_modules", ".venv", ".memsearch", ".git", "_stale", ".egg-info", "__pycache__", ".remember", ".claude")

SIBLINGS = {
    "advocatio": {
        "dir": "advocatio",
        "product": "advocatio",
        "old": "Legal-Workspace",
        "note": (
            "> _Naming (D-138, 2026-09-05; applied 2026-09-06): this product is **advocatio** (formerly Legal-Workspace / "
            "Legal Workspace); the evidence platform it consumes is **Indicia Probata** / `probata` (formerly "
            "Agno-MCP-Platform). Directory: `probata/modules/advocatio/` (old name kept as a junction). GitHub repo "
            "name unchanged pending its own decision. Canon: `probata/docs/NAMING.md`. Historical text below is "
            "left verbatim; both names remain valid in recall stores (D-142)._"
        ),
        "canon": {
            "README.md": [
                ("# Legal Workspace", "# advocatio (formerly Legal Workspace)"),
                ("Sibling application to [Agno-MCP-Platform](../Agno-MCP-Platform/).",
                 "Sibling application to [Indicia Probata / probata](../../) (formerly Agno-MCP-Platform)."),
                ("Evidence stays in Agno.", "Evidence stays in probata (formerly \"Agno\")."),
            ],
            "pyproject.toml": [
                ('description = "Legal analysis, strategy, drafting, and filing preparation sibling of Agno-MCP-Platform."',
                 'description = "advocatio (formerly Legal Workspace): legal analysis, strategy, drafting, and filing preparation sibling of Indicia Probata / probata (formerly Agno-MCP-Platform)."'),
            ],
        },
    },
    "vestigia": {
        "dir": "traceIQ",
        "product": "vestigia",
        "old": "traceIQ",
        "note": (
            "> _Naming (D-140, 2026-09-05; applied 2026-09-06): this product is **vestigia** (formerly traceIQ / "
            "TraceIQ - Latin: footprints, tracks). Working copy: `probata/modules/vestigia/` (directory rename from "
            "`modules/traceIQ/` lands with the workspace directory-rename step; old name kept as a junction). GitHub "
            "repo name unchanged pending its own decision. Canon: `probata/docs/NAMING.md`. Historical text below is "
            "left verbatim; both names remain valid in recall stores (D-142)._"
        ),
        "canon": {
            "README.md": [("# TraceIQ", "# vestigia (formerly TraceIQ)")],
            "AGENTS.md": [("# TraceIQ Outer Repository — Agent Entry Point", "# vestigia (formerly TraceIQ) Outer Repository — Agent Entry Point")],
        },
    },
}


def note_file(path: pathlib.Path, note: str) -> bool:
    s = path.read_text(encoding="utf-8", errors="replace")
    if note in s or not OLD_RX.search(s):
        return False
    lines = s.split("\n")
    # insert after the first heading line, else at top
    idx = next((i + 1 for i, ln in enumerate(lines[:5]) if ln.startswith("#")), 0)
    lines[idx:idx] = ["", note, ""]
    path.write_text("\n".join(lines), encoding="utf-8", newline="")
    return True


def main() -> None:
    for name, spec in SIBLINGS.items():
        repo = ROOT / spec["dir"]
        if not repo.exists():
            print("missing", repo)
            continue
        touched: list[str] = []
        for fname, pairs in spec["canon"].items():
            p = repo / fname
            if not p.exists():
                continue
            s = p.read_text(encoding="utf-8")
            o = s
            for a, b in pairs:
                s = s.replace(a, b)
            if s != o:
                p.write_text(s, encoding="utf-8", newline="")
        for fname in ("README.md", "AGENTS.md", "AGENT_MEMORY.md"):
            p = repo / fname
            if p.exists() and note_file(p, spec["note"]):
                touched.append(fname)
        for p in repo.rglob("*.md"):
            rel = p.relative_to(repo)
            if any(part in SKIP or part.endswith(".egg-info") for part in rel.parts):
                continue
            if rel.name in ("README.md", "AGENTS.md", "AGENT_MEMORY.md") and len(rel.parts) == 1:
                continue
            if note_file(p, spec["note"]):
                touched.append(str(rel))
        for fname in spec["canon"]:
            if fname not in touched and (repo / fname).exists():
                touched.append(fname)
        touched = sorted(set(touched))
        # gitignored files (local compact summaries etc.) are annotated on disk but cannot be staged
        ignored = subprocess.run(["git", "-C", str(repo), "check-ignore", "--", *touched], capture_output=True, text=True).stdout.split()
        touched = [t for t in touched if t.replace("\\", "/") not in {i.replace("\\", "/") for i in ignored}]
        print(f"{name}: {len(touched)} tracked files ({len(ignored)} ignored, annotated only)")
        if touched:
            subprocess.run(["git", "-C", str(repo), "add", "--", *touched], check=True)
            msg = (f"docs: naming sweep - product is {spec['product']} (formerly {spec['old']}); "
                   "evidence platform is probata (formerly Agno-MCP-Platform); historical docs annotated (D-137..D-150)\n\n"
                   "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n")
            subprocess.run(["git", "-C", str(repo), "commit", "-q", "-F", "-"], input=msg, text=True, check=True)
            print(subprocess.run(["git", "-C", str(repo), "log", "--oneline", "-1"], capture_output=True, text=True).stdout.strip())


if __name__ == "__main__":
    main()
