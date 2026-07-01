# D7 — Legal/Custody Relevance, Evidence-Gathering Tasks & Court Export (PG Domain Reconciliation)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> **Scope:** the *action + court-facing* lane of the unified PostgreSQL resource
> (PG18 + PostGIS + embedded DuckDB via `pg_duckdb`). This domain owns four coupled things:
> (1) the **MCL 722.23 (a)–(l) custody-factor reference** + per-case **legal-issue map**;
> (2) the **court-evidence spine** — `evidence_item`/exhibits, `factor_citation`
> (supports/contradicts polarity), and the curated **legal timeline**;
> (3) the **evidence-gathering plan** — findings → trackable tasks → drafted discovery
> instruments (subpoena/RFA/RFP/witness Q) → completion evidence, append-only and HITL-gated;
> (4) the **court-export gate** — a view that releases an item only when its confidence tier
> qualifies **AND** it is HITL-approved **AND** `safe_for_legal_use` is set.
>
> **Law (ground truth):** `extracted/E1_asbuilt_inventory.md` (security boundary + `0004`
> custom types). **Donor intents:** `extracted/E2_messaging_core.md` (§D/§E court tables —
> `mcl_factors`, `factor_citations`, `evidence_items`, `timeline_events`, behavior↔factor
> arrays), paper section `sections/12-evidence-plan.md` (the `evidence_plan` task model),
> `discovery/A3_crosswalk.md` (salem_v3 `mcl_factor`, `vw_forensic_evidence_package`
> HIGH/MED/LOW tiering), `discovery/CONTEXT_PACK.md`, the extension/reconciliation addendum,
> and sibling `domains/D1-source-custody.md` (the `evidence.source`/`file_node`/`evidence_hash`
> anchors this domain FKs into, and the `sensitivity_tier` enum rename).

---

## 1. Reconciliation stance (what changed vs the paper design)

The paper §12 is strong on *intent* but **invents two parallel top-level schemas** —
`evidence_plan.*` (tasks) and `legal.*` (issues/factors) — and a private enum sprawl
(`priority_t`, `risk_t`, `status_t`, `assertion_t`, `confidence_t`, `instrument_t`,
`sensitivity_t`). Both violate the as-built security boundary (E1 §0: only `evidence`,
`analysis`, `public`) and the `0004` custom-type contract. This reconciliation **re-homes
every D7 table under `analysis`** (these are all *derived/curated* artifacts — findings turned
into tasks, raw evidence curated into exhibits — so they belong in the write-after-approval
lane, never in `evidence` and never in a new top-level schema) and **collapses the private
enums to `TEXT + CHECK`**, mirroring the as-built style (`normalized_record.disclosure_tier`,
`agent_run.status`) per D1's discipline (avoid a sprawl of one-off enums; reuse `0004`).

| Paper / donor construct | Reconciled home | Why |
|---|---|---|
| `legal.custody_factor` (MCL 722.23) ; E2 `mcl_factors` (varchar) | **`analysis.custody_factor`** (PK = `mcl_factor` enum) | Reuse the as-built `0004` `mcl_factor` enum (`a`…`l`) as the key; `legal` becomes a *sub-domain prefix*, not a schema. |
| `legal.legal_issue` | **`analysis.legal_issue`** + `analysis.legal_issue_factor` | Per-case legal-issue map; weights are policy inputs (HITL). |
| E2 `evidence_items` / `messaging_evidence_items` (+ exhibits) | **`analysis.evidence_item`** | Merge the two E2 iterations (S1 court-prep richness ⊕ B `messaging_*` custody); FK to `evidence.source`/`file_node`/`evidence_hash`. |
| E2 `factor_citations` (+ S1 `supports_factor`/`strength`) | **`analysis.factor_citation`** | Keep S1's legally-critical supports/contradicts polarity + strength. |
| E2 court `timeline_events` (S1 full) | **`analysis.legal_timeline_event`** | Curated *legal* chronology (distinct from the raw geo `timeline_event` in E3/D3). |
| `evidence_plan.task` + 8 satellite tables | **`analysis.evidence_task`** + `task_event`/`task_revision`/`task_person`/`task_legal_link`/`task_dependency`/`discovery_request`/`discovery_request_revision`/`completion_evidence` | Same model, re-homed + TEXT-CHECK enums; FKs re-pointed at the reconciled tables. |
| `evidence_plan.*_t` private enums | **`TEXT + CHECK`** (closed vocab §14.5) | Mirrors as-built style; no new enum types except where `0004` already gives one. |
| paper `sensitivity_t` (routine/sensitive/high) | **`label_sensitivity` TEXT CHECK** | Renamed to *avoid collision* with the `0004` `sensitivity_tier` enum (public/restricted/sealed, the access-classification one). |
| paper `confidence_t` (high/med/low) | **`0004` `confidence` domain (numeric) + `confidence_tier` TEXT CHECK** | Reuse the as-built `confidence` domain for the score; keep a re-derivable HIGH/MED/LOW tier (A3 `vw_forensic_evidence_package`) for the export gate. |
| paper `evidence.object` (completion target) | **`evidence.source`** (D1) | D1 reconciled the raw registry to `evidence.source`; completion evidence is a *new* source object + custody hash. |
| paper court export (implicit) | **`analysis.vw_court_export`** + `export_package`/`export_item` | Explicit gate: confidence tier **AND** approved **AND** `safe_for_legal_use`. |

**As-built / D1 invariants preserved.** All cross-domain FKs land on stable anchors:
`evidence.evidence_hash(id)` (custody), `evidence.source(id)` / `evidence.file_node(id)` (D1),
`analysis.normalized_record(id)` (as-built bitemporal spine). Two FK targets are **not yet
frozen** and owned by other domains — `analysis.finding(id)` (analysis/behavioral, D4/E4) and
`analysis.person(id)` (entity, E5/D-entity); they are declared here but flagged in §4 for
ordered application.

