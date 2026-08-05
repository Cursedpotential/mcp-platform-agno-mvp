# ADR-0043 — Semantica as a governed extraction worker (pinned fork); SurrealDB exits the critical path

> _Byline: Claude Code · Fable 5 · 2026-08-02_

- **Status:** Accepted (owner rulings 2026-08-02, recorded verbatim below)
- **Context source:** `docs/HANDOFF-2026-08-02-semantica-platform-review.md`
  (Codex source-level review of upstream Semantica 0.6.0, pinned commit
  `1ad00075a3ac51d764dfc34135980849657641f9`)

## Decision

1. **Semantica's role — governed extraction worker.** It consumes
   custody-approved `NormalizedRecord` inputs and produces source-linked
   CANDIDATES only (entities, relations, events, conflicts, temporal facts,
   ontology-validation results) into `working.*` + provenance. PostgreSQL is
   the canonical control/provenance plane; Neo4j `evidence` and Weaviate are
   rebuildable projections; Graphiti stays the ignorant agent's belief state in
   Neo4j `memory`. The existing PG working projections and normalized tables
   REMAIN, restructured per the review (owner: "we still maintain the pg
   working projection and normalized tables just restructured in the way that
   codex recommended"). Semantica never becomes an intake door, a source of
   truth, or an agent-memory replacement.
2. **Source strategy — pinned fork/image.** Fork at the reviewed commit, build
   our own isolated worker image, patch forensic-hostile defaults (disable the
   last-resort `related_to` adjacency generator), write our own agno-2.8
   adapters (upstream's import four legacy APIs absent from 2.8.x and are
   stub-tested). Upstream merges are deliberate, per the proven house pattern
   (graphiti-mcp custom image; CNF plugin fork with fetch-only upstream).
3. **SurrealDB exits the critical path** — reversible: freeze Surreal-specific
   feature work, export/inventory with counts+checksums, migrate capability by
   capability to PostgreSQL, keep SurrealDB read-only/parked; only the owner
   deletes. (First concrete step already shipped: LearningMachine moved off
   SurrealDb — whose learning methods raise NotImplementedError — to the
   admin-plane PostgresDb, commit 9d4c43e.)
4. **First production slice** = NER + relation/event candidates + provenance +
   SHACL validation — before any reasoning, conflict auto-resolution, dedup
   merging, or agent decision tooling.
5. **Approval granularity** — decided per case as it comes up (owner:
   "not sure yet, ask as it comes up"), with the standing floor from the
   review: evidence and ontology mutations ALWAYS require individual approval;
   nothing automatic overwrites canonical data.

## Consequences

- Phase gates from the review govern the build (Phase 0 contracts → isolated
  worker → extraction validation → Neo4j projection → Weaviate projection →
  agent integration). Each gate's acceptance criteria are in the handoff and
  are the definition of done — config acceptance is never evidence
  (AGENTS.md session learning, 2026-08-02).
- The knowledge-horizon contract binds every retrieval surface this ADR
  touches: dict filters on Weaviate (FilterExpr silently no-ops — AGENTS.md
  §WHY), predicate parity on PostgreSQL/Neo4j, and the planted-future-fact
  contamination test as the proof.
- Bootstrap reproducibility (Codex C-02) is a Phase-0 dependency: the numbered
  migration chain must clean-bootstrap so the candidate/provenance schemas the
  worker writes to are reproducible (executed alongside this ADR: baseline
  capture + reconciliation migrations).

## Alternatives rejected

- **Upstream dependency (even commit-pinned):** broken Agno adapters, fabricated
  low-confidence edges by default, 157-file drift between 0.3→0.6, stub-only
  upstream CI — every reason detailed in the handoff §"Research basis".
- **SurrealDB retained as operational core:** upstream defects outside our
  control; agno's SurrealDb backend lacks the learning protocol entirely.
- **Separate ignorant/hindsight stores:** violates the one-store,
  filtered-per-agent canon (AGENTS.md §WHY).
