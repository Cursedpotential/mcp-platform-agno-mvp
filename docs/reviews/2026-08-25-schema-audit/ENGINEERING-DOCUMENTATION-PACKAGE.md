# Engineering Documentation Package

This is the entry point for the whole-system reconciliation documentation created from the 2026-08-25 schema audit and owner rulings D-069 through D-085.

The package describes the intended product as a controlled replay system—not a set of tables.
PostgreSQL is the canonical authority and change-event control plane; Weaviate, Neo4j and SurrealDB
are specialized rebuildable surfaces; SurrealDB is the final governed temporal-graph aggregation
and walk engine. **Agno is a replaceable orchestration/runtime adapter and owns no product truth.**

## Start here

| Document | Purpose |
|---|---|
| [Complete codebase audit](COMPLETE-CODEBASE-AUDIT.md) | Repository-backed evaluation, dated read-only live snapshot, discovery limitations, principal findings and stop gates |
| [Audit gap register](AUDIT-GAP-REGISTER.md) | Deduplicated severity-ranked gaps, exact evidence and acceptance gates |
| [Whole-system conceptual model](WHOLE-SYSTEM-CONCEPTUAL-MODEL.md) | Canonical objects, semantic layers, cardinalities and authority boundaries |
| [System architecture](SYSTEM-ARCHITECTURE.md) | End-to-end diagrams, state transitions, sequences and store responsibilities |
| [Cross-domain contract matrix](CROSS-DOMAIN-CONTRACT-MATRIX.md) | Exact handoffs, envelope fields, eligibility rules, clocks and completeness equation |
| [Reconciliation workstreams](RECONCILIATION-DOMAIN-WORKSTREAMS.md) | R00–R14 scope split, dependency DAG and ownership model |
| [Reconciliation runbook](RECONCILIATION-RUNBOOK.md) | Program waves, gates, failure handling and final acceptance trace |
| [Agent handoff protocol](AGENT-HANDOFF-PROTOCOL.md) | No-dropped-fields rules, completion packets and escalation triggers |
| [Provisional physical model](PROVISIONAL-PHYSICAL-MODEL.md) | Target physical schema concepts without authorizing migrations |
| [Temporal/n8n workflow and gaps](TEMPORAL-N8N-WORKFLOW-AND-GAPS.md) | Durable execution boundary, hashing Activities and current runtime gaps |

## R00–R14 implementation guides

| Lane | Guide | Primary outcome |
|---|---|---|
| R00 | [Canon and contract freeze](reconciliation-domains/R00-canon-contract-freeze.md) | Freeze vocabulary, authority, canons and inter-domain contracts |
| R01 | [PG backbone, CDC and receipts](reconciliation-domains/R01-pg-backbone-cdc-receipts.md) | Establish PG as canonical control plane with append-only outbox/receipts |
| R02 | [Context ingest and parser boundary](reconciliation-domains/R02-context-ingest-parser-boundary.md) | Make all intake context-first and parser-neutral |
| R03 | [Normalization, messages and clocks](reconciliation-domains/R03-normalization-messages-clocks.md) | Preserve source semantics, participants and distinct clocks |
| R04 | [Hashing, custody and promotion](reconciliation-domains/R04-hashing-custody-promotion.md) | Separate provisional hashing, verified promotion and reverification |
| R05 | [Weaviate search](reconciliation-domains/R05-weaviate-search.md) | Build exact-source, governed and horizon-prefiltered retrieval |
| R06 | [Semantica and Neo4j](reconciliation-domains/R06-semantica-neo4j.md) | Govern extraction candidates and source-anchored relationship projections |
| R07 | [Governed facts and realizations](reconciliation-domains/R07-governed-facts-realizations.md) | Establish immutable facts, support and plural realization histories |
| R08 | [PostGIS and modalities](reconciliation-domains/R08-postgis-modalities.md) | Preserve canonical multimodal/geo data and governed projection rules |
| R09 | [Cross-store reconciliation](reconciliation-domains/R09-cross-store-reconciliation.md) | Independently reconcile manifests, receipts, cursors and activation |
| R10 | [Surreal aggregation](reconciliation-domains/R10-surreal-aggregation.md) | Build final governed temporal-graph projection from PG-authorized inputs |
| R11 | [Walks and paired delta](reconciliation-domains/R11-walks-paired-delta.md) | Execute reproducible ignorant/hindsight walks and their delta |
| R12 | [Legal and Workbench](reconciliation-domains/R12-legal-workbench.md) | Expose only active governed, citation-resolvable conclusions |
| R13 | [Temporal and n8n execution](reconciliation-domains/R13-temporal-n8n-execution.md) | Divide visual/business choreography from durable execution correctly |
| R14 | [Migration, cutover and integration](reconciliation-domains/R14-migration-cutover-integration.md) | Own cross-lane gates, reader cutovers and final end-to-end proof |

## Reading paths

### Architecture or owner review

1. Whole-system conceptual model
2. System architecture
3. Cross-domain contract matrix
4. Reconciliation workstreams
5. Reconciliation runbook

### Lane implementation agent

1. Project canon and decision log
2. System architecture
3. Cross-domain contract matrix
4. Assigned Rxx guide
5. Agent handoff protocol
6. Closest applicable `AGENTS.md`

### Integration and cutover review

1. Reconciliation runbook
2. R09 cross-store reconciliation
3. R14 migration/cutover/integration
4. Completion packets from every upstream lane

## Status legend

The architecture documents specify target contracts; the audit documents certify repository state
and record a limited, dated, read-only live snapshot. After the 2026-08-26 challenge pass, the audit
is deliberately labeled an evaluation rather than exhaustive file-level certification because CCC
coverage/freshness is incomplete and the handoff-required DuckDB repository-catalog step is not
evidenced. The documents do not claim the target is implemented or production-certified. Current
runtime capabilities and gaps are called out in the relevant guide. No migration, deployment,
database mutation or destructive cleanup is authorized merely by inclusion in this package.
