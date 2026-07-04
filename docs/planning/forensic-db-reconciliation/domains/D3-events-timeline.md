# D3 — Events & Bitemporal Timeline (reconciled domain)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> Reconciliation domain **D3**. Scope: the canonical **event spine**, the raw Google-Timeline
> source objects (`visits`/`activities`/`paths`/`waypoints`/`trips`), the **bitemporal**
> interpretation model (valid + transaction + discovery + ingestion clocks),
> **relative-time anchoring**, earliest/latest windows, and **interpretation-revision history**.
>
> **Law:** `extracted/E1_asbuilt_inventory.md` (as-built ground truth). **Adopted prior art:**
> `extracted/E3_timeline_geo.md` (timeline_events/waypoints, 4 prior iterations), `A3_crosswalk.md`
> (salem_v3 `Incident`/`Event`, TraceIQ `timeline_enriched`). **Paper design:**
> `sections/08-temporal.md` (four clocks, `time_assertion`, anchors). **Guardrails:** addendum §B/§D + CONTEXT_PACK §1/§5.
>
> **Out of scope (owned by sibling domains, referenced by FK):** geocode resolution / provider
> disagreement / `location` canonicalization (geo/spatial domain); `normalized_record` core +
> message/call records (records/messaging domain); behavioral/abuse labels on events (behavioral domain);
> cross-store `id_xref` spine. Where this domain needs them it declares an FK and notes the owner.

---

## 1. The two headline reconciliation calls

**(A) Raw-vs-derived lane split across the `evidence`/`analysis` boundary.** The prior iterations (E3)
collapsed raw Google segments, *inferred* multi-device splits, *enriched* geocoding, and *analytical*
overnight/anomaly flags into one wide `timeline_enriched` row. That violates the as-built security
boundary and the lane-discipline guardrail. We split it:

- **`evidence`** (RO, append-only, verbatim): `raw_timeline_segment` (merge of visits/activities/paths/trips),
  `timeline_waypoint` (exploded path points), `ingestion_run` (run ledger). These are 1:1 transcriptions
  of the raw export (the *file* is custody-hashed in `evidence.evidence_hash`); coordinate-string parsing
  is the only transform allowed here.
- **`analysis`** (write-after-approval, derived): `timeline_event` (the enriched/curated event spine),
  `time_assertion` (bitemporal interpretation), `temporal_anchor`, `relative_rule`, `event_ordering`,
  `waypoint_device_split` (the *inferred* 100 m multi-device attribution — pulled out of the raw waypoint
  because it is an inference, not raw data).
- **`public`**: `vw_event_evidence_package` (court export, HITL-gated, confidence-tiered).

**(B) `timeline_event` is the analytical spine; `analysis.normalized_record` stays the per-record substrate.**
They are different grains. `normalized_record` (as-built, `record_type IN message/call/event/media`) = one
parsed record. `timeline_event` = a curated forensic event (salem `Incident`/`Event`) that may aggregate
several records and segments via `event_source_record`. The event's *current believed* valid time is a cache;
the authoritative, never-overwritten history lives in `time_assertion`. This keeps the as-built bitemporal
columns on `normalized_record` (`occurred_at`/`knowledge_time`/`disclosure_tier`) intact while giving the
event layer a full append-only revision lane.

**Bitemporal mechanics:** transaction time is a `tstzrange sys_period` with a **`btree_gist EXCLUDE`**
`(event_id WITH =, sys_period WITH &&)` — two beliefs about one event can never overlap in transaction time,
which *is* the "one current truth, infinite history" guarantee (the open-upper `[now,∞)` of two current rows
would overlap and is rejected). Valid time is a GiST-indexed `tstzrange valid_range` for native
overlap/containment ("what else happened that weekend") queries. The `disclosure_tier` double-definition bug
is fixed here (see §4 migration): the substantive 0003 semantics become enum `disclosure_horizon`
(`contemporaneous|hindsight|discovered`); the 0004 enum is renamed `sensitivity_tier`.

---

## 2. Reconciled DDL

