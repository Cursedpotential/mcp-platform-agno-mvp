# Phase-0 Contracts — Surreal Investigation, Projection, and Walk Memory

> _Byline: Codex · GPT-5 · 2026-08-16 · owner-ruling amendment 2026-08-16 ·
> ADR-0059 supersession amendment 2026-08-18_
>
> **Status:** ACCEPTED BY OWNER 2026-08-16 — logical contracts only
> **Implementation authority:** NONE. This document does not authorize schema, migration,
> corpus copy, Surreal activation, deployment, Graphiti replacement, or production writes.

## 1. Contract boundary

These contracts implement the accepted boundaries in ADR-0056 through ADR-0058 without
choosing a framework, database client, physical schema, embedding model, or agent runtime.
They extend rather than replace the existing `NormalizedRecord`, Matter/CourtCase, Horizon,
and belief-memory contracts.

The invariant is one-way authority:

```text
custody-backed source -> normalized representation -> candidate claim -> investigation
-> governed review -> established fact -> court-safe work-product candidate
                               |
                               +-> rebuildable analytical/belief projections
```

No arrow reverses authority. A Surreal, Weaviate, Neo4j, Graphiti, model, or extraction
result cannot update canonical truth by being retrieved, repeated, ranked highly, or stored.

## 2. Authority and material classes

| Material class | Meaning | Authoritative owner | May become court-facing directly? |
|---|---|---|---|
| Extraction output | Machine-produced entity/time/event/claim proposal | PostgreSQL candidate ledger | No |
| Candidate claim | Append-only proposition requiring investigation | PostgreSQL | No |
| Investigation material | Bounded query plan, hits, classifications, gaps, and trace | PostgreSQL run/audit records | No |
| Established fact | Immutable reviewed assertion with exact selected evidence links | PostgreSQL | Only through separate Case Prep/release review |
| Agent belief | What one agent/run had accepted or inferred at one walk step | PostgreSQL belief-event ledger; Graphiti/Surreal are projections | No |
| Analytical projection | Rebuildable promoted representation for retrieval/analysis | PostgreSQL promotion decisions remain authority | No |
| Work product | Authored analysis, chronology, draft, or export candidate | PostgreSQL work-product/review authority | Only after its own review gates |
| Court-safe export | Conduct-first, source-resolved, reviewed rendering | PostgreSQL release/audit authority | Yes, after explicit release |

“Artifact” remains reserved for created works. Extraction outputs are candidates, never
artifacts or facts.

## 3. Common envelope and identifiers

Every contract object carries the following logical envelope. Names are semantic; they are
not proposed column names.

| Field | Requirement |
|---|---|
| `contract_name` | Stable platform-owned name, independent of Agno/Spectron/Surreal SDKs |
| `contract_version` | SemVer-like immutable schema/API version |
| `object_id` | Opaque stable platform ID; never one UUID reused across identity layers |
| `matter_id` | Required scope for case material |
| `court_case_id` | Optional proceeding scope; never substitutes for Matter |
| `created_at` / `created_by` | Attributable system-record time and actor |
| `revision` | Immutable revision identity; corrections create a successor |
| `supersedes_id` | Optional pointer to the prior revision |
| `authority_state` | Candidate, reviewed, approved, rejected, revoked, or derived as applicable |
| `policy_version` | Exact promotion/retrieval/review policy applied |
| `trace_id` | Correlation into append-only audit/run reporting |

All external references use platform IDs. Adapter-native IDs may be carried only inside a
typed `ProjectionLocator` and never become the public identity.

## 4. Time and horizon contract

The source and experience clocks are distinct and never silently substituted:

| Clock | Meaning |
|---|---|
| `valid_time` | When the asserted event/state occurred in the world; may be an interval |
| `source_available_time` | When the source first became accessible to the selected subject: occurrence for first-party messages, acquisition for acquired-third-party messages |
| `realization_event_time` | Zero-to-many governed moments/intervals when the selected subject formed later derived understanding |
| `recorded_time` | When the platform recorded the representation; audit only |
| `decision_time` | When a review, promotion, or belief decision was made |
| `walk_observed_time` | When one walk agent actually encountered it |

