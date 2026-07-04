# A3 — Existing Data Crosswalk (Prior-Work Pre-Scan)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Maps the user's REAL prior schemas / ontologies / parsers (donor + archive material) into the
> new canonical forensic DB architecture, per master prompt lines 268-401 (Existing Data Pre-Scan
> & Controlled Merge). Classification vocabulary = MP line 294-303
> (Adopt / Adapt / Preserve-as-Note / Preserve-as-Hypothesis / Merge / Split / Deprecate / Needs-Review).
>
> **This is NOT a blank slate.** Every prior field is reviewed, mapped, and preserved or intentionally
> deprecated — never silently discarded, never silently invented. (MP Constraints 2412-2474.)

## Data-tier topology (owner-mandated hard constraint — target stores referenced below)
Four independently-deployable resources, no shared lifecycle:
1. **PG** = PostgreSQL + PostGIS + embedded DuckDB via `pg_duckdb`, ALL in ONE service/container
   (relational + analytical + spatial). DuckDB is NOT standalone; PostGIS is NOT standalone.
2. **Milvus** = vector, own resource.
3. **Neo4j** = graph (Graphiti + Semantica writers), own resource.
4. **SurrealDB** = consolidated analysis (IF adopted), own resource.

## Provenance / staleness — read before trusting any row
- **ALL** sources live under `dev-resources/Archives/**` = read-only donor/archive material, NOT live code.
- **Heavy duplication.** Every artifact exists in 3-7 near-identical copies across
  `OTHER_RESOURCES_TO_SORT/`, `TheBigOne/`, and `…/Junkyard/Source_A_Root_Folder/`,
  `Source_B_BigOne_Repo/`, `Timeline_Tools_Backup_20260108_214802/`. Canonical-copy choice below is
  arbitrary-but-consistent; **dedupe required** before adopting (HITL: confirm which copy is newest).
- **Chunker messaging parsers** have copies sitting under `…/Source_A_Root_Folder/TO_BE_DELETED/…`
  → flagged for deletion by the user; treat as low-trust / superseded.
- **Dates:** TraceIQ master `schema.sql` self-labels "V4.1 Final … Generated December 9, 2025";
  Timeline_Tools backup folder stamped `20260108`. `salem_v3.py` = v3 (v1/v2 not located → lineage gap).
- TraceIQ stored timestamps are mostly `TEXT` (string) not native temporal types → normalization needed.

---

## CROSSWALK ROWS

Columns: Original name | Source file | Description | Classification | Proposed canonical name | Target store/table | Confidence | HITL? | Staleness note

### A. salem_v3 case ontology (HIGHEST VALUE — user's case-specific entity/edge model)
Source (canonical copy): `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/AI_Config/MCP_Servers/zep-server-reference/ontology/salem_v3.py`
(7 duplicate copies exist incl. dial-stack, TheBigOne/archive/04_Utilities, _DUMP_External_Utils_Lib.)
This is the **Salem v. Kinzel** knowledge-graph ontology — case-specific domain knowledge, READ FULLY.

