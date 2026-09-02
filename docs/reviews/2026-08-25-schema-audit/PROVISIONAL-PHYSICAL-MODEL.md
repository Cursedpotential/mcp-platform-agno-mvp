# Provisional physical model


> _Recovery note: this file was lost (never committed) after being authored in a Codex CLI session on 2026-08-25/26. Reconstructed 2026-09-02 by Claude Code · Sonnet (recovery lane C) from the session's own `apply_patch` tool-call history in `C:\Users\matts\.codex\sessions\2026\08\`, per the method in `RECOVERY-NOTE.md`. All accepted `apply_patch` hunks touching this file located and applied cleanly; full recovery, high confidence._

> **Status:** Review draft only. No DDL, deployment, migration, or quarantine authority.
> **Depends on:** [WHOLE-SYSTEM-CONCEPTUAL-MODEL.md](WHOLE-SYSTEM-CONCEPTUAL-MODEL.md).
> **Byline:** Codex · GPT-5 · 2026-08-25.

## Purpose

This document translates the owner-approved governing intent into PostgreSQL relation families,
keys, links, and database-enforced boundaries. Names are provisional. The design deliberately does
not preserve current table shapes merely because they are live, and it does not remove useful
concepts merely because their present tables are empty.

The physical design follows one rule above all others:

> Storage progress does not imply authority progress.

A parse may exist before evidence promotion. A claim may exist without being a fact. A belief may
exist without being a claim or fact. A delta may exist without being court-eligible.

## Provisional defaults

> **Owner corrections, 2026-08-25:** this is a single-owner, single-personal-case platform;
> do not implement multi-Matter/CourtCase isolation or evidence scope bindings. Evidence types
> remain in their appropriate specialist stores. Semantica by awksite produces provenance-rich
> entity/relation/event/claim/conflict candidates and resolution proposals; governed review
> establishes facts. SurrealDB is the final reconciled temporal-graph aggregation and runtime
> for the ignorant/hindsight walks and delta analysis. PostgreSQL remains custody, promotion,
> approval, and audit authority. Any contrary Matter-scoping or “experimental Surreal” detail
> below is superseded by this correction and must be removed during implementation refinement.

### Final analytical dataflow

1. Context ingest preserves source bytes/records, fingerprints, typed message participants, and
   modality-native data without declaring evidence or truth.
2. Owner promotion verifies H1 and begins custody in PostgreSQL.
3. Each modality is normalized and indexed in its proper workload-local representation. PostgreSQL
   remains authoritative for identity, lineage, governance, source clocks, eligibility and receipts;
   external specialist stores are rebuildable projections and never independent truth. Modality
   payloads are not flattened into a lossy universal table.
4. Semantica reads the governed source representations and writes append-only entity, relation,
   event, temporal, claim, conflict, and resolution candidates with exact provenance locators.
5. Review/promotion converts selected candidates into immutable established-fact assertions with
   supporting, contradicting, and qualifying source links. Corrections supersede; they do not erase.
6. A versioned projector assembles the approved cross-modal facts and their typed source references
   into SurrealDB's temporal graph. Projection rows carry source IDs, versions, custody hashes,
   approval IDs, validity/occurrence time, source-availability time, and realization links.
7. The final as-lived and hindsight walks execute in Surreal against the same pinned graph version
   with different fail-closed horizon permissions. Their comparison is the final analysis product.

### H2 computation and verification lifecycle

- Normalization computes one deterministic provisional H2 per individual message/normalized-record
  version. Store the algorithm, canonicalization version, content locator, computed value, run ID,
  and computation time; do not mark it custody-approved.
- Promotion locks the selected record version, recomputes H2, verifies equality and the H1-backed
  original-source lineage, then appends the accepted custody-H2 assertion and promotion audit in
  one transaction. Mismatch fails closed and creates no partial custody assertion.
- Evidence processing may independently recompute H2 and append a reverification event referring
  to the accepted assertion. A mismatch creates an integrity exception/review item; neither result
  updates or deletes the original computation or accepted custody hash.
