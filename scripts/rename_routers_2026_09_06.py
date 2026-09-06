"""One-shot: alias the workspace and repo router files to the D-137..D-150 names.

Recall/router rule (D-142): the new name is added BESIDE the old one, never replacing it, so
either term resolves. `probata/` resolves today via a forward junction to `Agno-MCP-Platform/`;
the real directory rename lands with docs/handoffs/2026-09-06-rename-followups/01.

Run from the repo root:  uv run python scripts/rename_routers_2026_09_06.py
Byline: Claude Code · Fable 5.1 · 2026-09-06.
"""

from __future__ import annotations

import pathlib

WS = pathlib.Path(r"E:\AI_Workspace")
REPO = WS / "Projects/the-platform-workspace/Agno-MCP-Platform"

NOTE = (
    "> _Naming amendment: Claude Code · Fable 5.1 · 2026-09-06 — product canon D-137..D-150 "
    "(`probata/docs/NAMING.md`). Evidence Platform = **Indicia Probata** (`probata`, formerly "
    "`Agno-MCP-Platform`); Legal Workspace = **advocatio** (nested at `probata/modules/advocatio/`, "
    "formerly `modules/Legal-Workspace/`); TraceIQ = **vestigia** (nested at `probata/modules/vestigia/`, "
    "formerly `modules/traceIQ/`). `probata/` resolves today as a junction to `Agno-MCP-Platform/`; the "
    "real directory rename runs when no session holds the tree "
    "(`docs/handoffs/2026-09-06-rename-followups/01-finish-directory-rename.md`). Old paths stay as "
    "junctions for a week; both names remain valid in recall stores (D-142)._"
)


def edit(path: pathlib.Path, pairs: list[tuple[str, str]], note: bool = True, newline: str = "\n") -> None:
    s = path.read_text(encoding="utf-8")
    o = s
    for a, b in pairs:
        s = s.replace(a, b)
    if note and NOTE not in s:
        s = s.rstrip("\n") + "\n\n" + NOTE + "\n"
    path.write_text(s, encoding="utf-8", newline=newline)
    print("edited" if s != o else "unchanged", path)


