# ADR-0057 — Claim-centered evidence assembly and established facts

> _Byline: Codex · GPT-5 · 2026-08-15 · owner-ruling amendment 2026-08-16_

- **Status:** Accepted (owner approval 2026-08-15)
- **Decision:** D-062, refined by D-064
- **Relates:** ADR-0043, ADR-0045, ADR-0047, ADR-0052, ADR-0053, ADR-0055, ADR-0056

## Context

Retrieval chunks are useful search units but are too broad to represent an atomic
fact. An extracted sentence is also not truth. The owner requires a candidate
claim to generate a cross-system investigation that locates all supporting,
contradicting, and qualifying material across documents, conversations, messages,
geo observations, structured records, and graph relationships. The governed
result—not the initial extraction—creates the curated SurrealDB subgraph.

## Decision

1. Semantica and other extractors create append-only `claim_candidate` records,
   never established facts.
2. A candidate claim may start a versioned `claim_investigation` with an auditable,
   bounded query plan derived from its proposition, entities, aliases, times,
   locations, predicates, source requirements, and authority floor.
3. Discovery searches every authorized operational surface through platform-owned
   ports. Each result is classified as supporting, contradicting, qualifying,
   contextual, duplicate/derived, unresolved, or missing-expected evidence.
4. Human/governed review may create an immutable established fact. Corrections
   create a new assertion connected by `supersedes`, `contradicts`, or `qualifies`;
   claims and facts are never silently rewritten.
5. Every fact resolves through exact source spans and chunk generations to a
   normalized representation and custody-backed original. A chunk ID alone is
   insufficient provenance.
6. SurrealDB materializes the approved fact and its selected evidence subgraph.
   Source-centered promotion and claim-centered assembly are complementary flows.
7. Graphiti beliefs may generate investigative leads but cannot serve as canonical
   support without independent source resolution and promotion.
8. Corroboration is counted by independent source family, not raw artifact count.
   Derivative exports, screenshots, forwards, quotes, and backups sharing custody or
   content lineage count as one family unless provenance review establishes independent
   observation or creation. Dossiers display raw-hit and independent-source counts.

## Alternatives considered

### Treat proposition chunks as facts

- **Pros:** simple and inexpensive.
- **Cons:** launders extractor output into truth and weakens provenance.
- **Why rejected:** extraction is candidate generation, not adjudication.

### Store one source reference directly on each fact

- **Pros:** smaller schema.
- **Cons:** cannot represent corroboration, contradiction, derivative copies, or
  multi-modal support.
- **Why rejected:** evidence relationships are first-class and many-to-many.

### Rewrite facts when corrected

- **Pros:** easy current-state reads.
- **Cons:** destroys the realization and contradiction history central to the product.
- **Why rejected:** retain immutable assertions plus current pointers/views.

## Consequences

### Positive

- Atomic reasoning remains anchored to exact evidence.
- One claim can assemble messaging, documents, graph paths, and geo observations.
- Contradictions become visible deliverables instead of overwrite operations.
- The curated Surreal graph explains why each fact exists.

### Negative

- Cross-system discovery needs bounded orchestration, identity resolution, dedupe,
  and source-independence analysis.
- Human review remains necessary before establishment.

### Risks and mitigations

- **Confirmation bias:** every investigation searches for disconfirming evidence and
  alternative explanations.
- **Runaway retrieval:** cap hops, results, time, model cost, and context; persist the
  full query trace.
- **Duplicate corroboration:** group derivative copies by custody/content lineage
  before counting independent support.
- **Temporal laundering:** store valid, known/realized, recorded, established, and
  walk-observed clocks separately.