```sql
-- =====================================================================
-- D3 — Events & Bitemporal Timeline
-- Reuses 0004 custom types (event_type, temporal_class, confidence,
-- geo_point, mcl_factor, canonical_id). New domain-local enums below.
-- geo_point columns are PostGIS-guarded: omit if PostGIS absent (0001 §5.6).
-- =====================================================================

-- ---- New enums (NOT redefinitions of 0004; none of these exist in 0004) ----
CREATE TYPE timeline_segment_type AS ENUM ('visit','activity','path','trip');
CREATE TYPE timestamp_certainty   AS ENUM ('exact','approximate','inferred','uncertain');
CREATE TYPE assertion_kind        AS ENUM
  ('raw_evidence','extracted_fact','inferred_fact','analytical_finding','legal_conclusion');
-- Fix for the disclosure_tier double-definition (E1 §5.1): the SUBSTANTIVE
-- 0003 knowledge-horizon vocabulary, promoted from TEXT+CHECK to a real enum.
CREATE TYPE disclosure_horizon    AS ENUM ('contemporaneous','hindsight','discovered');
CREATE TYPE temporal_relation     AS ENUM
  ('preceded','meets','overlaps','during','same_day','equals','caused_hypothesis');
CREATE TYPE anchor_kind           AS ENUM
  ('docketed_event','recurring_holiday','life_event','derived');

-- Extend the reused 0004 event_type to cover location/communication-derived events
-- (ALTER ... ADD VALUE — extends, does not redefine; see migration note M3).
--   ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'presence';
--   ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'communication';
--   ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'observation';

-- =====================================================================
-- EVIDENCE schema — raw/source, agents READ-ONLY, append-only
-- =====================================================================

-- Ingestion run ledger (was TraceIQ/D processing_metadata).
CREATE TABLE evidence.ingestion_run (
  run_id              uuid PRIMARY KEY DEFAULT uuidv7(),
  source_file         text NOT NULL,
  source_artifact_id  uuid REFERENCES evidence.evidence_hash(id),   -- custody anchor
  file_sha256         bytea,                                        -- mirror of custody digest
  status              text NOT NULL DEFAULT 'running'
                        CHECK (status IN ('running','completed','failed','partial')),
  total_segments      integer, visits_created integer, activities_created integer,
  paths_created       integer, trips_created integer, waypoints_created integer,
  multi_device_splits integer, errors_encountered integer,
  started_at          timestamptz NOT NULL DEFAULT now(),
  completed_at        timestamptz,
  prompt_version      text, ontology_version text, schema_version text,
  meta                jsonb NOT NULL DEFAULT '{}',
  CONSTRAINT ingestion_run_sha256_len
    CHECK (file_sha256 IS NULL OR octet_length(file_sha256) = 32)
);

-- Merge of raw visits/activities/timeline_paths/memories_trips (E3 §B/§D).
-- ONE table, segment_type-discriminated; verbatim raw fields only.
CREATE TABLE evidence.raw_timeline_segment (
  segment_id          uuid PRIMARY KEY DEFAULT uuidv7(),
  ingest_run_id       uuid REFERENCES evidence.ingestion_run(run_id),
  source_artifact_id  uuid NOT NULL REFERENCES evidence.evidence_hash(id),
  segment_type        timeline_segment_type NOT NULL,
  source_serial_id    bigint,            -- event_serial_id — AUTHORITATIVE ordering (NOT timestamp)
  hierarchy_level     integer,
  parent_segment_id   uuid REFERENCES evidence.raw_timeline_segment(segment_id),
  -- raw temporal triple (verbatim; tz_offset NULL drives ambiguity workflow)
  start_ts_raw        text, start_ts_utc timestamptz, start_tz_offset_minutes integer,
  end_ts_raw          text, end_ts_utc   timestamptz, end_tz_offset_minutes   integer,
  duration_seconds    bigint,
  -- raw geo: verbatim geopair strings; coordinate-parse to geo_point only.
  -- Place/address RESOLUTION is deferred to the geo domain.
  start_geopair       text, end_geopair text,
  start_geo           geo_point, end_geo geo_point,                 -- PostGIS-guarded
  raw_place_id        text,
  -- source-provider probabilities (Google's own scores — raw, not our confidence)
  detection_probability       confidence,
  semantic_type               text, semantic_type_probability  confidence,
  activity_type               text, activity_type_probability  confidence,
  distance_meters             numeric,
  trip_distance_from_origin_km numeric,
  memory_ref          text,
  original_json       jsonb NOT NULL,    -- verbatim payload (RAW EVIDENCE contract — keep)
  data_source         text,             -- e.g. 'google-timeline' (NOT source_system enum)
  ingested_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_rawseg_run        ON evidence.raw_timeline_segment (ingest_run_id);
CREATE INDEX idx_rawseg_artifact   ON evidence.raw_timeline_segment (source_artifact_id);
CREATE INDEX idx_rawseg_type_serial ON evidence.raw_timeline_segment (segment_type, source_serial_id);
CREATE INDEX idx_rawseg_json       ON evidence.raw_timeline_segment USING gin (original_json);
CREATE INDEX idx_rawseg_startgeo   ON evidence.raw_timeline_segment USING gist (start_geo);

-- Exploded path waypoints (E3 §B timeline_paths / §D waypoints). RAW only;
-- multi-device split (an inference) lives in analysis.waypoint_device_split.
CREATE TABLE evidence.timeline_waypoint (
  waypoint_id         uuid PRIMARY KEY DEFAULT uuidv7(),
  segment_id          uuid NOT NULL REFERENCES evidence.raw_timeline_segment(segment_id) ON DELETE CASCADE,
  point_sequence      integer NOT NULL,  -- 1-based; ORDER BY THIS, NOT timestamp (E3 §D rule)
  point_timestamp_raw text,
  point_timestamp_utc timestamptz,
  tz_offset_minutes   integer,
  point_geopair       text,
  point_geo           geo_point,         -- PostGIS-guarded
  aligned_activity_id uuid REFERENCES evidence.raw_timeline_segment(segment_id),
  original_json       jsonb,
  UNIQUE (segment_id, point_sequence)
);
CREATE INDEX idx_waypoint_geo ON evidence.timeline_waypoint USING gist (point_geo);

-- =====================================================================
-- ANALYSIS schema — derived; writes only after recorded approval
-- =====================================================================

-- Canonical enriched EVENT spine (salem Incident/Event + TraceIQ timeline_enriched
-- + generic-spine semantics). Current valid-time is a CACHE of the current time_assertion.
CREATE TABLE analysis.timeline_event (
  event_id            uuid PRIMARY KEY DEFAULT uuidv7(),
  canonical_event_id  canonical_id,            -- cross-store xref identity (xref domain)
  event_key           citext UNIQUE,           -- stable human key, e.g. 'the_argument'
  serial_id           bigint,                  -- adopted TraceIQ ordering hint
  title               text NOT NULL,
  description         text,
  event_type          event_type NOT NULL,     -- 0004 enum (extended, see M3)
  temporal_class      temporal_class NOT NULL DEFAULT 'historical',  -- 0004 enum
  -- CURRENT believed valid time (cache; authoritative history in time_assertion)
  valid_earliest      timestamptz,
  valid_latest        timestamptz,
  valid_point         timestamptz,             -- aligns w/ normalized_record.occurred_at semantics
  valid_range         tstzrange GENERATED ALWAYS AS
                        (tstzrange(valid_earliest, valid_latest, '[]')) STORED,
  current_certainty   timestamp_certainty,
  current_confidence  confidence,
  disclosure_horizon  disclosure_horizon NOT NULL DEFAULT 'contemporaneous',
  assertion_type      assertion_kind NOT NULL DEFAULT 'analytical_finding',
  -- spatial link (geo domain owns canonicalization)
  location_id         uuid,                    -- FK -> analysis.location (geo domain)
  primary_geo         geo_point,               -- PostGIS-guarded cache
  -- court-safety + review gating (guardrails)
  is_conflicted       boolean NOT NULL DEFAULT false,
  requires_human_review boolean NOT NULL DEFAULT false,
  safe_for_legal_use  boolean NOT NULL DEFAULT false,   -- export gate
  reviewed_by         text, reviewed_at timestamptz,
  -- forensic context (model BOTH parties + custody relevance)
  conduct_party       text,                    -- which party (nullable; HITL-reviewed)
  mcl_relevance       mcl_factor[] NOT NULL DEFAULT '{}',   -- 0004 mcl_factor (a..l)
  -- provenance
  source_artifact_id  uuid REFERENCES evidence.evidence_hash(id),
  primary_record_id   uuid REFERENCES analysis.normalized_record(id),
  ingest_run_id       uuid REFERENCES evidence.ingestion_run(run_id),
  derived_from        uuid[] NOT NULL DEFAULT '{}',
  prompt_version      text, ontology_version text, schema_version text,
  attrs               jsonb NOT NULL DEFAULT '{}',
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_event_validrange ON analysis.timeline_event USING gist (valid_range);
CREATE INDEX idx_event_type_point ON analysis.timeline_event (event_type, valid_point);
CREATE INDEX idx_event_title_trgm ON analysis.timeline_event USING gin (title gin_trgm_ops);
CREATE INDEX idx_event_mcl        ON analysis.timeline_event USING gin (mcl_relevance);
CREATE INDEX idx_event_attrs      ON analysis.timeline_event USING gin (attrs);
CREATE INDEX idx_event_review     ON analysis.timeline_event (requires_human_review)
                                    WHERE requires_human_review;
CREATE INDEX idx_event_geo        ON analysis.timeline_event USING gist (primary_geo);

-- Event <- source provenance (m:n over records and/or raw segments).
CREATE TABLE analysis.event_source_record (
  link_id     uuid PRIMARY KEY DEFAULT uuidv7(),
  event_id    uuid NOT NULL REFERENCES analysis.timeline_event(event_id) ON DELETE CASCADE,
  record_id   uuid REFERENCES analysis.normalized_record(id),
  segment_id  uuid REFERENCES evidence.raw_timeline_segment(segment_id),
  role        text NOT NULL DEFAULT 'primary'
                CHECK (role IN ('primary','corroborating','context','contradicting')),
  CONSTRAINT  esr_has_source CHECK (record_id IS NOT NULL OR segment_id IS NOT NULL)
);
CREATE UNIQUE INDEX uq_esr_record  ON analysis.event_source_record (event_id, record_id)
                                     WHERE record_id IS NOT NULL;
CREATE UNIQUE INDEX uq_esr_segment ON analysis.event_source_record (event_id, segment_id)
                                     WHERE segment_id IS NOT NULL;

-- BITEMPORAL interpretation-revision history. One row = one INTERPRETATION of when an
-- event occurred. Append-only: never UPDATE except to close sys_period (set upper bound).
CREATE TABLE analysis.time_assertion (
  assertion_id        uuid PRIMARY KEY DEFAULT uuidv7(),
  event_id            uuid NOT NULL REFERENCES analysis.timeline_event(event_id) ON DELETE CASCADE,
  -- VALID TIME (real world) — always a range; point = working best estimate
  valid_earliest      timestamptz NOT NULL,
  valid_latest        timestamptz NOT NULL,
  valid_point         timestamptz,
  valid_range         tstzrange GENERATED ALWAYS AS
                        (tstzrange(valid_earliest, valid_latest, '[]')) STORED,
  -- raw/UTC/offset triple (tz_offset NULL => tz-ambiguity path)
  ts_raw              text,
  ts_utc              timestamptz,
  tz_offset_minutes   integer,
  tz_source           text CHECK (tz_source IS NULL OR tz_source IN
                        ('exif_offset','export_header','assumed_local','device_setting','unknown')),
  -- certainty + lane + confidence + knowledge horizon
  certainty           timestamp_certainty NOT NULL,
  assertion_type      assertion_kind NOT NULL DEFAULT 'extracted_fact',
  confidence          confidence,               -- 0004 domain (calibrated; NOT hard-coded 0.6)
  disclosure_horizon  disclosure_horizon NOT NULL DEFAULT 'contemporaneous',
  is_conflicted       boolean NOT NULL DEFAULT false,
  requires_human_review boolean NOT NULL DEFAULT false,
  -- DISCOVERY + INGESTION clocks
  discovered_at       timestamptz,
  discovery_source    uuid REFERENCES evidence.evidence_hash(id),
  ingested_at         timestamptz NOT NULL DEFAULT now(),
  ingest_run_id       uuid REFERENCES evidence.ingestion_run(run_id),
  -- TRANSACTION TIME (system-versioned via range + EXCLUDE; append-only)
  sys_period          tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
  superseded_by       uuid REFERENCES analysis.time_assertion(assertion_id),
  -- PROVENANCE + reasoning trail
  derived_from        uuid[] NOT NULL DEFAULT '{}',
  anchor_refs         uuid[] NOT NULL DEFAULT '{}',
  reasoning           text,
  prompt_version      text, ontology_version text, schema_version text,
  author              text NOT NULL,   -- 'pipeline:tz-resolver' | 'human:matt' | 'agent:forensic-data'
  CONSTRAINT valid_ordering CHECK (valid_earliest <= valid_latest),
  -- THE bitemporal guarantee: no two beliefs overlap in transaction time per event.
  -- Two "current" rows ([now,inf)) would overlap => exactly one current assertion.
  CONSTRAINT no_overlapping_belief
    EXCLUDE USING gist (event_id WITH =, sys_period WITH &&)
);
CREATE INDEX idx_ta_validrange ON analysis.time_assertion USING gist (valid_range);
CREATE INDEX idx_ta_event_tx   ON analysis.time_assertion (event_id, lower(sys_period) DESC);
CREATE INDEX idx_ta_current    ON analysis.time_assertion (event_id) WHERE upper_inf(sys_period);
CREATE INDEX idx_ta_review     ON analysis.time_assertion (requires_human_review)
                                 WHERE requires_human_review;

-- Anchor registry — datable reference events for relative-time resolution.
CREATE TABLE analysis.temporal_anchor (
  anchor_id           uuid PRIMARY KEY DEFAULT uuidv7(),
  anchor_key          citext UNIQUE,           -- 'court_hearing_2024_11_22'
  label               text NOT NULL,
  anchor_type         anchor_kind NOT NULL,
  event_id            uuid REFERENCES analysis.timeline_event(event_id), -- if anchor IS an event
  valid_earliest      timestamptz NOT NULL,
  valid_latest        timestamptz NOT NULL,
  valid_range         tstzrange GENERATED ALWAYS AS
                        (tstzrange(valid_earliest, valid_latest, '[]')) STORED,
  certainty           timestamp_certainty NOT NULL,
  confidence          confidence,
  derived_from        uuid[] NOT NULL DEFAULT '{}',
  requires_human_review boolean NOT NULL DEFAULT false,
  author              text NOT NULL,
  asserted_at         timestamptz NOT NULL DEFAULT now(),
  retracted_at        timestamptz,
  CONSTRAINT anchor_ordering CHECK (valid_earliest <= valid_latest)
);
CREATE INDEX idx_anchor_range ON analysis.temporal_anchor USING gist (valid_range);

-- Versioned relative-phrase -> window-arithmetic rules (audit-reproducible).
CREATE TABLE analysis.relative_rule (
  rule_id             uuid PRIMARY KEY DEFAULT uuidv7(),
  phrase_pattern      text NOT NULL,           -- 'the weekend after X'
  resolution_expr     text NOT NULL,           -- documented interval arithmetic
  result_certainty    timestamp_certainty NOT NULL,
  lower_offset        interval,
  upper_offset        interval,
  config              jsonb NOT NULL DEFAULT '{}',
  ontology_version    text, prompt_version text,
  is_active           boolean NOT NULL DEFAULT true,
  created_at          timestamptz NOT NULL DEFAULT now()
);

-- Event ordering edges (partial order when absolute time is fuzzy; Allen relations).
CREATE TABLE analysis.event_ordering (
  ordering_id         uuid PRIMARY KEY DEFAULT uuidv7(),
  before_event        uuid NOT NULL REFERENCES analysis.timeline_event(event_id) ON DELETE CASCADE,
  after_event         uuid NOT NULL REFERENCES analysis.timeline_event(event_id) ON DELETE CASCADE,
  relation            temporal_relation NOT NULL DEFAULT 'preceded',
  basis               text NOT NULL,           -- 'narrative:"night before"' | 'timestamp' | 'reasoning'
  confidence          confidence,
  requires_human_review boolean NOT NULL DEFAULT false,
  derived_from        uuid[] NOT NULL DEFAULT '{}',
  author              text NOT NULL,
  asserted_at         timestamptz NOT NULL DEFAULT now(),
  retracted_at        timestamptz,
  CONSTRAINT no_self_order CHECK (before_event <> after_event)
);
CREATE INDEX idx_ordering_before ON analysis.event_ordering (before_event);
CREATE INDEX idx_ordering_after  ON analysis.event_ordering (after_event);

-- INFERRED multi-device attribution for waypoints (100 m threshold) — lane-split out
-- of the raw waypoint because it is an inference, not raw data.
CREATE TABLE analysis.waypoint_device_split (
  split_id            uuid PRIMARY KEY DEFAULT uuidv7(),
  waypoint_id         uuid NOT NULL REFERENCES evidence.timeline_waypoint(waypoint_id),
  device_index        integer NOT NULL,
  split_from_segment  uuid REFERENCES evidence.raw_timeline_segment(segment_id),
  threshold_meters    numeric NOT NULL DEFAULT 100,
  certainty           timestamp_certainty NOT NULL DEFAULT 'inferred',
  confidence          confidence,
  requires_human_review boolean NOT NULL DEFAULT false,
  ingest_run_id       uuid REFERENCES evidence.ingestion_run(run_id),
  author              text NOT NULL,
  asserted_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_wds_waypoint ON analysis.waypoint_device_split (waypoint_id);

-- =====================================================================
-- PUBLIC schema — HITL court-export view (current beliefs only, gated)
-- =====================================================================
CREATE VIEW public.vw_event_evidence_package AS
SELECT
  e.event_id, e.serial_id, e.title, e.event_type,
  ta.valid_earliest, ta.valid_latest, ta.valid_point, ta.ts_utc,
  ta.certainty, ta.assertion_type, ta.confidence, ta.disclosure_horizon,
  CASE
    WHEN ta.certainty = 'exact'       AND ta.confidence >= 0.80 THEN 'HIGH'
    WHEN ta.certainty = 'approximate' AND ta.confidence >= 0.60 THEN 'MEDIUM'
    ELSE 'LOW'
  END AS temporal_confidence_tier,
  e.mcl_relevance, e.source_artifact_id, ta.reasoning
FROM analysis.timeline_event e
JOIN analysis.time_assertion ta
  ON ta.event_id = e.event_id AND upper_inf(ta.sys_period)   -- current belief only
WHERE e.safe_for_legal_use
  AND NOT e.requires_human_review
  AND NOT ta.requires_human_review;
```

