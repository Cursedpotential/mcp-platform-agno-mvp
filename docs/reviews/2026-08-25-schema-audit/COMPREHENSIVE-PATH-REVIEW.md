# Comprehensive Path Review — Old Code vs Corrected R00–R14 Direction

Date: 2026-08-26  
Status: completed documentation/code evaluation; no production or runtime mutation  
Verdict: **the corrected direction is right (8/10), but physical design and acceptance thresholds
must close before implementation or production claims.**

Preferred reading format: [COMPREHENSIVE-PATH-REVIEW.html](COMPREHENSIVE-PATH-REVIEW.html).

## Plain-English answer

Yes—we are now heading in the right direction.

The old system has useful pieces, but many of them can write or retrieve data without crossing one
clear authority boundary. Evidence custody starts too early, agents can obtain generic database
write tools, external stores can be reached outside the governed retrieval path, and the current
walk code does not produce the paired “what I believed then versus what I know now” result.

The corrected plan fixes those problems by making PostgreSQL the place that authorizes and records
every important transition. Weaviate, Neo4j and Surreal still do the work they are good at, but none
of them gets to silently invent truth. Surreal executes the temporal walks; PostgreSQL preserves the
versioned inputs, checkpoints, beliefs, receipts, pair and delta so the result can be audited and
rebuilt. R09 checks every projection before Surreal receives it. R14 independently proves the whole
path before cutover.

The remaining items are normal engineering closure work: choose a few explicit defaults, finish
the physical tables/contracts for the later lanes, decide how much identity-resolution history to
retain, and set measured performance/retention thresholds. They are addressable without changing
the architecture.

## Old code compared with the corrected path

| Old/current behavior | Why it is unsafe or incomplete | Corrected path |
|---|---|---|
| Evidence intake writes custody before parsing/promotion (`server/evidence/custody.py:277-328`) | A failed or unselected ingest can become evidence state | R02 lands context only; R04 is the sole atomic promotion/custody writer and independently verifies H1/H2/H3 |
| Promotion trusts an existing H1 and does not prove the full normalized H2/H3 generation (`server/case_management/repository.py:643-659,793-895`) | Custody does not prove the selected normalized content and complete ordered generation | Typed hash manifests and ordered members are recomputed and verified before an atomic promotion finalizer accepts custody |
| Agno agents receive generic write-capable database tools (`server/agents/providers.py:147-192`) | An orchestration adapter can bypass approval, idempotency and receipts | Agno submits typed platform commands only; least-privilege roles deny generic mutation |
| Weaviate/Graphiti can be reached directly and some stores accept anonymous/unauthenticated access | Callers can bypass horizon filters and audit receipts | Every store is identity-gated; horizon/source eligibility is applied before ranking/traversal; direct bypass tests must fail |
| Projection acknowledgements and local files substitute for a universal reconciliation authority | Surreal can receive incomplete, stale or orphaned material | R09 owns immutable PG receipts/manifests and blocks admission on count/hash/membership drift |
| Synthetic Surreal proof is useful but not production aggregation | It does not consume a PG-authorized manifest or return complete receipts | R10 consumes only an authorized R09 manifest and returns PG projection/observation receipts |
| Current walk derivation does not execute paired agent walks or preserve canonical belief/delta state | The primary deceit/realization deliverable is absent and cannot be reproduced | R11 runs as-lived and hindsight walks in Surreal while PG retains canonical lifecycle, checkpoint, belief, pair and delta ledgers |
| Workbench/legal surfaces can reach legacy or insufficiently governed material | Legal output may not resolve to established facts and custody-backed spans | R12 requires versioned work products, typed citations, reviews/releases and consumption acknowledgements |
| Legacy and new writers could run side by side as authors | Dual-run can create two incompatible truths | R14 Gate 3 now has a sole-writer fence matrix; shadow paths may emit comparison receipts but cannot author truth |

## Corrections made during this review

The review found and corrected target-document defects that could have misdirected implementation:

1. Removed Surreal-only canonical walk/belief/delta state; PG retains the auditable ledgers.
2. Replaced mutable-view admission to Surreal with immutable, versioned R09 manifests and members.
3. Changed nullable outbox uniqueness to structured identity plus `NOT NULL UNIQUE` idempotency.
4. Replaced polymorphic realization target IDs with typed FK relations and a deferred completeness gate.
5. Added enforceable ordered H2 membership for H3 generation verification and mandatory custody links.
6. Added promotion/custody/source-clock/projection-generation fields to embedding authority.
7. Added relation-candidate identity and typed source anchors for Neo4j edge provenance.
8. Expanded R12 from one export table to full work/product/version/assertion/citation/release ledgers.
9. Replaced blanket legacy drop lists with per-object R14 census, migration, reconciliation, rollback and owner gates.
10. Added the R14 sole-writer fence matrix before producer activation.
11. Reconciled D-072 throughout the current models: one owner, one personal case, no Matter→CourtCase hierarchy.
12. Corrected audit wording, CCC/DuckDB limitations, integration-test counts, vector-route nuance and classification HITL behavior.
13. Permanently fenced AI-chat authority in the target model: chat produces typed candidates,
    investigation items and created works, never evidence.
