# HANDOFF — R2 Temporal Truth and Horizon Engine (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
STATUS: PARTIAL
BUILD_STATUS: UNKNOWN

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| Product invariant | The ignorant agent walks advancing knowledge horizons; the hindsight delta is the deliverable |
| Existing predicate | PostgreSQL horizon visibility exists and is unit-tested |
| Wave-1 state | Uncommitted realization/derivation migrations and writers exist but have the R0 defects |
| Store rule | Horizon constraints must apply before ranking/traversal in PostgreSQL, Weaviate, and Neo4j |

## Findings / work done

- A run needs an immutable manifest, not a live query against a mutable corpus.
- Each entry must pin content/retrieval hashes, clocks, disclosure result, activation step, provenance, and policy version.
- Pending realization proposals must quarantine the fact from the as-lived view until resolved.
- Approval, rejection, and correction are append-only decisions; correction must not silently move visibility earlier.
- Rewalk/rebatch create new run versions and never mutate historical walks.

## UNRESOLVED (mandatory)

- Final schema names and whether unsafe Wave-1 migrations are replaced or amended before first application.
- Exact treatment of uncertain/interval knowledge times in activation scheduling.
- Storage strategy for large manifest membership lists.

## Pending owner decisions

- Adopt immutable manifests — WHAT: materialize membership and first activation per run · WHY: reproducibility after later ingestion · APPROACHES: live predicates, snapshots, event-log reconstruction · SHORTCOMINGS: manifests consume storage. Recommendation: content-addressed manifest entries with incremental activation records.

## Next steps (work in order)

1. Freeze `horizon_run`, `horizon_step`, `horizon_manifest_entry`, and `horizon_retrieval` contracts.
2. Repair realization proposal/decision semantics.
3. Implement full retrieval-affecting version hashes.
4. Add old-run-after-new-ingestion replay tests.
5. Implement store predicate compilers and future-fact canaries.
6. Bind agents exclusively through the Horizon Context API.

## Owner working-style contract

- The horizon is the project’s highest-priority invariant; contamination fails silently and must be tested adversarially.
