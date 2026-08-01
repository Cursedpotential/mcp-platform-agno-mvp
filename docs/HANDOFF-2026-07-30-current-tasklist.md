# HANDOFF — Current task list (2026-07-30)

> _Byline: Claude Code · Fable 5 · 2026-07-30_
> _Correction: Claude Code · Opus 5 · 2026-08-01 — task 1 items 1/2/3/4 are DONE (commit `9a7e4ac`,
> 2026-07-31); the "pending owner decision" below is superseded. See the dated block in task 1._
STATUS: RESOLVED (workstream 1 complete + deployed 2026-08-01)
BUILD_STATUS: PASSING (441 passed / 3 skipped / 0 failed at prod's agno 2.8.0 — 2026-08-01)

Persisted snapshot of the active task list, owner order. Fuller technical state for task 1 lives in
`docs/HANDOFF-2026-07-30-memory-knowledge-audit.md` — read that before working task 1.

## Task list (owner order)

### 1. [COMPLETE 2026-08-01 — merged to `main`, deployed, verified live] Memory/knowledge systems
Audit complete (read-only, 2026-07-30). Remaining, in order:
1. ~~Live checks (Option C)~~ **DONE 2026-07-31** — all five ran; live `/config` returned
   `databases:["agentos-db"]` (1 key), confirming the collision root cause.
2. ~~Apply fix #1 — distinct db ids (`agentos-admin-db` for the Postgres admin call) — PENDING OWNER
   DECISION, confirm live first.~~ **DONE 2026-07-31** (`9a7e4ac`): SurrealDb keeps `agentos-db`,
   admin plane → `agentos-admin-db`, Knowledge contents → `agentos-contents-db`. Same commit also
   enabled `enable_user_memories` on Root Router + Project PAL (live check found `agno_memories`
   empty in BOTH backends — nothing was ever capturing memories).
   ~~**NOT YET IN PROD**~~ — **IN PROD 2026-08-01.** Merged to `main`, exec-tier redeployed.
3. ~~Fix #2 — `uv lock` regen + rebuild local `.venv`~~ **RESOLVED 2026-07-31** — `uv.lock` already
   carried `weaviate-client==4.22.0`; `uv sync --extra dev` fixed the venv and
   `server.core.session` imports clean (re-verified 2026-08-01).
   ~~**Residual:** the lock pins `agno==2.6.13` while `requirements.txt` (prod) pins `agno==2.8.0`.~~
   **CLOSED 2026-08-01** — local venv pinned to prod's exact `agno==2.8.0`; suite re-run at that
   version: **406 passed, 3 skipped, 0 failed**. The old "1 pre-existing tool-roster failure" was a
   symptom of the version skew, not a defect. Run tests as `uv run --no-sync pytest -q`.
4. ~~Fix #4 — mechanical "Milvus-backed" doc-drift cleanup~~ **DONE 2026-07-31** (`9a7e4ac`) —
   main.py, factory.py, providers.py, knowledge_handle.py, settings.py, store.py, core/README.md,
   evidence/AGENTS.md, server/AGENTS.md.
5. Fix #5 — schedule ADR-0038 implementation (`graphiti-core` is accepted but nowhere in deps/code;
   Graphiti still MCP-only and silently skipped when `GRAPHITI_MCP_URL` unset).
   ~~**Now blocked on the Graphiti image rebuild decision**~~ — **UNBLOCKED.** The rebuild was
   approved, built, deployed and canary-verified on **2026-07-31** (parallel worktree
   `_worktrees/gateway-litellm` → merged to `origin/main`, brought onto this branch 2026-08-01).
   `ghcr.io/cursedpotential/graphiti-mcp:0.29.3` @ `sha256:fc64fd33…` runs on ovh-files with the
   Neo4j `database=` fix, GLiNER2 enabled, 13 tools (was 9). ADR-0038's `graphiti-core` wiring is
   now the only remaining piece. See the AS-BUILT section of
   `docs/planning/graphiti-image-rebuild-plan.md`.

6. ~~**NEW — deploy gate before the #1 fix reaches prod.**~~ **CLEARED 2026-08-01 (`6bfb522`)** —
   `server/api/db_id_middleware.py` defaults absent `db_id` to the operational store on all 48
   db_id-accepting routes. Proven on agno 2.8.0: three ids without the middleware → 400; with it →
   200; explicit `db_id` still honoured. Suite 414 passed / 0 failed.

7. ~~**NEXT — the deploy itself.**~~ **DONE 2026-08-01.** Merged to `main` and deployed. Took
   seven fixes: the deploy exposed a crash-loop (missing transitive deps), then the middleware
   matching zero routes under `base_app=`, then four separate ingest bugs. Full chain + standing
   lessons in the audit handoff's "RESOLVED + DEPLOYED" section.

