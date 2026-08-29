# AI → Platform Consolidation Implementation Packet

> _Byline: OpenCode DeepSeek V4 Flash · 2026-08-29_
> _Byline correction and implementation: Codex · GPT-5.6 · 2026-08-29_
>
> **READ-ONLY AUDIT.** No schema/data/role/grant changes were made. Live databases `ai` and
> `platform` on ovh-files (100.91.190.107:5432) were queried with catalog/count statements only.
> No credentials or case contents are reproduced; only aggregate counts and schema metadata.
> This packet is designed to be implemented by a separate worker without re-discovery.

> **CURRENT IMPLEMENTATION STATUS — THIS OVERRIDES CONFLICTING INSTRUCTIONS BELOW.** The
> structural foundation is implemented locally in forward migration
> `0049_ai_platform_consolidation_foundation.sql`, the read-only auditor
> `scripts/audit_ai_platform_consolidation.py`, and focused tests. No live copy/cutover has
> started. Migration `0046` is immutable and must never be edited or retargeted. No custody or
> append-only trigger may be disabled by this plan; any mutation-capable loader requires a
> separately designed, independently verified offline-load contract. `ai` remains untouched and
> may only be parked read-only after parity, caller-drain, live integration, and owner gates pass.

> **LOCAL VERIFICATION:** focused Ruff passed; the current non-PG contracts passed **9/9**. The
> strengthened rollback-only PostgreSQL 18 test now includes wrong-kind, unbound, and superseded
> receipt rejection, but its current-code rerun is pending restoration of the disposable
> `platform_migration_test` service credential in this shell. The earlier 8/8 receipt predates the
> strengthened assertions and is not current-revision proof. This remains a zero-net-write
> rehearsal boundary, not a live apply or production cutover.
>
> **V3 ACCEPTANCE HARDENING:** receipt binding versus supersession is now serialized by an
> immutable unique receipt-claim key; migration functions never use `CREATE OR REPLACE` and a
> namespace preflight fails on collision. Caller-fence evidence uses the authenticated
> `ai-platform-caller-fence-v2` contract and binds both database/snapshot/server identities plus
> separate writer counts. Nested dotenv, root `compose.*.yaml`, and standard runtime config formats
> are included in the static caller inventory with explicit auditor self-exclusion.

The read-only auditor inventories every physical partition but excludes partition children from
the logical copy order. Copying through both a partitioned parent and its children would duplicate
rows; the later schema phase must recreate partition DDL while the data manifest names the parent
once.

---

## 0. Executive Summary

**Owner ruling: `platform` is canonical.** The current defect is confirmed and material:

- **`ai`** (53 MB) holds the real, populated evidence/analysis/ops/reference/timeline/working
  schemas plus the Agno operational store (1,907 spans / 1,533 traces) and 1,741
  `working.context_record` rows, 1,918 `analysis.human_label` rows, 1,918 `human_label_gold`.
- **`platform`** (10 MB) is nearly empty — only the `context` import foundation (0036) and
  `public.schema_version` ledger. It holds 7 `activity_execution`, 6 `activity_receipt`,
  5 `hash_batch`/`hash_batch_member`, 1 `retained_object`, 1 `source`, 2 `source_version`,
  1 `source_version_object`, 1 `source_metadata`.

The defect must be **resolved, not accepted**: the canonical `platform` database does not yet
contain the working/evidence/analysis/ops/reference/timeline data that the product depends on,
and the runtime still defaults to `ai` (`server/core/url.py:22`).

This packet provides: (1) the dated read-only inventories and drift, (2) dependency maps, (3) caller
inventory, (4) zero-caller proof queries, (5) a phased, idempotent, rollback-safe move/copy
plan, (6) cutover order through Temporal/n8n/Coolify, (7) park criteria for `ai`, (8) tests
and live acceptance, and (9) migration-chain reachability reconciliation (0045→0046→0047→0048).

The live observations below were verified by the OpenCode audit on 2026-08-29; they are not a
claim that live state cannot drift. Re-run the new read-only auditor before every rehearsal or
cutover proposal.

---

## 1. Live Cluster Inventory

### 1.1 Databases (queried from `postgres`)

| database | size | role |
|---|---|---|
| `ai` | 53 MB | OLD operational + evidence store (defect source) |
| `ai_test_ingest` | 29 MB | test scratch (not in scope) |
| `casebible` | 117 MB | separate corpus (not in scope) |
| `platform` | 10 MB | **CANONICAL** (context + public only) |
| `postgres` | — | maintenance |
| `temporal` / `temporal_visibility` | — | Temporal backend (not in scope) |
| `traceiq` | 134 MB | separate (not in scope) |

### 1.2 Roles (cluster-wide)

| role | login | elevated | notes |
|---|---|---|---|
| `ai` | yes | SUPERUSER, CREATEDB, CREATEROLE, REPLICATION, BYPASSRLS | the superuser; runtime default user |
| `agno_app` | yes | none | created by 0046; currently inert (no password) |
| `platform_runtime` | yes | none | canonical runtime LOGIN |
| `temporal` | yes | none | Temporal |
| `context_import_writer` | no | — | NOLOGIN |
| `context_owner` | no | — | NOLOGIN |
| `context_reader` | no | — | NOLOGIN |
| `platform_admin` | no | — | NOLOGIN |
| `horizon_reviewer`, `pass_reader`, `pass_refresher`, `projection_refresher` | no | — | NOLOGIN |
| `timeline_writer`, `timeline_projector`, `timeline_reader` | no | — | NOLOGIN |