- H3 is computed once per normalized source/parser-canonicalization generation over the complete
  deterministic H2 sequence: `chain_0 = H1`; `chain_i = sha256(utf8(previous_hex || h2_hex))`.
  Store a provisional normalization result separately from the promotion-accepted custody H3.
  The accepted H3 row uses `h3-chain-h1genesis-hexconcat-v1` and references the H1 hash, source
  generation, ordered H2 membership manifest/member IDs, record count, canonicalization version,
  promotion decision, computation run, and chain head. Evidence reverification appends a result.
  Legacy `h3-chain-v1` and SBV `h3-chain-sbv-genesisempty-v1` rows are never relabelled or merged.

`public.canon_registry` is a KEEP/RESHAPE custody-governance contract, not generic legacy memory.
Before the first `h3-chain-h1genesis-hexconcat-v1` production write, an additive migration must
make the registry reproducible and add the exact H1/H2/H3 compatibility tuple, byte recipe, test
vectors, status, and reference implementation. The verifier must dispatch by precise canon. A
legacy bare `h3-chain-v1` without append-only writer attribution is `ambiguous/unverifiable`.
The current SBV-only inspection verifier is not sufficient for the evidence chain and must be
replaced or extended before activation.

Hash compute/verify operations are standalone Temporal Activities backed by one canon-dispatching
callable. Each input names the subject version, ordered-member manifest where applicable, operation
(`compute`, `verify`, or `reverify`), full H1/H2/H3 canon tuple, and idempotency key. Each result
returns a durable computation/verification receipt ID, digest/status, member count, and mismatch
details. Domain writers consume receipt IDs; they do not recompute hashes internally. Temporal
history carries references only. The complete Activity graph and implementation gaps are defined in
`TEMPORAL-N8N-WORKFLOW-AND-GAPS.md`.

PostgreSQL owns the universal change/outbox and projection-receipt contracts. A downstream job row
names the source/record/fact version, target store, projection generation, policy/canon versions,
immutable input manifest digest, and idempotency key. A completion receipt records the target
object IDs, counts, hashes, source-link verification, horizon-field verification, writer version,
and status. A PG reconciliation manifest selects the exact successful receipts required for one
Surreal aggregation generation. Surreal projection is prohibited while any required receipt is
missing, stale, mismatched, revoked, or not governed for its intended use.

PostgreSQL/PostGIS is the physical home for raw geo observations and normalized geometries. Geo
tables retain source/version/span identity, coordinate reference system, original coordinates or
payload, valid/occurred time, availability time, processing generation, and derivation receipts.
Relevant geo events/features and governed temporal-geospatial facts are selected through PG
manifests for Surreal aggregation. Do not create a separate raw-geo authority or copy all raw points
into Surreal merely because they exist.

The physical PG target assumes PostgreSQL 18 with `pg_duckdb`, PostGIS, and pgvector. Canonical
embedding identity, source linkage, embedding model/version, dimensions, content/vector hashes,
projection eligibility, and reconciliation receipts live in PG even when serving vectors are copied
to Weaviate. `pg_duckdb` queries object-backed analytical inputs through PG authority and must not
create an independent DuckDB truth path. These extensions expand the central engine; they do not
weaken append-only custody/governance boundaries.

Surreal never receives authority merely because data was projected there: custody and approval
remain in PostgreSQL, and every analytical node or edge must resolve back to its authoritative
source representation. There is one personal-case graph namespace, not tenant-selected Matter
partitions.

The following owner rulings and recommended answers make the draft concrete:

1. D-082/D-083: AI chat is permanently context-only. It fans out into typed candidates,
   investigation items, strategies, observations, and created works but can never be promoted,
   cited, or weighted as evidence.
2. One custody-backed evidence source is reused within the singleton personal case through immutable
   promotion/provenance links. No Matter/CourtCase binding relation is added.
3. Realizations may target source records, claim candidates, and established facts.
4. The paired delta is durable and version-pinned. Court-eligible delta items require
   established-fact anchors.
5. Legal, investigation, and proceeding-specific work belongs to the singleton personal case.
6. D-084/D-085: a maintained Timesketch fork displays any-context candidates and evidence-approved
   timeline entries. All individual/bulk edits round-trip through version-bound PG context commands;
   edits to approved entries become context amendment candidates until re-reviewed/reconciled.
   Court and docket identifiers remain procedural/source metadata rather than a CourtCase hierarchy.

