# D5 — Location & GPS (PostGIS)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> Reconciliation domain D5 of the forensic-evidence DB. Reconciles the paper-design `geo`
> schema (§03 section 6) + the prior-iteration geo corpus (E3: `normalized_geo_schema_v5`,
> TraceIQ `timeline_enriched`/visits/activities/paths/trips, dual-provider geocode stack,
> Postgres+PostGIS waypoints) **into the as-built security boundary** (E1) — schemas
> `evidence` (raw, agents read-only) and `analysis` (derived, write-after-approval), reusing
> the `sql/0004` custom types. PostGIS lives **inside** the single unified PG18 resource
> (`agno-postgres:18-duckdb`); it is never a standalone deployable (CONTEXT_PACK §1).

---

## 1. Reconciliation summary (prose)

**The biggest call: re-home, don't re-schema.** The paper put the geo lane in a top-level
`geo` schema with eleven tables. The as-built law (E1 §0, addendum §B) permits only three
schemas — `evidence` / `analysis` / `public` — and uses the data-*tier* (`raw` / `extracted`
/ `inferred` / `analytical`) to discriminate evidentiary weight. So every paper `geo.*` table
is re-homed by tier, not by subject:

- **`evidence` (raw tier, agents read-only, written by the ingestion pipeline role):** the
  byte-faithful Google Takeout objects and raw device fixes — `evidence.gps_point`,
  `evidence.raw_visit`, `evidence.raw_activity`, `evidence.raw_path`, `evidence.raw_trip`.
  These carry `raw_data jsonb` verbatim (C11) and FK to the custody anchor `evidence.source`.
- **`analysis` (extracted/inferred/analytical tiers, HITL-gated where sensitive):** everything
  derived — `analysis.gps_track`, `analysis.location` (canonical dedup), `analysis.stay_point`,
  `analysis.geofence`, `analysis.home_base`, `analysis.location_assertion`,
  `analysis.location_contradiction`, and the geocode pipeline
  (`geocode_request`/`geocode_result`/`geocode_resolution`/`geocode_audit`).

**Adopted wholesale from `normalized_geo_v5` (A3 §D, E3 §C):** the dual-provider
`geocode_resolution` model — `preferred_provider` / `distance_m` / `disagreement_flag` /
`tie_break_reason` — is excellent prior art and is carried verbatim into
`analysis.geocode_resolution`. `location_key` dedup becomes the `UNIQUE(geohash9, name)`
constraint on `analysis.location`. Append-only `geocode_audit` is kept as-is (C10).

**Adopted from TraceIQ (E3 §B):** raw `visits`/`activities`/`timeline_paths`/`memories_trips`
become the four `evidence.raw_*` tables; `location_fuzzy` (privacy-rounded coords) is preserved
as a first-class `is_fuzzed` flag plus a `sensitivity_tier` on `analysis.location`;
`serial_id`/`point_sequence` ordering is preserved because **timestamps lie inside ~2-hour
containers — order by sequence, never by timestamp** (E3 §D parsing rule, non-negotiable).
Multi-device split (`multi_device_split` / `device_index` / `split_from_segment`, 100 m
threshold) is carried onto `evidence.raw_path`.

**Modernized (A3 §111):** manual `geohash8/9` columns are replaced by a PostGIS **generated
column** `geohash9 GENERATED ALWAYS AS (ST_GeoHash(geog::geometry,9)) STORED`, so the dedup key
is never hand-maintained and can't drift from the geometry.

**Type reuse (E1 §3, guardrail):** point columns reuse the `0004` `geo_point` domain
(`geography(Point,4326)`) so the GiST + KNN `<->` story is uniform. `geo_point` is **Point-only**,
so `gps_track` (LineString) and `geofence` (Polygon) use raw `geography(LineString|Polygon,4326)`.
`confidence numeric(4,3)` is reused for every spatial-confidence column; `precision_class`,
`evidence_tier`, `review_state`, `strength_class` come from the shared §0.1 migration.

