# Schema reconciliation — reviewed plan (not yet owner-approved)

> _Byline: Claude Code · Fable 5 · 2026-08-25 03:10 · three independent Sonnet reviewers (Chesterton+Systems, Kepner-Tregoe+Archetypes, Graph blast-radius), all re-based on owner ruling D-069._

## Ruling this plan serves (D-069)

Ingest = context (mutable, re-derivable, fingerprinted). Owner promotes. Promotion verifies the
fingerprint against the original (H1), then custody and immutability begin in `evidence.*`.
Analysis and court read evidence only.

## What the reviewers rejected in the earlier "Shape C" proposal

| Proposal | Verdict | Why |
|---|---|---|
| Fold `chat_message` into `working.message` | **Rejected (3/3)** | ADR-0053/0044: AI chat is context, horizon-neutral by design; no FK to the spine on purpose. Folding it contaminates the spine. |
| One message table (merge `third_party_*`) | **REJECTED by owner 2026-08-25 03:07** ("a monstrosity, absolutely not") | Separate tables stay: first-party message, acquired-third-party message (ADR-0059, owner-exclusion trigger), AI-chat message (ADR-0053, context). Each keeps its own participant contract. |
| Remove `record_visible_from` | **Rejected as stated** | It is a base_version-pinned perf cache (0028), not the rejected COALESCE (already gone in 0026). Replace only with an indexed column that has equal staleness guarantees. |
| Add `source_available_from` as a column | **Name collision** | `working.source_available_from(uuid)` is a live function every horizon view calls. Column needs a different name or the function rewritten first. |
| Remove `realized_at` on `normalized_record` | **Approved** | Deprecated in 0026; but `normrec_clock_ordering` CHECK and `vw_record_disclosure` must be updated in the same migration. |
| Trim `normalized_record` (acquired_at, export_created_at, sender_entity_id, domain, …) | **Deferred** | Each breaks 3–4 views (`vw_derivation_lineage`, `current_provenance`, `vw_record_disclosure`, `vw_walk_base_version_input`, `vw_record_sender_resolution`). Highest-centrality node (16 FKs + 9 views). Do last. |
| D2 address book as FK target for every participant | **Approved as a new migration step**, not a rename | `message_participant` has no entity FK today; third-party path resolves entities via trigger. Design first-party resolution explicitly. |
| H2 pinned to `evidence.raw_*` | **Wrong under D-069** | Custody pins to promoted `evidence.*` rows. Ingest hashes are fingerprints. |

## The sequence the graph allows (reviewer 3), with D-069 applied

1. **Build the promotion → evidence writer** (`analysis.knowledge_evidence_promotion` → verify H1 → write `evidence.source` / `evidence_hash` / `custody_event`), live, unwired. Nothing else moves until this exists.
2. **Move the raw landing zone to the context layer.** `evidence.raw_*` currently lands pre-promotion inside the evidence schema — a D-069 violation. Repoint `vw_layer_map`, `vw_raw_all`, `vw_pipeline_funnel`, and the derivation engine reads.
3. **Backfill custody for already-ingested rows** through the promotion path. **This is the one irreversible step** — do it before retiring the ingest-time write, never after.
4. **Retire `custody.ingest_artifact()`'s evidence writes.** H1 stays as a fingerprint on the context row.
5. Then, and only then, the message-layer changes: port `validate_message_projection` onto the three separate tables (owner 03:07); add first-party entity resolution **alongside** the record's participant columns, never replacing them (D-071); rename-not-collide the availability clock; replace `record_visible_from` with an indexed equivalent; drop `realized_at` with its CHECK/view updates.
6. `normalized_record` trim last, one column family per migration, freshness test extended to columns.

## Canon debt this exposes (record, do not fix here)

- Two H2 canons (`h2-canonical-v2` in `public.canon_registry` vs `h2-rawelement-v1` in `custody.py`) — same collision pattern as the two H3 chains. Needs distinct tags + crosswalk.
- Python-parsed formats produce no H2/H3 today (`custody.py:188`); only SBV does. Under D-069 this moves to promotion, which fixes it structurally.
- No "sealed vs H1-only" state on `ingest_run`.
- ADR-0044 §evidence/context boundary and `sql/0009` header need a dated strike-through pointing at D-069.

## Owner decisions still needed

1. ~~Confirm D-069 wording as logged.~~ **CONFIRMED 2026-08-25 03:10.**
2. ~~Message shape after D-069: keep first-party / third-party as separate tables with the trigger (reviewers' recommendation), or one table with the trigger ported.~~ **RULED 2026-08-25 03:07: separate tables.** Open sub-question: the first-party table is `working.message` (June D2, 56 cols) — does it stay as designed, and gain `source_available_from` + an entity FK on `message_participant`? **PARTIAL RULING 03:25 (D-071): the record's own sender / recipients / participants columns STAY; `message_participant` → `entity` is additive resolution only. Still open: whether `source_available_from` lands on `working.message` as a column.**
3. ~~Whether `evidence.raw_*` is renamed into `working.raw_*` (landing zone becomes context) or stays in place with a promotion-only write gate.~~ **RULED 2026-08-25 03:10: context.** The raw landing tables leave the `evidence` schema. Sequencing step 2 above is therefore a schema move (`ALTER TABLE … SET SCHEMA`), with `vw_layer_map` / `vw_raw_all` / `vw_pipeline_funnel` / derivation reads repointed in the same migration.