## Logical authority boundaries

These are logical namespaces. Final PostgreSQL schema homing remains a separate reviewed decision.

| Namespace | Owns | Must not own |
|---|---|---|
| `context` | Intake identity, revisions, fingerprints, source-faithful raw/parsed context, AI chats | Custody authority, facts, beliefs |
| `evidence` | Promotion verification, evidence identity, acquisition, hashes, custody events, immutable promotion/provenance links | Pre-promotion landing, analysis conclusions |
| `spine` | One normalized, rebuildable source representation and typed human-message projections | Custody authority, mutable analysis hints, legal release |
| `identity` | Entity/address-book identities and additive resolution assertions | Replacement of verbatim source participants |
| `analysis` | Candidates, investigations, established facts, realizations, reviewed findings | Source custody, walk-local beliefs |
| `walk` | Run specifications, steps, retrieval receipts, beliefs, checkpoints, seals, paired deltas | Canonical evidence/facts |
| `legal` | Singleton-case created work, assertions, citations, approval/release versions | Raw context or unapproved candidate authority |
| `ops` | Workflow, tool, audit, projection jobs, durable reports | Domain truth |
| `reference` | Curated taxonomy, rules, patterns, legal reference material | Case-specific truth |
| `ai` | Agno operational runtime | Evidence or semantic authority |

## 1. Single personal case (supersedes the scope hierarchy below)

The target has no tenancy/scope hierarchy. The deployment represents one owner and one case.
An optional singleton `case_profile` may hold procedural metadata. Existing `analysis.matter`,
`court_case`, `matter_knowledge_partition`, and `case_id='primary'` remain compatibility
scaffolding only: do not add new foreign keys, APIs, caches, or authorization rules that expand
them. Flattening them requires a separate, safely reconciled migration.

### Legacy `matter` / `court_case` compatibility

These existing relations and identifiers are migration inputs, not target domain objects. R00/R14
must census their readers/writers and freeze new creation. Until a separately reviewed forward
migration retires them, compatibility IDs may be carried as non-authoritative references only; they
cannot select data, determine authorization, partition horizons, or require new foreign keys.

### Singleton-scope constraints

The server binds every operation to the one personal case. Caller-supplied Matter/CourtCase switching
or creation fails closed. Evidence custody remains source-based and uses promotion/provenance links,
not scope-binding tables.

## 2. Context intake and source revisions

### `context_source`

Stable identity for imported material or an external source endpoint.

- Primary key: `context_source_id`.
- Describes origin/source class, not evidence authority.
- One source has one-to-many immutable revisions.

### `context_source_revision`

One captured byte/retrieval state.

- Primary key: `source_revision_id`.
- Required FK: `context_source_id`.
- Carries object locator, capture metadata, fingerprint algorithm/value, byte/member manifest, and
  predecessor/successor relation.
- Unique content/revision identity prevents silent replacement.

### `context_source_member`

Archive/file/member hierarchy inside a source revision.

- Primary key: `source_member_id`.
- Required FK: `source_revision_id`.
- Optional self-FK parent; one parent at most, zero-to-many children.

### `context_parse_run`

Immutable receipt for parser/normalizer execution.

- Primary key: `parse_run_id`.
- Required FK: `source_revision_id` and `ops.workflow_run`/equivalent.
- Pins parser, version, configuration, input manifest, result manifest, and status.

### `context_record`

Source-faithful parsed unit before any claim/fact authority.

- Primary key: `context_record_id`.
- Required FK: `parse_run_id`.
- One source revision may yield zero-to-many records.
- Unsupported/rejected records remain explicit results; they are never silently dropped.

### `source_span`

Exact locator into a source revision/member.

- Primary key: `source_span_id`.
- Required FK: `source_revision_id`; optional member FK.
- Carries byte/character/message/page/time locator appropriate to the format.
- Context records and downstream candidates use typed link tables to spans.

### AI-chat context

Keep separate `ai_conversation`, `ai_message`, message-safe chunks, created works, attachments, and
projection/outbox relations inside the context boundary. An AI message is not silently inserted into
the evidence spine.

