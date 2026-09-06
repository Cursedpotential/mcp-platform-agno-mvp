# HANDOFF INDEX — mcp-platform-agno-mvp remediation

> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

Repo: `Cursedpotential/mcp-platform-agno-mvp`
Compiled: 2026-08-31
Source: full-tree audit (4,027 tracked files, 166 MB) + ADR/DEBT review

## How to use this set

One handoff = one agent = one conversation. Do not merge handoffs. Do not let an
agent working H-03 touch H-05 files. Each handoff is self-contained: it repeats
the evidence it needs so no agent has to read the others.

**Every handoff carries the same two invariants. They are non-negotiable and
appear verbatim in each file.**

## Global invariants (repeated in every handoff)

1. **Go `engine/uiw` is the only writer of custody receipts, raw generations,
   normalized generations, and lineage.** No Python module writes custody rows.
2. **PostgreSQL is canonical authority** for evidence, custody, claims,
   approvals, promotion decisions, and audit records (ADR-0056 D-1). Weaviate,
   Neo4j/Graphiti, and SurrealDB are rebuildable projections, never authority.

## Do-not-touch list (global)

Resist "simplifying" any of these. Each exists so the pipeline can prove what it
did, not merely produce a good answer.

- `engine/stagegraph/` DAG and its `DependsOn` edges
- Parser/chunker selection receipt contract (`engine/parser/registry.go`,
  `engine/chunk/registry.go`) — immutable `Selection` snapshot before execution
- H1/H2/H3 custody hash naming and its separation from normalized digests
- `sql/0017_append_only_guards.sql`
- The no-bypass horizon gate in `server/evidence/retrieval.py`
- Coverage reconciliation stages: `reconcile_record_accounting`,
  `reconcile_byte_coverage`, `verify_raw_coverage_against_source`

## The set

| # | Handoff | Type | Blocks / Blocked by |
|---|---|---|---|
| 01 | Custody path unification (Python parsers → n8n seam) | Build | Blocked by 02 (tests first) |
| 02 | Contract-test enforcement harness | Build | Blocks 01, 09 |
| 03 | `agno_app` role cutover | Ops | Independent — do first |
| 04 | Native evidence vector cutover (`EvidenceChunkV1`) | Ops | Blocks 05 step 2 |
| 05 | Retrieval seam: PG anchor + evidence packet | Build | Partially blocked by 04 |
| 06 | Semantica activation | Ops | Independent |
| 07 | pg_duckdb utilization | Build | Blocked by 01 |
| 08 | Status single-source-of-truth + DEBT correction | Docs/Build | Blocks 11 |
| 09 | Documentation and repo hygiene | Docs | Independent |
| 10 | Repo topology (forks, vendored, compose taxonomy) | Ops | Coordinate with 11 |
| 11 | SurrealDB analytical aggregation surface | Docs/Design | Coordinate with 08, 10 |

## Recommended execution order

**Wave 1 (parallel, no dependencies):** 03, 08, 09, 11
**Wave 2:** 02, 10, 06
**Wave 3:** 01, 04
**Wave 4:** 05, 07

## Corrections carried into this set

Two findings from the initial audit were wrong or incomplete and are corrected
inside the relevant handoffs. They are listed here so no agent re-introduces the
original error.

- **CORRECTION A (see H-11):** SurrealDB is NOT a denied path. ADR-0056 is
  Accepted; ADR-0032 already established `PG → Surreal` as the analysis sink.
  Only the *legacy parked deployment* is denied; the *new disposable target* is
  gated at D3/D4. Earlier advice to "move the Surreal compose files out of
  `deploy/`" is RESCINDED.
- **CORRECTION B (see H-01):** The n8n parser seam was not a missing design. It
  is fully built and production-wired in Go. The gap is narrow and lives on the
  Python side of one boundary. Do not redesign the seam.
