# PROJECT CANON — the durable source of truth

> **Read this first on any resume.** This file exists so a long conversation +
> repeated compaction never loses the vision, decisions, or plan. It is kept
> current as decisions are made. If something here conflicts with an older ADR,
> this file's "Locked Decisions" section wins and the ADR should be updated.
> Last updated: 2026-06-13.
> _Byline: Claude Code · Opus 4.8 · 2026-06-13 (created 2026-06; this revision Opus 4.8)_

---

## 0. Document Contract (ONE of each — read this to know what's authoritative)

To stop architecture/plan drift, **each concern has exactly ONE authoritative file.**
This canon is the entry point and names them. Everything else (the 22 ADRs, `docs/planning/*`,
the wiki, `glossary.md`) is **subordinate history/reference**, not a competing source of truth.

| Concern ("one X") | Authoritative file |
|---|---|
| **Vision + locked decisions** (the index) | `docs/PROJECT_CANON.md` ← you are here |
| **Inventory** (what code exists, where, what's the best version) | `docs/EVIDENCE_MERGE_MAP.md` |
| **Plan** (what we build next, phased) | `docs/BUILD_PLAN.md` |
| **Structure** (where every kind of file goes) | `docs/REPO_STRUCTURE.md` |
| **Style** (how we write code — Python/TS, tool contract) | `docs/CONVENTIONS.md` |
| **Handoffs** (forward build as small agent-executable units) | `docs/HANDOFFS.md` |

**Drift rules (non-negotiable):**
1. If any doc conflicts with another, **§5 Locked Decisions here wins**; fix the others to match.
2. When a locked decision is made, **update this canon in the SAME change** — never let it lag.
3. New capabilities become **atomic tools** (`evidence/tools/`) or **MCP services wrapped behind Agno** — NEVER a new forked architecture. See `REPO_STRUCTURE.md`.
4. `dev-resources/Archives/` is **read-only donor material** — mine it, never edit or build inside it.

---

## 1. What we are building (the three-part arc)

A personal **evidence-processing + analysis + legal-strategy platform** for the
owner's **pro se** family-law (custody) case, built on Agno AgentOS. It
bootstraps itself: the early agents help build the rest of the platform.

1. **Part 1 — Evidence.** Custody → parse → normalize → store → court-ready export.
   Many sources (SMS, Facebook, iMessage-PDF, Google Voice/Location, chat
   exports, Drive/OneDrive). Immutable, hashed, chain-of-custody.
2. **Part 2 — Analysis.** Multi-pass psychological / abuse / toxicity analysis of
   the conversations (gaslighting, DARVO, coercive control, misleading events).
3. **Part 3 — AI Legal Team.** A third agent family that uses the evidence +
   the knowledge base to build legal strategy, documents, and filings. Already
   prototyped by the owner as **Gemini Gems + personas**; to be **ported to Agno**.
   This is where the imported Michigan legal skills + MCL 722.23 ontology engage.

**The killer mechanism (why the memory is bitemporal):** Part 2 replays how a
person realizes they were abused, in passes with widening knowledge —
**Pass 1 contemporaneous** (agent sees only what was knowable at that moment —
where gaslighting works), **Pass 2/3 assembled hindsight** (all conversations
connected), **Final pass full disclosure** (incl. facts discovered later). A
"pass" is a **knowledge horizon** — a filter over a bitemporal graph. The
**delta between Pass 1 and the final pass for the same event IS the abuse made
legible** ("what you were led to believe vs what was true vs when you found
out"). Every evidence atom must carry **valid-time + knowledge-time +
disclosure-tier**. This is why Graphiti/Neo4j is the cognition substrate.

**The end-goal frame (the platform itself):** beneath the three-part arc, the
durable product is a **multi-surface tool-platform GATEWAY** — it **serves** its
own tools, **consumes** external tools, and **routes/proxies** between them, exposed
across surfaces (Claude MCP / Gemini / OpenAI / Agno itself). The evidence/analysis/
legal arc is the **first domain application** running on that gateway. The Builder
agents help build the gateway out (the bootstrap loop). **Gateway core = Agno**
(see §5); the abandoned prior attempt (AI DIAL, in `dev-resources/Archives/dial-stack`)
is a parts/pattern donor only.

---

## 2. Agent families (topology)

Root **Router** (`mode=route`) dispatches to one of three families:

1. **Platform Ops** (`coordinate`) — Ingestion Orchestrator, Analysis
   Orchestrator, Review Gatekeeper. Runs the evidence pipeline.
2. **Builder** (`coordinate`) — Dev Copilot, Project PAL, Forensic Data Agent.
   Helps build/port the platform itself (the bootstrap).
3. **AI Legal Team** (`coordinate`, **to build — Part 3**) — ported from the
   owner's Gemini Gems personas. Pro se case assistance: strategy, motions,
   filings, discovery. Uses evidence + knowledge + the Michigan legal skills.

Plus standalone: Document Digest (Gemini long-context). Stable agent keys —
UI/tests depend on them. (Cloud Drive Cleanup: removed from the active topology
2026-06-12 — owner decision, separate future feature, not part of this platform.)

---

## 3. The knowledge engine — multi-domain, any-agent, domain-separated

Knowledge is gathered from conversations covering **everything**: timeline &
relationship history, personal history, platform/engine **design decisions**,
and **legal strategy & planning**. **Requirement: any agent can query it, and
the domains MUST stay separated** so an agent pulls the right context.

**Design (to implement):** domain-partitioned knowledge — separate
collections/namespaces + metadata tags per domain, not one undifferentiated
corpus:
- `timeline_relationship` — relationship history, events, who/when
- `personal_history` — background, personal context
- `platform_design` — engine/platform design decisions & discussion (this canon, ADRs, planning)
- `legal_strategy` — case strategy, planning, filings discussion

**Two different taxonomies — keep them separate (owner decision 2026-06-13):**
the **knowledge DOMAINS above** are *storage partitions* (which collection a record
lands in). The parser's **`TopicTag`** (`RELATIONSHIP_HISTORY` / `PERSONAL_LEGAL` /
`DEVELOPMENT` / `EMOTIONAL` / `EVIDENCE` / `MIXED` / `UNKNOWN`) is a *separate metadata
field* on each segment — NOT merged into the domains. Because the owner's conversations
are "very ADD/bipolar" (every conversation spans all topics), **tagging happens at the
SEGMENT/TURN level, never per-conversation**, with `MIXED`/`UNKNOWN` as catch-alls.
**`RELATIONSHIP_HISTORY` is its own first-class lane** (split out of `PERSONAL_LEGAL`)
with heavy entity extraction + timeline construction.

Each agent family queries the domains relevant to it (Legal Team → legal_strategy
+ evidence + timeline; Builder → platform_design; Analysis → timeline +
personal). Implemented as per-domain pgvector collections (MVP) with metadata
filters; evidence-scale vectors move to a self-hosted store later (see §6).

**The comprehensive living wiki (ADR-0022) — the human-readable face of this engine.**
One wiki, **dual-rendered**: human-readable navigable markdown AND AI-queryable
(ingested into the domains above). **Covers everything** — every library used
(purpose/version/gotchas), every application/service, every bit of code created,
every decision (ADRs flow in), every strategy (platform + legal). It is *living*
(agents keep it current, a Builder-family doc responsibility), absorbs the three
archived wikis in `dev-resources`, and is the superset of which ADRs + this canon
are sections. Big build, **deferred** — until then this canon is the interim truth.

**Knowledge gathering is phased:** (a) help build the missing/incomplete
platform components → (b) process evidence against historical timelines/events
→ (c) produce legal strategy + docs + filings.

---

## 4. Current stack (deployed, OVH VPS `40.160.5.19`, `~/agno-mvp`)

Access: `ssh -i ~/.ssh/ovh debian@40.160.5.19`. Code volume-mounted (`.:/app`)
→ deploy = sync files + `docker compose ... up -d`/`restart`. Tailnet IP
`100.72.169.40`. Profiles: default, `tools`, `graph`, `desktop`.

| Service | Role | Port |
|---|---|---|
| `agentos-db` | PG18 custom (`agno-postgres:18-duckdb`): pg_duckdb + PostGIS + pgvector + pg_stat_statements + uuidv7; dual schema evidence(ro)/analysis | 5432 |
| `agentos-api` | AgentOS (base_app), router + agents, knowledge, learning, HITL routes | 8000 |
| `platform-tools` | SBV (GUI/API, musl-fixed, :8085 int) + tools-facade (registry, :8090) | 8080/8090 |
| `agent-sandbox` | isolated code-exec for agents (no secrets, no ports) | 8070 int |
| `gateway` | LiteLLM (all providers) + OpenCode | 4000/4096 |
| `neo4j` | Graphiti temporal graph (Browser 7474) | 7474/7687 |
| `graphiti-mcp` | Graphiti MCP (zepai image, Neo4j backend) | 8071 |
| `desktop` | Kasm browser desktop (persistent, profile `desktop`) | 6901 |
| *n8n* | SEPARATE server `74.208.130.34`, Tailscale-linked `100.98.98.38` | 5678 |

**Storage:** Cloudflare R2 bucket `nexus` — rclone docker-volume (`/r2`) + S3 API
+ pg_duckdb httpfs (`read_text('s3://nexus/...')`). Tailscale mesh
`tilapia-skilift.ts.net`.

---

## 5. Locked decisions

- **Deploy on the VPS** (ADR-0009), not local podman. n8n on its own server.
- **pg_duckdb inside Postgres** (ADR-0013, supersedes ADR-0003 no-DuckDB).
- **Neo4j for Graphiti** (ADR-0014, supersedes FalkorDB). Bitemporal cognition substrate.
- **Ollama Cloud `glm-5.1` = PRIMARY LLM** via LiteLLM gateway. NVIDIA NIM =
  embeddings + rerank + LLM backup only (NVIDIA rate-limited the owner).
- **Models:** embedder `nvidia/llama-nemotron-embed-vl-1b-v2` (2048-d, asymmetric —
  query vs passage modes, `db/embedder.py`); reranker `nvidia/rerank-qa-mistral-4b`
  (`db/reranker.py`, custom — Agno's CohereReranker leaks to Cohere). Gemini 2.5 Pro
  for Document Digest. Groq/OpenRouter in reserve.
- **Memory = LearningMachine (operational) + Graphiti/Neo4j (evidentiary, bitemporal)
  + pgvector Knowledge (reference, domain-partitioned).** Semantica pulled forward
  as substrate (decision/provenance layer); its multi-pass *use* is Part 2.
- **Tool architecture = polyglot orchestration mesh:** universal custody gate →
  named workflows A/B/C per evidence type → registered atomic tools (one
  library/language each) → agent re-composition in the sandbox on step failure.
- **Minimize custom code (locked 2026-06-13).** Default to **off-the-shelf open-source**;
  write custom code ONLY for what is genuinely situation-specific (the evidence custody/
  bitemporal logic, MCL/legal analysis, the owner's parsers/taxonomy). Everything generic
  uses a proven component.
- **VIP components — NEVER overwrite, reinvent, or fork around (owner, 2026-06-13).** Build
  *around* these; integrate, don't replace: **Agno** (+ its native UIs, below) · **custom
  Graphiti** (the bitemporal KG — our customized build, not stock) · **Semantica** (decision/
  provenance substrate) · **IBM ContextForge** (the tool gateway) · **the forked SBV tool**
  (custom SMS Backup & Restore, in `platform-tools`) · **CopilotKit** (UI, rides Agno's AG-UI).
- **Serve/consume topology (locked 2026-06-13) — the layered picture; nothing here gets dropped:**
  - **Model gateway = LiteLLM** (`gateway` container): routes ALL models — remote (Gemini/Groq/
    OpenRouter/NVIDIA/Anthropic) AND in-stack/local (Ollama Cloud primary `glm-5.1`). Every
    agent/LLM gets its model through LiteLLM.
  - **Tool gateway = IBM ContextForge**: serves/federates MCP tools to any MCP client — Agno
    agents (`MCPTools`, stdio + HTTP), **remote** LLMs (Claude/Gemini), and **local-stack** runners.
  - **Agent runtime + OUTBOUND serving = Agno AgentOS**: serves our agents/workflows out via
    **MCP-server + A2A + AG-UI (CopilotKit) + REST** → consumable by other LLMs/agents/frontends.
  - **OpenCode** (`gateway` container) = coding agent / builder surface — **consumes** our MCP
    tools (through ContextForge) and uses **LiteLLM** models. An in-stack consumer — KEEP.
  - **agent-sandbox** = isolated code-exec for agent re-composition (no secrets, no ports). KEEP.
  - **Kasm desktop** (`desktop` profile) = **persistent** browser desktop for agent/human GUI work. KEEP (persistence matters).
  - **Cognition = custom Graphiti** (bitemporal KG, VIP). **Store/session/Knowledge/memory =
    SurrealDB candidate** (Agno-native db+vector+memory; consolidates pg_duckdb/pgvector/memory;
    NOT a Graphiti replacement — Graphiti stays for cognition; decide before P3/Phase B).
  - ⚠️ A raw local model consumes tools ONLY through an MCP-capable harness (Agno / OpenCode /
    MCP client) — never directly. Two distinct gateways: **LiteLLM = models**, **ContextForge = tools**.
- **Universal exposure — API-first + MCP-wrapped (locked 2026-06-13; needs ADR).** EVERYTHING is
  atomically addressable — **every tool, every agent, every workflow** exposes:
  1. an **internal API** (FastAPI/HTTP) that in-platform ("platform-surface") consumers call directly;
  2. an **MCP wrapper over that API** for ALL external/any-surface consumers — federated by IBM ContextForge.
  Each unit is callable **atomically**; tools also **compose into workflows** (a workflow may declare a
  slot for a *variable set* of tools). **Workflows are first-class** and reachable **inside or outside**
  the platform from any surface, via the same API+MCP pattern. **Rule: everything gets an API; every API
  gets an MCP.** Exposed **token-efficiently via progressive disclosure** — `search_tools` → `describe_tool`
  on demand → `invoke_tool` → `get_ref` (paged); start with a search tool + name-only catalog, never dump all
  schemas into context (dial-stack `gateway.ts` pattern; ADR-0023, Phase C). (Implements minimize-custom +
  the serve/consume topology; registry + ContextForge carry it. Workflow *design* = a future brainstorm — see HANDOFFS.)
- **SurrealDB = store/session/Knowledge/memory layer (LOCKED 2026-06-13; needs ADR).** Consolidate
  AgentOS sessions+state + pgvector Knowledge + memory onto **SurrealDB** (Agno-native db + vector + memory).
  It also fits the **bitemporal evidence-record store** (native valid + transaction time). **Custom Graphiti
  STAYS** the bitemporal *cognition* substrate (VIP — NOT replaced; different altitude). Migrate off
  pg_duckdb/pgvector deliberately, weighed against the live ADR-0013 stack; sequence in Phase D.
- **Self-hosted Milvus = shared semantic-search store (LOCKED 2026-06-13; ADR-0026).** `claude-context`
  (code/knowledge index) + the **Case Bible** corpus run on **our own Milvus standalone** (Milvus+etcd+MinIO),
  Coolify-deployed on OVH from the `milvus-coolify` repo — **off** the managed Zilliz `aws-eu-central-1`
  cluster. Mapped (bind-mount) volumes (owner backup preference); Traefik h2c fronts gRPC 19530 so
  `MILVUS_ADDRESS=https://<domain>`; auth on. Embedder unchanged (OpenRouter `codestral-embed-2505`, 1536-d).
  **Distinct from SurrealDB (ADR-0024):** Milvus serves the Milvus-only `claude-context`/Case-Bible search;
  SurrealDB is the platform store/session/Knowledge/memory layer; Graphiti stays cognition.
- **Use Agno's NATIVE surface — do NOT rebuild it (validated against agno docs 2026-06-13).**
  AgentOS = Runtime (FastAPI serving agents/teams/workflows) + **Control-plane UI** (manage/
  monitor/debug) + a **Chat UI** (chat with agents, run workflows; open-source Next.js "AgentUI",
  self-hosted, DB-only). **Multi-surface interfaces are built in**: AG-UI (CopilotKit/Dojo),
  Slack, WhatsApp, Telegram, A2A — one agent answers on all, memory follows the user across
  surfaces. Plus native: sessions, memory, knowledge, evals, config (quick-prompts/per-domain
  models), auth/JWT. → We **do not build** a custom chat UI, control UI, or multi-surface
  serving; we configure Agno's. (Note: this reframes the "multi-surface gateway" — Agno already
  serves agents to many surfaces; IBM ContextForge is specifically the *MCP-tool* gateway layer.)
- **Tool gateway = IBM ContextForge, NOT custom, NOT DIAL (locked 2026-06-13).** The
  multi-surface tool-gateway (serve/consume/route/proxy MCP tools across surfaces) is
  **IBM ContextForge MCP Gateway (`IBM/mcp-context-forge`)** — off-the-shelf, per the
  minimize-custom rule. **Agno is the agent-orchestration core** (not the gateway). The
  prior AI-DIAL attempt (`dev-resources/Archives/dial-stack`) is a **parts/pattern donor
  only** (DIAL runtime dropped). ⚠ The ContextForge **tool gateway** is distinct from the
  **LLM/model gateway** (LiteLLM, ADR-0015) — don't conflate the layers. *(Needs an ADR;
  supersedes the earlier "Agno-native gateway, ContextForge fallback" framing.)*
- **Donor reconciliation (locked 2026-06-13):** Python `chatminer` (10 AI-chat parsers
  + segmenter) gets **vendored** into `evidence/tools/` as atomic modules (replacing the
  4 shallow placeholder parsers). dial-stack's TypeScript capabilities (forensic parsers,
  pattern-analyzer, timeline, bi-temporal Graphiti, document-intelligence engines incl.
  Google DocAI + IBM watsonx, ~100-tool catalog) are **wrapped as MCP services behind
  Agno** — no mass rewrite. Full inventory: `docs/EVIDENCE_MERGE_MAP.md`.
- **No-stub rule:** unavoidable stubs get `# STUB:` markers + a row in
  `docs/DEBT.md`. Tests are harness-first.
- **HITL is first-class:** every write (ingestion/normalization/evidence/config/db)
  pauses for recorded human approval. Trash-only for any cloud cleanup; never
  permanent-delete. `Secrets/` and case-data dirs are NEVER ingested into Knowledge.

---

## 6. Roadmap

**This round (plan: `plans/logical-herding-forest.md`) — Part 1 complete + memory substrate:**
- P0 ✅ debt register + embedding query-mode fix + persistent duckdb R2 secret
- P1 ✅ (2026-06-12) HITL fully NATIVE on agno 2.6.13: `@approval` +
  `requires_confirmation` → pause persists pending row; `POST /approvals/{id}/resolve`
  records decision; continue gated by `require_approval_resolved`; real
  `apply_db_modification` (analysis-only write, evidence-ref guard). Custom
  approval table/routes removed. Cloud Drive Cleanup agent removed from active
  topology (owner: separate future feature).
- P2 evidence spine 🟡 BUILT LOCALLY (`evidence/`: custody, registry, workflows,
  normalize, store, cli) — NOT yet redeployed; the 4 transcript parsers are shallow
  placeholders to be **replaced by vendored chatminer** (see BUILD_PLAN Phase A).
- P3 bitemporal substrate (valid/knowledge-time + disclosure-tier; Semantica stand-up)
- P4 SBV as Workflow A (custody-gated vertical + iframe + CLI + export)
- P5 harness-first tests + backups to R2

> **Forward build sequencing now lives in `docs/BUILD_PLAN.md`** (Phases A–E + Part 2/3),
> derived from the owner's critical path (transcript knowledge-gathering FIRST → bootstrap
> loop) and `EVIDENCE_MERGE_MAP.md` §5. `docs/planning/*` (EXECUTION_PLAN, BUILD_TODO,
> MIGRATION_PLAN_v8, …) is **build history**, superseded for forward work by BUILD_PLAN.

