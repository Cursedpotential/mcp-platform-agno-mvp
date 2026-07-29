# ADR-0036: DozerDB multi-database with RBAC-scoped writers (memory vs evidence isolation)

> _Byline: Claude (Opus 4.8, chat) + owner · 2026-07-13 · DRAFT for review_

**Status:** **Accepted** — owner 2026-07-29 (Proposed 2026-07-13). Execution/verification per the Open list still pending (deployment state not re-verified at acceptance time).
**Supersedes/relates:** [ADR-0014](0014-neo4j-graphiti-temporal-memory.md) (Neo4j + Graphiti temporal memory), [ADR-0031](0031-casebible-entity-layer-neo4j-graphiti.md) (CaseBible entity layer). Establishes the physical isolation those ADRs assume.

## Context

Two distinct graphs must coexist on Neo4j and must **not** commingle:

- The **memory graph** (Graphiti) — the agent's temporal, evolving cognition (bitemporal: event time vs. learned time). Speculative by nature. Agents read and write it freely.
- The **evidence graph** (Semantica) — entities and relationships extracted from the conformed corpus, provenance-anchored. Derived interpretation of evidence; agents read but never write it.

Neo4j **Community Edition supports exactly one standard database** (`neo4j`); multiple named databases are an Enterprise/AuraDB feature. A single stock Community container therefore **cannot** isolate the two graphs. Options: (a) two Community containers, or (b) one container with a multi-database add-on.

Governing constraints for this deployment:
- Personal Family Court matter (Genesee County, MI), single operator. Evidence reliability rests on **traceability and audit logs**, not on the licensing provenance of the graph engine — so the GPL-fork status of a multi-DB add-on is **not** a reliability concern here.
- No GPU; RAM on the OVH VPS nodes is the scarce resource. A second Neo4j container costs ~1–1.5 GB baseline (heap + pagecache) better spent on LLM extraction and the rest of the stack.

## Decision

Adopt **DozerDB** (GPL plugin/distribution adding Enterprise features — multi-database, RBAC, hardened container — to Neo4j Community) as the Neo4j engine. One instance, **two named databases**:

- `memory` — Graphiti's memory graph.
- `evidence` — Semantica's evidence graph.

Enforce the partition at the **permission layer**, not by convention:
- A `graphiti_writer` role scoped to `memory` only.
- A `semantica_writer` role scoped to `evidence` only.

Graphiti (library + MCP) targets `memory` via its `database:` config; Semantica targets `evidence`. **Pin the DozerDB image version**; test upgrades before applying.

## Consequences

- **Isolation is stronger than two containers**, because it is permission-enforced: a stray `clear_graph` from an agent cannot reach `evidence` — the role has no rights there. The wall is mechanical, not conventional.
- Saves ~1–1.5 GB baseline vs. two containers; one process to operate.
- Adds one pinned-dependency upgrade discipline (DozerDB version).
- RBAC and hardened-container are bonuses on top of the multi-DB requirement.

## Open

- DozerDB version-tracking cadence vs. Neo4j Community releases.
- Per-database backup strategy (part of the traceability/audit-log workstream, tracked separately).
- Confirm Graphiti honors the named-database target on the deployed version (see ADR-0037; Graphiti has a history of named-DB routing bugs — verify writes land in `memory`).
