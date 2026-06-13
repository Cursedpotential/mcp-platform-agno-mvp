# Glossary — Ubiquitous Language

> One term, one meaning — across agents, code, schema, and court-facing output. If a term drifts, fix it
> here first, then in code. Add a term the moment a new concept appears.

## Domain (forensic / legal)
- **Evidence** — original, source data (SMS/Facebook/iMessage exports, etc.). Immutable. Lives in the
  read-only `evidence` schema and the raw-bytes blob store (R2). Never mutated by agents.
- **Analysis (derived artifact)** — anything computed *from* evidence (reports, graphs, embeddings,
  summaries). Lives in the `analysis` schema. Approval-gated, never mixed into `evidence`.
- **Chain of custody** — the documented, hash-verified record of every handler/touch of evidence
  (SHA-256 at first touch). Produced by the TS MCP server's vault.
- **Provenance** — lineage of a derived artifact back to its evidence (W3C PROV-O at the platform stage).
- **HITL (human-in-the-loop) / Approval** — the mandatory human decision before any write to evidence,
  normalization, config, or DB. A first-class *state*, not a prompt convention.
- **Insight (transcript_insight)** — a raw, structured extraction mined from an AI chat transcript
  (decision/code/goal/blocker/etc.). Distinct from "learned knowledge."
- **Learned Knowledge** — a synthesized, reusable lesson stored in the LearningMachine (not a raw extraction).

## Platform / architecture
- **Bounded context** — a self-contained capability domain. Here: *Ingestion/Custody* (TS MCP),
  *Analysis/Document-Intelligence* (Py MCP), *Approval/Audit*, *Memory*, *Cloud Cleanup*. Tools and
  agents stay within their context.
- **Ports-and-adapters (hexagonal)** — agents are the thin policy **core**; MCP servers and Context
  Providers are the **adapters**. Business logic lives in the adapters, not the agents.
- **AgentOS** — Agno's FastAPI runtime that serves the agents (`base_app` + `get_app()`).
- **Agent** — a thin policy/orchestration unit. Platform agents *operate*; Builder agents *develop*.
- **Team** — a group of agents. **Router** team uses `mode="route"` (pick one family); **family** teams
  use `mode="coordinate"` (delegate + synthesize).
- **Router** — the top-level entry point (`agents["router"]`) that dispatches to Ops / Builder / Cleanup.
- **Context Provider** — adapter wrapping one source as `query_<id>` / `update_<id>` behind a sub-agent.
- **MCP server** — an external Model Context Protocol server exposing tools (our TS/Py/JS servers).
- **MCPTools** — Agno class attaching one MCP server's tools to an agent (AgentOS manages lifecycle).
- **MCPToolbox** — Agno class fronting Google's MCP Toolbox for Databases with toolset/tool filtering.
- **LearningMachine** — Agno's native memory; six stores (User Profile, User Memory, Session Context,
  Entity Memory, Learned Knowledge, **Decision Log**); modes Always / Agentic / **Propose** (HITL).
- **Knowledge** — Agno's retrievable reference corpus (pgvector hybrid search). Distinct from memory.

## The agents (stable keys)
- `ingestion_orchestrator` · `analysis_orchestrator` · `review_gatekeeper` (platform)
- `dev_copilot` · `project_pal` · `forensic_data_agent` (builder)
- `transcript_miner` (ChatMiner) · `router` (root)
- _(removed 2026-06-12: `cloud_drive_cleanup` — separate future feature, returns with Drive/OneDrive MCP)_

## Components / stores
- **ChatMiner** — the custom transcript-parsing subsystem (10 source parsers + chunker + segmenters).
- **n8n** — automation service on the shared Postgres; may drive the platform via REST.
- **Cloudflare R2** — S3-compatible object store; the **blob/object landing zone** for raw evidence + archives.
- **Semantica** — the platform-stage target the MVP bootstraps into (graph + decision intelligence).
- **FalkorDB / Graphiti** — evidentiary temporal graph; platform stage, not the MVP.
- **agno approvals (native)** — agno 2.6.13 persists pending approvals on pause; `/approvals` API
  records decisions; run-continue gated by `require_approval_resolved`. (Legacy `agent_run`/
  `approval_request` tables superseded 2026-06-12, kept for provenance.)
- **evidence_hash** — custody hashes (BYTEA) in the `evidence` schema.