Source retrieval uses ADR-0059's `source_available_from`: `occurred_at` for first-party messages
and custody-backed `acquired_at` for acquired-third-party messages. The acquired thread retains
its actual sender, recipients, and participants; the owner is not a historical participant.
Realization events are plural linked derivations and never replace or backdate source availability.
`knowledge_time` remains audit-only and is never a horizon predicate.

When realization is uncertain, the contract preserves the earliest and latest plausible bounds
plus a computed midpoint proposal. The midpoint is not an approved timestamp. HITL review must
approve it, choose another evidence-supported point, narrow the interval, or leave the realization
unresolved. Until that attributable decision exists, the proposed realization is ineligible for
realization/belief views; it does not hide an otherwise source-available message. Later
clarification creates a new realization revision; it never rewrites the prior
interval, decision, or historical walk.

`HorizonContext` is immutable and contains:

- `matter_id`, `walk_id`, `run_id`, `agent_role`, and `horizon_id`;
- mode: `as_lived_so_far`, `hindsight`, or one side of `paired_delta`;
- selected subject/knowledge actor;
- horizon instant or interval policy;
- disclosure and authority floors;
- content, retrieval, projection, prompt, tool, model, and policy versions;
- manifest hash plus the ordered activation-step hash;
- allowed source/profile/namespace IDs and explicit exclusions.

The mode is bound server-side. A caller may request a mode but cannot widen its own context.
Unsupported or unverifiable predicates fail closed before ranking or traversal.

## 5. Source-centered promotion contracts

### `SourceManifest`

Identifies one custody-backed source without copying its original bytes. Required fields are
canonical source ID, H1/SHA-256 binding, byte size, media type, acquisition/custody version,
normalization revision, authority state, `content_exposure` (`manifest_only`, `selected_spans`,
or `full_normalized_text`), and `binary_replication` (`reference_only` or `verified_copy`).
Binary replication never grants search eligibility or canonical authority.

### `PromotedSpan`

Represents one approved slice of a source. It carries the source revision, exact typed locator,
content-binding hash, approved normalized text/structure, promotion decision, temporal axes,
and sensitivity/access policy. A quote without its exact locator and custody path is invalid.

### `NormalizedRepresentation`

Represents source-level approved normalized content. It is eligible only after explicit
`full_normalized_text` approval. Approval of one span never implies source-level approval.

### First-party/acquired-third-party projections, `StructuralAtom`, `RetrievalChunk`, and `EmbeddingInstance`

- Canonical normalized messages are authored once. Analytical first-party and acquired-third-party
  message tables are separate version-pinned derived projections, not independent truth stores.
- Acquired-third-party projections require actual sender/recipient/participant identities, exclude
  the owner from participants, and link zero-to-many realization records separately.

- A structural atom is parser-emitted source structure with a stable locator within a parser
  and source revision.
- A retrieval chunk is a versioned grouping of atoms. Rechunking creates a new generation.
- An embedding instance belongs to exactly one chunk generation and one embedding profile.
  It carries provider/model/revision, input task, dimensions, numeric/normalization policy,
  truncation, content hash, chunk-policy version, and collection/index identity.

No one identifier may stand for source, atom, chunk, vector, claim, and fact simultaneously.

### `PromotionDecision`

An append-only owner/governance decision with independent content-exposure and binary-replication
policies. Revocation or correction creates a new decision and causes projections to become
ineligible/rebuildable; it does not erase the prior decision.

### `ProjectionReceipt`

Records projection target, target-native locator, canonical input IDs/hashes, projection and
adapter versions, written object counts, reconciliation hash, checkpoint, and status. A receipt
proves an attempted/materialized projection, not canonical approval.

## 6. Claim-centered investigation contracts

### `ClaimCandidate`

