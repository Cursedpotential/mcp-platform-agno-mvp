# Lane 1d — Agno SQL layer audit (30 migrations)

> _Byline: Claude Code · Opus 5 · 2026-08-23_ · source: subagent a906a43da91d70573

Scope: `Agno-MCP-Platform/sql/` — 30 numbered migrations 0001–0030, 9 `.backup_*` siblings,
`README.md`, and `_manual/`, `bootstrap/`, `drafts/`, `validation/`. Paths relative to `sql/`.

## 0. README.md — load-bearing context

Unusually candid; changes how every other file must be read:

- **The numbered chain does not replay from an empty database, and has not since 0008**
  (README.md:32-52, 54-104). A verified scratch-container replay failed with a documented failure table
  (`:70-83`): 0008 fails at `ALTER TABLE evidence.source` (table doesn't exist — created out-of-band),
  and 0009/0010/0012/0013/0016/0017/0018 all cascade from that.
- **0014 does not fail on a fresh replay — it silently no-ops** (`:78,84-95`): its `DO $$` blocks guard
  every table move with `IF EXISTS (...WHERE table_schema='analysis'...)`, true only on the live DB.
- **`sql/bootstrap/schema_baseline.sql`** is a `pg_dump --schema-only` capture and the only reproducible
  bootstrap path. As of the README's last update (2026-08-16) the committed baseline **predates
  0026-0030's current form** and a direct replay hit an extension-ordering bug (`pg_duckdb` created
  before conventional extensions). README.md:132-140 explicitly says: "do not describe this file alone
  as a complete reproducible bootstrap."
- Per-schema counts from the 2026-08-10 regeneration: `ai 23 · analysis 31 · evidence 19 · ops 5 ·
  public 17 · reference 14 · working 47 = 156 tables` (`:124-127`). Most of the schema by table count is
  reachable only through the baseline dump or the live DB.

**Implication:** many objects referenced by later migrations (`evidence.source`,
`evidence.custody_event`, `analysis.device`, `analysis.entity`) are never defined in any `NNNN_*.sql`.

## 1. Migration-by-migration

**0001_init_extensions** — extensions only: `vector, pg_trgm, pgcrypto (:8, "HASHING only… not
UUIDs"), btree_gin, btree_gist, unaccent, citext, ltree, hstore, fuzzystrmatch`, plus guarded
`postgis`, `pg_duckdb`, `pg_stat_statements` (`:27-46`). `pgcrypto` supplies `digest()` for every
sha256 in the chain.

**0002_schema** — creates `evidence` and `analysis` schemas (`:11-12`). Legacy HITL tables
`agent_run`/`approval_request` (`:23-53`), marked superseded by Agno's approvals store (`:17-20`) —
dead but not dropped. **First evidence-hash table**: `evidence.evidence_hash` (`:59-66`) — 5 columns
(`id, source_ref, algo, digest BYTEA, hashed_at`) with ONE check:
`algo <> 'sha256' OR octet_length(digest) = 32` (`:65`) — a **length** check, not correctness.

**0003_normalized_records** — adds `blob_key`, `meta` to `evidence_hash` (`:13-14`). Creates
`analysis.normalized_record` (`:16-31`): `record_type, source, conversation_id, role, content,
occurred_at` (valid time), `knowledge_time TIMESTAMPTZ NOT NULL DEFAULT NOW()` (`:26`),
`disclosure_tier TEXT CHECK (...'contemporaneous','hindsight','discovered')` (`:27-28`).
**`knowledge_time`'s `DEFAULT NOW()` is the defect 0008 later documents as recording row-write time,
not knowledge time** — this one choice cascades to the 0018/0026/0028 horizon-clock rewrites.

**0004_custom_types** — enums (`entity_type, temporal_class, event_type, mcl_factor, source_system,
match_method`) and, critically, `disclosure_tier AS ENUM ('public','restricted','sealed')` (`:30-33`) —
a **sensitivity** concept colliding in name with 0003's **knowledge** concept. Domains
(`confidence, canonical_id, geo_point`), `source_ref` composite.

**0005_workflow_run_ledger** — `analysis.workflow_run` / `workflow_run_stage` (`:18-48`). `sha256 TEXT`
on `workflow_run` (`:25`) is a cache, not verified.

**0006_run_gates_and_custody_tier** — adds `gate_state`, `parent_run_id`,
`custody_tier TEXT NOT NULL DEFAULT 'full' CHECK (IN ('full','light'))` (`:29-34`). Two-tier custody:
`full` = complete evidence-schema hash chain; `light` = sha256+blob+dedupe only, no chain rows, for
knowledge-lane ingests (`:13-21`).

