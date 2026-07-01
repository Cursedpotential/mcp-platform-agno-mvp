# D8 — Provenance, Confidence, Review/Audit & Work-Product Memory Ledger (PG Domain Reconciliation)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> **Scope:** the cross-cutting "how did we get here, who/what said so, was a human
> involved?" backbone of the unified PostgreSQL resource (PG18 + PostGIS + embedded DuckDB
> via `pg_duckdb`). This domain owns four interlocking lanes:
> 1. **Provenance / lineage** — the run/act table, the derived-artifact registry, the
>    derivation DAG, redaction + export records, and the prompt/model/schema/ontology/
>    classification **version registries** (paper §09 + §20).
> 2. **Confidence / scoring** — the 10-axis append-only score model + versioned band config
>    (paper §13).
> 3. **Review / audit** — the HITL review-task + reviewer-of-record records, and the single
>    **append-only, hash-chained `change_log`** audit spine (paper §09 `audit_log` + §20
>    `change_log`, merged).
> 4. **Work-product micro-memory ledger** — `memory_items`, `tool_call_ledger`,
>    `processing_runs`, `prompt_registry`, `decision_log`, `session_summaries`,
>    `open_questions`, and the three context-version tables (paper §20, the "project lab
>    notebook").
>
> **Law (ground truth):** `extracted/E1_asbuilt_inventory.md`. **Donor intents:**
> `extracted/E5_entity_ontology_misc.md` (§4 pattern-persistence HITL workflow, S5/S7),
> paper sections `sections/09-provenance-custody.md`, `sections/13-confidence-review.md`,
> `sections/20-workproduct-memory.md`, crosswalk `discovery/A3_crosswalk.md`,
> `discovery/CONTEXT_PACK.md`, and `forensic-db-extension-and-reconciliation-addendum.md`.
> **Adjacent domains:** D1 (source/custody) owns `evidence.*` and the H1/H2/H3 hash ledger;
> D8 references `evidence.evidence_hash(id)` as the stable source/artifact anchor. D3/D5/D6
> own the case domain tables (events, geo, behavioral patterns) and route every sensitive
> write through **D8's** review + `change_log` machinery rather than re-implementing it.

---

## 1. Reconciliation stance (what changed vs the paper design)

Three independent paper sections (§09 provenance, §13 confidence/review, §20 work-product
ledger) each invented their own run table, their own audit log, and their own artifact
notion, and §20 placed the entire ledger **outside** PostgreSQL in a local SQLite/DuckDB
tier. Reconciliation does two things: **(a)** collapse the triplicated structures into one
canonical set, and **(b)** re-home everything under the as-built `evidence`/`analysis`/
`public` security boundary — **no parallel `provenance` schema** (the paper's
`CREATE SCHEMA provenance` is dropped; its tables move to `analysis` and `public`).

### 1.1 The biggest call — canonical lives in **this PG resource**, SQLite/DuckDB become a mirror

The paper (§20 L1/L7) is **right that rough work must never pollute canonical evidence**, but
it implemented that as a *physically separate local-first SQLite store*. The owner guardrail
is explicit: **keep the canonical copy in this PG resource.** Reconciliation keeps the
*principle* (quarantine-by-default, promotion-gated) and changes the *mechanism*:

- **PostgreSQL is the canonical system-of-record** for every ledger/provenance/score/review
  table below. They live in `analysis` (derived work-product, write-after-approval) and
  `public` (HITL audit + Agno-managed operational memory) — the two as-built schemas whose
  semantics already match "derived/quarantined" and "audit/agent-owned".
- **SQLite `ledger.db` + DuckDB `analytics.duckdb` are demoted to an operational mirror /
  analytical lens**, not a separate authority: single-writer offline buffer for the
  orchestration loop, plus the columnar bulk-scan store. Because ledger PKs are **UUIDv7
  generated app-side** (paper §2) and identical to canonical `uuidv7()`, a row minted in the
  mirror is valid *verbatim* when it syncs into PG — no re-keying. **The store-mix stays**
  (SQLite ops / DuckDB analytical / PG canonical / JSONL-Parquet payload logs) but the word
  "canonical" attaches to PG, and DuckDB reaches PG and the R2 Parquet/JSONL via the **same
  embedded `pg_duckdb` engine** (ADR-0013/0030), so a mirror query ports to canonical
  unchanged. The promotion gate from §20 still governs ledger→*evidence/analysis case tables*.

### 1.2 De-duplication merges (one structure, not three)

| Paper constructs (separate) | Reconciled single home | Why |
|---|---|---|
| `provenance.run` (§09) + `processing_runs` (§20) + `analysis.scoring_run` (§13) | **`analysis.processing_run`** | All three are "a pass that consumed hash-pinned inputs, pinned prompt/model/schema/ontology/classification versions, and produced outputs." Scoring and review become `run_type` values. One run table = one lineage anchor. |
| `provenance.artifact` (§09) + `artifact_registry` (§20) | **`analysis.artifact_registry`** | Evidence-derived artifacts (ocr_span, message, finding) and work-product artifacts (schema_draft, classification_report, court_export_draft) share `assertion_type`/`confidence`/lineage; the DAG must span both (a court export derives from evidence findings). |
| `provenance.audit_log` (§09) + `change_log` (§20) | **`public.change_log`** | One append-only, hash-chained spine answers both "every state-change event" and "every field-level before/after." Two logs would re-create the very double-definition bug we are fixing. |
| `provenance.review` (§09) + `analysis.review_decision` (§13) + S5 `pattern_approval_log` (E5) | **`analysis.review_task` + `analysis.review_decision`** | §13's task/decision split is the cleaner shape; §09's review fields (`court_readiness`, `sensitive_label_decision`, `set_confidence`) fold into `review_decision`; S5's pattern approval quartet/audit is subsumed (see §1.3). |
| `provenance.prompt_version`/`model_version` (§09) + `prompt_registry` (§20) | **`public.prompt_registry` + `public.model_version`** | One prompt registry, one model registry; runs pin them by FK. |

### 1.3 Pattern-persistence (E5 / S5) — adopt the **approval pattern**, not duplicate tables

E5 §4 (dial-stack `create_pattern_persistence_tables.sql`) and S7 (Semantica
`ApprovalChain`/`PolicyException`/`Precedent`) converge with S4 on one HITL motif: every
machine-proposed pattern is `pending → approved/rejected` with a `(status, reviewed_by,
reviewed_at, review_notes)` quartet plus a `pattern_approval_log` audit trail. **That motif
is adopted here as the canonical `review_task`/`review_decision` + `change_log` machinery.**
The *domain* pattern tables themselves (`detected_patterns`, `spatial_patterns`,
`geofence_violations`, `inferred_relationships`) stay in their domains (D5 geo, D6
behavioral) but **must not carry their own approval columns** — they reference
`analysis.review_decision` and write field changes to `public.change_log`. The one genuinely
new lane with no as-built home is S7 **`Precedent`** (decision-similarity); it lands as
`public.decision_precedent` (optional, §2). `geofence_violations` keeps its S5 semantics of
**auto-approved facts** (review not required) — handled by D5, noted here so the gate logic
is consistent.

### 1.4 As-built invariants preserved & custom-type discipline (`0004`)

- **`evidence.evidence_hash(id)` is the stable artifact anchor.** D8 FKs (`parent_source`,
  `related_source_evidence`) point at it; `analysis.normalized_record.artifact_id` keeps
  working unchanged. No `evidence.*` table is altered by D8.
- **Reuse `0004` custom types, never redefine:** `confidence` (numeric(4,3) 0–1) for every
  score/confidence column (replaces §13's hand-rolled `numeric(4,3) CHECK`); `source_system`
  for cross-store mirror/pointer columns; `source_ref` (composite) for provenance pointers;
  `canonical_id` where a cross-store id is stored; **`sensitivity_tier`** (the renamed
  `0004` `disclosure_tier` enum `public|restricted|sealed`) for access classification on
  artifacts/exports/reviews.
- **`disclosure_tier` double-definition fix (E1 §5.1):** the substantive bitemporal text
  column (`analysis.normalized_record.disclosure_tier` = `contemporaneous|hindsight|
  discovered`) survives; the orphan `0004` enum is **renamed to `sensitivity_tier`** (idempotent
  guard re-stated here for standalone apply; D1 also performs it). D8 consumes
  `sensitivity_tier`, never the bitemporal column.
- **New closed sets use `TEXT + CHECK`, not new enums** (D1 discipline — avoid enum sprawl
  and cross-domain double-definition). `assertion_type`, `run_type`, `court_readiness`,
  `decision`, `lifecycle`, etc. are `TEXT + CHECK`. **`assertion_type` is used in D3/D6/D8
  alike** → flagged in §6 as a candidate for a single shared `0004` enum added in a
  coordinated types migration (do not let three domains each `CREATE TYPE assertion_type`).
- **Court-safe lanes:** every D8 artifact carries `assertion_type ∈ {raw_evidence,
  extracted_fact, inferred_fact, analytical_finding, legal_conclusion}`; sensitive
  behavior/abuse labels are **hypotheses** (`is_sensitive=true`, capped band, blocked from
  promotion) until a `review_decision` exists; both-parties / full-cycle modeling is enforced
  by review triggers R9/R11 (§13), surfaced here as `review_task.trigger_code`.
- **sha256 = identity, md5 = pre-filter only** (`pgcrypto.digest(...,'sha256')`); the
  `change_log` chain and export manifests use sha256. Append-only everywhere; nothing
  overwrites an original or a prior interpretation.

---

## 2. Reconciled DDL

```sql
-- =====================================================================
-- D8 — Provenance, Confidence, Review/Audit & Work-Product Memory Ledger
-- Target: unified PG18 resource (agno-postgres:18-duckdb)
-- Schemas:  analysis  = derived work-product + provenance of derivation
--                       (writes only after recorded approval)
--           public    = HITL audit spine + Agno-managed operational memory
-- Extensions used: pgcrypto (sha256 hash-chain), pg_trgm (recall fuzzy match),
--   btree_gin (mixed jsonb+scalar), citext (names/handles), native uuidv7().
--   tsvector FTS for cheap local recall (Milvus owns semantic/BM25, ADR-0027).
-- Reused 0004 types: confidence, source_system, source_ref, canonical_id,
--   sensitivity_tier (renamed disclosure_tier enum). NEW closed sets = TEXT+CHECK.
-- Boundary: analysis writes come only after a review_decision; public.change_log
--   is the only mutation-bearing audit and is itself append-only.
-- =====================================================================

-- ── 0. Bug fix (E1 §5.1): rename the orphan 0004 enum so it stops colliding
--      with the substantive bitemporal text column. Idempotent; D1 also does it.
DO $$ BEGIN
    ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;   -- public|restricted|sealed
EXCEPTION
    WHEN undefined_object THEN NULL;   -- already renamed, or 0004 not yet applied
    WHEN duplicate_object THEN NULL;   -- sensitivity_tier already present
END $$;

-- ── 1. Append-only / write-once guards (one per schema) ───────────────
CREATE OR REPLACE FUNCTION analysis.forbid_mutation() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'analysis.% is append-only (P4): % blocked', TG_TABLE_NAME, TG_OP;
END $$;
CREATE OR REPLACE FUNCTION public.forbid_mutation() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'public.% is append-only (P4): % blocked', TG_TABLE_NAME, TG_OP;
END $$;

-- =====================================================================
-- A. CONTEXT VERSION REGISTRIES  (public = Agno-managed operational context)
--    Runs pin exact version ids → any result is reproducible (L8).
-- =====================================================================

-- A.1 prompt_registry  (= provenance.prompt_version ⊕ §20 prompt_registry)
CREATE TABLE IF NOT EXISTS public.prompt_registry (
    prompt_id            uuid PRIMARY KEY DEFAULT uuidv7(),
    prompt_name          text NOT NULL,
    prompt_version       text NOT NULL,                 -- semver / int
    prompt_type          text NOT NULL CHECK (prompt_type IN
        ('extraction','classification','summary','agent_instruction',
         'tone_style','review','export')),
    full_prompt_text     text NOT NULL,                 -- small → inline
    body_sha256          bytea NOT NULL,                -- pgcrypto digest of body
    purpose              text,
    inputs_expected      text,
    outputs_expected     text,
    known_limitations    text,
    safety_constraints   text,
    human_approval_required boolean NOT NULL DEFAULT false,   -- court-facing prompts
    superseded_by        uuid REFERENCES public.prompt_registry(prompt_id),
    status               text NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active','superseded','deprecated')),
    created_by           text NOT NULL,
    created_at           timestamptz NOT NULL DEFAULT now(),
    UNIQUE (prompt_name, prompt_version)
);

-- A.2 model_version  (= provenance.model_version)
CREATE TABLE IF NOT EXISTS public.model_version (
    model_version_id  uuid PRIMARY KEY DEFAULT uuidv7(),
    provider          text,                             -- ollama-cloud|nvidia-nim|openrouter|local
    model_id          text NOT NULL,                    -- glm-5.1|nemotron-embed-vl-1b-v2|codestral...
    role              text NOT NULL CHECK (role IN ('llm','embedder','reranker','ocr','asr')),
    version           text,
    dims              int,
    ran_local_capable boolean NOT NULL DEFAULT false,   -- ≤4B local-eligible (ADR-0015 guard)
    params            jsonb NOT NULL DEFAULT '{}',
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (model_id, role, version)
);

-- A.3/4/5 schema_versions / ontology_versions / classification_versions (§20 3.9–3.11)
CREATE TABLE IF NOT EXISTS public.schema_version (
    schema_version_id uuid PRIMARY KEY DEFAULT uuidv7(),
    version_label     text NOT NULL,
    applies_to        text NOT NULL,                    -- table / namespace
    ddl_uri           text, ddl_hash bytea,
    migration_id      text,
    supersedes        uuid REFERENCES public.schema_version(schema_version_id),
    status            text NOT NULL DEFAULT 'active'
                      CHECK (status IN ('active','superseded','deprecated')),
    notes             text,
    created_by        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version_label, applies_to)
);
CREATE TABLE IF NOT EXISTS public.ontology_version (
    ontology_version_id uuid PRIMARY KEY DEFAULT uuidv7(),
    version_label     text NOT NULL,
    source            text NOT NULL,                    -- salem_v3|TraceIQ_V4.1|positive_behaviors.ttl|
                                                        -- behavioral_patterns.ttl|mcl_722_23.ttl|merged
    definition_uri    text, definition_hash bytea,
    node_types        jsonb NOT NULL DEFAULT '[]',
    edge_types        jsonb NOT NULL DEFAULT '[]',
    supersedes        uuid REFERENCES public.ontology_version(ontology_version_id),
    review_status     text NOT NULL DEFAULT 'pending'
                      CHECK (review_status IN ('pending','approved','rejected')),
    notes             text,
    created_by        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version_label, source)
);
CREATE TABLE IF NOT EXISTS public.classification_version (
    classification_version_id uuid PRIMARY KEY DEFAULT uuidv7(),
    version_label     text NOT NULL,
    scheme            text NOT NULL,                    -- message_category|abuse_pattern|MCL_factor|
                                                        -- cycle_phase|legal_relevance
    label_set         jsonb NOT NULL DEFAULT '[]',
    source            text NOT NULL,                    -- detection_patterns.py|seed-patterns.ts|
                                                        -- hurtlex|DARVO|mcl_722_23.ttl|positive_behaviors.ttl|custom
    definition_uri    text, definition_hash bytea,
    supersedes        uuid REFERENCES public.classification_version(classification_version_id),
    review_status     text NOT NULL DEFAULT 'pending'
                      CHECK (review_status IN ('pending','approved','rejected')),
    notes             text,
    created_by        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (version_label, scheme)
);

-- =====================================================================
-- B. PROVENANCE / LINEAGE  (analysis = derived, write-after-approval)
-- =====================================================================

-- B.1 processing_run  (MERGE provenance.run + §20 processing_runs + §13 scoring_run)
CREATE TABLE IF NOT EXISTS analysis.processing_run (
    run_id            uuid PRIMARY KEY DEFAULT uuidv7(),
    run_type          text NOT NULL CHECK (run_type IN
        ('acquisition','file_scan','repository_scan','evidence_ingestion','extraction',
         'ocr','transcription','message_parsing','entity_extraction','temporal_extraction',
         'location_extraction','gps_processing','embedding','graph_projection',
         'surreal_consolidation','ontology_merge','schema_generation','classification',
         'pattern_analysis','legal_issue_mapping','scoring','model_analysis',
         'evidence_task_generation','redaction','export','review')),
    run_purpose       text,
    status            text NOT NULL DEFAULT 'queued'
                      CHECK (status IN ('queued','running','ok','failed','partial',
                                        'cancelled','superseded')),
    actor             text NOT NULL,                    -- service account or person/agent id
    tool_or_model     text,                             -- convenience label
    code_version      text,                             -- platform git SHA
    -- pinned context (the L8 reproducibility contract) — cross-schema FKs to public.*
    prompt_version_id         uuid REFERENCES public.prompt_registry(prompt_id),
    model_version_id          uuid REFERENCES public.model_version(model_version_id),
    schema_version_id         uuid REFERENCES public.schema_version(schema_version_id),
    ontology_version_id       uuid REFERENCES public.ontology_version(ontology_version_id),
    classification_version_id uuid REFERENCES public.classification_version(classification_version_id),
    -- inputs / outputs (soft refs by id; hash-pinned for replay)
    input_evidence_ids uuid[]  NOT NULL DEFAULT '{}',   -- → evidence.evidence_hash(id)
    input_artifact_ids uuid[]  NOT NULL DEFAULT '{}',
    output_artifact_ids uuid[] NOT NULL DEFAULT '{}',
    input_digest      jsonb NOT NULL DEFAULT '[]',      -- [{id, sha256_at_consume}]
    inputs_hash       bytea,                            -- sha256 over input set (resume/dedupe, §13)
    params            jsonb NOT NULL DEFAULT '{}',
    ran_local_only    boolean NOT NULL DEFAULT false,   -- TRUE = no cloud LLM touched evidence (P8)
    cloud_exposure    boolean NOT NULL DEFAULT false,   -- inverse guard, logged either way
    counts_processed  int, counts_failed int,
    confidence_summary jsonb,
    human_review_requirement boolean NOT NULL DEFAULT false,
    replayable        boolean NOT NULL DEFAULT false,   -- all inputs hash-pinned?
    error_message     text,
    summary           text,
    supersedes_run    uuid REFERENCES analysis.processing_run(run_id),
    started_at        timestamptz,
    finished_at       timestamptz,                      -- write-once terminal field
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_run_type_status ON analysis.processing_run (run_type, status);
CREATE INDEX IF NOT EXISTS idx_run_started     ON analysis.processing_run (started_at DESC);
CREATE INDEX IF NOT EXISTS idx_run_prompt      ON analysis.processing_run (prompt_version_id);
CREATE INDEX IF NOT EXISTS idx_run_inputs_gin  ON analysis.processing_run USING gin (input_evidence_ids);

-- B.2 tool_call_ledger  (§20 3.4) — immutable child events of a run
CREATE TABLE IF NOT EXISTS analysis.tool_call_ledger (
    tool_call_id      uuid PRIMARY KEY DEFAULT uuidv7(),
    run_id            uuid REFERENCES analysis.processing_run(run_id),
    tool_name         text NOT NULL,
    tool_category     text NOT NULL CHECK (tool_category IN
        ('read','analysis','write','transfer','deploy','llm','mcp')),
    requested_by      text,                             -- model/agent id
    input_summary     text,
    input_payload_uri text,  input_hash  bytea,         -- L6: large payloads by reference
    output_summary    text,
    output_payload_uri text, output_hash bytea,
    created_artifact_ids uuid[] NOT NULL DEFAULT '{}',
    updated_record_refs  jsonb  NOT NULL DEFAULT '[]',
    runtime_ms        int,
    cost_estimate     numeric(12,4),
    human_approval_status text NOT NULL DEFAULT 'n/a'
        CHECK (human_approval_status IN ('n/a','pending','approved','denied')),
    safety_flags      jsonb NOT NULL DEFAULT '[]',      -- ['external_llm','sensitive_evidence','sweep_risk']
    replayability_status text NOT NULL DEFAULT 'replayable'
        CHECK (replayability_status IN ('replayable','inputs_lost','nondeterministic')),
    errors            text,
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_tcl_tool     ON analysis.tool_call_ledger (tool_name);
CREATE INDEX IF NOT EXISTS idx_tcl_run      ON analysis.tool_call_ledger (run_id);
CREATE INDEX IF NOT EXISTS idx_tcl_approval ON analysis.tool_call_ledger (human_approval_status);
CREATE TRIGGER tcl_append_only BEFORE UPDATE OR DELETE ON analysis.tool_call_ledger
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

-- B.3 artifact_registry  (MERGE provenance.artifact + §20 artifact_registry)
CREATE TABLE IF NOT EXISTS analysis.artifact_registry (
    artifact_id       uuid PRIMARY KEY DEFAULT uuidv7(),
    artifact_kind     text NOT NULL,                    -- broad, open-ended (CHECK-light, see note):
        -- ocr_span|transcript_seg|message|timeline_event|vector_ref|finding|narrative_draft|
        -- schema_draft|final_schema|ontology_draft|ontology_crosswalk|classification_report|
        -- extraction_report|analysis_report|mermaid_diagram|markdown_document|json_export|
        -- sql_migration|python_script|api_specification|test_fixture|evidence_index|
        -- redacted_copy|court_export_draft|human_review_packet|export_package
    title             text,
    format            text,
    sha256            bytea NOT NULL,                   -- artifact content hash (identity)
    path_or_uri       text,                             -- R2 / db pointer (L6: large by reference)
    byte_size         bigint,
    content_inline    text,                             -- small only (L6)
    -- lane typing (court-safe; §13 §4 layer-axis matrix)
    assertion_type    text NOT NULL CHECK (assertion_type IN
        ('raw_evidence','extracted_fact','inferred_fact','analytical_finding','legal_conclusion')),
    confidence        confidence,                       -- 0004 domain (0–1), NULL until scored
    evidence_strength text CHECK (evidence_strength IS NULL OR
                        evidence_strength IN ('weak','moderate','strong')),
    timestamp_certainty text CHECK (timestamp_certainty IS NULL OR
                        timestamp_certainty IN ('exact','approximate','inferred','uncertain')),
    is_sensitive      boolean NOT NULL DEFAULT false,
    sensitivity_tier  sensitivity_tier,                 -- access class (0004 renamed enum)
    -- lineage anchors
    producing_run     uuid REFERENCES analysis.processing_run(run_id),
    parent_artifact_id uuid REFERENCES analysis.artifact_registry(artifact_id),
    derived_from_artifact_ids uuid[] NOT NULL DEFAULT '{}',
    related_source_evidence   uuid[] NOT NULL DEFAULT '{}',   -- → evidence.evidence_hash(id)
    -- promotion-gate lifecycle (§20 §8)
    status            text NOT NULL DEFAULT 'draft' CHECK (status IN
        ('draft','needs_review','active','approved','promoted','rejected',
         'superseded','archived')),
    review_status     text NOT NULL DEFAULT 'none'
        CHECK (review_status IN ('none','pending','approved','rejected')),
    superseded_by     uuid REFERENCES analysis.artifact_registry(artifact_id),
    archive_reason    text,                             -- required when status='archived'
    summary_md        text,
    metadata_json     jsonb NOT NULL DEFAULT '{}',
    created_by        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (status <> 'archived' OR archive_reason IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_art_kind_status ON analysis.artifact_registry (artifact_kind, status);
CREATE INDEX IF NOT EXISTS idx_art_parent      ON analysis.artifact_registry (parent_artifact_id);
CREATE INDEX IF NOT EXISTS idx_art_run         ON analysis.artifact_registry (producing_run);
CREATE INDEX IF NOT EXISTS idx_art_sha256      ON analysis.artifact_registry (sha256);
CREATE INDEX IF NOT EXISTS idx_art_evid_gin    ON analysis.artifact_registry USING gin (related_source_evidence);
CREATE INDEX IF NOT EXISTS idx_art_sensitive   ON analysis.artifact_registry (is_sensitive) WHERE is_sensitive;

-- B.4 lineage_edge  (provenance.lineage_edge) — the derivation DAG
CREATE TABLE IF NOT EXISTS analysis.lineage_edge (
    edge_id           uuid PRIMARY KEY DEFAULT uuidv7(),
    child_artifact    uuid NOT NULL REFERENCES analysis.artifact_registry(artifact_id),
    parent_artifact   uuid REFERENCES analysis.artifact_registry(artifact_id),
    parent_source     uuid REFERENCES evidence.evidence_hash(id),   -- as-built source/artifact anchor
    producing_run     uuid REFERENCES analysis.processing_run(run_id),
    role              text NOT NULL CHECK (role IN
        ('derived_from','supersedes','corroborates','contradicts')),
    note              text,
    created_at        timestamptz NOT NULL DEFAULT now(),
    CHECK (parent_artifact IS NOT NULL OR parent_source IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_edge_child  ON analysis.lineage_edge (child_artifact);
CREATE INDEX IF NOT EXISTS idx_edge_parent ON analysis.lineage_edge (parent_artifact);
CREATE INDEX IF NOT EXISTS idx_edge_source ON analysis.lineage_edge (parent_source);
CREATE TRIGGER edge_append_only BEFORE UPDATE OR DELETE ON analysis.lineage_edge
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

-- =====================================================================
-- C. CONFIDENCE / SCORING  (analysis; §13)
-- =====================================================================

-- C.1 score_band_config — versioned thresholds (kills R5's hard-coded 0.6 cliff)
CREATE TABLE IF NOT EXISTS analysis.score_band_config (
    config_version  text PRIMARY KEY,
    bands           jsonb NOT NULL,                     -- [{band, lo, hi, phrasing}, ...]
    effective_from  timestamptz NOT NULL DEFAULT now(),
    changed_by      text NOT NULL,
    rationale       text NOT NULL
);

-- C.2 score — one row per (target, axis, run). APPEND-ONLY, bitemporal supersession.
CREATE TABLE IF NOT EXISTS analysis.score (
    score_id        uuid PRIMARY KEY DEFAULT uuidv7(),
    target_kind     text NOT NULL,                      -- evidence_item|timeline_event|person_edge|
                                                        -- claim|finding|artifact|export_item
    target_id       uuid NOT NULL,                      -- resolved per target_kind
    score_type      text NOT NULL CHECK (score_type IN
        ('extraction','temporal','identity','location','evidence_strength',
         'legal_relevance','abuse_pattern','corroboration','contradiction','court_readiness')),
    value           confidence NOT NULL,                -- 0004 domain (0–1) — reuse, don't redefine
    band            text NOT NULL CHECK (band IN
        ('very_low','low','medium','high','very_high')),
    method          text NOT NULL CHECK (method IN ('rule','model','human','hybrid')),
    method_detail   jsonb NOT NULL DEFAULT '{}',        -- rule id/weights, model id+ver, reviewer, calibrated
    rationale       text NOT NULL,                      -- court-safe, associational language
    evidence_refs   uuid[] NOT NULL DEFAULT '{}',       -- ≥1 cite required for strength/legal/abuse/corrob/contra
    assertion_type  text NOT NULL CHECK (assertion_type IN
        ('raw_evidence','extracted_fact','inferred_fact','analytical_finding','legal_conclusion')),
    config_version  text REFERENCES analysis.score_band_config(config_version),
    scoring_run_id  uuid NOT NULL REFERENCES analysis.processing_run(run_id),
    recheck_after   timestamptz,                        -- decay (brittle parser / cross-platform ER)
    stale           boolean NOT NULL DEFAULT false,     -- set on version bump, never deleted
    valid_from      timestamptz NOT NULL DEFAULT now(),
    valid_to        timestamptz,                        -- NULL = current
    superseded_by   uuid REFERENCES analysis.score(score_id),
    created_by      text NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_score_target  ON analysis.score (target_kind, target_id);
CREATE INDEX IF NOT EXISTS idx_score_current ON analysis.score (score_type) WHERE valid_to IS NULL;
CREATE INDEX IF NOT EXISTS idx_score_run     ON analysis.score (scoring_run_id);
-- scores are append-only: re-score = new row + set valid_to/superseded_by on prior (no UPDATE of value)

-- =====================================================================
-- D. REVIEW / HITL  (analysis; §13 task/decision split, folds §09 review + S5 pattern_approval_log)
-- =====================================================================

-- D.1 review_task — one blocking task per fired trigger R1–R13. APPEND-ONLY state log.
CREATE TABLE IF NOT EXISTS analysis.review_task (
    task_id         uuid PRIMARY KEY DEFAULT uuidv7(),
    trigger_code    text NOT NULL,                      -- 'R1'..'R13' (§13 §5 gate matrix)
    target_kind     text NOT NULL,
    target_id       uuid NOT NULL,                      -- artifact / score / pattern / export
    score_ids       uuid[] NOT NULL DEFAULT '{}',       -- exact score snapshot under review
    blocks          text NOT NULL,                      -- what transition/export is blocked
    reviewer_role   text,                               -- owner|legal_aware|reviewer_of_record
    state           text NOT NULL DEFAULT 'pending'
        CHECK (state IN ('pending','in_review','resolved')),
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rtask_state  ON analysis.review_task (state, trigger_code);
CREATE INDEX IF NOT EXISTS idx_rtask_target ON analysis.review_task (target_kind, target_id);

-- D.2 review_decision — reviewer-of-record. APPEND-ONLY (re-review = new row).
--     Subsumes provenance.review (court_readiness, sensitive_label, set_confidence)
--     and S5 pattern_approval_log (action/actor/prev->new status).
CREATE TABLE IF NOT EXISTS analysis.review_decision (
    decision_id     uuid PRIMARY KEY DEFAULT uuidv7(),
    task_id         uuid REFERENCES analysis.review_task(task_id),
    target_kind     text NOT NULL,                      -- mirrors task; lets non-task reviews exist
    target_id       uuid NOT NULL,
    reviewer        text NOT NULL,                      -- HUMAN principal of record (never a model)
    decision        text NOT NULL CHECK (decision IN
        ('approved','rejected','needs_changes','needs_context','escalated','hold')),
    -- scored/labelled at review time (master-prompt §10)
    set_confidence  confidence,
    set_evidence_strength text CHECK (set_evidence_strength IS NULL OR
                          set_evidence_strength IN ('weak','moderate','strong')),
    sensitive_label_decision jsonb,                     -- {label, status: approved|denied|insufficient_evidence}
    court_readiness text NOT NULL DEFAULT 'not_reviewed' CHECK (court_readiness IN
        ('not_reviewed','draft','needs_corroboration','review_passed',
         'court_ready','excluded','strategically_sensitive')),
    tier_approved   sensitivity_tier,                   -- disclosure tier this decision approves for
    requires_corroboration boolean NOT NULL DEFAULT false,
    score_snapshot  uuid[] NOT NULL DEFAULT '{}',       -- score_id[] exactly as reviewed
    prompt_version_id  uuid REFERENCES public.prompt_registry(prompt_id),
    ontology_version_id uuid REFERENCES public.ontology_version(ontology_version_id),
    schema_version_id  uuid REFERENCES public.schema_version(schema_version_id),
    rationale       text NOT NULL,                      -- court-safe; explanation != excuse
    decided_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_rdec_target ON analysis.review_decision (target_kind, target_id);
CREATE INDEX IF NOT EXISTS idx_rdec_task   ON analysis.review_decision (task_id);
CREATE TRIGGER rdec_append_only BEFORE UPDATE OR DELETE ON analysis.review_decision
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

-- =====================================================================
-- E. REDACTION & EXPORT  (analysis; §09 §8–§9) — versioned, non-destructive
-- =====================================================================
CREATE TABLE IF NOT EXISTS analysis.redaction (
    redaction_id      uuid PRIMARY KEY DEFAULT uuidv7(),
    redaction_run     uuid REFERENCES analysis.processing_run(run_id),
    source_artifact   uuid NOT NULL REFERENCES analysis.artifact_registry(artifact_id),
    redacted_artifact uuid NOT NULL REFERENCES analysis.artifact_registry(artifact_id),
    policy_version    text NOT NULL,
    redaction_map     jsonb NOT NULL,                   -- [{span/bbox, category: PII|minor|in_camera, reason}]
    reversible        boolean NOT NULL DEFAULT true,
    authorized_by     text NOT NULL,                    -- reviewer who approved policy application
    created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER redaction_append_only BEFORE UPDATE OR DELETE ON analysis.redaction
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

CREATE TABLE IF NOT EXISTS analysis.export (
    export_id          uuid PRIMARY KEY DEFAULT uuidv7(),
    export_run         uuid REFERENCES analysis.processing_run(run_id),
    package_uri        text NOT NULL,                   -- R2 immutable package object
    manifest_sha256    bytea NOT NULL,                  -- hash of the manifest itself
    signature          bytea,                           -- detached signature over manifest
    included_artifacts uuid[] NOT NULL,
    tier               sensitivity_tier NOT NULL,       -- disclosure tier of the package
    purpose            text,                            -- disclosure|exhibit|client_review
    requested_by       text NOT NULL,
    approved_by        text NOT NULL,                   -- HUMAN court-facing gate (R3)
    blocked_by_open_questions uuid[] NOT NULL DEFAULT '{}',  -- export blocked while non-empty
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER export_append_only BEFORE UPDATE OR DELETE ON analysis.export
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

-- =====================================================================
-- F. WORK-PRODUCT OPERATIONAL MEMORY  (public = Agno-managed)
-- =====================================================================

-- F.1 memory_items — durable project memory (mirrors to Graphiti for non-sensitive facts only)
CREATE TABLE IF NOT EXISTS public.memory_items (
    memory_id        uuid PRIMARY KEY DEFAULT uuidv7(),
    memory_type      text NOT NULL CHECK (memory_type IN
        ('user_preference','project_fact','evidence_fact','hypothesis','analysis_finding',
         'design_decision','open_question','warning','artifact_summary','run_summary',
         'deprecated_memory')),
    title            text NOT NULL,
    summary          text,
    content_inline   text,                              -- small (L6)
    content_uri      text, content_hash bytea,          -- large by reference
    source_of_memory text,
    created_by       text NOT NULL,                     -- human | agent id | model id
    confidence       confidence,                        -- 0004 domain
    assertion_type   text CHECK (assertion_type IS NULL OR assertion_type IN
        ('raw_evidence','extracted_fact','inferred_fact','analytical_finding','legal_conclusion')),
    status           text NOT NULL DEFAULT 'active' CHECK (status IN
        ('active','draft','needs_review','superseded','deprecated','rejected','archived')),
    review_status    text NOT NULL DEFAULT 'none'
        CHECK (review_status IN ('none','pending','approved','rejected')),
    is_sensitive     boolean NOT NULL DEFAULT false,
    mirror_store     source_system,                     -- 0004 enum: which store mirrored to (neo4j…)
    superseded_by    uuid REFERENCES public.memory_items(memory_id),
    related_artifact_ids uuid[] NOT NULL DEFAULT '{}',
    related_evidence_ids uuid[] NOT NULL DEFAULT '{}',  -- canonical evidence.evidence_hash(id)
    related_ontology_id  uuid REFERENCES public.ontology_version(ontology_version_id),
    related_schema_id    uuid REFERENCES public.schema_version(schema_version_id),
    tags             jsonb NOT NULL DEFAULT '[]',
    fts              tsvector GENERATED ALWAYS AS
                       (to_tsvector('english', coalesce(title,'') || ' ' || coalesce(summary,''))) STORED,
    created_at       timestamptz NOT NULL DEFAULT now(),
    updated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mem_type_status ON public.memory_items (memory_type, status);
CREATE INDEX IF NOT EXISTS idx_mem_review      ON public.memory_items (status, review_status);
CREATE INDEX IF NOT EXISTS idx_mem_sensitive   ON public.memory_items (is_sensitive) WHERE is_sensitive;
CREATE INDEX IF NOT EXISTS idx_mem_fts         ON public.memory_items USING gin (fts);
CREATE INDEX IF NOT EXISTS idx_mem_title_trgm  ON public.memory_items USING gin (title gin_trgm_ops);

-- F.2 decision_log — design & analysis decisions (local echo of the ADR set)
CREATE TABLE IF NOT EXISTS public.decision_log (
    decision_id      uuid PRIMARY KEY DEFAULT uuidv7(),
    decision_title   text NOT NULL,
    decision_type    text NOT NULL CHECK (decision_type IN
        ('schema','ontology','legal_relevance','evidence_classification','tooling',
         'storage','privacy','export','human_review')),
    context          text,                              -- cite ADR number here
    options_considered jsonb NOT NULL DEFAULT '[]',
    decision_made    text NOT NULL,
    reasoning_summary text,
    evidence_or_artifacts_considered jsonb NOT NULL DEFAULT '[]',
    owner            text NOT NULL,                     -- human/agent
    reversibility    text CHECK (reversibility IN ('reversible','costly','irreversible')),
    related_risks    text,
    related_open_questions uuid[] NOT NULL DEFAULT '{}',
    supersedes       uuid REFERENCES public.decision_log(decision_id),
    review_status    text NOT NULL DEFAULT 'none'
        CHECK (review_status IN ('none','pending','approved','rejected')),
    decided_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_dlog_type   ON public.decision_log (decision_type);
CREATE INDEX IF NOT EXISTS idx_dlog_review ON public.decision_log (review_status);

-- F.3 session_summaries — cross-session resume (mirrors .remember / MEMORY.md)
CREATE TABLE IF NOT EXISTS public.session_summaries (
    session_id       uuid PRIMARY KEY DEFAULT uuidv7(),
    session_start    timestamptz NOT NULL,
    session_end      timestamptz,
    user_goal        text,
    work_completed   text,
    files_inspected  jsonb NOT NULL DEFAULT '[]',
    artifacts_created jsonb NOT NULL DEFAULT '[]',
    decisions_made   uuid[] NOT NULL DEFAULT '{}',      -- → decision_log
    open_questions   uuid[] NOT NULL DEFAULT '{}',      -- → open_questions
    next_actions     text,
    blockers         text,
    tone_preference_notes text,
    important_warnings text,
    related_run_ids  uuid[] NOT NULL DEFAULT '{}',
    fts              tsvector GENERATED ALWAYS AS
                       (to_tsvector('english', coalesce(user_goal,'') || ' ' || coalesce(work_completed,''))) STORED,
    created_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sess_start ON public.session_summaries (session_start DESC);
CREATE INDEX IF NOT EXISTS idx_sess_fts   ON public.session_summaries USING gin (fts);
CREATE TRIGGER sess_append_only BEFORE UPDATE OR DELETE ON public.session_summaries
  FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();   -- insert-once per session

-- F.4 open_questions — unresolved issues & discovered gaps
CREATE TABLE IF NOT EXISTS public.open_questions (
    question_id      uuid PRIMARY KEY DEFAULT uuidv7(),
    question_text    text NOT NULL,
    category         text NOT NULL CHECK (category IN
        ('data_gap','schema','ontology','legal_relevance','corroboration_needed',
         'privacy','technical')),
    raised_by        text,
    status           text NOT NULL DEFAULT 'open' CHECK (status IN
        ('open','investigating','answered','wont_fix','superseded')),
    answer_summary   text,
    answered_by      text,
    answered_at      timestamptz,
    related_run_id   uuid REFERENCES analysis.processing_run(run_id),
    related_artifact_ids uuid[] NOT NULL DEFAULT '{}',
    blocks_export    boolean NOT NULL DEFAULT false,
    requires_corroboration boolean NOT NULL DEFAULT false,
    priority         int NOT NULL DEFAULT 3,
    raised_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_oq_status   ON public.open_questions (status, priority);
CREATE INDEX IF NOT EXISTS idx_oq_category ON public.open_questions (category);
CREATE INDEX IF NOT EXISTS idx_oq_blocks   ON public.open_questions (blocks_export) WHERE blocks_export;

-- F.5 decision_precedent  (OPTIONAL — S7 Semantica Precedent; decision-similarity lane)
CREATE TABLE IF NOT EXISTS public.decision_precedent (
    precedent_id      uuid PRIMARY KEY DEFAULT uuidv7(),
    decision_id       uuid NOT NULL REFERENCES public.decision_log(decision_id),
    source_decision_id uuid NOT NULL REFERENCES public.decision_log(decision_id),
    similarity_score  confidence,                       -- 0004 domain
    relationship_type text CHECK (relationship_type IN
        ('similar_scenario','same_policy','exception_precedent')),
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- =====================================================================
-- G. AUDIT SPINE  (public.change_log) — the ONE append-only, hash-chained log
--    MERGE of provenance.audit_log (§09) + change_log (§20).
-- =====================================================================
CREATE TABLE IF NOT EXISTS public.change_log (
    seq              bigint GENERATED ALWAYS AS IDENTITY,
    change_id        uuid PRIMARY KEY DEFAULT uuidv7(),
    table_name       text NOT NULL,
    record_id        uuid,
    field_name       text,                              -- NULL = whole-row / event-level
    action           text NOT NULL,                     -- insert|update|ingest|run_start|run_end|
                                                        -- review|redact|export|supersede|archive|
                                                        -- access|integrity_violation
    previous_value   text,
    new_value        text,
    actor            text NOT NULL,                     -- human id | agent/model id | system
    change_origin    text NOT NULL CHECK (change_origin IN
        ('model_generated','human_approved','system')),
    reason           text,
    related_run_id      uuid REFERENCES analysis.processing_run(run_id),
    related_decision_id uuid REFERENCES public.decision_log(decision_id),
    detail           jsonb,                             -- before/after refs, input hashes
    prev_change_hash bytea,                             -- sha256 of previous row (chain)
    row_hash         bytea NOT NULL,                    -- sha256(canonical row incl. prev_change_hash)
    change_timestamp timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_clog_record ON public.change_log (table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_clog_time   ON public.change_log (change_timestamp);
CREATE INDEX IF NOT EXISTS idx_clog_origin ON public.change_log (change_origin);
CREATE TRIGGER clog_append_only BEFORE UPDATE OR DELETE ON public.change_log
  FOR EACH ROW EXECUTE FUNCTION public.forbid_mutation();   -- the audit spine cannot be edited

-- Hash-chain maintainer: compute prev/row hash on insert (pgcrypto digest, sha256).
CREATE OR REPLACE FUNCTION public.change_log_chain() RETURNS trigger
  LANGUAGE plpgsql AS $$
DECLARE prev bytea;
BEGIN
  SELECT row_hash INTO prev FROM public.change_log ORDER BY seq DESC LIMIT 1;
  NEW.prev_change_hash := prev;
  NEW.row_hash := digest(
      coalesce(NEW.table_name,'') || '|' || coalesce(NEW.record_id::text,'') || '|' ||
      coalesce(NEW.field_name,'') || '|' || NEW.action || '|' ||
      coalesce(NEW.previous_value,'') || '|' || coalesce(NEW.new_value,'') || '|' ||
      NEW.actor || '|' || NEW.change_origin || '|' ||
      coalesce(encode(prev,'hex'),''), 'sha256');
  RETURN NEW;
END $$;
CREATE TRIGGER clog_chain BEFORE INSERT ON public.change_log
  FOR EACH ROW EXECUTE FUNCTION public.change_log_chain();

-- Per-table audit triggers (generated for every D8 + case table): an AFTER INSERT/UPDATE
-- trigger writes the (table, record, field, prev, new, actor, origin) tuple into
-- public.change_log. The MP "especially important" set — abuse-pattern labels,
-- legal-relevance labels, entity merges, timeline/location corrections, evidence-strength
-- scores, court-export status, review decisions — are exactly the fields these triggers
-- must capture. (Template omitted for brevity; one parametrised function over TG_TABLE_NAME.)
```

> **`artifact_kind` is intentionally `TEXT` (no CHECK):** the kind vocabulary spans evidence
> lanes *and* work-product lanes and will grow (new report types, new parsers). A closed enum
> here would force a migration per new kind and risks the same staleness as `0004 event_type`.
> The lane discipline that *matters* for court-safety is `assertion_type` (CHECK-enforced),
> not the free-grained kind. Validation of `artifact_kind` is a service-layer concern.

---

## 3. Decision table

Legend: **A**=adopt · **AD**=adapt · **M**=merge · **S**=split · **D**=deprecate.

| Table / field | Decision | Source (as-built / paper / prior) | Note |
|---|---|---|---|
| `analysis.processing_run` | **M** | paper §09 `provenance.run` + §20 `processing_runs` + §13 `scoring_run` | Three run tables collapsed into one; `scoring`/`review` are `run_type` values. The single lineage anchor. |
| `…run.run_type` (26-value CHECK) | M | union of §09 taxonomy + §20 run_type + `scoring` | Superset of all three vocabularies. |
| `…run.ran_local_only` / `cloud_exposure` | A | §13 `ran_local_only` + §09 P8 | ADR-0015 guard — was evidence touched by a cloud LLM. |
| `…run.{prompt,model,schema,ontology,classification}_version_id` | A | §20 L8 pinned-version contract + §09 §6.3 | Cross-schema FK to `public.*` registries → reproducibility. |
| `…run.inputs_hash` / `input_digest` | A | §13 `inputs_hash` + §09 input-digest | sha256 of inputs for replay/dedupe. |
| `analysis.tool_call_ledger` | A | paper §20 3.4 | Immutable child of run; large payloads by reference (L6); `safety_flags` carry `external_llm`/`sensitive_evidence`/`sweep_risk` (CONTEXT_PACK §4 approval-gated tools). |
| `analysis.artifact_registry` | **M** | §09 `provenance.artifact` + §20 `artifact_registry` | One registry for evidence-derived AND work-product artifacts; shared lineage/assertion/confidence. |
| `…artifact.assertion_type` | A | §09 P6 / §13 §4 / CONTEXT_PACK §6 | 5-lane court-safe typing; `TEXT+CHECK` (no as-built enum). |
| `…artifact.confidence` | **AD** | §13 (was `numeric(4,3) CHECK`) → **0004 `confidence` domain** | Reuse the as-built domain instead of redefining the numeric+CHECK. |
| `…artifact.sensitivity_tier` | A | **0004 renamed enum** (E1 §5.1 fix) | Access class; consumes the renamed `disclosure_tier`→`sensitivity_tier`. |
| `…artifact.status` (promotion gate) | A | §20 §8 state machine | draft→needs_review→approved→promoted→superseded; rejected/archived retained forever. |
| `…artifact_kind` | **AD** | §09 `artifact_kind` + §20 `artifact_type` | Merged + opened to `TEXT` (no CHECK) — see note above. |
| `analysis.lineage_edge` | A | §09 `provenance.lineage_edge` | DAG; `corroborates`/`contradicts` roles back the salem_v3 `CONTRADICTS` impeachment primitive (HITL). `parent_source` → `evidence.evidence_hash(id)`. |
| `analysis.score` | A | paper §13 `analysis.score` | 10 axes, append-only bitemporal supersession; `value` retyped to 0004 `confidence` domain; `recheck_after`/`stale` decay. |
| `analysis.score_band_config` | A | §13 | Versioned thresholds — kills R5's hard-coded `0.6` HIGH/MED/LOW cliff. |
| `analysis.review_task` | A | §13 | Blocking task per trigger R1–R13 (sensitive label, legal relevance, court sign-off, contradiction, custody-break, one-sided-cycle, user-conduct…). |
| `analysis.review_decision` | **M** | §13 `review_decision` + §09 `provenance.review` + **E5/S5 `pattern_approval_log`** | Reviewer-of-record; folds §09 `court_readiness`/`sensitive_label_decision`/`set_confidence`; subsumes the pattern-approval audit motif. Human-only `reviewer`. |
| `analysis.redaction` | A | §09 §8 | Non-destructive; new redacted artifact + reversible map. |
| `analysis.export` | A | §09 §9 | Court-package manifest (sha256 + signature); `tier` (sensitivity_tier); `blocked_by_open_questions`; human `approved_by` (R3). |
| `public.change_log` | **M** | §09 `provenance.audit_log` + §20 `change_log` | ONE append-only, hash-chained spine (pgcrypto sha256). Field-level + event-level in one table; per-table triggers feed it. |
| `public.prompt_registry` | **M** | §09 `provenance.prompt_version` + §20 `prompt_registry` | One prompt registry; versioned; `human_approval_required` for court-facing prompts. |
| `public.model_version` | A | §09 `provenance.model_version` | Model registry; `ran_local_capable` ≤4B eligibility. |
| `public.{schema,ontology,classification}_version` | A | §20 3.9–3.11 | Context registries; first rows = salem_v3 / TraceIQ_V4.1 / positive_behaviors.ttl / detection_patterns_256 / mcl_722_23.ttl (review_status=pending). |
| `public.memory_items` | A | §20 3.1 | Durable project memory; `tsvector`+`pg_trgm` recall (Milvus owns semantic, ADR-0027); `mirror_store` = 0004 `source_system`; Graphiti mirror for non-sensitive Project-Fact/Decision/Preference only. |
| `public.decision_log` | A | §20 3.6 | Local echo of the ADR set; `reversibility` lens. |
| `public.session_summaries` | A | §20 3.7 | Cross-session resume; insert-once; mirrors `.remember`/`MEMORY.md`. |
| `public.open_questions` | A | §20 3.8 | `blocks_export` gates court output; `requires_corroboration`. |
| `public.decision_precedent` | **A (optional)** | **E5/S7** Semantica `Precedent` | The one prior lane with no as-built home; decision-similarity. |
| `0004` enum `disclosure_tier` → `sensitivity_tier` | **AD (bug fix)** | E1 §5.1 | Rename so it stops colliding with the bitemporal text column; D8 + D1 both apply the idempotent guard. |
| §13 `score.value numeric(4,3) CHECK` | **AD** | redefine → reuse **0004 `confidence`** | Don't redefine an as-built type. |
| §09 `CREATE SCHEMA provenance` + all `provenance.*` homes | **AD (re-home)** | E1 boundary | Dropped; tables moved to `analysis`/`public`. No parallel top-level schema. |
| §20 SQLite-`ledger.db` as canonical store | **AD** | owner guardrail | Canonical → PG; SQLite/DuckDB demoted to operational mirror (same UUIDv7 keys). |
| S5 `detected_patterns`/`spatial_patterns`/`geofence_violations`/`inferred_relationships` (the *tables*) | **D here / A in D5–D6** | E5/S5 | Domain tables stay in D5/D6; their **approval columns are deprecated** in favor of D8 `review_decision` + `change_log`. `geofence_violations` keeps auto-approved-fact semantics. |
| `provenance.custody_hash` (H1/H2/H3) | **D here** | already in **D1** | Owned by D1 (`evidence.evidence_hash` extended). D8 references `evidence.evidence_hash(id)`. |

---

## 4. Migration notes (ALTER/CREATE to reach this on the LIVE DB)

**Pre-flight (verify-before-claiming — addendum D.9).** Diff against the live
`agno-postgres:18-duckdb` catalog before applying anything:
1. `SELECT version();` → **must be PG18** (every PK uses native `uuidv7()`, ungated — E1 §5.5).
2. `\dx` → confirm `pgcrypto`, `pg_trgm`, `citext`, `btree_gin` present (E1 §1). `pgcrypto`
   is required for `change_log` hash-chaining and `body_sha256`.
3. `\dn` → confirm schemas `evidence`, `analysis`, `public` exist (E1 §0).
4. `\dT` → check whether `0004` types exist on the **live** volume (apply-once drift, E1 §5.4).
   If `disclosure_tier`/`confidence`/`source_system`/`source_ref` are **absent**, run
   `sql/0004_custom_types.sql` by hand FIRST (D8 depends on `confidence`, `sensitivity_tier`,
   `source_system`, `source_ref`).

**Apply order (idempotent; all `CREATE … IF NOT EXISTS` / guarded):**
1. **Enum rename** `disclosure_tier → sensitivity_tier` (DDL §0). Coordinate with D1 — whichever
   runs first performs it; the other's guard no-ops. **Check no live column already binds the
   enum** (`SELECT … FROM pg_attribute …`) — E1 §4 confirms it is currently orphan/unused, so
   the rename is safe.
2. **Guard functions** `analysis.forbid_mutation()`, `public.forbid_mutation()`,
   `public.change_log_chain()`.
3. **Registries** (§A) → **runs/artifacts/lineage** (§B) → **scoring** (§C) → **review** (§D)
   → **redaction/export** (§E) → **operational memory** (§F) → **change_log** (§G).
   Order matters only for FK targets (registries before runs; runs+artifacts before
   lineage/score/review/export).
4. **Append-only triggers** attach after each table (already inlined).
5. **Per-table audit triggers** → generate one `AFTER INSERT OR UPDATE` trigger per D8 table
   (and per D3/D5/D6 case table) calling the parametrised change-log writer. Apply LAST so
   bulk seed inserts (step 7) don't each emit audit rows unless desired.
6. **Seed `score_band_config`** v1 (the five bands from §13 §2) and **`schema/ontology/
   classification_version`** first rows (salem_v3, TraceIQ_V4.1, positive_behaviors.ttl,
   detection_patterns_256, mcl_722_23.ttl) at `review_status='pending'`.
7. **Bootstrap rows** (§20 §10) — seed this reconciliation workflow as the first
   `processing_run`/`artifact_registry`/`decision_log`/`open_questions`/`session_summaries`
   rows so the ledger is self-describing.

**Non-breaking guarantees:** D8 creates only new objects + one enum *rename*. No `evidence.*`
or `analysis.normalized_record` column is altered; `evidence.evidence_hash(id)` stays the FK
anchor. Legacy `public.agent_run`/`approval_request` (E1 §5.7) are untouched — D8's
`review_*` tables supersede them functionally but do not drop them (never-delete rule).

**Mirror sync (out of band):** the SQLite `ledger.db` → PG sync job upserts by UUIDv7 PK into
the `public.*` operational tables; on conflict it inserts a supersession row (never an
in-place UPDATE), so the append-only invariant holds across the mirror boundary.

---

## 5. Connection to the four-resource topology

This domain lives **entirely inside resource #1** (PG18 + PostGIS + embedded `pg_duckdb`).
It references the others only by id: **Milvus** (#2) — `run_type='embedding'` records the
collection/row_id; vectors never land here. **Neo4j+Graphiti** (#3) — `memory_items.mirror_store`
marks durable non-sensitive project/decision facts mirrored for bitemporal recall; raw/abuse
evidence is **never** mirrored (CONTEXT_PACK §4). **SurrealDB** (#4, Phase D) —
`run_type='surreal_consolidation'` logs what was consolidated. DuckDB (`pg_duckdb`) provides
the `vw_lineage(artifact_id)` analytical view joining run/artifact/lineage/score/review and
reading the R2 Parquet/JSONL replay logs — the same engine canonically, so a mirror query
ports unchanged.

---

## 6. Needs-human-review / open items

- **Shared `assertion_type` enum (cross-domain):** D3/D6/D8 all use the same 5-lane vocabulary
  as `TEXT+CHECK`. To avoid re-introducing a double-definition, a single
  `CREATE TYPE assertion_type AS ENUM(...)` should be added to a coordinated `0005` types
  migration and the CHECKs retro-fitted. **Do not let each domain define it independently.**
  Owner/architect sign-off on whether to enum-ify now or stay TEXT.
- **`change_log` hash-chain canonicalization** (§G `change_log_chain`) concatenates fields with
  a `|` delimiter — fine as a first cut, but the exact canonical-serialization recipe must be
  version-pinned (mirror §09's `hash_canon_version`) before it is relied on for tamper-evidence
  in any export; needs the same sign-off as the export-manifest signing key (unspecified — ADR
  needed: where the private key lives, HSM vs pgcrypto, rotation).
- **Score-band thresholds & model calibration caps** (§13 §10) are bootstrapped defaults — they
  MUST be tuned against a real labeled review set before any court-tier reliance. Model scores
  are capped at `high` band pre-calibration; the per-axis calibration threshold and the
  minimum-episode count `N` for an abuse-pattern to leave hypothesis are owner-tunable, not
  fixed here.
- **`decision_precedent` (S7)** is included optional — confirm the Semantica precedent-similarity
  lane is in scope for this build before wiring node2vec/embedding similarity into it.
- **Per-table audit trigger generation** (the parametrised change-log writer) is described, not
  fully written — the `_stale`-archival path and the "especially important" field whitelist
  (MP 1268–1278) need to be enumerated per case table during implementation.
- **Live-catalog drift** (E1 §5.4 / addendum D.9): D8 assumes `0004` types and PG18 are present;
  if the live volume predates them, the §4 pre-flight remediation runs first — verify, don't
  assume.
