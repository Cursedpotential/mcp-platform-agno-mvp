# Migration Plan — Current Codebase → Handoff Guide v8.1 (+ companion files)

> **Purpose:** a reviewable, file-level plan to bring this repository in line with the v8.1 handoff
> and its companion artifacts. No code is changed by this document.
> **Authoritative inputs (newest wins):**
> - `Agno_MCP_Platform_MVP_Handoff_Guide_v8.1.md` — the spec (v8 + "agent-code reconciliation").
> - `Agno_MCP_Platform_FollowUp_Implementation_Guide.md` — §17 next steps: Router activation (already
>   built), Review Panel, Observability.
> - `agents_factory.py` + `agents_instructions.py` (workspace root) — **canonical reference
>   implementation** of the agent/team layer. Treat as drop-in targets, not designs to re-derive.
> - `v2_verification_and_repo_insights.md` — background (live-docs verification + repo adopt/adapt/skip);
>   no new architecture beyond what v8.1 already encodes.
> **Scope (locked by owner):** **Full v8.1** — MVP core **+ cloud (Drive/OneDrive)** **+ evals**
> **+ preserve the custom ChatMiner transcript-mining pipeline** **+ incorporate the existing n8n
> service and the Cloudflare R2 volume** (R2 doubles as the §17 blob landing zone).
> **Strategy (locked):** **fresh scaffold on the v8.1 layout; port the isolated custom assets in; drop
> in the reference `factory.py`/`instructions.py`.** Nearly every load-bearing decision in the current
> repo is the v1 pattern v8 corrects, so "patching" means rewriting the core anyway.

---

## What v8.1 changed vs v8 (so the earlier plan stays accurate)

v8.1 is a **surgical** update — only the agent/team layer:
1. **Two-layer Team topology (corrected):** top-level **Router `mode="route"`** (dispatch a request to
   exactly one family) over **family Teams `mode="coordinate"`** (leader delegates + synthesizes).
   v8 had described a single `TeamMode.coordinate` "routing agent" — v8.1 splits it correctly.
2. **§12 step 7 retargeted** to "build the constructors in `agents/factory.py`" — i.e. the reference
   file is now the source of truth for the topology.
3. Changelog/notes updated to cite `UserControlFlowTools` (structured-question intake) and the
   two-layer modes.

Everything else (AgentOS base_app, LearningMachine, Context Providers, PG18 dual-schema, provider
factory, evals, cloud) is unchanged from v8 — the v8 analysis below still applies in full.

---

## 0. TL;DR of the gap

Current repo = **v1-era app** (the thing §4 corrections target) + custom ChatMiner mining + a real
n8n/R2 stack. The companion files mean the *correct* agent layer is now **already written** and just
needs porting + wiring.

| v8.1 locked decision | Current state | Action |
|---|---|---|
| `AgentOS(base_app=app)` + `get_app()` | Plain FastAPI + manual `build_agent_team()`/`agent.arun()`; **no AgentOS** | Rewrite `app/main.py` |
| **Agent/team layer = reference `factory.py`** (route+coordinate, root router, native HITL) | Old flat 7-agent factory, raw `MCPTools`, no teams, no router | **Port the reference file**; re-add `transcript_miner` |
| **HITL = native confirmation** (`@tool(requires_confirmation=True)` → `continue_run`); `approval_request` = audit/display keyed by `run_id` | Custom REST approval state machine only; **no `run_id` capture**; `store_learned_knowledge()` present | Adopt native confirm; keep table as audit; **store `run_id`**; delete `store_learned_knowledge` |
| Native `LearningMachine`, no custom table | `learned_knowledge` table + `store_learned_knowledge()` | Delete both; add LearningMachine |
| Context Providers via a `ctx` object | Raw `MCPTools` attached directly | New `agents/providers.py`; assemble `ctx` in `app/main.py` |
| Provider factory, no hard default, pinned IDs | Defaults to `openai`/`gpt-4o`; stale `claude-sonnet-4-20250514` | Rewrite factory in `config/settings.py` |
| Custom **PG18** image, `uuidv7()`, evidence/analysis dual schema, `evidence_hash` BYTEA | `postgres:16`, `uuid_generate_v4()`, single schema | New `docker/postgres/Dockerfile`, split SQL |
| `Knowledge(vector_db=hybrid, contents_db=…)`, real `ainsert()` | Old `AgentKnowledge`, no hybrid; ingest is a **print-only stub** | Rewrite knowledge + ingest |
| **Routing agent** | Absent | Reference `build_root_router` exists → activate as entry point |
| Blob landing zone (§17) | **R2 volume already wired** | Adopt R2 as the §17 blob zone |
| Scaffold: `db/`, `providers.py`, `ingestion.py`, `drive_cleanup.py`, `memory/`, `evals/`, `docker/`, `pyproject.toml`, `compose.yaml` | None exist | Create |