---

## 2. Schema / Object Inventory and Drift

### 2.1 Schemas

| database | schemas |
|---|---|
| `ai` | `ai`, `analysis`, `duckdb`, `evidence`, `ops`, `public`, `reference`, `timeline`, `working` |
| `platform` | `context`, `public` |

**Drift:** `ai` carries the full evidence/analysis/ops/reference/timeline/working surface;
`platform` carries only `context` + `public`. The `working`, `evidence`, `analysis`, `ops`,
`reference`, `timeline` schemas exist **only** in `ai`.

### 2.2 Extensions

| database | extensions |
|---|---|
| `ai` (14) | btree_gin, btree_gist, citext (schema `ai`), fuzzystrmatch (`ai`), hstore (`ai`), ltree (`ai`), pg_duckdb 1.1.0, pg_stat_statements, pg_trgm, pgcrypto, plpgsql, postgis 3.6.4, unaccent, vector 0.8.6 |
| `platform` (2) | pgcrypto, plpgsql |

**Drift:** `platform` lacks the extensions the moved schemas depend on (postgis, vector,
pg_duckdb, pg_trgm, unaccent, btree_gin/gist, citext/hstore/ltree/fuzzystrmatch). These must
be installed on `platform` **before** data move (see §7.2).

### 2.3 Table Row Counts (non-zero only)

**`ai`:**

| schema.table | rows |
|---|---|
| ai.agno_learnings | 4 |
| ai.agno_metrics | 1 |
| ai.agno_schema_versions | 25 |
| ai.agno_service_accounts | 4 |
| ai.agno_sessions | 1 |
| ai.agno_spans | 1907 |
| ai.agno_traces | 1533 |
| ai.api_keys | 1 |
| ai.legal_knowledge_contents | 2 |
| ai.personal_history_knowledge_contents | 1 |
| ai.platform_context_contents | 488 |
| ai.platform_knowledge_contents | 19 |
| ai.relationship_timeline_knowledge_contents | 1 |
| analysis.court_case | 1 |
| analysis.human_label | 1918 |
| analysis.human_label_gold | 1918 |
| analysis.matter | 1 |
| analysis.matter_knowledge_partition | 1 |
| ops.audit_ledger | 7 |
| ops.workflow_run | 2 |
| ops.workflow_run_review_action | 1 |
| ops.workflow_run_stage | 8 |
| public.app_setting | 4 |
| public.canon_registry | 4 |
| public.spatial_ref_sys | 8500 |
| reference.behavior_category | 164 |
| reference.behavior_category_mcl | 225 |
| reference.custody_factor | 12 |
| reference.detection_pattern | 527 |
| reference.detection_pattern_set | 1 |
| reference.pattern_lexicon | 51 |
| reference.topic_code | 10 |
| timeline.timeline_collection | 1 |
| working.context_record | 1741 |

(`evidence.*` tables all empty; `working.normalized_record` 11; most `working.*` empty.)

**`platform`:**

| schema.table | rows |
|---|---|
| context.activity_execution | 7 |
| context.activity_receipt | 6 |
| context.hash_batch | 5 |
| context.hash_batch_member | 5 |
| context.retained_object | 1 |
| context.source | 1 |
| context.source_metadata | 1 |
| context.source_version | 2 |
| context.source_version_object | 1 |
| public.schema_version | 6 |

(`context.hash_manifest`, `hash_manifest_member`, `normalization_lineage`,
`normalized_generation`, `normalized_generation_publication`, `normalized_record_identity`,
`raw_format_registry`, `raw_generation`, `raw_record_identity`, `reconciliation_receipt`
present but 0 rows.)

### 2.4 Schema-Version Ledger Drift

- **`ai.public.schema_version`** columns: `[schema_version_id, version_label, applies_to,
  ddl_uri, ddl_hash, migration_id, supersedes, status, notes, created_by, created_at]` — **0 rows**.
- **`platform.public.schema_version`** columns: `[id, version_label, applies_to, ddl_uri,
  ddl_hash, migration_id, status, notes, created_by, created_at]` — **6 rows**, all `active`:
  `0000_platform_foundation`, `0036_context_import_foundation`, `0037_platform_runtime_connect`,
  `0038_platform_runtime_schema_version_probe`, `0039_context_source_retention_lock`,
  `0042_context_hash_bytea_slice`.

**Drift:** the two `schema_version` tables have **different column shapes** (see §4 collision).
`platform` has applied `0000,0036,0037,0038,0039,0042`; it has **not** applied
`0040,0041,0043,0044,0045,0046,0047,0048`. The `ai` ledger is empty, so `ai`'s applied
migration history is not recorded in `public.schema_version` (only in `ai.agno_schema_versions`,
which is the Agno operational table, not the migration ledger).

---

## 3. Dependency Inventories

### 3.1 `ai` — FK clusters (abridged; full list in §3.1.1)

- **ai.agno_***: component_configs→components, component_links→components+configs,
  schedule_runs→schedules, spans→traces.