**0007_curation_and_flags** — `analysis.corroboration_flag` (`:44-59`). `linked_artifacts jsonb` is
explicitly **not a foreign key** (`:9-13,55`). Adds a GIN index on `normalized_record.attrs` (`:80-81`)
rather than new columns.

**0008_temporal_clocks_and_provenance** (31KB, largest early file):
- `evidence.acquisition` (`:83-133`): one row per acquisition EVENT, HITL-only
  (`CHECK (asserted_by='human')`, `:117`), append-only **by convention** (`supersedes_id`, `:107-110`)
  — **no trigger enforces this**.
- `evidence.artifact_metadata` (`:162-216`): three-layer metadata (embedded/filename/filesystem), never
  collapsed; `resolved_export_at`/`resolved_source` record which layer won.
- Six new clocks on `normalized_record`: `export_created_at, acquired_at, ingested_at, realized_at`
  (nullable, no default — `:228-232`, deliberately honest-null), `realized_evidence JSONB`.
- **Explicitly marks `knowledge_time` superseded** (`:246-250`: "Do not use for 'when did you know'
  questions") but does not drop or rename it.
- `analysis.device_ownership` (`:314-352`): time-scoped, with a GiST `EXCLUDE` constraint preventing
  overlapping owners (`:345-352`) — real DB-enforced non-overlap.
- `analysis.entity_candidate` (`:416-490`) — first extraction staging table.
- **First append-only trigger**: `entity_candidate_no_mutate()` (`:494-512`) — blocks changing core
  claim fields on UPDATE. Real and unconditional (no GUC gate).
- Resolves the 0004 name collision by `DROP TYPE IF EXISTS public.disclosure_tier` (`:548`) — 0004's
  type was a byte-identical misnamed duplicate of an already-live `sensitivity_tier` (`:537-546`).
- `analysis.vw_record_disclosure` (`:563-585`): computes disclosure tier from clocks (>30-day gaps ⇒
  hindsight/discovered) rather than trusting the asserted column.

**0009_raw_layer_and_derivation** (29KB) — six per-source raw tables via a dynamic `DO $$` loop
(`:80-159`): `evidence.raw_imessage/sms/facebook/csv/ai_chat/phone`. Each has `content_hash TEXT`,
`content_canon DEFAULT 'h2-rawelement-v1'` (`:109-111`), dedup key
`(device_id, medium, content_hash) NULLS NOT DISTINCT` (`:144-145`), and `superseded_by` (`:118-130`).

**Append-only enforcement is INERT BY DEFAULT.** `evidence.raw_no_mutate()` (`:163-200`) checks
`current_setting('app.evidence_live', true)`; if not `'on'`, the trigger is a **pass-through no-op**
(`:174-176`: "During build-out the schema and parsers churn, and a hard immutability rule would force a
DB rebuild"). **Without `ALTER DATABASE <db> SET app.evidence_live = 'on'`, these six raw tables have
no append-only protection at all.** Same pattern for `analysis.derived_write_guard()` (`:281-295`),
gated on `app.enforce_derived_guard`, also off by default.

Also: `analysis.event_source_record.agrees BOOLEAN` (`:227,230-233`) — disagreement is a FINDING, never
auto-resolved; `analysis.record_observation` (`:354-395`, `safe_for_legal_use BOOLEAN DEFAULT FALSE`
`:374`); `analysis.extraction_batch` (`:520-558`) — a materialized, hashed batch handed to the external
extractor so extraction never queries the live DB.

**0010_extraction_candidate_and_acquisition_reconcile** — renames `analysis.entity_candidate` →
`analysis.extraction_candidate`, widens with
`candidate_kind IN ('entity','event','place','relation','claim')` (`:89-91`) plus
`target_table/target_id/payload`. Rebuilds the append-only trigger (`:145-166`) — still real, ungated.
Part B: `evidence.vw_source_acquisition` (`:186-212`) reconciles per-FILE
`evidence.source.acquisition_method` against per-EVENT `evidence.acquisition`, flagging
`METHOD_DIVERGES`/`ACQUIRED_AT_DIVERGES` rather than silently picking a winner.

**0011_attestation_without_event** — makes `event_source_record.event_id` nullable (`:29`) so an
attestation can precede any timeline event; adds
`CHECK (event_id IS NOT NULL OR record_id IS NOT NULL)` (`:39-43`).

**0012_pipeline_visibility** — written after a real incident: a parser silently dropped 516/7,815 MMS
with no trace (`:7-15`). Adds `evidence.ingest_run` (`:44-79`, funnel ledger
claimed→parsed→rejected→raw→spine→attestations) and `evidence.raw_rejected` (`:112-133`). Both written
**outside the ingest transaction** (`:24-26`) so a rollback still leaves an audit trail. Defines
`vw_layer_map, vw_pipeline_funnel, vw_reconciliation, vw_dropped_records, vw_derivation_lineage,
vw_ingest_history`.
**Bug it introduces:** `vw_pipeline_funnel` and `vw_derivation_lineage` hard-code `evidence.raw_sms`
only (`:200-207,307-309`) despite six raw tables — for any non-SMS artifact this silently reports
"0 raw rows," which 0013 calls "true by accident."

**0013_raw_all_and_funnel_across_formats** — fixes the above, found "by reading the first generated
pipeline report rather than by testing" (`:5`). Adds `evidence.vw_raw_all` — `UNION ALL` over all six
raw tables restricted to shared columns (`:31-54`) — and rebuilds the three views on top (`:67-167`).
Adds `evidence.vw_artifacts_without_claim` (`:179-191`) surfacing artifacts with NO `artifact_metadata`
row at all (0012's NULL-check missed this, the worse case).

**0014_split_analysis_into_working_reference_ops** — creates `working`, `reference`, `ops` (`:42-44`)
and moves ~45 tables/views/functions out of `analysis` via three `DO $$` loops, each guarded by
`IF EXISTS (...table_schema='analysis'...)` (`:71-157`). **On a fresh replay every guard is false, so
the loop body never executes once, and the migration commits having moved nothing.** "NO COMPATIBILITY
VIEWS, NO ALIASES" (`:34-36`) — a real design choice, but it means a caller of `working.message` on a
DB where this no-op'd gets a hard "relation does not exist," not a degraded read.

**0015_layer_map_after_schema_split** — rebuilds `evidence.vw_layer_map` with a `rebuild_cost` column
(`:26-72`): `re-parse originals` (RAW) / `re-derive from raw` (working) / `re-seed from source`
(reference) / `not rebuildable` (findings, human labels) / `append-only` (evidence ledger) / `prunable`
(ops). It queries `working.normalized_record`, `working.message` directly (`:36-47`), so on a DB where
0014 no-op'd, this view's `CREATE VIEW` itself fails.

**0016_working_gate_layer** (29KB) — the "real" candidate-review apparatus inside `working`:
`extraction_run` (`:124-149`), `source_provenance` (`:164-224`, append-only-by-convention,
`asserted_by_kind CHECK (='human')` `:195-196`), `candidate_entity`/`candidate_fact`/`candidate_event`
(`:249-402`, each with `promotion_requires_approval` + `promotion_is_complete` CHECK pairs so a row
cannot be half-promoted), `review_decision` (`:409-433`, a separate append-only audit trail from the
candidate's own mutable `review_state`), and `promotion` (`:438-497`, the ledger of what crossed the
human gate and which lane — `as_lived`/`hindsight`/`consolidated`/`support` — enforced via
`promotion_lane_matches_target` CHECK `:471-475`).
**This is the SECOND parallel staging/candidate system.** `:520-530` explicitly stamps
`working.extraction_candidate` and `working.record_observation` as
`'SUPERSEDED by working.candidate_entity / candidate_fact / candidate_event'` — via a `COMMENT ON
TABLE` only, not a DROP. Both coexist.

**0017_append_only_guards** — makes 0016's comment-only claims **actually enforced, unconditionally,
with no GUC gate** — the first place in the chain where this is true without an opt-in:
- `working.forbid_mutation()` (`:25-31`): unconditional `RAISE EXCEPTION` on any UPDATE/DELETE.
  Applied to `source_provenance` (`:33-36`) and `review_decision` (`:38-41`).
- `working.promotion_revoke_only()` (`:43-62`): blocks DELETE; permits exactly one UPDATE shape —
  setting `revoked_at`/`revoked_reason` and nothing else, verified via
  `to_jsonb(NEW) - 'revoked_at' - 'revoked_reason' IS DISTINCT FROM to_jsonb(OLD) - ...` (`:56-58`).
- Lifecycle CHECK: a `completed` run must have `finished_at`; a `failed` one must have `error` (`:70-76`).

**This is the file to cite when someone claims platform-wide append-only enforcement — it is enforced
here (0017) and reused for `ops.audit_ledger` (0020) and `ops.workflow_run_review_action` (0025), but
NOT for the six `evidence.raw_*` tables (0009, gated/off) and NOT via any trigger for
`evidence.evidence_hash` itself (no trigger exists anywhere in the chain for that table).**

**0018_retrieval_axes** — **NOT a table, NOT an enum.** It is a set of **columns added to four existing
tables** (`working.normalized_record, candidate_entity, candidate_fact, candidate_event`) via a
`DO $axes$` loop (`:40-85`): `case_id TEXT DEFAULT 'primary'`,
`domain TEXT CHECK (IN evidence/legal/behavioral/platform_design/context)`, `topic_tags TEXT[]`
(GIN-indexed), `knowledge_actor TEXT DEFAULT 'owner'`, `ontology_version TEXT`, and
`knowledge_time TIMESTAMPTZ` (`:60-61`, `ADD COLUMN IF NOT EXISTS` — a no-op on `normalized_record`,
which already has it from 0003 with the semantics 0008 disowned).
Plus one SQL function `working.horizon_visible(...)` (`:100-119`, `IMMUTABLE` so the planner inlines it)
and one view `working.vw_spine_horizon` (`:130-137`) applying it via session GUCs
`app.case_id`/`app.horizon`/`app.actor`.

**Load-bearing contradiction:** `horizon_visible`'s filter is `row_knowledge_time <= p_horizon` (`:114`)
— the exact column 0008:246-250 calls row-write time and warns against. **The 0018 horizon predicate
filters on a clock its own predecessor disowned.** This is precisely what the unapplied 0026-0028
sequence exists to fix; 0026's backup states it outright ("the predicate was therefore inert relative
to the signed decision — GAP-04").

**0019_reconcile_evidence_hash** — **despite the name, performs ZERO hash computation or verification.**
It only adds columns to `evidence.evidence_hash` (`blob_key, meta, level TEXT DEFAULT 'H1', source_id,
file_node_id, md5_prefilter, record_locator, member_hash_ids UUID[], canon_version DEFAULT
'h1-rawbytes-v1', computed_by`, `:45-55`), a `CHECK (level = ANY ('H1','H2','H3'))` (`:66-71`), and a
`NOT VALID` CHECK that non-H3 rows need `source_id` or `file_node_id` (`:83-87`) — **never later
VALIDATEd anywhere**. FKs added only if `evidence.source`/`file_node` already exist (`:94-120`) — both
out-of-band.
**No CHECK, trigger, or function anywhere verifies that `digest` is actually the hash of anything.** The
only DB guarantee is `octet_length(digest)=32` (0002:65). Hash computation happens entirely in
`custody.py`; the DB trusts whatever bytes are inserted.

**0020_audit_ledger** — `ops.audit_ledger` (`:58-71`): `id BIGINT IDENTITY, entry_hash TEXT NOT NULL,
prev_hash TEXT, payload_hash TEXT` (never raw payload, `:33-34,80-82`). **The chain
(`entry_hash = sha256(prev_hash || canonical-serialization(row))`) is computed in application code
(`server/core/audit.py::record()`) before INSERT — explicitly NOT a DB trigger** (`:40-46`: "UNLIKE
evidence.custody_event's DB-trigger hash…, this hash is computed in application code… The DB only
enforces append-only; it does not compute or verify the hash on write"). Append-only reuses
`working.forbid_mutation()` unconditionally (`:93-96`).

**By contrast, `evidence.custody_event` (out-of-band, only in `sql/bootstrap/schema_baseline.sql:702-717`)
DOES compute its chain via a real DB trigger** — `evidence.chain_custody_event()`:
```
NEW.event_digest := digest(convert_to(
    coalesce(NEW.source_id::text,'') || '|' || coalesce(NEW.file_node_id::text,'') || '|' ||
    coalesce(NEW.evidence_hash_id::text,'') || '|' || NEW.event_type || '|' || NEW.actor || '|' ||
    to_char(NEW.occurred_at,...) || '|' || coalesce(NEW.detail::text,'{}') || '|' ||
    coalesce(encode(NEW.prev_event_digest,'hex'),''), 'UTF8'), 'sha256');
```
(`schema_baseline.sql:710-715`, with `pg_advisory_xact_lock` serializing appends per source at `:706`.)
**The single most rigorous DB-enforced hash chain in the schema — completely invisible to anyone reading
only the numbered chain.** `sql/_manual/20260802_reconcile_evidence_ddl.sql` references the trigger by
name (`:369`) but does NOT include the function body.

**0021_context_record** — `working.context_record` (`:51-75`): a structurally near-identical twin of
`working.normalized_record` but **deliberately standalone — no evidence FK, referenced by no evidence
surface** (`:13-24`). The CONTEXT-never-EVIDENCE boundary made physical. `content_hash TEXT UNIQUE`
(`:68,74`) is the dedup key (`INSERT … ON CONFLICT DO NOTHING`, `:41-43`), computed by the app.
`weaviate_synced_at`/`graphiti_synced_at` (`:72-73`) are the CDC signal — NULL = pending.

**0022_context_assets** — `working.context_archive` (`:31-42`) and `working.context_asset` (`:44-59`) —
index rows for whole chat-export ZIPs and their generated documents/code/images; bytes live in R2,
`content_hash TEXT UNIQUE` (`:51,58`) is the R2 object key and idempotency key. Explicitly NOT routed
through `working.artifact_registry` for the same CONTEXT-never-EVIDENCE reason (`:12-19`).

**0023_drop_context_record_disclosure_tier** — owner correction, quoted verbatim and profanely
(`:8-10`): drops `disclosure_tier` from `context_record` because it should never have been asserted at
ingest — horizon tier is derived downstream from `working.realization_event`. `normalized_record`
KEEPS its `disclosure_tier` (`:18-22`).

**0024_chat_conversation_and_message** (18KB) — **a THIRD, independent chat-ingestion model**:
`working.chat_conversation` / `working.chat_message` (`:12-37`) with its own
`content_hash CHECK (length=64)` (`:34`), own `role`/`sent_at`/`thinking`. **No FK, no shared key, and
no comment relating it to `working.context_record`** (grepped both directions, zero cross-references).
Layers on: `chat_chunk` (`:103-118`), `chat_chunk_lane` (`:131-149`, routes to
`platform/legal/personal_history/context` — explicitly NOT `evidence`, `:128-130`),
`reference.knowledge_tag` + `chat_chunk_tag` (`:159-183`), `chat_chunk_embedding` (`:190-201`),
`chat_chunk_projection` (`:203-215`), and a full transactional-outbox/CDC apparatus
(`chat_conversation_event, chat_message_event, chat_chunk_event, chat_chunk_lane_event,
context_asset_event, chat_cdc_cursor, chat_projection_dead_letter` — `:296-372`) built on
`working.emit_chat_row_event()` (`:296-304`) and `pg_notify`. Also `working.investigation_event`
(`:224-249`) — a human-curated "concern, not established fact" register promotable to
`analysis.timeline_event` by explicit human act.

**0025_durable_run_reports** — adds `outcome_reason_code`/`outcome_reason_detail` to
`ops.workflow_run_stage` with a terminal-state CHECK (`:26-33`), `trace_id`/`report_schema_version` to
`ops.workflow_run`. `ops.workflow_run_review_action` (`:43-53`) — append-only, real unconditional
trigger via `working.forbid_mutation()` (`:59-63`).

**0026_realization_event** (30KB) — **line 2 of the current file:
`-- HELD FOR OWNER / NOT APPLIED FOUNDATION REWRITE -- 2026-08-18`.**
- `normalized_record` gains `source_record_key, source_content_sha256 BYTEA CHECK(len=32), sender,
  recipients, message_corpus CHECK(IN first_party/acquired_third_party)` (`:52-77`).
- `working.normalized_record_chunk` (`:83-104`) — derived chunks separated from the authored spine.
- `working.message_projection_route` (`:107-122`) — first-party vs acquired-third-party projection
  mutually exclusive via its PK.
- `working.third_party_conversation` / `third_party_message` / `third_party_message_participant` /
  `third_party_conversation_acquisition` (`:167-251`) — gated on an approved `evidence.acquisition` link.
- `working.realization_event` / `realization_event_record` (`:258-309`) — **plural** realization atoms
  (`kind IN contradiction/export_read/told_by_person/manual/betrayal/deceit/gaslighting/
  pattern_recognition`), replacing the singular `normalized_record.realized_at`, whose COMMENT this file
  deprecates: *"Deprecated singular clock; realization is plural in working.realization_event"*
  (`:463-467`); `acquired_at` gets the same stamp pointing at `evidence.acquisition` (`:457-461`).
- `working.source_available_from()` / `visible_from()` (`:311-334`) — the intended replacement clock.
- Two large plpgsql cross-table validators — `validate_message_projection()` (`:350-405`) and
  `validate_realization_links()` (`:407-425`) — installed as `DEFERRABLE INITIALLY DEFERRED` constraint
  triggers (`:427-445`), the most sophisticated validation in the chain. **Not applied.**
- `working.evidence_vector_projection_job` (`:482-502`) — Weaviate projection outbox, latest revision only.

**0027_walk_ledger** — line 10: `⚠ HELD FOR OWNER — COMMITTED + ROLLBACK-VALIDATED, NOT APPLIED TO PROD.`
`working.walk_run`/`walk_step`/`walk_step_retrieval` (`:82-238`) implement ADR-0045 §B's version-pinned,
hash-chained "pass" materialization (`base_version, genesis_hash`, per-step `corpus_hash`/`prev_hash`,
`:99-201`). `vw_walk_contamination` (`:247-265`, redefined `:361-376`) flags any record an "ignorant"
agent retrieved whose `visible_from()` is AFTER that step's horizon. 2026-08-18 amendments add
`working.walk_checkpoint` (healthy/resumable vs `failure_seal`/immutable, `:280-298`) and
`vw_walk_base_version_input` (`:329-358`).

**0028_horizon_repoint** — line 10: `⚠ HELD FOR OWNER — DRAFTED + ROLLBACK-VALIDATED 2026-08-14, NOT
APPLIED TO PROD.` This is the migration that would fix the 0018 contradiction: it would
`CREATE OR REPLACE VIEW working.vw_spine_horizon` to filter on `working.horizon_record_visible(...)` —
a materialized-fast-path/function-fallback predicate on `visible_from()`/`source_available_from()`
(`:116-160`) — instead of the superseded `knowledge_time` predicate. `working.record_visible_from`
(`:61-107`) is the materialized cache, fail-closed: NULL availability always denies, even for a
hindsight agent (`:119-137`, comment `:164-165`). **Because this is unapplied, `vw_spine_horizon` as
created by 0018 (filtering `knowledge_time`) is presumably still live** unless applied out-of-band.

**0029_pass_grants** — HELD, NOT APPLIED, **and self-documented as non-enforcing even if applied.**
Creates `pass_refresher, pass_reader, projection_refresher, horizon_reviewer` NOLOGIN roles with
default-deny GRANT/REVOKE scoping (`:63-238`), but its own header (`:11-19`) states:

> "⚠ INERT WHILE SUPERUSER (the decisive finding): the agno app connects as the role `ai`, which is a
> SUPERUSER (verified live 2026-08-14: rolsuper=True, rolcreaterole=True; the only login role; owner of
> every working./ops. table). Superusers bypass ALL grants and BYPASSRLS. These grants are therefore the
> SCHEMA CONTRACT for the target isolation, NOT an enforcing guard under the current connection model."

The file is explicit that "the F13 app-side advisory lock is the sole EFFECTIVE sole-writer guard" (`:19`).

**0030_matter_case_foundation** — line 6: `⚠ HELD FOR OWNER — DRAFTED + STATIC-VALIDATED, NOT APPLIED TO
ANY DATABASE.` Introduces `analysis.matter`/`analysis.court_case`/`analysis.matter_knowledge_partition`
(`:17-93`) as a **new, explicitly non-unifying** layer alongside the legacy `analysis.evidence_item.case_id`
UUID column (`:10-13,96,125-126`). `analysis.knowledge_evidence_promotion` (`:151-203`) with
`guard_knowledge_evidence_promotion()` (`:244-328`), a BEFORE INSERT trigger cross-validating against
`evidence.evidence_hash` — checking `hash_algo <> 'sha256'`, `hash_canon <> 'h1-rawbytes-v1'`,
`octet_length(hash_digest) <> 32`, **and**
`encode(hash_digest,'hex') IS DISTINCT FROM NEW.source_pointer ->> 'sha256'` (`:312-323`). Real,
DB-enforced, unconditional — **and not live.**

## 2. Backup files

| File | Lines | Byline / header | Relationship to current |
|---|---|---|---|
| `0026...backup_20260818_054732` | 254 | glm-5.2:cloud, 2026-08-14, HELD | Original narrow draft: only `realization_event`(+`_record`) |
| `0026...backup_20260818_070500` | 412 | Codex GPT-5 amendment #1 | Adds `message_projection_route`, `third_party_*` |
| `0026...backup_20260818_074500` | 452 | + amendment #2 | Adds `acquisition.asserted_by_identity`, validator triggers |
| `0026...backup_20260818_081415` | 453 | minor tweak | Near-final |
| `0026_realization_event.sql` (current) | 569 | + native Weaviate outbox + legacy realization-kind upgrade | Adds `evidence_vector_projection_job` + `pattern_recognition` |
| `0027...backup_20260818_054732` | 293 | glm-5.2:cloud, 2026-08-14 | Pre-checkpoint/resumability |
| `0027_walk_ledger.sql` (current) | 400 | + Codex GPT-5 2026-08-18 | Adds `walk_checkpoint`, `walk_step_realization_retrieval`, `vw_walk_base_version_input`, fail-closed NULL |
| `0028...backup_20260818_054732` | 100 | glm-5.2:cloud, 2026-08-14 | Pre legacy-cache forward upgrade |
| `0028_horizon_repoint.sql` (current) | 169 | + Codex amendment | Version-pins cached values, NULL = deny |
| `0029...backup_20260818_054732` | 127 | glm-5.2:cloud, 2026-08-14 | Original refresher/reader-only design |
| `0029...backup_20260818_074500` | 235 | + Codex amendment | Adds `projection_refresher`, `horizon_reviewer` |
| `0029...backup_20260818_081415` | 239 | minor tweak | Near-final |
| `0029_pass_grants.sql` (current) | 246 | + native vector outbox grants | |

**Verdict: an in-progress, actively-iterated migration sequence, not stale cruft.** Every backup and
current file for 0026-0029 carries the identical `HELD FOR OWNER … NOT APPLIED TO PROD` banner, and the
backups form a strict linear additive growth chain. Timestamped checkpoints from one intensive design
day (2026-08-18) building on a 2026-08-14 foundation, kept per the never-delete convention.

**The consequential fact: as of current file contents, 0026 through 0030 — five consecutive files,
one-sixth of the numbered chain — are all explicitly marked not applied to any database.** Therefore:
- The horizon predicate running live is very likely still 0018's `knowledge_time`-based one.
- `working.realization_event`, `walk_run`/`walk_step`, `third_party_*`, `analysis.matter`/`court_case`,
  and `knowledge_evidence_promotion` may not exist live at all, or may exist in a different shape
  applied out-of-band. The sql/ layer cannot resolve this.
- The README's 2026-08-16 note says the 2026-08-10 baseline already contains
  `horizon_visible`/`vw_spine_horizon`/realization_event objects, but that capture PREDATES the
  2026-08-18 amendments, so it cannot attest to the current shape either.

## 3. Duplicate / parallel table concepts

1. **THREE independent AI-chat/message ingestion schemas with no cross-links:**
   - `working.normalized_record` + `working.message`/`message_participant`/`conversation` (0003, 0009,
     moved by 0014) — the evidence-tier spine.
   - `working.context_record` (0021) — near-identical twin, deliberately standalone.
   - `working.chat_conversation`/`chat_message`/`chat_chunk` (0024) — a third fully independent model
     with its own hashing, chunking, lane-routing, CDC outbox. **Zero references either way** between
     0021 and 0024. Whether 0024 supersedes 0021/0022 or coexists is not stated anywhere in the SQL.
2. **Two extraction/candidate staging systems, neither dropped:**
   `analysis.entity_candidate` (0008) → `extraction_candidate` (0010) → `working.` (0014); vs
   `working.candidate_entity/candidate_fact/candidate_event` (0016), which 0016:520-530 stamps as
   superseding the former — via COMMENT only.
3. **Two `review_decision` concepts:** `analysis.review_decision` (out-of-band, in 0015's layer map
   `:59`) vs `working.review_decision` (0016:409-433) — unrelated schemas.
4. **`normalized_record` carries columns its own migration comments call deprecated** — `acquired_at`
   and `realized_at` deprecated by 0026:457-467, whose replacements aren't live.
5. **0012→0013 funnel churn** — 0012's SMS-only version fully superseded by 0013's cross-format one.
   Normal history, self-corrected within one cycle.
6. **Case-management identity duplication, acknowledged in source:** `analysis.evidence_item.case_id`
   (legacy UUID, out-of-band) vs the new `analysis.matter`/`court_case`/`matter_knowledge_partition`
   (0030), which states three times (`:10-13,96,125-126,140-145`) that it does NOT replace the legacy
   column; `matter_knowledge_partition` is purely a compatibility bridge.

## 4. `_manual`, `bootstrap`, `drafts`, `validation`

- **`_manual/20260801_clear_case_data.sql`** — a manual, already-executed, one-time data-clearing script
  (7,753 rows cleared 2026-08-01), kept OUT of the numbered chain so a runner can never replay it
  (`:4-6`). Documents its own near-miss: the first draft would have deleted 1,918 hand-labelled rows
  because `analysis.human_label.message_id` was the primary key, not just an FK (`:19-24`); and a
  write-once trigger on `evidence.source` stopped an attempted delete of the custody spine (`:26-28`) —
  real evidence that `source_immutable_core()` (out-of-band, `schema_baseline.sql:782-807`) fires.
- **`_manual/20260802_reconcile_evidence_ddl.sql`** — a PARTIAL `pg_dump --schema-only` capture
  (tables/constraints/triggers only, no function bodies) of the out-of-band custody DDL
  (`evidence.source`, `custody_event`, `file_node`), captured as "evidence of what exists, not a
  migration to run" (`:14-16`). References `chain_custody_event()` and `forbid_mutation()` by name
  (`:369,376,383`) without bodies.
- **`bootstrap/schema_baseline.sql`** (455KB) — the full schema-only dump, 2026-08-10; per README now
  stale relative to the 2026-08-18 state of 0026-0029 and currently fails a direct replay
  (`pg_duckdb` ordering bug). **The only file in `sql/` containing the real hash-chain trigger bodies.**
- **`drafts/walk_ledger.postgres-draft.HOLD.sql`** — explicitly marked superseded at the top
  ("SUPERSEDED (2026-08-09) — the 'wrong engine' HOLD below is VOID. Kept as design history only. Do NOT
  apply as-is."). Originally `sql/0009_walk_ledger.sql` on the theory the walk ledger belonged in
  SurrealDB; that theory died with ADR-0043 and was superseded by ADR-0045 §B, implemented as 0027.
- **`validation/`** — `gen_validate.py` and `gen_validate_0016.py` build a rollback-transaction test
  harness per migration (migration body verbatim, `COMMIT` swapped for probes + `ROLLBACK`), designed so
  "a run against production writes nothing." `validate_0016_working_gate_layer.sql` is generated output
  and carries its own live-vs-design-history warning (still references SurrealDB because it mirrors
  APPLIED HISTORY from when 0016 was written).

## 5. Summary — hash/custody enforcement: DB-level vs documented-only

| Object | Real DB enforcement? | Notes |
|---|---|---|
| `evidence.evidence_hash.digest` correctness | **No.** Only `octet_length(digest)=32` (0002:65) | Nothing computes or verifies this hash against source bytes. |
| `evidence.evidence_hash` append-only | **No trigger exists for this table at all** | Immutability lives on `source`/`custody_event`/`file_node`, not `evidence_hash`. |
| `evidence.source` immutability | **Yes, real, unconditional** — `source_immutable_core()` (schema_baseline.sql:782-807), **out-of-band** | Verified fired in practice per `_manual/20260801`. |
| `evidence.custody_event` hash chain | **Yes, real, unconditional, DB-computed** — `chain_custody_event()` (schema_baseline.sql:702-717) | Most rigorous chain in the schema; **entirely out-of-band**. |
| `evidence.raw_*` (six tables) append-only | **No, by default** — `raw_no_mutate()` (0009:163-200) gated on `app.evidence_live` | Explicit, deliberate, documented. |
| `analysis`/`working` derived-table guard | **No, by default** — gated on `app.enforce_derived_guard` (0009:281-295) | Same pattern. |
| `working.extraction_candidate` mutation guard | **Yes, real, unconditional** (0008:494-512, 0010:145-166) | |
| `working.source_provenance`, `review_decision` | **Yes, real, unconditional** — `forbid_mutation()` (0017:25-41) | First fully-enforced ungated pattern. |
| `working.promotion` | **Yes, real** — revoke-only (0017:43-67) | |
| `ops.audit_ledger` | Append-only **yes**; hash chain **no** (app-side, 0020:40-46) | |
| `ops.workflow_run_review_action` | **Yes, real, unconditional** (0025:59-63) | |
| `analysis.knowledge_evidence_promotion` | **Yes, real** — cross-checks claimed sha256 vs `evidence_hash.digest` (0030:312-323) | Consistency check between two stored values, not recomputation. **HELD, not applied.** |
| `evidence.acquisition`, `working.candidate_*`, `walk_*`, `third_party_*` | Documented append-only/HITL in comments (0008, 0016, 0026, 0027) | **No enforcing trigger** for most; 0026's validators are unapplied. |

**Bottom line:** genuine unconditional DB-level enforcement exists and is real, but concentrated in a
handful of places (0017, 0020, 0025, plus out-of-band `evidence.source`/`custody_event`) — not uniform.
A large fraction of "append-only"/"immutable"/"hash-verified" claims in comments are either gated behind
a GUC defaulting off (0009), computed and trusted from application code with no DB check (0019's
`evidence_hash.digest`, 0020's `audit_ledger.entry_hash`), or sitting in migrations (0026-0030)
explicitly not applied.
