# Whole-system conceptual model

> **Status:** Review architecture; no DDL or deployment authority.
> **Owner direction:** Governing product model approved in conversation on 2026-08-25.
> **Byline:** Codex · GPT-5 · 2026-08-25.

## Governing sentence

The platform ingests everything as context, extracts possible meaning without declaring truth,
promotes selected material into custody-backed evidence, reconstructs what was knowable and
believed at each historical moment, compares that experience against hindsight, and turns the
resulting deceit/realization delta into source-grounded investigation and legal work.

The final analysis is a governed cross-modal temporal graph. Each evidence type remains in the
store best suited to it—relational/custody data in PostgreSQL, vectors in Weaviate, geospatial
data in its geo engine, and other modalities in their specialist homes. Semantica by awksite
extracts provenance-linked entity, relation, event, temporal, claim, and conflict candidates and
supports entity/conflict resolution proposals. Human/governed promotion establishes facts.
Those established facts, with exact typed references back to every source store, aggregate into
SurrealDB. The final ignorant and hindsight walks and the deceit/realization delta are analyzed
there. Surreal is the final analytical graph, not intake, custody, or truth-by-ingestion.

Hash lifecycle is staged. H1 fingerprints the original source. Normalization computes a
deterministic H2 for every individual message/normalized record, but that H2 is provisional.
Promotion independently recomputes and verifies H2 against the selected normalized content and
its H1-backed source lineage before recording it as custody-backed. Evidence processing may
reverify the same H2 later and append the verification result; no stage overwrites prior hashes
or verification history.

H3 seals completeness and ordering for one normalized source generation. Starting with H1, fold
every normalized-record H2 in deterministic source order using
`sha256(utf8(previous_hex || h2_hex))`. Normalization may compute a provisional head; promotion
independently verifies H1, every H2, the ordered membership/count, and the final head before H3
becomes custody-backed. The chain covers the entire normalized source even if only selected records
become evidence: it proves that the backing source representation is complete and ordered, not that
every member is approved evidence. A parser/canonicalization change creates a new generation and
new chain. SBV's empty-genesis/LF chain remains a separate raw-import receipt.

Hash canon is itself governed data. Every accepted H3 carries the exact H1, H2, and H3 canon
identities plus an ordered member manifest. Verifiers dispatch from that tuple; they never guess
from a legacy label. The canon registry, byte-level recipes, and executable vectors must exist
before the first production write under a new tag.

Workflow execution is split without splitting authority. n8n owns the visual business and agent
flow, while Temporal owns durable sequencing and schedules every independently observable Activity.
Hash computation and verification are a standalone Activity family invoked at context intake,
normalization, promotion, and evidence reverification; no parser, normalizer, or storage writer may
hide a hash operation. Activities exchange immutable source/generation/receipt references rather
than carrying files or full corpora through workflow history.

PostgreSQL is the lifecycle backbone. Canonical context/normalized/custody/candidate/fact state is
written there first; PG change detection/outbox events trigger every specialized downstream job.
Weaviate stores derived chunks/embeddings for search and every object and hit resolves to its exact
PG source, record version, chunk/span, projection generation, availability boundary, and promotion
state. Neo4j is primarily Semantica's semantic candidate/relationship graph; every node and edge
carries exact PG candidate/source/span/provenance identity. Raw geodata, normalized geometry, and
geo provenance remain in PostgreSQL/PostGIS. PG derives relevant versioned geo events/features and
governed temporal-geospatial facts there. Every actual sister store returns a projection receipt and
reconciliation status to PG.
Only after PG verifies the required receipts, governance state, counts, versions, and hashes does it
authorize a Surreal aggregation generation for final temporal-graph walking and analysis.

This is an augmented PostgreSQL engine, not a narrow relational database: PostgreSQL 18 provides
the transactional/source-of-truth core, `pg_duckdb` performs analytical and object-store scans,
PostGIS owns geospatial representations and operations, and pgvector holds canonical/local vector
representations and reconciliation data. Weaviate, Neo4j, and Surreal exist because their serving
models fit particular workloads—not because canonical data must be fragmented among them.

