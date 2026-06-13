# Build TODO — agno-mvp (v8.1, container-first)

> **⚠️ STATUS (2026-06-11): Phases 1–9 are DONE; stack live on the VPS.** Current state, vision,
> and the active round live in [`../PROJECT_CANON.md`](../PROJECT_CANON.md) and the active plan
> [`../../plans/logical-herding-forest.md`](../../plans/logical-herding-forest.md). Decisions since
> v8.1: ADRs 0013–0021 (pg_duckdb, Neo4j/Graphiti, LiteLLM/Ollama-primary, container consolidation,
> polyglot evidence mesh, bitemporal memory, 3rd agent family, multi-domain knowledge, no-stub conventions).
> This file is retained as build history.
>
> **Read order for any agent:** `Agno_MCP_Platform_MVP_Handoff_Guide_v8.1.md` (source of truth) →
> `Agno_MCP_Platform_FollowUp_Implementation_Guide.md` (roadmap) → this file. Ignore v2–v8 (superseded).
> **Containerized:** Agno runs **only inside the `agno-app` image (python:3.11)** — never on the host
> (host is Python 3.14, no agno; that's expected). Dev loop = `docker compose up -d --build`, verify in
> the container, not via a host venv.
> **Verify Agno symbols against the running image**, not the handoff snapshot. Already verified vs live
> docs (see `VERIFIED_AGNO_API.md`): `MCPContextProvider`, `WorkspaceContextProvider`, `MCPToolbox`,
> `LearningMachine`, AgentOS `base_app`/`on_route_conflict` all real. Re-confirm once a version is pinned.

---

## Reconciliation model (skeleton vs reference)
- **KEEP from the skeleton** (proven, runnable Agno template): `db/` (`get_postgres_db`, `create_knowledge`,
  `db_url`), AgentOS `get_app()` pattern, `app/config.yaml`, `compose.yaml`, `Dockerfile`, `evals/`
  harness, `scripts/` (`generate_requirements.sh`, `entrypoint.sh`, etc.), `pyproject.toml`.
- **REPLACE with the reference topology**: `agents/factory.py` + `agents/instructions.py` (already
  copied in) — teams (`route`+`coordinate`), root router, native HITL tools, `ctx`-injected providers +
  LearningMachine. The skeleton's flat per-agent modules + `agents/__init__.py` are **superseded**.
- **ADAPT**: `app/settings.py` (skeleton defaults to NVIDIA NIM → make provider-agnostic, **no hard
  default**, pin Anthropic `claude-opus-4-8`/`claude-sonnet-4-6` per handoff §10.4).
- **WRITE NEW**: `agents/providers.py` (build the Context Providers → `ctx.*_tools`), `app/main.py`
  (assemble `ctx`, `build_agent_team(ctx)`, register router + custom routes on AgentOS `base_app`).

---

## Phase 0 — Decisions to lock (no code)
- [ ] **D1 Settings home:** follow skeleton (`app/settings.py` + `db/url.py`) vs handoff (`config/settings.py`
      "only place os.getenv"). *Proposed:* keep skeleton layout, centralize env reads in `app/settings.py`.
- [ ] **D2 transcript_miner placement:** standalone agent serving `/v1/transcripts/mine` (not in a
      coordinate team). *Proposed: yes.*
- [ ] **D3 MCP servers:** vendor `dev-resources/Archives/MCP_PLATFORM/mcp-servers` into `agno-mvp/mcp-servers/`
      (self-contained image) vs reference external path. *Proposed: vendor.*
- [ ] **D4 PG18 vs PG17:** target PG18 (`uuidv7()`); fall back to PG17 + `pg_uuidv7` if extension builds
      missing. *(owner: confirmed fall-back OK.)*
- [ ] **D5 Cloud accounts:** counts + service-account vs OAuth per Google/Microsoft account (needed at Phase 7).
- [ ] **D6 n8n role:** driver (calls `/v1/...`), consumer, or both → whether to set `enable_mcp_server=True`.
- [ ] **D7 Model provider for the MVP runtime:** Anthropic (pinned) vs the skeleton's NVIDIA/OpenRouter
      default vs OpenAI (embeddings still need OpenAI key for `text-embedding-3-small`).

---

## Phase 1 — Pin deps + settings + provider factory  (handoff §10.3/10.4)
- [ ] Pin Agno + stack in `pyproject.toml` (agno, fastapi, sqlalchemy[asyncio], asyncpg/psycopg, pgvector,
      pydantic-settings, mcp, openai-embedder dep, etc.); regenerate `requirements.txt` via `scripts/generate_requirements.sh`.
- [ ] Rewrite `app/settings.py`: provider-agnostic factory, **no hard default**, pinned IDs
      (`claude-opus-4-8` / `claude-sonnet-4-6`); env for PG, `TOOLBOX_URL`, Drive/OneDrive, **R2 (`R2_*`)**, n8n.
- [ ] Expand `example.env` to the full §10.3 set + R2 + cloud + n8n.
- [ ] **Verify (container):** `docker compose build agno-app` succeeds; `python -c "import agno; print(agno.__version__)"` in the image.
- [ ] **Verify (eval):** unit test for provider selection + pinned IDs.

## Phase 2 — Database: PG18 image + dual schema  (handoff §8.1/§10.2)
- [ ] `docker/postgres/Dockerfile`: PG18 + PostGIS + pgvector + pg_textsearch (fallback PG17+pg_uuidv7).
- [ ] `sql/0001_init_extensions.sql` (vector, postgis, pg_trgm, pgcrypto, btree_gin/gist, unaccent).
- [ ] `sql/0002_schema.sql`: `uuidv7()` PKs; `evidence`(read-only)+`analysis` schemas; `evidence_hash` BYTEA
      (`CHECK octet_length=32`); `agent_run`+`approval_request` (**add `run_id` + paused-tool ref** for
      native-confirm resume); `transcript_insight` (ChatMiner). **No `learned_knowledge` table** (→ LearningMachine).
- [ ] Confirm `db/url.py`/`db/session.py` point at the PG18 service; n8n keeps its own DB isolated.
- [ ] **Verify:** extensions+schema apply on first boot; a `default_transaction_read_only=on` conn rejects `evidence` writes.

## Phase 3 — Compose: PG18 + agno-app + n8n + R2  (handoff §10.1, owner: n8n+R2 in scope)
- [ ] Merge into one `compose.yaml`: `postgres`(PG18 custom image), `agno-app`(built image, **no pip-at-startup, no reload**),
      `n8n`(depends_on postgres healthy), `r2_shared_cloud` rclone volume mounted in agno-app. R2 = §17 blob landing zone.
- [ ] **Verify:** `docker compose up -d --build` → all healthy; `/health` 200; R2 mounts rw.

## Phase 4 — Context Providers → `ctx.*_tools`  (handoff §3.3b–e; VERIFIED imports)
- [ ] `agents/providers.py`: build and return tool lists the reference `ctx` expects:
  - [ ] `WorkspaceContextProvider` (codebase) → `ctx.code_tools`
  - [ ] `DatabaseContextProvider(sql_engine=analysis, readonly_engine=evidence)` → `ctx.readonly_db_tools` (+ write path)
  - [ ] `MCPContextProvider` over `MCPToolbox` (DB fleet) → part of `ctx.source_tools`
  - [ ] per-account `GoogleDriveContextProvider` (read) → `ctx.drive_read_tools`
  - [ ] per-account OneDrive `MCPContextProvider` (read)
  - [ ] custom **ChatLogs** provider wrapping ChatMiner → `query_chatlogs`
- [ ] **Verify (container):** providers import; read sub-agents cannot write; no tool-name collisions.

## Phase 5 — Memory: LearningMachine  (handoff §3.2/§7.1b)
- [ ] Confirm exact import (`agno.learn` vs `agno.learning`) + `LearningMode` against the image.
- [ ] `build_learning(...)`: stores with modes — Profile/Session `ALWAYS`/`AGENTIC`, Entity + Learned Knowledge
      `PROPOSE` (HITL); consider the **Decision Log** store for the approval audit trail; `enable_clear_memories=False`.
- [ ] **Verify:** stores persist on Postgres; a PROPOSE capture surfaces a human-confirm.

## Phase 6 — ⭐ `app/main.py` wiring (the spine — "build this first")  (FollowUp "Open dependency")
- [ ] Build Context Providers → assemble **`ctx`** (model, db, knowledge, learning, source_tools, code_tools,
      readonly_db_tools, drive_read_tools, drive_write_tools) → `build_agent_team(ctx)`.
- [ ] `AgentOS(base_app=fastapi_app, on_route_conflict="preserve_base_app", scheduler=True, tracing=True,
      db=get_postgres_db(), lifespan=...)` → `get_app()`. **Register `agents["router"]` as the primary entry point.**
- [ ] `register_approval_routes(app)` + `register_knowledge_routes(app)` + transcript routes; on pause persist
      `approval_request` **with `run_id`**. Never subpath-mount; never reload with MCP attached.
- [ ] Reconcile/remove skeleton's flat `agents/__init__.py` + per-agent modules (keep `transcript_miner` for re-add).
- [ ] **Verify (container):** service boots; a request hits the router and routes to the right family.

## Phase 7 — MCP connectivity + tool servers  (handoff §7.2)
- [ ] Vendor `MCP_PLATFORM/mcp-servers` (ts/py/js) into `agno-mvp/mcp-servers/`; set `TS_MCP_COMMAND`/`PY_MCP_COMMAND`.
- [ ] One `MCPTools` per server, `refresh_connection=True`, `tool_name_prefix`; AgentOS manages lifecycle.
- [ ] **Verify:** tool discovery lists the TS + Py tools (AdminTools/DuckDbVault/.../document_intelligence/...).

## Phase 8 — Approval flow end-to-end (native HITL)  (handoff §9.2)
- [ ] Wire `apply_db_modification` / `trash_cloud_file` (`requires_confirmation`) to the real write engines after confirm.
- [ ] **Verify:** request → pause → `approval_request` row (with `run_id`) → approve via `continue_run` → completes;
      reject → reason in `confirmation_note`; DB read/write split holds.

## Phase 9 — Knowledge + ingestion  (handoff §7.1/§9.1)
- [ ] `Knowledge(vector_db=PgVector(SearchType.hybrid), contents_db=PostgresDb(...))` via `db/session.create_knowledge`.
- [ ] `scripts/ingest_knowledge.py` + `python -m agents.ingestion`: manifest/normalize → `knowledge.ainsert(name,path,metadata)`
      (paths local or R2 URLs). Embed frozen archives; navigate live sources. **Never ingest `Secrets/`.**
- [ ] **Verify:** ingest indexes `knowledge/platform/**`; an agent answers a grounded question.

## Phase 10 — ChatMiner integration (custom)
- [ ] Review old `Agno-MCP-Platform/chatminer/` parsers; port the good ones into `agno-mvp/` (fix the 3 bugs:
      `chatminer/__init__` missing `core.pipeline`; root `parsers/` broken; `artifacts.EVIDENCE_REFERENCE` enum).
- [ ] Backfill gaps from `OTHER_RESOURCES_TO_SORT` ancestors; dedupe. Port `lib/chunking.py`.
- [ ] `/v1/transcripts/mine` + `/v1/transcripts/insights` routes; `transcript_miner` services them; keep `transcript_insight`.
- [ ] **Verify:** `import chatminer` clean; mine endpoint persists insights.

## Phase 11 — Cloud cleanup agent (Drive + OneDrive, multi-account)  (handoff §3.3d/e)
- [ ] Stand up third-party MCP servers per account (Drive: piotr-agier; OneDrive: MrFixit96) behind
      `MCPContextProvider(include_tools=[trash-only])`; **never** `delete_permanently`/`empty_trash`.
- [ ] Dry-run → approve-plan → auto move/rename + per-item trash confirm (reference `build_cloud_drive_cleanup_agent`).
- [ ] **Verify:** plan phase read-only; trash recoverable before real data.

## Phase 12 — Evals (first-class)  (handoff §13)
- [ ] Extend skeleton `evals/`: accuracy, **routing (ReliabilityEval — router dispatch guard)**, governance,
      boundaries, safety. `python -m evals --category`.
- [ ] **Verify:** governance + boundaries + routing pass before trusting any write path.

## Phase 13 — Companion roadmap (post-MVP, FollowUp guide)
- [ ] **Router activation** — already built (`build_root_router`); just make it the entry point (Phase 6) + routing eval.
- [ ] **Review Panel** — UI over `approval_request`; decision endpoint must resume via `continue_run(run_id)` (no parallel path).
- [ ] **Observability** — `pg_stat_statements` preload conf + `sql/0003_observability.sql` (rebuild, not live).

---

## Definition of Done (a phase is NOT done until ALL hold)
A phase task (#1–#14) may only be marked complete when:
1. **Code in place** in `agno-mvp/` (not the old repo), committed when the owner approves.
2. **Builds containerized** — `docker compose build` (and `up` where relevant) succeeds; verified
   **inside the image**, never a host venv.
3. **Phase verify passes** — the phase's "Verify" bullet(s) demonstrably pass (boot, route, read-only
   reject, ingest answer, etc.), with the evidence stated in plain text (the extractor can't see tool output).
4. **Eval/test green** — the relevant test or eval category passes (esp. governance/boundaries/routing
   before any write path is trusted).
5. **Decisions recorded** — any new architecture/dependency/boundary/HITL decision has an ADR in
   `docs/adr/`; any new term is in `docs/glossary.md`.
6. **Orientation updated** — `AGENTS.md` (and the relevant nested one) + the task tracker reflect the new state.
7. **Agno symbols re-verified** against the pinned image when the phase introduces a new Agno class.

> Skipping a step is allowed only with an explicit owner waiver, logged in the phase task.

## Cross-cutting guardrails (every phase)
- Containerized: verify inside the image; no host venv. No `reload` with MCP attached. No subpath-mount.
- `Secrets/` and case-data dirs: never ingested. Old `Agno-MCP-Platform/` repo: never built on.
- Embedder dim contract: `VECTOR(1536)` ↔ `text-embedding-3-small`; switching embedder ⇒ re-embed.
- Keep stable agent keys (UI/tests depend on them). Commit only when the owner asks.
