# Live-DB Diff & Migration — Forensic-Evidence Database

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Diff baseline = `live-introspection/` (captured over Tailscale from ovh3-data, 2026-06-30).
> Target = `RECONCILED_SCHEMA.sql`. Migration artifact = `migrations/0005_forensic_reconciliation.sql`.
> **Paper-only. Nothing in this report connected to or executed against any database.**

---

## 1. Summary verdict — ADDITIVE / LOW-RISK

The migration is **additive and low-risk**. The live `ai` DB is at an early "spine" stage: the
evidence/analysis/public security boundary already exists, plus exactly **two** forensic tables
with data-shape (`evidence.evidence_hash`, `analysis.normalized_record`) and three public
operational tables (`agent_run`, `approval_request`, `transcript_insight`). Everything else in the
93-table target is **greenfield** (cite: `PG_live_summary.txt` lines 19–45 — no `evidence.source`,
no `analysis.entity`, no `analysis.timeline_event`, etc.).

- **No destructive operations.** The two live forensic tables are touched only by `ADD COLUMN IF
  NOT EXISTS` / additive `ADD CONSTRAINT … NOT VALID`. No column drop, no retype, no data move.
- The design's "competing/deprecated" tables (`analysis.provenance`, `evidence.ingestion_run`,
  D3 `raw_timeline_segment`/`timeline_waypoint`) **never existed live** → there is nothing to drop.
- **Two real corrective items** must land first (see §3): install 4 drifted contrib extensions;
  apply the sql/0004 custom types with the `disclosure_tier` collision fix.
