# Cross-Domain Integrity Review — forensic-db-reconciliation

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> **Scope.** Cross-checks E1 (as-built law) against the 8 PG domains (D1–D8) and the 3
> store reconciliations (S1 Milvus, S2 Neo4j, S3 SurrealDB) for: duplicate/competing table
> definitions, PK/FK resolvability, the `evidence`(RO)/`analysis`/`public` boundary, `0004`
> custom-type reuse, the `disclosure_tier` bug fix, extension usage, `id_xref`/`source_system`
> coherence, and UUIDv7 PKs.
>
> **Verdict.** The per-domain reconciliations are individually strong, but they were written
> in parallel and **do not yet compose**. There are real competing table definitions for the
> raw timeline/geo lane and for messages, two undefined-but-FK'd canonical anchors
> (`analysis.finding`, `analysis.provenance`), an incompletely-reconciled `disclosure_tier`
> survivor column, a double-defined `id_xref`, and at least one hard `evidence → analysis` FK
> that violates the dependency arrow. None is fatal to the design; all are fixable in a
> consolidation pass (a `0005`/`0006` shared-types + cross-domain-FK migration), but they must
> be fixed before any DDL is emitted, because several will fail to `CREATE` as written.

---

## A. Concrete conflicts (most severe first)

### A1 — Competing raw timeline/geo tables: D3 vs D5 model the SAME Google-Timeline source two incompatible ways  **[SEVERITY: critical]**
- **D3** (`D3-events-timeline.md` §2, L111) merges visits/activities/paths/trips into **one
  discriminated** table `evidence.raw_timeline_segment` (`segment_type` enum), with exploded
  points in `evidence.timeline_waypoint` (L147), anchored to `evidence.evidence_hash(id)` via
  `source_artifact_id`.
- **D5** (`D5-geo-gps.md` §2, L141/167/193/217) splits the *same* source into **four separate**
  tables `evidence.raw_visit` / `raw_activity` / `raw_path` / `raw_trip` (+ `evidence.gps_point`
  L119), anchored to `evidence.source(id)` (D1) via `source_id`.
- Both cite **E3 §B** as the donor and both claim the `evidence` raw lane. This is a direct
  competing definition: a parser would have two contradictory landing schemas and two different
  custody anchors (`evidence_hash` vs `evidence.source`) for one Takeout file.
- **Sub-conflict (lane split reversed):** D3 deliberately pulls the inferred 100 m multi-device
  split OUT of raw into `analysis.waypoint_device_split` (L338, "it is an inference, not raw");
  D5 puts `multi_device_split`/`device_index`/`split_from_segment` back **inline on the raw**
  `evidence.raw_path` (L203). The two domains disagree on whether an inference may live in the RO
  evidence lane.

### A2 — `evidence.message` (S1/S2) vs `analysis.message` (D2): cross-store links bind to a table the owning domain refuses to create  **[critical]**
- **D2** (`D2-messages.md` §1/§3, L36–41, L203) is explicit: message *bytes* stay in
  `evidence.evidence_hash`; every *parsed* message row is derived → **`analysis.message`**
  (PK-sharing subtype of `analysis.normalized_record`). There is intentionally **no**
  `evidence.message` table.
- **S1** (`S1_milvus.md` §2/§4, L36, L89) maps `ev_message` → **`evidence.message`** (PK
  `message_id`, "raw evidence" lane). **S2** (`S2_neo4j.md` §1, L50) re-homes `:Message` →
  **`evidence.message`** as well.
- Result: the Milvus link contract and the Neo4j projection both point at a non-existent table
  and the wrong lane. S2 additionally invents `evidence.identifier_raw` / `evidence.platform`
  (L51–52) that no PG domain defines.

