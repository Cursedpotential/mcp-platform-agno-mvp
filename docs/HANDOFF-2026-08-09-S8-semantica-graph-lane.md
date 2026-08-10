# HANDOFF S8 — Semantica graph lane (currently NOT wired)
> _2026-08-09 · repo @ a68fabd · STATUS: BLOCKED until S6 lands visible_from · Depends: S5, S6 · Blocks: S9 via tasks 1–6 only; task 7 (backfill) runs AFTER S9 task 1 — no cycle_
> MANDATORY: read PLAN-2026-08-09-completion-master.md §Standing constraints before executing.
> Inventory items: R-4, F-G (preserve), DA-10, SD-5 boundary. Verified 2026-08-09: Semantica fully
> vendored (server/vendored/semantica: triplet_extractor, coreference_resolver, kg/graph_builder,
> graph_store/neo4j_store) but ZERO production callers — only semantica_wiring.py (config dicts) and
> a smoke script. Only graph writer today = AI-chat lane via GraphitiCaseClient. Evidence records
> never reach Neo4j. This is unbuilt canon §6 P3 roadmap, not drift.

## Goal
Stand up the governed Semantica extraction worker (ADR-0043, locked): canonical factual graph
populated from evidence, horizon-blind at extraction, horizon-filterable at derivation.

## Tasks
1. Worker slice: compose service under NEW profile `analysis` (new `compose.semantica.yaml`) +
   entrypoint `server/analysis/semantica_worker.py` wiring
   server/vendored/semantica pipeline (semantic_extract → kg/graph_builder → graph_store.neo4j_store)
   using semantica_wiring.full_wiring() config (already points at ovh-files). Batch-driven, resumable,
   idempotent (re-run on same base_version → same graph).
2. [F-G] Extraction reads `working.normalized_record` UNFILTERED — extraction is horizon-blind by
   invariant; Semantica forms no beliefs. Any horizon logic in this worker is a defect.
3. [DA-10] Assertions carry provenance + time: every triplet/assertion node links its source
   record id and carries that record's `visible_from` (and occurred_at); entity nodes are identity
   anchors only (no knowledge content) — the assertions are what pass derivations filter.
   Targets the Neo4j `evidence` DB under DozerDB isolation (ADR-0036: database-scoped wall;
   memory DB untouched).
4. Graphiti boundary (SD-5): the worker writes the FACTUAL graph (Neo4j evidence DB via Semantica
   graph_store). It does NOT write Graphiti belief groups — those belong to walking agents (S6).
   Where Graphiti-side entity extraction duplicates Semantica's (context lane), document the
   boundary in server/analysis/AGENTS.md-level docstrings: context lane → Graphiti's own
   extraction; evidence lane → Semantica.
5. Audit hooks: every worker write → ops.audit_ledger (`write`, actor=semantica-worker, batch ref,
   base_version). Worker runs are derivation-ADJACENT but factual-layer writes — action_type
   `write`, not `derivation`.
6. Graph-side derivation: extend server/analysis/derivation.py (S6) with the graph lane — a pass's
   graph view = assertions where visible_from <= horizon (same single predicate function), used by
   walking agents' retrieval. Reads → ledger.
7. Backfill: once S9 population lands (D-008-gated), run the worker over the full corpus; record
   corpus-size + assertion counts in a dated report.
8. Tests: fixture corpus → deterministic assertion set; provenance links resolve; horizon-blind
   check (worker output identical regardless of any HorizonContext in env); DozerDB isolation
   (worker credentials cannot touch `memory` DB).

## Acceptance
`docker compose --profile analysis up semantica-worker` processes the fixture corpus; Neo4j
evidence DB contains provenance-linked, visible_from-stamped assertions; re-run is idempotent;
graph reads through the derivation lane respect a test horizon; all writes/reads in the ledger.

## Constraints
Standing constraints per PLAN master. Semantica is VIP — wire it, never fork it. Extraction
horizon-blind (F-G). Neo4j evidence/memory isolation per ADR-0036. Graphiti extraction LLM rules
per ADR-0039 apply to any LLM the worker invokes (hosted structured-output only).