- **analysis.***: court_case→matter; evidence_item→court_case+matter+self(supersedes);
  evidence_task→finding; finding_version→finding; finding→self(contradicts);
  factor_citation→evidence_item+self; export_item→evidence_item+export_package;
  completion_evidence→evidence_item+evidence_task; discovery_request→evidence_task;
  discovery_request_revision→discovery_request;
  knowledge_evidence_promotion→court_case+evidence_item+matter_knowledge_partition;
  location_contradiction→location_assertion; matter_knowledge_partition→court_case+matter;
  pattern_finding→finding; review_decision→review_task; score→self(superseded_by);
  task_dependency→evidence_task; task_event/task_legal_link/task_person/task_revision→evidence_task;
  time_assertion→timeline_event+self.
- **evidence.***: acquisition→self(supersedes); artifact_metadata→acquisition+source;
  custody_event→evidence_hash+file_node+source; evidence_hash→file_node+source;
  file_node→self(parent)+source; gps_point→file_node+source; ingest_run→source;
  raw_activity→file_node+source; raw_ai_chat/raw_csv/raw_facebook/raw_imessage/raw_phone/raw_sms→acquisition+source;
  raw_path→raw_activity+file_node+self(parent)+source; raw_rejected→ingest_run;
  raw_trip/raw_visit→file_node+self(parent)+source; source→acquisition+self(supersedes).
- **ops.***: processing_run→self(supersedes); tool_call_ledger→processing_run;
  workflow_run→self(parent); workflow_run_review_action/stage→workflow_run.
- **reference.***: behavior_category_mcl→behavior_category; detection_pattern→behavior_category+detection_pattern_set;
  knowledge_tag→self(parent); legal_issue_factor→custody_factor+legal_issue;
  lexicon_sync→detection_pattern_set; pattern_lexicon→detection_pattern_set.
- **timeline.***: timeline_member→event_candidate+timeline_collection;
  timeline_projection_activation→timeline_projection_generation;
  timeline_projection_generation→timeline_collection+self(since/superseded);
  timeline_projection_member→timeline_projection_generation+timeline_member;
  timeline_projection_receipt→timeline_projection_generation+timeline_projection_member+self(previous).
- **working.*** (largest): account/device/email/handle/organization/person/phone/vehicle→entity(+owner_entity_id);
  artifact_registry→self(parent/superseded); attachment→message; block_status→entity+device;
  call_log→conversation+normalized_record; candidate_entity/event/fact→extraction_run;
  chat_chunk→chat_conversation; chat_chunk_embedding/lane/message/projection/tag→chat_chunk;
  chat_chunk_message→chat_message; chat_message→chat_conversation; context_asset→context_archive;
  context_asset_derivation→context_asset(self); context_asset_message→context_asset+chat_message;
  context_asset_projection→context_asset; conversation_group_member→conversation+conversation_group;
  device_ownership→device+entity; entity→self(merged_into);
  entity_alias/entity_merge_event/entity_resolution→entity; entity_resolution→entity_mention;
  event_source_record→normalized_record; evidence_vector_projection_job→normalized_record_chunk;
  extraction_candidate→extraction_batch+normalized_record;
  geocode_resolution→geocode_result+location+geocode_request; geocode_result→geocode_request;
  gps_track→device; home_base→entity+location; id_xref→entity;
  investigation_event_evidence_link/evidence_need/source/tag→investigation_event;
  lineage_edge→artifact_registry(self); message→conversation+message_projection_route+normalized_record+self(next/prev)+screenshot_attachment;
  message_participant→message; message_projection_route→normalized_record;
  normalized_record→conversation+device+entity; normalized_record_chunk→normalized_record;
  realization_event→normalized_record; realization_event_record→normalized_record+realization_event;
  record_observation→extraction_batch+normalized_record; record_visible_from→normalized_record;
  stay_point→device+location+gps_track;
  third_party_conversation_acquisition→third_party_conversation+self;
  third_party_message→third_party_conversation+normalized_record+message_projection_route+entity;
  third_party_message_participant→entity+third_party_message; walk_checkpoint→walk_run;
  walk_run→walk_checkpoint(self resume)+self(rewalk_of); walk_step→normalized_record+walk_run;
  walk_step_realization_retrieval→realization_event+walk_step; walk_step_retrieval→normalized_record+walk_step.

**Sequences (`ai`):** only `ai.api_keys_id_seq`.

**Triggers (`ai`):** analysis (court_case_set_updated_at, discrev_immutable×2, task_snapshot,
task_status_log, export_append_only×2, finding_version_immutable×2,
knowledge_evidence_promotion_append_only×2+_guard, matter_set_updated_at, redaction_append_only×2,
trg_resev_append×2, rdec_append_only×2, taskevent_immutable×2, taskrev_immutable×2);
evidence (custody_event_chain, custody_event_immutable×2, filenode_immutable×2,
trg_raw_ai_chat/csv/facebook/imessage/phone/sms_no_mutate×2 each, source_immutable×2);
ops (audit_ledger_append_only×2, geocode_audit_immutable×2, tcl_append_only×2,
workflow_run_review_action_append_only×2); timeline (event_candidate_append_only×2,
timeline_member_source_immutable, timeline_projection_activation_append_only×2,
timeline_projection_generation_append_only+_supersede_only, timeline_projection_member_append_only×2,
timeline_projection_receipt_append_only×2); working (chat_chunk_outbox×2, chat_chunk_lane_outbox×2,
chat_conversation_outbox×2, chat_message_outbox×2, context_asset_outbox×2, trg_mention_append×2,
trg_merge_append×2, trg_extraction_candidate_no_mutate, edge_append_only×2,
message_projection_validate×3, trg_message_derived_guard×2, trg_message_participant_derived_guard×2,
evidence_vector_route_enqueue×3, evidence_vector_chunk_enqueue, promotion_revoke_only×2,
realization_link_validate×3, review_decision_append_only×2, source_provenance_append_only×2,
evidence_vector_acquisition_enqueue×3).