**Custom-type discipline (`0004`).** Reuses `mcl_factor` (enum `a`–`l`, the custody-factor
key + `mcl_factor[]` arrays), `confidence` (numeric(4,3) domain, every score), `sensitivity_tier`
(the renamed `0004` enum, access classification), and `source_ref` (composite — preserved as a
cross-store-pointer note, not forced onto a column). New closed sets use `TEXT + CHECK`.

**Court-safe lanes (hard guardrail).** Every D7 row carries an explicit
`assertion_type` (`raw` / `extracted_fact` / `inferred_fact` / `analytical_finding` /
`legal_conclusion`) and an `is_hypothesis` flag. Behavior/abuse labels enter D7 **only by
reference** (a `factor_citation` or a task's `trigger_kind`/finding link) and stay
**hypotheses** until a human clears them — they never become a court-export row on their own.
Both parties and the full relational cycle are first-class: a task may be generated from the
*user's own* conduct (`risk_kind` includes `self_incrimination`; `trigger_kind` includes
`selective_framing`), and a finding may be **rebutted** by what is gathered
(`completion_evidence.outcome = 'overcome'`, task status `closed_overcome`). Nothing reaches
`vw_court_export` without `review_status='approved'` **and** `safe_for_legal_use=true`.

---

## 2. Reconciled DDL

