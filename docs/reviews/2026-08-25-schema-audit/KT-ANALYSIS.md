# Kepner-Tregoe board — schema audit, night of 2026-08-25

> _Byline: Claude Code · Fable 5 · 2026-08-25 03:30. Companion to `REVIEWED-PLAN.md`; rulings in `docs/DECISION_LOG.md` (D-069/070/071). Assessment only — nothing here is built._

## SA — concerns, prioritised (Timing · Impact · Trend)

| # | Concern | Timing | Impact | Trend | Pri | Process |
|---|---|---|---|---|---|---|
| 1 | Custody gap: D-069 retires ingest-time custody; the promotion→`evidence.*` writer does not exist yet | before any new ingest | critical | widens per ingest | **P0** | PPA (below) |
| 2 | Rejected shapes re-surface in generated docs | next generator run | high | recurring | **P1** | PA (below) |
| 3 | Memory-write target after D-070 undefined | next session that records | high (silent stall, cf. 2026-08-05) | stable until it bites | **P1** | DA (below) |
| 4 | `compose.yaml` → `deploy/compose.yaml` move, uncommitted | next Coolify deploy | med–high if base-dir is root | stable | P2 | owner rules |
| 5 | `analytics/visit-locations` deleted from Agno tree (copy in `Projects/traceIQ/traceiq-rebuild/`) | next Agno commit | low | stable | P3 | owner rules |
| 6 | Graph engine: Cognee vs Memgraph | not yet | medium | stable | P3 | DA later, needs data |

## PA — why rejected proposals resurface

**Deviation:** shape rejected 03:07 was still rendered as "the merge I recommend" and read by the owner 03:25.

| | IS | IS NOT | Distinction |
|---|---|---|---|
| What | generated HTML (`build_shapes.py`) | `REVIEWED-PLAN.md`, `DECISION_LOG.md` | generators don't read the log |
| Where | Section C prose + delta table | Sections A/B (catalog-driven) | only *opinion* drifted |
| When | built ~03:00; rulings 03:02–03:10; crash 03:12 | not before the audit | ruling landed between generate and regen |
| Extent | 1 page, ~8 literal strings | `catalog.json`, reckoning page | only hand-written prose in code |

| Candidate cause | Explains IS | Explains IS-NOT | Verdict |
|---|---|---|---|
| agent ignored ruling | ✗ (ruling was logged) | — | ruled out |
| crash prevented regen | ✓ | ✗ | contributing |
| opinion hard-coded, facts data-driven | ✓ | ✓ | **root cause** (verified: every string changed 03:20 was a literal) |

**Fix (not built):** opinion sections rendered from `DECISION_LOG.md` rows (`owner-ruled` + rejected/stay/kept) as a "Ruled — do not re-propose" strip on every page. No new register file — one source of truth.

## DA — interim memory write target (concern 3)

MUSTs: exists today · reachable from desktop and ovh · already an approved lane · not Graphiti (D-070).

| Alternative | MUSTs | Note |
|---|---|---|
| SurrealDB (ADR-0056) | PASS | governed projection + walk memory already designed |
| auto-memory `MEMORY.md` only | PASS | flat; no entity/relationship lane |
| wait for Cognee/Memgraph | FAIL | the "hole" scenario |
| keep Graphiti quietly | FAIL | D-070 |

**Recommendation:** SurrealDB is the interim write target; one-line D-070 amendment. Cognee vs Memgraph not scorable honestly without throughput/ops numbers on this stack — do not fake weights.

## PPA — D-069 sequencing plan (concern 1)

| # | Potential problem | P | S | Preventive | Contingent · trigger |
|---|---|---|---|---|---|
| 1 | ingest runs after ingest-time custody is retired but before backfill (step 4 before 3) | M | critical | step 4's migration **asserts** backfilled `evidence.*` count ≥ existing raw count | any `evidence.*` count < promoted-row count → halt, replay promotion |
| 2 | promotion references the *live* context row; a re-derive changes the fingerprint that was verified | H | critical | promotion **stores the H1/H2 it verified** on the `evidence.*` row | fingerprint mismatch on read → row flagged, never silently trusted |
| 3 | `ALTER TABLE … SET SCHEMA` on `evidence.raw_*` breaks `vw_layer_map` / `vw_raw_all` / `vw_pipeline_funnel` / derivation reads | H | high | same migration repoints all four; add a **view-compiles** assertion to the freshness test (it checks columns, not views) | red test → migration rolled back in the same transaction |
| 4 | two H2 canons (`h2-canonical-v2` vs `h2-rawelement-v1`) collide during backfill | M | high | distinct tags + crosswalk **before** step 3 — promoted from "record, do not fix" to prerequisite | duplicate tag in `canon_registry` → stop |
| 5 | session crash mid-migration | L | high | one migration per step, apply-check-rollback first (standing rule) | `.remember` + DECISION_LOG on disk before any DDL |

**Monitoring to add before step 3:** view-validity assertion in `tests/test_schema_docs_current.py`; invariant `count(evidence.*) ≥ count(promoted)`.

## Deltas vs `REVIEWED-PLAN.md`

- Two new guards: fingerprint pinning at promotion (PPA-2); view-compiles check (PPA-3).
- H2 canon collision moves from "canon debt, record only" to **prerequisite for step 3** (PPA-4).
- Interim memory target for D-070 recorded as a gap needing a one-line ruling.