This is the design anchor. The database is not primarily a message catalog, evidence warehouse,
or collection of analysis tables. It is a controlled reconstruction of source authority, factual
support, historical knowledge, belief change, and governed use.

## Architectural decision

Use **linked, append-oriented state machines**, one for each authority-bearing aggregate.

A single linear pipeline or universal status column would launder authority: successful parsing
would look like evidence; extraction would look like fact; an agent belief would look like a
governed conclusion. Full event sourcing would preserve history but add unnecessary operational
complexity. Linked state machines retain explicit authority boundaries, immutable history, and
rebuildable projections without forcing every cache or job into one event log.

## End-to-end product loop

```text
external material
    -> context source + fingerprint
    -> parsed context records and exact source spans
    -> extraction candidates (never truth)
    -> owner evidence promotion + original-byte H1 verification
    -> custody-backed evidence source and append-only custody history
    -> evidence-eligible normalized representations
    -> claim investigations and governed established facts
    -> approved realization events
    -> horizon-prefiltered walk experience and walk-local beliefs
    -> paired ignorant/hindsight comparison
    -> realization/deceit delta
    -> reviewed investigation and legal work product
```

Extraction may run on context because extraction forms no beliefs and grants no authority.
Evidence, facts, beliefs, deltas, and court release each require their own explicit boundary.

## Truth and authority classes

| Class | What it means | Authority gained | Change rule |
|---|---|---|---|
| Context source/record | Material available to the platform and a source-faithful parse | None | Reparse/rederive by new version; retain prior receipts |
| Evidence promotion | Human decision selecting exact material for custody | Custody eligibility after verification | Append decision/result; rejection never deletes context |
| Custody-backed evidence | Verified original/source with hashes and custody events | Evidence authority | Append-only; revocation changes eligibility, not history |
| Normalized representation | Rebuildable, typed source representation | None by itself | Successor generation; never rewrite prior interpretation |
| Extraction candidate | Possible entity, time, event, pattern, contradiction, claim, legal issue, concern, observation, strategy, or evidence need | None | Accumulate; reject/link duplicates without erasing origins |
| Established fact | Immutable reviewed proposition with exact custody-backed support | Governed factual authority | Qualify/contradict/supersede with a new assertion |
| Realization event | When/how the owner formed a realization | Governed realization authority after approval | Plural append-only events; never rewrite source clocks |
| Walk belief | What one agent believed in one walk at one horizon | Experiential only | Immutable revisions within one walk; never active across walks |
| Delta item | Version-pinned difference between compatible ignorant and hindsight runs | Analytical comparison only | Recompute successor when inputs/policy change |
| Legal work product | Draft, filing, exhibit, strategy, or other created work | Release authority only after separate review | Immutable versions; supersede/withdraw, never erase |

## Cross-cutting invariants

1. **No authority laundering.** Context -> normalization -> extraction does not increase truth
   authority.
2. **Human-governed boundaries.** Only attributable decisions create evidence authority,
   established facts, approved realizations, or released legal work.
3. **Immutable history.** Corrections append successors and typed relations; they do not rewrite
   evidence, claims, facts, realization decisions, beliefs, deltas, or released outputs.
4. **Separate identities.** Sources, spans, normalized records, claims, facts, realizations,
   beliefs, deltas, and legal products do not share one universal row identity.
5. **Custody closure.** Every active established fact and released factual assertion resolves to
   exact spans in active custody-backed source revisions.
6. **Clock separation.** `occurred_at`, `source_available_from`, realization time, acquisition
   time, write/audit time, decision time, and walk observation time are never substituted.
7. **Prefilter before ranking.** An as-lived source is eligible only when
   `source_available_from <= horizon_at`; stores apply that predicate before top-k.
8. **No parallel authored truths.** As-lived/hindsight corpora and typed message/vector/graph
   surfaces are version-pinned derived projections.