**disclosure_tier bug (E1 §5.1):** this domain depends on the rename — the `0004` enum
`('public','restricted','sealed')` becomes **`sensitivity_tier`** (access classification), used
here on `analysis.location` to mark privacy-fuzzed/sealed addresses. The substantive bitemporal
`disclosure_tier` (`contemporaneous|hindsight|discovered`) stays on `analysis.normalized_record`
untouched. This domain does **not** redefine either; it consumes `sensitivity_tier`.

**Lane discipline / court-safety:** raw fix (`gps_point`) ≠ extracted track (`gps_track`) ≠
inferred dwell (`stay_point`/`home_base`) ≠ analytical conflict (`location_contradiction`) — kept
in distinct tables with structurally-enforced `data_tier` CHECKs. Location **contradictions** and
claimed-vs-observed conflicts are HITL-gated (`requires_human_review`, `safe_for_legal_use`) and
never auto-promoted to fact. Heavy geo (GiST indexes, KNN, ST_GeoHash, ST_Distance) **stays in
PG**; only a lightweight GeoJSON projection (`ST_AsGeoJSON` over approved assertions) flows
downstream to SurrealDB — no spatial index is duplicated there (CONTEXT_PACK §1, ADR-0024).

---

## 2. Reconciled DDL

```sql
-- =====================================================================
-- D5 — Location & GPS (PostGIS) — reconciled DDL
-- Target: unified PG18 resource agno-postgres:18-duckdb (PostGIS embedded, never standalone)
-- Schemas: evidence (raw, agents RO) · analysis (derived, write-after-approval)
-- Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. PREREQUISITES — REUSED, never redefined here.
--    Shared / sql/0004 types (apply 0004 + shared §0.1 migration first):
--      uuidv7()             native PG18
--      confidence           DOMAIN numeric(4,3) CHECK 0..1            (0004)
--      geo_point            DOMAIN geography(Point,4326)              (0004; POINT-ONLY)
--      source_system        ENUM postgres/neo4j/milvus/surrealdb     (0004)
--      source_ref           COMPOSITE (system,native_id,locator)     (0004)
--      evidence_tier        ENUM raw/extracted/inferred/analytical/legal_conclusion  (shared §0.1)
--      precision_class      ENUM exact/approximate/inferred/uncertain (shared §0.1)
--      strength_class       ENUM none/weak/moderate/strong/conclusive (shared §0.1)
--      review_state         ENUM unreviewed/in_review/approved/rejected/needs_more_evidence (shared §0.1)
--      sensitivity_tier     ENUM public/restricted/sealed
--                           (RENAMED from 0004 disclosure_tier — see migration notes M2)
--    Dependency-domain tables REFERENCED (FKs; create in dependency order):
--      evidence.source(id)        custody anchor, carries hash_sha256   (D1 custody)
--      evidence.file_node(id)     custody tree node                     (D1 custody)
--      analysis.entity(id),
--      analysis.device(id)        entity / device registry             (D3 entity)
--      analysis.event(id)         timeline event (polymorphic subject)  (D4 timeline)
--      analysis.provenance(id)    provenance audit (model/prompt ver)   (Dprov)
-- NOTE: geo_point is POINT-only; LineString/Polygon use raw geography(...).

-- ---------------------------------------------------------------------
-- 0a. Geo-domain enums (NEW, geo-specific; created once)
-- ---------------------------------------------------------------------
CREATE TYPE assertion_source AS ENUM
  ('gps','claimed_text','exif','ip_geo','cell_tower','wifi','witness','geocode','manual');
CREATE TYPE geocode_provider AS ENUM
  ('google','radar','nominatim','osm','manual');

-- =====================================================================
-- 1. RAW TIER  (schema evidence — agents read-only, ingestion-written)
-- =====================================================================

-- 1.1 Raw GPS fixes (MP 1727). Adopts TraceIQ point-level fixes.
CREATE TABLE evidence.gps_point (
  id             uuid PRIMARY KEY DEFAULT uuidv7(),
  source_id      uuid NOT NULL REFERENCES evidence.source(id),
  file_node_id   uuid REFERENCES evidence.file_node(id),
  device_id      uuid REFERENCES analysis.device(id),
  geog           geo_point NOT NULL,                       -- reuse 0004 domain
  captured_at    timestamptz,
  captured_raw   text,                                     -- verbatim source ts string (never discarded)
  ts_precision   precision_class NOT NULL DEFAULT 'exact',
  accuracy_m     numeric(8,2),
  point_sequence bigint,                                   -- order by sequence, NOT timestamp (E3 §D)
  raw_data       jsonb NOT NULL DEFAULT '{}'::jsonb,       -- C11 byte-faithful payload
  data_tier      evidence_tier NOT NULL DEFAULT 'raw' CHECK (data_tier = 'raw'),
  ingested_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_gps_point_geog    ON evidence.gps_point USING gist (geog);
CREATE INDEX idx_gps_point_devtime ON evidence.gps_point (device_id, captured_at);
CREATE INDEX idx_gps_point_source  ON evidence.gps_point (source_id);
CREATE INDEX idx_gps_point_seq     ON evidence.gps_point (source_id, point_sequence);
CREATE INDEX idx_gps_point_raw     ON evidence.gps_point USING gin (raw_data);

-- 1.2 Raw Google-Timeline VISIT objects (E3 §B visits). Stay-point source.
CREATE TABLE evidence.raw_visit (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  source_id       uuid NOT NULL REFERENCES evidence.source(id),
  file_node_id    uuid REFERENCES evidence.file_node(id),
  event_serial    bigint,                                  -- authoritative ordering (not ts)
  hierarchy_level int,
  start_raw       text, end_raw text,                      -- verbatim Google strings
  start_utc       timestamptz, end_utc timestamptz,
  tz_offset_min   int,
  duration_s      bigint,
  detection_probability confidence,                        -- visit_detection_probability
  semantic_type   text,                                    -- HOME/WORK/SHOPPING…
  semantic_probability confidence,
  place_id        text,                                    -- provider place ref
  geog            geo_point,                               -- visit_geopair → point
  parent_id       uuid REFERENCES evidence.raw_visit(id),
  memory_id       uuid,
  raw_data        jsonb NOT NULL DEFAULT '{}'::jsonb,
  data_tier       evidence_tier NOT NULL DEFAULT 'raw' CHECK (data_tier = 'raw'),
  ingested_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_raw_visit_source ON evidence.raw_visit (source_id);
CREATE INDEX idx_raw_visit_geog   ON evidence.raw_visit USING gist (geog);
CREATE INDEX idx_raw_visit_utc    ON evidence.raw_visit (start_utc);

-- 1.3 Raw Google-Timeline ACTIVITY objects (E3 §B activities). Movement segments.
CREATE TABLE evidence.raw_activity (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  source_id       uuid NOT NULL REFERENCES evidence.source(id),
  file_node_id    uuid REFERENCES evidence.file_node(id),
  event_serial    bigint,
  start_raw       text, end_raw text,
  start_utc       timestamptz, end_utc timestamptz,
  tz_offset_min   int,
  duration_s      bigint,
  activity_type   text,                                    -- IN_PASSENGER_VEHICLE/WALKING…
  activity_probability confidence,
  distance_m      numeric(12,2),
  start_geog      geo_point,
  end_geog        geo_point,
  place_id_start  text, place_id_end text,
  parent_id       uuid,
  memory_id       uuid,
  raw_data        jsonb NOT NULL DEFAULT '{}'::jsonb,
  data_tier       evidence_tier NOT NULL DEFAULT 'raw' CHECK (data_tier = 'raw'),
  ingested_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_raw_activity_source ON evidence.raw_activity (source_id);
CREATE INDEX idx_raw_activity_start  ON evidence.raw_activity USING gist (start_geog);
CREATE INDEX idx_raw_activity_utc    ON evidence.raw_activity (start_utc);

-- 1.4 Raw exploded PATH waypoints (E3 §B timeline_paths / §D waypoints) — multi-device split.
CREATE TABLE evidence.raw_path (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  source_id          uuid NOT NULL REFERENCES evidence.source(id),
  file_node_id       uuid REFERENCES evidence.file_node(id),
  path_serial        bigint,
  point_sequence     bigint NOT NULL,                      -- 1-based; CRITICAL ordering (E3 §D)
  point_geog         geo_point NOT NULL,
  point_ts_raw       text,
  point_ts_utc       timestamptz,
  tz_offset_min      int,
  multi_device_split boolean NOT NULL DEFAULT false,       -- 100 m threshold (E3 §D)
  device_index       int,
  split_from_segment text,
  aligned_activity_id uuid REFERENCES evidence.raw_activity(id),
  parent_id          uuid REFERENCES evidence.raw_path(id),
  raw_data           jsonb NOT NULL DEFAULT '{}'::jsonb,
  data_tier          evidence_tier NOT NULL DEFAULT 'raw' CHECK (data_tier = 'raw'),
  ingested_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_raw_path_source ON evidence.raw_path (source_id, path_serial, point_sequence);
CREATE INDEX idx_raw_path_geog   ON evidence.raw_path USING gist (point_geog);
CREATE INDEX idx_raw_path_split  ON evidence.raw_path (device_index) WHERE multi_device_split;

-- 1.5 Raw TRIP objects (E3 §B memories_trips).
CREATE TABLE evidence.raw_trip (
  id              uuid PRIMARY KEY DEFAULT uuidv7(),
  source_id       uuid NOT NULL REFERENCES evidence.source(id),
  file_node_id    uuid REFERENCES evidence.file_node(id),
  event_serial    bigint,
  start_raw       text, end_raw text,
  start_utc       timestamptz, end_utc timestamptz,
  tz_offset_min   int,
  duration_s      bigint,
  distance_from_origin_km numeric(12,3),
  destination_place_ids text[],
  parent_id       uuid REFERENCES evidence.raw_trip(id),
  raw_data        jsonb NOT NULL DEFAULT '{}'::jsonb,
  data_tier       evidence_tier NOT NULL DEFAULT 'raw' CHECK (data_tier = 'raw'),
  ingested_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_raw_trip_source ON evidence.raw_trip (source_id);
CREATE INDEX idx_raw_trip_utc    ON evidence.raw_trip (start_utc);

-- =====================================================================
-- 2. EXTRACTED / INFERRED / ANALYTICAL TIER (schema analysis)
-- =====================================================================

-- 2.1 Canonical place registry (MP 1732). Adopts normalized_geo_v5 location_key dedup;
--     PostGIS generated geohash replaces manual geohash (A3 §111).
CREATE TABLE analysis.location (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  name               text,
  geog               geo_point NOT NULL,                   -- reuse 0004 domain
  geohash9           text GENERATED ALWAYS AS (ST_GeoHash(geog::geometry, 9)) STORED,
  address            text,
  place_type         text,
  is_fuzzed          boolean NOT NULL DEFAULT false,       -- TraceIQ location_fuzzy (privacy-rounded)
  sensitivity_tier   sensitivity_tier NOT NULL DEFAULT 'restricted',  -- renamed 0004 enum
  spatial_confidence confidence,
  data_tier          evidence_tier NOT NULL DEFAULT 'extracted'
                       CHECK (data_tier IN ('extracted','inferred','analytical')),
  provenance_id      uuid NOT NULL REFERENCES analysis.provenance(id),
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_location_dedup   ON analysis.location (geohash9, coalesce(name,''));
CREATE INDEX        idx_location_geog   ON analysis.location USING gist (geog);
CREATE INDEX        idx_location_name_trgm ON analysis.location USING gin (name gin_trgm_ops);

-- 2.2 Extracted GPS tracks (MP 1728). LineString → raw geography (geo_point is Point-only).
CREATE TABLE analysis.gps_track (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  device_id     uuid REFERENCES analysis.device(id),
  source_id     uuid REFERENCES evidence.source(id),
  geog          geography(LineString,4326) NOT NULL,
  started_at    timestamptz, ended_at timestamptz,
  point_count   int,
  data_tier     evidence_tier NOT NULL DEFAULT 'extracted' CHECK (data_tier = 'extracted'),
  provenance_id uuid NOT NULL REFERENCES analysis.provenance(id),
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_gps_track_geog    ON analysis.gps_track USING gist (geog);
CREATE INDEX idx_gps_track_devtime ON analysis.gps_track (device_id, started_at);

-- 2.3 Inferred stay points / dwell (MP 1729).
CREATE TABLE analysis.stay_point (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  track_id           uuid REFERENCES analysis.gps_track(id),
  location_id        uuid REFERENCES analysis.location(id),
  device_id          uuid REFERENCES analysis.device(id),
  geog               geo_point NOT NULL,
  arrived_at         timestamptz, departed_at timestamptz,
  dwell_s            bigint,
  spatial_confidence confidence,
  requires_human_review boolean NOT NULL DEFAULT false,
  review_status      review_state NOT NULL DEFAULT 'unreviewed',
  data_tier          evidence_tier NOT NULL DEFAULT 'inferred' CHECK (data_tier = 'inferred'),
  provenance_id      uuid NOT NULL REFERENCES analysis.provenance(id),
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_stay_point_geog ON analysis.stay_point USING gist (geog);
CREATE INDEX idx_stay_point_loc  ON analysis.stay_point (location_id);

-- 2.4 Geofences (MP 1731). Polygon → raw geography.
CREATE TABLE analysis.geofence (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  name          text NOT NULL,
  geog          geography(Polygon,4326) NOT NULL,
  purpose       text,
  data_tier     evidence_tier NOT NULL DEFAULT 'analytical' CHECK (data_tier = 'analytical'),
  provenance_id uuid NOT NULL REFERENCES analysis.provenance(id),
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_geofence_geog ON analysis.geofence USING gist (geog);

-- 2.5 Detected home/base (adopts TraceIQ home_base). Inferred.
CREATE TABLE analysis.home_base (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  entity_id          uuid REFERENCES analysis.entity(id),
  location_id        uuid REFERENCES analysis.location(id),
  spatial_confidence confidence,
  typical_schedule   jsonb NOT NULL DEFAULT '{}'::jsonb,
  requires_human_review boolean NOT NULL DEFAULT false,
  review_status      review_state NOT NULL DEFAULT 'unreviewed',
  data_tier          evidence_tier NOT NULL DEFAULT 'inferred' CHECK (data_tier = 'inferred'),
  provenance_id      uuid NOT NULL REFERENCES analysis.provenance(id),
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_home_base_entity ON analysis.home_base (entity_id);

-- 2.6 Polymorphic location ASSERTIONS (MP 1733-1738): event/message/person/device → place.
CREATE TABLE analysis.location_assertion (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  subject_type       text NOT NULL CHECK (subject_type IN ('event','message','person','device','media')),
  subject_id         uuid NOT NULL,
  location_id        uuid REFERENCES analysis.location(id),
  geog               geo_point,
  asserted_at_ts     timestamptz,
  ts_precision       precision_class NOT NULL DEFAULT 'inferred',
  spatial_confidence confidence,
  assertion_source   assertion_source NOT NULL,            -- gps/claimed_text/exif/ip…
  evidence_strength  strength_class,
  requires_human_review boolean NOT NULL DEFAULT false,
  review_status      review_state NOT NULL DEFAULT 'unreviewed',
  safe_for_legal_use boolean NOT NULL DEFAULT false,
  data_tier          evidence_tier NOT NULL DEFAULT 'inferred'
                       CHECK (data_tier IN ('inferred','analytical')),
  provenance_id      uuid NOT NULL REFERENCES analysis.provenance(id),
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_locassert_subject ON analysis.location_assertion (subject_type, subject_id);
CREATE INDEX idx_locassert_geog    ON analysis.location_assertion USING gist (geog);
CREATE INDEX idx_locassert_review  ON analysis.location_assertion (review_status)
                                     WHERE requires_human_review;

-- 2.7 Location CONTRADICTIONS (MP 1739-1740): claimed vs observed conflict. HITL-gated.
--     Adopts normalized_geo_v5 dual-provider disagreement_flag/tie_break_reason model.
CREATE TABLE analysis.location_contradiction (
  id                    uuid PRIMARY KEY DEFAULT uuidv7(),
  claimed_assertion_id  uuid NOT NULL REFERENCES analysis.location_assertion(id),
  observed_assertion_id uuid NOT NULL REFERENCES analysis.location_assertion(id),
  distance_m            numeric(12,2),
  disagreement_flag     boolean NOT NULL DEFAULT false,
  tie_break_reason      text,
  analysis_confidence   confidence,
  requires_human_review boolean NOT NULL DEFAULT true,
  review_status         review_state NOT NULL DEFAULT 'unreviewed',
  safe_for_legal_use    boolean NOT NULL DEFAULT false,
  data_tier             evidence_tier NOT NULL DEFAULT 'analytical' CHECK (data_tier = 'analytical'),
  provenance_id         uuid NOT NULL REFERENCES analysis.provenance(id),
  created_at            timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_loc_contra_distinct CHECK (claimed_assertion_id <> observed_assertion_id)
);
CREATE INDEX idx_loc_contra_claimed  ON analysis.location_contradiction (claimed_assertion_id);
CREATE INDEX idx_loc_contra_observed ON analysis.location_contradiction (observed_assertion_id);
CREATE INDEX idx_loc_contra_review   ON analysis.location_contradiction (review_status)
                                       WHERE requires_human_review;

-- =====================================================================
-- 3. GEOCODE PIPELINE  (extracted tier; adopts normalized_geo_v5 lane verbatim)
-- =====================================================================

-- 3.1 Geocode request log (append-only) (A3 §113).
CREATE TABLE analysis.geocode_request (
  id            uuid PRIMARY KEY DEFAULT uuidv7(),
  query         text NOT NULL,
  geog          geo_point,                                 -- coords for reverse geocode
  status        text NOT NULL DEFAULT 'pending',
  data_tier     evidence_tier NOT NULL DEFAULT 'extracted' CHECK (data_tier = 'extracted'),
  provenance_id uuid REFERENCES analysis.provenance(id),
  requested_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_geocode_request_status ON analysis.geocode_request (status, requested_at);

-- 3.2 Per-provider geocode result (merges TraceIQ caches + v5 results, A3 §114).
CREATE TABLE analysis.geocode_result (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  request_id  uuid NOT NULL REFERENCES analysis.geocode_request(id),
  provider    geocode_provider NOT NULL,
  place_id    text,
  address     text,
  geog        geo_point,
  confidence  confidence,
  bounds      jsonb,
  raw_json    jsonb NOT NULL DEFAULT '{}'::jsonb,
  data_tier   evidence_tier NOT NULL DEFAULT 'extracted' CHECK (data_tier = 'extracted'),
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_geocode_result_req      ON analysis.geocode_result (request_id);
CREATE INDEX idx_geocode_result_place    ON analysis.geocode_result (provider, place_id);

-- 3.3 Dual-provider tie-break (A3 §115) — adopted verbatim from normalized_geo_v5.
CREATE TABLE analysis.geocode_resolution (
  id                 uuid PRIMARY KEY DEFAULT uuidv7(),
  request_id         uuid NOT NULL REFERENCES analysis.geocode_request(id),
  location_id        uuid REFERENCES analysis.location(id),
  preferred_provider geocode_provider,
  chosen_result_id   uuid REFERENCES analysis.geocode_result(id),
  distance_m         numeric(12,2),                        -- inter-provider disagreement distance
  disagreement_flag  boolean NOT NULL DEFAULT false,
  tie_break_reason   text,
  data_tier          evidence_tier NOT NULL DEFAULT 'extracted' CHECK (data_tier = 'extracted'),
  provenance_id      uuid REFERENCES analysis.provenance(id),
  resolved_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_geocode_resolution_req ON analysis.geocode_resolution (request_id);

-- 3.4 Append-only geocode action log (A3 §116, C10).
CREATE TABLE analysis.geocode_audit (
  id          uuid PRIMARY KEY DEFAULT uuidv7(),
  request_id  uuid REFERENCES analysis.geocode_request(id),
  action      text NOT NULL,
  actor_kind  text,                                        -- human/service/agent
  detail      jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_geocode_audit_req ON analysis.geocode_audit (request_id, occurred_at);

-- Append-only enforcement for geocode_audit + raw evidence tables: no UPDATE/DELETE
-- granted to the agent/ingestion roles (REVOKE), backed by a no-mutate trigger (see M5).
```