---

## 3. Decision table

| Table / field | Decision | Source (as-built / paper / prior file) | Note |
|---|---|---|---|
| `evidence.raw_timeline_segment` | **merge** (visits+activities+timeline_paths+memories_trips → 1) | E3 §B/§D (TraceIQ, inventory) | One discriminated raw table; verbatim fields + `original_json`; geo *resolution* deferred to geo domain |
| `…segment.source_serial_id` | **adopt** | E3 §B `serial_id`; §D `sequence` | Authoritative ordering — order by this, NOT timestamp |
| `…segment.start/end geopair/geo` | **adapt** | E3 `location_geopair` | Keep raw geopair text; parse to `geo_point` (0004) only; place/address = geo domain |
| `…segment.*_probability` | **adopt** | E3 `*_probability` | Google's own scores; reuse `confidence` domain; ≠ our calibrated confidence |
| `evidence.timeline_waypoint` | **adopt** | E3 §B `timeline_paths`, §D `waypoints` | Exploded points; `(segment_id, point_sequence)` unique |
| waypoint `multi_device_split`/`device_index`/`split_from_segment` | **split** → `analysis.waypoint_device_split` | E3 §B/§D | It is an *inference* (100 m), not raw → moved to `analysis` lane |
| `evidence.ingestion_run` | **adapt** | E3 §D `processing_metadata` | Run ledger + custody hash + counts; append-only provenance |
| `analysis.timeline_event` | **merge/adapt** | salem `Incident`/`Event` (A3 §A); TraceIQ `timeline_enriched` (E3 §B); generic spine (E3 §A) | Curated analytical event; aggregates records/segments |
| `timeline_event.event_type` | **adapt** (extend 0004 enum) | 0004 `event_type` | `ALTER TYPE ADD VALUE` presence/communication/observation (M3) |
| `timeline_event.temporal_class` | **adopt** | 0004 `temporal_class` | historical/current/future |
| `timeline_event.valid_*` (cache) | **adapt** | paper §2 | Current-belief cache; authoritative history in `time_assertion` |
| `timeline_event.mcl_relevance` | **adopt** | 0004 `mcl_factor`; salem `EXPOSED_CHILD`/`AFFECTED_PARENTING_ACCESS` (A3) | Tags custody factors on events (edge analogues live in Neo4j) |
| `timeline_event.conduct_party` | **adapt** (needs-review) | A3 §A gap note | Model BOTH parties / reactive context; nullable, HITL |
| `timeline_event.safe_for_legal_use` | **adopt** | guardrail | Court-export gate |
| `analysis.event_source_record` | **adapt** | E3 §A `chat_message_life_events`/`entity_timeline_associations` | Event↔record/segment provenance m:n |
| `analysis.time_assertion` | **adopt** | paper §2/§5 | Bitemporal core; 4 clocks; append-only revision history |
| `time_assertion.sys_period` + EXCLUDE | **adapt** | paper §5 (asserted_at/retracted_at) | Re-expressed as `tstzrange` + `btree_gist EXCLUDE` (stronger than partial-unique) |
| `time_assertion.certainty`/`assertion_type` | **adopt** | paper §2.1; CONTEXT_PACK §5 lanes | New enums (absent from 0004) |
| `time_assertion.disclosure_horizon` | **adopt** (bugfix) | 0003 text CHECK; E1 §5.1 | Promotes the substantive 0003 vocabulary to an enum |
| `time_assertion.confidence` | **adopt** | 0004 `confidence`; paper §4.1 | Calibrated formula; replaces legacy 0.6 |
| `analysis.temporal_anchor` | **adopt** | paper §3.1 | Anchor registry; `valid_range` GiST |
| `analysis.relative_rule` | **adopt** | paper §3.2 | Versioned phrase→window arithmetic (reproducible) |
| `analysis.event_ordering` | **adopt** | paper §4.2 | Allen relations; `caused_hypothesis` never auto-promoted |
| `public.vw_event_evidence_package` | **adapt** | E3 §B `vw_forensic_evidence_package` | Court export; current belief only; confidence tier; HITL-gated |
| 0004 `disclosure_tier` enum (public/restricted/sealed) | **deprecate→rename** | 0004; E1 §5.1 | Rename to `sensitivity_tier` (access classification) — see M1 |
| `normalized_record.disclosure_tier` (TEXT+CHECK) | **adapt** (retype) | 0003 | → `disclosure_horizon` enum; coordinate w/ records domain (M2) |
| 0004 `source_ref` composite / `source_system` / `match_method` | **note** (not used here) | 0004 | Belong to xref/provenance domain; explicit FKs used in D3 instead |
| `geo_point` (0004 domain) | **adopt** | 0004 | Used on segment/waypoint/event; PostGIS-guarded |
| `canonical_id` (0004 domain) | **adopt** | 0004 | `timeline_event.canonical_event_id` for cross-store xref |