| Original | Source | Description | Classification | Proposed canonical | Target store/table | Conf | HITL? | Staleness |
|---|---|---|---|---|---|---|---|---|
| Entity `Person` | salem_v3.py | Individual in/related to case | **Adopt** | `Person` (graph node) | Neo4j node; mirror in PG `person` | High | No | v3, dedupe |
| Entity `Incident` | salem_v3.py | Specific case-relevant event/occurrence | **Adopt** | `Incident`/`Event` | Neo4j node; PG `event` | High | No | align w/ TraceIQ timeline `event_id` |
| Entity `Location` | salem_v3.py | Physical place of incident/presence | **Adopt** | `Location` | Neo4j node; PG `location` (PostGIS geom) | High | No | merge w/ TraceIQ geo tables |
| Entity `Statement` | salem_v3.py | Declaration/assertion by a person | **Adopt** | `Statement` | Neo4j node; PG `statement` | High | No | distinguish raw vs extracted |
| Entity `Vulnerability` | salem_v3.py | Weakness of a person that can be exploited | **Adapt** | `Vulnerability` (sensitive) | Neo4j node + SurrealDB analysis | Med | **Yes** | inferred/clinical-ish label → HITL before court-facing |
| Entity `Tactic` | salem_v3.py | Action/strategy used by one person vs another | **Adapt** | `Tactic`/`BehavioralPattern` | Neo4j node + SurrealDB | Med | **Yes** | maps to abuse-pattern lane; sensitive |
| Entity `Evidence` | salem_v3.py | Data/document supporting a fact | **Adopt** | `Evidence`/`EvidenceItem` | PG `evidence` (provenance anchor) + Neo4j node | High | No | central provenance object |
| Edge `WAS_AT` (Person→Location) | salem_v3.py | Person present at location | **Adopt** | `WAS_AT` | Neo4j edge | High | No | corroborate w/ timeline geo |
| Edge `PARTICIPATED_IN` (Person→Incident) | salem_v3.py | Person involved in incident | **Adopt** | `PARTICIPATED_IN` | Neo4j edge | High | No | — |
| Edge `MADE_STATEMENT` (Person→Statement) | salem_v3.py | Person authored a statement | **Adopt** | `MADE_STATEMENT` | Neo4j edge | High | No | — |
| Edge `CONTRADICTS` (Statement→Statement) | salem_v3.py | Two statements in opposition | **Adopt** | `CONTRADICTS` | Neo4j edge | High | No | high analytical value (impeachment) |
| Edge `RELATED_TO` (Incident→Incident) | salem_v3.py | Generic incident link | **Adapt** | split into typed edges | Neo4j edge | Low | **Yes** | too vague → Split into causal/temporal/topical subtypes |
| Edge `USED_TACTIC` (Person→Tactic) | salem_v3.py | Person employed coercive/manipulative tactic | **Preserve-as-Hypothesis** | `USED_TACTIC` | Neo4j edge + SurrealDB hypothesis | Med | **Yes** | allegation, not fact; needs corroboration + review before court |
| Edge `TARGETED_WOUND` (Person→Vulnerability) | salem_v3.py | Person exploited another's vulnerability | **Preserve-as-Hypothesis** | `EXPLOITED_VULNERABILITY` | Neo4j + SurrealDB hypothesis | Low | **Yes** | strong inferred/intent claim; sensitive; rename for clarity |
| Edge `EXPOSED_CHILD` (Incident→Person) | salem_v3.py | Child exposed to an incident | **Adopt** | `EXPOSED_CHILD` | Neo4j edge | Med | **Yes** | custody-relevant; verify child = minor Person |
| Edge `AFFECTED_ACCESS` (Incident→Person) | salem_v3.py | Incident interfered w/ parent's access to child | **Adopt** | `AFFECTED_PARENTING_ACCESS` | Neo4j edge | Med | **Yes** | custody-relevant; rename for precision |
| Edge `SPREADS_RUMOR` (Statement→Person) | salem_v3.py | Statement disparaging/rumor about a person | **Preserve-as-Hypothesis** | `DISPARAGES` | Neo4j + SurrealDB | Low | **Yes** | reputational claim; allegation not fact |

**Ontology gaps to flag for HITL (NOT inventing — recommending review):** salem_v3 models only adversarial
conduct. MP (lines 372-377) requires modeling BOTH parties incl. the user's own conduct, the FULL relational
cycle (positive/neutral/love-bombing/repair), and reactive context. Recommend adding (post-approval):
`PositiveInteraction`/`RepairAttempt`/`LoveBombing` incident-subtypes and a `conduct_party` attribute so the
user's own mistakes/reactions are modeled in temporal context. → Needs-Review with user.

### B. TraceIQ core timeline (`timeline_enriched` + raw event tables)
Canonical copy: `…/Timeline_Tools_Backup_20260108_214802/TraceIQ_Main/schemas/schema_complete.sql` (SQLite,
indexes+views) and `…/TraceIQ_Snippets/traceiq/schema.sql` (V4.1 "Final", adds evidence/messaging tables).