---

## 3. Decision table

Classification vocab: **adopt** (carry as-is) / **adapt** (carry with change) / **merge** (fold
sources together) / **split** (one source → several) / **deprecate** (drop). Source =
as-built (E1) / paper (§03 §6) / which prior file (E3 §A–D / A3 §A–F).

| Table / field | Decision | Source | Note |
|---|---|---|---|
| **Schema homing** `geo.*` → `evidence`/`analysis` | **adapt** | as-built E1 §0 | Paper's top-level `geo` schema is illegal; re-home by data-tier into the 3-schema boundary. |
| `evidence.gps_point` | adopt | paper `geo.gps_point` + E3 §B/D | Raw fix; reuse `geo_point` domain; `point_sequence` for ordering. |
| `evidence.raw_visit` | adopt | E3 §B `visits` / A3 §B | Raw Google VISIT; stay-point source; `event_serial` ordering. |
| `evidence.raw_activity` | adopt | E3 §B `activities` | Raw movement segment; start/end geopair. |
| `evidence.raw_path` | adopt | E3 §B `timeline_paths` + §D `waypoints` | **Merged** the two identical waypoint models; `multi_device_split`/`device_index`/`split_from_segment` (100 m). |
| `evidence.raw_trip` | adopt | E3 §B `memories_trips` | Raw trip object. |
| `analysis.location` | merge | paper `geo.location` + E3 §C `location_key` + TraceIQ `location_fuzzy` | Canonical dedup; `geohash9` **generated** (was manual, A3 §111); `is_fuzzed` + `sensitivity_tier` preserve privacy-rounding. |
| `analysis.gps_track` | adopt | paper `geo.gps_track` + TraceIQ `timeline_paths` | Extracted LineString → raw `geography(LineString)` (domain is Point-only). |
| `analysis.stay_point` | adopt | paper `geo.stay_point` + E3 §B `visits` | **Inferred** dwell; HITL fields. |
| `analysis.trip` (paper) | merge→`evidence.raw_trip` | paper `geo.trip` | `memories_trips` is a **raw** Google object → demoted to `evidence` raw tier (lane discipline), not a separate analysis table. |
| `analysis.geofence` | adopt | paper `geo.geofence` | Analytical Polygon. |
| `analysis.home_base` | adapt | TraceIQ `home_base` (A3 §C) | Inferred; `typical_schedule jsonb`; HITL. |
| `analysis.location_assertion` | adopt | paper `geo.location_assertion` (MP 1733-38) | Polymorphic spatial link; `assertion_source` enum new; `safe_for_legal_use` added. |
| `analysis.location_contradiction` | merge | paper + E3 §C `geocode_resolution` + TraceIQ `location_confidence` | Claimed-vs-observed; `disagreement_flag`/`tie_break_reason`; HITL default `true`. |
| `analysis.geocode_request` | adapt | E3 §C `geocode_request` | append-only log. |
| `analysis.geocode_result` | merge | E3 §C `geocode_result_google/_radar` + TraceIQ `google/radar_api_cache` | Per-provider rows via `provider` enum (was 2 tables / 2 caches). |
| `analysis.geocode_resolution` | **adopt verbatim** | E3 §C `geocode_resolution` | Best prior art — `preferred_provider`/`distance_m`/`disagreement_flag`/`tie_break_reason`. |
| `analysis.geocode_audit` | adopt | E3 §C `geocode_audit` | Append-only (C10). |
| `geo_point` domain | adopt (reuse) | as-built 0004 | Point columns only; not redefined. |
| `confidence` domain | adopt (reuse) | as-built 0004 | All `*_confidence` columns. |
| `sensitivity_tier` (was `disclosure_tier` enum) | adapt (rename) | as-built 0004 §5.1 bug | Consumed on `location`; rename owned by shared migration M2. |
| `geohash8`, `lat_r3/r4/r5`, `lng_r3/r4/r5` | deprecate | E3 §C `event_geokey` | Replaced by single PostGIS-generated `geohash9` + native `geog`. |
| `enrichment_queue` | deprecate (→pipeline) | E3 §B / A3 §B | Operational job state (n8n/Windmill), not evidentiary DB. |
| `data_quality_metrics` + trigger | deprecate (→observability) | E3 §B | Re-implement as a DQ job, not a canonical table (out of D5 scope). |
| `vw_place_analytics`/`vw_route_patterns`/`vw_city_summary` | defer (→DuckDB analytics) | E3 §B | Analytical views over these tables; built in the analytics lane via pg_duckdb. |
| `vw_bouncy_trips` | defer-as-hypothesis | E3 §B / A3 §B | Surveillance-pattern anomaly view → HITL, lives in analysis/SurrealDB, not D5 base DDL. |
| `assertion_source`, `geocode_provider` enums | new | this domain | Geo-specific; created once. |
| GeoJSON projection to SurrealDB | adopt (note) | CONTEXT_PACK §1 / ADR-0024 | `ST_AsGeoJSON` over **approved** assertions only; no spatial index duplicated downstream. |