## 3. Evidence promotion and custody

### `evidence_promotion_request`

Human-governed command selecting exact context material.

- Primary key: `promotion_request_id`.
- Fixed singleton personal-case scope; no caller-selected Matter/CourtCase identity.
- One request contains one-to-many atomic items.

### `evidence_promotion_item`

Atomic selection and decision unit.

- Primary key: `promotion_item_id`.
- Required FK: promotion request.
- Selects one source revision or a version-pinned set of exact source spans.
- State is append-derived from result events, not a mutable authority flag.

### `fingerprint_verification_attestation`

Result of re-reading the original and recomputing H1.

- Primary key: `attestation_id`.
- Required FK: promotion item and source revision.
- Failed/mismatched attempts remain recorded but cannot create evidence.

### `evidence_source`

Custody-backed identity created or reused only after successful attestation.

- Primary key: `evidence_source_id`.
- Unique successful promotion/verified content identity.
- No direct ownership by Matter/CourtCase.

### `evidence_scope_binding` — rejected by D-072

Do not build this relation for the target architecture. The platform has one personal case, so
custody-backed evidence needs provenance and promotion links, not reusable Matter/CourtCase scope
bindings. Any existing similarly named relation is compatibility scaffolding pending a safe census.

No target table or replacement scope hierarchy is created. Existing similarly named rows are
compatibility inputs for R00/R14 consumer reconciliation only.

### `evidence_hash`, `file_node`, `custody_event`, `acquisition`

Preserve current custody primitives and history, with these contracts:

- At least one verified H1 exists before evidence activation.
- Hash/chain construction tags name the exact algorithm. SBV and Case Bible H3 remain distinct.
- Custody events are append-only.
- Acquisitions represent custody-backed possession, not generic pre-promotion intake metadata.
- Revocation/supersession appends events and changes eligibility; it never deletes history.

## 4. One normalized spine without authority laundering

### `normalized_record`

Stable identity for one logical source record.

- Primary key: `record_id`.
- No required evidence FK: normalization is allowed before promotion.
- One logical identity has one-to-many immutable versions.

### `normalized_record_version`

Immutable source-faithful representation.

- Primary key: `record_version_id`.
- Required FK: `record_id`, context parse run, and one-to-many exact source-span links.
- Carries only cross-record source semantics: record type, canonical content, `occurred_at`, source
  native key, temporal precision, derivation identity, and source-faithful attributes.
- Does not carry custody authority, legal-release state, mutable analytical hints, singular
  realization, or walk beliefs.
- At most one current version per record and canonicalization generation, maintained by a
  single-writer pointer/registry rather than rewriting versions.

### `record_source_span`

Many-to-many record-version-to-source-span provenance.

- Primary key: `(record_version_id, source_span_id, role)`.
- Roles distinguish origin, quoted material, attachment, corroborating copy, and related context.

### `evidence_record_binding`

The only bridge granting a normalized version evidence eligibility.

- Primary key: `evidence_record_binding_id`.
- Required FK: record version, evidence source, active promotion item, and exact custody-backed
  source spans.
- Facts and court citations may reference this binding; they may not cite a bare normalized row as
  custody-backed evidence.

### `record_supersession`

Append-only relation between old/new versions with reason and derivation receipt.

## 5. Three physical message families

The tables remain separate. Shared read behavior belongs in governed union views/functions, never a
universal authored message table.

### `first_party_conversation` / `first_party_message`

- Conversation one-to-many messages.
- Message unique FK to one normalized record version.
- Verbatim sender, recipients, participants, platform identifiers, content-specific forensic
  metadata, and source ordering remain on the message record.
- Owner occurs exactly once in the participant payload/occurrences and at least one non-owner exists,
  subject to explicit system-message exceptions.
- Availability basis is occurrence.

### `acquired_third_party_conversation` / `acquired_third_party_message`

- Conversation one-to-many messages.
- Message unique FK to one normalized record version.
- Actual sender/recipients/participants remain on the record.
- Owner occurs zero times in the historical participant set.
- Conversation has one-to-many approved acquisition bindings.
- Availability basis is earliest valid approved custody-backed acquisition.

### `ai_conversation` / `ai_message`