def main() -> None:
    edit(WS / "AGENT_MEMORY.md", [(
        "- `Projects/the-platform-workspace/Agno-MCP-Platform/`, `Projects/traceIQ/`,",
        "- `Projects/the-platform-workspace/probata/` (Indicia Probata; formerly `Agno-MCP-Platform/`), "
        "`Projects/traceIQ/` (product name **vestigia**; working copy nested at `probata/modules/vestigia/`),",
    )])
    edit(WS / "AGENTS.md", [])
    edit(WS / "Projects/AGENTS.md", [
        ("| Evidence Platform | `the-platform-workspace/Agno-MCP-Platform/AGENTS.md` | `the-platform-workspace/Agno-MCP-Platform/` |",
         "| Evidence Platform — **Indicia Probata** (`probata`; formerly `Agno-MCP-Platform`) | `the-platform-workspace/probata/AGENTS.md` | `the-platform-workspace/probata/` (junction to `Agno-MCP-Platform/` until the directory rename lands) |"),
        ("| Legal Workspace | `the-platform-workspace/Legal-Workspace/AGENTS.md` | `the-platform-workspace/Legal-Workspace/` | ignored independent child |",
         "| Legal Workspace — **advocatio** (formerly `Legal-Workspace`) | `the-platform-workspace/probata/modules/advocatio/AGENTS.md` | `the-platform-workspace/probata/modules/advocatio/` (nested since 2026-09-01; the old top-level `Legal-Workspace/` path no longer exists) | ignored independent child |"),
        ("| TraceIQ | `traceIQ/AGENTS.md` | `traceIQ/` | raw gitlink; local private data ignored by child |",
         "| TraceIQ — **vestigia** (product name, D-140) | `the-platform-workspace/probata/modules/vestigia/AGENTS.md` (working copy; the top-level `traceIQ/` directory is absent on disk though still a parent gitlink) | `the-platform-workspace/probata/modules/vestigia/` | raw gitlink `Projects/traceIQ` retained in the index pending a boundary decision; local private data ignored by child |"),
        ("| TraceIQ rebuild | `traceIQ/traceiq-rebuild/AGENTS.md` | `traceIQ/traceiq-rebuild/` |",
         "| TraceIQ rebuild | `the-platform-workspace/probata/modules/vestigia/traceiq-rebuild/AGENTS.md` | `…/modules/vestigia/traceiq-rebuild/` |"),
    ])
    edit(WS / "Projects/AGENT_MEMORY.md", [
        ("- Platform evidence/legal system: `the-platform-workspace/AGENT_MEMORY.md`.",
         "- Platform evidence/legal system (probata + advocatio): `the-platform-workspace/AGENT_MEMORY.md`."),
        ("- traceIQ: `traceIQ/AGENT_MEMORY.md`.",
         "- traceIQ (**vestigia**): `the-platform-workspace/probata/modules/vestigia/AGENT_MEMORY.md` (the top-level `traceIQ/` directory is absent on disk)."),
    ])
    edit(WS / "Projects/REPOSITORY_BOUNDARIES.md", [
        ("| Evidence Platform | `Projects/the-platform-workspace/Agno-MCP-Platform` |",
         "| Evidence Platform (**Indicia Probata**, `probata`) | `Projects/the-platform-workspace/probata` (formerly `Agno-MCP-Platform`; junction until the directory rename lands) |"),
        ("| Legal Workspace | `Projects/the-platform-workspace/Legal-Workspace` |",
         "| Legal Workspace (**advocatio**) | `Projects/the-platform-workspace/probata/modules/advocatio` (formerly `modules/Legal-Workspace`; the top-level `Legal-Workspace/` path no longer exists) |"),
    ])
    edit(WS / "Projects/the-platform-workspace/AGENTS.md", [
        ("| Evidence custody, ingestion, parsing, knowledge horizons, analysis, and operations | `Agno-MCP-Platform/` | `Agno-MCP-Platform/AGENTS.md` | `Agno-MCP-Platform/` |",
         "| Evidence custody, ingestion, parsing, knowledge horizons, analysis, and operations — **Indicia Probata** | `probata/` (formerly `Agno-MCP-Platform/`) | `probata/AGENTS.md` | `probata/` |"),
        ("| Legal research, strategy, drafting, review, and release preparation | `Legal-Workspace/` | `Legal-Workspace/AGENTS.md` | `Legal-Workspace/` |",
         "| Legal research, strategy, drafting, review, and release preparation — **advocatio** | `probata/modules/advocatio/` (formerly `Legal-Workspace/`) | `probata/modules/advocatio/AGENTS.md` | `probata/modules/advocatio/` |"),
    ])
    edit(WS / "Projects/the-platform-workspace/AGENT_MEMORY.md", [
        ("  - Projects/the-platform-workspace/Agno-MCP-Platform/AGENTS.md",
         "  - Projects/the-platform-workspace/probata/AGENTS.md (formerly Agno-MCP-Platform/)"),
        ("  - Projects/the-platform-workspace/Legal-Workspace/AGENTS.md",
         "  - Projects/the-platform-workspace/probata/modules/advocatio/AGENTS.md (formerly Legal-Workspace/)"),
        ("| Evidence, custody, ingestion, parsing, analysis, platform operations | `Agno-MCP-Platform/` | `Agno-MCP-Platform/` |",
         "| Evidence, custody, ingestion, parsing, analysis, platform operations — **Indicia Probata** | `probata/` (formerly `Agno-MCP-Platform/`) | `probata/` |"),
        ("| Strategy, legal research, drafting, review, release preparation | `Legal-Workspace/` | `Legal-Workspace/` |",
         "| Strategy, legal research, drafting, review, release preparation — **advocatio** | `probata/modules/advocatio/` (formerly `Legal-Workspace/`) | `probata/modules/advocatio/` |"),
    ])
    gi = WS / ".gitignore"
    s = gi.read_text(encoding="utf-8")
    if "the-platform-workspace/probata/" not in s:
        s = s.rstrip("\n") + (
            "\n\n# 2026-09-06 rename (D-137..D-142): `probata/` is a junction to Agno-MCP-Platform/ until the directory\n"
            "# rename lands; then Agno-MCP-Platform/ becomes the junction. Ignore whichever is the alias; the real\n"
            "# child is a raw gitlink. Remove after 2026-09-13.\n"
            "Projects/the-platform-workspace/probata/\n"
        )
        gi.write_text(s, encoding="utf-8", newline="\n")
        print("parent .gitignore: probata junction ignored")
    # product repo routers (keep their existing line endings)
    edit(REPO / "AGENTS.md", [
        ("| `modules/Legal-Workspace/` | **Nested independent product repo, gitignored**",
         "| `modules/advocatio/` (**advocatio**, D-138; directory formerly `modules/Legal-Workspace/`, old name kept as a junction) | **Nested independent product repo, gitignored**"),
        ("| `modules/traceIQ/` | **Nested independent product repo, gitignored** (contains its own nested `traceiq-rebuild` repo).",
         "| `modules/vestigia/` (**vestigia**, D-140; the rename from `modules/traceIQ/` lands with the directory-rename step, old name kept as a junction) | **Nested independent product repo, gitignored** (contains its own nested `traceiq-rebuild` repo)."),
    ], note=False, newline="")
    edit(REPO / "AGENT_MEMORY.md", [
        ("| `modules/workbench/**` (was root `workbench/`, moved 2026-09-01) |",
         "| `modules/advocatio/**` (advocatio; formerly `modules/Legal-Workspace/`) and `modules/vestigia/**` (vestigia; formerly `modules/traceIQ/`) | each nested repo's own `AGENTS.md` / `AGENT_MEMORY.md` |\n| `modules/workbench/**` (was root `workbench/`, moved 2026-09-01) |"),
    ], note=False, newline="")


if __name__ == "__main__":
    main()