An append-only extracted or human-entered proposition with proposition text/structure,
subjects, predicates, objects, time/location qualifiers, provenance for its origin, confidence,
and candidate state. It is never an established fact by configuration or score.

### `ClaimInvestigation`

A versioned run binding one or more candidate claims to an immutable `InvestigationPlan`,
`AnalysisScope`, budgets, authority floor, horizon mode, versions, and trace. A new scope or
policy creates a new investigation revision.

### `InvestigationPlan`

Contains normalized questions, aliases, source requirements, independent-source rules,
required disconfirmation/alternative queries, ordered retrieval stages, exact budgets, stop
conditions, and expected-missing evidence. Plans are inspectable before execution.

### `EvidenceHit`

One returned item with canonical source/span/chunk coordinates, retrieval surface, eligibility
proof, score/rank within its own profile, classification (`supporting`, `contradicting`,
`qualifying`, `contextual`, `duplicate_derived`, or `unresolved`), reason surfaced,
lineage/independence group, and exact trace step. Ranking never establishes truth.
`missing_expected` is an `EvidenceExpectation` containing the expected source/kind/time/actor,
search coverage, and absence confidence; it never fabricates a source span.

Derivative files or messages sharing custody/content lineage belong to one source family unless
review proves independent observation or creation. Every dossier reports raw-hit count and
independent-source-family count separately; preservation multiplicity is not corroboration.

### `FactDossier`

Frozen review input containing the claim, plan, all selected and rejected hits, contradictions,
alternatives, gaps, source-independence analysis, budget exhaustion, limitations, and dossier
hash. Review cannot silently refresh it; new evidence creates a new dossier revision.

### `EstablishedFact` and `FactEvidenceLink`

An established fact is an immutable atomic reviewed assertion. Each many-to-many evidence link
names an exact source span and its role, weight/quality assessment, independence group, and
review rationale. Corrections use `supersedes`, `contradicts`, or `qualifies`; facts are never
rewritten in place. Establishment is not court release.

## 7. Investigation and behavioral-analysis run contracts

### `AnalysisScope`

An immutable manifest containing Matter, subjects and roles, zero or more non-contiguous date
ranges, selected events, conversation groups, sources, locations, exclusions, source revisions,
horizon mode, and expansion budgets. Closed-set inputs and outward discoveries are different
collections. Accepting a discovery creates a new scope revision.

### `InvestigationRun`

Uses one intent: `find_evidence`, `reconstruct_event`, or `discover_patterns`. It binds scope,
plan, ports, versions, budgets, results, trace, run report, and termination reason. Its query
trace records decomposition, filters, eligible counts before ranking, returned IDs, dedupe,
grading, retries, cost, and context construction.

### `BehavioralFinding`

Separates observed conduct, recurrence, evidence quality, functional impact, contradiction,
alternative explanation, limitation, internal lens labels, and authenticated diagnostic status.
Lens labels organize private analysis; they never assert diagnosis.

### `CasePrepCandidate`

A conduct-first rendering of approved material with exact citations, transformation policy,
excluded diagnostic shorthand, reviewer state, and release blockers. Generation does not mark
the candidate court-safe.

## 8. Belief and walk-memory contracts

### `BeliefEvent`

An append-only record of what one run/role proposed, accepted, rejected, superseded, qualified,
or observed, including upstream evidence/fact IDs, HorizonContext, decision and observation
times, confidence/uncertainty, prompt/tool/model versions, and prior event hash.

### Shared Surreal Context and `Walk`

The disposable product/environment uses one shared Surreal Context. Promoted evidence and facts
are stored once and partitioned by mandatory Matter and authorization scopes. A `Walk` is a
first-class workflow record—not a separate Context, evidence store, or truth clock—and binds
`walk_id`, `run_id`, role/mode, schedule, current horizon, projection revision, policy versions,
and status. `WalkStep` advances the horizon. Agent-created beliefs and observations bind to their
originating `walk_id`; shared promoted evidence does not.