**Functions (`ai`, app schemas):** analysis.guard_knowledge_evidence_promotion(),
knowledge_evidence_pointer_hash(jsonb), log_task_status(), set_case_management_updated_at(),
snapshot_task(); evidence.chain_custody_event(), forbid_mutation(), raw_no_mutate(),
source_immutable_core(); timeline.forbid_member_source_repoint(), forbid_mutation(),
generation_supersede_only(); working.derived_write_guard(), emit_chat_row_event(),
enqueue_evidence_vector_projection(uuid[],text), entity_candidate_no_mutate(),
extraction_candidate_no_mutate(), forbid_mutation(), horizon_record_visible(uuid,timestamptz,text),
horizon_visible(text,timestamptz,text,text,text,timestamptz,text,text), promotion_revoke_only(),
queue_vector_chunk_on_insert(), queue_vector_route_change(),
queue_vector_third_party_authority_change(), reject_mutation(), source_available_from(uuid),
validate_message_projection(), validate_realization_links(), visible_from(uuid).
(`ai.*` functions are ltree/hstore/citext/fuzzystrmatch extension functions.)

### 3.2 `platform` — dependencies

**FKs (context):** activity_execution→source_version; activity_receipt→activity_execution;
hash_batch→activity_execution+activity_receipt+normalized_generation+raw_generation+source_version;
hash_batch_member→hash_batch+normalized_record_identity+raw_record_identity+source_version;
hash_manifest→normalized_generation+raw_generation+hash_receipt(sealed);
hash_manifest_member→hash_manifest+normalized_record_identity+raw_record_identity;
hash_receipt→activity_receipt+hash_manifest+normalized_generation+normalized_record_identity+raw_generation+raw_record_identity+source_version;
normalization_lineage→normalized_generation+normalized_record_identity+raw_generation+raw_record_identity(composite);
normalized_generation→raw_generation+source_version;
normalized_generation_publication→activity_receipt+normalized_generation;
normalized_record_identity→normalized_generation+source_version;
raw_generation→retained_object(extraction_bundle)+raw_format_registry+source_version;
raw_record_identity→raw_generation+raw_format_registry+source_version_object+source_version;
reconciliation_receipt→activity_receipt+normalized_generation+raw_generation;
source_metadata→activity_receipt+raw_record_identity+source_version;
source_version→source_version_object(original_object_membership)+retained_object+source;
source_version_object→retained_object+self(parent)+source_version.

**Sequences (`platform`):** none.

**Triggers (`platform`, context):** activity_execution_append_only×2+_retention_gate;
activity_receipt_append_only×2; hash_batch_insert_gate+_transition_gate×2;
hash_batch_member_append_only×2+_open_gate; hash_manifest_delete_forbidden+_insert_gate+_seal_gate;
hash_manifest_member_append_only×2+_open_gate; hash_receipt_append_only×2+_insert_gate+_seal_manifest;
normalization_lineage_append_only×2+_open_generation_gate;
normalized_generation_retention_gate+_seal_publish_gate;
normalized_generation_publication_append_only×2+_receipt_gate;
normalized_record_identity_append_only×2+_open_generation_gate;
raw_format_registry_append_only×2; raw_generation_retention_gate+_seal_gate;
raw_record_identity_append_only×2+_open_generation_gate;
reconciliation_receipt_append_only×2+_insert_gate; retained_object_append_only×2;
source_append_only×2; source_metadata_append_only×2+_open_generation_gate;
source_version_append_only×2; source_version_object_append_only×2+_insert_gate.

**Functions (`platform`, context):** assert_hash_manifest_complete(uuid),
assert_normalized_generation_open(uuid), assert_raw_generation_open(uuid),
assert_raw_subtype_completeness(uuid), assert_source_version_retained(uuid), forbid_mutation(),
guard_activity_execution_insert(), guard_hash_batch_insert(), guard_hash_batch_member_insert(),
guard_hash_batch_transition(), guard_hash_manifest_insert(), guard_hash_manifest_member_insert(),
guard_hash_manifest_transition(), guard_hash_receipt_insert(), guard_normalization_lineage_insert(),
guard_normalized_generation_insert(), guard_normalized_generation_transition(),
guard_normalized_publication(), guard_normalized_record_insert(), guard_raw_generation_insert(),
guard_raw_generation_transition(), guard_raw_record_insert(), guard_raw_subtype_insert(),
guard_reconciliation_receipt_insert(), guard_source_metadata_insert(),
guard_source_version_mutation(), guard_source_version_object_insert(),
register_raw_format_subtype(text), seal_hash_manifest_from_receipt().
Plus `public.*` pgcrypto functions.

