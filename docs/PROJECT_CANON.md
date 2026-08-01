# PROJECT CANON — the durable source of truth

> **Read this first on any resume.** This file exists so a long conversation +
> repeated compaction never loses the vision, decisions, or plan. It is kept
> current as decisions are made. If something here conflicts with an older ADR,
> this file's "Locked Decisions" section wins and the ADR should be updated.
> Last updated: 2026-07-29 (§4 rewritten to the 4-box Coolify fleet from live inventory;
> §5/§6/§7/§8 doc-sync — ADR-0040 Weaviate, ADR-0041 Memgraph, ADR-0042 Portkey/LiteLLM-retired,
> agno 2.8.0; ADR-0036–0039 accepted same day; prior: 2026-06-13, §6 refresh 2026-07-11).
> _Byline: Claude Code · Opus 4.8 · 2026-06-13 (created 2026-06; this revision Opus 4.8;
> §6 status refresh 2026-07-11 Claude Code · Sonnet 5; §5/§6/§8 sync 2026-07-29
> Claude Code · Fable 5)_

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
3. New capabilities become **atomic tools** (`server/tools/`, capability-sub-namespaced per ADR-0035) or **MCP services wrapped behind Agno** — NEVER a new forked architecture. See `REPO_STRUCTURE.md`.
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

## 4. Current stack (deployed — 4-box Coolify fleet; rewritten 2026-07-29 from live Coolify inventory)

