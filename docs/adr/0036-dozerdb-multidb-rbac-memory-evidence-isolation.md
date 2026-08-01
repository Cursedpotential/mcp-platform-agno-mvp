# ADR-0036: DozerDB multi-database with RBAC-scoped writers (memory vs evidence isolation)

> _Byline: Claude (Opus 4.8, chat) + owner · 2026-07-13 · DRAFT for review_

**Status:** **Accepted & IMPLEMENTED (multi-DB) / BLOCKED UPSTREAM (RBAC)** — owner 2026-07-29 (Proposed 2026-07-13). DozerDB 5.26.27.0 is live on `data-neo4j`; the `memory` and `evidence` databases exist and are isolation-verified. Role-scoped writers are **not implementable** — DozerDB has not shipped its security component. See Outcome.

## Outcome (2026-07-29)

**Engine swap DONE.** `data-neo4j` runs `graphstack/dozerdb:5.26.27.0`, replacing
`neo4j:5-community`. The swap was store-safe because DozerDB publishes the *same upstream
version* that was already running (`neo4j --version` = 5.26.27 on both), so the on-disk format
is unchanged and the existing bind mount reattached with no dump/load. Verified: boot log
prints "Enhanced By DozerDB Plugin"; node/relationship counts identical pre/post (440 / 717);
`grc doctor` OVERALL PASS (Graphiti reads/writes fine). Pre-swap backups on ovh-data
`/data/agno/backups/`: `neo4j_data_pre_dozerdb_2026-07-29.tar.gz` (physical) +
`neo4j_{nodes,rels}_2026-07-29.txt` (logical). Rollback = restore image + redeploy.

**Databases DONE; RBAC NOT AVAILABLE (2026-07-30).**

`memory` and `evidence` both exist and are `online`. Isolation is **proven, not assumed**: a
node written into `memory` returns `count = 0` when queried from `neo4j`, and the working graph
is untouched.

⚠ **SYNTAX GOTCHA — this cost a full investigation, do not repeat it.** DozerDB implements the
*plain* form only:

```cypher
CREATE DATABASE memory          -- ✅ works
CREATE DATABASE memory IF NOT EXISTS WAIT   -- ❌ "Unsupported administration command"
```

The `IF NOT EXISTS` and `WAIT` variants are unimplemented, and the failure message is the
generic *Community-runtime* error `Unsupported administration command`, which reads exactly
like "this edition can't do multi-database at all." That misleading error initially led to the
wrong conclusion that DozerDB doesn't support multi-DB — it does. Always test the plain form
before concluding a feature is missing. (Idempotent scripts must therefore tolerate the
"most likely already exists" error instead of relying on `IF NOT EXISTS`.)

**❌ The RBAC half of this ADR is NOT achievable on DozerDB today.** Role commands are
unimplemented upstream:

```
CREATE ROLE graphiti_writer   -> Unsupported administration command
SHOW ROLES                    -> Unsupported administration command
```

Confirmed by the maintainer on the identical error (DozerDB/dozerdb-plugin#53, and still-open
dozerdb-core#36): *"This will be part of our security component updates this year."*

**What that means for the design.** The wall is **database-scoped, not permission-scoped**:
a `clear_graph`/`DETACH DELETE` aimed at `memory` cannot reach `evidence`, which removes the
blast-radius risk that motivated this ADR. But because every caller still authenticates as
`neo4j` (superuser), the "a stray agent has *no rights* on evidence" guarantee in Consequences
below is **not** in force — a caller that names the wrong database can still write it. Treat
the separation as strong protection against *accident*, not against *authority*.

**Remaining work (phase 2):** migrate Graphiti's existing graph out of the default `neo4j`
database into `memory` and repoint its `database:` config; point Semantica at `evidence`.
Revisit role scoping when DozerDB ships its security component.

**Housekeeping:** a `(:_ProbeNode {k:1})` test node remains in `memory` from the isolation
proof — it is deliberately left (removal is excluded by the operator's own autoMode rule) and
should be cleared during the phase-2 migration.

**Backup note for whoever does phase 2:** Neo4j *Community* (and therefore this DozerDB build,
until the multi-DB features are exercised) has no `db.checkpoint()` procedure and refuses
`STOP DATABASE` — a truly cold file backup isn't available; take a hot tar plus a logical
cypher-shell export, as above.
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
