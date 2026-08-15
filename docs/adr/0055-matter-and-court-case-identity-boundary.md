# ADR-0055 — Matter and CourtCase identity boundary

> _Byline: Codex · GPT-5 · 2026-08-15_

- **Status:** Accepted (owner approval 2026-08-15)
- **Decision:** D-060
- **Relates:** D-041, ADR-0044, ADR-0045, ADR-0053, ADR-0054

## Context

Canonical Knowledge partitions use a textual key such as `primary`, while
case-work tables including `analysis.evidence_item` use UUID `case_id` values
without an authoritative case table. A docket or proceeding is not the same
thing as the enduring personal/legal matter, and using either identifier for
both roles prevents provenance-safe Knowledge-to-Evidence promotion.

D-041 correctly fixed the product as single-owner and rejected speculative
multi-user/multi-client architecture. Its additional conclusion that one text
`case_id='primary'` should permanently represent every identity role no longer
fits the approved case-management workflow.

## Decision

1. The platform models an enduring `Matter` separately from each `CourtCase`
   proceeding. One Matter may contain multiple CourtCases.
2. The current product remains single-owner and initially seeds one Matter;
   this decision does not introduce multi-user or multi-client tenancy.
3. Legacy textual Knowledge partitions map explicitly to a Matter through a
   `analysis.matter_knowledge_partition` bridge. `primary` is preserved as the initial partition
   key and is never reinterpreted as a UUID.
4. New case-work writes carry both `matter_id` and `court_case_id`. Existing
   UUID `case_id` columns remain compatibility fields until their provenance is
   reconciled; they are not destructively converted.
5. Knowledge-to-Evidence promotion is transactional and idempotent. It creates
   an unreviewed, HITL-required, legally unsafe draft with an immutable source
   pointer and stable promotion key. It never mutates the Knowledge hit,
   normalized record, original evidence, or approved evidence item.
6. `analysis.timeline_event` remains the single authored factual timeline;
   court-specific timelines are projections, not a second writable truth.

This narrowly supersedes D-041's identity-model consequence while preserving
its single-owner and single-client/matter scope.

## Alternatives considered

### Keep only textual `primary`

- **Pros:** no schema change.
- **Cons:** cannot represent proceedings, enforce relational integrity, or
  connect existing UUID case-work safely.
- **Why rejected:** preserves the current identity collision and blocks the
  requested case-management MVP.

### Use one combined Case table

- **Pros:** fewer initial tables and simpler selectors.
- **Cons:** conflates enduring matter identity with court/docket identity and
  forces a later breaking split when another proceeding appears.
- **Why rejected:** the owner approved Matter and CourtCase as separate
  entities.

### Convert every legacy `case_id` to UUID immediately

- **Pros:** one apparent identifier type.
- **Cons:** destructive, cannot honestly infer mappings for historical UUIDs,
  and would rewrite Knowledge partitions whose text key has valid meaning.
- **Why rejected:** provenance may not be invented; compatibility must be
  additive and explicit.

## Consequences

### Positive

- Knowledge, evidence, people, tasks, timelines, work products, and exports gain
  one stable Matter scope.
- Court-specific metadata no longer becomes the universal Knowledge partition.
- Cross-matter reads/writes and duplicate promotions can fail closed.

### Negative

- A bridge and dual-write compatibility period are required.
- Existing UUID `case_id` rows need later reconciliation before stronger legacy
  foreign keys can be validated.

### Risks and mitigations

- **Wrong legacy mapping:** seed only the explicit `primary` bridge; never
  infer historical UUID relationships.
- **Duplicate evidence:** enforce stable request and canonical source-pointer
  uniqueness in `analysis.knowledge_evidence_promotion`, then return the
  existing draft on retry.
- **Unsafe promotion:** database defaults and service invariants force
  `unreviewed`, `hitl_required=true`, and `safe_for_legal_use=false`.
- **Framework coupling:** public contracts use platform vocabulary; Agno,
  Workbench, and future orchestration runtimes are adapters.