9. **Participant fidelity.** Verbatim sender, recipients, and participants stay on the source
   record. Entity resolution is additive. Acquired-third-party records must not invent the owner
   as a participant.
10. **One personal case.** The platform has one owner and one personal case scope. Do not add
    multi-Matter tenancy, cross-Matter isolation, Matter/CourtCase hierarchies, or per-case
    scope-binding machinery. A fixed `case_id='primary'` may remain only for compatibility.
11. **Fail closed.** Missing horizon context, custody mismatch, projection drift, or contamination
    blocks/seals work; it never becomes empty success or hindsight fallback.
12. **Revocation propagates eligibility, not deletion.** Descendants become stale, blocked, or
    review-required while their historical records remain.
13. **Independent corroboration.** Copies or derived representations from one source family cannot
    inflate corroboration counts.
14. **Legal release is independent.** A fact, realization, behavioral finding, belief, or delta is
    not automatically court-safe.
15. **Artifact vocabulary.** `artifact` means a created work. Parsed records, extraction output,
    claims, and projections are not artifacts.

## Core object model and cardinalities

### Context, promotion, and custody

- One `ContextSource` has zero-to-many `ContextRecord`s; every record belongs to exactly one
  source. Zero records is valid for an unsupported or failed parse.
- A `ContextRecord` resolves through one-to-many exact `SourceSpan`s. Spans and downstream records
  are many-to-many through explicit provenance links.
- One `PromotionRequest` contains one-to-many atomic `PromotionItem`s. Each item selects an exact
  record/span set and produces exactly one fingerprint-verification attestation.
- A successful promotion item creates or reuses exactly one `EvidenceSource` and records one
  immutable promotion-to-source link. The singleton personal-case deployment never duplicates
  original bytes or custody history merely to express relevance.
- One evidence source has one-to-many evidence-hash attestations and one-to-many append-only
  custody events. File trees use one parent at most and zero-to-many children.
- Normalized representations resolve through exact source spans to one custody lineage before
  they become evidence-eligible. Parse success alone never grants eligibility.

### Three separate message families

The three families remain separate. They are not merged behind a discriminator.

1. **First-party human communication**
   - One conversation contains one-to-many messages.
   - Each message derives from exactly one evidence-normalized record version.
   - The owner appears exactly once in the participant set, with at least one non-owner.
   - Source availability is occurrence time.
2. **Acquired-third-party human communication**
   - One conversation contains one-to-many messages.
   - Each message derives from exactly one evidence-normalized record version.
   - The historical sender/recipients/participants are preserved and the owner appears zero times.
   - The conversation has one-to-many approved custody-backed acquisition links.
   - Source availability is the earliest valid approved acquisition boundary.
3. **AI-chat/context communication**
   - One AI conversation contains one-to-many AI messages.
   - Messages preserve actual user/assistant/system/tool role semantics.
   - AI chat is never joined or promoted to the evidence spine and never enters a historical
     evidence walk. Its context-only lineage contributes zero evidentiary support weight.
   - One versioned extraction run may fan out from exact message/span inputs into claim/event
     candidates, investigation issues/concerns/evidence needs, AI observation candidates, strategy
     candidates, and created-work versions.
   - A generated legal document is a created work, not evidence. Attributable human selection may
     materialize it as a draft R12 work product; its factual assertions still require independent
     custody-backed citations before governed release.

Each message retains verbatim sender/recipient/participant values. A participant occurrence may
have zero or one active approved entity resolution, while retaining zero-to-many historical
resolution assertions. Conversation participants are derived from message occurrences unless the
source contains an explicit roster, which is preserved separately.

### Chunks and projections

- One canonical representation has zero-to-many chunks.
- Chunks and source spans/messages are many-to-many because a chunk may cover adjacent turns and
  controlled overlaps are valid.
- One chunk has zero-to-many embedding/projection versions, each bound to one sink, lane,
  embedder, source boundary, base version, and generation.
- Projection generations carry membership/content hashes and receipts. They are rebuildable and
  never authoritative.

### Claims, facts, and realizations

