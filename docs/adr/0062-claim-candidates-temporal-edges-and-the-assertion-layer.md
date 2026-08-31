# ADR-0062: Claim candidates, temporal edges, and the assertion/synthesis layer

- Status: **Accepted** — owner rulings across the 2026-08-29 design session
- Date: 2026-08-29
- _Byline: Claude · Opus 5 · 2026-08-29_
- Amends: **ADR-0052 ruling Q6 / D-054** (the `claim_candidate` naming, corrected below)
- Implements: ADR-0053 §7 deferred work — "entity/claim/time/event candidates"
- Preserves: ADR-0044 evidence/context boundary · ADR-0045 §B single authored spine ·
  D-082 (AI chats are permanently context-only)
- Migration: `sql/0052_claim_and_assertion_candidates.sql`
- Design detail: `docs/design/CLAIM-AND-ASSERTION-CANDIDATES-2026-08-29.md`

## Context

The platform's chat corpus — several hundred conversations — has no extraction target. The
tables ADR-0053 §7 deferred were never built, and `working.claim_candidate` exists only as a
string inside a CHECK constraint on `working.investigation_event_source`.

Separately, a prior high-capability extraction produced three analysis documents over one
source conversation. They contain reasoning worth keeping and no atoms underneath them: the
panels cite nothing addressable, so nothing in them can be expanded, verified, or queried.
That is the shape this ADR is built to prevent repeating at corpus scale.

## Decision

### 1. ADR-0052 ruling Q6 is amended

Q6 removed `artifact_candidate` because *artifact* reads as a **created work**. It then
renamed that row to `claim_candidate` and described it as a legal-document extractor
("MCL 722.23 factors, case/court/docket references, parties, motions, allegations, dates").

Owner ruling, 2026-08-29: a legal document extracted from a chat is **a production, a work
product — not a claim.** Three distinct outputs were compressed into two names:

| Output | Merge semantics | Home |
|---|---|---|
| **Claim** — a narrated assertion made in a chat | accumulates; never merged or rewritten | `working.claim_candidate` (this ADR) |
| **Entity** — a person, org, or thing referenced | dedup-merged | existing layers, untouched |
| **Created work** — a document, timeline, or analysis *produced* in a chat | versioned as a work product | **deferred; needs its own name** |

`working.claim_candidate` is hereby the narrated-assertion row. Q6's merge-semantics
ruling — entities merge, claims accumulate and are never rewritten — is unchanged and is
the load-bearing rule of this design, enforced by an append-only trigger on content columns.

### 2. Review is pulled by the work, never pushed by the pipeline

**There is exactly one human on this system.** A design that queues a decision per extracted
row is a design that does not run. An earlier draft of this ADR put
`review_state DEFAULT 'pending'` on `claim_candidate` and `claim_temporal_edge`; at corpus
scale that is tens of thousands of rows awaiting approval for material that cannot be filed,
cited, or promoted. Approving one changes nothing. The queue only grows, and its existence
degrades every other "pending" in the system into noise.

That is the same endpointless standard the corpus itself already diagnosed — a bar with no
finish line, which is why the work never finishes.

**Rule: extraction output is `active` on write.** Claims and edges carry a `lifecycle` of
`active` / `superseded` and no approval gate. Correction is supersession, never rejection.

Human attention is spent only where a decision changes an outcome:

| Gets human judgment | Does not |
|---|---|
| Promoting material to evidence | Confirming an extractor read a sentence correctly |
| Resolving a time anchor (one inference standing in for many edges) | Approving each ordering statement |
| Accepting an assertion about to be relied on | Every assertion the model ever emitted |
| A divergence blocking work actually in progress | Every divergence in the corpus |

`claim_assertion.owner_disposition` defaults to `unreviewed`, and **`unreviewed` is a
resting state, not a backlog.** Nothing should ever present "clear the unreviewed
assertions" as a task. Disposition is set when the owner reaches for that assertion,
argument-scoped, the same way promotion is.

Corollary for the deferred batch-failure work: a rejection table is a **diagnostic, sampled**
— not a second queue to be cleared.

### 3. Context side only; no promotion anywhere

AI chats are permanently context (D-082). No table created by this ADR carries a promotion
column, because nothing extracted from a chat has anywhere to be promoted to. Evidence,
custody binding, corroboration, and evidence pointers are the next phase. The phase boundary
is structural, not procedural.

### 4. Placement: land beside, do not reconcile

Owner ruling: the pre-existing candidate layers (`analysis.extraction_candidate`,
`analysis.entity_candidate`, `working.candidate_entity|fact|event`) are **not reconciled
here**. New tables land beside them. Reconciliation is its own change and its own ruling.

Raw landing tables — `working.chat_conversation`, `chat_message`, `chat_chunk`, and the
`context.*` raw tables — come from actual sources and are **referenced, never altered**.
This migration is additive only.

