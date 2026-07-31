# HANDOFF — Current task list (2026-07-30)

> _Byline: Claude Code · Fable 5 · 2026-07-30_
STATUS: PARTIAL
BUILD_STATUS: UNKNOWN

Persisted snapshot of the active task list, owner order. Fuller technical state for task 1 lives in
`docs/HANDOFF-2026-07-30-memory-knowledge-audit.md` — read that before working task 1.

## Task list (owner order)

### 1. [in_progress] Memory/knowledge systems — AgentOS "broken on first open"
Audit complete (read-only, 2026-07-30). Remaining, in order:
1. Live checks (Option C): db-registry key count on running container (1 vs 2 confirms the
   `DB_ID = "agentos-db"` collision root cause) · browser/network trace of exact failing UI call ·
   was deployed image built before weaviate-client landed in requirements.txt (2026-07-29 ~07:37) ·
   does Weaviate `Platform_knowledge` hold objects post-cutover · is `GRAPHITI_MCP_URL` set live.
2. Apply fix #1 — distinct db ids (`agentos-admin-db` for the Postgres admin call) — PENDING OWNER
   DECISION, confirm live first.
3. Fix #2 — `uv lock` regen + rebuild local `.venv` (lock is stale, missing weaviate-client;
   local import of `server.core.session` is broken — verified).
4. Fix #4 — mechanical "Milvus-backed" doc-drift cleanup (providers.py:61, factory.py:144,
   knowledge_handle.py docstring, main.py:149/166, settings.py:15).
5. Fix #5 — schedule ADR-0038 implementation (`graphiti-core` is accepted but nowhere in deps/code;
   Graphiti still MCP-only and silently skipped when `GRAPHITI_MCP_URL` unset).

### 2. [pending] TraceIQ → Agno knowledge tie-in
HANDOFF-2026-07-27 Phase 3 task 2: TraceIQ facts → Graphiti with provenance + node-count landing gate.

### 3. [pending] Finish the Case Bible
Scope with owner first (sort completion vs vault scaffold vs lakehouse vs all).
Use case-bible:* skills; case-bible-architect governs structure.

### 4. [complete 2026-07-30] HANDOFF v2 system (global, ~/.claude)
`/handoff` skill (`~/.claude/skills/handoff/SKILL.md`) + PreCompact hook (compact summaries follow
HANDOFF v2 shape) + SessionStart(compact) hook (re-anchors fresh context on newest `HANDOFF-*.md`).
Scripts pipe-tested; settings.json validated.

## UNRESOLVED (mandatory)

- HANDOFF v2 hooks not yet live-fire verified — compaction fires outside a turn; first real
  `/compact` is the end-to-end test. If silent, open `/hooks` once to reload config.
- BUILD_STATUS UNKNOWN — branch `fix/review-hardening-adr36-40` build/tests not run at handoff time;
  local `.venv` is known-broken until fix #2 (stale uv.lock).
- Uncommitted working-tree changes NOT covered by this handoff: `docs/PROJECT_CANON.md`,
  `docs/adr/0036-...md` (modified), `.migration-passes/` (untracked) — provenance unknown to this
  session; do not sweep into unrelated commits.

## Pending owner decisions

- Fix #1 db-id split — WHAT: give admin Postgres db its own id · WHY: both backends currently merge
  into one registry bucket, routing memory/session routes by luck · options: rename admin id
  (recommended) vs rename SurrealDb id vs registry-level guard · confirm live (check 1) first.

## Owner working-style contract

- Structured replies: bullets, labeled blocks, white space, answer-first.
- Confirm before changes; never hard-delete (quarantine); byline every artifact; verify before
  claiming done.
