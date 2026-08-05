# Memory / Recall / Context Architecture

> _Byline: Claude Code · Opus 4.8 · 2026-06-16_ · Reconciled 2026-06-16 · CNF vs auto-memory lanes
> disambiguated 2026-07-05 · **Rewritten 2026-08-05 (Claude Code · Opus 5): 6 lanes → 9, enforcement
> column added, Rule 0's fragmentation claim corrected, Graphiti re-homed onto the `grc` CLI.**

The single map of every memory/recall/context system: what it's for, where it lives, **who writes to
it, when, and how compliance is actually checked**. If you're about to add a new memory mechanism —
**don't**; fit it into one of these or extend this doc.

> **Why this was rewritten.** On 2026-08-05 an audit found the previous version listed 6 lanes while
> 9 existed — Graphiti (mandated in `CLAUDE.md`), `CHANGE-ORDER.md` (self-described "ledger of
> record") and Spec Memory had all been added *without* extending this doc, in direct violation of
> the rule above. Five obligations had failed **silently**, none caught by any mechanism:
> the change-order went unwritten 16 days; 27 memories sat unreachable across 6 stores; the Graphiti
> lane went unused for an entire session; memsearch's embed→Milvus indexing had been dead; and this
> doc itself was stale and wrong. The lesson is in **Rule 2**.

## Rule 0 — canonical working directory (and its real limits)

**Always open Claude Code at the workspace ROOT** (`E:/AI_Workspace/Projects/the-platform-workspace`).

The **cwd-keyed** lanes — CNF (`.claude/memories/`), `.remember/`, `.memsearch/` — key off the open
folder, so one working dir keeps them from fragmenting. That part works.

⚠️ **Rule 0 does NOT protect auto-memory.** ~~Opening at the root prevents fragmentation.~~
**Corrected 2026-08-05:** auto-memory keys off the **project**, not the open folder, so Rule 0 has no
effect on it. Reality check that day found **10 separate auto-memory stores**, including a 121-file
and a 134-file store created by sessions opened in subdirectories, plus one with no index at all.
Consolidating them is an open task. Until then, `memory_health.py` reports every store it finds.

## Rule 1 — never delete
NEVER `rm`/delete. Move stale/duplicate files into the root `_stale/`; the owner removes them later.
Mechanically enforced by the `cc_guard` hook (it blocks `rm -rf` outright — verified live 2026-08-05).

## Rule 2 — hooks are good at "don't", bad at "do"
Every mechanism that worked before 2026-08-05 either **blocked a destructive action** or **reacted to
a file write**. Nothing verified a *positive obligation* — that a fact got written, a ladder got
searched, a ledger got appended, a lane got used. That asymmetry is why all five failures above were
silent rather than noisy.

**So: any lane carrying a standing obligation needs an explicit check, or it will rot unobserved.**
The Enforcement column below is the honest status of each. `honour-system` means *nothing will tell
you when it lapses* — treat those as the risk list, not as "fine".

## The lanes (one home per concern)

| # | Concern | Canonical home | Writer / tool | Write WHEN | Enforcement | State |
|---|---|---|---|---|---|---|
| 1 | **Auto-memory** — durable cross-session facts (owner prefs, decisions, infra) | `~/.claude/projects/<project>/memory/` — `MEMORY.md` index + one frontmatter `.md` per fact | Claude Code native | A durable fact is established or corrected | **ENFORCED** — `memory_index_guard.py` (Stop + SessionStart) catches files missing from the index, missing indexes, and broken links | ⚠️ **fragmented across 10 stores**; 27 orphans found 2026-08-05 (active store fixed, rest open) |
| 2 | **Graphiti** — entity/relationship + temporal graph; the ignorant agent's accumulating belief state | Neo4j (`memory` DB) via the `grc` CLI | `~/.claude/skills/graphiti-client/scripts/grc.py` (**primary**; MCP only when a server happens to be registered) | Recall before a non-trivial task; record durable facts as established | **CHECKABLE** — `grc doctor` already tests transport, tools, search roundtrip AND episode freshness. It was simply never run; `memory_health.py` now runs it | ⚠️ **read-healthy, write-dead** — all connectivity PASS, but newest episode **135h old** (2026-08-05). Nobody has been recording |
| 3 | **SSOT docs** — vision, decisions, ADRs, plans, conventions | `Agno-MCP-Platform/docs/` | Hand-maintained per PROJECT_CANON §0 | A decision is made or reality changes | **PARTIAL** — `adr-index.py` PostToolUse auto-indexes new ADRs (verified). Nothing checks DECISION_LOG or doc drift | ✅ ADR ledger continuous 0001–0044 |
| 4 | **CHANGE-ORDER** — append-as-you-go ledger of executed changes | `C:\Users\matts\OneDrive\AI Space\CHANGE-ORDER.md` | Whoever makes the change, **same turn** | After ANY executed change: what / where / why-authorization / reversal | `honour-system` | ⚠️ lapsed 07-20 → 08-04 (16 days), resumed 2026-08-05 |
| 5 | **CNF session-recall** — realtime capture + manual entries | `.claude/memories/project_memory.json` (ROOT) | claude-never-forgets fork (`/cnf-*`) | Automatic; `/cnf-remember` for manual | auto-consolidates at 20 entries | ✅ |
| 6 | **Session handoff** — day snapshots, now/recent/archive | `.remember/` (ROOT) | recall plugin (PreCompact, SessionStart) | Automatic | hook-driven | ✅ |
| 7 | **memsearch** — semantic search over past sessions | `.memsearch/` per git root | memsearch CLI + plugin hooks | Automatic | `honour-system` on health | 🔴 **BROKEN** — see Known-broken |
| 8 | **Spec Memory** — recent-context blocks injected into `CLAUDE.md` files | the `CLAUDE.md` files themselves | external tooling | Automatic | none | ℹ️ low-value; episodic noise |
| 9 | **Archive** — stale/duplicates | `_stale/` (ROOT) | Rule 1 moves | On supersession | `cc_guard` blocks deletes | ✅ |

Also present, not a lane: `.claude/recall-context.md` — populated by the recall plugin and
`@`-included by the root `CLAUDE.md`.

### Which lane wins on conflict
**SSOT docs (#3) > auto-memory (#1) > Graphiti (#2) > CNF (#5) / handoff (#6) / memsearch (#7).**
Newer owner statements beat all of them. A memory is a point-in-time observation; the SSOT is intent.

## The contract — standing obligations

Four things are owed every session. Nothing else in this doc matters if these lapse.

1. **Recall before planning.** Non-trivial task ⇒ search the ladder below *before* proposing an
   approach. Cite what you found; never assert from memory-of-memory.
2. **Record durable facts when established** — owner corrections, decisions + rationale, infra
   changes, "X is now Y". Auto-memory for the fact; Graphiti for the entities/timeline. Writing the
   file is only half — **the `MEMORY.md` index line is what makes it exist** (lane #1 is guarded
   precisely because that half kept getting skipped).
3. **Append the change order the same turn** as any executed change (#4).
4. **Comply with a rule the moment you find it** — a standing rule IS the authorization; don't ask
   permission to follow it. (Still confirm when the *action* is destructive or outward-facing.)

## Search-priority ladder
1. Auto-memory `MEMORY.md` index → the frontmatter `.md` (durable, project-keyed).
2. Graphiti — `grc search facts "<terms>"` / `grc search nodes` (entity/temporal).
3. CNF `project_memory.json` (current-session realtime).
4. `.remember/` handoff (recent/day) → memsearch (older turns, stale-aware).
5. **ASK the owner** if 1–4 yield nothing — never fabricate prior work.

## Memory protocol discipline
_(borrowed from the retired `mem0-protocol` skill, 2026-07-05 — discipline, not a new lane)_

**Anti-hallucination** — search-then-cite, never memory-of-memory; verify a write succeeded before
treating a fact as stored; surface discrepancies ("memory says X, I see Y") rather than silently
picking; only verbatim or confirmed facts.

**Correction protocol** — save the NEW fact immediately by updating the existing `.md` (don't
duplicate); record the transition in the body (`Previous: X. Updated to: Y. Reason: <owner wording>`);
apply it for the rest of the session; stop citing the superseded value.

**Save / don't-save** — SAVE owner corrections, preferences, decisions-with-rationale, infra changes,
bug+exact-error+fix. DON'T save greetings, generic advice, transient paths, hypotheticals, or
chit-chat CNF already captures.

## Health check
```
python ~/.claude/hooks/memory_health.py          # all lanes, PASS/WARN/FAIL
python ~/.claude/hooks/memory_index_guard.py --check   # auto-memory index only
```
Run it when resuming, or any time a lane feels stale. It is read-only.

## Known-broken (as of 2026-08-05)
- 🔴 **memsearch indexing dead — TWO stacked faults.**
  1. ~~`embedding.provider = "onnx"` with `model = "gemini-embedding-001"`~~ **FIXED 2026-08-05**:
     provider set to **`google`** (not `gemini` — that string isn't in memsearch's `_PROVIDERS`
     registry and raises `Unknown embedding provider`). Verified standalone: init 1.8s, embed 0.3s,
     **dim 768**, which matches every existing collection, so no re-embed was needed.
  2. 🔴 **STILL BROKEN — Milvus.** With the embedder fixed, indexing now hangs instead of erroring.
     Thread-stack dump: `store.py:_load_collection` → `pymilvus.load_collection` →
     `wait_for_loading_collection` → `time.sleep` forever. `get_load_state` shows **3 of 6
     collections stuck at `Loading, progress: 0`** (`agent_session_memory`,
     `ms_agno_mcp_platform_9e350219`, `ms_double_shot_latte_4080276b`); the other 3 load fine.
     Milvus accepts the connection and lists collections instantly — it just never finishes loading
     these three. **This is the live argument for ADR-0040's Weaviate cutover**, which already
     locked Weaviate and sidelined Milvus; memsearch still pointing at Milvus is drift from canon
     *and* is now the thing blocking semantic recall.
  The Claude Code memsearch plugin is also 11 versions behind (0.4.6 vs 0.4.17).
- ⚠️ **Auto-memory fragmented across 10 stores** (Rule 0). 27 orphans outside the active store,
  including a store with no `MEMORY.md` at all. Several are `*.from-*.md` sync artifacts — decide
  what those are before indexing them.
- ⚠️ **Graphiti write-lane silently stalled.** `grc doctor` 2026-08-05: every connectivity check
  PASSes (direct init, ContextForge init, status, 9 tools, search roundtrip with a working embedder)
  but **episode freshness FAILs — newest episode 135h old**. The lane isn't broken; the *obligation*
  lapsed and nothing noticed. Textbook Rule 2.
- ℹ️ **Two working Graphiti transports** (corrected 2026-08-05): the direct no-auth door
  `100.119.96.29:8071` **and** the authenticated ContextForge route
  `100.72.169.40:4444/servers/<id>/mcp`. `grc` prefers direct. Retiring the no-auth door is an open
  ADR-0037 item — when it happens, `grc` should fall back to the CF route rather than break.
