# UNIFIED-PHYSICAL-MODEL — PARTIAL RECOVERY

> _Recovery note: this file's creation (`Add File`) was never captured by any `apply_patch` call across every rollout in `C:\Users\matts\.codex\sessions\2026\08\{25,26,27,28}\` — the file already existed live by the time the earliest `Update File` hunk below was issued, so it was created through some other mechanism (a full-file write, or a session/date genuinely outside this recovery task's scope). **This is therefore a PARTIAL recovery: the document's base structure, headings, and any untouched passages could not be reconstructed.** What follows is every located, accepted `apply_patch` hunk that touched this file, in chronological order, shown as unified-diff-style fragments (`-` = text the fragment replaced, `+` = text it introduced, ` ` = unchanged context) — all verbatim from the session transcripts. Reconstructed 2026-09-02 by Claude Code · Sonnet (recovery lane C)._

The document reconciles `PROPOSAL-FINAL` (owner's draft) against Codex's schema-audit docset into one unified physical model, and was itself later corrected/superseded in the direction later formalized by `PROVISIONAL-PHYSICAL-MODEL.md`, ADR-0060, and D-082–D-085. Every fragment below is real content this document contained; the missing piece is only the surrounding unmodified document (its section 1-8 skeleton, tables, and any passage no hunk ever touched).

**6 accepted hunk(s) recovered, none of which is a file-creation event.**

---

### Fragment 1 — 2026-08-26T13:05:44.826Z (`Update File`, call `call_WUkWLkj7EH6MT9S2QgDK6TO1`, session `rollout-2026-08-26T08-31-45-01a03e0e-13ba-7430-86b6-3e53ec175d38.jsonl`)

```diff
@@
 # UNIFIED-PHYSICAL-MODEL — reconciling PROPOSAL-FINAL (mine) + Codex's schema-audit docset
+
+> **Status correction, 2026-08-26:** provisional and blocked as an implementation source until its
+> R09–R14 PostgreSQL control/ledger families are reconciled with D-078/D-080 and the corrected lane
+> guides. Surreal is the final derived walk/analysis engine, but PostgreSQL must retain canonical
+> manifests, commands, checkpoints, beliefs, paired-delta records, receipts, and migration/cutover
+> attestations. The older “out of PG entirely” rows below were contradictory and are superseded by
+> the corrected workstream mapping in §5.
@@
-| R9 Cross-store reconciliation | reads `ops.projection_receipt` across all stores; writes the reconciled manifest as a view over `governed.*`+`context.*` joined to receipts — no new table |
-| R10 Surreal aggregation | reads the R9 manifest only; no PG table of its own beyond the receipts above |
-| R11 Walks/beliefs/delta | **out of PG entirely** — SurrealDB query per 09:19; nothing here |
+| R9 Cross-store reconciliation | reads `ops.projection_receipt` across all stores; writes immutable/versioned PG aggregation-manifest, membership, reconciliation-run, quarantine, activation-attestation, cursor and receipt records. A mutable view is not an admission authority. |
+| R10 Surreal aggregation | consumes only an authorized R9 manifest; returns append-only PG projection checkpoints, object/member receipts, observed hashes, revocation/supersession results and aggregate-manifest attestations. Surreal remains rebuildable. |
+| R11 Walks/beliefs/delta | Surreal executes governed temporal traversal/analysis, while PG retains append-only walk command/run/lifecycle, retrieval receipt, checkpoint, belief/support/transition, seal/rewalk, pair/delta and court-eligibility ledgers. No canonical walk or delta exists only in Surreal. |
@@
-| R14 Migration/cutover | executes §4's drop list into `_stale`; nothing new |
+| R14 Migration/cutover | writes PG migration/backfill manifests and step receipts, cutover/rollback events, integration acceptance runs/assertion results, and a legacy-asset registry. Retirement is forward, owner-approved, and never deletion. |
@@
-**Final table count per schema**: `context` = 33 · `evidence` = 6 · `candidate` = 3 · `governed` = 5 ·
-`ops`/`public` = 4 · **total = 51**.
+**Pre-R09 minimum table count only**: `context` = 33 · `evidence` = 6 · `candidate` = 3 ·
+`governed` = 5 · `ops`/`public` = 4 · **minimum = 51**. This is not a final physical count: the
+required R09–R14 manifest, walk/belief/delta, migration, cutover, rollback, and acceptance ledger
+families above must be designed and reviewed before implementation.
```

### Fragment 2 — 2026-08-26T13:08:18.495Z (`Update File`, call `call_za6BK9Ptw7af7qdrbwRd0VTM`, session `rollout-2026-08-26T08-31-45-01a03e0e-13ba-7430-86b6-3e53ec175d38.jsonl`)

```diff
@@
-**`context.hash_manifest`** — NEW: `id`·derived · `subject_table text`·derived (which context/evidence
-table the hash is about) · `subject_id uuid` nullable·derived (null for a generation-level H3 row) ·
-`level text CHECK(H1|H2|H3)`·derived · `canon_tag text NOT NULL`·derived (e.g.
-`h3-chain-h1genesis-hexconcat-v1`) · `algo text`·derived · `hash_hex text`·derived · `run_id uuid`·
-Temporal workflow/activity run ref (external, unenforced FK) · `member_manifest jsonb` nullable·
-derived (H3 only — ordered H2 id/hash membership) · `member_count int` nullable·derived ·
-`computed_at timestamptz`·derived · `status text CHECK(provisional|superseded) default 'provisional'`·
-derived · `created_at`·derived.
+**`context.hash_manifest`** — NEW: `id` · typed `source_generation_id` FK · `level
+CHECK(H1|H2|H3)` · `canon_tag NOT NULL` · algorithm/version · hash · normalized-generation count ·
+ordered-membership hash · workflow/activity receipt FK · computed timestamp · append-only status.
+The subject is a typed generation/record FK, never an unvalidated table-name/UUID pair. H3 membership
+is normalized into **`context.hash_manifest_member`** with manifest FK, ordinal, normalized record
+version FK, H2-manifest FK, H2 hash and canonicalization version. Unique generation+level+tag+version
+and manifest+ordinal constraints make count/order/tag reconciliation enforceable; JSON may cache the
+serialized manifest but is not the authority.
@@
-**`context.embedding`** — NEW: `id`·derived · `chunk_id uuid FK context.chunk` nullable (null =
-whole-row embedding) · `source_table text`·derived · `source_id uuid`·derived · `embedder_id text`·
-derived (e.g. `nvidia/nv-embed-v1`) · `embedder_version text`·derived · `dims int`·derived ·
-`vector vector(4096)`·derived (pgvector-native; a different-dimension embedder gets its own
-generation/table, never a mixed-dim column) · `content_hash bytea`·derived · `weaviate_object_id text`
-nullable·derived · `reconciliation_status text CHECK(pending|ok|drift) default 'pending'`·derived ·
-`created_at`·derived. `context.message.body_embedding_ref` now denormalizes this row's `id`.
+**`context.embedding`** — NEW: `id` · typed `chunk_id`/record-version FK · embedder/model/version ·
+dims · pgvector value · content/vector hashes · immutable `source_available_from` · promotion and
+custody revision IDs · projection generation/policy IDs · activation receipt ID · reconciliation
+state · created timestamp. Whole-record embeddings use a typed record-version relation rather than
+dynamic `source_table`/`source_id`. A different-dimension embedder gets its own generation/table;
+dimensions are never mixed. Weaviate object IDs are receipt-backed projection identities, not PG
+authority. `context.message.body_embedding_ref` may cache this row's ID only.
@@
-**`evidence.custody_event`** — PF's shape **plus**: `canon_tag text NOT NULL`·derived (the exact
-construction name — never a bare `h3-chain-v1`) · `hash_manifest_id uuid FK context.hash_manifest`
-nullable·derived (which provisional receipt this accepted/verified hash traces back to).
+**`evidence.custody_event`** — PF's shape **plus**: `canon_tag text NOT NULL` for hash-bearing events
+(never a bare `h3-chain-v1`) and `hash_manifest_id` FK. A constraint makes the manifest reference
+mandatory for accepted H1/H2/H3 promotion or reverification events and verifies compatible level,
+generation, tag and algorithm; non-hash custody events do not misuse this field.
@@
-**`governed.realization_target`** — NEW, polymorphic (consistent with `evidence.promotion.
-context_table` pattern already in PF): `id`·derived · `realization_event_id FK`·derived ·
-`target_table text CHECK(context.message|context.third_party_message|candidate.fact|governed.fact)`·
-derived · `target_id uuid`·derived · `created_at`·derived. A deferred CHECK requires ≥1 target row
-per realization event.
+**Typed realization targets** — NEW: separate target relations for normalized record version,
+source span, claim candidate and established fact, each with a real FK plus
+`realization_event_id`. A deferred constraint trigger requires at least one target across the typed
+relations at commit. An unchecked polymorphic `target_table`/`target_id` pair is prohibited because
+it cannot enforce provenance or referential integrity.
@@
-**`ops.outbox`** — PF's shape **plus**: `idempotency_key text UNIQUE` nullable·derived
-(`workflow_id+source_version_id+operation+canon/generation/version`, per D-077's Activity
-idempotency contract) — lets duplicate-delivery retries collapse at the event layer, not just inside
-each Activity.
+**`ops.outbox`** — PF's shape **plus**: structured, `NOT NULL` identity columns for workflow/command,
+source version, operation, canon/generation and schema/policy version, plus a canonical
+`idempotency_key NOT NULL UNIQUE` derived from their versioned serialization. This lets duplicate
+delivery collapse at the event layer; nullable uniqueness is prohibited because PostgreSQL permits
+multiple `NULL` values.
```

### Fragment 3 — 2026-08-26T13:08:29.065Z (`Update File`, call `call_aiT4CvXTozgATooKYjwUk9Ah`, session `rollout-2026-08-26T08-31-45-01a03e0e-13ba-7430-86b6-3e53ec175d38.jsonl`)

```diff
@@
-Unchanged from PF §D **except**: `working.realization_event`/`realization_event_record` **move OFF
-the drop list** — restored as `governed.realization_event`/`realization_target` (§1 row 14, above).
-Added: `evidence_scope_binding` (Codex-proposed, never built) — do not build; superseded by ONE CASE
-(D-072). Everything else in PF §D stands as written (`working.normalized_record`, `evidence.raw_phone`,
-`message_projection_route`, `walk_*` views, `analysis.court_case`/`matter`/`matter_knowledge_partition`,
-23× `case_id`/`matter_id` columns, hint-column clusters, `prev/next_message_id`, `graphiti_synced_at`,
-me/you inference code paths, etc.).
+There is no blanket drop list. Every legacy relation, view, column and caller is an R14 retirement
+candidate only after a complete reader/writer census, compatibility contract, forward backfill,
+count/hash reconciliation, rollback/restore proof and owner gate. Existing `walk_*` ledgers are
+explicitly preserved and evolved because PG remains canonical for walk/checkpoint/belief/delta
+state. `working.normalized_record`, route relations, Matter/CourtCase compatibility structures,
+legacy raw families, hint columns, Graphiti markers and inference paths each require separate
+disposition. Files approved for retirement move to `to_be_deleted`; no agent deletes them.
@@
-| R12 Legal/workbench | `governed.export_package` |
+| R12 Legal/workbench | PG legal work item/product/version, assertion, typed citation, review/release/supersession, export package and consumption-acknowledgement ledgers; every legal output resolves to governed fact/delta/evidence anchors. |
```

### Fragment 4 — 2026-08-26T13:09:53.605Z (`Update File`, call `call_3fE5DhrrXGHC7pndvC9KFmZ8`, session `rollout-2026-08-26T08-31-45-01a03e0e-13ba-7430-86b6-3e53ec175d38.jsonl`)

```diff
@@
-> (16 AI-chat raw tables → ONE `context.raw_ai_chat` + `format` column). ONE model. Layers 1–4 only
-> (layer 5 = SurrealDB query, out of PG per 09:19). Tie-break rule applied throughout: where no
-> ruling decides it, fewer tables wins and the more concrete (column-level) doc wins — that is
-> PROPOSAL-FINAL in most disagreements, because Codex's docs are still at the relation-family level.
+> (16 AI-chat raw tables → ONE `context.raw_ai_chat` + `format` column). ONE model. PostgreSQL owns
+> authority/control ledgers for every layer; Surreal executes the final derived temporal traversal
+> and analysis. Where no ruling decides a shape, enforceable authority, provenance, clocks and
+> lifecycle invariants outrank table-count minimization or earlier column-level concreteness.
@@
-| 11 | Per-store receipt idempotency | `ops.projection_receipt` exists; `ops.outbox` has no idempotency key | R1 exit gate requires "duplicate delivery collapses" via a key derived from `workflow_id+source_version_id+operation+canon/generation/version` | **ADD `idempotency_key text UNIQUE`** to `ops.outbox`; `projection_receipt` unchanged | D-078, R1 (RECONCILIATION doc) |
+| 11 | Per-store receipt idempotency | `ops.projection_receipt` exists; `ops.outbox` has no idempotency key | R1 exit gate requires "duplicate delivery collapses" via a key derived from `workflow_id+source_version_id+operation+canon/generation/version` | **ADD structured identity columns plus `idempotency_key text NOT NULL UNIQUE`** to `ops.outbox`; nullable uniqueness is insufficient. `projection_receipt` remains append-only. | D-078, R01 |
@@
-| 13 | Candidate table granularity | 3 tables (`entity`/`event`/`fact`, discriminator columns absorb pattern/contradiction/time-adjacent candidates) | 6 tables (`entity_candidate`/`time_candidate`/`event_candidate`/`pattern_candidate`/`contradiction_candidate`/`claim_candidate`) | **PF wins** — fewer-tables tie-break; date-hint columns already give every row bounds/precision/anchor, covering Codex's `time_candidate` need without a separate table | tie-break |
-| 14 | **Realization events** | Folded into `candidate.event`(draft) + `governed.fact`(fact_type='realization') — no dedicated table | Dedicated `realization_event` + 4 typed target tables (`realization_record_target`/`claim_target`/`fact_target`/`source_span`) | **Codex's concept wins**, PF's fold is wrong. OWNER-BACKBONE + AGENTS.md repeat verbatim: "plural realization events remain **separate**" from facts, not a fact subtype. **ADD `governed.realization_event` + ONE polymorphic `governed.realization_target`** (collapsing Codex's 4 typed tables — fewer-tables tie-break, no ruling demands typed FKs specifically). `candidate.event` gets `promoted_realization_id` alongside `promoted_fact_id` | OWNER-BACKBONE governing rules; AGENTS.md "WHY THIS EXISTS" |
+| 13 | Candidate identity, relations and anchors | PF has only entity/event/fact rows with JSON source refs | D-074 requires entity, relation, event, temporal, claim and conflict candidates; D-078 requires every projected Neo4j edge to resolve to exact PG provenance | **Use a common candidate assertion identity with typed entity/event/fact/relation subtypes and typed source-anchor rows.** Temporal/pattern/conflict semantics may be typed discriminators only where their required fields and provenance remain enforceable. | D-074/D-078 |
+| 14 | **Realization events** | Folded into `candidate.event`(draft) + `governed.fact`(fact_type='realization') — no dedicated table | Dedicated `realization_event` + typed target tables | **Keep realizations separate and use typed record/span/claim/fact target relations with real FKs plus a deferred at-least-one-target constraint trigger.** A polymorphic UUID pair is not sufficient. | OWNER-BACKBONE; AGENTS.md knowledge-horizon mechanism |
@@
-| 16 | **ONE CASE scaffolding** | DROP→`_stale`: `analysis.court_case`/`matter`/`matter_knowledge_partition` + all `case_id`/`matter_id` columns | WHOLE-SYSTEM (pre-D-072 language) still models Matter/CourtCase in depth (§1/§13); PROVISIONAL-PHYSICAL-MODEL's opening correction caveats but doesn't remove it; explicitly rejects a *new* `evidence_scope_binding` table ("rejected by D-072") | **PF's DROP→`_stale` wins outright** — D-072 is binding and same-morning; Codex's own later physical-model doc already agrees in its opening correction. WHOLE-SYSTEM §1/§13 is stale within Codex's own docset | D-072 |
+| 16 | **ONE CASE scaffolding** | PF proposed bulk retirement of Matter/CourtCase structures and IDs | D-072 fixes one owner/one personal case and forbids further hierarchy | **Freeze new creation and treat every legacy object as a separate R14 retirement candidate.** No blanket drop/move occurs without reader/writer census, compatibility/backfill/reconciliation, rollback proof and owner gate. | D-072/R14 |
@@
-| `hash_manifest` | 1 | provisional H1/H2/H3 receipts, pre-custody | **NEW (D-077)** |
+| `hash_manifest` / `hash_manifest_member` | 1 | typed provisional H1/H2/H3 receipts plus ordered generation membership, pre-custody | **NEW (D-077)** |
@@
-### `candidate` — 3
+### `candidate` — required minimum families
@@
-| `entity` | 3 | proposed entity | unchanged |
-| `event` | 3 | proposed event, incl. draft realization | **CHANGED — +promoted_realization_id** |
-| `fact` | 3 | proposed claim/contradiction/signal | unchanged |
+| `assertion` | 3 | common candidate identity, lifecycle and version | **NEW authority supertype** |
+| `entity` / `event` / `fact` / `relation` | 3 | typed candidate payloads; relation has typed endpoints | **CHANGED — D-074 complete family** |
+| `source_anchor` | 3 | exact record-version/span/provenance anchors for every candidate | **NEW typed provenance** |
@@
-### `governed` — 5
+### `governed` — required minimum families
@@
 | `fact` | 4 | owner-approved conclusion, source-pinned | unchanged |
+| `fact_relation` | 4 | typed governed edge with independent source anchors | **NEW (D-074/D-078)** |
 | `contradiction` | 4 | one contradiction, flat, dated | unchanged |
 | `export_package` | 4 | filed-bundle manifest | unchanged |
 | `realization_event` | 4 | when/how the owner realized something, plural | **NEW (backbone ruling)** |
-| `realization_target` | 4 | polymorphic link: realization → record/claim/fact | **NEW (backbone ruling)** |
+| typed realization target relations (4) | 4 | realization → record version/source span/claim/fact with real FKs | **NEW (backbone ruling)** |
@@
-**Total = 51** (33+6+3+5+4), down from PF's original 59 because the 10:07 collapse removes 15
-tables (28→13 raw) while this reconciliation adds 7 (`hash_manifest`, `chunk`, `embedding`,
-`geo_feature`, `realization_event`, `realization_target`, `canon_registry`) net of PF's original 59
-− 15 + 7 = 51.
+**Exact table count withdrawn.** The earlier total of 51 omitted ordered hash membership, relation
+candidates, typed source anchors, typed realization targets, governed relations, and the R09–R14
+control/ledger families. Physical counting resumes only after these enforceable contracts are frozen.
@@
-| R6 Semantica/candidates/Neo4j | `candidate.entity`/`event`/`fact`, `ops.projection_receipt(store=neo4j)` |
-| R7 Governed facts/realizations | `governed.fact`, `governed.contradiction`, `governed.realization_event`, `governed.realization_target` |
+| R6 Semantica/candidates/Neo4j | common candidate identity plus typed entity/event/fact/relation and source-anchor families; `ops.projection_receipt(store=neo4j)` with node/edge membership and independent anchor hashes |
+| R7 Governed facts/realizations | `governed.fact`, typed fact relations/source support, contradiction, realization event and typed target families |
@@
-| R13 Temporal/n8n execution | drives workflow starts off `ops.outbox`; owns no domain table |
+| R13 Temporal/n8n execution | drives workflow starts off `ops.outbox`; writes PG workflow/activity/command receipts and lifecycle events but owns no evidence/fact truth |
@@
-**Pre-R09 minimum table count only**: `context` = 33 · `evidence` = 6 · `candidate` = 3 ·
-`governed` = 5 · `ops`/`public` = 4 · **minimum = 51**. This is not a final physical count: the
-required R09–R14 manifest, walk/belief/delta, migration, cutover, rollback, and acceptance ledger
-families above must be designed and reviewed before implementation.
+**No final physical count is certified.** The required candidate/provenance, typed-target,
+R09–R14 manifest, walk/belief/delta, migration, cutover, rollback, and acceptance ledger families
+must be designed and reviewed before implementation.
```

### Fragment 5 — 2026-08-26T13:10:28.880Z (`Update File`, call `call_2DpGE0v9DluCSrQ6ZpFU1myc`, session `rollout-2026-08-26T08-31-45-01a03e0e-13ba-7430-86b6-3e53ec175d38.jsonl`)

```diff
@@
-| 5 | Promotion granularity | One `evidence.promotion` row per promoted context row | 4-table pipeline: `evidence_promotion_request`→`item`→`fingerprint_verification_attestation`→`evidence_source` | **PF wins** — no ruling mandates the split; PF's `h1_reverify_sha256`/`h1_match` already satisfy D-069/D-075's re-verify-before-accept requirement | tie-break (fewer tables) |
+| 5 | Promotion granularity | One `evidence.promotion` row per promoted context row | 4-table pipeline: `evidence_promotion_request`→`item`→`fingerprint_verification_attestation`→`evidence_source` | A compact promotion row is acceptable only when it has mandatory typed links to separately computed H1, normalized H2 and complete ordered-generation H3 verification manifests, and an atomic finalizer enforces their exact revisions/tags/count/order. H1 reverify fields alone do not satisfy D-075/D-076. | D-069/D-075/D-076 |
```

### Fragment 6 — 2026-08-26T13:41:18.623Z (`Update File`, call `call_46Y6bNvia5i5ZbqFeKmnJxWS`, session `rollout-2026-08-26T08-31-45-01a03e0e-13ba-7430-86b6-3e53ec175d38.jsonl`)

```diff
@@
 > attestations. The older “out of PG entirely” rows below were contradictory and are superseded by
 > the corrected workstream mapping in §5.
+>
+> **D-082–D-085 amendment, 2026-08-26:** this blocked model also predates the permanent AI-chat
+> no-evidence rule, typed extraction/created-work fan-out, maintained Timesketch fork, immutable PG
+> timeline generations, and governed bulk context-curation/amendment-candidate ledgers. Use
+> `PROVISIONAL-PHYSICAL-MODEL.md`, ADR-0060, and the semantic work-package/handoff documents for those
+> contracts. Do not infer a chat promotion bridge or direct Timesketch/OpenSearch authority from any
+> older row below.
@@
-> `docs/DECISION_LOG.md` D-069–D-081, and `LENS-BRIEF.md` through its 10:07 amendment
+> `docs/DECISION_LOG.md` D-069–D-085, and `LENS-BRIEF.md` through its 10:07 amendment
```