---

## 4. Migration notes (live DB → this state)

Apply in dependency order against the live `agno-postgres:18-duckdb`. **Acceptance step
(verify-before-claiming, addendum §D.9):** diff this DDL against the live `information_schema`
before writing the migration; confirm PostGIS + the `0004` types are actually present (both are
apply-once / guarded and may be absent on the live `pgdata` volume).

- **M1 — PostGIS present.** Confirm `CREATE EXTENSION IF NOT EXISTS postgis;` succeeded on the
  live image (E1 §5.6: guarded, may have been skipped with a NOTICE on a stock image). If absent,
  no `geo_point`/`gist(geog)` object can be created — this is a hard blocker; rebuild on the
  custom image first.
- **M2 — disclosure_tier rename (shared, blocks `analysis.location`).** `ALTER TYPE
  disclosure_tier RENAME TO sensitivity_tier;` for the `0004` enum (`public/restricted/sealed`).
  Leave `analysis.normalized_record.disclosure_tier` (TEXT CHECK `contemporaneous/hindsight/
  discovered`) untouched — that is the substantive bitemporal column (E1 §5.1). This is a global
  fix; D5 only consumes the renamed enum.
- **M3 — shared §0.1 types.** Ensure `evidence_tier`, `precision_class`, `strength_class`,
  `review_state` exist (created by the shared reconciliation migration). Ensure `0004` types
  (`confidence`, `geo_point`, `source_system`, `source_ref`) are applied (run
  `psql -f sql/0004_custom_types.sql` if the live volume predates it — E1 §3 apply-once caveat).