### A3 — `analysis.finding` is FK'd everywhere but defined nowhere  **[critical]**
- Referenced as a canonical anchor by **D6** (`pattern_finding.finding_id`, L275 — "→
  analysis.finding(id) (findings domain)"), **D7** (`evidence_task.finding_id uuid REFERENCES
  analysis.finding(id)`, L323 — written **inline as a hard FK** in the DDL block), **S1** (L41/94
  `ev_pattern_finding → analysis.finding (+ analysis.finding_version)`), **S2** (L62), **S3** (§3).
- **No domain D1–D8 defines `analysis.finding`** (or `analysis.finding_version`). D6 explicitly
  defers it to a "findings domain (paper §8.3)" that is absent from this reconciliation set.
- As written, D7's `CREATE TABLE analysis.evidence_task … REFERENCES analysis.finding(id)` will
  **fail to create**. The central synthesized-finding table — the thing court export ultimately
  rests on — has no owner.

### A4 — D5 hard `NOT NULL` FK to `analysis.provenance(id)` which does not exist (D8 calls it `analysis.processing_run`)  **[critical]**
- **D5** puts `provenance_id uuid NOT NULL REFERENCES analysis.provenance(id)` on **every**
  analysis table (`location` L254, `gps_track` L270, `stay_point` L289, `geofence` L302,
  `home_base` L317, `location_assertion` L339, `location_contradiction` L361, `geocode_*`); §0
  (L101) lists `analysis.provenance(id)` as a dependency "(Dprov)".
- **D8** (the provenance domain) creates **no** `analysis.provenance` — the run anchor is
  `analysis.processing_run` (L258). S2 (L201) further calls it `provenance.provenance`.
- So the provenance anchor is named three ways (`analysis.provenance` / `analysis.processing_run`
  / `provenance.provenance`) and D5's hard `NOT NULL` FK is unresolvable → **every D5 analysis
  insert is blocked**. (D2/D4/D6/D7 correctly use a *nullable, soft* `provenance_id` with no FK;
  D5 is the outlier.)

### A5 — `disclosure_tier` fix is only half-done: the surviving bitemporal column has 3 names/types across domains  **[high]**
- The **enum rename** (`0004 disclosure_tier` → `sensitivity_tier`) is consistent across
  D1/D2/D4/D5/D6/D7/D8/S1/S2/S3 — good.
- The **surviving substantive column is not reconciled**:
  - **D2** (L151, L413) keeps `analysis.normalized_record.disclosure_tier` as **TEXT CHECK**,
    name and type **unchanged**.
  - **D3** (L72–74, L406, M2 L426–430) **retypes and renames** it to a **new enum
    `disclosure_horizon`** and flags M2 as "owner = records domain."
  - **S2** (L104) and **S3** (L54) carry the field as **`knowledge_horizon`**.
  - **S1** (L62) keeps it as **`disclosure_tier`** (INT8 mirror).
- Four names (`disclosure_tier` / `disclosure_horizon` / `knowledge_horizon`) for one field →
  D2 and D3 issue **directly conflicting migrations on the same column**, and the cross-store
  field mapping (which assumes one canonical name) breaks.

### A6 — `analysis.id_xref` is double-defined with incompatible schemas (D4 vs S1)  **[high]**
- **D4** (`D4-entities-idres.md` §2.7, L381) defines it as **entity-keyed, one row per store**:
  `(canonical_entity_id → analysis.entity(id), source_system, native_id, match_method,
  confidence, is_current, sys_period)`, `UNIQUE(source_system, native_id)`.
- **S1** (`S1_milvus.md` §5, L105–114) defines the same `analysis.id_xref` as a **pairwise**
  crosswalk: `(system_a, native_id_a, system_b, native_id_b, match_method, confidence,
  source source_ref)` — **no entity FK**, designed to link any row (e.g. message ↔ vector pk).
- These are two different tables under one name. The *very table meant to unify identity across
  PG/Milvus/Neo4j/Surreal* is itself incoherent. (D4's is entity-only and cannot express the
  message↔vector links S1 needs; S1's cannot enforce the entity anchor D4 needs.)

### A7 — Boundary violation: hard `evidence → analysis` FK in D5  **[high]**
- **D5** `evidence.gps_point.device_id uuid REFERENCES analysis.device(id)` (L123) makes the
  **read-only `evidence` lane FK into the writable `analysis` lane**.
- **D4** §1.2 (L40–48) and §4 item 8 (L477) explicitly forbid this ("otherwise the RO `evidence`
  lane would FK into writable `analysis` … must be **soft uuid refs, no FK**") and flag it for
  the custody domain. D5 reintroduces exactly the coupling D4 outlawed: rebuilding/truncating
  `analysis` would break an `evidence` FK, and it inverts the dependency arrow.
- **Related (medium):** the provenance-link convention is itself split — D4 mandates soft
  `source_ref[]` (no FK), while D2/D3/D5/D7 use hard `analysis → evidence.evidence_hash` FKs.
  The `analysis → evidence` direction is acceptable, but the project has two contradictory rules
  for the same linkage; pick one.

### A8 — Competing run-ledger tables + a run ledger in the RO lane  **[medium]**
- **D3** creates `evidence.ingestion_run` (L91) in the **`evidence`** schema. **D8** establishes
  `analysis.processing_run` (L258) as the single canonical run table that explicitly **merges**
  "provenance.run + processing_runs + scoring_run" (§1.2). `evidence.ingestion_run` is a fourth
  run table D8's merge missed, and putting run/lineage metadata (a derivation, written by the
  pipeline) in the **RO evidence** lane is a boundary smell — runs are derived provenance and
  belong in `analysis` per D8.

### A9 — Duplicate `0004`-style type: `precision_class` (D2/D5) == `timestamp_certainty` (D3)  **[medium]**
- **D2** §4 step 0 (L105) creates `precision_class AS ENUM('exact','approximate','inferred',
  'uncertain')`; **D5** reuses it. **D3** (L69) creates `timestamp_certainty AS ENUM('exact',
  'approximate','inferred','uncertain')` — **identical values, different type name** — and uses
  it on every temporal table. Two competing enums for one concept; cross-domain joins/casts on
  the precision class will not line up.
- **Also (medium):** the 5-lane epistemic class is represented three ways — D3 enum
  `assertion_kind` ('raw_evidence'…), D7/D8 `assertion_type` **TEXT CHECK** ('raw_evidence'…),
  and D2's `evidence_tier` enum uses a **different vocabulary** ('raw','extracted','inferred',
  'analytical','legal_conclusion'). D8 §6 already flags `assertion_type` for a shared enum; note
  it must also reconcile the `evidence_tier` value-set mismatch (`raw` vs `raw_evidence`,
  `extracted` vs `extracted_fact`) that S1 (L64) has to map by hand.

### A10 — Entity satellite table names disagree: D4 vs S2  **[medium]**
- **D4** names the resolved-entity tables `analysis.entity` + satellites `analysis.person`,
  `analysis.organization`, `analysis.device`, `analysis.account` (L143–255). D5/D7 correctly FK
  these (`analysis.device`, `analysis.person`).
- **S2** (`S2_neo4j.md` §1, L53–57) re-homes graph nodes to `analysis.entity_person`,
  `analysis.entity_org`, `analysis.entity_device`, `analysis.entity_account` — names that **do
  not exist** in D4. The Neo4j↔PG `pg_table` back-refs therefore point at phantom tables.

### A11 — "Both-parties" / conduct vocabulary is incoherent across stores  **[medium]**
- `conduct_party`/party enums differ: **D2** `('user','partner','child','third_party',
  'institution','unknown')` (L117); **D4** `person.connection_to`
  `('petitioner','respondent','child','mutual','third_party','unknown')` (L182); **D3**
  `conduct_party text` (untyped, L196); **S3** envelope `('petitioner','respondent','child',
  'mutual')` (L84); **S1** `subject_party` INT8 `1 user · 2 counterparty · 3 child · 4 third_party`
  (L78). Five vocabularies for "whose conduct" defeats the cross-store both-parties guard the
  design leans on.
- **Related:** `review_state` is an enum in D2/D4/D5/D6 (`unreviewed/in_review/approved/rejected/
  needs_more_evidence`) but **D7** uses `review_status TEXT CHECK` dropping `needs_more_evidence`
  (L223 etc.) — same field, two types and two value sets.

### A12 — Domain cross-reference numbering drift (documentation)  **[low]**
- D2 routes behavior labels to "behavioral domain **D4**" (L425/438) — behavioral is **D6**;
  D4 is entities. D5 §0 labels entity tables "(D3 entity)" and timeline "(D4 timeline)" (L100–102)
  — entity is **D4**, timeline is **D3**. The references resolve by table name but the domain tags
  are wrong, which will mislead the consolidation pass.

### A13 — UUIDv7 PK exceptions (defensible, note for the record)  **[low]**
- `uuidv7()` PKs are used essentially everywhere. Intentional natural/identity-key exceptions:
  D1 `evidence.custody_event` PK = `seq bigint IDENTITY` (+ `id uuid UNIQUE`, L248–249); D8
  `public.change_log` PK = `change_id uuid` but ordered by `seq bigint IDENTITY` (L670–671); D6
  `behavior_category` PK = `citext category_id` (L124); D7 `custody_factor` PK = `mcl_factor`
  enum (L124), `score_band_config` PK = `config_version text` (D8 L411). These are fine, but the
  "UUIDv7 everywhere" invariant should be restated as "UUIDv7 for all *surrogate* PKs; natural
  keys allowed for reference/ledger-ordering tables."

### A14 — `btree_gist` EXCLUDE on a `citext` equality column may lack a gist opclass  **[low/verify]**
- D4 `analysis.phone` / `email` / `handle` use `EXCLUDE USING gist (e164 WITH =, validity WITH &&)`
  on **`citext`** columns (L211/221/232). `btree_gist` ships gist opclasses for the common
  scalar types but **not** `citext` out of the box — this EXCLUDE can fail at creation. Verify on
  the live image; if unsupported, cast the equality member to `text` (`(e164::text)`), which the
  surrounding indexes already do.

---

## B. What is correct (so the fixes don't regress it)
- **disclosure_tier ENUM rename** to `sensitivity_tier` is uniform and the idempotent guard is
  repeated safely (D1/D2/D7/D8) — keep that.
- **Extension usage is sound:** `btree_gist EXCLUDE` for bitemporal no-overlap (D3 `time_assertion`
  L273, D4 ownership ranges); `fuzzystrmatch` `dmetaphone` generated columns (D4 L270/297);
  `pgcrypto digest(...,'sha256')` hash-chains (D1 custody_event L278, D8 change_log L704);
  `geo_point` used Point-only with raw `geography(LineString|Polygon)` for tracks/fences
  (D5 L266/299) — all correct.
- **`source_system`/`match_method`/`confidence`/`canonical_id`/`source_ref` are reused, not
  redefined**, across D4/S1/S2/S3 (modulo the `id_xref` shape clash in A6).
- **`source_ref` composite vs `evidence_hash.source_ref` TEXT** collision is correctly handled as
  a documented foot-gun, not a hard conflict (D1 L332, S2 L84).
- **Schema boundary** is otherwise respected: raw → `evidence`, derived → `analysis`, audit/Agno
  → `public`; `analysis.entity_mention` immutability-by-trigger (D4) is a sound way to keep
  evidence-grade fixity without putting a derivation in `evidence`.

---

## C. Fix list (do these in a single consolidation pass, before emitting any DDL)

1. **Pick ONE raw timeline/geo schema (A1).** Either D3's discriminated `raw_timeline_segment`
   or D5's four `raw_*` tables — not both. Recommend D5's four typed tables (richer, geo-domain
   owns them) and **delete** D3's `raw_timeline_segment`/`timeline_waypoint`; have D3's
   `event_source_record` point at D5's raw tables. Standardize the raw custody anchor on
   **`evidence.source(id)`** (D1) and move the multi-device split to `analysis` per D3's lane rule.
2. **Define the missing canonical anchors (A3, A4).** Add a findings-domain table
   `analysis.finding` (+ `analysis.finding_version`) and converge the provenance anchor name on
   **`analysis.processing_run`** (drop `analysis.provenance`/`provenance.provenance`). Until then,
   make every cross-domain FK to these targets a **soft nullable uuid** (as D6/D7 §4 intend) so
   the DDL creates; D5 must drop its `NOT NULL` and the hard FK.
3. **Fix the message lane (A2).** S1/S2 must bind `ev_message`/`:Message` to **`analysis.message`**
   (D2), with raw bytes anchored via `evidence.evidence_hash`. Delete the phantom
   `evidence.message`/`evidence.identifier_raw`/`evidence.platform` references (S2).
4. **Finish the disclosure_tier fix (A5).** Choose one canonical name for the surviving
   bitemporal column — recommend **`knowledge_horizon`** (S2/S3 already use it) — and apply it as
   a single owned migration: keep TEXT-CHECK *or* promote to the `disclosure_horizon` enum, but
   decide once. Update D2 (currently "unchanged"), D3 (currently retype+rename), and the S1 INT8
   mirror to that one name. The enum→`sensitivity_tier` rename stays as-is.
5. **Unify `analysis.id_xref` (A6).** Adopt **one** schema. S1's pairwise
   `(system_a/native_id_a, system_b/native_id_b, match_method, confidence, source)` is the more
   general crosswalk (handles entity *and* row links); add an optional
   `canonical_entity_id → analysis.entity(id)` column so D4's entity-anchor need is met. Delete
   D4's competing definition.
6. **Enforce the dependency arrow (A7).** Make `evidence.gps_point.device_id` a **soft uuid (no
   FK)**, resolved through the entity registry — matching D4's rule. Then pick ONE
   provenance-linking convention project-wide (soft `source_ref[]` vs hard `analysis → evidence`
   FK) and apply it everywhere.
7. **Collapse the run ledgers (A8).** Drop `evidence.ingestion_run`; add an `ingestion`/`file_scan`
   `run_type` to `analysis.processing_run` and re-point D3/D5 `ingest_run_id` FKs at it.
8. **Add a shared-types `0005` migration (A9, A10, A11).** One coordinated CREATE for the cross-
   domain enums so each is defined once: collapse `timestamp_certainty`→`precision_class`; decide
   `assertion_type` enum vs TEXT and reconcile `evidence_tier` values to it (or keep them distinct
   and document the mapping); standardize ONE party vocabulary for `conduct_party`/`subject_party`/
   `connection_to`; make D7 use the `review_state` enum (or document the deliberate TEXT choice).
   Rename S2's `analysis.entity_*` back-refs to D4's `analysis.person`/`organization`/`device`/
   `account`.
9. **Housekeeping (A12, A13, A14).** Correct the domain-number cross-references; restate the
   UUIDv7 invariant to permit natural keys on reference/ledger tables; verify the `citext`
   `EXCLUDE` opclass on the live image (cast to `text` if `btree_gist` lacks citext support).
