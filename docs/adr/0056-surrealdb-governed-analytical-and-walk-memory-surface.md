# ADR-0056 — SurrealDB governed analytical and walk-memory surface

> _Byline: Codex · GPT-5 · 2026-08-15 · owner-ruling amendment 2026-08-16_

> **Narrow supersession notice (2026-08-18, ADR-0059; Codex · GPT-5):** Decision 10 is
> superseded only where it collapses every pause into a terminal seal/new identity. A healthy,
> reconciled checkpoint resumes the same walk identity. Projection revocation, drift, mismatch,
> or another terminal integrity failure still seals an immutable non-resumable snapshot and
> requires an explicitly linked rewalk. All other ADR-0056 decisions remain in force.

- **Status:** Accepted; Decision 10 superseded in part by ADR-0059 (owner approval 2026-08-15)
- **Decision:** D-061, refined by D-064
- **Relates:** ADR-0014, ADR-0024, ADR-0032, ADR-0040, ADR-0043, ADR-0045, ADR-0052

## Context

ADR-0043 correctly removed SurrealDB from the operational critical path because
Agno's adapter silently failed required learning operations and armed an unsafe
multi-database route. The platform is now framework-neutral and needs a curated
multi-model analytical surface, a tri-temporal as-lived walk memory, and a future
TraceIQ temporal-geospatial projection. Spectron documents a useful target shape,
but its self-hosted binary is prerelease/private and cannot be a hard dependency.

## Decision

1. PostgreSQL remains the canonical authority for evidence, custody, claims,
   approvals, promotion decisions, and audit records.
2. SurrealDB returns as a **governed, rebuildable analytical projection** and an
   experimental tri-temporal memory/runtime for one as-lived walk agent. It is
   not the Agno operational database and does not replace PostgreSQL.
3. The platform owns a Spectron-compatible memory API and implementation. An
   official Spectron binary may be used when available and acceptable, but the
   platform must remain independently operable.
4. SurrealDB receives promoted manifests, normalized content, exact locators,
   chunks, embedding instances, graph relationships, temporal state, traces,
   and future TraceIQ projections. Original binaries remain in custody-controlled
   object storage and are referenced by immutable hashes. Verified binary
   replication is optional and never changes authority.
5. Promotion is fail-closed. A partially approved source contributes its manifest
   and approved spans only. Full normalized text becomes agent-searchable only
   after source-level approval.
6. Graphiti remains the current belief-memory baseline until a measured bake-off
   proves parity or superiority. Neo4j and Weaviate remain operational projections.
7. The parked legacy Surreal deployment stays read-only. This ADR authorizes a
   design and later isolated spike, not an in-place activation, migration, or
   production cutover.
8. The disposable slice uses one shared Surreal Context for its product/environment
   world. Matter scopes partition promoted material inside that Context; first-class
   walk records, steps, horizons, and walk-bound belief records separate executions.
   Ignorant and hindsight walks do not receive separate Contexts or duplicated corpora.
9. After parity is proven, an as-lived walk retrieves evidence and memory only through
   its reconciled Surreal projection. PostgreSQL may supply canonical control and
   approval metadata, but no broad-store retrieval fallback is permitted.
10. Revocation, drift, mismatch, or outage pauses the affected walk and fails closed.
    The system seals an immutable, read-only historical walk snapshot, reconciles or
    rebuilds the projection, then starts a new linked rewalk. Historical snapshots are
    replayable and comparable but are never active retrieval fallback state.
    **Superseded in part by ADR-0059:** a healthy operational pause with an exactly reconciled
    projection/checkpoint resumes the same walk; terminal integrity failures follow the sealed
    snapshot plus linked-rewalk path above.
11. A walk may form explicitly uncertain candidate beliefs only from horizon-eligible
    inputs. It cannot import corpus-wide candidates or extraction findings produced
    under a broader horizon.
12. Uncertain realization time retains its full interval. A computed midpoint is only
    a proposal: mandatory human review must approve it, select another supported point,
    narrow the interval, or leave it unresolved. No unapproved estimate is walk-visible.

This supersedes ADR-0043 only where that ADR says SurrealDB has no future
analytical/memory role. ADR-0043's PostgreSQL authority, Semantica candidate
boundary, and removal of SurrealDB from Agno's operational critical path remain
in force. ADR-0024 remains superseded; its consolidated Agno-store design is not
revived.

## Alternatives considered

### Reactivate SurrealDB as the universal operational database

- **Pros:** apparent consolidation.
- **Cons:** repeats the adapter failure, multi-db routing, and authority problems.
- **Why rejected:** the analytical projection must not own canonical operations.

### Wait for official Spectron

- **Pros:** less implementation ownership if it becomes available.
- **Cons:** private availability, unknown licensing, and an uncontrolled schedule.
- **Why rejected:** compatibility is useful; dependency is unacceptable.

### Replace Graphiti immediately

- **Pros:** fewer memory systems.
- **Cons:** destroys the working baseline before temporal, reconciliation, and
  retrieval parity are proven.
- **Why rejected:** replacement follows a bake-off, not architectural optimism.

## Consequences

### Positive

- The curated walk can combine graph, document, vector, temporal, and geo state.
- PostgreSQL custody and governance remain unambiguous.
- Official Spectron can become an adapter instead of a platform dependency.
- Partial-source promotion prevents unreviewed or future content leakage.

### Negative

- Projection, reconciliation, and versioned embedding contracts are required.
- Graphiti and SurrealDB coexist during evaluation.
- Full source availability may lag ingestion until governance completes.

### Risks and mitigations

- **Horizon contamination:** bind every promoted node/edge/chunk to temporal and
  disclosure predicates and prove pre-ranking filters with planted future facts.
- **Projection drift:** carry PostgreSQL IDs, custody hashes, projection revisions,
  and rebuild checkpoints; mismatches fail closed.
- **Shared-Context bleed:** bind reads, writes, caches, profiles, consolidation, and
  traces to Matter plus walk/horizon policy; disable any Context-wide facility that
  cannot prove those predicates for the as-lived path.
- **Historical-state contamination:** seal snapshots as immutable/non-resumable and
  require a new walk identity after reconciliation; compare snapshots through explicit
  input, policy, and reasoning deltas.
- **Blob duplication:** reference custody storage by default; replicate bytes only
  under an explicit availability/analysis policy.
- **Private-product assumptions:** label official Spectron behavior verified,
  supported, candidate, or unknown and require implementation spikes.
