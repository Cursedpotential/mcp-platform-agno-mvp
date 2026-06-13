# ADR-0014: Pull Graphiti temporal memory forward on Neo4j (not FalkorDB)
- Status: Accepted
- Date: 2026-06-10

## Context
The handoff staged Graphiti (evidentiary temporal graph — "what was true as of when,
and how it changed") for the platform stage, on FalkorDB (one engine later shared with
Semantica's graph store). On 2026-06-10 the owner pulled Graphiti forward and chose
**Neo4j** over FalkorDB.

## Decision
Run **Neo4j community** (heap capped for the 8GB VPS) + the **Graphiti MCP server**
as compose services. Graphiti's entity-extraction LLM and embeddings route through the
**LiteLLM gateway** (`http://gateway:4000`) — no separate provider keys. Agents reach
the temporal graph via `MCPTools` (streamable-http), attached when `GRAPHITI_MCP_URL`
is set; AgentOS manages the MCP lifecycle (no reload).

## Rationale (why Neo4j won)
- Graphiti is Neo4j-first: its best-tested backend, not the late addition.
- Neo4j Browser = visual graph exploration of evidence relationships (court-relevant),
  plus Cypher/APOC ecosystem depth.
- Owner has prior Neo4j work (ADR 015 "Neo4j Direct Access" in earlier iterations).
- FalkorDB's advantages (footprint; future Semantica engine-sharing) are real but not
  decisive: heap caps fit the VPS, and Semantica can get FalkorDB at platform stage if
  needed — Graphiti data migrates.

## Consequences
- Two memory systems coexist by design (handoff §3.2 table): LearningMachine answers
  "what do we know/prefer/plan now"; Graphiti answers "what was true as of when".
- Heaviest single service on the box — heap/pagecache capped in compose; watch RAM.
- ~Platform stage: if Semantica's graph store wants FalkorDB, run it alongside or
  evaluate Semantica's Neo4j support then. Not a blocker now.