- Context-only by default; actual user/assistant/system/tool role semantics remain intact.
- Explicit promotion creates evidence bindings to the immutable export/source spans. It does not
  recast the AI message as first-party/third-party human communication and does not establish model
  assertions.

### Cross-table exclusivity

Do not reintroduce a universal `projection_kind` table as authored truth. First-party and
acquired-third-party tables use unique record-version FKs plus a deferred cross-table constraint
trigger preventing one record version from appearing in both families. AI chat is outside this
spine unless explicitly promoted through evidence bindings.

## 6. Verbatim participants and additive identity resolution

### `participant_occurrence`

One source-native participant occurrence associated with one typed message.

- Separate typed FKs/link tables per message family; avoid unchecked polymorphic target IDs.
- Stores verbatim token/name/address and role (`from`, `to`, `cc`, `bcc`, `group`, etc.).
- Never replaces the participant payload on the message.

### `entity`, identifiers, aliases, merge events

Preserve the existing address-book/entity concepts and explicit merge history.

### `participant_resolution_assertion`

Append-only occurrence-to-entity assertion.

- Primary key: `resolution_assertion_id`.
- Required participant occurrence and entity FKs.
- Carries method, confidence, proposer/reviewer, validity, and supersession.
- At most one active approved assertion per occurrence; historical assertions remain.

## 7. Source-availability boundary

### `record_horizon_boundary`

Version-pinned, indexed derived projection replacing ambiguous writable visibility fields.

- Primary key: `(record_version_id, boundary_generation)`.
- Fixed singleton-case scope, `source_available_from`, basis kind, typed basis reference, base version,
  source-clock hash, and derivation receipt.
- First-party basis must reconcile to occurrence.
- Acquired-third-party basis must reconcile to approved custody acquisition.
- Missing or stale boundary row fails closed.
- Realization never changes this boundary.

This is the indexed equivalent of the current `record_visible_from` cache, but its name and contract
say what it is: a rebuildable source-availability projection, not authored truth. Retrieval functions
select only the caller-pinned generation before ranking.

## 8. Chunks, embeddings, and store projections

### `record_chunk`

- One record version has zero-to-many chunks.
- Chunk/message/span mapping is explicit and may be many-to-many.
- Carries source boundary inheritance and chunker/input hashes.

### `derived_projection_generation`

Registry for vector, graph, search, and materialized walk inputs.

- Pins base version, projection policy, embedder/model, membership/content hashes, row counts, and
  status.
- One generation has one-to-many projection members and receipts.
- Only small single-writer current pointers are mutable.

### `projection_member` / `projection_receipt` / outbox

Rebuildable operational relations. Vector/graph objects inherit the fixed singleton-case scope, record version,
`source_available_from`, disclosure policy, and projection generation. No projection can grant
authority.

External graph memory is optional and replaceable. PostgreSQL remains authority for walk beliefs;
Graphiti is currently retired rather than a required target.

## 9. Candidates, claims, and established facts

### Candidate families

Keep separate candidate types where lifecycle differs:

- `entity_candidate`
- `time_candidate`
- `event_candidate`
- `pattern_candidate`
- `contradiction_candidate`
- `claim_candidate`
- `legal_issue_candidate`
- `observation_candidate`
- `strategy_candidate`

Every candidate is immutable and has one-to-many exact candidate-source links. Candidates accumulate.
Entity merge/dedup uses explicit merge events; claim equivalence links candidates without erasing
their separate provenance. Observation candidates require model/run/prompt/tool identity and cannot be
promoted directly to fact. Strategy candidates retain assumptions, risks, alternatives and review
state. `legal_issue_candidate` is case-specific applicability, separate from the reference legal-issue
taxonomy.

### `investigation_lead` / `evidence_need`

The context-level lead register separately types concern, contradiction, legal issue, question,
event lead, missing expected material, and other investigation triggers. It is not named or treated as
an established event. Each item has exact typed context anchors; evidence needs may later link to exact
independent evidence records/spans without treating the originating context as support.

The claim chart/list is a derived read model over claim/event candidates, investigation leads,
evidence needs, investigation results, and governed facts. It is not a second authored claim store.