### 5. Speaker attribution is enforced, not conventional

`CHECK ((speaker_role = 'assistant') = (claim_class = 'AI_PROPOSAL'))`.

An assistant framing recorded as the subject's own account is the single worst failure this
system can produce, because it is invisible on inspection and its consequence is a filing.
The guard is a constraint, not a prompt instruction.

> **Known limitation, open for revision.** The biconditional also forces an assistant turn
> quoting an actual document into `AI_PROPOSAL`, when it is properly a `DOCUMENT_QUOTE`.
> The two errors are asymmetric — a lost fact is recoverable, contamination is not — so
> strict-both-ways is the safe starting position. The proposed fix is to split the concept:
> keep `speaker_role` (who typed it) and add `originates_with` ∈
> `subject|assistant|document|third_party` (whose claim it is), enforcing the biconditional
> on `originates_with` instead. Not adopted in this ADR; recorded so it is not rediscovered.

### 6. Time is captured as stated and resolved elsewhere

A claim never carries a resolved date. `date_raw` holds the literal phrase; there is no
`date_iso`, no `occurred_at`, and no `validity` on `claim_candidate`. A claim *about* a date
is not an event.

**`working.claim_temporal_edge`** records ordering **as stated**: `before` / `after` /
`same_window` / `during` / `approximately_at`, with the verbatim span it was read from and
the literal offset phrase. There is deliberately **no `date_relative_to` free-text column**
on `claim_candidate` — two representations of one relationship, only one of them computable,
is a drift generator.

The other end of an edge is either an extracted claim **or an unresolved phrase**. Windowed
extraction means most ordering references point outside the current window; an edge that
required a resolved target would discard nearly all of them. Resolution is additive and
never overwrites the original phrase.

**Why this must be captured at extraction time:** ordering is only visible in the sentence
where it was spoken. The utterance clock (`chat_message.occurred_at`) bounds a phrase like
"last August"; the edge chain propagates that bound; a single absolute date anywhere in the
chain collapses the rest. Discard the edges at extraction and no later pass can recover them.

`context.relative_time_anchor` is **unchanged** and remains the home of resolved placement —
it already carries `placement_kind`, bounds, before/after anchor links, confidence,
`review_state`, and `supersedes_id`. Edges are its input; anchors are its reviewed output.
`claim_candidate.relative_time_anchor_id` is an inert, nullable seam, unpopulated in this
phase.

### 7. Temporal edges live in PostgreSQL, and are projected nowhere yet

Temporal edges are a graph *shape*, which is not the same as a graph *workload*. Decided on
the measured properties of this data, not by deference to a prior ADR:

| Property | Measured / estimated | Implication |
|---|---|---|
| Volume | ~5–50 ordering statements per conversation; ~10⁴ edges across the corpus | Not a graph-scale problem |
| Traversal depth | 2–6 hops; people narrate linearly | A recursive CTE is sufficient |
| The actual computation | interval propagation from edges + one absolute anchor | Neither Cypher nor SurrealQL does interval arithmetic; the solver gets written either way |
| Mutation model | append-only, superseded not edited, per-row review state, contradictory edges retained | Relational strength, graph-DB weakness |

The hard problem here is constraint solving, not pattern matching. A graph engine would
solve the easy half and leave the hard half untouched, while adding a store to keep in sync.
**PostgreSQL is the authoring home on the merits.**

**No projection is created by this ADR.** SurrealDB carries the D-073/D-080 designation as
the reconciled temporal-graph and analysis engine, but as of 2026-08-29 its analytical role
stands at `docs/UNRESOLVED-QUESTIONS-2026-08-16-surreal-investigation-phase0.md` — open
questions, not a proven service. Graphiti is retired (D-070) and Milvus is deliberately
down. Projecting authored data into a store that is not operationally proven buys a sync
surface and a drift risk for no present capability.

**Sequence instead:** build the recursive CTE and the bounds solver against PG, demonstrate
that a relative phrase resolves to a year given one absolute anchor, and only then evaluate
whether any downstream consumer needs a projection. If one does, it is a derived,
version-pinned, single-writer materialization — never a second authoring home. That
constraint is independently correct and also happens to be what ADR-0045 §B requires.

> **Note on reasoning, owner directive 2026-08-29.** An earlier draft of this section
> justified the same conclusion by citing AGENTS.md and ADR-0045 rather than by evaluating
> the workload. That is how a misreading becomes canon: each document inherits the prior
> one's authority without re-testing it. Prior rulings are evidence about what was decided,
> never a substitute for evaluating the current shape of the data. Where this ADR and an
> earlier ruling agree, they should agree for independently stated reasons.

### 8. Assertions have two generations and a hard depth cap

