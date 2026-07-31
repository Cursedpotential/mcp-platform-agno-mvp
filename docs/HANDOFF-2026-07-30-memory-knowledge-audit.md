# HANDOFF — Memory/Knowledge audit + review-hardening (2026-07-30)

> _Byline: Claude Code · Fable 5 · 2026-07-30_
> Prior session ran in the WRONG cwd (`C:\Users\matts\.agents\skills\mineru`) — this handoff
> moves the work here. Next session: run from THIS repo root, read this file top to bottom.
> Session logs from the prior work live under
> `C:/Users/matts/.claude/projects/C--Users-matts--agents-skills-mineru/*.jsonl` (grep-able).

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| **Branch** | `fix/review-hardening-adr36-40` — pushed, PR #17 open (base `docs/adr-graphiti-memory`). 4 commits: `ed0978b` five review fixes · `b571323` 10-point doc/config reconciliation · `ea2d1ca` owner ADR/canon docs + ADR-0042 · plus fork-point handoff commit. |
| **Review fixes (ed0978b)** | workflows.py dedup-skip transparency · registry.load_builtin_tools memoized · apply_db_modification `DB_WRITE_SCHEMAS` env allowlist (evidence HARD-denied) · two-way `REROUTE: builder`/`platform-ops` routing (Router honors ONE bounce) · semantica_wiring.py rewritten per ADR-0036/0040. |
| **Reconciliation (b571323)** | Embedder truth propagated (nv-embed-v1 4096-d LIVE since 2026-07-19; bge-m3 retired; nemotron = legacy asymmetric fallback) across session.py/settings.py/core README/example.env/milvus_forensic banner/smoke script/HANDOFF ADR row/DEBT.md. |
| **Weaviate cutover** | DONE in session.py by the parallel session (2026-07-29): `create_knowledge()` → agno Weaviate wrapper, `connect_to_custom` 100.119.96.29 REST :8081 / gRPC :50051. A live worktree existed at `.claude/worktrees/wf_2f37bdc8-dea-3/` — check it's merged/closed before editing session.py/main.py. |
| **ADR-0036** | ACCEPTED 2026-07-29 — DozerDB, one Neo4j, `memory` DB (graphiti_writer, ONLY thing Graphiti writes) + `evidence` DB (semantica_writer). Graphs permission-isolated. |

## AUDIT RESULT — AgentOS memory/knowledge "broken on first open"

Read-only audit completed 2026-07-30 (agno==2.6.13 in local venv; prod requirements pins 2.8.0). Findings ranked:

### #1 — DB id collision (root cause, HIGH confidence — NOT yet fixed)
- `server/core/session.py:40` `DB_ID = "agentos-db"` used by BOTH `get_agno_db()` (SurrealDb, line ~179) and `get_postgres_db()` (line ~165).
- `main.py:179` agents get SurrealDb; `main.py:199` `admin_db = get_postgres_db()` → `AgentOS(db=admin_db)` (main.py:237).
- agno `os/app.py:1325-1334` registers dbs keyed by `db.id` → both backends merge into ONE bucket `"agentos-db"`.
- agno `os/utils.py:246-312` resolver: multi-db guard counts dict KEYS (=1) so it never fires → memory/session/knowledge-content routes hit SurrealDb-or-Postgres by registration order + table-name luck.
- Timeline: admin-db split 2026-07-23 (main.py:21 byline) → owner saw breakage 2026-07-27. Weaviate cutover was a red herring.
- **Fix**: distinct ids — e.g. `get_postgres_db()` admin call → `id="agentos-admin-db"`; contents_db its own id. Then verify registry shows 2 keys and memory routes resolve to SurrealDb explicitly.
- **PENDING OWNER DECISION** (was Option A/B/C): confirm live first (below), then apply.

### #2 — uv.lock stale/trap
- `uv.lock` (2026-07-23) has NO weaviate-client → local `.venv` cannot import `server.core.session` at all (top-level Weaviate import). Verified live.
- Prod likely safe: Dockerfile + CI install from requirements.txt (`weaviate-client==4.22.0`, `agno==2.8.0`).
- **Fix**: `uv lock` regen + rebuild `.venv`.

### #3 — agno Weaviate wrapper closes shared client per sync search
- agno `vectordb/weaviate/weaviate.py:487/565/646` `finally: get_client().close()` on the ONE shared client. Self-healing sequentially; race under concurrent UI panel loads. insert/upsert don't close (asymmetry).
- **Check**: agentos-api logs for `WeaviateClosedClientError` / gRPC UNAVAILABLE at UI-open times. Fix = upstream/pin, not platform code.

### #4 — Doc drift ("Milvus-backed" in providers.py:61, factory.py:144, knowledge_handle.py docstring, main.py:149/166, settings.py:15) — mechanical cleanup.

### #5 — ADR-0038 accepted 2026-07-29 but UNIMPLEMENTED — `graphiti-core` nowhere in deps/code; Graphiti still MCP-only (`providers.py:180-195`, silently skipped if `GRAPHITI_MCP_URL` unset — also presents as "memory features missing").

### Live checks still needed (Option C)
1. Running container: does AgentOS db registry show 1 key or 2? (confirms #1)
2. Browser/network trace of the exact failing UI call (memory-list 400 vs knowledge 503 vs Weaviate 5xx).
3. Was the deployed image built BEFORE weaviate-client landed in requirements.txt (2026-07-29 ~07:37)?
4. Does Weaviate `Platform_knowledge` actually hold objects post-cutover (Milvus→Weaviate export status)?
5. `GRAPHITI_MCP_URL` set on live agentos-api?

## Open workstreams (owner order)

1. **[in_progress] Memory/knowledge systems** — this audit → live checks → apply #1 fix → #2 lock regen → #4 docs → #5 schedule graphiti-core.
2. **[pending] TraceIQ → Agno knowledge tie-in** — HANDOFF-2026-07-27 Phase 3 task 2: TraceIQ facts → Graphiti w/ provenance + node-count landing gate.
3. **[pending] Finish the Case Bible** — scope with owner first (sort completion vs vault scaffold vs lakehouse vs all). Use case-bible:* skills; architect governs structure.

## Owner working-style contract (REQUIRED)

- **Structured replies always**: bullets, labeled Observation/Question/Recommendation blocks, white space, answer-first (owner ADHD; in global CLAUDE.md; hyperfocus plugin flow-mode when loaded).
- Confirm before changes; never hard-delete (quarantine); byline every artifact; verify before claiming done.

## Tooling notes for next session

- smart-explore engine: `bash /c/Users/matts/.agents/skills/smart-explore/se` — this repo is already indexed in the central store (search/outline/unfold/refs --lsp/imports/changed all work).
- /smart-explore command: history-digest (Step 1.5) + log-arbitrated contradiction sweep (Step 3) are wired in.
- Contradiction-arbitration rule: newest owner-approved statement wins (owner corrections > newer docs > older docs > code comments).