### `claim_investigation` / `investigation_run` / `investigation_result`

Version-pinned dossier construction.

- One investigation has one root claim candidate and one-to-many runs.
- Results link exact sources and classify support, contradiction, qualification, context, duplicate,
  unresolved, or missing-expected material.
- Freezing a dossier does not establish a fact.

### `fact_lineage` / `fact_assertion`

- A lineage has one-to-many immutable assertions and at most one current assertion.
- Establishment is an attributable review event, not an update to a candidate.

### `fact_support`

Many-to-many fact assertion to `evidence_record_binding`/exact span support.

- Typed role: supports, contradicts, qualifies, contextualizes.
- Carries source-family independence identity so copies cannot inflate corroboration.
- Deferred constraints require qualifying support before an assertion becomes established.

### `fact_relation`

Typed self-relations for supersedes, contradicts, and qualifies.

## 10. Maintained Timesketch timeline fork and context curation

### `timeline_collection` / `timeline_member`

A collection is a curated singleton-case chronology. Members point to exact event-candidate,
fact-assertion, or procedural-event versions and retain their original authority. Candidate/context and
evidence-approved/governed entries may coexist only with explicit, filterable authority state.

### `timeline_projection_generation` / `timeline_projection_member` / `timeline_projection_receipt`

Each immutable generation pins source membership, display policy, Timesketch schema/fork version,
content/membership hashes, bounded attributes and activation state. A member maps to Timesketch's
required `datetime`, `message`, and `timestamp_desc`, while retaining exact source/version IDs,
occurred-at point or interval, temporal confidence, entity refs, authority, verification, dispute,
privacy/privilege, revocation and generation hash. OpenSearch/Timesketch remains rebuildable.

### `timeline_curation_batch` / `timeline_curation_item`

One attributable individual/bulk request records actor, rationale, idempotency identity, expected
projection generation and strict-atomic or itemized-partial mode. Every item records target type/ID/
version, operation, before/after hashes, validation result and `accepted|rejected|conflict|no_op` state.
Accepted context edits append typed annotations, classifications, time proposals, entity/grouping
assertions, candidate decisions, inclusion/order decisions, or successor derived-context versions.

### `timeline_amendment_candidate` / `timeline_curation_reversal`

Any edit proposed against an evidence-approved/governed timeline member becomes a context-layer
amendment candidate linked to the exact approved entry, fact/assertion version, citations and batch.
The approved version remains unchanged until independent re-review/reconciliation appends a governed
successor. Undo is a compensating batch linked to the original; no edit history is deleted.

Fork-local tags/comments/manual edits/analyzer output never become canonical merely because OpenSearch
accepted them. The authenticated PG command result and subsequent reprojected generation are the only
accepted state.

## 11. Realization events

### `realization_event`

Immutable event with the singleton personal-case/subject perspective, time/interval, kind, proposer,
approval history, and provenance.

### Typed target tables

- `realization_record_target`
- `realization_claim_target`
- `realization_fact_target`
- `realization_source_span`

Use real foreign keys rather than `(target_type, target_id)`. A deferred constraint requires at
least one target. Realizations never alter source availability.

## 12. Walk-local beliefs

### `walk_specification`

Immutable singleton-case binding, agent role, horizon policy, source/fact scope manifest, schedule, model/prompt/tool
versions, base version, and projection generation.

### `walk_run`, `walk_step`, `walk_retrieval_observation`

Preserve the current ledger concepts while making query/rank/store occurrence explicit. One step may
record the same logical item from several queries/stores.

### `belief_thread` / `belief_event`

- Belief thread belongs to exactly one walk.
- Events are immutable proposals, acceptance/rejection, qualification, contradiction,
  supersession, or invalidation.
- Belief support uses typed links to retrieval receipts, records, approved realizations, claims, and
  facts.
- A belief never becomes active memory in another walk.

### Checkpoints, seals, and rewalks

- Healthy checkpoint contains step/horizon, state/trace hashes, belief references, retrieval
  manifest, and projection reconciliation hash.
- Terminal seal is immutable and non-resumable.
- `rewalk_edge` links one new walk to one sealed prior walk with an attested change manifest.

## 13. First-class paired delta

### `walk_pair`