| Original | Source | Description | Classification | Proposed canonical | Target store/table | Conf | HITL? | Staleness |
|---|---|---|---|---|---|---|---|---|
| `timeline_enriched` (table) | schema_complete.sql / schema.sql | Master human-readable enriched timeline event row | **Adapt** | `timeline_event` (enriched view/materialization) | PG `timeline_event` (+ DuckDB analytics via pg_duckdb) | High | No | split raw vs enriched; TEXT timestamps→`timestamptz` |
| `event_id` / `serial_id` | timeline_enriched | Unified PK + ordered serial | **Adopt** | `event_id` (uuid) + `serial_id` | PG | High | No | V4.1 unified `source_event_id` — adopt unified-ID design |
| `device`, `device_index`, `multi_device_split` | timeline_enriched / timeline_paths | Multi-device attribution & split flags | **Adopt** | `device_id` + `multi_device_*` | PG | Med | No | strong forensic signal |
| `event_type`, `label` | timeline_enriched | VISIT_START/ACTIVITY_START etc. + human label | **Adapt** | `event_type` (enum) | PG enum | High | No | enumerate values |
| `date_us`,`time_12h`,`day_of_week`,`duration`,`timestamp_utc` | timeline_enriched | Localized + UTC temporal display fields | **Adapt** | normalize → `ts_utc timestamptz`, `tz_offset`, derived display | PG (+ exact/approx flag) | High | **Yes** | MUST add timestamp-precision class (exact/approx/inferred/uncertain) per MP |
| `google_place_*`,`radar_place_*`,`address_*`,`location_geopair`,`location_fuzzy`,`map_link_*` | timeline_enriched | Dual-provider geocoded place identity + fuzzy/exact coords | **Adapt** | `location` + `place_resolution` | PG PostGIS (geom) + DuckDB | High | No | `location_fuzzy` = privacy-fuzzed coord — preserve as such |
| `probability`,`semantic_type_probability`,`activity_type_probability` | timeline_enriched | Google confidence scores | **Adopt** | `*_confidence` | PG | High | No | drives evidence confidence tiers |
| `overnight_flag`,`overnight_type`,`delta_distance_meters`,`delta_duration_seconds`,`distance_miles` | timeline_enriched | Overnight & inter-event deltas (analytical) | **Adapt** | derived analytical fields | DuckDB (in PG) / SurrealDB | Med | No | inferred facts — label as such, not raw |
| `original_json`,`data_source`,`processed_at` | timeline_enriched | Raw payload + provenance | **Adopt** | provenance columns | PG (append-only) | High | No | provenance is mandatory (MP) |
| `visits` / `activities` / `timeline_paths` / `memories_trips` (raw tables) | schema_complete.sql | Raw Google Timeline segments (visit/activity/path/trip) | **Adopt** | `raw_visit`/`raw_activity`/`raw_path`/`raw_trip` | PG (raw-evidence layer) | High | No | keep raw separate from enriched (raw vs extracted) |
| `google_api_cache` / `radar_api_cache` | schema_complete.sql | Geocode API response cache (dual provider) | **Adopt** | `geocode_cache_google` / `geocode_cache_radar` | PG | High | No | radar cache has rich parsed fields |
| `enrichment_queue` | schema_complete.sql | Pending geocode work queue | **Preserve-as-Note** | (pipeline-only) | n8n/Windmill job state, not canonical DB | Med | No | operational, not evidentiary |
| `data_quality_metrics` + `trig_quality_check` | schema_complete.sql | DQ metric rows + insert trigger (missing-coord %) | **Adapt** | `data_quality_metric` | PG | Med | No | good audit pattern; reimplement as job |
| View `vw_place_analytics` | schema_complete.sql | Visit-frequency rollup per fuzzy location | **Adapt** | analytical view | DuckDB (in PG) | Med | No | analytical finding, not fact |
| View `vw_bouncy_trips` | schema_complete.sql | Anomalous city ping-pong/bounce pattern detector | **Preserve-as-Hypothesis** | anomaly view | SurrealDB / DuckDB | Low | **Yes** | inferred pattern; explanation≠fact |
| View `vw_route_patterns` | schema_complete.sql | Repeated A→B route detection | **Adapt** | route analytics view | DuckDB | Med | No | analytical |
| View `vw_overnight_activity` / `vw_city_summary` | schema_complete.sql | Overnight + per-city rollups | **Adapt** | analytical views | DuckDB | Med | No | analytical |
| View `vw_forensic_evidence_package` | schema_complete.sql | Court-export view w/ HIGH/MED/LOW location-confidence tiering (prob>0.6) | **Adopt** | `evidence_package` (export) | PG view + SurrealDB | High | **Yes** | court-facing → HITL; great confidence-tier model |

