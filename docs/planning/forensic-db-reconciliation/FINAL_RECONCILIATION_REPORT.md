# Forensic-Evidence DB — Final Reconciliation Report

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> **Status: DRAFT / paper-only.** Consolidates the per-domain reconciliations (D1–D8), the
> store reconciliations (S1 Milvus / S2 Neo4j / S3 SurrealDB), the cross-domain integrity
> review, the court-safety review, and the deferred-corrections addendum into one deployable
> draft schema (`RECONCILED_SCHEMA.sql`) + this report. **Nothing here has been applied or
> diffed against the running DB.** It HAS been reconciled against the captured live
> introspection (`live-introspection/`). The acceptance checklist (§9) gates any deploy.

---

## 1. Executive summary

The deployed forensic layer is at an **early spine stage**: the `evidence`/`analysis`/`public`
security boundary exists, the custody-hash table (`evidence.evidence_hash`) and the bitemporal
spine (`analysis.normalized_record`) exist, and everything else is **greenfield**. Live
introspection (2026-06-30, ovh3-data) confirms only migrations `0001`+`0002`+`0003` are applied;
`0004` custom types are **not** applied and four extensions (`citext`, `ltree`, `hstore`,
`fuzzystrmatch`) are **declared but not installed**. The reconciled schema therefore lands as a
**mostly-additive, low-risk migration** — not a destructive alter.

The reconciliation's job was to fold three layers of prior work — the 91k-word paper design, the
small-but-deliberate as-built DDL, and a large corpus of heavily-iterated prior-iteration schemas
(Salem Forensic Trinity / TraceIQ / dial-stack / salem_v3 / Zep / Semantica) plus the behavioral
ontology — into ONE coherent model that obeys the as-built law. The headline outcome: **93 tables
created** (8 `evidence`, 74 `analysis`, 11 `public`), **2 as-built tables extended additively**
(`evidence.evidence_hash`, `analysis.normalized_record`), **3 legacy as-built `public` tables
retained** (never deleted), alongside the pre-existing Agno-managed tables (live in schema `ai`).
3 court-export views. Every paper "parallel top-level schema" (`core/raw/geo/legal/provenance/
multimodal/timeline/entity/evidence_plan`) was **re-homed** as a table-name sub-domain prefix
inside the three real schemas. The `0004` custom types are reused, never redefined.

### The 4-resource data-tier topology (independently restartable)