- **M4 — dependency-domain tables.** This domain FKs to `evidence.source`, `evidence.file_node`
  (D1 custody), `analysis.entity`/`analysis.device` (D3 entity), and `analysis.provenance`
  (Dprov). Land those domains first, OR stage D5 with the FK lines commented and add them via
  `ALTER TABLE … ADD CONSTRAINT` once the referents exist. Do **not** invent stub referents.
- **M5 — create geo enums + tables.** Run §0a then §1–§3 of the DDL block (all `CREATE`,
  additive — no `ALTER`/`DROP` on existing as-built tables, so the migration is reversible by
  `DROP` of the new objects). Then enforce append-only on `evidence.gps_point`/`raw_*` and
  `analysis.geocode_audit`: `REVOKE UPDATE, DELETE … FROM <agent_role>, <ingestion_role>;` plus a
  `BEFORE UPDATE OR DELETE` no-mutate trigger (custody guarantee, C10).
- **M6 — read-only boundary.** Confirm the agent `readonly_engine` role has `USAGE` on `evidence`
  and `SELECT` on the new `evidence.*` geo tables, and **no write** — the boundary is
  connection-enforced (E1 §6), not prompt-enforced. `analysis.*` geo writes go through the
  approval-gated writer role only.
- **M7 — DuckDB analytics (no DDL here).** The deferred analytical views (`vw_place_analytics`,
  routes, city summaries) read these tables via `pg_duckdb` inside the same resource — they are
  built in the analytics lane, not as base D5 objects.