---

## 4. Migration notes (live `agno-postgres:18-duckdb` → this domain)

Apply in order. **Acceptance step first:** diff against the LIVE DB (`information_schema`, `pg_type`,
`pg_extension`) before running anything — `0004` may not be applied on the live volume (E1 §3 apply-once),
and PostGIS/`uuidv7()` presence must be confirmed (E1 §5.5/5.6).

- **M0 — preconditions.** Confirm `CREATE EXTENSION` present: `btree_gist`, `pg_trgm`, `pgcrypto`, `citext`,
  `postgis` (for `geo_point`); confirm engine is **PG18** (native `uuidv7()`). If PostGIS absent, create
  the tables **without** the `geo_point` columns + their GiST indexes (store `*_geopair` text only) and
  backfill geo later. Confirm `0004` types exist; if not, run `sql/0004` (it is idempotent-guarded).
- **M1 — fix `disclosure_tier` double-definition (E1 §5.1).** `ALTER TYPE disclosure_tier RENAME TO
  sensitivity_tier;` (the 0004 `public|restricted|sealed` access enum). Then
  `CREATE TYPE disclosure_horizon AS ENUM ('contemporaneous','hindsight','discovered');`.
- **M2 — retype `normalized_record` (cross-domain; coordinate with records domain).**
  `ALTER TABLE analysis.normalized_record DROP CONSTRAINT <disclosure_tier_check>;`
  `ALTER TABLE analysis.normalized_record ALTER COLUMN disclosure_tier TYPE disclosure_horizon
  USING disclosure_tier::disclosure_horizon;` (values already align) then optionally
  `RENAME COLUMN disclosure_tier TO disclosure_horizon;`. **Owner = records domain** — flag, do not apply unilaterally.