| # | Resource | Role | Notes |
|---|---|---|---|
| 1 | **PostgreSQL 18 + PostGIS + embedded DuckDB (`pg_duckdb`)** = ONE unified resource | System of record: custody, normalized records, entities, geo, timeline, behavioral, legal, work-product ledger, audit spine | PostGIS + DuckDB are **embedded**, never standalone. This file targets resource #1 only. |
| 2 | **Milvus** (3.0, self-hosted + WoodPecker + Attu) | Primary semantic + hybrid dense+sparse/**BM25** retrieval (ADR-0027); disposable index, rebuildable from PG | Vectors live here; PG carries `embedding_ref` only. |
| 3 | **Neo4j + Graphiti (+ Semantica)** | Relationship-shape + identity keys + bitemporal memory; `project(PostgreSQL)` | Append-only; rebuildable from PG. Semantica not yet deployed. |
| 4 | **SurrealDB** | Consolidated-analysis / orchestration sink (ADR-0024) | **DEFER** — ratified, not deployed (Phase D). |

A crash in any one resource must never tear down the others. Cross-store links are **by id only**
(reuse `0004.source_system`/`match_method`/`canonical_id`/`source_ref`); ADR-0032 dropped FDW.

### Extension contract (corrected; truth = Dockerfile + sql/0001 + live drift)

**Live & enabled** (verified): `pg_duckdb 1.1.0` (embedded DuckDB + R2/S3 httpfs, in
`shared_preload_libraries`), `postgis 3.6.4`, `pgvector 0.8.2` (**legacy/migration-only** —
vectors → Milvus, ADR-0027), `pg_stat_statements`, `pgcrypto` (SHA-256 custody), `pg_trgm`,
`btree_gin`, `btree_gist` (bitemporal `EXCLUDE`), `unaccent`. Native PG18 `uuidv7()`.
**LIVE DRIFT — declared in 0001 but NOT installed (migration must `CREATE EXTENSION`):**
`citext`, `ltree`, `hstore`, `fuzzystrmatch`. **BM25:** `pg_textsearch` is **STAGED-not-baked**
(no PGDG package) and correctly absent — Milvus owns primary BM25; PG keeps `tsvector`+`pg_trgm`
for cheap local lookups; `pg_textsearch` stays an optional staged PG-local fallback (do not bake
preemptively). Entity resolution = `fuzzystrmatch` (`dmetaphone`/`levenshtein`) + `pg_trgm` +
`citext`. Bitemporal no-overlap = `btree_gist EXCLUDE` on `tstzrange`. Custody =
`pgcrypto.digest(...,'sha256')`. **sha256 = canonical evidence identity; md5 = pre-filter only.**

---

## 2. Table-by-table reconciliation matrix

Status legend: **new** = created here · **adopt** = carried ~as-is · **adapt** = carried with change ·
**merge** = folded from several sources · **split** = one source → several · **extend** = additive
ALTER of an as-built table · **deprecate** = dropped/retired. Court/HITL column shorthand:
SFL = `safe_for_legal_use` + approved-gate CHECK · AO = append-only (trigger) · WO = write-once.

### evidence schema (raw/source; agents read-only)

| Table | Schema | Status | Source | Court/HITL notes |
|---|---|---|---|---|
| `evidence.evidence_hash` | evidence | **extend** | as-built 0002/0003 + D1 (H1/H2/H3 level, source/file_node FK, Merkle members) | Custody anchor; 32B sha256 CHECK preserved; immutability trigger deferred until backfill (TODO). |
| `evidence.source` | evidence | **merge/new** | paper `raw_object` ⊕ E2 `messaging_documents` ⊕ TraceIQ `data_source` | WO core columns (trigger); only lifecycle status mutable; sha256 UNIQUE dedupe. |
| `evidence.file_node` | evidence | **adopt** | paper `custody.file_node` + E2 attachment kinds | AO; recursive `ltree` decomposition. |
| `evidence.custody_event` | evidence | **adapt** | paper `audit_log` custody slice | AO + pgcrypto sha256 per-source hash chain. |
| `evidence.gps_point` | evidence | **adopt** | paper `geo.gps_point` + E3 | Raw fix; `device_id` is SOFT uuid (no FK — A7). |
| `evidence.raw_visit` / `raw_activity` / `raw_path` / `raw_trip` | evidence | **adopt** (D5 canonical) | E3 §B Google-Timeline objects | A1 fix: D5's four typed tables WIN; D3's `raw_timeline_segment`/`timeline_waypoint` **deprecated**. Multi-device split removed from raw_path → analysis. Order by sequence, never timestamp. |

### analysis schema — records / messages (D2)

| Table | Status | Source | Court/HITL notes |
|---|---|---|---|
| `analysis.normalized_record` | **extend** | as-built 0003 | Universal parser-emission spine; +`conversation_ref`,`ts_precision`,`sensitivity_tier`,`data_tier`,`review_status`,`safe_for_legal_use`,`provenance_id`. `disclosure_tier` (knowledge-horizon TEXT CHECK) **unchanged**. |
| `analysis.conversation` | **merge** | E2 `messaging_conversations` + S1 generic | Thread grouping; FK → `evidence.evidence_hash`. |
| `analysis.message` | **merge → subtype** | E2 family-B + S1 + paper | PK-shares the spine; interpretive cols renamed `*_hint` (non-court-readable, review #3). |
| `analysis.message_participant` | **adopt** | E2 + paper | M:N; `conduct_party` for both-parties balance. |
| `analysis.attachment` | **merge** | E2 `messaging_attachments` + paper multimodal | OCR/transcript = extracted; vector → Milvus. |
| `analysis.call_log` | **adopt → subtype** | E2 sms_backup_parser | `record_type='call'`; blocked-call type 5/6. |
| `analysis.relational_classification` | **adopt** | paper §8.1 + `positive_behaviors.ttl` | Multi-label HITL; **SFL gate added** (review #2). Full-cycle / both-parties categories. |

### analysis schema — entities & identity resolution (D4)

| Table | Status | Source | Court/HITL notes |
|---|---|---|---|
| `analysis.entity` (+ `person`/`organization`/`phone`/`email`/`handle`/`device`/`account`/`vehicle`) | **merge** | paper §3.1 + E2 `entities` + salem/Zep | Supertype + shared-PK satellites; `entity_type` extended via ADD VALUE; `risk_level` deprecated off-entity → finding. |
| `analysis.entity_alias` | **adapt** | E2 `aliases[]` + Zep | `dmetaphone` blocking generated col. |
| `analysis.entity_mention` | **adopt** | E2 `entity_mentions` | AO; immutability-by-trigger keeps evidence-grade fixity in `analysis`. |
| `analysis.entity_resolution` | **adopt** | paper §3.2 + 0004 `match_method` | Supersedable via `sys_period`; one current per mention; HITL default. |
| `analysis.resolution_evidence` | **adopt** | paper + E2 polarity | AO supports/contradicts. |
| `analysis.entity_merge_event` | **adopt** | paper + MP merge log | AO, reversible. |
| `analysis.id_xref` | **merge (UNIFIED)** | A6 fix: **S1 pairwise** shape + D4 optional `canonical_entity_id` | ONE crosswalk for entity AND row↔vector links; reuses `source_system`/`match_method`/`source_ref`. D4's entity-only version dropped. |

### analysis schema — geo/location (D5), events/timeline (D3)

| Table | Status | Source | Court/HITL notes |
|---|---|---|---|
| `analysis.location` | **merge** | paper `geo.location` + E3 `location_key` + TraceIQ fuzzy | PostGIS-generated `geohash9` dedup; `sensitivity_tier` for privacy-fuzzed. |
| `analysis.gps_track` / `stay_point` / `geofence` / `home_base` | **adopt/adapt** | paper + TraceIQ | Tracks/fences use raw `geography(LineString|Polygon)` (geo_point is Point-only); HITL on inferred. |
| `analysis.location_assertion` / `location_contradiction` | **adopt/merge** | paper + normalized_geo_v5 | Polymorphic spatial link; **SFL gates added**; contradictions HITL-default. |
| `analysis.geocode_request` / `geocode_result` / `geocode_resolution` / `geocode_audit` | **merge/adopt** | normalized_geo_v5 (verbatim dual-provider) | `geocode_audit` AO; provider tie-break preserved. |
| `analysis.timeline_event` | **merge/adapt** | salem `Incident`/`Event` + TraceIQ `timeline_enriched` | Curated event spine; current valid-time is a cache of `time_assertion`. |
| `analysis.event_source_record` | **adapt** | E3 | A1 fix: now points at `normalized_record` + `evidence.source` + `raw_ref` jsonb (D3 raw tables gone). |
| `analysis.time_assertion` | **adopt** | paper §2/§5 | Bitemporal core; `btree_gist EXCLUDE (event_id, sys_period)` = exactly one current belief. |
| `analysis.temporal_anchor` / `relative_rule` / `event_ordering` | **adopt** | paper §3/§4 | `caused_hypothesis` never auto-promoted. |
| `analysis.waypoint_device_split` | **split** | E3 inference | A1 lane fix: inferred 100m split lives in `analysis`, references `evidence.raw_path`. |

### analysis schema — behavioral (D6), findings (NEW), legal/tasks/export (D7)

| Table | Status | Source | Court/HITL notes |
|---|---|---|---|
| `analysis.detection_pattern_set` / `detection_pattern` / `pattern_lexicon` / `behavior_category` / `behavior_category_mcl` | **merge/adapt** | E2 18-cat + E4 26-cat + `*.ttl` + seed-patterns.ts + detection_patterns.py | Config-as-DATA, versioned, append-only; dual-polarity; `sensitivity_tier` gates minor terms. |
| `analysis.pattern_finding` | **adapt** | E2 `messaging_behaviors` + S9 | Every row a HYPOTHESIS; **legal gate + attribution gate** (review #4); `bias_caution`/`authored_perspective` denormalized (review #6). |
| `analysis.finding` (+ `finding_version`) | **new** | A3 fix (paper §8.3 had no owner) | MINIMAL court-safe stub; SFL gate; FK target for pattern_finding + evidence_task. **TODO: flesh out.** |
| `analysis.custody_factor` | **adopt (seeded)** | E2 `mcl_factors` + 0004 `mcl_factor` | PK = enum; J=facilitation, K=domestic_violence (statutory-canonical, fixes J↔K). |
| `analysis.legal_issue` / `legal_issue_factor` | **adapt** | paper `legal.legal_issue` | Per-case issue map; weights are HITL policy inputs. |
| `analysis.evidence_item` | **merge** | E2 S1 court-prep ⊕ B custody | The court-export trip-wire (`evidence_item_safe_ck`); **confidence_tier↔confidence CHECK** (review #5). |
| `analysis.factor_citation` | **adopt** | E2 S1 (supports/contradicts + strength) | **SFL gate added** (review #5). |
| `analysis.legal_timeline_event` | **adopt** | E2 S1 | **SFL gate added** (review #5); distinct from raw geo timeline. |
| `analysis.evidence_task` + 8 satellites | **adapt** | paper §12 | Re-homed; private `*_t` enums → TEXT+CHECK / `review_state`; snapshot + status-log triggers; history AO. |
| `analysis.discovery_request` (+ revision) | **adopt** | paper §12.11 | DRAFT only, never auto-served; HITL-gated. |
| `analysis.export_package` / `export_item` | **adapt (new)** | paper + D1 custody | Signed reproducible packet. |

### analysis/public schema — provenance, scoring, review, memory, audit (D8)

| Table | Status | Source | Notes |
|---|---|---|---|
| `analysis.processing_run` | **merge** | paper `provenance.run` + `processing_runs` + `scoring_run` | A4/A8 fix: THE single run anchor; `evidence.ingestion_run` + `analysis.provenance` names dropped. |
| `analysis.tool_call_ledger` / `artifact_registry` / `lineage_edge` | **adopt/merge** | paper §09/§20 | AO ledgers; `assertion_type` enum lane typing. |
| `analysis.score` / `score_band_config` | **adopt** | paper §13 | Append-only bitemporal score; versioned bands kill the hard-coded 0.6 cliff. |
| `analysis.review_task` / `review_decision` | **merge** | paper §13 + §09 + S5 `pattern_approval_log` | Reviewer-of-record (human-only); AO decisions. |
| `analysis.redaction` / `analysis.export` | **adopt** | paper §09 | AO; non-destructive; signed manifest. |
| `public.prompt_registry` / `model_version` / `schema_version` / `ontology_version` / `classification_version` | **merge/adopt** | paper §09/§20 | Context registries; runs pin them by FK → reproducibility. |
| `public.memory_items` / `decision_log` / `session_summaries` / `open_questions` / `decision_precedent` | **adopt** | paper §20 + S7 | Operational memory; `tsvector`+`pg_trgm` recall; Graphiti mirror for non-sensitive only. |
| `public.change_log` | **merge** | paper `audit_log` + `change_log` | THE single AO sha256 hash-chained audit spine. |

### Retained / deprecated

| Object | Status | Note |
|---|---|---|
| `public.agent_run`, `public.approval_request` | **retain (legacy)** | Superseded by Agno `agno_approvals` (live in schema `ai`); never deleted. |
| `public.transcript_insight` | **retain** | ChatMiner output; as-built. |
| `0004` enum `disclosure_tier` (public/restricted/sealed) | **renamed → `sensitivity_tier`** | The bug fix (see §4). |
| D3 `evidence.raw_timeline_segment` / `evidence.timeline_waypoint` | **deprecate** | A1: D5's four typed raw tables win. |
| `evidence.ingestion_run` | **deprecate** | A8: folded into `analysis.processing_run` (`run_type='ingestion'`). |
| D3 `timestamp_certainty` enum, D3 `assertion_kind` enum, per-domain `precision_class` dups | **collapse** | A9: one `precision_class` + one `assertion_type` enum. |
| Per-platform flat staging tables (`sms_messages`, `facebook_messages`…) | **deprecate** | Folded into `message.platform_attrs`. |
| Engine-hardcoded regex | **deprecate** | E4 #5: patterns live in tables, not code. |

---

## 3. What changed — vs paper, vs as-built, vs prior iterations

**vs the paper design.** The paper invented ~10 parallel top-level schemas and a private enum
sprawl; both violate the as-built law. Every paper `geo.*`/`legal.*`/`provenance.*`/`entity.*`/
`evidence_plan.*`/`multimodal.*`/`timeline.*` object was **re-homed** into `evidence`/`analysis`/
`public` by data-tier (raw → evidence, derived → analysis, audit/memory → public), and private
enums collapsed to `TEXT+CHECK` or the shared `0004`/`0005` types. Three triplicated paper run
tables, two audit logs, and two artifact notions were merged into one each.

**vs the as-built.** The as-built was small but correct; the reconciliation **builds on it, never
beside it**. `evidence.evidence_hash` is extended (H1/H2/H3 levels, Merkle members) not replaced;
`analysis.normalized_record` stays the universal spine and is extended additively; `normalized_
record.artifact_id → evidence.evidence_hash(id)` is preserved. The `0004` custom types
(`confidence`, `geo_point`, `canonical_id`, `source_system`, `mcl_factor`, `source_ref`,
`entity_type`, `event_type`, `temporal_class`, `match_method`) are reused; `entity_type` and
`event_type` are **extended via `ALTER TYPE … ADD VALUE`**, never redefined.

**vs prior iterations (NOT a blank slate).** Prior-iteration tables and intents were adopted/
adapted with cited provenance: TraceIQ/supabase `entities`+`entity_mentions`, Salem Forensic
Trinity messaging core, `normalized_geo_v5`'s dual-provider geocode model (verbatim), TraceIQ
Google-Timeline objects, salem_v3 `Incident`/`Statement`/`CONTRADICTS`, Zep ORM alias/crosswalk,
dial-stack pattern-persistence + Semantica `ApprovalChain`/`Precedent`. The decision tables in
each domain doc carry the per-field adopt/adapt/merge/split/deprecate marks.

**Behavioral-ontology integration (the heart of court-safety).** The full E4 ontology was
adopted as **versioned config DATA**, not code: `behavior_category` (the 18 from E2 ⊕ the 26 from
seed-patterns ⊕ `positive_behaviors.ttl`) with a first-class `category_polarity`
(negative/positive/neutral/linguistic_marker), `detection_pattern`/`pattern_lexicon` as
append-only versioned rows, and `behavior_category_mcl` as the normalized MCL map. Crucially the
model is **NOT one-sidedly negative**: positive / neutral / love-bombing / repair categories +
`cycle_phase` + `conduct_party` make the full relational cycle and **both parties** first-class,
so the user's own conduct and repair attempts are modeled with the same fidelity as adverse
conduct. Every detection row is a HYPOTHESIS by construction (`requires_human_review DEFAULT
true`, `safe_for_legal_use DEFAULT false`, legal-gate CHECK, attribution-gate CHECK). The J↔K MCL
label-swap and the single-party-lexicon bias are carried as explicit, flagged migration steps —
not silently "fixed."

---

## 4. Applied deferred corrections (the 9 from the addendum)

| # | Addendum correction | Status | Where |
|---|---|---|---|
| 1 | §04 extension list → full init set (`fuzzystrmatch`,`citext`,`ltree`,`hstore`,`unaccent`,`btree_gist`) | ✅ **applied** | `RECONCILED_SCHEMA.sql` STEP 0 (with live-drift `CREATE EXTENSION` for the 4 missing). |
| 2 | `id_xref` entity resolution → `fuzzystrmatch`+`pg_trgm`+`citext` | ✅ **applied** | D4 tables: `dmetaphone` generated cols, `gin_trgm_ops`, `citext` keys. |
| 3 | Temporal → `btree_gist EXCLUDE` on `tstzrange` | ✅ **applied** | `time_assertion.no_overlapping_belief`; `phone/email/handle` ownership EXCLUDE. |
| 4 | Write the BM25 resolution (Milvus primary; pg_textsearch staged fallback) | ✅ **applied** | §1 extension contract + §6 per-store; STEP 0 comment. |
| 5 | Track the `pg_textsearch` doc inconsistency + BM25-location conflict + `disclosure_tier` double-def | ✅ **applied** | §1 (BM25), §4 (disclosure_tier); the stale "pg_textsearch in image" docs flagged in §8. |
| 6 | §09 custody → confirm `pgcrypto.digest(...,'sha256')` | ✅ **applied** | `custody_event` chain + `change_log_chain` both use `digest(...,'sha256')`. |
| 7 | Re-home paper schemas under `evidence`/`analysis`/`public`; reuse `0004` types | ✅ **applied** | All domains; §3. |
| 8 | Fold in prior-iteration tables/intents (adopt/adapt) | ✅ **applied** | Per-domain decision tables; §2 matrix. |
| 9 | Acceptance step — diff reconciled DDL vs LIVE PG/Milvus/Neo4j before any migration | ✅ **applied (baseline captured)** | `live-introspection/` captured; §9 acceptance checklist. **Still must re-diff at deploy time.** |

**The `disclosure_tier` fix (primary bug, applied).** The name was bound to two disjoint
concepts. Resolution: (a) the substantive bitemporal column `analysis.normalized_record.
disclosure_tier` (TEXT CHECK `contemporaneous|hindsight|discovered`) is the **survivor, kept
unchanged** (non-destructive — guardrail says 0003 is the substantive one); (b) the orphan `0004`
ENUM (`public|restricted|sealed`) is **renamed `sensitivity_tier`** (access classification), via
an idempotent guard repeated safely across D1/D2/D4/D5/D6/D7/D8; (c) NEW tables needing the
bitemporal concept use a new `disclosure_horizon` enum with the **same vocabulary**.
**Outstanding (TODO-human, integrity A5):** the cross-store docs call this concept
`knowledge_horizon`; decide once whether to rename the surviving column to `knowledge_horizon`
in a coordinated records-domain migration, or keep `disclosure_tier`. Until then the column name
is canonical and the new-table enum mirrors it.

---

## 5. Per-store summary + BM25 + SurrealDB verdict

**Milvus (Resource 2, S1).** 8 collections in one embedding space (split by content type for
lifecycle/HITL/partitioning, not geometry), shared envelope, RRF hybrid fusion, `partition_key=
case_id`, append-only `superseded`. Re-homed every `pg_schema` to the 3 real schemas; the join key
is `milvus_pk == PG uuidv7`, recorded in `analysis.id_xref`; custody anchor = `evidence.evidence_
hash(id)`. **Integrity fix required (A2):** S1 must bind `ev_message` to **`analysis.message`**
(not a non-existent `evidence.message`); raw bytes anchor via `evidence.evidence_hash`. Embedding
dims are placeholders pending live-ovh2 verification; **never ship raw forensic/abuse evidence to
a cloud embedder without owner sign-off.** Live: 4 non-forensic collections exist; all forensic
collections are greenfield.

**Neo4j + Graphiti (Resource 3, S2).** Graph = `project(PostgreSQL)`, append-only, rebuildable.
Adopts the §06 label/edge catalog; re-homes every node `pg_table` to `evidence.*`/`analysis.*`.
Reuses `0004` types for the crosswalk; carries three orthogonal props (`knowledge_horizon`
bitemporal, `sensitivity_tier` access, `assertion_type` epistemic). Both-parties / full-cycle
labels (`CyclePhase`, `REACTION_TO`, `conduct_party`) added from `positive_behaviors.ttl` (needs
owner sign-off — extends VIP salem_v3, does not replace it). **Integrity fix required (A2/A10):**
S2 must bind `:Message` → `analysis.message` and use D4's names `analysis.person`/`organization`/
`device`/`account` (not `analysis.entity_*`); drop the phantom `evidence.identifier_raw`/
`evidence.platform`. Live: bare Graphiti, 0 nodes, no Semantica labels.

**SurrealDB (Resource 4, S3) — verdict: DEFER (conditional adopt).** Build the entire
consolidated-analysis model inside PG `analysis` (Phases A–C) with zero new infra — JSONB +
`pg_duckdb`/Cypher/Milvus-SDK federated reach + materialized views + `btree_gist` bitemporality +
`LISTEN/NOTIFY` review queue cover the requirement today with one fewer engine and no drift class.
Keep the schema "Surreal-shaped" (envelope + `fed_ref` pointer contract + edge vocab are portable).
Promote to SurrealDB in Phase D **only** on a fired trigger (cross-3-engine query latency, an
Agno-native session/memory win, or `LIVE SELECT` review-UX gain), and then only as a pure derived
sink (reference-by-pointer, batch projection, never authoritative, never a second system of
record). Live: empty (confirms ratified-undeployed).

**BM25 resolution (explicit).** **Milvus owns primary semantic + hybrid dense+sparse/BM25**
(`SPARSE_INVERTED_INDEX` via the Milvus BM25 `Function` over `text`, CPU-friendly) — ADR-0027. PG
keeps `tsvector` + `pg_trgm` for cheap local lookups. `pg_textsearch` is a **STAGED, not-baked,
optional PG-local fallback** — do not bake preemptively. This resolves the ADR-0013-vs-ADR-0027
location conflict in favor of Milvus.

---

## 6. Outstanding integrity + court-safety items (human attention)

**Integrity (from `review/integrity.md` — resolved in the draft vs still-open):**

| Item | Severity | Status in `RECONCILED_SCHEMA.sql` |
|---|---|---|
| A1 competing raw timeline/geo tables (D3 vs D5) | critical | **resolved** — D5's four typed tables; D3 raw tables dropped; anchor = `evidence.source`. |
| A2 `evidence.message` phantom (S1/S2 vs D2) | critical | **resolved in PG** (`analysis.message`); **store docs still need editing** (S1/S2 bind targets). |
| A3 `analysis.finding` FK'd but undefined | critical | **resolved** — minimal `analysis.finding`/`finding_version` created (**TODO: flesh out taxonomy**). |
| A4 `analysis.provenance` NOT NULL FK undefined | critical | **resolved** — converged on `analysis.processing_run`; provenance_id nullable FK. |
| A5 `disclosure_tier` surviving-column has 4 names | high | **partially** — enum→`sensitivity_tier` done; **column canonical-name decision still open** (TODO). |
| A6 `id_xref` double-defined (D4 vs S1) | high | **resolved** — unified pairwise + optional entity anchor. |
| A7 hard `evidence → analysis` FK (D5 `gps_point.device_id`) | high | **resolved** — soft uuid; provenance-link convention unified (analysis→processing_run / →evidence FK allowed; evidence→analysis soft). |
| A8 competing run ledgers + run ledger in RO lane | medium | **resolved** — `evidence.ingestion_run` dropped; `run_type='ingestion'`. |
| A9 `precision_class` vs `timestamp_certainty`; assertion_type 3 ways | medium | **resolved** — one `precision_class`, one `assertion_type` enum; `evidence_tier` kept as the parallel data-tier axis (documented 1:1 mapping). |
| A10 entity satellite names (D4 vs S2) | medium | **resolved in PG**; **S2 doc still needs renames**. |
| A11 party / review_state vocab incoherent | medium | **resolved** — one `conduct_party` enum; D7 uses `review_state`. |
| A12 domain cross-reference numbering drift | low | **doc-only** — corrected in this report's matrix. |
| A13 UUIDv7 PK exceptions | low | **accepted** — natural keys allowed on reference/ledger tables (custody_event.seq, change_log.seq, behavior_category, custody_factor, score_band_config). |
| A14 `btree_gist` EXCLUDE on `citext` | low/verify | **resolved** — EXCLUDE keys cast to `::text`. **Verify on live image.** |

**Court-safety (from `review/court_safety.md` — resolved vs still-open):**

| Finding | Status |
|---|---|
| #1 child NAME seeded as severity-10 `parental_alienation` abuse; "load verbatim" | **NOT a DDL fix — BLOCKING migration-step (§7 / seed loader).** The loader MUST route child-name/place/vulnerability terms to `pattern_lexicon` (severity 0) and reject any `detection_pattern` row that is case-specific + child-name + severity>0. |
| #2 `relational_classification` lacked legal gate | **resolved** — `relcls_legal_gate` CHECK added. |
| #3 `message` interpretive labels readable as fact | **resolved** — renamed `*_hint`; **must be excluded from agent court-read grants** (role grant, deploy step). |
| #4 `pattern_finding.author_party` nullable, attribution not enforced | **resolved** — `pattern_finding_attribution_gate` CHECK (no legal use without attribution). |
| #5 `factor_citation`/`legal_timeline_event` no SFL gate; `confidence_tier` unbound | **resolved** — SFL gates added to both; `evidence_item_conf_tier_ck` binds tier to numeric confidence. |
| #6 `bias_caution` didn't propagate to `pattern_finding` | **resolved** — `bias_caution`+`authored_perspective` denormalized onto `pattern_finding`. |

**Still needs human attention (carry-forward, court-use blocking):** child-name seed-routing
(#1); J↔K MCL remap of any imported S3/S6 tags; signing-key custody ADR (export manifest +
custody-chain anchoring — HSM vs pgcrypto, rotation); confidence-band/model-calibration tuning
against a real labeled review set before any court-tier reliance; H2 canonicalization recipe per
source type; instrument templates require attorney review; the `analysis.finding` taxonomy must be
fleshed out; the surviving-`disclosure_tier` column-name decision; single-party-lexicon bias
sign-off before any aggregate metric is shown.

---

## 7. MIGRATION PLAN (live `agno-postgres:18-duckdb` → this schema)

> **Init-only-on-empty-volume caveat:** the `/docker-entrypoint-initdb.d` scripts (`0001`–`0004`)
> run **only on a fresh data dir**. The live volume is NOT fresh, so this migration is applied
> **by hand** as an idempotent `0005`+ set. `0004` was never applied live and four extensions are
> missing — both are remediated as step 1/2. Do **not** wrap the whole file in one transaction
> (it contains `ALTER TYPE … ADD VALUE` + `CREATE TYPE`).

1. **Extensions (live drift).** `CREATE EXTENSION IF NOT EXISTS citext; ltree; hstore;
   fuzzystrmatch;` (already-live ones are no-ops). Confirm `SELECT version()` ≥ 18.
2. **Apply `0004` custom types** (`psql -f sql/0004_custom_types.sql`) — idempotent-guarded.
   This creates `confidence`/`geo_point`/`canonical_id`/`entity_type`/`event_type`/
   `temporal_class`/`mcl_factor`/`source_system`/`match_method`/`source_ref` + the (soon-renamed)
   `disclosure_tier` enum.
3. **Type fixes (STEP 1 of the SQL), run standalone (not in a txn):**
   (a) `ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;` (guarded; check no live column
   binds it — introspection confirms it's orphan); (b) create the shared `0005` enums
   (`evidence_tier`, `assertion_type`, `precision_class`, `strength_class`, `review_state`,
   `conduct_party`, `cycle_phase`, `disclosure_horizon`, domain enums); (c) the `ALTER TYPE
   entity_type/event_type ADD VALUE` block — **each on its own statement, before any table uses
   the new values.**
4. **Guard functions** (STEP 2) + **reference seed** (`custody_factor`, STEP 3).
5. **`evidence.*`** (STEP 4): create `source`/`file_node`, `ALTER evidence.evidence_hash ADD
   COLUMN …` (all additive/nullable → existing rows + the `artifact_id` FK unaffected),
   `custody_event`, the four raw geo tables. **Backfill** `evidence_hash.level='H1'`/`source_id`
   on legacy rows, then `VALIDATE CONSTRAINT evidence_hash_subject_ck` and only THEN attach the
   `evidence_hash` immutability trigger (the trigger blocks UPDATE).
6. **`public` registries** (STEP 5) → **`analysis.processing_run` + lineage/scoring** (STEP 6) →
   **`analysis` entities** (STEP 7) → **spine+messages** (STEP 8, includes `ALTER
   normalized_record ADD COLUMN`) → **geo** (STEP 9) → **timeline** (STEP 10) → **finding** (STEP
   11) → **behavioral** (STEP 12) → **legal/tasks/export** (STEP 13) → **review/redaction/export**
   (STEP 14) → **operational memory + change_log** (STEP 15) → **views** (STEP 16). All
   `CREATE … IF NOT EXISTS` / guarded — idempotent and additive.
7. **Seed config-as-DATA** (NOT by hand): load `seed-patterns.ts` (308), `behavioral_patterns.
   ttl`, `ABUSE_PATTERNS`, `detection_patterns.py`, `positive_behaviors.ttl`, case-specific
   lexicons into `detection_pattern_set` v1 — **applying the court-safety #1 routing**
   (child/place/vuln → `pattern_lexicon` sev 0; reject sev>0 child-name abuse rows). Seed
   `behavior_category_mcl` statutory-canonical (J=facilitation, K=domestic_violence) + remap legacy
   S3/S6 tags. Seed `score_band_config` v1 + `schema/ontology/classification_version` first rows
   (`review_status='pending'`).
8. **Per-table audit triggers** (D8 §G) — generate the parametrised `change_log` writer per case
   table; apply LAST so bulk seed inserts don't each emit audit rows.
9. **Role grants (connection-level boundary — NOT prompt):** agent read-only role keeps
   `default_transaction_read_only` (evidence RO); ingestion role `INSERT,SELECT` on `evidence.*`,
   no `UPDATE/DELETE` on hash/file_node/custody_event; `review-gatekeeper` is the ONLY role that
   may flip `safe_for_legal_use`/`review_status`; agent court reads hit `analysis.vw_court_export`
   only (never base tables, never `message.*_hint`). Set `app.actor`/`app.actor_kind` per
   connection. R2 object-lock is the storage-side half of write-once (not expressible in DDL).

**Rollback:** the migration creates only new objects + additive columns + one enum rename. Roll
back by `DROP` of the new objects (never `DROP` data — never-delete rule moves to `_stale`).

---

## 8. ACCEPTANCE / VERIFY-BEFORE-CLAIMING checklist

> **HARD RULE: design is paper-only until this passes.** A live baseline was captured
> (`live-introspection/`, 2026-06-30) but MUST be re-run immediately before deploy — the live DB
> can drift.

**PostgreSQL (`agno-postgres:18-duckdb`, DB `ai`):**
- [ ] `SELECT version();` → PG **18** (every PK uses native `uuidv7()`, ungated).
- [ ] `\dn` → `evidence`, `analysis`, `public` exist (✅ live). Note Agno tables are in `ai`.
- [ ] `\dx` → `citext`,`ltree`,`hstore`,`fuzzystrmatch` installed (🔴 currently MISSING — step 1).
      `pgcrypto`,`pg_trgm`,`btree_gist`,`btree_gin`,`postgis`,`pg_duckdb` present (✅ live).
- [ ] `\dT` / `pg_type` → `0004` types present (🔴 currently ABSENT — step 2). Confirm
      `disclosure_tier`→`sensitivity_tier` rename applied and no live column binds the old name.
- [ ] `\d analysis.normalized_record` / `\d evidence.evidence_hash` → confirm as-built columns
      before the additive `ALTER`; confirm row-counts for the `evidence_hash` backfill + VALIDATE.
- [ ] `EXCLUDE` constraints create on the live image (verify `btree_gist` + the `::text` cast on
      citext keys); `ST_GeoHash`/`geography` create (PostGIS present).
- [ ] `\dt evidence.* analysis.*` after apply → all 93 tables present; spot-check the SFL/
      attribution CHECK constraints and the append-only triggers fire.

**Milvus:** `list_collections` → forensic collections absent today (additive); after build,
confirm `pk`↔PG uuidv7 join + `partition_key=case_id` + the shared envelope; **verify the embedder
runs locally on CPU before embedding any sensitive evidence.**

**Neo4j:** `CALL db.schema.visualization()` / `db.labels()` → bare Graphiti today; after
projection confirm node `pg_table` ∈ {`evidence.*`,`analysis.*`} only and the crosswalk via
`id_xref(source_system='neo4j')`.

**SurrealDB:** `INFO FOR DB` → empty today (defer); do not deploy unless a Phase-D trigger fired.

---

## 9. Deliverables + recap

**Paths (absolute):**
- `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform/docs/planning/forensic-db-reconciliation/RECONCILED_SCHEMA.sql`
- `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform/docs/planning/forensic-db-reconciliation/FINAL_RECONCILIATION_REPORT.md`

**Total table count:** **93 tables created** (8 `evidence`, 74 `analysis`, 11 `public`) +
**2 as-built extended** (`evidence.evidence_hash`, `analysis.normalized_record`) +
**3 legacy as-built retained** (`public.agent_run`/`approval_request`/`transcript_insight`).
Plus 3 court-export views and the pre-existing Agno-managed tables (schema `ai`).