**Three runtime bugs to fix during the port (current code doesn't fully import):**
1. `chatminer/__init__.py` → imports non-existent `chatminer.core.pipeline` → `import chatminer` raises.
2. `parsers/__init__.py` → imports non-existent `parsers.detector`/`.pipeline`/`.normalizer` → raises.
3. `chatminer/core/artifacts.py` → `ArtifactType.EVIDENCE_REFERENCE` not in the enum → `AttributeError`.

---

## 1. Agents & templates v8.1 defines (with the reference implementation mapped in)

### 1a. Roster + topology (§6, now reflected in `agents_factory.py`)

**Two-layer team structure (route over coordinate):**
```
Root Router  (mode="route")           → build_root_router(...)            key "router"
├── Platform Ops Team (coordinate)     → build_platform_ops_team(...)     key "platform_ops_team"
│   ├── Ingestion Orchestrator         key "ingestion_orchestrator"
│   ├── Analysis Orchestrator          key "analysis_orchestrator"
│   └── Review Gatekeeper              key "review_gatekeeper"
├── Builder Team (coordinate)          → build_builder_team(...)          key "builder_team"
│   ├── Dev Copilot (UserControlFlowTools intake)   key "dev_copilot"
│   ├── Project PAL (Session+User memory)           key "project_pal"
│   └── Forensic Data Agent (readonly DB tools)     key "forensic_data_agent"
└── Cloud Drive Cleanup Agent (standalone, write, trash-only)  key "cloud_drive_cleanup"
```
- **HITL is native:** `apply_db_modification` and `trash_cloud_file` are `@tool(requires_confirmation=True)`
  → the run **pauses** before the side effect; `continue_run(updated_tools=...)` approves/rejects. Real
  side effects live in the MCP servers / Context Providers; the tools are just the pause boundary.
- **Dev Copilot / Cleanup carry `UserControlFlowTools()`** — the structured-question intake (agent
  pauses mid-run to ask the owner) the builder flow was promised.
- **Forensic Data Agent gets `readonly_db_tools`** from `DatabaseContextProvider`'s read sub-agent
  (`readonly_engine → evidence`) — physically cannot write.

> **Custom-agent gap:** the reference `factory.py` has **no `transcript_miner`**. The ChatMiner agent
> must be re-added (key `transcript_miner`) — likely a standalone builder-adjacent agent that the
> `/v1/transcripts/mine` route invokes directly (it doesn't need to sit inside a coordinate team).

### 1b. Reference "templates" v8.1 is assembled from
`agentos-docker-template` (scaffold) · `dash` (dual-schema, read-only enforcement, evals, the Forensic
archetype) · `scout` (Context Providers, embed-vs-navigate) · `vibe-video` (route/coordinate teams,
numeric history) · `vibe-to-prd` (`UserControlFlowTools` intake, Non-Goals fence) · `semantica`
(platform-stage target). The Agno **docs MCP** (`https://docs.agno.com/mcp`) is itself usable as an
institutional-knowledge provider.

---

## 2. Target scaffold (full v8.1 + mining + cloud + evals + n8n/R2 + companion items)

```text
Agno-MCP-Platform/
├── .dockerignore                      # NEW
├── example.env                        # RENAME from .env.example; §10.3 vars + R2/n8n + cloud
├── compose.yaml                       # REPLACE docker-compose.yml — PG18 + agno-app + n8n + R2 [+ toolbox/falkordb later]
├── pyproject.toml                     # NEW — dependency source of truth
├── requirements.txt                   # REGENERATE via scripts/generate_requirements.sh
├── Dockerfile                         # REWRITE — built deps, no pip-at-startup, no reload
├── docker/postgres/
│   ├── Dockerfile                     # NEW — PG18 + PostGIS + pgvector + pg_textsearch
│   └── conf.d/10-pgss.conf            # NEW (deferred) — pg_stat_statements preload (Observability)
├── README.md / HANDOFF_INSTRUCTIONS.md / CLAUDE.md   # UPDATE / KEEP / NEW
├── app/
│   └── main.py                        # REWRITE — assemble `ctx`, build_agent_team(ctx), register router + routes; no reload
├── agents/
│   ├── factory.py                     # PORT the reference agents_factory.py (+ re-add transcript_miner)
│   ├── instructions.py               # PORT the reference agents_instructions.py
│   ├── ingestion.py                   # NEW — python -m agents.ingestion
│   ├── providers.py                   # NEW — Context Provider wiring (produces ctx.*_tools)
│   └── drive_cleanup.py               # (covered by factory's cleanup agent; keep wiring here if split)
├── db/__init__.py                     # NEW — get_postgres_db()
├── config/settings.py                 # REWRITE factory (no hard default, pinned IDs, cloud/toolbox/R2 env)
├── knowledge/platform/{conversations,docs,notes}/   # NEW
├── memory/README.md                   # NEW — LearningMachine usage (+ Graphiti later)
├── prompts/                           # KEEP
├── lib/chunking.py                    # KEEP/PORT
├── chatminer/                         # PORT (fix __init__ + artifacts enum)
├── scripts/{generate_requirements.sh, ingest_knowledge.py, mine_transcripts.py}
├── sql/
│   ├── 0001_init_extensions.sql       # NEW
│   ├── 0002_schema.sql                # NEW — uuidv7, evidence/analysis, evidence_hash, audit (+ run_id), transcript_insight
│   └── 0003_observability.sql         # NEW (deferred) — CREATE EXTENSION pg_stat_statements
├── evals/                             # NEW — accuracy/routing/governance/boundaries/safety
├── ui/review_schema.ts                # KEEP
└── ui/review_panel/                   # NEW (post-MVP) — thin panel over approval_request + continue_run
```

---

## 3. Asset disposition — every existing tracked file

Legend: **KEEP · PORT · REWRITE · PORT-REF (replace with the provided reference) · SPLIT/REPLACE · DELETE**

| File | Disposition | Notes |
|---|---|---|
| `agents/factory.py` | **PORT-REF** | Replace with workspace `agents_factory.py`; **re-add `transcript_miner`**; fix imports to repo layout |
| `agents/instructions.py` | **PORT-REF** | Replace with workspace `agents_instructions.py`; add transcript_miner text |
| `app/main.py` | **REWRITE** | Assemble `ctx` (model, db, knowledge, learning, source_tools, code_tools, readonly_db_tools, drive_read/write_tools); `build_agent_team(ctx)`; register **router** as entry point + `register_approval_routes`/`register_knowledge_routes`; **capture `run_id`** on pause; **drop `store_learned_knowledge`** + manual run loop |
| `config/settings.py` | **REWRITE (factory)** | No hard default; pinned `claude-opus-4-8`/`-sonnet-4-6`; PG18 URL, `TOOLBOX_URL`, Drive/OneDrive + R2 vars |
| `sql/schema.sql` | **SPLIT/REWRITE** | → `0001_init_extensions.sql` + `0002_schema.sql` (uuidv7, evidence/analysis, `evidence_hash` BYTEA, **add `run_id` to `agent_run`/`approval_request` for resume**). **Drop `learned_knowledge`.** Keep `agent_run`/`approval_request`/`transcript_insight` |
| `scripts/ingest_knowledge.py` | **REWRITE (load step)** | Keep scan/manifest/normalize; replace print-stub with real `knowledge.ainsert(name=, path=, metadata=)`; add `agents/ingestion.py` entrypoint |
| `scripts/mine_transcripts.py` | **KEEP/PORT** | Mining batch driver |
| `lib/chunking.py`, `lib/__init__.py` | **KEEP** | |
| `chatminer/**` | **PORT + FIX** | Fix `__init__` + `artifacts.EVIDENCE_REFERENCE` |
| `parsers/discovery.py`, `parsers/__init__.py` | **DELETE (consolidate)** | Superseded by `chatminer/parsers/` |
| `ui/review_schema.ts` | **KEEP** | Matches §8.1; the Review Panel binds to it |
| `prompts/**` | **KEEP** | Knowledge seed |
| `docker-compose.yml` | **REWRITE → `compose.yaml`** | Keep postgres/n8n/R2; postgres→PG18 custom image; replace pip-at-startup `agno-app` with built image |
| `Dockerfile` | **REWRITE** | Built deps; keep Node for TS MCP |
| `.env.example` | **RENAME → `example.env`** + expand | §10.3 + R2 + cloud |
| `requirements.txt` | **REGENERATE** | From `pyproject.toml` |
| `DEPLOYMENT_GUIDE.md` / `DEVELOPER_HANDOFF.md` | **REVIEW/ARCHIVE** | Describe v1 stack; reconcile to v8.1 |
| `tests/**` | **KEEP + EXPAND** | §13 matrix + `evals/` |

---

## 4. Staged migration plan (handoff §12 + companion items)

### Phase 1 — Settings + provider factory (§10.3/10.4, §12.1)
Files: `config/settings.py`, `example.env`, `pyproject.toml`, `scripts/generate_requirements.sh`.
Do: provider-agnostic factory, no hard default, pinned IDs; PG18 URL, `TOOLBOX_URL`, Drive/OneDrive,
**R2 (`R2_*`)**, n8n vars. Accept: credential-selection unit test; requirements regenerate.

### Phase 2 — Database (§8.1, §10.2, §12.2)
Files: `docker/postgres/Dockerfile`, `sql/0001_init_extensions.sql`, `sql/0002_schema.sql`, `db/__init__.py`.
Do: `uuidv7()` PKs; `evidence`(read-only)+`analysis` schemas; `evidence_hash` BYTEA; **add `run_id`
columns** to `agent_run`/`approval_request` (native-confirm resume key); drop `learned_knowledge`; keep
`transcript_insight`. n8n keeps its own DB/schema, isolated from evidence/analysis. Accept: image
builds; read-only conn rejects `evidence` writes; n8n connects.

### Phase 2b — Compose integration (n8n + R2 + agno-app + PG18)
Files: `compose.yaml`, `Dockerfile`. Do: one compose — `postgres`(PG18), `agno-app`(built image, no
pip-at-startup, **no reload**, 8000), `n8n`(depends_on postgres healthy), `r2_shared_cloud` mounted into
agno-app. R2 = §17 blob landing zone (S3-compatible). Accept: `docker compose up -d --build` green;
`/health` ok; R2 mounts rw.

### Phase 3 — Knowledge + ingestion (§7.1, §9.1, §12.3)
Files: `agents/ingestion.py`, `scripts/ingest_knowledge.py`. Do: `Knowledge(vector_db=PgVector(hybrid),
contents_db=PostgresDb(...))`; manifest/normalize then `knowledge.ainsert()` (paths local **or R2 URLs**);
embed frozen archives, navigate live sources (§9.1b). Accept: `python -m agents.ingestion` indexes
`knowledge/platform/**`; an agent answers a grounded question.

### Phase 4 — MCP connectivity (§7.2, §12.4)
Source the servers from **`dev-resources/Archives/MCP_PLATFORM/mcp-servers/`** (ts/py/js) — recommend
**vendoring** them into the repo under `mcp-servers/` for a self-contained image. One `MCPTools` per
TS/Py server, `refresh_connection=True`, `tool_name_prefix`; no manual connect/close inside AgentOS.
Accept: tool discovery lists TS+Py tools (mocked until vendored).

### Phase 4b — Context Providers (§3.3b/c/d/e, §12.4b) — produces the `ctx.*_tools`
Files: `agents/providers.py`. Build: `Workspace`(code → `ctx.code_tools`), `FilesystemContextProvider`
(docs), `DatabaseContextProvider(sql_engine=analysis, readonly_engine=evidence)` (→ `ctx.readonly_db_tools`),
`MCPContextProvider` over `MCPToolbox` (DB fleet → part of `ctx.source_tools`), per-account
`GoogleDriveContextProvider` (→ `ctx.drive_read_tools`), per-account OneDrive `MCPContextProvider`
(read), a custom **ChatLogs** provider wrapping ChatMiner (`query_chatlogs`). Accept: read sub-agents
cannot write; no tool-name collisions.

### Phase 4c — Cloud cleanup providers (§3.3d/e, §12.4c) — produces `ctx.drive_write_tools`
Third-party MCP servers per account (Drive: piotr-agier; OneDrive: MrFixit96) behind
`MCPContextProvider(include_tools=[trash-only set])`; **never** `delete_permanently`/`empty_trash`.
Accept: write set is trash-only; `trash` recoverable verified before real data.

### Phase 5 — Memory (LearningMachine) (§3.2, §7.1b, §12.5)
`learning=build_learning(...)`: `PROPOSE` for Entity + Learned Knowledge, `ALWAYS`/`AGENTIC` for
profile/session; `enable_clear_memories=False`; strong extraction model. Accept: stores persist; PROPOSE
surfaces a human-confirm.

### Phase 6 — Agents + teams (PORT the reference) (§6, §12.7)
Files: `agents/factory.py` (PORT-REF), `agents/instructions.py` (PORT-REF). Do: drop in the reference
constructors; **re-add `transcript_miner`**; wire native-confirm tools (`apply_db_modification`,
`trash_cloud_file`) to the real write engines after confirm. Accept: ops/builder coordinate teams +
standalone cleanup + root router instantiate; keys stable.

### Phase 6b — `app/main.py` runtime wiring (THE lynchpin — FollowUp "Open dependency")
Files: `app/main.py`. Do: build Context Providers → assemble **`ctx`** (model, db, knowledge, learning,
source_tools, code_tools, readonly_db_tools, drive_read_tools, drive_write_tools) → `build_agent_team(ctx)`
→ `AgentOS(base_app=app, on_route_conflict="preserve_base_app", scheduler=True, tracing=True)` →
register **`agents["router"]` as the primary entry point** + approval/knowledge/transcript routes →
`get_app()`; **never** subpath-mount; **never** reload with MCP attached. On a pause, persist the
`approval_request` row **with `run_id`** + paused-tool refs. Accept: an API request hits the router and
routes to the right family; a write pauses, is recorded with `run_id`, and resumes via `continue_run`.

### Phase 7 — Approval flow end-to-end (§8.2, §9.2, §12.6)
HITL is the native confirmation pause; `approval_request` is the audit/display record. Route DB
*modifications* through it. Accept: request → pause → recorded row → approve → `continue_run` → completes;
reject → reason lands in `confirmation_note`; read/write split holds.

### Phase 7m — ChatMiner integration (custom) — *mining track*
Fix `chatminer/__init__.py` (+ add `core/pipeline.py` or trim exports), fix `artifacts.EVIDENCE_REFERENCE`,
delete root `parsers/`. Port `/v1/transcripts/mine` + `/v1/transcripts/insights` into the registered
routes; the `transcript_miner` agent services them. Keep `transcript_insight`. Accept: `import chatminer`
ok; `python -m chatminer pipeline` runs; mine endpoint persists insights under AgentOS.

### Phase 8 — Evals (§13, §12.8) — *evals track*
`evals/` + `python -m evals --category`: accuracy, **routing (ReliabilityEval — the router dispatch
guard)**, governance + boundaries + safety. Accept: governance + boundaries + routing pass before any
write path is trusted.

### Phase 9 — Retrieval upgrade (optional, §10.5) — `pg_textsearch` BM25 + RRF only if hybrid insufficient.

### Phase 10 — Review Panel (FollowUp §2) — *post-MVP, makes HITL usable*
Files: `ui/review_panel/` + two routes (`GET /v1/approval-requests?status=pending`,
`POST /v1/approval-requests/{id}/decision`). Binds to `ui/review_schema.ts`. **Critical:** the decision
endpoint must resolve the *same* paused run via `continue_run(run_id, updated_tools=...)` — not a
parallel approval path. Accept: paused action appears in seconds; approve resumes+completes; reject reason
→ `confirmation_note`; state lives in Postgres (no browser storage).

### Phase 11 — Observability (FollowUp §1) — *post-MVP, only when tuning real load*
Files: `docker/postgres/conf.d/10-pgss.conf` (`shared_preload_libraries='pg_stat_statements'`),
`sql/0003_observability.sql` (`CREATE EXTENSION pg_stat_statements`). **Rebuild + restart**, not a live
change. Accept: `\dx` lists it; top-5 by total time / block reads identifiable.

> **Suggested companion-item order (FollowUp):** Router activation (Phase 6/6b — nearly free) → main.py
> wiring (6b, unblocks both) → Review Panel (10) → Observability (11, only when tuning).

---

## 5. Schema delta (concrete)
- Keep `agent_run`, `approval_request` → `uuidv7()` PKs; **add `run_id`** (+ paused-tool ref) for native-confirm resume.
- Add `evidence`+`analysis` schemas; `evidence_hash(... digest BYTEA, CHECK octet_length=32)` in `evidence`.
- Drop `learned_knowledge` (→ LearningMachine).
- Keep custom `transcript_insight`; consider moving under `analysis`.
- Isolate n8n's own DB/schema from evidence/analysis.
- Let Agno own its Knowledge `vector_db`/`contents_db` tables.
- `VECTOR(1536)` for `text-embedding-3-small`; changing embedder ⇒ re-embed.

---

## 6. Bug-fix appendix (fold into Phase 7m)
1. `chatminer/__init__.py` → add `chatminer/core/pipeline.py` (`parse_file/parse_multiple/parse_directory`) **or** trim exports.
2. Root `parsers/` → delete; consolidate on `chatminer/parsers/`.
3. `artifacts.EVIDENCE_REFERENCE` → add the enum member or map to an existing type.

---

## 7. Open decisions for the owner
1. **n8n + R2 — RESOLVED (owner):** both in scope; single `compose.yaml`; **R2 = §17 blob zone**.
2. **Router as entry point — RESOLVED (companion):** `build_root_router` exists; make `agents["router"]`
   the primary AgentOS entry point (Phase 6b). Decide the cross-family tie-break (current: prefer Builder).
3. **`transcript_miner` placement** — standalone agent serving `/v1/transcripts/mine` (recommended), or a
   member of a coordinate team? It's not in the reference factory and must be re-added either way.
4. **PG18 base image — RESOLVED (owner):** target **PG18** for native `uuidv7()`; if any of
   PostGIS/pgvector/pg_textsearch lacks a PG18 build at pin time, **fall back to PG17 + `pg_uuidv7`**
   and note it. No blocking on PG18.
5. **MCP servers — RESOLVED (located):** the TS/Py/JS servers exist at
   **`dev-resources/Archives/MCP_PLATFORM/mcp-servers/`** (`ts-mcp-server`, `py-mcp-server`,
   `js-mcp-server` + AGENTS.md/INDEX.md/TODO.md/memory) — the canonical modular iteration. A second
   iteration is at `dev-resources/Archives/dial-stack/mcp-servers/` (same 3 servers, no docs).
   *Sub-decision (owner, at Phase 4):* **vendor** the MCP_PLATFORM servers into this repo under
   `mcp-servers/` (clean `TS_MCP_COMMAND`/`PY_MCP_COMMAND` relative paths, self-contained image) vs.
   **point commands at the dev-resources path** (no copy, but couples the build to that location).
   *Recommend vendoring* the MCP_PLATFORM iteration so the container is self-contained. Until then
   Phase 4 can run mocked.
6. **Cloud accounts — RESOLVED (owner):** **both Google *and* OneDrive, multi-account.** So Phase 4b
   builds **one `GoogleDriveContextProvider` per Google account** *and* **one OneDrive
   `MCPContextProvider` per Microsoft account** (read), and Phase 4c gives the Cleanup Agent
   write-filtered (trash-only) providers for both. Still needed: exact account count + service-account
   vs OAuth per account (env fan-out: `GOOGLE_SA_FILE_*`, `MICROSOFT_CLIENT_ID`/`ONEDRIVE_MCP_URL_*`).
7. **n8n role** — driver (calls `/v1/...`), consumer, or both? If a driver, consider
   `enable_mcp_server=True` so n8n/coding agents can call agents as MCP tools.
8. **R2 layout** — bucket/prefix convention (raw evidence vs derived vs knowledge archives) for
   provenance-friendly Semantica ingest later.
9. **Old guides** — archive/update `DEPLOYMENT_GUIDE.md` / `DEVELOPER_HANDOFF.md` (v1 stack).

---

## 8. What carries forward unchanged (value already here)
- **Reference `agents_factory.py` + `agents_instructions.py`** — drop-in agent layer (de-risks Phase 6).
- **ChatMiner parser suite** (10 parsers) + segmenters + CLI — clean, isolated.
- **`lib/chunking.py`** smart chunker.
- **`ui/review_schema.ts`** + `agent_run`/`approval_request` tables — already v8.1-aligned (Review Panel reuses the schema).
- **`ingest_knowledge.py`** scan/manifest/normalize logic (needs the real `ainsert`).
- **n8n + Cloudflare R2** — already running; adopted (R2 as blob zone).
- **`prompts/platform_context/*`** — Knowledge seed.
```
