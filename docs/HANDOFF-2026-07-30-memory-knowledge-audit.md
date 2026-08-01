# HANDOFF — Memory/Knowledge audit + review-hardening (2026-07-30)

> _Byline: Claude Code · Fable 5 · 2026-07-30 (conformed to HANDOFF v2 template 2026-07-31)_
> _Correction: Claude Code · Opus 5 · 2026-08-01 — findings #1, #2 and #4 are RESOLVED in commit
> `9a7e4ac` (2026-07-31); all five live checks ran. A NEW pre-deploy gate was found while
> re-verifying against agno 2.8.0 (the version prod actually runs) — see "Pre-deploy gate" below._
STATUS: PARTIAL
BUILD_STATUS: PASSING (405 tests, 1 pre-existing agno tool-roster failure that also fails on stash)

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
- ~~**PENDING OWNER DECISION** (was Option A/B/C): confirm live first (below), then apply.~~
- **RESOLVED 2026-07-31** (`9a7e4ac`, option (a)): SurrealDb keeps `agentos-db`, admin plane →
  `agentos-admin-db`, Knowledge contents → `agentos-contents-db`. Live `/config` had returned
  `databases:["agentos-db"]` (1 key) before the fix — root cause confirmed, not just inferred.
- Same commit set `enable_user_memories` on Root Router + Project PAL: the live check found
  `agno_memories` with **0 rows in BOTH backends**, so the memory panel was empty for a second,
  independent reason — nothing was ever extracting memories.
- **NOT IN PROD YET** — live agentos-api still runs the 2026-07-23 image.

#### Pre-deploy gate (NEW — **PROVEN** 2026-08-01 by executable probe, not inference)

**Probe:** `scratchpad/db_id_gate_probe.py` builds a real `AgentOS` on agno **2.8.0** with throwaway
SQLite dbs in both registry shapes and calls `GET /memories` through a `TestClient`:

| Registry shape | `/config` databases | `GET /memories` (no `db_id`) | `GET /memories?db_id=…` |
|---|---|---|---|
| BEFORE fix — one shared id | `['agentos-db']` | **200** (silently wrong backend) | 200 |
| AFTER fix — three ids | `['agentos-db','agentos-contents-db','agentos-admin-db']` | **400** `db_id query parameter is required` | 200 |

**Live state confirmed the same day** (tailnet `http://100.72.169.40:8000/config`, HTTP 200):
`databases: ['agentos-db']`, `os_id: mcp-forensic-platform`; container
`agentos-api-rz41wqhpjfh1rj796ixvjhfs-…` started **2026-07-23T06:35Z** — i.e. the pre-fix image,
still the one-key shape. The audit's root cause is now proven at both ends.

> Note: `https://agentos.mitechconsult.com` returns 503 (`no available server`). That is
> **pre-existing and already documented** in `docs/adr/0035-*.md:168` — Traefik has no dynamic route
> for the host and the `default_redirect_503.yaml` catch-all answers. It is NOT a regression and not
> the owner's path: the control surface tunnels to tailnet `:8000`, which serves 200.

**Agno's documented contract** (docs.agno.com, `agent-os/knowledge/manage-knowledge`): omitting the
id is explicitly *backward-compatibility for the single-instance case*; multi-instance callers are
expected to pass `db_id`/`knowledge_id`. So the 400 is agno working as designed, not a bug.

**The gate that remains:** whether the os.agno.com SPA actually sends `db_id`. It is closed-source,
so this cannot be settled from the repo — it needs the UI opened against a deployed instance.

#### Superseded reasoning (kept for history)

The audit reasoned against agno 2.6.13 (local venv). Re-verified in 2.8.0 — the mechanism holds,
and it has a **behavioural edge the fix introduces**:

- `AgentOS._register_db_with_validation` builds `dbs: Dict[str, List[db]]`, appending same-id
  backends into ONE list under one key. Confirmed.
- `agno/os/utils.py` resolver: `if len(dbs) > 1: raise HTTPException(400, "The db_id query
  parameter is required when using multiple databases")`. It counts **keys**. With one shared id
  the guard never fired and the resolver returned `all_dbs[0]` — the first-registered backend,
  regardless of which one owns the table. Exactly the audit's claim.
- **Edge:** post-fix the registry has **3 keys**, so that guard now DOES fire. `db_id` is
  `Optional[str] = Query(default=None)` on *every* memory route — so any client that omits it gets
  a hard **400** where it previously got a silently-wrong-but-200 answer.
- **Therefore, before/at redeploy:** confirm the AgentOS UI sends `db_id` on memory/session/
  knowledge calls. If it does not, the fix converts a silent-wrong bug into a visible-broken one.
  Mitigation if needed: keep the admin/contents split but re-merge the two Postgres roles under a
  single id, leaving 2 keys, and pass `db_id` explicitly from our own callers.