Every as-lived read is bound to exactly one walk and horizon before ranking or traversal. Cache,
profile, consolidation, prompt-assembly, and retrieval state must include the Matter, walk,
horizon, projection revision, and policy identity or be unavailable to the as-lived path.

### `WalkCheckpoint`, `WalkSnapshot`, and linked rewalk

A healthy pause writes a resumable checkpoint containing current step/horizon, projection and
eligible-manifest hashes, state/trace hashes, and belief/retrieval references. It resumes the same
walk identity only when the checkpoint and projection still reconcile exactly.

On revocation, projection drift, hash mismatch, or another terminal integrity failure, the service
fails closed and seals the walk.
The immutable snapshot binds its step/horizon, projection and eligible-record manifests/hashes,
belief-event state, retrieved context and traces, versions, and failure reason. It is historical,
read-only, non-resumable, and ineligible for active recall. After reconciliation, a fresh walk
links through `rewalk_of`; comparison distinguishes input/projection changes from model, prompt,
tool, schedule, policy, and reasoning changes.

### `MemoryState` and `MemoryDiff`

`MemoryState` is a replayable projection at an event sequence/horizon. `MemoryDiff` compares two
states and classifies additions, removals-by-invalidation, contradictions, supersessions,
confidence changes, and realization changes. Projection state is never canonical evidence.

## 9. Framework-neutral service ports

| Port | Required operations | Fail-closed obligations |
|---|---|---|
| `CanonicalEvidencePort` | Resolve canonical IDs, spans, custody, versions, and authorized structured facts | No fuzzy fallback for provenance; no projection-native ID as authority |
| `PromotionPort` | Propose, review, revoke/supersede, project, reconcile, rebuild | Partial approval exposes only approved spans; receipt mismatch quarantines projection |
| `RetrievalPort` | Compile eligibility, search lexical/vector/graph/geo, explain, page | Apply Matter/authority/horizon predicates before ranking/traversal; preserve requested eligible `k` |
| `InvestigationPort` | Plan, execute bounded stages, classify hits, freeze dossier, inspect trace | Mandatory disconfirmation path; budgets and stop reason required |
| `FactReviewPort` | Review dossier, establish/qualify/contradict/supersede fact | Human/governed decision required; exact evidence links required |
| `HorizonContextPort` | Create run, advance, materialize manifest, retrieve, replay, rewalk, compare | Immutable manifest; no unbound read path; no post-filter-only adapter |
| `BeliefMemoryPort` | Append event, project, acknowledge, current/as-of search, diff, replay | Per-run/role isolation; projection acknowledgement and upstream provenance required |
| `BehavioralAnalysisPort` | Freeze scope, closed analysis, propose discoveries, revise scope, paired delta | No silent scope expansion; lenses and diagnosis fields remain separate |
| `CasePrepPort` | Transform approved findings, inspect citations/blockers, submit review, release | Conduct-first default; explicit attributable release; no status laundering |
| `EvaluationPort` | Load corpus manifest, run profile, score, compare, emit signed report | Versions and exclusions pinned; zero-leak gate cannot be averaged away |

Every port returns a stable result envelope with outcome (`success`, `partial`, `blocked`, or
`failed`), itemized errors, input/output hashes, version bindings, budget use, trace ID, and
durable run-report reference. “Partial” never means a safety predicate was skipped.

Normative operation families are:

- canonical reads: `get_manifest`, `resolve_span`, `list_structural_atoms`,
  `get_authority_revisions`;
- governance: `submit_candidate`, `open_investigation`, `record_evidence_relation`,
  `establish_fact`, `authorize_projection`;
- retrieval: `search`, `neighbors`, `explain`;
- projection: `plan_projection`, `apply_projection`, `reconcile`, `rebuild`, `quarantine`;
- investigation: `freeze_scope`, `plan`, `execute`, `expand`, `build_dossier`;
- walk memory: `create_walk`, `advance_walk`, `append`, `retrieve`, `reconcile`, `checkpoint`,
  `seal_snapshot`, `start_rewalk`, `diff`, `invalidate`, `export_trace`;