### C. TraceIQ V4.1 evidence / messaging / people / anomaly tables (`traceiq/schema.sql`)
| Original | Source | Description | Classification | Proposed canonical | Target store/table | Conf | HITL? | Staleness |
|---|---|---|---|---|---|---|---|---|
| `messages` | traceiq/schema.sql | Unified message store (SMS/FB/Snapchat/GChat), `is_private` judicial-review flag, linked to location event | **Adopt** | `message` | PG + Milvus (body embeddings) | High | **Yes** | `is_private`→sensitive-review gate; link to timeline = key |
| `people` | traceiq/schema.sql | Unified person registry, phone/email, social IDs, `relationship_type`, `is_flagged` | **Merge** (with salem_v3 `Person`) | `person` | PG canonical + Neo4j node | High | No | reconcile PG row ↔ graph node identity |
| `screenshots` | traceiq/schema.sql | Screenshot evidence + OCR text + extracted entities | **Adopt** | `screenshot_evidence` | PG + Milvus (OCR text) | Med | No | OCR = extracted fact, label provenance |
| `actions` | traceiq/schema.sql | Social actions (FRIEND_ADD/FOLLOW/UNFRIEND/BLOCK) vs target person | **Adopt** | `social_action` | PG + Neo4j edges | Med | **Yes** | behavioral signal; allegations not facts |
| `home_base` | traceiq/schema.sql | Detected home/base locations + confidence + typical schedule | **Adapt** | `home_base` | PG PostGIS | Med | No | inferred location class |
| `expected_schedule` | traceiq/schema.sql | Claimed vs actual location/time w/ anomaly + discrepancy fields | **Adapt** | `claim_verification` | PG + SurrealDB | Med | **Yes** | "claimed" = allegation; verify before court |
| `problematic_locations_contacts` | traceiq/schema.sql | Flagged people/places, `severity_level`, `legal_restriction`, alerting | **Adapt** | `flagged_entity` | PG + Neo4j | Low | **Yes** | subjective flags; bias risk → HITL |
| `temporal_alignment` | traceiq/schema.sql | Activity↔path time-delta alignment | **Preserve-as-Note** | (pipeline) | processing artifact | Low | No | operational |

### D. normalized_geo_schema_v5 (geo-precision normalization)
Source: `…/TraceIQ_Main/schemas/normalized_geo_schema_v5.sql` (SQLite) + `traceiq/supabase_schema.sql` (Postgres mirror).
| Original | Source | Description | Classification | Proposed canonical | Target store/table | Conf | HITL? | Staleness |
|---|---|---|---|---|---|---|---|---|
| `timeline_master` | normalized_geo_schema_v5 | Minimal event spine (uuid, type, start/end/point time, latlng, path-time fallback) | **Merge** (into B `timeline_event`) | `timeline_event` | PG | Med | No | overlaps TraceIQ core; consolidate |
| `event_geokey` | normalized_geo_schema_v5 | Per-event coords rounded r3/r4 + geohash8/9 (start/end/point) | **Adapt** | derive via PostGIS | PG PostGIS / generated cols | Med | No | replace manual geohash w/ PostGIS |
| `location_key` | normalized_geo_schema_v5 | Canonical dedup'd location by exact latlng + rounded + geohash | **Adopt** | `location` (canonical) | PG PostGIS | High | No | good dedup key design |
| `geocode_request` | normalized_geo_schema_v5 | Geocode request log w/ status | **Adapt** | `geocode_request` | PG | Med | No | append-only audit |
| `geocode_result_google` / `geocode_result_radar` | normalized_geo_schema_v5 | Per-provider geocode results (place_id, addr, confidence, bounds, raw_json) | **Merge** (with C caches) | `geocode_result` (provider col) | PG | Med | No | reconcile w/ `*_api_cache` |
| `geocode_resolution` | normalized_geo_schema_v5 | Provider tie-break: preferred, distance_m, `disagreement_flag`, `tie_break_reason` | **Adopt** | `geocode_resolution` | PG | High | No | excellent dual-source disagreement model |
| `geocode_audit` | normalized_geo_schema_v5 | Append-only geocode action log | **Adopt** | `geocode_audit` | PG (append-only) | High | No | matches provenance mandate |