- A `ClaimCandidate` has one-to-many exact source links; a source span may support, contradict,
  qualify, duplicate, or contextualize many candidates.
- Claims accumulate and never rewrite. Entity deduplication is expressed through merge decisions;
  claim deduplication links provenance-preserving candidates rather than erasing them.
- A claim investigation may establish zero-to-many immutable fact assertions; a fact may synthesize
  one-to-many investigations.
- An established fact has one-to-many exact evidence-support links and belongs to a lineage with
  at most one current assertion. Typed fact-to-fact edges record supersession, contradiction, and
  qualification.
- Investigation items separately type legal issues, concerns, contradictions, questions, leads,
  and evidence needs. Observation candidates retain model/run identity and are never facts.
  Strategy candidates retain assumptions, risks, options, and source lineage and become legal work
  items only through an attributable materialization decision.
- One created-work identity has one-to-many immutable content versions and one-to-many exact
  chat-message/span or archive-asset source links. Selection into the Workbench creates a linked
  draft work-product version; it never overwrites the extracted created work.
- One realization event belongs to the singleton personal-case/subject perspective and links to
  one-to-many targets.
  A target may have zero-to-many realizations. Realizations may target source records and, subject
  to the explicit ruling below, governed claims/facts.

### Timeline fork and round-trip context curation

- Any context record/span may produce zero-to-many event candidates through versioned extraction.
- A timeline collection has zero-to-many versioned members pointing to exact event-candidate,
  established-fact, or procedural-event versions without copying their authority.
- Candidate/context and evidence-approved/governed entries are both visible in the maintained
  Timesketch fork with unmistakable authority, verification, dispute, and source badges.
- One immutable projection generation has one-to-many members and delivery/read-back receipts.
  Timesketch/OpenSearch remains rebuildable serving state.
- One curation batch has one-to-many independently validated edit items. Each targets an exact PG
  object/version and returns accepted, rejected, conflict, or no-op.
- Accepted context edits append typed annotations, resolution/grouping assertions, candidate review
  decisions, or successor derived-context versions; raw messages/assets never change.
- Every change proposed against an evidence-approved entry becomes a linked context amendment
  candidate. The approved version remains unchanged until independent re-review/reconciliation
  appends a governed successor.
- A reversal is a new compensating batch. Fork-local tags/comments/edits are not authoritative until
  PG accepts the command and reprojects the result.

### Walks, beliefs, and the delta

- The singleton personal case has zero-to-many walk runs. Every run pins its agent binding, horizon
  policy, source/fact scope manifest, base version, and projection/policy generation.
- One run has zero-to-many ordered steps and zero-to-many checkpoints. An ignorant horizon advances
  monotonically; hindsight is an explicit grant.
- A healthy pause resumes from one reconciled checkpoint. A terminal failure seals the run and a
  repair creates a new walk with exactly one `rewalk_of` parent and an attested change manifest.
- One step has zero-to-many retrieval observations and zero-to-many belief events. Belief threads
  are confined to one walk and contain immutable revisions.
- A valid delta comparison references exactly two compatible runs: one ignorant and one hindsight.
  They share the singleton case, scope manifest, base version, projection generation, and controlled
  model/prompt/tool variables.
- One comparison has one-to-many delta items. Each item identifies the as-lived belief/conclusion,
  the hindsight conclusion, the change type, governed anchors, realization links, and exact source
  citations.

The paired delta is a first-class product object. It cannot remain only an incidental view over
walk steps because it is the platform's central deliverable and requires reproducibility,
governance, review, citation, and legal reuse.

### Personal case and legal work

- The deployment contains one owner and one personal case. Existing Matter/CourtCase identifiers are
  compatibility references only and cannot create a hierarchy, authorization scope, or new row.
- Evidence relevance is expressed by governed promotion/support/provenance links inside that fixed
  case, never by reusable Matter/CourtCase scope bindings.
- Facts and legal issues are many-to-many through typed applicability/support relations.
- Legal work products have immutable versions and explicit citations to established facts,
  approved delta items, and custody-backed evidence spans.