**Next rounds:**
- **Part 2** — multi-pass analysis engine (knowledge horizons, pass-delta surfacing).
- **Part 3** — AI Legal Team (port Gemini Gems personas to Agno; strategy/docs/filings).
- **Knowledge engine** — domain-partitioned collections + ingestion of all
  conversation domains (timeline/personal/design/legal).
- **Hardening** — self-hosted evidence vector store (Qdrant-leaning) at scale;
  multi-user auth; V2 slim Graphiti image.

---

## 7. Access & credentials (POINTERS — secrets live in gitignored `.env`, local + VPS)

- VPS: `ssh -i ~/.ssh/ovh debian@40.160.5.19` (sudo passwordless). n8n box:
  same key, `debian@74.208.130.34` (sudo password-gated).
- Tailscale: admin API key in `.env` (`TAILSCALE_API_KEY`) mints auth keys.
- R2 `nexus`: `R2_*` in `.env` (account `1a7406c497493a52128bb282f499e7b8`).
- Providers in `.env`: `OLLAMA_API_KEY` (primary), `NVIDIA_API_KEY`,
  `GOOGLE_API_KEY` (gemini-2.5-pro), `GROQ_API_KEY`, `OPENROUTER_API_KEY`,
  `LITELLM_MASTER_KEY`. Kasm `KASM_VNC_PW`. Neo4j `NEO4J_PASSWORD`.
