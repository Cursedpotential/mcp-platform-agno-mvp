# ADR-0012: Phase 0 Decisions Locked
- Status: Accepted
- Date: 2026-06-09

## Context
Phase 0 of the build plan requires seven decisions to be locked before proceeding. All have been
evaluated against current code state, ADRs 0001-0011, and the handoff guide.

## Decisions

### D1: Settings home — Keep skeleton layout
`app/settings.py` + `db/url.py` is the canonical location. All `os.getenv` calls centralized in
`app/settings.py`. No new `config/` directory. Rationale: skeleton pattern is proven, matches
existing code, and consolidates env reads in one module.

### D2: transcript_miner — Standalone agent
`transcript_miner` stays as a standalone agent serving `/v1/transcripts/mine` and
`/v1/transcripts/insights`. Not part of any coordinate team. Rationale: it has its own HTTP
endpoint surface, different lifecycle from team agents.

### D3: MCP servers — Vendor into `mcp-servers/`
Self-contained server images vendored into `agno-mvp/mcp-servers/`. `TS_MCP_COMMAND` and
`PY_MCP_COMMAND` in `.env` point to vendored paths. Rationale: containerized, no external path
dependency, matches `example.env` already set up.

### D4: PG18 vs PG17 — Target PG18, fall back to PG17+pg_uuidv7
`agnohq/pgvector:18` in compose already targets PG18. Native `uuidv7()` is preferred. If PG18
image issues arise, fall back to PG17 with `pg_uuidv7` extension. Rationale: native UUIDv7
eliminates extension dependency.

### D5: Cloud accounts — Defer to Phase 11
Multi-account confirmed in design (ADR-0011, handoff §3.3d/e). Exact account counts and
service-account vs OAuth per provider deferred to Phase 11 when Drive/OneDrive MCP servers are
actually wired. Rationale: no code impact until Phase 11; `example.env` already has placeholders.

### D6: n8n role — Driver only, NOT a consumer
n8n calls platform API endpoints (`/v1/...`). It does not consume MCP tools directly. This
means `enable_mcp_server=False` on n8n workflows. Rationale: n8n is the external trigger layer,
not an MCP consumer; keeps the MCP boundary clean.

### D7: Model provider — NVIDIA NIM active default
NVIDIA NIM is the active default provider. Anthropic (`claude-opus-4-8`/`claude-sonnet-4-6`) is a
first-class alternate in `_PINNED` dict. The factory selects by available credentials in fixed
order. ADR-0008's D7 open question is now resolved: NVIDIA NIM primary (per skeleton and current
settings.py), OpenAI key needed only for embeddings if not using NIM embedders (ADR-0010/0011
resolved this: NIM has its own embedders).

## Consequences
- All Phase 0 decisions are locked; Phases 1+ can proceed without ambiguity.
- D5 deferral means Phase 11 must resolve account details before wiring.
- D7 decision updates ADR-0008's "open (D7)" status to resolved.