Exactly one ignorant and one hindsight run with compatible singleton-case binding, scope manifest, base version, projection
generation, schedule, and controlled comparison variables.

### `delta_snapshot`

Immutable comparison execution with input/output manifests and hash.

### `delta_item`

One classified belief/knowledge difference: addition, invalidation/removal, contradiction,
confidence change, realization change, or other governed type.

### Typed basis/anchor tables

- `delta_belief_basis`
- `delta_record_basis`
- `delta_realization_basis`
- `delta_claim_basis`
- `delta_fact_anchor`
- `delta_source_citation`

An analytical delta may exist without a fact anchor. A deferred constraint requires at least one
established-fact anchor plus exact custody-backed citations before `court_eligible` approval.

### `delta_supersession`

New comparisons supersede old snapshots when source membership, custody state, policy, or projection
changes. Old deltas are never silently refreshed.

## 14. Legal and court work products

### `legal_work_item`

Singleton-case investigation/strategy/task. It never creates Matter/CourtCase rows.

### `work_product` / `work_product_version`

Created work identity and immutable content versions. This is valid `artifact` vocabulary.

### `context_created_work` / `context_created_work_version` / typed source links

Generated briefs, motions, affidavits, declarations, discovery papers, exhibit plans, timelines, code,
and attachments extracted from chats remain context-created works with immutable versions and exact
conversation/message/span or archive-asset lineage. An attributable `created_work_adoption_event` may
copy/select one exact version into a new R12 draft `work_product_version`; adoption neither alters the
context-created work nor makes its chat source evidence.

### `legal_work_item` candidate adoption

An attributable materialization event may turn a reviewed `strategy_candidate` into a legal work item.
It retains candidate lineage and assumptions, but gains no factual authority.

### `legal_assertion`

Each factual proposition made in a work-product version.

### Typed citations

- `assertion_fact_citation`
- `assertion_delta_citation`
- `assertion_evidence_citation`
- `assertion_legal_authority_citation`

Released factual assertions must close through established facts/delta fact anchors to exact
custody-backed spans. Raw context, candidates, unapproved realizations, and walk beliefs are not
direct court citations.

### Proceeding-specific objects

Filings, hearings, orders, docket/service events, exhibits, and release packages belong to the
singleton personal case and carry source-faithful court/docket metadata where applicable.
Release/withdrawal/supersession are immutable attributed events.

## Database-enforced authority constraints

1. Successful H1 attestation is required before evidence activation.
2. Evidence eligibility exists only through `evidence_record_binding`.
3. Candidates cannot be FK targets for court release or fact authority without establishment.
4. Established facts require attributable decisions and qualifying custody-backed support.
5. AI-chat conversations/messages/exports can never bind to custody, fact support, evidence citations,
   or evidence promotion. Their lineage contributes zero evidentiary support.
6. First-party/acquired-third-party record-version membership is mutually exclusive.
7. Acquired-third-party participant sets exclude the owner; first-party sets require the owner,
   subject to explicit source-native system-message exceptions.
8. New Matter/CourtCase rows and caller-selected scope changes are rejected; legacy compatibility
   IDs cannot authorize or partition reads.
9. Every edit to an evidence-approved timeline member creates a context amendment candidate; direct
   update of the approved member/fact/evidence lineage is rejected.
10. The Timesketch fork can write only authenticated typed curation commands, never canonical tables,
    OpenSearch-to-PG replication, evidence, facts, realizations, or legal releases.
9. Approved realization requires at least one typed target.
10. Walk resume requires exact checkpoint/projection reconciliation; terminal seals cannot reopen.
11. Court-eligible delta items require established-fact anchors and exact citations.
12. Append-only authority roles receive no `UPDATE` or `DELETE`; corrections use successor/events.

## Horizon-safe read surface

Agent roles receive no direct read grant on retrieval base tables. A security-barrier view or
parameterized function binds the singleton case server-side and requires explicit horizon, disclosure context, actor/grant, and pinned
projection generation. Missing parameters return zero rows and an error.

The predicate sequence is fixed:

1. server-bound singleton personal-case scope;
2. active evidence binding and custody eligibility;
3. pinned boundary generation;
4. `source_available_from <= horizon_at` for as-lived mode;
5. disclosure/access policy;
6. only then keyword/vector rank or graph expansion.