- URLs: AgentOS `:8000` (`/config`, `/docs`, `/approvals`), SBV `:8080`,
  Neo4j Browser `:7474`, LiteLLM `:4000`, OpenCode `:4096`, Kasm `:6901` (https),
  Graphiti MCP `:8071/mcp` (Host-header override needed).

---

## 8. Gotchas (hard-won, do not relearn)

- agno 2.6.13 (upgraded from 2.6.9 on 2026-06-12): embedders/rerankers under `agno.knowledge.embedder/.reranker`; Team
  mode needs `TeamMode` enum (strings break `/config`); `requirements.txt` is
  `uv pip sync`'d → new pkg needs its transitive deps listed; EntityMemoryStore
  has no PROPOSE mode (falls back to ALWAYS).
- NIM embedqa REQUIRES `input_type`; asymmetric (passage for docs, query for search).
- Graphiti image (zepai): embeds an UNUSED FalkorDB (`BROWSER=0`); `CONFIG_PATH`
  env ignored → mount config OVER `/app/mcp/config/config.yaml`; MCP endpoint
  `/mcp` (no trailing slash); Host-header DNS-rebind guard → `header_provider`
  `{"Host":"localhost:8000"}`; LLM factory drops `api_url` → `OPENAI_BASE_URL` env.