```sql
-- =====================================================================
-- D7 — Legal/Custody Relevance, Evidence-Gathering Tasks & Court Export
-- Target: unified PG18 resource (agno-postgres:18-duckdb), schema `analysis`
-- Boundary: `analysis` = DERIVED artifacts; writes only after a recorded HITL
--   approval (agents connect read-only; the ingestion/analysis service role +
--   review-gatekeeper write here). Reference seeds are applied by migration.
-- Reuses 0004 types: mcl_factor (enum a-l), confidence (numeric domain),
--   sensitivity_tier (renamed 0004 enum), source_ref (composite, by note).
-- Cross-domain FK anchors: evidence.source/file_node/evidence_hash (D1),
--   analysis.normalized_record (as-built); deferred: analysis.finding (D4),
--   analysis.person (E5) -- see §4.
-- =====================================================================

-- ── 0. Bug-fix dependency (idempotent; primary owner = D1).
--      Reuse the renamed 0004 enum for access classification. No-op if D1 ran.
DO $$ BEGIN
    ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;   -- public|restricted|sealed
EXCEPTION
    WHEN undefined_object THEN NULL;   -- already renamed, or 0004 never hand-applied
    WHEN duplicate_object THEN NULL;   -- sensitivity_tier already exists
END $$;
-- If 0004 was never applied on the live volume, create the type fresh:
DO $$ BEGIN
    CREATE TYPE sensitivity_tier AS ENUM ('public','restricted','sealed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── shared append-only guard for analysis history/audit tables ─────────
CREATE OR REPLACE FUNCTION analysis.forbid_mutation() RETURNS trigger
  LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'analysis.% is append-only: % blocked (never-delete -> _stale)',
        TG_TABLE_NAME, TG_OP;
END $$;

-- =====================================================================
-- 1. LEGAL / CUSTODY MAP  (sub-domain prefix `legal_*`, schema analysis)
-- =====================================================================

-- ── 1.1 MCL 722.23 (a)-(l) custody-factor reference (seeded once) ──────
--      Adopt E2 `mcl_factors` (A-L statutory) keyed on the 0004 `mcl_factor` enum.
CREATE TABLE IF NOT EXISTS analysis.custody_factor (
    factor          mcl_factor PRIMARY KEY,              -- 0004 enum: 'a'..'l'
    code_display    text NOT NULL,                       -- 'A'..'L' for court output
    name            text NOT NULL,
    statutory_text  text NOT NULL,                       -- verbatim MCL 722.23(x)
    is_key_factor   boolean NOT NULL DEFAULT false,      -- E2: J & K flagged KEY
    notes           text
);
-- Seed (E2 §D; statutory_text abbreviated here, full text supplied at migration):
INSERT INTO analysis.custody_factor (factor, code_display, name, is_key_factor) VALUES
  ('a','A','Love, affection & emotional ties',                false),
  ('b','B','Capacity & disposition to give love/guidance',    false),
  ('c','C','Capacity to provide food, clothing, medical care', false),
  ('d','D','Length of time in a stable environment',          false),
  ('e','E','Permanence as a family unit',                     false),
  ('f','F','Moral fitness',                                   false),
  ('g','G','Mental & physical health',                        false),
  ('h','H','Home, school & community record',                 false),
  ('i','I','Reasonable preference of the child',              false),
  ('j','J','Willingness to facilitate the other relationship', true),
  ('k','K','Domestic violence',                               true),
  ('l','L','Any other relevant factor',                       false)
ON CONFLICT (factor) DO NOTHING;

-- ── 1.2 Per-case legal issues (custody, parenting time, relocation, ...) ─
CREATE TABLE IF NOT EXISTS analysis.legal_issue (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    case_id         uuid NOT NULL,
    issue_key       text NOT NULL,                       -- short slug, UNIQUE per case
    title           text NOT NULL,
    description     text,
    issue_type      text NOT NULL DEFAULT 'custody'
                    CHECK (issue_type IN ('custody','parenting_time','support',
                      'relocation','protective_order','property','contempt','other')),
    statutory_basis text,                                -- e.g. 'MCL 722.23'
    weight          confidence,                          -- 0004 domain; materiality (HITL-set, nullable)
    weight_basis    text,                                -- why this weight (policy, never hard-coded)
    -- provenance
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (case_id, issue_key)
);
CREATE INDEX IF NOT EXISTS idx_legal_issue_case ON analysis.legal_issue (case_id, issue_type);

-- ── 1.3 Issue -> MCL factor mapping (n:m) ─────────────────────────────
CREATE TABLE IF NOT EXISTS analysis.legal_issue_factor (
    legal_issue_id  uuid NOT NULL REFERENCES analysis.legal_issue(id),
    factor          mcl_factor NOT NULL REFERENCES analysis.custody_factor(factor),
    element_note    text,
    PRIMARY KEY (legal_issue_id, factor)
);

-- =====================================================================
-- 2. COURT-EVIDENCE SPINE  (adopt E2 court tables)
-- =====================================================================

-- ── 2.1 evidence_item / exhibit (merge E2 S1 court-prep + B custody) ───
CREATE TABLE IF NOT EXISTS analysis.evidence_item (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    case_id         uuid NOT NULL,
    -- provenance anchors (raw stays in evidence.*; this is the curated pointer)
    source_id            uuid REFERENCES evidence.source(id),
    file_node_id         uuid REFERENCES evidence.file_node(id),
    normalized_record_id uuid REFERENCES analysis.normalized_record(id),
    evidence_hash_id     uuid REFERENCES evidence.evidence_hash(id),   -- custody anchor
    -- exhibit identity
    exhibit_number  text,                                -- assigned only when exhibited
    title           text NOT NULL,
    description     text,
    quote           text,                                -- the exact passage relied on
    context         text,                                -- surrounding context (anti-cherry-pick)
    evidence_type   text NOT NULL DEFAULT 'communication'
                    CHECK (evidence_type IN ('communication','document','photo','record',
                      'media','screenshot','transcript','metadata','other')),
    evidence_date       timestamptz,
    evidence_date_end   timestamptz,
    date_precision  text NOT NULL DEFAULT 'exact'
                    CHECK (date_precision IN ('exact','approximate','inferred','uncertain')),
    -- court-safe lane discipline
    assertion_type  text NOT NULL DEFAULT 'extracted_fact'
                    CHECK (assertion_type IN ('raw','extracted_fact','inferred_fact',
                      'analytical_finding','legal_conclusion')),
    confidence      confidence,                          -- 0004 domain (numeric score)
    confidence_tier text NOT NULL DEFAULT 'low'
                    CHECK (confidence_tier IN ('high','medium','low')),  -- A3 HIGH/MED/LOW gate
    relevance_score confidence,
    is_hypothesis   boolean NOT NULL DEFAULT false,
    -- authentication (MRE 901)
    is_exhibit          boolean NOT NULL DEFAULT false,
    is_authenticated    boolean NOT NULL DEFAULT false,
    authentication_method text
                    CHECK (authentication_method IS NULL OR authentication_method IN
                      ('witness_with_knowledge','distinctive_characteristics','process_or_system',
                       'public_record','hash_chain_of_custody','self_authenticating','stipulation')),
    chain_of_custody    text,                            -- narrative; authoritative chain = evidence.custody_event (D1)
    -- classification / redaction (reuse renamed 0004 enum for access tier)
    sensitivity_tier    sensitivity_tier NOT NULL DEFAULT 'restricted',   -- public|restricted|sealed
    privacy_sensitivity text NOT NULL DEFAULT 'none'
                    CHECK (privacy_sensitivity IN ('none','pii','minor','sensitive_pii')),
    redaction_status text NOT NULL DEFAULT 'none'
                    CHECK (redaction_status IN ('none','required','applied')),
    -- HITL review gate
    review_status   text NOT NULL DEFAULT 'unreviewed'
                    CHECK (review_status IN ('unreviewed','in_review','approved','rejected')),
    reviewed_by     text,
    reviewed_at     timestamptz,
    hitl_required   boolean NOT NULL DEFAULT true,
    -- THE court-export trip-wire: only a human-approved, authenticated, non-hypothesis
    -- item may ever be marked safe for legal use (enforced by table CHECK below).
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    -- append-only correction (never overwrite a prior interpretation)
    supersedes_item_id uuid REFERENCES analysis.evidence_item(id),
    -- provenance quintuple (Context Pack §2)
    source_run_id    uuid,
    prompt_version   text,
    ontology_version text,
    schema_version   text,
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    metadata        jsonb NOT NULL DEFAULT '{}',
    UNIQUE (case_id, exhibit_number),
    CONSTRAINT evidence_item_safe_ck CHECK (
        safe_for_legal_use = false
        OR (review_status = 'approved' AND is_authenticated = true
            AND is_hypothesis = false AND redaction_status <> 'required')
    )
);
CREATE INDEX IF NOT EXISTS idx_evitem_case     ON analysis.evidence_item (case_id, review_status);
CREATE INDEX IF NOT EXISTS idx_evitem_source   ON analysis.evidence_item (source_id);
CREATE INDEX IF NOT EXISTS idx_evitem_export   ON analysis.evidence_item (case_id)
    WHERE safe_for_legal_use = true;
CREATE INDEX IF NOT EXISTS idx_evitem_title_trgm ON analysis.evidence_item USING gin (title gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_evitem_meta     ON analysis.evidence_item USING gin (metadata);

-- ── 2.2 factor_citation: evidence_item <-> MCL factor (supports/contradicts) ──
--      Keep S1's polarity + strength (the legally-critical bit B dropped).
CREATE TABLE IF NOT EXISTS analysis.factor_citation (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    evidence_item_id uuid NOT NULL REFERENCES analysis.evidence_item(id),
    factor          mcl_factor NOT NULL REFERENCES analysis.custody_factor(factor),
    legal_issue_id  uuid REFERENCES analysis.legal_issue(id),
    supports_factor boolean NOT NULL,                    -- S1: TRUE supports / FALSE contradicts
    strength        text NOT NULL DEFAULT 'moderate'
                    CHECK (strength IN ('weak','moderate','strong','decisive')),
    supporting_text text,
    relevance_explanation text,
    assertion_type  text NOT NULL DEFAULT 'analytical_finding'
                    CHECK (assertion_type IN ('raw','extracted_fact','inferred_fact',
                      'analytical_finding','legal_conclusion')),
    confidence      confidence,
    is_hypothesis   boolean NOT NULL DEFAULT false,
    review_status   text NOT NULL DEFAULT 'unreviewed'
                    CHECK (review_status IN ('unreviewed','in_review','approved','rejected')),
    supersedes_citation_id uuid REFERENCES analysis.factor_citation(id),
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (evidence_item_id, factor, supports_factor)   -- S1 UNIQUE(evidence,factor)+polarity
);
CREATE INDEX IF NOT EXISTS idx_factcite_factor ON analysis.factor_citation (factor, supports_factor);
CREATE INDEX IF NOT EXISTS idx_factcite_item   ON analysis.factor_citation (evidence_item_id);

-- ── 2.3 curated legal timeline (E2 S1 full; distinct from raw geo timeline) ──
CREATE TABLE IF NOT EXISTS analysis.legal_timeline_event (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    case_id         uuid NOT NULL,
    event_date      timestamptz NOT NULL,
    event_date_end  timestamptz,
    date_precision  text NOT NULL DEFAULT 'exact'
                    CHECK (date_precision IN ('exact','approximate','inferred','uncertain')),
    title           text NOT NULL,
    description     text,
    event_type      text NOT NULL DEFAULT 'communication'
                    CHECK (event_type IN ('communication','incident','filing','hearing',
                      'order','exchange','visit','other')),
    evidence_item_ids   uuid[] NOT NULL DEFAULT '{}',
    normalized_record_ids uuid[] NOT NULL DEFAULT '{}',
    mcl_factors     mcl_factor[] NOT NULL DEFAULT '{}',  -- reuse 0004 enum array
    participants    text[] NOT NULL DEFAULT '{}',
    assertion_type  text NOT NULL DEFAULT 'analytical_finding'
                    CHECK (assertion_type IN ('raw','extracted_fact','inferred_fact',
                      'analytical_finding','legal_conclusion')),
    confidence      confidence,
    is_verified     boolean NOT NULL DEFAULT false,
    is_disputed     boolean NOT NULL DEFAULT false,
    review_status   text NOT NULL DEFAULT 'unreviewed'
                    CHECK (review_status IN ('unreviewed','in_review','approved','rejected')),
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now(),
    metadata        jsonb NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_legaltl_case ON analysis.legal_timeline_event (case_id, event_date);
CREATE INDEX IF NOT EXISTS idx_legaltl_fact ON analysis.legal_timeline_event USING gin (mcl_factors);

-- =====================================================================
-- 3. EVIDENCE-GATHERING PLAN  (paper §12, re-homed analysis.evidence_*)
-- =====================================================================

-- ── 3.1 the task (finding -> trackable to-do) ─────────────────────────
CREATE TABLE IF NOT EXISTS analysis.evidence_task (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    task_key        text UNIQUE NOT NULL,                -- EGP-2026-0007 (filing/checklist handle)
    case_id         uuid NOT NULL,
    finding_id      uuid REFERENCES analysis.finding(id),   -- DEFERRED FK (D4) -- §4
    trigger_kind    text NOT NULL DEFAULT 'manual'
                    CHECK (trigger_kind IN ('contradiction','anomaly','gap','behavioral_pattern',
                      'custody_factor_concern','safety_concern','communication_barrier',
                      'established_custodial_environment','selective_framing','timeline_hole',
                      'attribution_uncertainty','manual')),
    evidence_needed text NOT NULL,
    evidence_need_kind text NOT NULL DEFAULT 'corroboration'
                    CHECK (evidence_need_kind IN ('corroboration','original_source','authentication',
                      'metadata','completeness','chain_of_custody','rebuttal','foundation','impeachment')),
    likely_source_id   uuid REFERENCES evidence.source(id),
    likely_source_note text,
    -- priority (computed + stored with inputs; human-overridable)
    priority        text NOT NULL DEFAULT 'P3_low'
                    CHECK (priority IN ('P0_critical','P1_high','P2_medium','P3_low','P4_backlog')),
    priority_score  numeric,
    priority_inputs jsonb,
    priority_override text
                    CHECK (priority_override IS NULL OR priority_override IN
                      ('P0_critical','P1_high','P2_medium','P3_low','P4_backlog')),
    priority_override_reason text,
    -- risk (overall + typed facets; value and risk kept separate, MP 2467)
    risk            text NOT NULL DEFAULT 'none'
                    CHECK (risk IN ('none','low','medium','high')),
    risk_kind       text[] NOT NULL DEFAULT '{}',        -- litigation|prejudice|privacy_redaction|safety|self_incrimination|cost|chain_of_custody
    risk_note       text,
    due_date        date,
    due_basis       text,
    status          text NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','proposed','needs_human_review','approved',
                      'in_progress','awaiting_response','blocked','obtained','verified',
                      'closed_satisfied','closed_unmet','closed_overcome','superseded','archived')),
    human_action    text,
    human_action_kind text NOT NULL DEFAULT 'none_yet'
                    CHECK (human_action_kind IN ('review_label','approve_instrument','serve_subpoena',
                      'collect_self','request_from_counsel','interview_witness','authenticate',
                      'redact','decide_relevance','file_motion','none_yet')),
    -- court-safe lane discipline
    assertion_type  text NOT NULL DEFAULT 'analytical_finding'
                    CHECK (assertion_type IN ('raw','extracted_fact','inferred_fact',
                      'analytical_finding','legal_conclusion')),
    confidence      confidence,
    confidence_tier text NOT NULL DEFAULT 'low'
                    CHECK (confidence_tier IN ('high','medium','low')),
    confidence_note text,
    is_hypothesis   boolean NOT NULL DEFAULT false,
    -- sensitivity / HITL  (label-sensitivity renamed to avoid 0004 sensitivity_tier collision)
    label_sensitivity text NOT NULL DEFAULT 'routine'
                    CHECK (label_sensitivity IN ('routine','sensitive','high')),
    hitl_required   boolean NOT NULL DEFAULT false,
    hitl_status     text NOT NULL DEFAULT 'pending'
                    CHECK (hitl_status IN ('pending','approved','declined')),
    -- provenance quintuple
    source_run_id    uuid,
    prompt_version   text,
    ontology_version text,
    schema_version   text,
    review_status    text NOT NULL DEFAULT 'unreviewed',
    created_by       text NOT NULL,
    created_at       timestamptz NOT NULL DEFAULT now(),
    archive_reason   text
);
CREATE INDEX IF NOT EXISTS idx_task_case_status ON analysis.evidence_task (case_id, status);
CREATE INDEX IF NOT EXISTS idx_task_finding     ON analysis.evidence_task (finding_id);
CREATE INDEX IF NOT EXISTS idx_task_priority    ON analysis.evidence_task (priority, due_date);
CREATE INDEX IF NOT EXISTS idx_task_riskkind    ON analysis.evidence_task USING gin (risk_kind);

-- ── 3.2 append-only status / audit log ────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis.task_event (
    event_id    uuid PRIMARY KEY DEFAULT uuidv7(),
    task_id     uuid NOT NULL REFERENCES analysis.evidence_task(id),
    from_status text,
    to_status   text NOT NULL,
    actor       text NOT NULL,
    actor_kind  text NOT NULL CHECK (actor_kind IN ('system','agent','human')),
    reason      text,
    ts          timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_taskevent_task ON analysis.task_event (task_id, ts DESC);

-- ── 3.3 versioned edits (never overwrite) ─────────────────────────────
CREATE TABLE IF NOT EXISTS analysis.task_revision (
    revision_id uuid PRIMARY KEY DEFAULT uuidv7(),
    task_id     uuid NOT NULL REFERENCES analysis.evidence_task(id),
    snapshot    jsonb NOT NULL,
    changed_by  text NOT NULL,
    change_note text,
    ts          timestamptz NOT NULL DEFAULT now()
);

-- ── 3.4 people involved (role-typed) ; person owned by entity domain (E5) ─
CREATE TABLE IF NOT EXISTS analysis.task_person (
    task_id   uuid NOT NULL REFERENCES analysis.evidence_task(id),
    person_id uuid NOT NULL REFERENCES analysis.person(id),   -- DEFERRED FK (E5) -- §4
    role      text NOT NULL
              CHECK (role IN ('subject','custodian','witness','child','third_party','self')),
    PRIMARY KEY (task_id, person_id, role)
);

-- ── 3.5 legal links (task -> issue + MCL factor + element) ────────────
CREATE TABLE IF NOT EXISTS analysis.task_legal_link (
    task_id        uuid NOT NULL REFERENCES analysis.evidence_task(id),
    legal_issue_id uuid NOT NULL REFERENCES analysis.legal_issue(id),
    factor         mcl_factor REFERENCES analysis.custody_factor(factor),  -- MCL 722.23, nullable
    element_note   text,
    PRIMARY KEY (task_id, legal_issue_id, factor)
);

-- ── 3.6 dependency DAG ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis.task_dependency (
    task_id    uuid NOT NULL REFERENCES analysis.evidence_task(id),
    depends_on uuid NOT NULL REFERENCES analysis.evidence_task(id),
    dep_kind   text NOT NULL CHECK (dep_kind IN ('blocks','prereq_of','corroborates','duplicate_of')),
    PRIMARY KEY (task_id, depends_on, dep_kind),
    CHECK (task_id <> depends_on)
);

-- ── 3.7 proposed discovery instruments (DRAFT ONLY; system never serves) ──
CREATE TABLE IF NOT EXISTS analysis.discovery_request (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    task_id         uuid NOT NULL REFERENCES analysis.evidence_task(id),
    instrument_type text NOT NULL
                    CHECK (instrument_type IN ('subpoena','subpoena_duces_tecum','rfa','rfp','rog',
                      'witness_question','deposition_topic','self_collection','records_request',
                      'preservation_letter')),
    target_person_id uuid REFERENCES analysis.person(id),     -- DEFERRED FK (E5) -- §4
    target_custodian text,
    draft_text      text NOT NULL,                       -- review-ready draft; NOT legal advice
    scope_note      text,
    status          text NOT NULL DEFAULT 'draft'
                    CHECK (status IN ('draft','approved','served','responded','withdrawn')),
    hitl_status     text NOT NULL DEFAULT 'pending'
                    CHECK (hitl_status IN ('pending','approved','declined')),
    prompt_version  text,
    created_by      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_discreq_task ON analysis.discovery_request (task_id, status);

CREATE TABLE IF NOT EXISTS analysis.discovery_request_revision (
    revision_id uuid PRIMARY KEY DEFAULT uuidv7(),
    request_id  uuid NOT NULL REFERENCES analysis.discovery_request(id),
    snapshot    jsonb NOT NULL,
    changed_by  text NOT NULL,
    ts          timestamptz NOT NULL DEFAULT now()
);

-- ── 3.8 completion evidence (closes the loop back to evidence + custody) ──
CREATE TABLE IF NOT EXISTS analysis.completion_evidence (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    task_id         uuid NOT NULL REFERENCES analysis.evidence_task(id),
    source_id       uuid REFERENCES evidence.source(id),         -- the new evidence object (D1)
    evidence_item_id uuid REFERENCES analysis.evidence_item(id),
    evidence_hash_id uuid REFERENCES evidence.evidence_hash(id), -- chain-of-custody anchor
    sha256          bytea,                               -- convenience copy of the custody hash
    outcome         text NOT NULL
                    CHECK (outcome IN ('satisfied','unmet','overcome','partial')),
    outcome_note    text,
    recorded_by     text NOT NULL,
    recorded_at     timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT completion_sha_len CHECK (sha256 IS NULL OR octet_length(sha256) = 32)
);
CREATE INDEX IF NOT EXISTS idx_completion_task ON analysis.completion_evidence (task_id);

-- ── 3.9 append-only enforcement (mirrors paper §14.8) ─────────────────
CREATE OR REPLACE FUNCTION analysis.snapshot_task() RETURNS trigger
  LANGUAGE plpgsql AS $$ BEGIN
    INSERT INTO analysis.task_revision(task_id, snapshot, changed_by, change_note, ts)
    VALUES (OLD.id, to_jsonb(OLD),
            COALESCE(current_setting('app.actor', true), 'unknown'),
            'auto-snapshot before UPDATE', now());
    RETURN NEW;
  END $$;
CREATE TRIGGER task_snapshot BEFORE UPDATE ON analysis.evidence_task
  FOR EACH ROW EXECUTE FUNCTION analysis.snapshot_task();

CREATE OR REPLACE FUNCTION analysis.log_task_status() RETURNS trigger
  LANGUAGE plpgsql AS $$ BEGIN
    IF NEW.status IS DISTINCT FROM OLD.status THEN
      IF NEW.status = 'archived' AND COALESCE(NEW.archive_reason,'') = '' THEN
        RAISE EXCEPTION 'archived status requires archive_reason (no silent discard)';
      END IF;
      INSERT INTO analysis.task_event(task_id, from_status, to_status, actor, actor_kind, reason, ts)
      VALUES (NEW.id, OLD.status, NEW.status,
              COALESCE(current_setting('app.actor', true), 'system'),
              COALESCE(current_setting('app.actor_kind', true), 'system'),
              NEW.archive_reason, now());
    END IF;
    RETURN NEW;
  END $$;
CREATE TRIGGER task_status_log BEFORE UPDATE OF status ON analysis.evidence_task
  FOR EACH ROW EXECUTE FUNCTION analysis.log_task_status();

-- history tables are insert-only (REVOKE in deployment + trigger belt-and-braces)
CREATE TRIGGER taskevent_immutable BEFORE UPDATE OR DELETE ON analysis.task_event
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();
CREATE TRIGGER taskrev_immutable BEFORE UPDATE OR DELETE ON analysis.task_revision
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();
CREATE TRIGGER discrev_immutable BEFORE UPDATE OR DELETE ON analysis.discovery_request_revision
  FOR EACH ROW EXECUTE FUNCTION analysis.forbid_mutation();

-- =====================================================================
-- 4. COURT EXPORT  (gate: confidence tier AND approved AND safe_for_legal_use)
-- =====================================================================

CREATE TABLE IF NOT EXISTS analysis.export_package (
    id            uuid PRIMARY KEY DEFAULT uuidv7(),
    case_id       uuid NOT NULL,
    package_name  text NOT NULL,
    purpose       text,                                  -- 'motion for temporary relief', 'GAL packet'
    status        text NOT NULL DEFAULT 'draft'
                  CHECK (status IN ('draft','approved','exported','withdrawn')),
    approved_by   text,
    approved_at   timestamptz,
    exported_at   timestamptz,
    manifest      jsonb NOT NULL DEFAULT '{}',           -- item ids + hashes captured at export
    signature     bytea,                                 -- detached signature over the manifest (HSM/pgcrypto)
    created_by    text NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS analysis.export_item (
    package_id      uuid NOT NULL REFERENCES analysis.export_package(id),
    evidence_item_id uuid NOT NULL REFERENCES analysis.evidence_item(id),
    ordinal         int,
    included_at     timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (package_id, evidence_item_id)
);

-- ── 4.1 THE court-export view: nothing leaves without all three gates ──
CREATE OR REPLACE VIEW analysis.vw_court_export AS
SELECT ei.id, ei.case_id, ei.exhibit_number, ei.title, ei.description, ei.quote,
       ei.context, ei.evidence_type, ei.evidence_date, ei.date_precision,
       ei.assertion_type, ei.confidence, ei.confidence_tier,
       ei.is_authenticated, ei.authentication_method, ei.chain_of_custody,
       ei.sensitivity_tier, ei.redaction_status,
       ei.source_id, ei.file_node_id, ei.evidence_hash_id, ei.reviewed_by, ei.reviewed_at
FROM analysis.evidence_item ei
WHERE ei.safe_for_legal_use = true                       -- gate 1: human-set HITL trip-wire
  AND ei.review_status      = 'approved'                 -- gate 2: HITL approved
  AND ei.confidence_tier IN ('high','medium')            -- gate 3: confidence tier
  AND ei.is_hypothesis      = false                      -- never export a hypothesis
  AND ei.is_authenticated   = true                       -- MRE 901
  AND ei.redaction_status  <> 'required'                 -- redaction satisfied
  AND ei.sensitivity_tier  <> 'sealed';                  -- sealed needs separate in-camera clearance

-- ── 4.2 cross-session "where was I" board (paper §14.12) ──────────────
CREATE OR REPLACE VIEW analysis.vw_open_tasks AS
SELECT t.id, t.task_key, t.case_id, t.status, t.priority, t.priority_score,
       t.due_date, t.due_basis, t.human_action, t.human_action_kind,
       t.label_sensitivity, t.hitl_required, t.hitl_status, t.confidence_tier,
       t.is_hypothesis,
       (SELECT count(*) FROM analysis.task_dependency d
         WHERE d.depends_on = t.id AND d.dep_kind IN ('blocks','prereq_of')) AS blocks_n,
       (SELECT e.to_status FROM analysis.task_event e
         WHERE e.task_id = t.id ORDER BY e.ts DESC LIMIT 1)                  AS last_event
FROM analysis.evidence_task t
WHERE t.status NOT IN ('closed_satisfied','closed_unmet','closed_overcome','superseded','archived')
ORDER BY t.priority, t.priority_score DESC NULLS LAST, t.due_date NULLS LAST;
```

