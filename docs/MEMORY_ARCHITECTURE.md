# Memory / Recall / Context Architecture

> _Byline: Claude Code · Opus 4.8 · 2026-06-16_ · Reconciled 2026-06-16 · CNF vs auto-memory lanes disambiguated 2026-07-05 (per code.claude.com/docs/en/memory) · mem0-protocol skill retired + discipline borrowed 2026-07-05

The single map of every memory/recall/context system, what it's for, and where it lives. If you're
about to add a new memory mechanism — **don't**; fit it into one of these or extend this doc.

## Rule 0 — canonical working directory
**Always open Claude Code at the workspace ROOT** (`E:/AI_Workspace/Projects/the-platform-workspace`).
The cwd-keyed recall lanes — CNF session-recall (`.claude/memories/`), `.remember/` handoffs,
`.memsearch/` semantic search — key off the open folder, so one working dir = no fragmentation.
These are distinct from the built-in **auto-memory** (`~/.claude/projects/<project>/memory/MEMORY.md`
+ frontmatter `.md`), which keys off the project, not the open folder. The `Agno-MCP-Platform/`
subdir is the active *build repo* but is accessed from the root session.

## Rule 1 — never delete
NEVER `rm`/delete files. Move stale/duplicate files into the root `_stale/` directory; the owner
removes them later. (Same non-destructive ethos as the CaseBible quarantine.)

## The systems (one home per concern)

| # | Concern | Canonical home | Owner / tool | Notes |
|---|---|---|---|---|
| 1 | **CNF session-recall** (realtime capture + manual `/cnf-remember` entries) | `.claude/memories/project_memory.json` (ROOT) | claude-never-forgets plugin (forked; skill `cnf-recall`, commands `/cnf-*`) | Subdir copy was merged in + moved to `_stale/`. JSON: `manual_memories[]` + `realtime_memories[]`. NOT the built-in auto-memory — separate lane. |
| 2 | **SSOT docs** (vision, decisions, plans, structure, conventions, ADRs) | `Agno-MCP-Platform/docs/` | Hand-maintained, per PROJECT_CANON §0 contract | Entry = `PROJECT_CANON.md`. ADRs in `docs/adr/`. Root's duplicate top-level copies → `_stale/`. |
| 3 | **Session handoff** (per-day snapshots, now/recent/archive) | `.remember/` (ROOT) | recall plugin hooks (PreCompact, SessionStart) | Writes here, NOT to root top-level. Logs in `.remember/logs/`. |
| 4 | **Auto-memory** (built-in, durable cross-session facts) | `C:/Users/matts/.claude/projects/E--AI-Workspace/memory/` | Claude Code native (v2.1.59+) | `MEMORY.md` is the index; one frontmatter `.md` per durable fact. The canonical durable lane for owner/project/feedback memory. Keys off the project, not the open folder. |
| 5 | **Code semantic search** | `Agno-MCP-Platform/.memsearch/` | memsearch tool | Auto-generated (SQLite + locks). Subdir-only by design. |
| 6 | **Archived duplicates / stale** | `_stale/` (ROOT) | this reconciliation | Do not use. Owner removes later. |

### How they relate
- Root `CLAUDE.md` is short (progressive disclosure): points to `PROJECT_CANON.md` + this doc, and
  `@`-includes `.claude/recall-context.md` (recall plugin populates it).
- **Auto-memory (#4)** holds durable facts (owner prefs, infra, decisions) and is the most
  important to keep current — update it via `MEMORY.md` + per-fact frontmatter `.md` files.
- **CNF session-recall (#1)** is the per-session realtime cache; **handoff (#3)** is day-to-day
  continuity; **SSOT (#2)** is authoritative design/decisions. On conflict, SSOT (PROJECT_CANON §5) wins.

## Memory protocol discipline (borrowed from the retired `mem0-protocol` skill, 2026-07-05)

The user-level `memory-management` skill (a mem0/openmemory protocol, v2.0.0, 2026-02-27) was
**retired 2026-07-05** — its MCP targets (`mcp__openmemory__*`, `mcp__structured_memory__*`) were
never configured so it was functionally inert, and it name-collided with the `knowledge-work-plugins/
productivity` `memory-management` glossary skill. Before deletion, four protocol patterns worth
keeping were extracted here. These are **discipline, not a new lane** — apply them across the
existing lanes (auto-memory #4, CNF #1, `.remember/` #3, graphiti).

**Anti-hallucination rules** — for any recall claim:
- Search-then-cite: execute the search first, then cite the source ("auto-memory says on [date] we [did X]"); never assert from memory-of-memory.
- Verify the write succeeded (tool result shows success/ID) before treating a fact as stored.
- Surface discrepancies: "Memory says X, but I see Y" — don't silently pick one.
- Only verbatim or confirmed facts; never paraphrase a stored fact into a stronger claim.

**Search-priority ladder** (when recalling prior context):
1. Auto-memory `MEMORY.md` index → frontmatter `.md` (durable, project-keyed).
2. Graphiti `search_memory_facts` / `search_nodes` (entity/temporal).
3. CNF `.claude/memories/project_memory.json` (current-session realtime).
4. `.remember/` handoff (recent/day) → memsearch (older turns, stale-aware).
5. **ASK the user** if 1–4 yield nothing — never fabricate prior work.

**Correction / preference-update protocol** (when the owner revises a prior fact):
1. Save the NEW fact immediately (update the existing frontmatter `.md` — don't duplicate).
2. Record the transition in the body: `Previous: X. Updated to: Y. Reason: [owner's wording].`
3. Apply the corrected version to all subsequent actions this session.
4. Discard the old — don't cite the superseded value again.

**Save / don't-save noise filter** (what graduates into auto-memory):
- **Save**: owner corrections, workflow/preferences, bug-fix-with-exact-error+fix, decisions-with-rationale, infra/endpoint changes.
- **Don't save**: greetings/acknowledgments ("okay", "thanks"), generic advice, transient session paths, hypothetical discussions, chit-chat already captured by CNF realtime.

## ADR → decisions auto-index
When a new ADR file `Agno-MCP-Platform/docs/adr/NNNN-*.md` is created, a Claude Code PostToolUse hook
appends a one-line entry to `Agno-MCP-Platform/docs/adr/README.md` (the decisions index) if not
already present. Hook + script live in the root `.claude/settings.json` + `.claude/hooks/`.
