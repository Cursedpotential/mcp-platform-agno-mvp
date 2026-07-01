# E3 — Timeline / Geo / Location Schemas (Prior-Iteration Corpus)

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
> Extraction lane E3 of the forensic-db reconciliation. Pulls every timeline-event,
> waypoint/path/trip/visit/stay-point, geocode-resolution, multi-device-split,
> processing-metadata, and data-quality table+column from the four richest prior
> iterations. Source-of-truth for the location/temporal lane of the forensic DB.

## Sources extracted
| # | File | Engine | Role |
|---|------|--------|------|
| A | `dev-resources/Archives/Voice_Analysis/Context_Analysis_Suite/Chat_Parser_App/timeline_ingestion_schema.sql` | PostgreSQL 14+ | 24-table generic timeline-ingestion spine (events/chat/life/locations + views/triggers/functions) — **richest architecture** |
| B | `dev-resources/Archives/TheBigOne/TraceIQ/TraceIQ_Main/schema_complete.sql` | SQLite (WAL) | TraceIQ "complete" — enriched Google-Timeline forensic store + analytical views — **richest geo-forensic** |
| C | `dev-resources/Archives/TheBigOne/TraceIQ/TraceIQ_Main/src/normalized_geo_schema_v5.sql` | SQLite | Normalized geo v5 — geokey/geocode-resolution/provider-result split |
| D | `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/Case/COMPLETE_SCHEMA_PARSER_INVENTORY.md` PART 3 | Postgres+PostGIS | Inventory: timeline_events/waypoints/processing_metadata + parsing rules |

---

## A. PostgreSQL generic timeline-ingestion spine (Source A, 24 tables)

Extensions: `uuid-ossp`, `pg_trgm` (fuzzy text), `btree_gist` (exclusion constraints), `pgcrypto`. TimescaleDB optional. PostGIS noted but commented-out (see locations).

### Shared infrastructure
- **sources** — source_id PK, source_name UNIQUE, source_type (CHECK: chat/email/calendar/social/document/location/health/finance/manual/other), source_metadata JSONB, is_active, sync_frequency_minutes, last_sync_at, last_sync_status, timestamps. Intent: register every feed + its sync cadence/health.
- **entities** — entity_id PK, entity_type (user/organization/service/bot), external_id (unique partial idx), display_name, email, metadata JSONB, is_active. Multi-user/actor registry.
- **tags** — tag_id PK, tag_name UNIQUE, tag_category, tag_color hex, parent_tag_id self-FK (hierarchy), usage_count (trigger-maintained). Cross-timeline categorization.

### Core timeline (the generic event spine)
- **timeline_events** — event_id PK; source_id FK (RESTRICT), entity_id FK (SET NULL).
  - Temporal: `event_timestamp` (NOT NULL), `event_end_timestamp` (duration events), `event_timezone` (default UTC).
  - Classification: event_type (message/meeting/transaction/activity…), event_category.
  - Content: title, description, `raw_data` JSONB (original), `processed_data` JSONB (enriched).
  - Linking: external_id, parent_event_id self-FK (CASCADE) — sub-event nesting.
  - Search/scoring: `content_vector` tsvector, `importance_score` NUMERIC(3,2) 0–1.
  - Audit: ingested_at, updated_at, is_deleted/deleted_at (soft delete).
  - Constraints: end ≥ start; importance 0–1; UNIQUE(source_id, external_id).
  - **Indexes** incl. GiST on `tstzrange(start,end)` for overlapping-time queries; GIN on raw_data/processed_data/content_vector; partial-by-is_deleted. Quarter-partition stub.
- **event_attachments** — attachment_id PK, event_id FK CASCADE, attachment_type (file/image/video/audio/link/document), file_name/path/url/size_bytes/mime_type, metadata.
- **event_tags** — (event_id, tag_id) PK m:n, tagged_at, confidence_score (auto-tag).

### Chat extraction sub-lane (extends events)
- **chat_platforms** (platform_id, source_id FK, platform_name, platform_type team/personal/public/private).
- **chat_channels** (channel_id, platform_id FK, external_channel_id, channel_name, channel_type direct/group/channel/thread/broadcast, is_private, participant_count trigger-maintained, archived_at; UNIQUE(platform,external)).
- **chat_participants** (participant_id, channel_id+entity_id UNIQUE, role, joined_at/left_at).
- **chat_messages** — message_id PK = FK→timeline_events (table-inheritance pattern); channel_id, sender_id; parent_message_id + thread_root_id self-FKs; reply_count/reaction_count (trigger-maintained); message_text/html; is_edited/edited_at, is_deleted/deleted_at; `message_vector` tsvector; external_message_id (UNIQUE per channel). Trigram GIN on message_text.
- **message_reactions / message_mentions / message_links** — engagement + URL extraction (url_domain, url_title, preview_image_url).