**Coolify is the deploy plane** (control plane on `ion-control`): deploy = git push → Coolify
build, with per-app **Watch Paths** scoping the blast radius (set watch_paths at app creation,
always — an app without them redeploys on EVERY push). Boxes are Tailscale-meshed
(`tilapia-skilift.ts.net`); services bind `${BIND_IP}` (the box's tailnet IP), never loopback —
probes and tunnels target the tailnet IP, not `localhost`. Coolify projects: `agno-platform`,
`Case Bible`. (The original single-VPS `~/agno-mvp` compose layout this section used to describe
is preserved in git history + `docs/planning/`.)

| Box (tailnet IP) | Role | Coolify apps (live, verified 2026-07-29) |
|---|---|---|
| `ion-control` (Ionos 3.8 GB) | Coolify control plane | — (Coolify itself) |
| `ovh-app` `100.72.169.40` | Exec tier (the old exec bundle split into independent apps, owner rule "separate everything separable") | `exec-tier` (agentos-api + db rump) · `exec-gateway` (OpenCode; LiteLLM deprecated → teardown pending, ADR-0042) · `exec-contextforge` (tool gateway) · `exec-platform-tools` (SBV forensic fork + tools-facade) · `exec-sandbox` · `exec-desktop` (Kasm) · `portkey` (THE model gateway, ADR-0042) · `knowledge-workbench` (staged-ingest console, :8020) · `agent-ui` · `browser` · `coolify-mcp` |
| `ovh-data` `100.119.96.29` | Data tier — independent apps on the shared external `agno` docker network (172.30.0.0/16; cross-app DNS — `neo4j:7687`, `milvus:19530`, …) | `data-pg` (PG18: pg_duckdb + pgvector + PostGIS; tailnet `DB_HOST=100.119.96.29`) · `data-neo4j` (Graphiti's graph) · `data-graphiti` (Graphiti MCP) · `data-surreal` · `data-weaviate` (ADR-0040 substrate — deployed & healthy, cutover pending) · `data-vector` (Milvus — sidelined per ADR-0040) · `nocodb` (review front-end, ADR-0029 lineage) |
| `ovh-files` `100.91.190.107` | Files + chat surfaces | `librechat` (:3080) · `librechat-mongo` (real Mongo — owner waiver of the FerretDB rule) · file services (Cloudreve, casebible rclone lane) |

**Off-Coolify:** Homepage dashboard `http://100.72.169.40:3010` (plain compose,
`/data/dashboards` on ovh-app); n8n on its own server (tailnet `100.98.98.38`); AgentOS
control plane = os.agno.com via the localhost tunnel (`agentos-control.cmd`, Desktop
shortcut). **Storage:** Cloudflare R2 (`nexus` + the casebible buckets) — rclone mounts +
S3 API + pg_duckdb httpfs (`read_text('s3://nexus/...')`).

---

## 5. Locked decisions

- **Deploy on the VPS** (ADR-0009), not local podman. n8n on its own server.
- **pg_duckdb inside Postgres** (ADR-0013, supersedes ADR-0003 no-DuckDB).
- **Neo4j for Graphiti** (ADR-0014, supersedes FalkorDB). Bitemporal cognition substrate.
- **Ollama Cloud `glm-5.1` = PRIMARY LLM** via LiteLLM gateway. NVIDIA NIM =
  embeddings + rerank + LLM backup only (NVIDIA rate-limited the owner).
- **Models:** embedder `nvidia/llama-nemotron-embed-vl-1b-v2` (2048-d, asymmetric —
  query vs passage modes, `server/core/embedder.py`); reranker `nvidia/rerank-qa-mistral-4b`
  (`server/core/reranker.py`, custom — Agno's CohereReranker leaks to Cohere). Gemini 2.5 Pro
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
    agent/LLM gets its model through LiteLLM. ⚠ **Superseded 2026-07-29 → Portkey (ADR-0042)**;
    LiteLLM deprecated pending teardown — see the Portkey entry below.
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
    MCP client) — never directly. Two distinct gateways: **models** (Portkey since ADR-0042,
    formerly LiteLLM) and **ContextForge = tools**.
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
- **SurrealDB = store/session/memory + bitemporal-record layer (LOCKED 2026-06-13; ADR-0024, amended by ADR-0027).**
  Consolidate AgentOS sessions+state + memory + the **bitemporal evidence-record store** (native valid+transaction
  time) onto **SurrealDB**. ⚠ **The vector/Knowledge role moved to Milvus (ADR-0027)** — SurrealDB is NOT the vector
  store; semantic search lives in Milvus. **Custom Graphiti STAYS** the bitemporal *cognition* substrate (VIP — NOT
  replaced; different altitude). Migrate off pg_duckdb deliberately vs the live ADR-0013 stack; sequence in Phase D.
- **Milvus = the platform-wide VECTOR/ANN substrate (LOCKED 2026-06-13; ADR-0026 + ADR-0027). LIVE on ovh2.**
  Self-hosted **Milvus 3.0 standalone (embedded etcd + local storage + WoodPecker) + Attu v3**, Coolify-deployed
  on ovh2 from the `milvus-coolify` repo — **off** the managed Zilliz `aws-eu-central-1` cluster. **Everything
  that needs similarity search lands in Milvus** (one collection per embedder/domain): the `claude-context` code
  index, the **Case Bible** corpus, the **domain-partitioned Knowledge engine**, and evidence-text embeddings —
  via **Agno's native Milvus integration** (off-the-shelf). Gains **hybrid dense+sparse/BM25** retrieval. Reachable
  over Tailscale (`100.91.190.107`: gRPC 19530, Attu UI 3000); mapped (bind-mount) volumes at `/data/milvus/volumes/*`
  (owner backup preference); auth on (`root:Milvus`, rotate). Embedder unchanged (OpenRouter `codestral-embed-2505`,
  1536-d). Beta-aware: code/Case-Bible now; **Knowledge-engine migration off pgvector = Phase B/D** (accept beta or
  pin GA then). Deploy gotchas recorded in [[milvus-coolify-decision]] memory.
  ⚠ **Engine choice superseded by ADR-0040 (2026-07-27): Weaviate LOCKED** — see the next entry;
  Milvus stays sidelined-but-up until cutover is verified, then parks (FalkorDB status).
- **Weaviate = the platform-wide VECTOR/ANN substrate (LOCKED 2026-07-27; ADR-0040 — supersedes
  ADR-0026/ADR-0027 on the engine choice).** Single Go binary on the data tier replaces the
  Milvus 4-container convoy (etcd fragility — lived 07-21→23 outage — plus data corruption and
  a heavy footprint for unused components). No practical HNSW dim cap → keeps the nv-embed-v1
  4096-d embed contract with NO re-embed; native hybrid BM25+vector. Collection-shape ADRs
  0010/0011 carry over unchanged. **Execution underway:** the `data-weaviate` Coolify app is
  deployed & healthy on ovh-data (verified live 2026-07-29); data cutover + verification still
  pending — steps in ADR-0040.
- **Memgraph = ADDITIVE temporal GraphRAG layer, read-side only (LOCKED 2026-07-28; ADR-0041).**
  Variant B (classic Memgraph analytical projection). NEVER a system of record — Neo4j/DozerDB
  stays (Semantica is Neo4j-bound; Graphiti's supported backends exclude Memgraph). Orchestration
  is Agno-native. Variant A (MemGQL federation) parked as an experiment.
- **Portkey = the MODEL gateway; LiteLLM RETIRED (owner ruling 2026-07-29; ADR-0042 — supersedes
  ADR-0015).** Portkey has carried the Graphiti lane + exec-tier since 2026-07-19 (11-provider
  failover, 4-key Gemini rotation, configs committed under `docker/gateway/portkey/`; decoupling
  proven through a 40-min exec-tier outage). LiteLLM is deprecated pending teardown — a separate
  owner-gated task (incl. remapping OpenCode's model config); until then nothing NEW points at it.
- **Graphiti/memory-lane ADRs 0036–0039 ACCEPTED (owner 2026-07-29; Proposed 2026-07-13):**
  DozerDB multi-DB with RBAC-scoped writers — `memory` vs `evidence` isolation (0036; **LIVE
  2026-07-30** — `data-neo4j` = `graphstack/dozerdb:5.26.27.0`, same upstream version so no
  store migration; `memory` + `evidence` created and isolation-verified. ⚠ Two caveats: DozerDB
  only accepts the PLAIN `CREATE DATABASE x` form — `IF NOT EXISTS`/`WAIT` return a misleading
  "Unsupported administration command"; and **RBAC roles are unimplemented upstream**, so the
  wall is database-scoped (blocks accidents) not permission-scoped (does not block a caller
  holding the `neo4j` superuser credential). Phase 2 = move Graphiti onto `memory`) · Graphiti
  MCP as a write-enabled ContextForge virtual server, standalone `:8071` no-auth door to be
  retired (0037) · Agno agents use `graphiti-core` in-process, the MCP door serves GUI clients
  only (0038) · Graphiti extraction LLM = hosted structured-output provider, never small/local
  (0039 — live in practice since 2026-07-04: NIM nemotron guided-JSON, lane routed via Portkey).
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
  + segmenter) gets **vendored** into `server/tools/parsers/ai_chat/` as atomic modules
  (replacing the 4 shallow placeholder parsers; done — see ADR-0035). dial-stack's
  TypeScript capabilities (forensic parsers,
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
- P2 evidence spine 🟡 **parser core-swap DONE** (verified 2026-07-11), **pipeline/schema
  population still open**. Directory layout repacked twice since this line was written:
  ADR-0033 server/ repack merged+deployed 2026-07-09; ADR-0035 tools sub-namespacing
  merged+deployed 2026-07-10 (see that ADR's Outcome section). Chatminer vendoring landed —
  `server/vendored/chatminer/` + 11 real parser modules in `server/tools/parsers/ai_chat/`
  (9 chatminer-backed, 2 genuinely custom formats — claude.ai export JSON, Claude Code
  JSONL — chatminer has no equivalent); `DEBT.md` marks "Backend atomic tools attached"
  resolved 2026-07-10. Still open: "Evidence schemas populated by a real pipeline" remains
  `planned` (`DEBT.md`) — live PG evidence schema is near-empty (`evidence_hash`=26 rows,
  verified 2026-07-11); the RESTART-0001 per-source raw-table redesign (6 `source.*` tables
  + `file_custody` anchor, h1/h2/h3 as row columns) is DRAFT awaiting owner sign-off (D-008,
  `docs/DECISION_LOG.md`) and the old ingestion schema is DEAD per owner.
- P3 bitemporal substrate (valid/knowledge-time + disclosure-tier; Semantica stand-up)
- P4 SBV as Workflow A (custody-gated vertical + iframe + CLI + export) 🟡 **largely landed**
  (as of 2026-07-11): forensic fork LIVE in prod with H1/H2/H3 custody hashing
  (`ghcr.io/cursedpotential/sbv-forensic:0.2.3-forensic`, deployed 2026-07-09); all 14 facade
  tools registered in ContextForge virtual server `platform_tools` (2026-07-10). Open:
  Phase 5a native Go automation endpoints (`POST /api/automation/extract`+`status`/`export`/
  `backups`) are BUILT on fork branch `worktree-agent-abe280ccbefefe136` (`813f3b2`) but not
  yet shipped through the subtree→fork→CI→tag-bump sequence (`docs/COORDINATION.md`); Phase
  5b `/x/sbv/` UI embed is DEFERRED to the G2/VPS window (see `docs/planning/sbv-fork-plan.md`).
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
- **Hardening** — evidence-text embeddings at scale in **Weaviate** (the locked platform-wide
  vector substrate — ADR-0040 2026-07-27, superseding the Milvus lock ADR-0026/ADR-0027; Milvus
  stays sidelined-but-up on the `data-vector` Coolify app until cutover is verified);
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
- URLs (tailnet; box IPs in §4): AgentOS `ovh-app:8000` (`/config`, `/docs`, `/approvals`),
  SBV `:8080`, OpenCode `:4096`, Kasm `:6901` (https), Neo4j Browser `ovh-data:7474`,
  Graphiti MCP `:8071/mcp` (Host-header override; door retirement pending per ADR-0037),
  LibreChat `ovh-files:3080`, Homepage `ovh-app:3010`, workbench console `:8020`.
  LiteLLM `:4000` deprecated (ADR-0042 — do not wire anything new to it).

---

## 8. Gotchas (hard-won, do not relearn)

- agno 2.8.0 (2.6.9→2.6.13 on 2026-06-12; →2.8.0 on 2026-07-23): embedders/rerankers under `agno.knowledge.embedder/.reranker`; Team
  mode needs `TeamMode` enum (strings break `/config`); `requirements.txt` is
  `uv pip sync`'d → new pkg needs its transitive deps listed; EntityMemoryStore
  has no PROPOSE mode (falls back to ALWAYS); 2.8.0 stopped bundling per-provider
  model SDKs as transitive deps → every provider in the ADR-0008 chain must be an
  explicit dependency (see the comment in `pyproject.toml`).
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
