# ADR-0059 — First-party and acquired-third-party message projections, source clocks, and resumable walks

> _Byline: Codex · GPT-5 · 2026-08-18; native evidence-vector amendment 2026-08-18._

- **Status:** Accepted (owner ruling 2026-08-18)
- **Decision:** D-065
- **Supersedes in part:** ADR-0045 Decision A/A.4 and ADR-0056 Decision 10
- **Preserves:** ADR-0045 Decision B/C; ADR-0056's PostgreSQL authority, governed
  Surreal projection, shared Context, and activation holds

## Context

The earlier universal `visible_from = COALESCE(realization, occurrence)` rule conflated
three different facts: when a message occurred, when its source first became available to
the owner, and when one or more later realizations were formed from it. That happens to work
for first-party messages known as they occur, but it leaks old third-party conversations into
an as-lived walk before the owner acquired them and collapses several realization events into
one date. Acquired conversations also have their own real senders, recipients, and participants;
the owner is the acquirer/evidence subject, not a fictional participant in the historical thread.

The walk lifecycle had a related ambiguity: a healthy, deliberately paused walk must be
resumable under the same identity, while a walk stopped by projection drift or another terminal
integrity failure must never resume from contaminated state.

## Decision

1. **One authored spine remains authoritative.** Messages are normalized once in the canonical
   PostgreSQL spine with custody/provenance. First-party and acquired-third-party message tables
   in analytical stores are separate, rebuildable, version-pinned **derived projections**, not
   parallel authored truths. Derived chunks and embeddings come from those projections and carry
   their source identity and clock; chunks are never an authored message store.
2. **The source classes have distinct participant and availability contracts.** A first-party
   message is between the owner and another participant and becomes source-visible at
   `occurred_at`. An acquired-third-party message preserves its actual sender, recipients, and
   participants; the owner MUST NOT appear in that participant set. It becomes source-visible at
   the acquisition time recorded by custody/provenance, even when `occurred_at` is years earlier.
3. **Three clocks stay separate.** `occurred_at` is valid/event time. `source_available_from` is
   the earliest horizon at which the source may be retrieved: occurrence for first-party messages,
   acquisition for acquired-third-party messages. A message then has zero-to-many realization
   links, each with its own interval/date, kind, provenance, proposer, and approval state.
   Realizations accumulate and are never folded into one writable date or used to backdate source
   availability. A derived realization/belief view may apply its own approved-event predicate, but
   source retrieval always gates first on `source_available_from` before ranking.
4. **Healthy pause and terminal failure are different transitions.** A healthy walk writes a
   version-pinned checkpoint containing its current step/horizon, state and trace hashes, belief
   references, and retrieval references. It may resume the **same walk identity** only when that
   checkpoint and its projection guard still reconcile exactly. A projection revocation, drift,
   mismatch, or other integrity failure seals an immutable, non-resumable terminal snapshot.
   Reconciliation then starts a new walk identity connected to the sealed walk by an explicit
   `rewalk_of` edge and an attested change manifest. A sealed snapshot is historical comparison
   input, never active recall or fallback memory. A transient operational pause may resume only
   after proving the original projection remains healthy and unchanged; otherwise it is terminal.
5. **Projection and restore receipts prove the boundary.** Membership/content hashes and counts
   cover exactly the authorized projected records. Export/import includes checkpoints, terminal
   snapshots, realization links, and rewalk edges, and must reproduce both canonical export hashes
   and horizon-filtered retrieval results before any activation decision.
6. **Evidence vectors use a native, versioned Weaviate projection.** Evidence chunks move off
   Agno's JSON-metadata collection contract to immutable `EvidenceChunkV1`, exposed after a held
   operator cutover through the stable `EvidenceChunks` alias. `occurred_at` and
   `source_available_from` are typed dates, the source boundary is range-indexed and applied before
   ranking, and supplied-vector/embedder/projection identities are explicit. This decision does
   not authorize collection creation, backfill, alias movement, reader rebinding, or migration
   application. The prior Agno evidence collection remains the rollback target until exact
   count/hash/canary reconciliation and owner-approved activation complete.

## Alternatives considered

### Keep one universal message projection

- **Pros:** fewer tables and query branches.
- **Cons:** invites participant fabrication and hides the acquisition boundary.
- **Why rejected:** first-party and acquired-third-party conversations have materially different
  provenance and horizon semantics.

### Continue using earliest approved realization as universal visibility

- **Pros:** reuses ADR-0045's existing predicate.
- **Cons:** conflates possession with interpretation, cannot represent several realizations, and
  may expose a third-party source before acquisition.
- **Why rejected:** realization is derived knowledge about a source, not source availability.

### Resume every paused walk or replace every pause with a new walk

- **Pros:** either choice produces a simpler state machine.
- **Cons:** the first can revive contaminated state; the second destroys continuity after a
  healthy interruption.
- **Why rejected:** checkpoint reconciliation provides the safe boundary between those cases.

## Consequences

### Positive

- As-lived retrieval can reproduce what the owner could actually access at each step.
- Third-party attribution remains historically accurate and multiple realizations remain legible.
- Healthy walks are resumable without making terminal snapshots active memory.
- Projection and restore parity are independently attestable.

### Negative

- Every projection, retrieval adapter, export, and test fixture must preserve source class and all
  three clock concepts.
- Queries spanning both message projections require an explicit governed union/view.
- Walk orchestration needs guarded transitions and durable state/trace/reference checkpoints.
- Native collection evolution requires a new versioned collection plus reconciled alias cutover;
  it cannot rely on Agno's generic knowledge-management endpoints.

### Risks and mitigations

- **Clock regression:** reject first-party rows whose availability differs from occurrence and
  third-party rows whose availability differs from acquisition; plant both canaries in tests.
- **False owner participation:** validate sender/recipient membership and fail closed if the owner
  appears in an acquired-third-party participant set.
- **Realization collapse:** store realization links as plural append-only records and test several
  dates/statuses against one message.
- **Contaminated resume:** require exact checkpoint/projection reconciliation; otherwise seal and
  create a linked rewalk.
- **Vector cutover drift:** freeze a PostgreSQL watermark, reconcile exact membership/count/hash
  and first-party/acquired/future/cross-case canaries, then move the alias only by explicit operator
  action. Preserve the old Agno collection for rollback. See the held native-Weaviate runbook.