- Court surfaces never cite raw context, unapproved candidates/realizations, or walk beliefs
  directly.

## Aggregate lifecycles

### Context source

```text
received -> fingerprinted -> parsed/normalized -> promotion_proposed
  -> promotion_rejected
  -> fingerprint_mismatch -> quarantined
  -> fingerprint_verified -> promoted
```

Reprocessing creates a successor derivation. Rejected context remains context. A mismatch is
terminal for that promotion attempt.

### Evidence promotion and custody

```text
proposed -> verifying_original -> rejected | quarantined | active
active -> partially_revoked | revoked | superseded
```

Promotion is a governance event, not a row move. Activation recomputes H1, binds exact source
material, begins custody, and authorizes downstream evidence projections atomically.

### Normalized representation

```text
derived -> validated -> invalid | current -> superseded
```

Pre-promotion normalization is context-derived. Evidence eligibility is computed through active
promotion/custody linkage, not stamped by a parser.

### Candidate and established fact

```text
candidate: proposed -> triaged -> rejected | duplicate_linked | under_investigation -> dossier_frozen
fact: dossier_frozen -> review_pending -> rejected | established
established -> qualified_by | contradicted_by | superseded_by | revoked
```

Confidence prioritizes review; it never establishes a fact.

### Realization

```text
proposed -> review_pending -> rejected | approved -> superseded | revoked
```

Realizations remain plural and never edit message time or source availability.

### Walk and belief

```text
walk: created -> running -> healthy_paused -> reconciled_resume -> running
running -> completed -> sealed
running -> integrity_failure -> terminal_sealed -> linked rewalk

belief: proposed -> accepted | rejected
accepted -> qualified | superseded | contradicted | invalidated
```

Sealed snapshots are comparison history, never active recall.

### Delta and legal work

```text
delta: requested -> pair_validated -> blocked | computed -> reviewed -> superseded
legal work: draft -> citation_validated -> legal_review_pending
            -> rejected | approved_for_release -> released -> superseded | withdrawn
```

Upstream revocation blocks new release and creates review obligations; it does not erase what was
previously released under the prior manifest.

## Current relation-family disposition

Disposition applies to semantic families, not a promise that every current table name survives.

### Keep as aligned contracts

- Agno runtime and `ops.*` workflow/audit/run ledgers.
- `reference.*` curated taxonomy and configuration.
- Singleton personal-case identity plus an explicit compatibility census for legacy
  Matter/CourtCase identifiers; those identifiers never partition knowledge or authorization.
- Post-promotion custody primitives: source, hashes, file nodes, custody events.
- Entity/address-book identity and additive resolution history.
- Generic immutable lineage, cross-reference, and source-provenance concepts.

### Reshape because the concept survives

- Move the pre-promotion raw landing family out of `evidence.*` into a context boundary; repoint
  funnel, layer-map, reconciliation, derivation, and runtime reads together.
- Make promotion the sole writer of custody primitives after original-byte fingerprint verification.
- Slim the normalized spine into one rebuildable source representation. Remove custody authority,
  legal release state, mutable analysis hints, and singular realization meaning from it.
- Preserve the three message families but standardize their source-reference, clock, derivation,
  verbatim-participant, and additive-resolution contracts.
- Consolidate candidate staging around explicit entity/event/time/pattern/contradiction and
  authoritative `claim_candidate` semantics.
- Build established-fact support, review, independence, and append-only supersession explicitly.
- Preserve plural realization and the walk ledger; add first-class walk belief threads and paired
  delta objects.
- Keep caches, chunks, embeddings, outboxes, and graph/vector projections rebuildable and
  base-version pinned.
- Rebuild investigation and legal/court consumers around governed facts and approved delta items.

### Quarantine later, never delete automatically

Candidates for later quarantine include superseded candidate pipelines, authored as-lived/hindsight
promotion lanes, duplicate/dormant legal scaffolds, parked duplicate geo tables, legacy public
memory/HITL tables, and ambiguous unused registries.

No relation enters quarantine merely because it is empty. Before any move:

