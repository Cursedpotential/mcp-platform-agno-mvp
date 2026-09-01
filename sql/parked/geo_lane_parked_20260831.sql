-- geo_lane_parked_20260831.sql
-- THE GEO / LOCATION LANE — PARKED BY OWNER RULING (D-121, 2026-08-31).
-- Owner: "that is the use for those tables, the code will come later...
-- I don't want to recreate them later so back them up... why am I gonna
-- bring in the key to the application I've been working on even longer
-- than this, just to have it fucked up too."
-- RESTORE: run this one file. Two-phase: tables first, then constraints
-- and indexes, so intra-lane FKs resolve regardless of order.
-- Generated 2026-09-01T03:34:47.199843+00:00 from live platform.
-- Amended 2026-09-01: FK targets requalified reference.* -> registry.* after migration 0062
-- (D-120 registry split); restore-proof of 2026-08-31 predates the move.
SET client_min_messages = warning;

-- ===== phase 1: tables =====
CREATE TABLE IF NOT EXISTS working.stay_point (
  id uuid DEFAULT uuidv7() NOT NULL,
  track_id uuid,
  location_id uuid,
  device_id uuid,
  geog ai.geo_point NOT NULL,
  arrived_at timestamp with time zone,
  departed_at timestamp with time zone,
  dwell_s bigint,
  spatial_confidence ai.confidence,
  requires_human_review boolean DEFAULT false NOT NULL,
  review_status review_state DEFAULT 'unreviewed'::review_state NOT NULL,
  data_tier evidence_tier DEFAULT 'inferred'::evidence_tier NOT NULL,
  provenance_id uuid,
  created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS working.gps_track (
  id uuid DEFAULT uuidv7() NOT NULL,
  device_id uuid,
  source_id uuid,
  geog geography(LineString,4326) NOT NULL,
  started_at timestamp with time zone,
  ended_at timestamp with time zone,
  point_count integer,
  data_tier evidence_tier DEFAULT 'extracted'::evidence_tier NOT NULL,
  provenance_id uuid,
  created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS working.geocode_request (
  id uuid DEFAULT uuidv7() NOT NULL,
  query text NOT NULL,
  geog ai.geo_point,
  status text DEFAULT 'pending'::text NOT NULL,
  data_tier evidence_tier DEFAULT 'extracted'::evidence_tier NOT NULL,
  provenance_id uuid,
  requested_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS working.geocode_resolution (
  id uuid DEFAULT uuidv7() NOT NULL,
  request_id uuid NOT NULL,
  location_id uuid,
  preferred_provider geocode_provider,
  chosen_result_id uuid,
  distance_m numeric(12,2),
  disagreement_flag boolean DEFAULT false NOT NULL,
  tie_break_reason text,
  data_tier evidence_tier DEFAULT 'extracted'::evidence_tier NOT NULL,
  provenance_id uuid,
  resolved_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS working.geocode_result (
  id uuid DEFAULT uuidv7() NOT NULL,
  request_id uuid NOT NULL,
  provider geocode_provider NOT NULL,
  place_id text,
  address text,
  geog ai.geo_point,
  confidence ai.confidence,
  bounds jsonb,
  raw_json jsonb DEFAULT '{}'::jsonb NOT NULL,
  data_tier evidence_tier DEFAULT 'extracted'::evidence_tier NOT NULL,
  created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS working.home_base (
  id uuid DEFAULT uuidv7() NOT NULL,
  entity_id uuid,
  location_id uuid,
  spatial_confidence ai.confidence,
  typical_schedule jsonb DEFAULT '{}'::jsonb NOT NULL,
  requires_human_review boolean DEFAULT false NOT NULL,
  review_status review_state DEFAULT 'unreviewed'::review_state NOT NULL,
  data_tier evidence_tier DEFAULT 'inferred'::evidence_tier NOT NULL,
  provenance_id uuid,
  created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS working.waypoint_device_split (
  split_id uuid DEFAULT uuidv7() NOT NULL,
  raw_path_id uuid NOT NULL,
  device_index integer NOT NULL,
  split_from_activity uuid,
  threshold_meters numeric DEFAULT 100 NOT NULL,
  certainty precision_class DEFAULT 'inferred'::precision_class NOT NULL,
  confidence ai.confidence,
  requires_human_review boolean DEFAULT false NOT NULL,
  ingest_run_id uuid,
  author text NOT NULL,
  asserted_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS working.vehicle (
  id uuid NOT NULL,
  plate citext,
  make_model text,
  owner_entity_id uuid
);

CREATE TABLE IF NOT EXISTS reference.geofence (
  id uuid DEFAULT uuidv7() NOT NULL,
  name text NOT NULL,
  geog geography(Polygon,4326) NOT NULL,
  purpose text,
  data_tier evidence_tier DEFAULT 'analytical'::evidence_tier NOT NULL,
  provenance_id uuid,
  created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS ops.geocode_audit (
  id uuid DEFAULT uuidv7() NOT NULL,
  request_id uuid,
  action text NOT NULL,
  actor_kind text,
  detail jsonb DEFAULT '{}'::jsonb NOT NULL,
  occurred_at timestamp with time zone DEFAULT now() NOT NULL
);

-- ===== phase 2: constraints =====
ALTER TABLE working.stay_point ADD CONSTRAINT stay_point_pkey PRIMARY KEY (id);
ALTER TABLE working.gps_track ADD CONSTRAINT gps_track_pkey PRIMARY KEY (id);
ALTER TABLE working.geocode_request ADD CONSTRAINT geocode_request_pkey PRIMARY KEY (id);
ALTER TABLE working.geocode_resolution ADD CONSTRAINT geocode_resolution_pkey PRIMARY KEY (id);
ALTER TABLE working.geocode_result ADD CONSTRAINT geocode_result_pkey PRIMARY KEY (id);
ALTER TABLE working.home_base ADD CONSTRAINT home_base_pkey PRIMARY KEY (id);
ALTER TABLE working.waypoint_device_split ADD CONSTRAINT waypoint_device_split_pkey PRIMARY KEY (split_id);
ALTER TABLE working.vehicle ADD CONSTRAINT vehicle_pkey PRIMARY KEY (id);
ALTER TABLE reference.geofence ADD CONSTRAINT geofence_pkey PRIMARY KEY (id);
ALTER TABLE ops.geocode_audit ADD CONSTRAINT geocode_audit_pkey PRIMARY KEY (id);
ALTER TABLE working.stay_point ADD CONSTRAINT stay_point_data_tier_check CHECK ((data_tier = 'inferred'::evidence_tier));
ALTER TABLE working.gps_track ADD CONSTRAINT gps_track_data_tier_check CHECK ((data_tier = 'extracted'::evidence_tier));
ALTER TABLE working.geocode_request ADD CONSTRAINT geocode_request_data_tier_check CHECK ((data_tier = 'extracted'::evidence_tier));
ALTER TABLE working.geocode_resolution ADD CONSTRAINT geocode_resolution_data_tier_check CHECK ((data_tier = 'extracted'::evidence_tier));
ALTER TABLE working.geocode_result ADD CONSTRAINT geocode_result_data_tier_check CHECK ((data_tier = 'extracted'::evidence_tier));
ALTER TABLE working.home_base ADD CONSTRAINT home_base_data_tier_check CHECK ((data_tier = 'inferred'::evidence_tier));
ALTER TABLE reference.geofence ADD CONSTRAINT geofence_data_tier_check CHECK ((data_tier = 'analytical'::evidence_tier));
ALTER TABLE working.stay_point ADD CONSTRAINT stay_point_track_id_fkey FOREIGN KEY (track_id) REFERENCES working.gps_track(id);
ALTER TABLE working.stay_point ADD CONSTRAINT stay_point_device_id_fkey FOREIGN KEY (device_id) REFERENCES registry.device(id);
ALTER TABLE working.stay_point ADD CONSTRAINT stay_point_location_id_fkey FOREIGN KEY (location_id) REFERENCES registry.location(id);
ALTER TABLE working.stay_point ADD CONSTRAINT stay_point_provenance_id_fkey FOREIGN KEY (provenance_id) REFERENCES ops.processing_run(run_id);
ALTER TABLE working.gps_track ADD CONSTRAINT gps_track_source_id_fkey FOREIGN KEY (source_id) REFERENCES evidence.source(id);
ALTER TABLE working.gps_track ADD CONSTRAINT gps_track_device_id_fkey FOREIGN KEY (device_id) REFERENCES registry.device(id);
ALTER TABLE working.gps_track ADD CONSTRAINT gps_track_provenance_id_fkey FOREIGN KEY (provenance_id) REFERENCES ops.processing_run(run_id);
ALTER TABLE working.geocode_request ADD CONSTRAINT geocode_request_provenance_id_fkey FOREIGN KEY (provenance_id) REFERENCES ops.processing_run(run_id);
ALTER TABLE working.geocode_resolution ADD CONSTRAINT geocode_resolution_location_id_fkey FOREIGN KEY (location_id) REFERENCES registry.location(id);
ALTER TABLE working.geocode_resolution ADD CONSTRAINT geocode_resolution_chosen_result_id_fkey FOREIGN KEY (chosen_result_id) REFERENCES working.geocode_result(id);
ALTER TABLE working.geocode_resolution ADD CONSTRAINT geocode_resolution_provenance_id_fkey FOREIGN KEY (provenance_id) REFERENCES ops.processing_run(run_id);
ALTER TABLE working.geocode_resolution ADD CONSTRAINT geocode_resolution_request_id_fkey FOREIGN KEY (request_id) REFERENCES working.geocode_request(id);
ALTER TABLE working.geocode_result ADD CONSTRAINT geocode_result_request_id_fkey FOREIGN KEY (request_id) REFERENCES working.geocode_request(id);
ALTER TABLE working.home_base ADD CONSTRAINT home_base_entity_id_fkey FOREIGN KEY (entity_id) REFERENCES registry.entity(id);
ALTER TABLE working.home_base ADD CONSTRAINT home_base_provenance_id_fkey FOREIGN KEY (provenance_id) REFERENCES ops.processing_run(run_id);
ALTER TABLE working.home_base ADD CONSTRAINT home_base_location_id_fkey FOREIGN KEY (location_id) REFERENCES registry.location(id);
ALTER TABLE working.waypoint_device_split ADD CONSTRAINT waypoint_device_split_ingest_run_id_fkey FOREIGN KEY (ingest_run_id) REFERENCES ops.processing_run(run_id);
ALTER TABLE working.waypoint_device_split ADD CONSTRAINT waypoint_device_split_raw_path_id_fkey FOREIGN KEY (raw_path_id) REFERENCES raw.raw_path(id);
ALTER TABLE working.waypoint_device_split ADD CONSTRAINT waypoint_device_split_split_from_activity_fkey FOREIGN KEY (split_from_activity) REFERENCES raw.raw_activity(id);
ALTER TABLE working.vehicle ADD CONSTRAINT vehicle_id_fkey FOREIGN KEY (id) REFERENCES registry.entity(id) ON DELETE CASCADE;
ALTER TABLE working.vehicle ADD CONSTRAINT vehicle_owner_entity_id_fkey FOREIGN KEY (owner_entity_id) REFERENCES registry.entity(id);
ALTER TABLE reference.geofence ADD CONSTRAINT geofence_provenance_id_fkey FOREIGN KEY (provenance_id) REFERENCES ops.processing_run(run_id);
ALTER TABLE ops.geocode_audit ADD CONSTRAINT geocode_audit_request_id_fkey FOREIGN KEY (request_id) REFERENCES working.geocode_request(id);

-- ===== phase 3: indexes =====
CREATE INDEX IF NOT EXISTS idx_stay_point_geog ON working.stay_point USING gist (geog);
CREATE INDEX IF NOT EXISTS idx_gps_track_geog ON working.gps_track USING gist (geog);
CREATE INDEX IF NOT EXISTS idx_geocode_result_req ON working.geocode_result USING btree (request_id);
CREATE INDEX IF NOT EXISTS idx_wds_path ON working.waypoint_device_split USING btree (raw_path_id);
CREATE INDEX IF NOT EXISTS idx_geofence_geog ON reference.geofence USING gist (geog);
CREATE INDEX IF NOT EXISTS idx_geocode_audit_req ON ops.geocode_audit USING btree (request_id, occurred_at);

-- ===== comments =====