**Tables (`platform`, 21):** context.activity_execution, activity_receipt, hash_batch,
hash_batch_member, hash_manifest, hash_manifest_member, hash_receipt, normalization_lineage,
normalized_generation, normalized_generation_publication, normalized_record_identity,
raw_format_registry, raw_generation, raw_record_identity, reconciliation_receipt,
retained_object, source, source_metadata, source_version, source_version_object;
public.schema_version.

---

## 4. Duplicate / Conflicting Object Names

| relname | `ai` | `platform` | conflict |
|---|---|---|---|
| `schema_version` | public.schema_version (cols: schema_version_id, supersedes) | public.schema_version (cols: id uuid, no supersedes) | **DIFFERENT COLUMN SHAPES** — cannot merge as-is |
| `source` | evidence.source | context.source | different schemas, different shapes — safe (schema-qualified) |

No other same-name collisions across the two databases. Within `ai`, `public.schema_version`
and `ai.agno_schema_versions` are distinct tables (migration ledger vs Agno operational).

---

## 5. Caller / Env Inventory — who still selects `ai` or old env names

| location | reference | issue |
|---|---|---|
| `server/core/url.py:22` | `database = getenv("DB_DATABASE", "ai")` | **DEFAULT IS `ai`** — runtime default points at old DB |
| `server/core/url.py:18-19` | user/pass default `ai`/`ai` | old creds default |
| `server/core/url.py:13` | `PLATFORM_DB_URL` override | exists but not default |
| `.env` | DB_HOST=agentos-db, DB_PORT=5432, DB_USER=ai, DB_DATABASE=ai, POSTGRES_DB=ai | all point at OLD `ai` db, host `agentos-db` (compose-internal) |
| `deploy/compose.yaml:31,69` | `POSTGRES_DB=${DB_DATABASE:-ai}`, `DB_DATABASE=${DB_DATABASE:-ai}` | defaults to `ai` |
| `deploy/data-pg.yaml:46` | `POSTGRES_DB=${DB_DATABASE:-ai}` | defaults to `ai` |
| `deploy/exec.yaml:111` | `DB_DATABASE=${DB_DATABASE:-ai}` | defaults to `ai` |
| `scripts/railway/up.sh:102,124` | `DB_DATABASE:-ai` | defaults to `ai` |
| `scripts/audit_dump.py` | `DB_DATABASE=ai` example | doc/example |
| `scripts/run_classification_batch.py:40` | `dbname=DB_DATABASE` | inherits env default |
| `scripts/apply_validate_0043_0044.py` | TARGET_DATABASE='platform', LEGACY_DATABASE='ai' | correct split |
| `scripts/bootstrap_platform_database.py` | TARGET_DATABASE='platform' | correct |
| `scripts/apply_0036_live.py` / `validate_0036_live.py` | connect to platform, verify current_database()='platform' AND legacy ai exists | correct |
| `server/core/session.py` | get_agno_db() → PostgresDb db_id='agentos-db' (Agno operational); get_postgres_db() → Postgres for Knowledge rows + pg_duckdb/evidence; create_knowledge() → Weaviate vectors | operational store + knowledge rows land in whatever DB the env points at |

**Conclusion:** the runtime and all deploy manifests default to database `ai`. The canonical
`platform` is only reached by the explicit `scripts/*_platform*` and `apply_validate_0043_0044`
paths. **Cutover requires flipping the default** (`DB_DATABASE` default → `platform`) and
re-pointing `server/core/url.py`, `.env`, and all deploy manifests, **after** the data move.

---

## 6. Zero-Caller Proof Queries (run on `ai` before park)

These must return **0 rows / no active sessions** before `ai` is parked read-only. Run as a
superuser on `ai`:

```sql
-- 1. No active backend sessions connected to ai
SELECT count(*) FROM pg_stat_activity WHERE datname = 'ai' AND pid <> pg_backend_pid();

-- 2. No prepared statements / open transactions from app roles
SELECT count(*) FROM pg_prepared_xacts WHERE database = 'ai';

-- 3. No replication slots bound to ai
SELECT count(*) FROM pg_replication_slots WHERE database = 'ai';

-- 4. No active locks held by non-self sessions on ai
SELECT count(*) FROM pg_locks l JOIN pg_database d ON d.oid = l.database
 WHERE d.datname = 'ai' AND l.pid <> pg_backend_pid();

-- 5. No uncommitted xacts (read-only snapshot of oldest active xid)
SELECT count(*) FROM pg_stat_activity
 WHERE datname='ai' AND pid <> pg_backend_pid() AND state <> 'idle';
```

**Park gate:** all five return 0, the read-only auditor reports zero unresolved static runtime
references to `ai`, and `--live-config-evidence` supplies at least one valid, time-bounded
`ai-platform-caller-fence-v2` attestation authenticated with a trusted HMAC key supplied as
`--trusted-fence-key KEY_ID=PATH`. The signed payload must bind the current repository revision;
source and target database names/OIDs; both snapshot hashes; system identifier, server address/port,
postmaster start; issued/established/expiry times; signer key ID; separate zero source/target active
writer counts and admission fences; and Coolify, n8n, and Temporal configuration inventories. Wrong
target, cluster, revision, snapshot, signer, signature, or observation window fails closed. A
point-in-time session count alone cannot pass. The scanner covers nested `.env` variants,
`compose.*.yaml`, Dockerfiles, PowerShell, JSON/JSONC, INI/config/properties, Terraform, TOML,
JS/TS, YAML, XML, Python, Go, and shell runtime surfaces, and explicitly excludes the auditor itself.

