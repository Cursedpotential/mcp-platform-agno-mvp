# ADR-0031: CaseBible entity / temporal-graph layer = Neo4j + Graphiti, isolated by group_id
- Status: **Accepted (2026-06-23)** — extends ADR-0014 (Neo4j/Graphiti) and ADR-0018 (bitemporal)
- Date: 2026-06-23
- _Byline: Claude Code · Opus 4.8 · 2026-06-23_
- _Handoff 2026-06-25: drafted by the CaseBible ingestion workstream; ownership/maintenance transferred to the platform workstream (owner of this repo). This ADR == the platform plan's "P3 (populate the graph)". File stays in place; revise as you see fit._

## Context
The ingest evidence vertical (custody → parse → store → knowledge, ADR-0017) is implemented and
verified, but the **analysis / mining half is not built** in deployed code: `transcript_insight` has
**no writer** (schema-only), and the `analysis-orchestrator` / `transcript-miner` agents are **toolless
conversational shells** — there is no entity extraction and no knowledge-graph wiring. CaseBible needs
entities and relationships (people, claims, events, dates) out of the evidence, not just chunked text.
The platform already runs **Neo4j 5-community + Graphiti** (`zepai/knowledge-graph-mcp`) on ovh3
(MCP at `100.119.96.29:8071`, healthy) per ADR-0014.

## Decision
Use the existing **Neo4j + Graphiti** stack as CaseBible's entity / temporal-knowledge layer rather than
building a custom extractor. CaseBible content (the evidence vertical's `normalized_record`s / rendered
transcripts) is fed to Graphiti as **episodes** under a dedicated **`group_id = "casebible"`** for
subgraph isolation; Graphiti's LLM extraction yields **entities + temporal facts** into Neo4j, which the
bitemporal substrate (ADR-0018) and any agent can query (`search_memory_facts` / `search_memory_nodes`).
This is the concrete realization of the "analysis/entity" half left unbuilt.

## Consequences
- Entity resolution and temporal relationship facts become queryable across CaseBible evidence,
  graph-isolated from other `group_id`s (no cross-contamination with platform/other graphs).
- The dedicated CaseBible ingestion resource (ADR-0029) gains a **post-store step**: after
  `normalized_record`, push the conversation/record to Graphiti `add_memory`.
- Obligation: manage Graphiti's LLM extraction cost on bulk ingest (entity extraction is per-episode LLM
  work); scope/throttle on large domains. `transcript_insight` remains optional — Graphiti's fact graph
  is the primary entity store; a thin projection into `transcript_insight` can follow if a relational
  view is wanted.

## Alternatives considered
- **Build a custom entity extractor / wire `transcript_insight`** — rejected: Graphiti is off-the-shelf
  and already deployed (ADR-0021 minimize-custom; ADR-0014 chose Neo4j/Graphiti for exactly this).
- **Use the platform's `analysis-orchestrator` / `transcript-miner` agents** — rejected: not implemented
  (toolless shells); they would need tools built before they could do anything.
- **A separate CaseBible-dedicated Neo4j** — deferred: the shared ovh3 Neo4j with `group_id` isolation is
  sufficient and avoids standing up duplicate infra.