The AI/analysis layer — panels, connections, framings — has `working.claim_assertion` plus
two member tables.

| | Generation 1 — assertion | Generation 2 — synthesis |
|---|---|---|
| Members | `claim_candidate` rows only | generation-1 assertions only |
| Minimum | 1 | 2 |
| May cite a synthesis | n/a | **never** |

There is no generation 3. Owner ruling, 2026-08-29:

> "As long as it's not an analysis of an analysis, but the synthesis of the same
> first-generation analysis just based on a different iteration, we can maybe get a complete
> idea of everything."

Several first-generation passes will read the same conversations at different times, with
different prompts, or by different models. Each sees part of it. The synthesis is the union,
and it is worth more than any single pass. Analysis *of* analysis is the opposite: the chain
stops reaching anything a person said, and confidence inflates while evidence stays constant.

"Members must be generation 1" is enforced by a composite foreign key to
`(id, assertion_generation)` — a referential fact rather than a trigger's opinion.
Cardinality and member-kind agreement span rows and are enforced by a deferred constraint
trigger.

### 9. Synthesis preserves variance; it does not resolve it

When two generation-1 assertions about the same material disagree, the synthesis records
the disagreement. It does not pick a winner and does not average. Each synthesis member
carries `concurs` / `diverges` / `extends`, and a divergence must be explained.

Divergence between independent readings is signal: it marks where the material is genuinely
ambiguous or where one pass saw something the others missed. Collapsing it silently is the
same defect as deduplicating claims.

Adjudication is a new assertion with `supersedes_id`, never an edit.

## Consequences

- The chat corpus has an extraction target for the first time.
- Every analysis claim is one hop from something a person actually said, or it cannot be
  accepted.
- Relative time survives extraction intact and becomes resolvable in bulk once a single
  absolute anchor lands, rather than requiring per-claim hand resolution.
- Redundancy grows deliberately: the fortieth retelling is a fortieth row. Storage is the
  cheap side of that trade; lost variance is unrecoverable.
- Nothing in these tables can be filed, cited, or produced. That is a constraint and also
  the reason extraction can be complete and unflinching.

## Already ruled — apply, do not re-decide

**Batch failure handling is settled.** D-054 point 7 (owner-signed 2026-08-12):
**dead-letter table + replay tool + mandatory alert on count>0**, surfaced on the
operator-console cdc-status view; nothing silently dropped. D-085 adds the batch semantics:
**partial bulk success is explicit, conflicts fail closed, undo is a new compensating batch
rather than a deletion.**

Applied to this ADR, that means the implementation work — not a decision:

- per-row transactions, never a whole-run abort;
- `working.claim_candidate_rejected` as the dead-letter table, holding the full attempted
  payload, the constraint that failed, and run/window, with a replay tool;
- `claims_rejected` on `extraction_window`, alerting on count>0;
- grounding as a `grounding_state` column that gates `owner_disposition='accepted'` rather
  than raising at COMMIT.

Per §2, the dead-letter table is a **diagnostic that alerts**, not a queue to be cleared.
**Status: not yet implemented in `sql/0052`.**

**Entity identity is settled.** D-071 (owner-ruled 2026-08-25): `message_participant →
entity` is the address-book link used for entity resolution, and sender/recipients/
participants columns stay on the message record — a "trim" that removes them is rejected.
Any alias work builds on that link and does not invent a parallel mechanism. See
`docs/design/DUAL-GRAPH-IDENTITY-AND-WRITEBACK-2026-08-29.md`.

**Redaction is settled and does not apply here.** D-092 (2026-08-27): canonical content is
never redacted at intake, extraction, storage, or ordinary query; redaction happens only in
an explicitly requested derived court-facing output. Nothing in this ADR carries redaction
state. (Provider-side redaction of a source conversation is a separate availability problem
— see `docs/design/GROUNDING-VS-UNAVAILABLE-SOURCES-2026-08-29.md`.)

## Genuinely open

1. `originates_with` split (§5 limitation above).
2. `provenance_depth` — marking a claim whose verbatim was quoted inside a derived analysis
   document rather than read from the original conversation. Searched `DECISION_LOG.md`,
   `PROJECT_CANON.md`, and `docs/adr/`: no prior ruling.
3. Migration number confirmation. D-098 records that `0049` is scaffolding only and
   uncommitted; `0050`/`0051` were also uncommitted on disk when this was authored.
4. Whether `argument_targets` becomes a controlled reference table. The MCL 722.23 ontology
   is named across `PROJECT_CANON.md` §93/§592 and ADR-0019/ADR-0052 as real and imported,
   but no enumerated table exists. Making it one is what turns coverage-by-argument into a
   computed number instead of an impression.
5. Harvesting the three existing analysis documents into `claim_assertion` as generation 1.