Indexes begin with the source boundary, for example
`(source_available_from, record_version_id)`, with any fixed `case_id='primary'` retained only when
required for compatibility. Every external vector/graph object carries the same typed boundary and
generation. Post-top-k horizon filtering is prohibited.

## Compatibility map from current relations

| Current family | Provisional target | Treatment |
|---|---|---|
| `evidence.raw_*`, `raw_rejected`, ingest/funnel views | context source/member/record/span | Move boundary and repoint readers atomically |
| `analysis.knowledge_evidence_promotion` | promotion request/item/result | Reshape into executable, append-only D-069 writer contract |
| `evidence.source`, hashes, file/custody events | evidence custody primitives | Keep identity/history; change sole writer to promotion |
| `working.normalized_record` | normalized record + immutable versions | Reshape last; compatibility view during cutover |
| `working.normalized_record_chunk` | record chunk | Re-key to record version and inherited boundary |
| `working.message` / conversation / participants | first-party family | Preserve separate family; slim mixed analysis fields |
| `working.third_party_*` | acquired-third-party family | Preserve separate family and owner-exclusion contract |
| `working.chat_*`, context assets | AI-chat/context, typed candidates and created-work lineage | Keep permanently context-only; remove/hard-fence every evidence-promotion bridge |
| `message_projection_route` | cross-table exclusivity constraints | Replace; do not make a universal authored discriminator |
| `record_visible_from` | record horizon boundary | Replace/rename as version-pinned indexed derived projection |
| singular `realized_at` fields | realization events/typed targets | Retire only after view/constraint/read cutover |
| `candidate_fact` | `claim_candidate` plus exact sources | Transform with provenance reconciliation |
| `working.investigation_event*`, `analysis.corroboration_flag` | investigation lead/evidence need plus derived claim-chart view | Reconcile naming, typed anchors and authority; preserve history |
| `working.artifact_registry`, context assets, generated documents | context-created work/version/source links plus adoption event | Census writers/readers; preserve immutable works and explicit R12 adoption |
| `extraction_candidate`, `record_observation` | superseded candidate path | Quarantine later after zero-use proof; do not reuse for D-083 |
| `analysis.timeline_event`, `analysis.legal_timeline_event` | timeline source families plus immutable Timesketch projection/curation ledgers | Preserve authority identities; reconcile per-object before reader/writer cutover |
| `analysis.finding`/review/corroboration | fact/finding governance | Reshape around immutable assertion/support decisions |
| `walk_run/step/retrieval/checkpoint` | walk ledger | Keep/reshape; add belief and delta families |
| dormant legal task/export tables | legal work product model | Preserve exports, then rebuild rather than assume current shape |
| Agno/ops/reference tables | runtime/audit/config | Keep outside truth authority |

## Implementation slices

1. **Contracts only:** source revision/span, promotion command/result, evidence binding,
   `claim_candidate`, fact support/supersession, belief, and delta tables. No reader switch.
2. **Promotion writer:** live but unwired transaction with H1 verification and no partial custody.
3. **Context cutover:** raw schema move plus dependent views/readers in one boundary.
4. **Custody backfill:** run through the real promotion writer; reconcile every hash/count/link.
5. **Ingest switch:** context-only intake; promotion sole custody writer.
6. **Message families:** first party, acquired third party, then AI context, each independently
   reconciled.
7. **Spine reshape:** one concern family per migration, last among source tables.
8. **Claims/facts:** exact-source backfill, human approval canaries, append-only cutover.
9. **Walk/belief/delta:** cross-store prefilter canaries before any agent binding.
10. **Legal readers:** governed facts and approved anchored deltas only.
11. **Quarantine:** only after telemetry, dependency proof, checked export, restore rehearsal, and
    owner approval; move packages under `to_be_deleted`, never permanently delete.

## Explicit holds

- No physical schema/table rename is approved by this draft.
- No current column is approved for removal.
- No live relation is approved for quarantine.
- No dual-write/cutover period is approved.
- No migration, deployment, role change, graph/vector activation, or legal-reader switch is approved.