1. prove zero readers/writers for two releases;
2. prove zero FK/view/function dependencies;
3. export rows, schema, counts, and checksums;
4. rehearse restoration;
5. obtain owner approval;
6. move the checked export/retirement package under
   `to_be_deleted/schema-audit-YYYYMMDD`.

The agent never permanently deletes. Only the owner deletes from `to_be_deleted`.

## Safe implementation order

0. Freeze contracts and inventory: current catalog, counts, hashes, dependency graph, writer/reader
   census, allow-list/freshness tests, and planted-future-fact canaries.
1. Add target contracts only: context source version/fingerprint, promotion command/result,
   `claim_candidate`, established-fact support/supersession, walk belief, and delta objects.
2. Implement the D-069 promotion writer live but unwired. Its transaction locks the context source
   version, recomputes H1, writes custody primitives, records scope, and appends audit/result.
3. Move raw landing to the context boundary and repoint all dependent views/readers atomically.
4. Backfill existing ingested material through the promotion writer and reconcile every custody
   chain, count, and hash.
5. Cut ingestion to context-only writes and retire ingest-time evidence creation.
6. Reshape the message families separately: shared contract, first-party resolution,
   acquired-third-party acquisition/owner-exclusion, then AI-chat context.
7. Reshape the high-centrality normalized spine last, one semantic concern per migration, rebuilding
   dependent views/functions each time.
8. Cut candidates/facts over with exact-source reconciliation and append-only governance.
9. Add walk beliefs and delta computation; enable agents only after cross-store prefilter and
   contamination canaries pass.
10. Switch investigation/court/legal readers to custody-backed established facts and approved
    delta items, with no raw-context/candidate fallback.
11. Quarantine only after telemetry, export, restoration proof, and owner approval.

## Irreversible semantic gates

- **Gate A — custody creation:** the first append-only custody write cannot be rolled back by erasure;
  corrections are forward events.
- **Gate B — ingestion cutover:** switch only after a live canary proves context ingest creates no
  custody and explicit promotion does.
- **Gate C — fact establishment:** approved facts become immutable legal history; correction is
  supersession.
- **Gate D — walk sealing:** a sealed hash chain is never resumed or rewritten; drift creates a
  rewalk.
- **Gate E — legal consumer cutover:** no court/legal reader retains fallback access to raw context,
  candidates, or unapproved beliefs.

## Owner rulings still genuinely required

These change authority or cardinality and should not be guessed during physical design:

1. **AI-chat authority — resolved by D-082/D-083:** AI chat is permanently context-only and never
   evidence. Its typed extraction fan-out feeds the claim chart, investigation register,
   observation/strategy candidates, and created-work versions. Independent custody-backed evidence
   alone can establish facts; created legal works enter R12 only as drafts through attributable
   selection.
2. **Timeline product — resolved by D-084/D-085:** use a maintained Timesketch fork as the chronology
   and bulk-curation service. Any-context candidates and evidence-approved entries are visible with
   explicit authority. Edits return as typed, version-bound PG context commands; edits to governed
   entries become context amendment candidates until re-reviewed and reconciled into successors.
3. **Custody reuse — resolved by D-072:** one custody-backed evidence source is reused within the
   singleton case through provenance/promotion links; no Matter/CourtCase scope-binding model exists.
4. **Realization targets:** may realizations target governed claims/facts as well as normalized
   records? Recommended: yes.
5. **Delta authority:** is the paired delta a durable governed product, and must court-eligible
   items use established-fact anchors? Recommended: durable/version-pinned; established-fact
   anchors required for court eligibility.
6. **Legal-work scope — resolved by D-072:** all investigation, strategy, and proceeding-specific
   work belongs to the singleton personal case. Existing docket/court identifiers are source or
   procedural metadata, not CourtCase domain hierarchy.

## Explicit non-decisions

This document does not choose physical schema names, final table names, SQL columns, indexes,
partitioning, database roles, deployment timing, or quarantine targets at relation granularity.
Those follow only after the rulings above and an owner-reviewed physical model.