- SBV binary is musl-linked → carries `ld-musl` + Alpine `/usr/lib` +
  `LD_LIBRARY_PATH=/opt/sbv-libs`; listens :8085 internal; data dir `/opt/sbv/data`.
- AgentOS: `base_app=` + `get_app()`, NEVER `app.mount`; NEVER uvicorn reload with MCP.

---

## 9. Where things live

- **The 5 authoritative docs (§0 Document Contract):** `docs/PROJECT_CANON.md` (this),
  `docs/EVIDENCE_MERGE_MAP.md` (inventory), `docs/BUILD_PLAN.md` (plan),
  `docs/REPO_STRUCTURE.md` (structure), `docs/CONVENTIONS.md` (style).
- Subordinate: ADRs `docs/adr/` (index `README.md`); Debt `docs/DEBT.md`; build
  history `docs/planning/*`; living wiki `docs/wiki/` (ADR-0022, deferred); glossary.
- Mined reusable code: `extracted-code/` (+ `MANIFEST.md`) — SBV, parsers,
  extractors, schemas, ontologies (MCL 722.23, behavioral patterns).
- **Donor archives (READ-ONLY)**: `dev-resources/Archives/` — `dial-stack` (TS
  forensic/analysis/gateway donor, DIAL dropped), `Agno-MCP-Platform-alpha/chatminer`
  (parser core to vendor). **Part-2 behavioral ML "Tether"** lives at
  `dial-stack/utilities/apps/ml-nlp/Tether/` (deferred external-libs area;
  `SamanthaStorm/tether-*` HF models — dig in when Part 2 is built).