---

## 7. Phased Schema + Data Move/Copy Plan

### 7.0 Guiding invariants (must be preserved)

- **UUIDs** — copy `id`/PK values verbatim; never regenerate.
- **FKs** — copy in dependency order (parents before children); re-create FK constraints after
  data load, or use `SET CONSTRAINTS ALL DEFERRED` within a single transaction.
- **Append-only / custody hashes** — do not recompute; copy stored `sha256`/`bytea` digests
  verbatim. **Do not disable custody or append-only triggers.** A future mutation-capable loader
  is blocked until a separately designed and independently verified offline-load contract proves
  how these invariants remain enforced throughout the copy.
- **Provenance / source clocks** — copy `occurred_at`, `source_available_from`,
  `knowledge_available_from`, `created_at`, `updated_at` verbatim; do not stamp new clocks.
- **First/third-party projections** — copy `third_party_*` tables and their
  `conversation_acquisition_id` FKs verbatim; do not invent owner participants.
- **Relative-time links** — copy `relative_time_anchor` and link tables verbatim.
- **Schema versions** — reconcile the two `schema_version` shapes (§4) before merge; the
  canonical ledger is `platform.public.schema_version`.
- **Roles** — recreate the NOLOGIN grant roles on `platform` and re-grant; `platform_runtime`
  is the only LOGIN among the grant roles.

### 7.1 Phase 0 — Freeze & snapshot (no delete)

1. Record a **pre-move manifest** of every `ai` object (schema/table/sequence/trigger/function/
   constraint) with row counts and a `pg_dump --schema-only` + `pg_dump --data-only` to a
   versioned archive (e.g. `../_stale/ai-consolidation-20260829/`). This is the rollback source.
   The read-only audit manifest binds each database's MVCC transaction snapshot, WAL LSN,
   observation timestamp, database OID, server version/address/start time and system identifier
   when available, plus independent source/target snapshot hashes and the repository revision.
   Source and target snapshots are explicitly separate database observations; the external caller
   fence is what prevents writes across the comparison window.
2. **Do not drop anything.** Rollback = restore from this snapshot into a fresh DB, or abort
   mid-phase and leave `ai` untouched.

### 7.2 Phase 1 — Prepare `platform` (canonical)

1. Install missing extensions on `platform`: `postgis`, `vector`, `pg_duckdb`, `pg_trgm`,
   `unaccent`, `btree_gin`, `btree_gist`, `citext`, `hstore`, `ltree`, `fuzzystrmatch`
   (match `ai` §2.2). **Owner decision:** confirm these are acceptable on the canonical DB.
2. Recreate the NOLOGIN grant roles on `platform` if absent: `context_import_writer`,
   `context_owner`, `context_reader`, `platform_admin`, `horizon_reviewer`, `pass_reader`,
   `pass_refresher`, `projection_refresher`, `timeline_writer`, `timeline_projector`,
   `timeline_reader`. `platform_runtime` (LOGIN) must be the only LOGIN among them.
3. Reconcile `public.schema_version` shape: **owner decision** — either (a) migrate `ai`'s
   ledger rows into `platform`'s `id`-shaped table, or (b) keep `platform`'s shape as canonical
   and record `ai`'s history as a single `0000_ai_legacy_import` row. Recommend (b) to avoid
   rewriting the canonical ledger DDL.
4. Apply only migrations proven applicable to the canonical target in their forward order.
   **Never edit or retarget `0046`; it is immutable historical state.** Migration `0049` is the
   forward-only consolidation proof foundation. Runtime-role/cutover grants, if still required,
   belong in a later reviewed forward migration after the runtime-role decision is settled.

### 7.3 Phase 2 — Schema + data move (copy, not move, until verified)

Copy each `ai` schema into `platform` under the **same schema name**, in dependency order:

1. **Reference data first** (no FK to app data): `reference.*`, `public.*` (app tables:
   agent_run, app_setting, approval_request, canon_registry, change_log, classification_version,
   decision_log, decision_precedent, memory_items, model_version, ontology_version,
   open_questions, prompt_registry, session_summaries, transcript_insight — **skip**
   `spatial_ref_sys` which is postgis-managed, and skip `schema_version` which is reconciled
   separately).
2. **Agno operational** `ai.agno_*` + `ai.api_keys` (needed by `get_agno_db()`).
3. **Evidence spine** `evidence.*` (parents: source, acquisition, file_node; then children).
4. **Working** `working.*` (entity/person/device/conversation first, then normalized_record,
   then message/chat_chunk, then derived/outbox/vector tables).
5. **Analysis** `analysis.*` (matter, court_case, then findings/evidence_item/tasks).
6. **Ops** `ops.*` (workflow_run, then stages/review_actions/processing_run/tool_call_ledger).
7. **Timeline** `timeline.*` (timeline_collection, event_candidate, then projections).