### E. new_timeline_processor schemas (alt pipeline draft)
Source: `…/new_timeline_processor/schemas/database/schema_template.sql`, `…/target/master_enriched_locations_schema.json`, `…/source/google_timeline_schema.json`.
| Original | Source | Description | Classification | Proposed canonical | Target store/table | Conf | HITL? | Staleness |
|---|---|---|---|---|---|---|---|---|
| `timeline_events` (`custom_id` PK, flat) | schema_template.sql | Alt flat event table (visit+activity+path+anomaly cols merged) | **Deprecate** (superseded by B) | — | — | Med | No | older flat design; keep cols as field-name reference only |
| `radar_enrichment`/`google_places_enrichment`/`radar_cache`/`google_places_cache` | schema_template.sql | Duplicate geocode caches | **Merge** (into B/D caches) | `geocode_cache_*` | PG | Med | No | redundant |
| `expected_schedules`/`problematic_locations`/`overnight_stays` (stub) | schema_template.sql | Stub tables (id/name/details only) | **Deprecate** | — (use C richer versions) | — | Low | No | incomplete stubs |
| `master_enriched_locations_schema.json` | target JSON schema | JSON contract for enriched location export (nested google/radar/visit/activity/analysis/device/map) | **Preserve-as-Note** | export contract | doc / pipeline IO | Med | No | useful as ingestion/export shape ref |
| `google_timeline_schema.json` (`semanticSegments`…) | source JSON schema | Authoritative Google Timeline raw-export shape (visit/activity/timelinePath, latLng pattern) | **Adopt** | raw ingestion contract | pipeline + PG raw layer | High | No | defines RAW EVIDENCE shape — keep verbatim |

### F. Chunker messaging parsers (HTML→text extraction configs)
Canonical copy: `…/OTHER_RESOURCES_TO_SORT/Tools/Chunker/schemas/{facebook_messages,snapchat_messages,generic_html}.json`.
Duplicate copies under `…/Source_A_Root_Folder/TO_BE_DELETED/02_Voice_Analysis/…` and `…/TO_BE_DELETED/04_Utilities/…` → **flagged for deletion**.
| Original | Source | Description | Classification | Proposed canonical | Target store/table | Conf | HITL? | Staleness |
|---|---|---|---|---|---|---|---|---|
| `facebook_messages.json` (selectors `div._a6-g`, `_a6-h`, `_a6-p`, `_a6-o`) | Chunker/schemas | FB export HTML → sender/timestamp/content extraction map | **Adapt** | `parser_config.facebook` | pipeline config (feeds PG `message`) | Med | No | brittle FB CSS classes rot fast; copy under TO_BE_DELETED |
| `snapchat_messages.json` (`.sender-name`/`.message-text`/`.timestamp`) | Chunker/schemas | Snapchat export HTML extraction map | **Adapt** | `parser_config.snapchat` | pipeline config | Med | No | same brittleness; verify vs current export |
| `generic_html.json` (`div,section,article,p`) | Chunker/schemas | Fallback generic HTML extractor | **Preserve-as-Note** | `parser_config.generic` | pipeline config | Low | No | low fidelity fallback |
| Parser `output_format` template (`**{sender}** ({timestamp})\n{content}`) | Chunker/schemas | Render template for extracted messages | **Deprecate** | — | — | Low | No | replace w/ structured rows, not markdown blobs |

---

## Summary of classification counts
- **Adopt:** ~24 (salem_v3 core entities/edges, raw timeline tables, geocode caches/resolution/audit, V4.1 messages/screenshots, location_key, Google raw contract, forensic evidence package).
- **Adapt:** ~18 (timestamp normalization, enriched timeline, analytical views, parser configs, flagged/claim tables).
- **Merge:** 4 (timeline_master, people↔salem Person, geocode results↔caches, alt caches).
- **Preserve-as-Hypothesis:** 4 (USED_TACTIC, TARGETED_WOUND, SPREADS_RUMOR, vw_bouncy_trips).
- **Preserve-as-Note:** 4 (enrichment_queue, temporal_alignment, export JSON contract, generic parser).
- **Split:** 1 (RELATED_TO → typed edges). **Deprecate:** ~5 (flat timeline_events, stub tables, redundant caches, markdown output template).
- **Needs-Review (cross-cutting):** ontology lacks BOTH-parties / full-relational-cycle / reactive-context modeling — must be added with user before court-facing use.

## Guardrail compliance notes (carried into target schema)
- Raw (visits/activities/paths, original_json, message body) vs extracted (OCR, geocode) vs inferred
  (overnight, anomalies, home_base) vs analytical (views) vs legal-conclusion lanes kept **distinct**.
- Timestamp precision class (exact/approx/inferred/uncertain) is **missing** in all prior schemas → MUST add.
- All sensitive Tactic/Vulnerability/flagging labels routed through HITL before court output.
- Provenance + append-only (geocode_audit pattern, original_json, data_source) preserved everywhere.
