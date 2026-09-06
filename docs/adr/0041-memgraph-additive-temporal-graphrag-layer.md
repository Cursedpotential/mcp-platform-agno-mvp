# ADR-0041: Memgraph as an ADDITIVE temporal GraphRAG layer (Neo4j/DozerDB stays)

> _Byline: Claude Code · Fable 5 · 2026-07-27_

**Status**: ACCEPTED (owner "go" 2026-07-28): **Variant B (classic Memgraph projection) is the decision**; Variant A (MemGQL federation) demoted to parked experiment — see 2026-07-28 addendum. ~~Orchestration settled Agno-native.~~
> **SUPERSEDED IN PART — 2026-09-06 (D-143).** The Agno-native orchestration premise was retired by D-107. **LlamaIndex is IN as the retrieval/indexing library (a dependency, not a permission) and LangGraph is IN as the deterministic retrieval state machine** (Temporal Activities / n8n agent nodes). The sentence below, "LangGraph only reconsidered if a control-flow need arises," no longer applies. Everything else in this ADR (Memgraph additive layer, Variant B) stands. _Claude Code · Fable 5.1 · 2026-09-06._
**Relates**: ADR-0036 (DozerDB memory/evidence isolation), ADR-0037/0038 (Graphiti), ADR-0032 (Surreal analysis sink)

## Context

Owner (2026-07-27) wants "a real temporal graph RAG" and proposes Memgraph — explicitly **layered on top of the current storage infrastructure, not replacing it**. Neo4j/DozerDB stays: Semantica is semi-hard-coded to Neo4j (locked decision 2026-07-13 #14) and Graphiti's officially supported backends are Neo4j/FalkorDB/Kuzu/Neptune — Memgraph is not on that list, so it must NOT become Graphiti's store.

## Decision (proposed)

Memgraph enters read-side only, never as a system of record. Two variants, A preferred pending evaluation:

**LICENSING GATE PASSED (2026-07-27): MemGQL Community is FREE** — includes GQL→Cypher and
GQL→SQL translation, Bolt interface, all eight connector types, multi-connection mode, and an
**MCP server** (which slots directly into the Agno-native tool plan). Variant A is GO.

**Variant A — Memgraph Zero (federated, zero-ETL).** Owner-surfaced 2026-07-27
(memgraph.com/docs/memgraph-zero): MemGQL federated engine queries data *in place* across
PostgreSQL, DuckDB, Neo4j (and others) — exactly this stack. No sync job, no copy, no
staleness; GQL over the live bitemporal PG rows + both Neo4j graphs at once. Open before
adoption: licensing/pricing (docs don't state it — likely commercial), maturity, whether
MAGE algorithms and vector search apply to federated data or only native storage, and
DozerDB-vs-Neo4j connector compatibility.

**Variant B — classic Memgraph as analytical projection** (fallback if Zero's licensing or
maturity disqualifies it):

- **Source of truth unchanged**: evidence graph (Semantica→Neo4j `evidence` DB), memory graph (Graphiti→Neo4j `memory` DB), rows in PG (`working.normalized_record`).
- **Projection pipeline**: a one-way sync job materializes selected subgraphs + temporal edges (valid_from/valid_to from the bitemporal record) into Memgraph. Rebuildable from scratch at any time — Memgraph being in-memory-first is acceptable *because* it holds only derived data.
- **What Memgraph buys**: MAGE algorithms (community detection, PageRank, dynamic/streaming algos), deep path traversals (WSP/ASP/KSP with filter lambdas), vector search (2.22+), and hybrid GraphRAG retrieval per the memgraph-graph-rag blueprint — i.e., the cycle-detection / antecedent-reconstruction analysis lane gets a fast graph-compute engine without touching evidence stores.
- **Orchestration (settled 2026-07-27)**: **Agno-native** — everything still ties into Agno; no
  second agent framework. Memgraph GraphRAG retrieval is built as **thin MCP tools** (per the
  memgraph-graph-rag tool-contract blueprint) that Agno agents consume like every other tool.
  **LlamaIndex is permitted as a library inside those tools** (retrievers/query engines wrapped as
  functions) where it earns its keep; LangGraph only reconsidered if a control-flow need arises
  that Agno cannot express.

## Addendum 2026-07-28 — Variant B chosen; MemGQL parked

> _Byline: Claude Code · Fable 5 · 2026-07-28_

**Re-decision (owner "go" 2026-07-28): Variant B — plain Memgraph Community (`memgraph/memgraph-mage`) as a materialized analysis graph — is the accepted path. Variant A (MemGQL) is KILLED entirely** (owner 2026-07-28): `data-memgql` Coolify app deleted, `deploy/data-memgql.yaml` compose remains only in git history for reference. Not an experiment, not parked — removed from the architecture.

Why the flip:

1. **License limit surfaced**: MemGQL Community caps at **2 connectors and 2 simultaneous connections** (Enterprise lifts it; owner policy is free-tier). The 2-connection cap would bite under concurrent Agno agents.
2. **Wrong tool for the actual workloads.** Owner requirements expanded (2026-07-28) beyond cycle detection to: **isolation/targeted-alienation trajectories** (windowed contact-degree trends per person-set, before/after incident anchors), **community detection** ("my people / her people" via Louvain/Leiden), **bridge-node analysis** (betweenness; bridge-cutting over time), and **anomaly mapping** (entities/edges that fit no community, coordinated-timing bursts). These are whole-graph MAGE algorithm workloads — federation cannot run them; only a materialized graph can.
3. **DuckDB is embedded in PG** (pg_duckdb — owner correction 2026-07-28). There were only ever two upstreams (PG, Neo4j); the projection sync job reads DuckDB-resident data through the same PG connection. No funnel work needed.

Additional guardrails from this round:

5. **Temporal axis**: project **event time** (valid_from/valid_to) onto graph edges; record/ingest time stays in PG. Provenance record-ids (guardrail 2) give the full bitemporal story one hop away. Decided early because re-projection = wipe + re-sync + re-validate every query.
6. **Identity spine is a prerequisite**: one human = one node across phone/email/platform identities (`normalize.py` entity-key stamping) before the projection job runs, or community/centrality results are garbage.
7. Sync job is idempotent (Cypher MERGE), incremental, and rebuild-from-scratch capable; graph is a disposable derived artifact.

## Guardrails

1. Memgraph is derived-only; no writer other than the projection job. Losing it loses nothing.
2. Provenance pointers (record ids / evidence hashes) travel into every projected node/edge — GraphRAG answers must cite back to PG rows.
3. RAM budget check on the target node before deploy (in-memory engine on VPS-class hardware; start with a bounded projection, not the whole corpus).
4. Empirical smoke test of the Bolt driver + Cypher dialect differences (Memgraph ≠ Neo4j on some syntax) before any tooling is wired.

## Consequences

- Temporality itself still comes from Graphiti's bi-temporal model + the bitemporal `normalized_record`; Memgraph adds compute and retrieval speed over that, not the temporal semantics.
- One more container in Coolify (own app per the 2026-07-05 owner mandate) + Memgraph Lab optional.
- Memgraph official Claude skills installed at user level (2026-07-27) to support this work.