### Personal-history sub-lane (extends events)
- **life_event_categories** (self-FK hierarchy, icon/color/sort_order; seeded Career/Education/Relationships/Health/Travel/Achievements/Family/Residence/Financial/Hobbies).
- **life_events** — life_event_id PK = FK→timeline_events; entity_id, category_id; event_title/description/**event_location** (free-text); `date_precision` (year/month/day/hour/minute); is_approximate; significance_level (low/medium/high/critical); emotional_valence (positive/negative/neutral/mixed); privacy_level (private/family/friends/public); notes, metadata.
- **relationships** — entity_id_1/2 (CHECK ≠), relationship_type/subtype, started_at/ended_at/is_current, strength 0–1; UNIQUE(e1,e2,type). Powers recursive `get_relationship_network`.
- **life_event_participants** (life_event_id+entity_id, role).

### Location tables (Source A) — **A's geo lane**
- **locations** — location_id PK; location_name, location_type (residence/workplace/venue/city…); address components (street_address, city, state_province, country, postal_code); `latitude NUMERIC(10,7)`, `longitude NUMERIC(10,7)`; metadata; CHECK coords both-null-or-in-range (lat −90..90, lng −180..180). PostGIS/earthdistance GiST index `ll_to_earth(lat,lng)` present **but commented out**.
- **life_event_locations** — (life_event_id, location_id) m:n with `location_role` (primary/secondary/origin/destination).

### Cross-component + audit
- **chat_message_life_events** (link chat→life event; link_type planning/discussing/documenting/related).
- **entity_timeline_associations** (entity↔event; association_type creator/participant/mentioned/related; association_strength).
- **sync_logs** (per-run: records_processed/created/updated/failed, error_details JSONB).
- **audit_trail** (table_name/record_id/action INSERT|UPDATE|DELETE, old_values/new_values JSONB, change_reason).

### Views / functions / triggers (Source A)
- **Materialized views**: `daily_event_summary` (date×source×type counts + avg importance); `entity_activity_summary` (per-entity message/life-event counts + last_activity).
- **Functions**: `search_timeline_events` (FTS websearch_to_tsquery + date/type filters + ts_rank), `get_entity_timeline`, `get_relationship_network` (RECURSIVE, max_depth).
- **Triggers**: updated_at touch; tsvector maintenance for events & messages; tag usage_count; channel participant_count; message reaction/reply counts; soft-delete helper.

---

## B. TraceIQ enriched Google-Timeline store (Source B, SQLite)

The **forensic geo workhorse**. Wide denormalized `timeline_enriched` + normalized source objects (visits/activities/paths/trips) + dual-provider geocode cache + quality lane + analytical views.

### timeline_enriched (the enriched master row — one per timeline event)
PK event_id, `serial_id` UNIQUE (sequence ordering — authoritative, NOT timestamp). Columns by intent:
- **Device/type**: device, event_type (VISIT_START/ACTIVITY_START/etc.), label, day_of_week, duration.
- **Local time**: date_us, time_12h, timestamp_utc, processed_at, created/updated.
- **Google geocode**: google_place_id, google_place_name, google_place_types, google_address.
- **Radar geocode**: radar_place_name, radar_place_type, radar_address.
- **Resolved display**: address_display, address_street, address_city, map_link_coords, map_link_place.
- **Geo keys**: location_geopair (exact "lat,lng"), location_fuzzy (rounded/privacy key — the **join/grouping key** across views).
- **Movement deltas**: distance_miles, delta_duration, delta_distance_meters, delta_duration_seconds.
- **Overnight forensics**: overnight_flag (INT), overnight_type ('spans'/partial).
- **Probabilities**: semantic_type_probability, activity_type_probability, probability (overall confidence — drives evidence-package filter `>0.6`).
- **Provenance/links**: google_api_cache_id FK, radar_api_cache_id FK, source_visit_id, source_activity_id, source_path_id, source_memory_id, original_json (raw), data_source.

### Normalized source tables (raw Google Timeline objects, pre-enrichment)
- **visits** — visit_id PK, event_serial_id UNIQUE, hierarchy_level, start/end timestamp raw+utc+`timezone_offset_minutes`, duration_seconds, `visit_detection_probability`, `semantic_type` + probability, visit_place_id, `visit_geopair`, parent_id, memory_id, meta_json. (**Stay-point / visit lane.**)
- **activities** — activity_id PK, event_serial_id UNIQUE, start/end raw+utc+offset, duration_seconds, `activity_type` + probability, distance_meters, `activity_start_geopair`/`activity_end_geopair` (NOT NULL), activity_place_id_start/_end, parent_id, memory_id. (**Movement segments.**)
- **timeline_paths** — path_id + `point_id` PK (exploded waypoints), parent_id, path_type, start/end raw+utc+offset, duration_seconds, path_start/end_geopair, `waypoints_count`, `point_sequence` (ordering), point_geopair, point_timestamp raw+utc, **multi_device_split INT, device_index, split_from_segment**, aligned_activity_id, meta_json. (**Path/waypoint lane WITH multi-device split logic.**)
- **memories_trips** — memory_id PK, event_serial_id UNIQUE, start/end raw+utc+offset, duration_seconds, `trip_distance_from_origin_km`, `trip_destination_place_ids`, parent_id. (**Trip lane.**)

### Geocode caches (dual provider)
- **google_api_cache** — cache_id PK, place_id UNIQUE, name, formatted_address, types, location_lat/lng, location_fuzzy, viewport NE/SW lat/lng (bounds), maps_url, api_response_json, last_validated.
- **radar_api_cache** — cache_id PK, request_lat/lng, response_lat/lng, `geocode_accuracy_meters`, label/label_type/layer/top_type/types, full address parts (street_number/street/city/state/state_code/postal_code/formatted_address), place_label/address_label, `distance_from_request`, timezone_id/name/code, google_place_id(+_found), **problematic_poi + problematic_notes, manually_verified, custom_label**, batch_file/timestamp, request_coords_fuzzy.

### Enrichment queue + quality
- **enrichment_queue** — queue_id, event_id FK, event_type, request_lat/lng + fuzzy, needs_radar/needs_google flags, priority, event_date/city, attempt_count, last_attempt_at, error_message, status (pending…), completed_at. (Geocode work queue.)
- **data_quality_metrics** — metric_id, check_date, table_name, metric_name, metric_value, threshold_min/max, status CHECK(PASS/WARN/FAIL), details. Fed by trigger `trig_quality_check` (e.g. missing-coordinates-% per day, FAIL if >5%).

### Analytical views (Source B) — the forensic analytics layer
- **vw_place_analytics** — per `location_fuzzy`+place: total_visits, unique_days, avg/min/max minutes (duration string→minutes parse), first/last visit, days_span, arrival-hour extraction (12h→24h), days_of_week_visited, overnight_visits + overnight_percentage, frequency_category bucket (Very Frequent 50+ → Rare 1–4), map links.
- **vw_bouncy_trips** — LAG/LEAD over serial_id to flag back-and-forth city movement: BOUNCY_LEFT / BOUNCY_RETURN / BOUNCY_PING_PONG / NORMAL + is_anomalous. (Anomaly / surveillance pattern.)
- **vw_route_patterns** — prev→curr place & city routes, times_traveled (HAVING >1), avg_distance_miles, first/last traveled. (Recurring routes.)
- **vw_overnight_activity** — overnight_flag=1 rows, overnight_category (Long/Spans/Partial).
- **vw_city_summary** — per city: days_visited, total_events, first/last, overnight_events, total_miles.
- **vw_forensic_evidence_package** — court export: evidence_id, sequence_number, utc+local timestamp, location_name (coalesce google/radar), verified_address, coordinates, map_link, confidence_score, `location_confidence` HIGH/MEDIUM/LOW (both providers vs one vs none), overnight flags, source IDs, raw_evidence (original_json); filtered `probability>0.6`, ordered by serial_id.

---

## C. Normalized geo schema v5 (Source C, SQLite) — geocode-resolution lane

Fully normalized split of geo from event, with multi-precision geokeys and provider-disagreement resolution.
- **timeline_master** — event_uuid PK, event_id, event_type, start/end/point_time, start/end_latlng, `path_time_fallback`, `path_time_source` (path timestamp provenance — the "timestamps lie in 2-hour containers" fix).
- **event_geokey** — event_uuid PK/FK; for start/end/point each: exact latlng, rounded `lat_r3/r4`+`lng_r3/r4`, `geohash8`/`geohash9`. (Multi-resolution spatial keys for fuzzy joins.)
- **location_key** — location_uuid PK, `latlng_exact` UNIQUE, lat_r5/r4, lng_r5/r4, geohash8/9. (Canonical dedup of physical points.)
- **geocode_request** — request_uuid PK, location_uuid FK, latlng at r4/r5/exact6 precision, requested_at, status. (One geocode lookup.)
- **geocode_result_google** / **geocode_result_radar** — result_uuid PK, request_uuid, place_id (UNIQUE idx), formatted_address, `confidence`, bounds, raw_json. (Per-provider answers.)
- **geocode_resolution** — event_uuid PK, `preferred_provider`, result_uuid, `distance_m` (provider disagreement distance), `disagreement_flag`, `tie_break_reason`, resolved_at. (**The multi-provider reconciliation decision record.**)
- **geocode_audit** — audit_id, event_uuid, action, details, created_at. (Geo decision trail.)

---

## D. Inventory PART 3 (Source D) — Postgres+PostGIS Google-Timeline + parsing rules

- **timeline_events** (Postgres variant) — event_id (visit_X/activity_X), object_type (VISIT/ACTIVITY), start/end_timestamp, duration_seconds; VISIT fields (visit_place_id, visit_semantic_type WORK/HOME/SHOPPING, visit_probability, visit_lat/lng); ACTIVITY fields (activity_type IN_PASSENGER_VEHICLE/WALKING…, activity_probability, start/end lat/lng, distance_meters).
- **waypoints** — waypoint_id PK, parent_id (→event), parent_type ('activity'/'orphaned_path'), `sequence` (1-based, CRITICAL), timestamp, lat/lng, **multi_device_split BOOL, device_index, split_from_segment**.
- **processing_metadata** — source_file, file_hash, status, counts (total_segments, visits_created, activities_created, orphaned_paths_created, waypoints_created, multi_device_splits, errors_encountered), start/end_time. (Ingestion run ledger.)
- **PostGIS**: `CREATE EXTENSION postgis` required (PART 6) for timeline geospatial; deployment order ends timeline_events → waypoints.

### Parsing rules (load-bearing, carry into reconciliation)
- Coordinates arrive as `"43.1181886°, -83.6187962°"` → regex-parse.
- **Order by `sequence`/`point_sequence` integers, NOT timestamps** — timestamps lie inside ~2-hour containers.
- **Multi-device detection: 100-meter threshold** → split path into device_index segments (split_from_segment records origin).
- **Orphaned paths**: a `timelinePath` with no parent activity → link to previous visit.

---

## Reconciliation notes / cross-iteration synthesis
- **Four modeling styles** to reconcile: (A) generic event spine with table-inheritance subtypes + free-text/locations table; (B) wide denormalized enriched row + normalized source objects + dual-cache; (C) fully normalized geokey/resolution lane; (D) Postgres+PostGIS canonical with explicit waypoints + run metadata.
- **Common geo primitives** across all: exact latlng + a *fuzzy/rounded/geohash* key for privacy-safe joins/grouping (B `location_fuzzy`, C `lat_r3..r5`+geohash8/9, A NUMERIC(10,7)).
- **Multi-device split** appears in B (timeline_paths) and D (waypoints) identically: `multi_device_split`/`device_index`/`split_from_segment`, 100m threshold.
- **Provider reconciliation** is C's `geocode_resolution` (preferred_provider/distance_m/disagreement_flag/tie_break) and B's `location_confidence` HIGH/MED/LOW + problematic_poi/manually_verified flags — merge into one resolution+confidence model.
- **Sequence-over-timestamp** ordering (serial_id / point_sequence / sequence) is non-negotiable for path integrity.
- **PostGIS** is the intended spatial engine (A commented earthdistance fallback, D requires postgis) — target DB should bake PostGIS for the geo lane (memory flags BM25/pg_textsearch staged + Milvus for vector; PostGIS is the spatial counterpart).
- **Forensic outputs** already designed: B's `vw_forensic_evidence_package` (probability>0.6, confidence tiering, raw_json retention) is the template for the analysis/public evidence-export boundary.
- **Quality lane** (B data_quality_metrics + trigger, D processing_metadata counts) maps to the platform's data-quality/observability layer.