- Agent auto-memory (loads on session start): `C:\Users\matts\.claude\projects\E--AI-Workspace\memory\`.

---

## 10. Open threads / parking lot

- Owner had one more idea that slipped away (2026-06-11) — to be added when recalled.
- Knowledge-engine domain separation: finalize collection scheme + ingestion routing.
- Legal Team: inventory the Gemini Gems personas to port.
- **SurrealDB — strong consolidation candidate (validated 2026-06-13).** Multi-model
  (document + relational + vector + graph + live queries), AND **Agno supports it natively
  as a database (agent/team/workflow sessions+state) + vector store (Knowledge/RAG) + memory
  backend** (`/database/providers/surrealdb`, `/knowledge/vector-stores/surrealdb`,
  `/examples/integrations/surrealdb`). So it could **consolidate** AgentOS db + pgvector
  Knowledge + memory into one off-the-shelf engine (fits minimize-custom). **NOT a replacement
  for custom Graphiti** (VIP — stays the bitemporal evidence substrate), and weigh against the
  already-LIVE pg_duckdb stack (ADR-0013). **DECIDED 2026-06-13 → see §5 Locked Decisions;**
  sequence the migration in Phase D. Does NOT block Phase A (parsers emit storage-agnostic
  `NormalizedRecord`s).