**Mechanics are intentionally not implemented in this slice.** The future loader may use COPY
or another bounded mechanism only after its offline-load contract proves append-only and custody
enforcement without disabling triggers. Preserve sequence positions. Use dependency order and
only defer constraints that are already declared DEFERRABLE; never bypass FK or custody guards.

**Idempotent receipts/checkpoints:** migration `0049` creates
`public.platform_consolidation_checkpoint` and
`public.platform_consolidation_proof_receipt`, plus the internal
`public.platform_consolidation_receipt_claim` serialization table. Phase/relation/attempt and
receipt-proof unique keys make exact reruns idempotent; all three tables reject
UPDATE/DELETE/TRUNCATE and authorize no copy. The claim table's receipt-ID primary key makes
`verified` and `superseded` mutually exclusive even across racing transactions. A `verified`
checkpoint names one exact unsuperseded passing receipt of its required kind.
The receipt's non-empty details must exactly bind phase, relation, proof kind, source/target
transaction snapshot IDs and hashes, manifest hash, and repository revision. Row-parity proof also
requires equal non-null counts. Caller proof additionally binds the exact time-bounded external
fence-attestation ID, digest, establishment time, and expiry. A bound receipt cannot be superseded; corrections are a
new immutable checkpoint attempt.

Migration-owned functions have `_v0049` names and are created without replacement. Before creating
anything, migration 0049 rejects any existing consolidation relation or same-signature function;
it never overwrites an existing namespace object.

### 7.4 Phase 3 — Verify (before any cutover)

1. **Row-count parity:** for every copied table, `count(*)` on `platform` == `count(*)` on `ai`.
2. **Hash/custody integrity:** re-run the custody chain recomputation on `platform` and confirm
   it matches the stored digests (append-only triggers re-enabled). Any mismatch = abort.
3. **FK integrity:** `SET CONSTRAINTS ALL IMMEDIATE`; run a full FK-violation scan
   (`pg_constraint` × `NOT VALID` re-check) — must be 0.
4. **Schema-version ledger:** `platform.public.schema_version` reflects all applied migrations
   including the legacy import row.
5. **Zero-caller proof on `ai`** (§6) — all five queries return 0.

### 7.5 Phase 4 — Cutover (through Temporal/n8n/Coolify)

1. **Drain writers to `ai`:** stop the Agno runtime / n8n workflows / Temporal workers that
   write to `ai` (Coolify: stop `agentos-api` and any ingest workers; n8n: deactivate
   ingest workflows; Temporal: pause/terminate ingest workflows).
2. **Flip the default:** change `server/core/url.py:22` default `ai`→`platform`; update `.env`
   (`DB_DATABASE=platform`, `DB_USER=platform_runtime` or the canonical runtime user);
   update `deploy/compose.yaml`, `deploy/data-pg.yaml`, `deploy/exec.yaml`,
   `scripts/railway/up.sh` defaults `ai`→`platform`.
3. **Deploy** via Coolify (watch_paths scoped per app — see AGENTS.md gotcha). Redeploy
   `agentos-api` and ingest workers with the new env.
4. **Re-point `get_agno_db()` / `get_postgres_db()`** to the canonical DB (session.py) — verify
   the Agno operational store now lands in `platform`.
5. **Live acceptance:** run the integration suite (`uv run pytest -m integration`) against
   `platform`; confirm a live ingest writes to `platform` and reads back.

### 7.6 Phase 5 — Park `ai` read-only (no delete)

1. `REVOKE CONNECT ON DATABASE ai FROM PUBLIC;` and from all app roles except a single
   read-only auditor role.
2. `ALTER DATABASE ai WITH ALLOW_CONNECTIONS false;` (or set `default_transaction_read_only=on`
   for the auditor role).
3. Keep the snapshot archive (§7.1) as the rollback source. **Never delete `ai`** until the
   owner explicitly authorizes it after a sustained (e.g. 30-day) clean run.

### 7.7 Rollback / Abort (without delete)

- **Abort mid-phase:** stop the copy and roll back its transaction; `ai` remains untouched. No
  automatic DROP/DELETE/TRUNCATE cleanup path is authorized. Any residual target object is
  quarantined or handled by a later forward migration after inspection.
- **Rollback after cutover:** restore the §7.1 snapshot into a fresh DB, flip the default back
  to `ai`, redeploy. The `consolidation_checkpoint` table makes re-run idempotent.

---

## 8. Cutover Order (Temporal / n8n / Coolify)

1. **Freeze** (Phase 0) — snapshot `ai`.
2. **Prepare** `platform` (Phase 1) — extensions, roles, pending migrations.
3. **Copy** (Phase 2) + **verify** (Phase 3) — no cutover yet.
4. **Drain** — stop n8n ingest workflows, pause Temporal ingest workflows, stop Coolify
   `agentos-api` + ingest workers (writers to `ai`).
5. **Zero-caller proof** on `ai` (§6) — must be 0.
6. **Flip defaults + deploy** (Phase 4) — Coolify redeploy with `DB_DATABASE=platform`.
7. **Live acceptance** — integration tests + live ingest to `platform`.
8. **Park** `ai` (Phase 5) — read-only, snapshot retained.

---