- behavior/Case Prep: `analyze_closed_scope`, `plan_outward_discovery`, `compare_modes`,
  `prepare_case_language`, `submit_review`, `release`.

Stable failures include `UNAUTHENTICATED`, `FORBIDDEN`, `SCOPE_MISMATCH`, `HORIZON_REQUIRED`,
`HORIZON_VIOLATION`, `AUTHORITY_NOT_FOUND`, `CUSTODY_MISMATCH`, `NOT_PROMOTABLE`,
`REVISION_CONFLICT`, `BUDGET_EXHAUSTED`, `CAPABILITY_UNAVAILABLE`, `PROJECTION_DRIFT`, and
`CONTAMINATION_DETECTED`. Adapters may not convert these into empty success responses.

## 10. Cross-store eligibility proof

Before any store is accepted, its adapter must expose a compiled eligibility plan and evidence
that filtering occurs before candidate ranking or graph expansion. The common logical predicate
is:

```text
matter matches
AND authority/review state is eligible
AND promotion is active at the requested revision
AND source/span access is authorized
AND source_available_from <= selected horizon for as-lived mode
AND disclosure policy permits the item
AND projection revision reconciles to canonical hashes
AND any agent-belief lookup matches the bound walk_id
```

For Weaviate, the implementation must use adapter-supported dictionary filters; Agno
`FilterExpr` lists are forbidden because the pinned adapter drops them. An adapter that cannot
prove prefiltering is ineligible for the as-lived path.

## 11. Projection and reconciliation behavior

- PostgreSQL approval/outbox state is the only projection trigger authority.
- Every projection object carries canonical IDs, hashes, revision, promotion scope, temporal
  axes, and policy version.
- Reconciliation compares canonical eligible membership and content hashes with target state.
- Missing, extra, stale, or hash-mismatched target objects quarantine the affected
  Matter/projection revision and block its as-lived reads until repaired.
- A healthy paused walk resumes from its exact checkpoint only while its original projection remains
  active and reconciled. A terminally blocked walk is sealed before repair; repair never resumes or
  rewrites it, and a reconciled projection receives a new linked walk.
- Rebuild starts from canonical decisions and receipts; it never imports truth from Surreal.
- Deterministic export/import includes source-class projections, plural realization links,
  checkpoints, terminal snapshots, and rewalk edges. Equal export hashes and equal restored
  horizon-filtered retrieval are independent required postconditions.
- Original binaries remain in custody storage. Optional verified replication never changes
  authority or approval.

## 12. Explicitly unresolved physical choices

This contract intentionally does not decide:

- exact Surreal namespace/database/table/record layout or SDK inside the accepted shared-Context
  and mandatory Matter/walk-scope boundary;
- named vectors versus profile-specific Weaviate collections;
- embedding/reranking models and dimensions;
- memory versus corpus embedding-profile reuse;
- TraceIQ precision/retention representation;
- behavior-lens vocabulary and discovery-budget values;
- Graphiti replacement or official Spectron adoption.

Those choices require the evaluation gates and owner rulings in the companion Phase-0 packet.

## 13. Acceptance criteria for freezing this contract

1. Every canonical/projection/belief/work-product class has one unambiguous authority.
2. Candidate claims cannot become facts without a frozen dossier and review decision.
3. Every fact resolves through exact spans to a custody-backed source revision.
4. Every as-lived read is bound to one immutable HorizonContext and prefiltered in every store.
5. Partial promotion cannot expose unapproved normalized text.
6. Closed behavioral scope cannot expand without a new revision.
7. Projection loss/rebuild cannot alter canonical decisions.
8. Contract tests import no Agno, Graphiti, SurrealDB, Weaviate, or database client.
9. R9 activation holds remain unchanged.
10. Historical walk snapshots remain replayable but cannot become active retrieval fallback.
11. Unapproved realization midpoint proposals produce zero realization/belief-view visibility;
    independently source-available messages remain retrievable under their source clock.
12. Raw duplicate count cannot inflate independent corroboration count.