### "NOTHING IN THE PLATFORM IS POPULATED" — answered against the live API (2026-08-01)

Owner report, with 13 UI screenshots: *"really nothing in the platform is populated or functional,
no agents, no workflows, knowledge, entities, nothing."* Checked `GET /config` on the live instance
(tailnet `:8000`, HTTP 200). The roster **is** served:

| Surface | Live API says | Verdict |
|---|---|---|
| **Agents** | **6** — ingestion-orchestrator, analysis-orchestrator, review-gatekeeper, dev-copilot, project-pal, forensic-data-agent | ✅ populated |
| **Teams** | **3** — mcp-platform-router, platform-ops, builder | ✅ populated |
| **Workflows** | **0** | ❌ genuinely none registered |
| **Interfaces** | **0** | (none configured) |
| **Knowledge** | 1 instance `platform` → `agentos-db` / `platform_knowledge_contents` | ⚠ contents exist, vectors mostly missing (above) |
| **Databases** | **1** — `agentos-db` | ❌ the collision, still live |

**The agents/teams complaint is a UI-surface confusion, not an outage.** The screenshots are of
**Studio → Agents / Teams / Workflows** (`os.agno.com/studio/*`), which is agno's **cloud authoring**
surface — "Get started by creating a new agent", with greyed *demo templates* (Support Agent, Data
Agent, Sales Team, Report Generator…). Those are agno's samples, not ours. Agents defined in Python
and served by a connected AgentOS do **not** appear there; they appear under **Chat** (the
agent/team picker) and in **Studio → Registry**.

**Registry corroborates the connection is healthy** — it shows our real instance: model `Ollama /
GLM-5.1`, tools `apply_db_modification` / `describe_tool` / `execute_tool`, database `AGENTOS-DB`.

**Genuinely broken/empty, with causes:**
1. **Memory panel empty** — `agno_memories` 0 rows in both backends; nothing ever extracted
   memories. Fixed in `9a7e4ac` (`enable_user_memories`), **not yet deployed**.
2. **Knowledge mostly unretrievable** — 3 of 4 content rows have no vectors (table above).
3. **Workflows genuinely 0** — `server/evidence/workflows.py` exists but nothing is registered as
   an AgentOS `Workflow`, so the panel is correctly empty. Separate piece of work.
4. **Entity Memories empty** — same root cause as (1).

**Useful UI evidence for the deploy gate:** the Memory page renders an explicit
`Database: agentos-db / Table: agno_memories` selector — i.e. the SPA *is* database-aware and
resolves a specific db, which is encouraging (though not proof) for it sending `db_id` once the
registry holds three keys.

### DEPLOY BLOCKERS — what a redeploy of this branch actually ships (verified 2026-08-01)

The redeploy is **not** just the db-id fix. The live image is the **2026-07-23** build; the branch
has moved on twice since. Verified by probing the running container directly:

```
docker exec <agentos-api> python -c "import weaviate"  -> ModuleNotFoundError: No module named 'weaviate'
docker exec <agentos-api> python -c "import agno"      -> 2.8.0
docker exec <agentos-api> python -c "import pymilvus"  -> 3.0.0
```

So prod today is **still Milvus-era code**. One redeploy lands three changes at once:

| # | Change | Risk |
|---|---|---|
| 1 | db-id split (`9a7e4ac`) | **Arms agno's multi-db guard** — clients omitting `db_id` get 400 (proven by probe) |
| 2 | **Milvus → Weaviate cutover goes live for the first time** | See count mismatch below |
| 3 | `enable_user_memories` on Root Router + Project PAL | Benign/desired — memory capture starts working |

**Count mismatch — RAISED then RESOLVED the same day. NOT a blocker.**

> ~~Milvus 14 rows vs Weaviate 7 objects → "cutting over risks halving the knowledge base".~~
> **Wrong — corrected 2026-08-01 by a full `query_iterator` walk.** Milvus's `row_count: 14` is a
> segment-level statistic that counts soft-deleted/uncompacted rows (the doc was re-indexed once).
> Iterating the collection returns **7 live rows**. Both stores hold the *same* content:

| Store | Live rows | Distinct sha256 | Chunks |
|---|---|---|---|
| Milvus `platform_knowledge` | **7** | `d8f1b80f8826` ×7 | 1–7 |
| Weaviate `Platform_knowledge` | **7** | `d8f1b80f8826` ×7 | 1–7 |

**Vector parity is exact.** The Milvus→Weaviate export is complete. Lesson: never compare
`get_collection_stats()['row_count']` against another store's object count — walk the collection.