- **One execution hazard, not a data hazard:** STEP 1 contains `CREATE TYPE` / `ALTER TYPE … ADD
  VALUE`, which cannot be wrapped in one transaction and whose new enum values cannot be used in the
  same txn — run STEP 0+1 in autocommit before the table DDL (handled in the migration's structure).

Verdict: **safe to apply on the (near-empty) live volume, pending owner sign-off**, run by hand
(not via docker-entrypoint, which only fires on an empty pgdata).

---

## 2. PostgreSQL object-by-object diff

Status legend: **EXISTS-MATCHES** (live = target, no action) · **EXISTS-NEEDS-ALTER** (live present,
additive change) · **CREATE** (greenfield) · **CONFLICT** (incompatible — needs decision).

### 2a. Extensions (cite: `PG_live_summary.txt` 8–18)

| Extension | Live | Target | Status | Action |
|---|---|---|---|---|
| pgcrypto | 1.4 | required | EXISTS-MATCHES | re-assert (no-op) |
| pg_trgm | 1.6 | required | EXISTS-MATCHES | re-assert |
| btree_gin | 1.3 | required | EXISTS-MATCHES | re-assert |
| btree_gist | 1.8 | required | EXISTS-MATCHES | re-assert |
| unaccent | 1.1 | required | EXISTS-MATCHES | re-assert |
| vector (pgvector) | 0.8.2 | legacy/required | EXISTS-MATCHES | re-assert (vectors live in Milvus) |
| postgis | 3.6.4 | required (geo_point) | EXISTS-MATCHES | guarded re-assert |
| pg_duckdb | 1.1.0 | required (analytics) | EXISTS-MATCHES | guarded re-assert |
| pg_stat_statements | 1.12 | ops | EXISTS-MATCHES | (image preload; not in migration) |
| plpgsql | 1.0 | required | EXISTS-MATCHES | built-in |
| **fuzzystrmatch** | **ABSENT** | required (dmetaphone/levenshtein) | **CREATE** | **`CREATE EXTENSION` (corrective A)** |
| **citext** | **ABSENT** | required (name/email/handle cols) | **CREATE** | **`CREATE EXTENSION` (corrective A)** |
| **ltree** | **ABSENT** | required (`file_node.node_path`) | **CREATE** | **`CREATE EXTENSION` (corrective A)** |
| **hstore** | **ABSENT** | declared (attr bags) | **CREATE** | **`CREATE EXTENSION` (corrective A)** |
| pg_textsearch / BM25 | ABSENT | STAGED-not-baked | n/a | intentionally skipped (Milvus owns BM25, ADR-0027) |

The 4 missing are standard contrib; sql/0001 asserts they "ship with the base image, no apt."
**Availability flag:** I cannot confirm from disk that the `agno-postgres:18-duckdb` image actually
carries the contrib `.control` files — if any `CREATE EXTENSION` errors with "could not open extension
control file," STOP and rebuild the image (fuzzystrmatch/citext are load-bearing: `entity.display_name
citext`, `entity_alias.alias_dmeta = dmetaphone(...)`).

### 2b. Custom types (cite: `PG_live_types.txt` — only the 11 baseline/PostGIS/Agno types live; the introspection enum query errored, but the summary confirms 0004 absent)

| Type | Kind | Live | Target | Status | Action |
|---|---|---|---|---|---|
| entity_type | enum | ABSENT | 0004 + 14 ADD VALUEs | **CREATE + ALTER** | create from 0004, then `ALTER TYPE … ADD VALUE` (phone/email/handle/device/account/vehicle/address/court/attorney/school/doctor/institution/platform/ai_system) |
| event_type | enum | ABSENT | 0004 + 3 ADD VALUEs | **CREATE + ALTER** | create, then ADD VALUE presence/communication/observation |
| temporal_class | enum | ABSENT | 0004 | CREATE | inline from 0004 |
| mcl_factor | enum | ABSENT | 0004 | CREATE | inline from 0004 |
| source_system | enum | ABSENT | 0004 | CREATE | inline from 0004 |
| match_method | enum | ABSENT | 0004 | CREATE | inline from 0004 |
| confidence | domain | ABSENT | 0004 | CREATE | inline from 0004 |
| canonical_id | domain | ABSENT | 0004 | CREATE | inline from 0004 |
| geo_point | domain | ABSENT | 0004 | CREATE | inline from 0004 (postgis-guarded; postgis IS live) |
| source_ref | composite | ABSENT | 0004 | CREATE | inline from 0004 |
| **disclosure_tier** | enum | ABSENT (0004 never applied) | **renamed→sensitivity_tier** | **CONFLICT→FIX** | see §3b — create `sensitivity_tier`, never create the colliding enum name |
| sensitivity_tier | enum | ABSENT | new (the renamed access enum) | CREATE | `('public','restricted','sealed')` |
| evidence_tier, assertion_type, precision_class, strength_class, review_state, conduct_party, cycle_phase, disclosure_horizon, temporal_relation, anchor_kind, assertion_source, geocode_provider, pattern_match_type, category_polarity, detection_method | enum | ABSENT | new shared/domain enums | CREATE (15) | inline guarded `CREATE TYPE` |

### 2c. Schemas (cite: `PG_live_summary.txt` 2–7)

| Schema | Live | Status |
|---|---|---|
| evidence | yes | EXISTS-MATCHES (re-assert `CREATE SCHEMA IF NOT EXISTS`) |
| analysis | yes | EXISTS-MATCHES |
| public | yes | EXISTS-MATCHES |
| ai (Agno) | yes | untouched (not in design scope) |
| duckdb (pg_duckdb) | yes | untouched |

### 2d. Tables — 93 reconciled objects

**EXISTS-NEEDS-ALTER (2):**

| Table | Live as-built (cite `PG_live_schema.sql`) | Target adds | Status |
|---|---|---|---|
| `evidence.evidence_hash` | id, source_ref(text), algo, digest(bytea), hashed_at, blob_key, meta(jsonb) + CHECK(algo<>'sha256' OR octet_length(digest)=32) + `idx_evidence_hash_digest` (lines 731–740, 1361) | **+8 cols** `level`('H1' default,CHECK H1/H2/H3), `source_id`→evidence.source, `file_node_id`→evidence.file_node, `md5_prefilter`, `record_locator`, `member_hash_ids uuid[]`, `canon_version`, `computed_by`; **+constraint** `evidence_hash_subject_ck … NOT VALID`; **+3 idx** (level_source, filenode, meta gin). Immutability trigger intentionally deferred (TODO, blocks legacy backfill). | EXISTS-NEEDS-ALTER (purely additive) |
| `analysis.normalized_record` | id, artifact_id→evidence.evidence_hash, record_type(CHECK msg/call/event/media), source, conversation_id(**text**), role, participants, content, occurred_at, knowledge_time, disclosure_tier(**text** CHECK contemporaneous/hindsight/discovered), attrs, created_at + 3 idx (lines 708–724, 1340–1354) | **+7 cols** `conversation_ref uuid`→analysis.conversation, `ts_precision`, `sensitivity_tier`, `data_tier`, `review_status`, `safe_for_legal_use`, `provenance_id`→processing_run; **+FK** fk_normrec_conv; **+3 idx**. **`disclosure_tier` TEXT column kept verbatim** (the survivor — see §3b). New `conversation_ref uuid` coexists with the as-built `conversation_id text`; no rename. | EXISTS-NEEDS-ALTER (purely additive) |

**CREATE — greenfield (91):** every other reconciled table. By schema:

- **evidence (8 CREATE):** source, file_node, custody_event, gps_point, raw_visit, raw_activity, raw_path, raw_trip.
- **analysis (72 CREATE):** custody_factor; processing_run, tool_call_ledger, artifact_registry, lineage_edge, score_band_config, score; entity, person, organization, phone, email, handle, device, account, vehicle, entity_alias, entity_mention, entity_resolution, resolution_evidence, entity_merge_event, id_xref; conversation, message, message_participant, attachment, call_log, relational_classification; location, gps_track, stay_point, geofence, home_base, location_assertion, location_contradiction, geocode_request, geocode_result, geocode_resolution, geocode_audit; timeline_event, event_source_record, time_assertion, temporal_anchor, relative_rule, event_ordering, waypoint_device_split; finding, finding_version; detection_pattern_set, behavior_category, detection_pattern, pattern_lexicon, behavior_category_mcl, pattern_finding; legal_issue, legal_issue_factor, evidence_item, factor_citation, legal_timeline_event, evidence_task, task_event, task_revision, task_person, task_legal_link, task_dependency, discovery_request, discovery_request_revision, completion_evidence, export_package, export_item; review_task, review_decision, redaction, export.
- **public (11 CREATE):** prompt_registry, model_version, schema_version, ontology_version, classification_version, memory_items, decision_log, session_summaries, open_questions, decision_precedent, change_log.

**Tally: 2 EXISTS-NEEDS-ALTER + 91 CREATE = 93.** Plus 3 views (CREATE OR REPLACE): `public.vw_event_evidence_package`, `analysis.vw_court_export`, `analysis.vw_open_tasks`.

**Live tables NOT in the design (left untouched, not dropped):** `ai.agno_*` + `ai.*_contents` (Agno-managed), `public.spatial_ref_sys` (PostGIS), `public.agent_run`/`approval_request`/`transcript_insight` (live operational — the D8 memory tables land alongside, no collision), `duckdb.*` (pg_duckdb internal). **No CONFLICT** among these.

---

## 3. The two corrective items (must land first)

### 3a. Install the 4 drifted contrib extensions
`citext`, `ltree`, `hstore`, `fuzzystrmatch` are declared in `sql/0001` but **NOT live** (cite:
`LIVE_INTROSPECTION_SUMMARY.md` line 12; absent from `PG_live_summary.txt` 8–18). Migration STEP 0:
```sql
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS ltree;
CREATE EXTENSION IF NOT EXISTS hstore;
```
All standard contrib. **Flag:** confirm the contrib package is present in the pg_duckdb base image; if
`CREATE EXTENSION` fails on a control-file error, rebuild the image before proceeding (these back
entity-resolution `citext`/`dmetaphone` columns and `file_node.node_path ltree`).

### 3b. Apply sql/0004 custom types WITH the disclosure_tier fix
`sql/0004` was never applied live (cite: `LIVE_INTROSPECTION_SUMMARY.md` line 13). The migration bakes
0004 inline (idempotent) and resolves the name collision:

- The 0004 enum `disclosure_tier ('public','restricted','sealed')` is an **access/sensitivity**
  classification. It collides by name with the **as-built** `analysis.normalized_record.disclosure_tier`
  **TEXT** column (`contemporaneous|hindsight|discovered` = a **knowledge-horizon**, from 0003 — verified
  live: `normalized_record_disclosure_tier_check`, `PG_live_schema.sql` 719/722).
- **Fix:** rename the orphan 0004 access enum to **`sensitivity_tier`**; since 0004 never ran live, the
  migration simply creates `sensitivity_tier` fresh and never creates the colliding name. The 0003
  bitemporal TEXT column **stays exactly as-built** (untouched, non-destructive).
- New tables use the separate `disclosure_horizon` enum for the knowledge-time concept (same vocabulary).
- **TODO(human)** preserved: decide once whether to later rename the as-built column
  `disclosure_tier`→`knowledge_horizon` + retype to `disclosure_horizon` (a coordinated records-domain
  migration). Until then the TEXT column is canonical.

---

## 4. Ordered, idempotent migration

Written to **`migrations/0005_forensic_reconciliation.sql`** (base dir). Order: extensions → types
(+ disclosure_tier fix, + ADD VALUE pre-step) → schemas → guard functions → reference tables →
`evidence.*` → `public.*` registries → `analysis.*` (provenance → entities → messages → geo → events →
finding → behavioral → legal/tasks/export → review) → `public.*` memory/audit → views. Every object is
guarded (`IF NOT EXISTS` / `DO $$ … duplicate_object` / `DROP TRIGGER IF EXISTS` before each
`CREATE TRIGGER`). All 8 `TODO(human):` markers from source preserved as comments. No destructive DROPs.

**Execution contract (critical):** run **STEP 0 + STEP 1 in autocommit FIRST** (they contain
`CREATE TYPE` / `ALTER TYPE … ADD VALUE`, which can't share a txn and whose new values can't be used in
the adding txn). STEP 2–16 may then run, optionally inside one `BEGIN; … COMMIT;`.

The fenced block below is the head of the migration (STEP 0 + the corrective type fix); the full,
runnable script is the file:

```sql
-- STEP 0 — EXTENSIONS (corrective A: install the 4 drifted contrib extensions)
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS btree_gin;
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;   -- [DRIFT → INSTALL]
CREATE EXTENSION IF NOT EXISTS citext;          -- [DRIFT → INSTALL]
CREATE EXTENSION IF NOT EXISTS ltree;           -- [DRIFT → INSTALL]
CREATE EXTENSION IF NOT EXISTS hstore;          -- [DRIFT → INSTALL]
DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS postgis;  EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'postgis skipped'; END $$;
DO $$ BEGIN CREATE EXTENSION IF NOT EXISTS pg_duckdb; EXCEPTION WHEN OTHERS THEN RAISE NOTICE 'pg_duckdb skipped'; END $$;

-- STEP 1 — SCHEMAS + TYPES (corrective B: 0004 inline + disclosure_tier fix) — RUN IN AUTOCOMMIT
CREATE SCHEMA IF NOT EXISTS evidence;
CREATE SCHEMA IF NOT EXISTS analysis;
-- 0004 base types (idempotent): entity_type, event_type, temporal_class, mcl_factor,
--   source_system, match_method (enums); confidence, canonical_id, geo_point (domains);
--   source_ref (composite) — see file STEP 1.0.
-- disclosure_tier collision FIX:
DO $$ BEGIN ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;
EXCEPTION WHEN undefined_object THEN NULL; WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN CREATE TYPE sensitivity_tier AS ENUM ('public','restricted','sealed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
-- + 15 new shared/domain enums (evidence_tier, assertion_type, precision_class, strength_class,
--   review_state, conduct_party, cycle_phase, disclosure_horizon, temporal_relation, anchor_kind,
--   assertion_source, geocode_provider, pattern_match_type, category_polarity, detection_method).
-- ADD VALUE pre-step (NOT usable in same txn): entity_type += phone/email/handle/device/account/
--   vehicle/address/court/attorney/school/doctor/institution/platform/ai_system; event_type +=
--   presence/communication/observation.

-- STEP 2..16 (transaction-safe): guard fns → reference → evidence.* → public registries →
--   analysis.* → public memory/audit → views. (Full DDL in the file.)
```

---

## 5. Per-store migration

### Milvus (cite: `MILVUS_live.txt`) — additive
Live collections (4, keep): `casebible_ai_conversations`, `agent_session_memory`,
`ms_scratchpad_31bc129d`, `ms_matts_f436780d`. **None of the design's forensic collections exist.**
**Create (additive, when the embedding pipeline lands)** the design's forensic collections — typical
set: `forensic_messages`, `forensic_ocr_text`, `forensic_event_summaries`, `forensic_claims`,
`forensic_pattern_findings`, `forensic_legal_issue`, `forensic_multimodal`. Each: PK = the PG row's
`*_embedding_ref`/`embedding_ref` string (e.g. `message.body_embedding_ref`,
`attachment.embedding_ref`); store `group_id`/`case_id` + `data_tier` + `safe_for_legal_use` scalar
fields for filtered search; vectors NEVER stored in PG (ADR-0027). No collection drops. Dimensions/metric
**TODO(human):** pin to the chosen embedder via `public.model_version` before creating.

### Neo4j / Semantica (cite: `NEO4J_live.txt`) — ready, no data
Live = bare Graphiti (labels `Saga/Episodic/Entity/Community`; `nodes = 0`). **No Semantica entity layer
deployed.** No migration object to create on disk; readiness = the PG `analysis.entity` + `analysis.id_xref`
crosswalk (`source_system='neo4j'`) is the bridge. Projecting entities/relationships into Neo4j is a
pipeline task, not DDL — defer until the entity-resolution lane produces approved entities. No destructive
action (0 nodes).

### SurrealDB (cite: `SURREAL_live.txt`) — defer, no action
Namespaces `agno` + `main` exist; `main:main` has **zero tables/functions/analyzers** (completely empty;
ADR-0024 ratified-but-unused). **No action this migration.** When activated, it is the downstream analysis
sink fed from PG via `id_xref` (`source_system='surrealdb'`); GeoJSON projections of `geo_point` go here
(Surreal lacks a spatial index — heavy geo stays in PG/PostGIS).

---

## 6. Acceptance checklist — runnable read-only verification (post-migration)

All read-only. Run from the app tier over Tailscale or `docker exec` into `agentos-db`.

```bash
# --- PostgreSQL (psql -U ai -d ai) ---
\dx                              # EXPECT: + citext, ltree, hstore, fuzzystrmatch (added) alongside the 10 live
\dn                              # EXPECT: ai, analysis, duckdb, evidence, public (unchanged)
\dT public.*                     # EXPECT: sensitivity_tier present; NO type named disclosure_tier
SELECT typname FROM pg_type WHERE typname IN
  ('entity_type','event_type','mcl_factor','confidence','geo_point','source_ref',
   'sensitivity_tier','disclosure_horizon','evidence_tier','assertion_type');   -- EXPECT: all 10 rows
SELECT enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
  WHERE t.typname='entity_type';                 # EXPECT: 6 base + 14 added = 20 labels (incl. phone, ai_system)
\dt evidence.*                   # EXPECT: evidence_hash + source, file_node, custody_event, gps_point, raw_visit, raw_activity, raw_path, raw_trip (9)
\dt analysis.*                   # EXPECT: normalized_record + 72 new = 73 tables
\d evidence.evidence_hash        # EXPECT: original 7 cols + level, source_id, file_node_id, md5_prefilter, record_locator, member_hash_ids, canon_version, computed_by
\d analysis.normalized_record    # EXPECT: original 13 cols + conversation_ref, ts_precision, sensitivity_tier, data_tier, review_status, safe_for_legal_use, provenance_id; disclosure_tier still TEXT
SELECT count(*) FROM analysis.custody_factor;    # EXPECT: 12 (MCL a–l seeded)
\dv analysis.* public.*          # EXPECT: vw_court_export, vw_open_tasks, vw_event_evidence_package
SELECT count(*) FROM pg_tables WHERE schemaname IN ('evidence','analysis','public'); # sanity

# --- Milvus (pymilvus) ---  EXPECT: original 4 unchanged (forensic collections only after pipeline build)
python -c "from pymilvus import MilvusClient; print(MilvusClient(uri='...').list_collections())"

# --- Neo4j (cypher-shell) ---  EXPECT: Saga/Episodic/Entity/Community; nodes still 0 (no DDL change)
CALL db.labels() YIELD label RETURN label;
MATCH (n) RETURN count(n);

# --- SurrealDB ---  EXPECT: tables: {} (still empty — deferred)
INFO FOR DB;
```

---

## 7. Risk / rollback

- **Risk profile: low.** Additive DDL on a near-empty volume; the only live forensic rows are in two
  tables touched solely by `ADD COLUMN IF NOT EXISTS` (new cols are nullable or have defaults — no rewrite
  risk on large tables, and these tables are small/early-stage).
- **Idempotent + re-runnable:** safe to re-run after a partial failure; guards make every object a no-op
  on the second pass.
- **Rollback = drop the new objects.** Because the migration only adds, rollback is bounded: `DROP SCHEMA
  evidence CASCADE` / drop the new `analysis.*` + `public.*` tables and the new types, then on the two
  live tables `ALTER TABLE … DROP COLUMN IF EXISTS …` for the additive columns (and `DROP CONSTRAINT
  evidence_hash_subject_ck`). The as-built columns/constraints/indexes are never altered, so the live
  spine returns to its captured state. (Per project rule: prefer never-delete; for a real rollback, move
  data out first — but on this empty layer there is no data to preserve.)
- **`disclosure_tier` safety:** the bitemporal TEXT column is never touched → no risk to the 0003 spine.
- **Init-only-on-empty-volume caveat:** sql/0004 + this migration do **not** auto-apply via
  `/docker-entrypoint-initdb.d` (that fires only on an empty pgdata; the live volume already has 0001–0003).
  **Run STEP 0+1 by hand in autocommit, then STEP 2–16.** Do not rely on the container entrypoint.
- **Extension availability** is the one external dependency that could block (image must carry contrib
  control files) — verify with the first four `CREATE EXTENSION` statements before running the rest.

**Safe to apply pending owner sign-off:** yes — additive, idempotent, reversible, no destructive DROPs.