- **M3 — extend `event_type`.** `ALTER TYPE event_type ADD VALUE IF NOT EXISTS 'presence';` (+`communication`,
  `observation`). `ADD VALUE` cannot run inside the same txn that *uses* the new value (PG); run these in a
  standalone migration before creating `timeline_event`.
- **M4 — create new enums** (`timeline_segment_type`, `timestamp_certainty`, `assertion_kind`,
  `temporal_relation`, `anchor_kind`); then **create tables** in dependency order: `evidence.ingestion_run`
  → `evidence.raw_timeline_segment` → `evidence.timeline_waypoint` → `analysis.timeline_event` →
  `event_source_record`/`time_assertion`/`temporal_anchor`/`relative_rule`/`event_ordering`/`waypoint_device_split`
  → `public.vw_event_evidence_package`.
- **M5 — connection boundary.** New `evidence.*` tables inherit RO via `readonly_engine`
  (`default_transaction_read_only`); confirm the ingestion writer uses the privileged engine. `analysis.*`
  writes must pass the recorded-approval (`agno_approvals`) gate — no agent writes without it.
- **M6 — cache sync (deferred).** The `timeline_event.valid_*` cache should be kept in step with the current
  `time_assertion` via an `AFTER INSERT/UPDATE` trigger or a refresh job. Not created here (HITL: confirm
  trigger vs job before adding write-side automation in the RO/approval-gated boundary).

---

## 5. Needs-human-review

- **Confidence calibration (paper §4.1).** `base[]` constants / `window_penalty` are unvalidated defaults;
  tune before any `confidence` reaches a court export. The view's HIGH/MED/LOW thresholds (0.80/0.60) inherit this.
- **`conduct_party` + full-relational-cycle modeling.** salem_v3 models only adversarial conduct (A3 §A gap);
  adding `conduct_party` and positive/repair/love-bombing event subtypes must be confirmed with the owner before court use.
- **M2 (normalized_record retype)** is cross-domain — must be coordinated with the records/messaging domain, not applied by D3 alone.
- **Multi-device split + overnight/bouncy anomalies** are inferences/hypotheses (`waypoint_device_split`,
  future analytical views) — never auto-promote to fact; `caused_hypothesis` ordering edges stay HITL.
- **tz-ambiguity rows** (`tz_offset_minutes IS NULL`) stay `uncertain`/flagged until device-timezone evidence is confirmed present in the corpus.
```