14. Added the maintained Timesketch-fork target with immutable PG projection generations and
    candidate/governed authority labels.
15. Added governed individual/bulk round-trip context curation and context amendment candidates for
    every proposed change to an evidence-approved entry.

## Remaining closure decisions and proposed answers

These are bounded decisions. The proposals below preserve the product intent and should be ratified
in R00 before DDL or implementation handoffs.

### CR-001 — AI-chat authority — resolved by D-082/D-083

**Owner ruling:** AI chat is permanently context-only and never evidence. It produces typed claim/
event candidates, investigation leads/evidence needs, observation candidates, strategy candidates,
and immutable created-work versions. Claim/event candidates enter the claim chart/list and drive an
independent evidence search. Chat lineage contributes zero evidentiary support.

### CR-001A — Timeline product and editing — resolved by D-084/D-085

**Owner ruling:** use a maintained Timesketch fork as the timeline and bulk-curation service. It shows
both any-context candidates and evidence-approved timeline entries with explicit authority. Every edit
round-trips through a version-bound PG context command. A proposed change to an approved entry becomes
a context amendment candidate; the approved version remains unchanged until re-review/reconciliation
creates a governed successor.

### CR-002 — Realization targets

**Proposed answer:** permit realization events to target exact normalized record versions, source
spans, claim candidates and established facts. Use separate typed target relations with real foreign
keys and require at least one target at commit.

### CR-003 — Delta durability and legal eligibility

**Proposed answer:** make the paired delta durable and version-pinned in PostgreSQL while Surreal
executes the comparison. A delta item may remain analytical without a fact anchor, but it cannot be
court-eligible unless it resolves to at least one established fact and exact custody-backed citation.

### CR-004 — Participant/entity resolution history

**Proposed answer:** preserve verbatim sender/recipient/participant data permanently and make entity
resolution append-only before resolved identities can influence a governed fact or legal output.
Each assertion records actor/method/confidence/time/supersession. A nullable current entity FK may be
a cache, never the history.

### CR-005 — R09–R14 physical families

**Proposed answer:** complete and review the physical manifest/member/reconciliation, Surreal
projection receipt, walk/belief/pair/delta, legal product/citation, and migration/cutover/rollback
families described by the lane guides. `UNIFIED-PHYSICAL-MODEL.md` remains visibly blocked until
those contracts have enforceable keys, clocks, foreign keys and append-only lifecycles.

### CR-006 — Capacity, retention and performance

**Proposed answer:** do not guess permanent thresholds. Before production cutover, benchmark a
representative corpus and ratify: outbox/receipt partitioning, dead-letter retention, pgvector index
strategy, reconciliation batch size, projection-lag objective, walk latency/cost budget, soak period
and rollback threshold. R14 records the measured values and fails closed when objectives are missed.

## Architecture scorecard

| Area | Score | Meaning |
|---|---:|---|
| Correctness | 8/10 | Authority and custody direction are sound; later physical contracts remain to be finalized |
| Architecture | 9/10 | Canonical PG plus governed rebuildable projections and independent R09/R14 gates is the right structure |
| Security | 8/10 target | Design is sound; current generic writes, superuser use and direct-store access remain stop gates |
| Performance | 6/10 | Correct primitives exist, but benchmarks, capacity and retention thresholds are not frozen |
| Maintainability | 8/10 | Lane ownership, gap backlinks, handoffs and durable documentation are strong |

## Implementation decision

The direction is approved for continued design reconciliation, not yet for an implementation-complete
or production-ready claim. The safe sequence is:

1. Ratify CR-001 through CR-004 in R00.
2. Complete CR-005 physical contracts and CR-006 measured acceptance thresholds.
3. Issue implementation handoffs in dependency order, beginning with R01–R04 and the R14 writer fences.
4. Activate no search, graph, Surreal, walk or legal reader until its negative security/horizon tests,
   receipts and R14 evidence pass.

## Multi-agent execution handoffs

- [Semantic agent work packages](SEMANTIC-AGENT-WORK-PACKAGES.md) divide the remaining work by
  authority/domain, dependencies, file ownership and acceptance rather than by database.
- [Timesketch fork and curation handoff](TIMESKETCH-FORK-CURATION-HANDOFF.md) freezes the fork,
  projection, bulk-edit, context-return and approved-entry re-review contract.
- The critical first implementation item is the permanent D-082 fence: the current Workbench
  chat-export route can still reach evidence import and must prove zero custody/evidence writes live.

## Verification performed

- Independent static review compared the target package with `server/`, `sql/`, `workbench/`,
  `deploy/`, `tests/`, and D-069 through D-081.
- All relative Markdown links in the 34-file schema-audit package resolved after correction.
- `uv run pytest -q -m integration tests/test_schema_docs_current.py`: **3 passed**.
- No production service, database, deployment or runtime source code was changed.