8. ~~**NEW — broken knowledge ingest.**~~ **FIXED + VERIFIED 2026-08-01.** Root cause was NOT the
   embedder: agno's async client fell back to `localhost:8080`, so every WRITE failed while sync
   reads worked. `ingest_all` now returns `INGEST OK, files: 4`; Weaviate 7 -> 59 objects across 5
   documents; content rows 7 completed / 1 failed (the leftover `PROJECT_CANON.md`).

9. **STILL OPEN — deploy plumbing.** (a) The GitHub->Coolify webhook does not fire; every deploy
   today was a manual API call, and this is likely why prod sat 9 days stale. (b) `agentos:latest`
   is overwritten in place, so there was NO rollback target during the crash-loop — deploy by
   digest like the Graphiti image does.

### 2. [pending] TraceIQ → Agno knowledge tie-in
HANDOFF-2026-07-27 Phase 3 task 2: TraceIQ facts → Graphiti with provenance + node-count landing gate.

### 3. [pending] Finish the Case Bible
Scope with owner first (sort completion vs vault scaffold vs lakehouse vs all).
Use case-bible:* skills; case-bible-architect governs structure.

### 4. [complete 2026-07-31] HANDOFF v2 system (global, ~/.claude) — LIVE-FIRE VERIFIED
`/handoff` skill (`~/.claude/skills/handoff/SKILL.md`) + three hooks in `~/.claude/settings.json`:
- **PreCompact** (`precompact_handoff.py`) — snapshots open tasks to `docs/TODO-SNAPSHOT-<date>.json`.
  It does **NOT** shape the compaction summary: Claude Code schema-validates hook JSON and PreCompact
  has **no `hookSpecificOutput.additionalContext` variant**. Emitting it fails validation and discards
  the hook's entire output. Verified live 2026-07-31 (first real `/compact` errored on exactly this);
  script rewritten to emit only top-level fields (`suppressOutput` + `systemMessage`).
- **PostCompact** (`postcompact_summary.py`) — writes the summary to `docs/COMPACT-SUMMARY-<date>.md`.
- **SessionStart(compact)** (`sessionstart_compact_handoff.py`) — the only injection point that works;
  re-anchors fresh context on the newest `HANDOFF-*.md`, points at the newest `TODO-SNAPSHOT-*.json`,
  and restates the owner working-style contract.

Net effect: HANDOFF v2 shape is enforced by the `/handoff` skill and by post-compact re-anchoring —
never by pre-compact summary instructions, which the platform does not support.

## UNRESOLVED (mandatory)

- ~~HANDOFF v2 hooks not yet live-fire verified~~ — RESOLVED 2026-07-31. First real `/compact` ran:
  PreCompact task-snapshot worked, PreCompact context-injection failed schema validation (see task 4),
  PostCompact + SessionStart succeeded. Hooks reload at session start, so the corrected PreCompact
  script takes effect from the next session onward.
- ~~BUILD_STATUS UNKNOWN~~ — RESOLVED 2026-08-01: 441 passed / 3 skipped / 0 failed at prod's
  agno 2.8.0; ruff clean; mypy unchanged (2 pre-existing `server/evidence/cli.py` errors).
- Uncommitted working-tree changes NOT covered by this handoff: `docs/PROJECT_CANON.md`,
  `docs/adr/0036-...md` (modified), `.migration-passes/` (untracked) — provenance unknown to this
  session; do not sweep into unrelated commits.

## Pending owner decisions

- ~~Fix #1 db-id split~~ — **DECIDED, APPLIED, AND DEPLOYED** (`9a7e4ac`, option (a)); live in prod
  2026-08-01 behind the `db_id` default middleware (`6bfb522`/`a930114`).
- ~~**Graphiti image rebuild**~~ — **BUILT, DEPLOYED, CANARY-GREEN 2026-07-31**; all three owner
  questions answered (rebuild approved, GLiNER2 enabled, no upstream PR). Original framing kept
  below for history. WHAT: vendor `mcp_server/` at
  a pinned ref into `docker/graphiti/`, apply the ~6-line Neo4j `database=` driver fix, build on
  `graphiti-core 0.29.3`, publish to GHCR by digest, canary on `data-graphiti-case`. WHY: we run
  `zepai/knowledge-graph-mcp:latest` built 2026-03-11 and unpinned, and the upstream driver drops
  the `database` field, which is what forced the hotfix pile. OPTIONS + the two sub-questions
  (GLiNER2 on/off, upstream PR identity) are at the foot of
  `docs/planning/graphiti-image-rebuild-plan.md`.

## Owner working-style contract

- Structured replies: bullets, labeled blocks, white space, answer-first.
- Confirm before changes; never hard-delete (quarantine); byline every artifact; verify before
  claiming done.
