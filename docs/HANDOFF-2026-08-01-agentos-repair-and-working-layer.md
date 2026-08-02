# HANDOFF — AgentOS repair, ovh-data retirement, and the WORKING layer (2026-08-01)

> _Byline: Claude Code · Opus 5 (1M) · 2026-08-01_
STATUS: PARTIAL
BUILD_STATUS: PASS (464 passed / 3 skipped / 0 failed at prod's pinned agno 2.8.0; ruff clean)

Supersedes the open items in `HANDOFF-2026-07-30-current-tasklist.md` and
`HANDOFF-2026-07-30-memory-knowledge-audit.md` (both updated in place today).

---

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| **Branch / remote** | `main` @ `4eb25e7`, local == origin. 12+ commits pushed today. Use `git push origin main` — pushing `HEAD:main` all day left local `main` 65 commits stale and a `git checkout main` surfaced pre-agno-2.8 files, which looked like a catastrophic revert and was not. |
| **AgentOS live** | tailnet `http://100.72.169.40:8000`, bearer `OS_SECURITY_KEY` (also set as a User env var). `/config` 200 · **6 agents, 3 teams** · `/memories` 200 · `/sessions` 200 · `/traces` 200 · `/knowledge/search` 200 with real text · `/workflows` **`[]`**. |
| **Public endpoint** | `https://agentos.mitechconsult.com` = **503, pre-existing** (ADR-0035:168, no Traefik dynamic route). Not a regression. Owner's path is the tailnet tunnel. |
| **Weaviate** | ovh-data `:8081` REST / `:50051` gRPC. `Platform_knowledge` **59 objects / 5 docs**. Schema types matter: `meta_data` is **text** (JSON string), `filters` is **object** (dict) — mixing them is a hard 422. |
| **Milvus** | **Moved to ovh-files** `100.91.190.107:19530`, Coolify app `d725i1io2o1dwlfjdz09lo87`, **healthy, restarts=0**. ovh-data's copy is stopped. |
| **Neo4j / Graphiti** | Case lane `100.91.190.107:8073`, db `memory`, image `ghcr.io/cursedpotential/graphiti-mcp@sha256:fc64fd33…`, patch confirmed live. `memory` db = 4 episodic, `neo4j` (dev lane) = 27, `evidence` = 0. |
| **Postgres 18.1** | Native `uuidv7()` available. Schemas: `ai`, `analysis`, `evidence`, `duckdb`, `public`. **`evidence.raw_sms` = 14,107 rows; `analysis.message`/`conversation` = 0.** `evidence.raw_ai_chat` exists and is empty. `analysis.human_label`/`human_label_gold` = 1,918 each. |
| **Coolify** | API `http://100.98.98.38:8000/api/v1` (tailnet). SSH `debian@100.98.98.38`, **passwordless sudo**. exec-tier app `rz41wqhpjfh1rj796ixvjhfs` deploys from `main`. **All 15 `main`-tracking apps now have watch paths** (portkey + coolify-mcp were unscoped and bounced on every push). |
| **Auto-deploy** | **Works** — proven by test commit `3dc9172` deploying itself with no manual trigger. Owner's GitHub App re-sync fixed it. |
| **Providers (live-verified)** | Ollama Cloud **18 models** (glm-5.1 OK) · NVIDIA NIM **102 models** (91 chat / 11 embed, `nv-embed-v1` 4096-d OK) · Anthropic 11 models via `CLAUDE_CODE_OAUTH_TOKEN` → `ANTHROPIC_AUTH_TOKEN`. **No `ANTHROPIC_API_KEY` exists anywhere.** **OpenRouter is 402 out of credits — never route through it.** |
| **memsearch** | Repointed to the new Milvus. Collection `agent_session_memory`. Embedder switched `onnx` → `google` / `gemini-embedding-001` (**3072-d, verified 200**). `google-genai` injected into its uv tool env. **Index is empty — it has never successfully indexed.** |
| **Local venv trap** | Drifts to agno **2.8.6** on any plain `uv run`. Prod pins **2.8.0**. Always `uv run --no-sync`. |

---

## Findings / work done

### The AgentOS chain — eight bugs, each masking the next (all fixed, all deployed)

1. **DB-id collision** (`9a7e4ac`) — SurrealDb and PostgresDb shared `id="agentos-db"`; agno keys its registry by `db.id` and its resolver counts KEYS, so memory/session/knowledge routes resolved by registration-order lottery. Live `/config` showed `databases:["agentos-db"]` (1 key). **This was the original "broken on first open".**
2. **Missing transitive deps** (`e999dd2`) — `requirements.txt` pinned `weaviate-client` but not `validators` / `authlib` / `joserfc`. `session.py` imports Weaviate at module scope, so prod **crash-looped, 11 restarts**. agno masked the real `ModuleNotFoundError: validators` as *"Weaviate is not installed"*.
3. **Middleware matched ZERO routes** (`a930114`) — the `db_id` guard scanned `app.routes` for `APIRoute`, but under `base_app=` agno's routes are `_IncludedRouter` objects one level down. Live topology: 17 APIRoute + 21 _IncludedRouter + 1 Mount. All 48 `db_id` routes were hidden. **The test built a simplified app and passed while prod 400'd.**
4. **`fetch_objects(where=)`** (`3e3813d`) — agno 2.8.0 uses the v3 kwarg; weaviate-client 4.22.0 wants `filters=`. Runs AFTER the write, so it aborted reindex on file 1.
5. **Async client → `localhost:8080`** (`5483d76`) — **the root cause of "knowledge never populates"**. `Weaviate.__init__` has no `async_client` param and `get_async_client()` falls back to `use_async_with_local()`. Ingest is fully async, search is sync — so every probe passed and only WRITES failed, silently.
6. **`meta_data` dict vs text** (`9bc142f`) — 422.
7. **`filters` object vs text** (`a3d897f`) — fix #6 serialized both and broke `filters`. Read the live schema instead of assuming.
8. **Search results missing `id`** (`3ec7d90`) — `Weaviate.get_search_results()` never sets `Document.id` while `VectorSearchResult` requires `id: str`, so `POST /knowledge/search` **500'd on every call**. Could only surface after #5–#7 because search is unreachable on an empty index.

**Result:** memory capture proven (3 real rows from a live agent run), knowledge search returns real text, Weaviate went 7 → 59 objects, `ingest_all` returns `INGEST OK, files: 4`.

### Knowledge/embedder fixes

- **Embedder was routed to OpenRouter** for `nvidia/nv-embed-v1`, which OpenRouter does not host (400), and that key is also 402. Now routes text → NVIDIA NIM, code → OpenRouter. `scripts/verify_nvidia_provider.py` proves the key live.
- **`VerifiedWeaviate`** (`server/core/knowledge_vectordb.py`) — agno silently skips docs whose embedding is None and still marks content `COMPLETED`. It now raises so a dead embedder reports `FAILED`. **That guard is what made bug #5 findable.**

### Infrastructure

- **ovh-data → ovh-files migration**: hot logical backups (pg_dumpall 12 MB / SurrealDB 5 tables / Weaviate 59 objects **with vectors**) verified on `E:` **and** B2 (`rclone check` 0 differences). Cold copies `data-neo4j.tar.gz` (290 entries, 1,047 MB, gzip OK) and `data-vector.tar.gz` (1,093 entries, 378 MB). Neo4j `neo4j` db 506 = 506 exact match. **6 corrupt Milvus dirs (1,536 MB) deliberately left behind per owner.**
- **Milvus etcd was corrupt in the DATA, not the host** — panicked identically on both boxes (`etcdserver: leader changed`, term 462). Quarantined 385 MB of etcd to `/data/agno/_quarantine/milvus-etcd-corrupt-20260801` (**moved, never deleted**); Milvus came up clean in 40s.
- **Blast radius closed** — `portkey` and `coolify-mcp` had no watch paths and redeployed on every push to `main`. Both scoped; all 15 apps now covered.

### memsearch — root-caused

Never indexed because `provider = "onnx"` (runs the model **locally**) with `model = "nvidia/nv-embed-v1"`, a **gated HuggingFace repo** → 401. The `base_url` pointing at NIM was unused. Owner: *"onnx was never supposed to be a thing."* Now on Gemini. Free tier (100 embed req/min) is acceptable per owner; needs batching (`batch_size` is 4).

### Graphiti — NOT broken

A subagent reported a write-persistence bug. **Disproven by controlled probe**: baseline 3 episodic nodes → wrote one → polled → `t=120s: 4`. Both of the agent's earlier episodes were in the graph all along. Commit latency is ~2 min (one log line recorded `Completed add_episode in 67507ms`); the agent checked at 60–90s. **Lesson: baseline → act → poll past the known worst case.**

---

## UNRESOLVED (mandatory)

- **Workflow registration is BUILT BUT UNCOMMITTED** — `server/api/workflow_registry.py` (161 lines), `tests/test_workflow_registry.py` (118 lines, **8/8 passing** incl. end-to-end registration under the real `base_app=` topology), and the `workflows=registered_workflows(db, knowledge)` kwarg in `main.py`. WHY unfinished: owner called the session at 100% context. SHORTCOMING of leaving it: `/workflows` stays `[]`. There is also a leftover `git stash` entry (`wf-registry-wip`) that can be dropped once the work is committed.
- **`sql/0008_working_schema.sql` is WRITTEN BUT NEVER VALIDATED** — the apply-in-transaction-then-ROLLBACK check was interrupted before running. **Do not apply it until that check passes.** It is additive (new `working` schema only, touches nothing existing).
- **agno 2.8.6 breaks the platform** — `providers.py:254` passes `EntityMemoryConfig(mode=LearningMode.PROPOSE)`; 2.8.6 added a `__post_init__` guard rejecting anything but `AGENTIC`, so `import server.api.main` fails. 2.8.0 has no guard. **Corollary: the entity-memory HITL has never actually worked** — 2.8.0 accepted PROPOSE and silently did nothing, because there is no extraction pass. Fix is one line (`AGENTIC`), but the HITL it implied must come from elsewhere.
- **`learned_knowledge` also uses `PROPOSE`** (`providers.py:256`) and is NOT guarded — **unverified** whether that mode genuinely functions there.
- **`agno_memories` never wired** into chat ingest. Scoped approach: `MemoryManager(model=…, db=get_agno_db()).acreate_user_memories(...)` — a direct API needing no fake agent turn.
- **No HITL on the AI-chat context lane** — the pipeline is fully automatic. The platform's existing gates (`mode='supervised'` in `server/evidence/workflows.py:226-308`; `@tool(requires_confirmation=True)`) are not applied to it.
- **`/app/knowledge/legal/` never indexed** — holds the coercive-control classification rubrics, but `ingest_all` only walks `/app/knowledge/platform`. **Agents cannot retrieve your rubrics.** One-line fix, high value.
- **memsearch index still empty** — config is fixed; a throttled reindex has not been run.
- **`GRAPHITI_MCP_URL` points at the DEV lane** (`:8071`, db `neo4j`), not the case lane. Agent-decided memories go to the wrong graph. Owner explicitly deferred wiring the case lane into `providers.py`.
- **`build_chat_transcript_workflow` populates only 4 of 6 outputs** — custody → parse → `analysis.normalized_record` → knowledge. **No entities, no timeline, no `agno_memories`, no artifacts.**
- **OpenAI key exposed** — a subagent's masking regex covered only `sk-ant-` and missed an `sk-svcacct-` key, which appeared in its tool output. **Owner declined rotation.** Also: `~/.secrets/MASTER_ENV_COMPILED_20260801.env.md` stores keys in plaintext.
- **ovh-data not retired** — `data-pg`, `data-surreal`, `data-weaviate` still live there and were never stopped. Milvus moved; nothing else has.
- **Today's fixes are deployed; the uncommitted workflow work is not.**

---

## Pending owner decisions

- **Commit + deploy the workflow registration** — WHAT: commit `workflow_registry.py` + tests + the `main.py` kwarg, then redeploy. WHY: `/workflows` is empty and the Studio panel has nothing in it; the workflows have existed for months, unreachable. APPROACH: `WorkflowFactory` (not plain `Workflow`) because the builders close over a per-request path; agno invokes the factory per request with validated input. SHORTCOMING: touches `main.py`, the boot path that crash-looped once today — mitigated because `registered_workflows()` catches everything and returns `[]` rather than raising. RECOMMENDATION: commit and deploy.
- **The `working` layer (new architecture, owner-designed 2026-08-01)** — WHAT: `raw → working → gated evidence`, with a human gate at the promotion boundary. `sql/0008_working_schema.sql` implements the middle: `extraction_run`, `candidate_entity`, `candidate_fact`, `candidate_event` (with `tstzrange` validity + GiST), append-only `review_decision`, and a `promotion` ledger covering onward fan-out to SurrealDB / Semantica / Graphiti / Weaviate. CHECK constraints make `promoted_at IS NULL OR review_state = 'approved'` structurally enforced. SHORTCOMING: **unvalidated against the live DB.** RECOMMENDATION: run the transaction-rollback check, then apply.
- **As-it-happened vs hindsight analysis (owner, end of session — NOT yet designed)** — WHAT: even inside the gated evidence side there are **two distinct passes**: (a) the *contemporaneous* record, strictly as it happened, with no hindsight; and (b) the *hindsight* analysis carrying the human experience — manipulation, lies, deceit, what really happened. WHY it matters: the court needs the defensible contemporaneous record, but the truth of a coercive-control pattern is only visible retrospectively. Mixing them contaminates the factual record; omitting the second loses the case's actual substance. APPROACH not yet chosen. SHORTCOMING of leaving it: the current `analysis.*` schema has no way to express which pass a row belongs to, and hindsight interpretation has nowhere to live that cites the contemporaneous facts. **This is the next design conversation.**
- **Agent access to case memory** — read-only for casework agents (`review_gatekeeper`, `forensic_data_agent`, `analysis_orchestrator`) vs none yet. Owner deferred; agent instructed not to touch `providers.py`.
- **Claude Code agent (`agno.agents.claude.ClaudeAgent`)** — verified to EXIST in prod's pinned 2.8.0, factory built at `server/agents/claude_code_agent.py`, **deliberately not mounted**. Open compliance question: Anthropic's SDK docs discourage powering third-party products off a subscription OAuth token rather than an API key, and that token is all the platform has.

---

## Next steps (work in order)

1. **Commit the workflow registration** (`workflow_registry.py` + tests + `main.py` kwarg); drop the `wf-registry-wip` stash. Verify `uv run --no-sync pytest -q` still passes, then deploy and confirm `/workflows` lists `chat-transcript` and `sms-xml`.
2. **Validate `sql/0008_working_schema.sql`** — apply inside a transaction, inspect `information_schema.tables WHERE table_schema='working'`, then ROLLBACK. Only apply for real once that passes.
3. **Design the as-it-happened vs hindsight split** with the owner before writing more schema. This is the load-bearing decision for the evidence side.
4. **Fix `EntityMemoryConfig(mode=…)` → `AGENTIC`** so an agno upgrade stops being a boot-blocker; verify whether `learned_knowledge`'s `PROPOSE` actually functions.
5. **Index `/app/knowledge/legal/`** so the coercive-control rubrics are retrievable — smallest change with the largest analytical payoff.
6. **Wire `agno_memories`** into the chat lane via `MemoryManager.acreate_user_memories`.
7. **Throttled memsearch reindex** on Gemini (raise `batch_size` from 4; free tier is 100 req/min).
8. **Extend `build_chat_transcript_workflow`** to the missing outputs (entities / timeline / memories / artifacts), reusing the existing `mode='supervised'` gate rather than building a new HITL.
9. **Finish ovh-data retirement** — `data-pg`, `data-surreal`, `data-weaviate` still to move.

---

## Standing lessons earned today (carry these forward)

- **Success signals lie.** A `200` from `/v1/knowledge/reindex` that wrote nothing; agno reporting *"Weaviate is not installed"* for a missing transitive dep; *"Completed add_episode"* for a write that was merely slow. **Read the underlying traceback and measure the end state — never the wrapper's text.**
- **Test the REAL topology.** A guard verified against a simplified app is not verified. The `db_id` middleware shipped green tests straight into a silent production failure because the test never used `base_app=`.
- **Sync-working ≠ async-working.** Bug #5 hid for weeks because every manual probe used the sync path.
- **Baseline → act → poll past the known worst case.** 67s extraction meant a 60s check reported "silently dropped" for a write that succeeded.
- **Never compare against a stash you did not confirm.** A silently-failed `git stash` had me comparing my code against my code and reporting a false conclusion.
- **AI chats are KNOWLEDGE, not EVIDENCE.** They must never enter `analysis.conversation`/`message` — those carry `exhibit_number`, `sender_e164`, custody lineage. Owner correction; I had it backwards once and retracted before it landed.
- **Don't compare `get_collection_stats()['row_count']` against another store** — it counts soft-deleted rows (reported 14 vs 7 real). Walk the collection.

---

## Owner working-style contract

- Structured replies: bullets, labeled blocks, white space, answer-first (ADHD; hyperfocus flow mode active this session).
- Confirm before changes; never hard-delete (quarantine); byline every artifact; **verify before claiming done**.
- Doc drift is the enemy: when reality changes, update every doc asserting the old reality in the SAME turn; strike through superseded claims rather than deleting them.
- Search past sessions before executing a topic — it repeatedly surfaced work already done that the docs denied.