## 9. Migration-Chain Reachability: 0045 → 0046 → 0047 → 0048

- **0045** (`context_fingerprint_semantics.sql`, working-tree modified) is now a **guarded
  supersession marker no-op**: it requires `current_database()='platform'`, requires the 0036
  relations/columns, and **fails** if abandoned-draft objects (`context.hash_kind`,
  `context.hash_canon`, `context.receipt_kind`, `context.custody_chain`) or legacy
  `hash_receipt` columns (`kind`/`canon`) exist. Body is `BEGIN/COMMIT` around only the DO
  guard. **Reachable** on `platform` as long as the abandoned-draft objects are absent (they
  are — `platform` has none of them). Historical broken draft preserved at
  `to_be_deleted/sql/0045_context_fingerprint_semantics.broken-historical-20260829.sql`.
- **0046** (`agno_app_role.sql`) targets database `ai` and is preserved as immutable historical
  state. **Never edit or retarget it.** If the runtime role still needs canonical-target grants,
  add them in a later numbered forward migration after the `agno_app` versus
  `platform_runtime` decision is settled and independently reviewed.
- **0047** (`content_chunk_and_context_thread_foundation.sql`) runs only in db `platform`
  (guard), requires 0036 relations + roles `platform_admin`/`platform_runtime`/`context_owner`
  + timeline roles, and creates the chunk/thread/relative-time/review tables. **Reachable** on
  `platform` after 0036 (already applied) and after roles exist. It is additive and does not
  depend on 0045/0046.
- **0048** (`context_fingerprint_uiw_repair.sql`, untracked new) runs only in db `platform`,
  requires 0036 relations + roles + membership, and is the **governed fix-forward** for the
  context-fingerprint vocabulary (relabels hash kinds, rewrites guard functions, re-grants).
  **Reachable** on `platform` after 0036. It is independent of 0045/0046/0047.

**Reachability correction:** do not represent `0046` as retargetable. It is a historical
old-database migration. Canonical consolidation proceeds through new forward migrations;
`0049` adds the platform-only proof foundation without replaying or editing `0046`.

---

## 10. Tests and Live Acceptance

- **Unit/contract:** `uv run pytest -q` (fast smoke).
- **Integration (mandatory, live services):** `uv run pytest -m integration` against `platform`.
- **Implemented foundation tests:** `tests/test_0049_ai_platform_consolidation_foundation.py`
  covers forward-only guards, role safety, UPDATE/DELETE/TRUNCATE immutability, exact receipt and
  snapshot binding, wrong-kind/unbound/stale-receipt rejection, deterministic FK/cycle/partition
  ordering, adversarial multi-format/nested-dotenv caller scanning, authenticated cross-database
  snapshot/fence evidence with wrong-target/cluster/signature rejection,
  PostgreSQL 18 application, and complete rollback. Current non-PG result is 9/9; current-code PG18
  rerun remains pending the disposable service credential and must pass before merge/deploy.
- **Still required with the future mutation-capable loader:** per-table live parity, custody-chain
  recomputation, full FK validation, and sustained zero-caller integration proof. Those are cutover
  acceptance tests, not claims made by this foundation slice.
- **Live acceptance:** a real ingest writes to `platform` and reads back; `get_agno_db()`
  operational store lands in `platform`; `public.schema_version` reflects the full chain.

---

## 11. Owner Decisions Required (flagged)

1. **Extensions on `platform`** — install postgis/vector/pg_duckdb/pg_trgm/unaccent/btree_*/
   citext/hstore/ltree/fuzzystrmatch on the canonical DB (§7.2.1). Recommend: yes.
2. **`schema_version` shape reconciliation** (§7.2.3). Recommend: keep `platform`'s `id`-shaped
   ledger as canonical; record `ai` history as one `0000_ai_legacy_import` row.
3. **Runtime role** — `agno_app` vs `platform_runtime` as the canonical LOGIN (§9). Recommend:
   `platform_runtime`.
4. **Runtime grant forward migration** — decide whether any `agno_app` grant remains necessary;
   if so, create a new numbered forward migration. Never edit `0046`.
5. **Park window** — how long `ai` stays read-only before any deletion is considered (§7.6).
   Recommend: 30 days clean run; never auto-delete.
6. **`ai_test_ingest` / `casebible` / `traceiq`** — out of scope; confirm they are not to be
   consolidated. Recommend: leave untouched.

---

## 12. Explicitly Out of Scope (per owner ruling)

- **No canonical redaction** — do not propose redaction as part of consolidation.
- **No SQLite migration** — do not propose SQLite as a target.
- **Retained source XML is the SBV migration authority** — the SBV (Go) migration must be
  driven from the retained source XML, not from any derived store.

---

## 13. Implementation Handoff (for a separate worker)

1. Read this packet fully; it is self-contained.
2. Execute Phase 0 (snapshot) → Phase 1 (prepare) → Phase 2 (copy) → Phase 3 (verify) →
   Phase 4 (cutover) → Phase 5 (park), in order.
3. Preserve 0046 unchanged; use 0049 and later numbered forward migrations only.
4. Use the `consolidation_checkpoint` table for idempotency.
5. Never delete `ai`; park it read-only with the snapshot retained.
6. Run the §10 test suite and live acceptance before declaring done.