**The REAL knowledge defect (found via the owner's 2026-08-01 UI screenshots):** the Knowledge page
lists **4 content rows**, but only **one** of them has vectors in either store:

| Content row | Status in UI | Vectors |
|---|---|---|
| `d8f1b80f8826-d11a456b…` (file, 23 Jul) | COMPLETED | **7 chunks** ✅ |
| `38dfbfc8bbce-63ec8468…` (file, 20 Jul) | COMPLETED | **none** ❌ |
| `PROJECT_CANON.md` (file, 20 Jul) | **FAILED** | none |
| `ingest-smoke-test` (text) | COMPLETED | **none** ❌ |

So contents rows (Postgres) and vectors (Milvus/Weaviate) have diverged: two rows report COMPLETED
with nothing embedded, one hard-FAILED. That — not the cutover — is why knowledge retrieval looks
empty. Chase the ingest/embed path, and note the global rule: a `float vector field … got nil`
class of failure means the embedder returned no vector (dead key / out-of-credits / gateway).

**Finding #3 (Weaviate client-close race) is NOT observable in prod** and cannot be: 9 days of
`agentos-api` logs contain **zero** `WeaviateClosedClientError`, zero gRPC `UNAVAILABLE`, and zero
mentions of Weaviate at all — because the module isn't installed. The race becomes live only
*after* this redeploy. It is a post-deploy watch item, not a pre-deploy one.

### #2 — uv.lock stale/trap
- `uv.lock` (2026-07-23) has NO weaviate-client → local `.venv` cannot import `server.core.session` at all (top-level Weaviate import). Verified live.
- Prod likely safe: Dockerfile + CI install from requirements.txt (`weaviate-client==4.22.0`, `agno==2.8.0`).
- ~~**Fix**: `uv lock` regen + rebuild `.venv`.~~ **RESOLVED 2026-07-31** — the lock already carried
  `weaviate-client==4.22.0`; `uv sync --extra dev` rebuilt the venv. `server.core.session` imports
  clean (re-verified 2026-08-01).
- ~~**Residual, still open:** `uv.lock` pins `agno==2.6.13` … **Fix**: pin `agno==2.8.0` in
  `pyproject.toml`~~ — **RESOLVED 2026-08-01, by a different mechanism than first proposed.**
  - Correction: `uv.lock` is **gitignored**; `.gitignore:31` states *"requirements.txt is the
    lockfile of record"*. `requirements.txt` is generated by `uv pip compile pyproject.toml`
    (`scripts/generate_requirements.sh`) and the image installs it via
    `uv pip sync requirements.txt --system`. So pinning pyproject was the wrong lever.
  - `uv pip sync requirements.txt` **cannot run on Windows** — the file is a Linux-target compile
    (contains `uvloop==0.22.1`; see commit `c0fe6cb` "regenerate requirements.txt for linux, not the
    compiling host"). This is why local dev uses `uv sync` from pyproject instead. Not a defect.
  - Applied instead: `uv lock --upgrade-package agno` (resolved 2.8.6, latest) then pinned the venv
    to prod's exact version with `uv pip install "agno[os,slack]==2.8.0"`. Run tests with
    `uv run --no-sync` so `uv run` does not re-sync 2.8.6 over it.
  - **Result: 406 passed, 3 skipped, 0 failed.** The previously-recorded "1 pre-existing agno
    tool-roster failure" was an **artefact of the 2.6.13 skew** — it passes on prod's 2.8.0. There
    is no known-failing test on this branch.
  - Still-open (cosmetic, pre-existing, untouched): `ruff format --check` would reformat 7 test
    files; `mypy server` reports 2 errors in `server/evidence/cli.py:55`.

### #3 — agno Weaviate wrapper closes shared client per sync search
- agno `vectordb/weaviate/weaviate.py:487/565/646` `finally: get_client().close()` on the ONE shared client. Self-healing sequentially; race under concurrent UI panel loads. insert/upsert don't close (asymmetry).
- **Check**: agentos-api logs for `WeaviateClosedClientError` / gRPC UNAVAILABLE at UI-open times. Fix = upstream/pin, not platform code.

### #4 — Doc drift ("Milvus-backed" in providers.py:61, factory.py:144, knowledge_handle.py docstring, main.py:149/166, settings.py:15) — mechanical cleanup.
- **RESOLVED 2026-07-31** (`9a7e4ac`) across main.py, factory.py, providers.py, knowledge_handle.py,
  settings.py, store.py, core/README.md, evidence/AGENTS.md, server/AGENTS.md. Deliberate
  deprecation aliases left untouched.

### #5 — ADR-0038 accepted 2026-07-29 but UNIMPLEMENTED — `graphiti-core` nowhere in deps/code; Graphiti still MCP-only (`providers.py:180-195`, silently skipped if `GRAPHITI_MCP_URL` unset — also presents as "memory features missing").
- **Still open, now sequenced behind the image rebuild.** Research completed 2026-07-31:
  `docs/planning/graphiti-image-rebuild-plan.md`. We run `zepai/knowledge-graph-mcp:latest`, digest
  built 2026-03-11, **unpinned**; upstream `DatabaseDriverFactory.create_config` drops the `database`
  field on the neo4j branch (a ~6-line wiring gap, fixable upstream), which is why the hotfix pile
  exists. Three owner questions are open at the foot of that doc.

### ~~Live checks still needed (Option C)~~ — ALL RAN 2026-07-31
1. ~~Running container: does AgentOS db registry show 1 key or 2?~~ **1 key** (`databases:["agentos-db"]`) — confirms #1.
2. ~~Browser/network trace of the exact failing UI call.~~ Ran; combined with (1) and the empty `agno_memories` finding.
3. ~~Was the deployed image built BEFORE weaviate-client landed in requirements.txt?~~ Ran — live image is the 2026-07-23 build.
4. ~~Does Weaviate `Platform_knowledge` actually hold objects post-cutover?~~ Ran.
5. ~~`GRAPHITI_MCP_URL` set on live agentos-api?~~ Ran.

## UNRESOLVED (mandatory)

_Updated 2026-08-01. Resolved entries kept struck-through for history._

- ~~**Root-cause fix #1 NOT applied**~~ — RESOLVED 2026-07-31 (`9a7e4ac`).
- ~~**All five live checks below are unrun**~~ — RESOLVED 2026-07-31, all five ran.
- ~~**BUILD_STATUS UNKNOWN**~~ — RESOLVED: ruff clean, 405 tests pass with one pre-existing agno
  tool-roster failure that also fails on stash.
- ~~**Findings #2–#5 all open**~~ — #2 and #4 resolved; #3 and #5 still open, plus two new items:
- **#1 fix is committed but NOT DEPLOYED** — WHY: live agentos-api still runs the 2026-07-23 image;
  the fix reaches prod only via merge + exec-tier redeploy. SHORTCOMING of leaving it: the owner's
  original "broken on first open" symptom is still live in prod today.
- **Pre-deploy gate on the #1 fix — mechanism PROVEN, UI behaviour still UNVERIFIED** — the 400 is
  now demonstrated by executable probe on agno 2.8.0 (table under finding #1). What remains unknown
  is only whether the closed-source os.agno.com SPA sends `db_id`. SHORTCOMING: deploying blind
  risks trading a silent-wrong bug for a visible-broken one.
  RECOMMENDED MITIGATION (makes the deploy safe either way, and is arguably the *complete* fix):
  a small middleware in `main.py` that defaults absent `db_id` to `agentos-db` (SurrealDb) on
  memory/session routes. That makes routing **deliberate** rather than either a lottery (pre-fix)
  or a 400 (post-fix). Not yet applied — owner decision.
- ~~**agno version skew**~~ — RESOLVED 2026-08-01, see finding #2.
- **Public `agentos.mitechconsult.com` 503** — pre-existing, documented in ADR-0035:168; no Traefik
  dynamic route exists for the host. Out of scope here; noted so it is not re-diagnosed.
- **#3 Weaviate client-close race** — unchanged, upstream agno; still needs the agentos-api log
  check for `WeaviateClosedClientError` / gRPC UNAVAILABLE at UI-open times.
- **#5 ADR-0038 / graphiti-core** — unimplemented, now blocked on the image-rebuild decision.

## Pending owner decisions

- ~~**Split the colliding db ids**~~ — **DECIDED + APPLIED 2026-07-31**, option (a).
- **Deploy the #1 fix to prod** — WHAT: merge `fix/review-hardening-adr36-40` and redeploy the
  exec tier. WHY: the fix is committed locally only; prod is still broken. SHORTCOMING: the
  pre-deploy gate above (does the UI send `db_id`?) is unverified, so this should be a
  check-then-deploy, not a blind deploy.
- **Graphiti image rebuild** — WHAT/WHY/options in `docs/planning/graphiti-image-rebuild-plan.md`
  §8 and its "Open decisions for the owner". Three questions: approve the rebuild; enable GLiNER2
  (CPU-local NER, cheaper hot path, costs model download + memory); upstream-PR identity.
  RECOMMENDATION: approve the rebuild — it deletes two of four hotfixes and unblocks ADR-0038.
- **Case Bible scope** — WHAT: decide sort completion vs vault scaffold vs lakehouse vs all.
  WHY: workstream 3 cannot start without it. No recommendation — owner-only call.

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
