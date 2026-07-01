# Memory / Recall / Context Architecture

> _Byline: Claude Code · Opus 4.8 · 2026-06-16_ · Reconciled 2026-06-16

The single map of every memory/recall/context system, what it's for, and where it lives. If you're
about to add a new memory mechanism — **don't**; fit it into one of these or extend this doc.

## Rule 0 — canonical working directory
**Always open Claude Code at the workspace ROOT** (`E:/AI_Workspace/Projects/the-platform-workspace`).
The auto-memory tools key off the open folder, so one working dir = no fragmentation. The
`Agno-MCP-Platform/` subdir is the active *build repo* but is accessed from the root session.

## Rule 1 — never delete
NEVER `rm`/delete files. Move stale/duplicate files into the root `_stale/` directory; the owner
removes them later. (Same non-destructive ethos as the CaseBible quarantine.)

## The systems (one home per concern)

| # | Concern | Canonical home | Owner / tool | Notes |
|---|---|---|---|---|
| 1 | **Auto-memory** (consolidated project facts) | `.claude/memories/project_memory.json` (ROOT) | Claude Code native + recall plugin | Subdir copy was merged in + moved to `_stale/`. JSON: `memories[]` consolidated + `realtime_memories[]` noise. |
| 2 | **SSOT docs** (vision, decisions, plans, structure, conventions, ADRs) | `Agno-MCP-Platform/docs/` | Hand-maintained, per PROJECT_CANON §0 contract | Entry = `PROJECT_CANON.md`. ADRs in `docs/adr/`. Root's duplicate top-level copies → `_stale/`. |
| 3 | **Session handoff** (per-day snapshots, now/recent/archive) | `.remember/` (ROOT) | recall plugin hooks (PreCompact, SessionStart) | Writes here, NOT to root top-level. Logs in `.remember/logs/`. |
| 4 | **Long-term cross-session memory** | `C:/Users/matts/.claude/projects/E--AI-Workspace/memory/` | Claude Code auto-memory store | `MEMORY.md` is the index; one `.md` per durable fact. The durable owner/project/feedback memory. |
| 5 | **Code semantic search** | `Agno-MCP-Platform/.memsearch/` | memsearch tool | Auto-generated (SQLite + locks). Subdir-only by design. |
| 6 | **Archived duplicates / stale** | `_stale/` (ROOT) | this reconciliation | Do not use. Owner removes later. |

### How they relate
- Root `CLAUDE.md` is short (progressive disclosure): points to `PROJECT_CANON.md` + this doc, and
  `@`-includes `.claude/recall-context.md` (recall plugin populates it).
- The **long-term store (#4)** holds durable facts (owner prefs, infra, decisions) and is the most
  important to keep current — update it via `MEMORY.md` + per-fact `.md` files.
- **Auto-memory (#1)** is the per-session consolidated cache; **handoff (#3)** is day-to-day continuity;
  **SSOT (#2)** is authoritative design/decisions. On conflict, SSOT (PROJECT_CANON §5) wins.

## ADR → decisions auto-index
When a new ADR file `Agno-MCP-Platform/docs/adr/NNNN-*.md` is created, a Claude Code PostToolUse hook
appends a one-line entry to `Agno-MCP-Platform/docs/adr/README.md` (the decisions index) if not
already present. Hook + script live in the root `.claude/settings.json` + `.claude/hooks/`.