> **`safe_for_legal_use` is a human-only switch.** The `evidence_item_safe_ck` table CHECK makes
> it *impossible* to set true unless the row is approved, authenticated, non-hypothesis, and not
> pending redaction — and the column should be writable only by the `review-gatekeeper` role
> (connection-enforced, like the `evidence` RO boundary in E1 §6), never by an extraction agent.
> The `vw_court_export` view is the single court-facing surface; `export_package.manifest` +
> `signature` capture the exact item ids and custody hashes at export time so a produced packet
> is reproducible and tamper-evident.

---

## 3. Decision table

| Table / field | Decision | Source (as-built / paper / prior) | Note |
|---|---|---|---|
| **`analysis` schema** as home for all of D7 | **adopt** | as-built E1 §0 | Re-home; paper's `evidence_plan` + `legal` top-level schemas rejected (boundary). All D7 rows are derived/curated ⇒ write-after-approval lane. |
| `analysis.custody_factor` (MCL 722.23 a–l ref) | **adopt** | E2 §D `mcl_factors`; `0004` `mcl_factor` enum | PK = `mcl_factor` enum (reuse `0004`); J & K flagged `is_key_factor`; seeded by migration. |
| `analysis.legal_issue` + `legal_issue_factor` | **adapt** | paper §12 `legal.legal_issue` | Per-case issue map; `weight` uses `0004 confidence` domain, HITL-set (no hard-coded legal weighting). |
| `legal.*` as a **schema** | **deprecate** | paper §12 | Converted to a `legal_*`/`custody_*` table-name prefix inside `analysis`. |
| `analysis.evidence_item` | **merge** | E2 §E S1 `evidence_items` (court-prep) ⊕ B `messaging_evidence_items` (exhibit/custody) | S1 authentication/custody columns promoted onto B; FK to `evidence.source`/`file_node`/`evidence_hash`. |
| `evidence_item.is_authenticated / authentication_method / chain_of_custody` | **adopt** | E2 §E S1 (MRE 901) | Item-level authentication (E2 reconciliation flag #4 — promote from S1). |
| `evidence_item.safe_for_legal_use` + `evidence_item_safe_ck` | **adapt** (new gate) | paper §12 export intent; A3 `vw_forensic_evidence_package` | The court-export trip-wire; CHECK ties it to approved+authenticated+non-hypothesis. |
| `evidence_item.confidence_tier` (HIGH/MED/LOW) | **adopt** | A3 `vw_forensic_evidence_package` (prob>0.6 tiering) | Re-derivable tier for the export gate; numeric score in `0004 confidence`. |
| `evidence_item.sensitivity_tier` (enum) | **adapt** | `0004` `disclosure_tier` **renamed** (E1 §5.1 fix, D1) | Reuse renamed enum for access classification. |
| `evidence_item.assertion_type / is_hypothesis` | **adopt** | Context Pack §2; MP 2420 | Court-safe lane discipline on every row. |
| `analysis.factor_citation` (supports/contradicts + strength) | **adopt** | E2 §E S1 `factor_citations` (`supports_factor`, `strength`) | Keep S1 polarity + strength (B dropped them); append-only correction via `supersedes_citation_id`. |
| `analysis.legal_timeline_event` | **adopt** | E2 §E S1 `timeline_events` (full) | Curated legal chronology; `mcl_factors mcl_factor[]`; **distinct** from raw geo `timeline_event` (E3/D3). |
| `analysis.evidence_task` (+ 8 satellites) | **adapt** | paper §12 `evidence_plan.task` family | Re-homed; private `*_t` enums → `TEXT + CHECK`; all 14 MP fields preserved. |
| paper `evidence_plan.*_t` enums | **deprecate** | paper §12 | Replaced by `TEXT + CHECK` (D1 discipline; avoids enum sprawl). |
| paper `sensitivity_t` (routine/sensitive/high) | **adapt → `label_sensitivity`** | paper §14.5 | Renamed to avoid collision with the `0004` `sensitivity_tier` enum. |
| paper `confidence_t` (high/med/low) | **merge** | paper §14.5 + `0004 confidence` domain + A3 tiering | `confidence` (numeric domain) + `confidence_tier` (TEXT CHECK). |
| `task_event` / `task_revision` / `discovery_request_revision` | **adopt** | paper §12 | Append-only; snapshot + status-log triggers; `forbid_mutation` + REVOKE. |
| `task.finding_id → analysis.finding` | **adopt (deferred FK)** | paper §12; D4/E4 | Cross-domain; apply after the analysis/behavioral domain lands (§4). |
| `task_person.person_id` / `discovery_request.target_person_id → analysis.person` | **adopt (deferred FK)** | paper §12; E5 entity domain | Person registry owned by the entity domain; FK applied after it lands (§4). |
| `analysis.completion_evidence` (→ `evidence.source`) | **adapt** | paper §12 (`evidence.object`) | Re-pointed at D1's `evidence.source`; `sha256`/`evidence_hash_id` custody anchor. |
| `analysis.discovery_request` (subpoena/RFA/RFP/witness Q) | **adopt** | paper §12.11 | DRAFT only; `instrument_type` TEXT CHECK; HITL-gated; never auto-served. |
| `analysis.export_package` / `export_item` | **adapt** (new) | paper §12 export intent; D1 custody | Signed, reproducible court packet; manifest captures item ids + hashes. |
| `analysis.vw_court_export` (3-gate view) | **adopt** | task mandate; A3 court-export view | confidence tier **AND** approved **AND** `safe_for_legal_use` (+ authenticated/non-hypothesis/redaction/not-sealed). |
| `analysis.vw_open_tasks` | **adopt** | paper §14.8/§14.12 | Cross-session resumption board. |
| behavior categories → MCL-factor arrays (the 18) | **defer (out of D7)** | E2 §D; E4 behavioral ontology | Behavior taxonomy owned by the behavioral domain (E4/D4); D7 links to factors via `factor_citation`, not the taxonomy itself. |
| E2 `messaging_timeline_events` (S2 minimal) | **deprecate** | E2 §E | Superseded by S1-full `legal_timeline_event`. |
| `source_ref` composite (`0004`) | **preserve-as-note** | `0004`; E1 §5.2 | Available for cross-store instrument/source pointers; not forced onto a D7 column. |

---

## 4. Migration notes (ALTER/CREATE to reach this on the LIVE DB)

> **Verify-before-claim (addendum §D.9):** diff against the live `agno-postgres:18-duckdb`
> catalog **before** applying. Confirm (a) PG major = 18 (`uuidv7()` resolves, E1 §5.5);
> (b) `pg_trgm`, `pgcrypto`, `btree_gin` present (`0001`); (c) whether `0004` was hand-applied
> (so `mcl_factor`, `confidence`, and the renamed `sensitivity_tier` exist); (d) whether D1 has
> already run (it owns the `disclosure_tier → sensitivity_tier` rename and creates
> `evidence.source`/`file_node` that D7 FKs into); (e) that `analysis.normalized_record` exists.

1. **Apply order.** D7 depends on **D1** (`evidence.source`, `evidence.file_node`, the
   `sensitivity_tier` rename) and the as-built `analysis.normalized_record` /
   `evidence.evidence_hash`. Run D1 first. The §0 guarded `ALTER TYPE … RENAME` /
   `CREATE TYPE` block is idempotent — safe to re-run if D1 already did it.
2. **`0004` precondition.** If `0004` was never hand-applied on the live volume (E1 §5.4),
   `mcl_factor` and `confidence` will be missing and every `mcl_factor`/`confidence` reference
   fails. Apply `sql/0004_custom_types.sql` (or at minimum create `mcl_factor`, `confidence`,
   and `sensitivity_tier`) **before** the D7 block.
3. **Create reference + seed first.** `analysis.custody_factor` then its seed `INSERT … ON
   CONFLICT DO NOTHING` (supply full statutory text for `statutory_text` at apply time — left
   abbreviated in the DDL), then `analysis.legal_issue` / `legal_issue_factor`.
4. **Create the court spine + task model** (idempotent `IF NOT EXISTS`): `evidence_item`,
   `factor_citation`, `legal_timeline_event`, `evidence_task` + 8 satellites, the triggers/
   functions (§3.9), `export_package`/`export_item`, and the two views.
5. **Deferred cross-domain FKs.** `analysis.finding` (D4) and `analysis.person` (E5) may not
   exist yet. Either (a) apply D7 **after** those domains, or (b) create D7 now with those two
   FK clauses **omitted** and add them later as `ALTER TABLE … ADD CONSTRAINT … REFERENCES …
   NOT VALID; … VALIDATE CONSTRAINT;` once the targets land. The columns (`finding_id`,
   `person_id`, `target_person_id`) are present either way. `finding_id` is left **nullable**
   so `trigger_kind='manual'` tasks are legal without a finding (paper generation rule 1).
6. **Role grants (boundary enforcement, connection-level — not prompt):**
   - extraction/analysis service role: `INSERT, SELECT` on `analysis.*`; **no** `UPDATE` on
     `evidence_item.safe_for_legal_use`.
   - `review-gatekeeper` (HITL) role: the only role granted `UPDATE` on
     `evidence_item.review_status / safe_for_legal_use / reviewed_by`, `factor_citation.review_status`,
     `discovery_request.status / hitl_status`, and `export_package.status / approved_*`.
   - agent read-only role: `SELECT` only (`default_transaction_read_only`, E1 §6) — and for
     court-facing reads, **`SELECT` on `analysis.vw_court_export` only**, not the base
     `evidence_item` table.
   - history tables (`task_event`, `task_revision`, `discovery_request_revision`):
     `REVOKE UPDATE, DELETE … FROM PUBLIC;` grant `INSERT, SELECT` to the app role only.
7. **`current_setting('app.actor')` / `app.actor_kind`** must be set per connection by the
   app/agent so the audit trail names the real actor (service account / agno agent id / human),
   matching D1's custody-event actor discipline.
8. **Signing-key custody** for `export_package.signature` reuses the same unresolved
   signing-key ADR flagged in D1 (HSM vs pgcrypto key, rotation) — the export manifest is the
   anchor point.

### Needs-human-review
- **MCL factor materiality weights** (`legal_issue.weight`, used in `evidence_task` priority
  scoring) are **policy inputs** — a human or the legal map must set them; the system must never
  hard-code legal weightings (paper §14.15).
- **Instrument templates are jurisdiction-shaped** (`discovery_request.draft_text` assumes
  Michigan custody practice) and require **attorney/human review before any use** — the
  strongest HITL gate, intentionally not automatable.
- **Statutory text** for `custody_factor.statutory_text` must be pasted verbatim from MCL
  722.23 at migration time (abbreviated in the seed here).
- **Deferred FK contracts** (`analysis.finding` PK/cols from D4; `analysis.person` PK/cols from
  E5) must be frozen before step 5(a)/(b); confirm the referenced PK column names
  (`id` assumed) match those domains' final DDL.
- **Sealed-item export path.** `vw_court_export` excludes `sensitivity_tier='sealed'`; the
  in-camera/under-seal production path (who clears it, how it is logged) needs its own HITL
  procedure + ADR — not expressible in this view alone.
- **`safe_for_legal_use` writability** must be enforced by the `review-gatekeeper` role grant
  (step 6); the table CHECK only guarantees the *preconditions*, not *who* may flip it.
```
