---
scope: sql/0052_claim_and_assertion_candidates.sql
status: current
verified_at: 2026-08-29
superseded_by: null
authority:
  - docs/adr/0062-claim-candidates-temporal-edges-and-the-assertion-layer.md
  - docs/design/CLAIM-AND-ASSERTION-CANDIDATES-2026-08-29.md
  - docs/DECISION_LOG.md
watches:
  - sql/0052_claim_and_assertion_candidates.sql
  - docs/adr/0062-claim-candidates-temporal-edges-and-the-assertion-layer.md
contains_secrets: false
---

# Exact-file memory — `sql/0052_claim_and_assertion_candidates.sql`

> _Byline: Claude · Opus 5 · 2026-08-29._

Governed by ADR-0062. This file records only what causes wrong edits to this migration.

## Never add these columns

**`Owner directive` — no review gate on `claim_candidate` or `claim_temporal_edge.`**
An earlier draft carried `review_state DEFAULT 'pending'`. At corpus scale that queues tens
of thousands of approvals in front of the single owner, for rows that cannot be filed,
cited, or promoted — approving one changes nothing. Removed 2026-08-29 on owner correction.
Both tables carry `lifecycle` (`active`/`superseded`) instead; correction is supersession,
never rejection. ADR-0062 §2. **Do not reintroduce a per-row approval column here.**

**`Owner directive` — no `date_relative_to` free-text column.** Ordering lives in
`working.claim_temporal_edge`, which is computable. Two representations of one relationship,
only one computable, drift apart. ADR-0062 §6.

**`Owner directive` — no promotion columns anywhere in this migration.** AI chats are
permanently context-only (D-082); nothing extracted from them has a promotion target. The
phase boundary is structural. Unlike `working.candidate_fact` (0016), which does carry
`promoted_to_table`/`promoted_to_id`/`promoted_at` — do not copy that shape here.

**`Owner directive` — no `occurred_at` or `validity` on `claim_candidate`.** A claim *about*
a date is not an event. Resolved placement belongs in `context.relative_time_anchor`.

## Constraints that will reject real rows — this is intended

**`claim_candidate_assistant_is_proposal`** — biconditional:
`(speaker_role='assistant') = (claim_class='AI_PROPOSAL')`. An extractor that mislabels an
assistant framing as `SELF_ACCOUNT` fails at the row. That failure is the point: an AI
framing reaching a filing as the subject's own account is the worst outcome this schema can
produce. **`Inferred` limitation:** it also forces an assistant turn quoting a real document
into `AI_PROPOSAL` when it is properly a `DOCUMENT_QUOTE`. Proposed fix is an
`originates_with` split — ADR-0062 §5, not adopted, searched and not previously ruled.

**Content is append-only by trigger** on both `claim_candidate` and `claim_assertion`.
`UPDATE` of `title`/`body`/`verbatim`/`claim_class`/`speaker_role`/`hedged`/`date_raw`/
`content_sha256`/`chat_message_id` raises `23514`. Review/lifecycle columns stay mutable.
Enforces ADR-0052 Q6: claims accumulate and are never rewritten.

**`claim_candidate_run_span_key`** is unique on `(extraction_run_id, chat_message_id,
content_sha256)` — NOT on `fingerprint`. `fingerprint` is a blocking key for clustering and
identical values across mentions are expected and required. **Never make it unique.**

**Generation cap.** `claim_assertion_synthesis_member` FKs to
`claim_assertion(id, assertion_generation)` with `member_generation = 1`, so a synthesis
citing a synthesis is a referential impossibility, not a trigger check. Cardinality
(gen 1 ≥ 1 claim member; gen 2 ≥ 2 synthesis members) is a DEFERRABLE constraint trigger and
fires at COMMIT, not INSERT.

## Dependencies and ordering

`Verified 2026-08-29` — dependency pre-check against live PG returned PASS for
`working.extraction_run`, `working.chat_conversation`, `working.chat_message`,
`working.chat_chunk`, and schema `reference`; FAIL for `context.relative_time_anchor`, which
migration `0047` creates and which was not applied live. **0052 requires 0047 first.** In a
clean ordered rebuild this resolves; against a partially-migrated live DB it will not.

The FK on `relative_time_anchor_id` was briefly removed as a live workaround and then
restored once it was established that the read-only failure was a database rebuild, not a
schema defect. Do not remove it again.

`Historical` — migration number: `0049`–`0051` existed on disk uncommitted when 0052 was
authored, and D-098 records `0049` as scaffolding only. Confirm the number against a settled
tree before applying.

## Not yet implemented here

D-054 point 7 (dead-letter table + replay tool + alert on count>0) and D-085 (partial bulk
success explicit, conflicts fail closed) are **signed rulings that this migration does not
yet implement.** As written a constraint violation aborts the transaction, so one bad row
kills a whole run. Needed: per-row transactions, `working.claim_candidate_rejected`,
`claims_rejected` on `extraction_window`, and grounding as a `grounding_state` column gating
`owner_disposition='accepted'` rather than raising. ADR-0062 "Already ruled".
