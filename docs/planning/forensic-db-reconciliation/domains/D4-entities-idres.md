# D4 — Entities & Identity Resolution (PG domain reconciliation)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> **Scope.** The canonical entity registry (persons, organizations, and the communication/device
> identifiers that belong to them) plus the identity-resolution machinery that maps the messy,
> inconsistent surface references found in evidence (nicknames, misspellings, changed numbers,
> blocked accounts, metadata-less screenshots, AI-transcript references, partial/ambiguous names)
> onto those canonical entities — **with full alias/merge/split history, evidence for-and-against,
> and human approval**, and a cross-store crosswalk so the PG identity is the same identity in
> Neo4j, Milvus and SurrealDB.
>
> **Law of this pass** = `extracted/E1_asbuilt_inventory.md` (as-built `sql/0001–0004`). Everything
> below is re-homed under the as-built security boundary (`evidence` / `analysis` / `public`),
> reuses the `0004` custom types, and adopts/adapts the prior-iteration ontologies (salem_v3 / Zep
> ORM = `E5`; TraceIQ/supabase `entities`+`entity_mentions` = `E2 §147–148`; A3 crosswalk §A/§C).
> Paper source: `sections/03-canonical-data-model.md §3`.

---

## 1. Reconciliation reasoning (the load-bearing calls)

### 1.1 Schema homing — everything lands in `analysis`, mentions stay append-only-immutable
The as-built law is narrow and explicit: **`evidence` = raw/source + custody hashes ONLY** (agents
read-only, connection-enforced); **`analysis` = derived/normalized artifacts emitted by parsers,
write-after-recorded-approval**; **`public` = HITL audit + Agno-managed**. The paper's parallel
top-level `entity` schema (paper C1's ten schemas) is **WRONG under this boundary** and is collapsed:

- **Canonical entities, their identifiers, aliases, and all resolution/merge tables are *derived* →
  `analysis`.** A "person" is not raw source bytes; it is an inference *about* the evidence. This also
  keeps the dependency arrow correct (analysis depends on evidence, never the reverse).
- **`analysis.entity_mention` is the verbatim "what literally appeared" capture** (a substring of a
  source artifact, no interpretation). It is held **append-only + immutable** (trigger + role) so it
  carries evidence-grade fixity *without* violating "evidence = raw only." It is `data_tier='extracted'`.
  - *Considered alternative:* put `entity_mention` in `evidence`. Rejected — mentions are produced by
    parser/NER extraction (a derivation), and the as-built reserves `evidence` for raw + custody hashes.
    Immutability is achieved by trigger instead. (Owner may override to `evidence` if they want the
    extracted surface form to be physically inside the RO lane; flagged below.)

### 1.2 Provenance by `source_ref[]`, **not** hard FK into `evidence`
Every derived row carries provenance as a `source_ref[]` array (the `0004` composite
`(system source_system, native_id text, locator text)`) rather than a hard FK to
`evidence.evidence_hash`. This (a) reuses the as-built type verbatim, (b) avoids an `evidence→analysis`
or `analysis→evidence` FK that would couple the read-only lane to the writable one, and (c) lets one
entity cite many heterogeneous sources. **Cross-domain seam (D1 custody):** `custody.source`'s
`device_origin_id`/`account_origin_id`/`custodian_id` must be **soft references** (uuid, no FK) resolved
*through* this registry — otherwise the RO `evidence` lane would FK into writable `analysis`. Flagged
for the D1 doc.

### 1.3 Reuse `0004` types; **extend, never redefine**, `entity_type`
`0004.entity_type` (`person,org,project,tech,location,concept`) is **too generic for the forensic lane**
(E5 gap #1 — it omits the device/account/comms-identifier kinds the registry needs). Guardrail forbids
redefining it, so it is **ADAPTED by `ALTER TYPE … ADD VALUE`** (extension, fully reversible-in-intent)
to add the genuinely-*entity* kinds (`phone,email,handle,device,account,vehicle,court,attorney,school,
doctor,institution,platform,ai_system,address`). The salem/Zep structural concepts that are **not
entities** — `Incident` (→ `timeline.event`, D5/D6), `Statement` (→ its own evidence/statement lane),
`Evidence` (→ custody/D1), `Vulnerability`/`Tactic` (→ `analysis.finding` behavioral lane) — are
**NOT** crammed into the enum (adopts E5's "make them first-class tables, not enum members"). Fine-grained
org kinds (court vs school vs doctor) ride a `org_type` text column, not enum explosion.

### 1.4 disclosure_tier double-definition fix (consumed here)
Per E1 §5.1 / addendum §B: the substantive bitemporal column is `0003`'s text
`contemporaneous|hindsight|discovered`; the mis-scoped `0004` enum `public|restricted|sealed` is an
**access-classification** type and is **renamed `sensitivity_tier`** (global one-time migration, §4).
Sensitive entities (minors, intimate-party attributions, privileged third parties) carry
`sensitivity_tier` here.

### 1.5 Identity-resolution engine = `fuzzystrmatch` + `pg_trgm` + `citext`
- **`citext`** on every name/email/handle/identifier so `Matt`/`matt`/`MATT` collapse without `lower()`.
- **`pg_trgm`** GIN (`gin_trgm_ops`) for nickname/misspelling candidate generation (`name % $1`).
- **`fuzzystrmatch`** `dmetaphone()` materialized as a generated column (phonetic blocking key) +
  `levenshtein()` at scoring time. Stored similarity metrics live in `entity_resolution.similarity_metrics`.
- **`btree_gist` EXCLUDE on `tstzrange`** so a reassigned/blocked phone number or handle cannot have two
  simultaneous owners (changed-number / blocked-account requirements, E1/paper §3.1; A3 §C).

### 1.6 Append-only history + HITL, everywhere identity can change meaning
`entity_mention`, `entity_merge_event`, `resolution_evidence` are **append-only**. `entity_resolution`
is **supersedable** via `sys_period` (close the old, insert the new) — a resolution is never overwritten,
so any past attribution can be replayed. Sensitive merges (e.g. attributing an anonymous account to a
party, flagging a minor) gate on `requires_human_review` + `review_state` + `safe_for_legal_use` (C8).
Only `review_status='approved' AND safe_for_legal_use` rows are court-exportable, and only **approved**
resolutions/merges project to Neo4j (§1.7).

### 1.7 Cross-store identity = `analysis.id_xref` (built from the as-built forward-declares)
`0004` forward-declared `source_system`, `match_method`, `canonical_id` and the `id_xref` *intent* but
no table exists (E1 §4). It is **built here**: one canonical PG entity ↔ its Neo4j node ↔ its Milvus PK ↔
its SurrealDB record. Adopts the Zep ORM precursor (`zep_node_id`/`zep_user_id`/`ZepEdge.source_table`,
E5 §3) as a typed, FK-anchored crosswalk.

### 1.8 Court-safety: the registry holds *identity*, not clinical judgments
Zep `Person.risk_level (safe/high_risk/transient)` (E5 §1 S2) is **DEPRECATED off the entity** and
re-homed to the behavioral `analysis.finding` lane — baking a risk label into the identity registry would
present a HYPOTHESIS as an identity fact. Structural role fields that are *not* judgments
(`role_in_case`, `connection_to`, `is_minor`, `is_party`) stay, because they describe who the person is
in the matter, not an abuse conclusion.

---

## 2. Reconciled DDL

```sql
-- ============================================================================
-- D4 — Entities & Identity Resolution
-- Target: unified PG resource (agno-postgres:18-duckdb) — PostgreSQL 18 + PostGIS
--         + embedded DuckDB(pg_duckdb), ONE resource. Schema: analysis.
-- Reuses 0004 types (entity_type, confidence, canonical_id, source_system,
--   match_method, source_ref) and the paper shared enums (evidence_tier,
--   review_state) created once in the D0/shared-types migration (see §4).
-- Extensions assumed live (0001): citext, pg_trgm, fuzzystrmatch, btree_gist,
--   btree_gin, unaccent, pgcrypto; native uuidv7().
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 2.0  Type adaptations (migration-time; see §4 for ordering/caveats)
-- ---------------------------------------------------------------------------
-- ADAPT (not redefine) the as-built entity_type with forensic entity kinds.
-- ALTER TYPE ... ADD VALUE cannot run inside a txn block and the new value is
-- not usable in the same txn — run each on its own, before the DDL below.
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'phone';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'email';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'handle';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'device';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'account';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'vehicle';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'address';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'court';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'attorney';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'school';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'doctor';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'institution';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'platform';
ALTER TYPE entity_type ADD VALUE IF NOT EXISTS 'ai_system';

-- Global one-time fix consumed by this domain (E1 §5.1): the 0004 enum
-- public/restricted/sealed is access-classification, not the bitemporal tier.
-- ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;   -- (run once, §4)

-- ===========================================================================
-- 2.1  CANONICAL ENTITY SUPERTYPE  (analysis; derived → 'inferred' tier)
--      Merges TraceIQ/supabase `entities` (E2 §147) + salem/Zep Person/Org
--      core (E5) into one addressable supertype with shared-PK satellites.
-- ===========================================================================
CREATE TABLE analysis.entity (
    id                  uuid PRIMARY KEY DEFAULT uuidv7(),
    entity_type         entity_type   NOT NULL,                 -- reuse+extend 0004
    display_name        citext,                                 -- human label
    canonical_name      citext,                                 -- resolved canonical form
    normalized_name     citext,                                 -- dedup key (E2 entities.normalized_name)
    sensitivity_tier    sensitivity_tier,                       -- renamed 0004 enum (access class)
    is_party            boolean       NOT NULL DEFAULT false,    -- E2 entities.is_party
    -- lane + provenance + confidence (design contract C3/C6/C7)
    data_tier           evidence_tier NOT NULL DEFAULT 'inferred',
    evidence_confidence confidence,
    provenance          source_ref[]  NOT NULL DEFAULT '{}',    -- reuse 0004 composite (no FK into evidence)
    -- HITL gates (C8)
    requires_human_review boolean     NOT NULL DEFAULT false,
    review_status       review_state  NOT NULL DEFAULT 'unreviewed',
    safe_for_legal_use  boolean       NOT NULL DEFAULT false,
    -- merge tombstone: non-null => this entity was merged away into survivor
    merged_into_id      uuid REFERENCES analysis.entity(id),
    -- observation window + transaction time (bitemporal, C5)
    first_seen_at       timestamptz,
    last_seen_at        timestamptz,
    sys_period          tstzrange     NOT NULL DEFAULT tstzrange(now(), NULL),
    created_at          timestamptz   NOT NULL DEFAULT now(),
    CONSTRAINT entity_not_self_merge CHECK (merged_into_id IS DISTINCT FROM id)
);
CREATE INDEX idx_entity_type            ON analysis.entity (entity_type);
CREATE INDEX idx_entity_live            ON analysis.entity (id) WHERE merged_into_id IS NULL;
CREATE INDEX idx_entity_review          ON analysis.entity (review_status);
CREATE INDEX idx_entity_dispname_trgm   ON analysis.entity USING gin ((display_name::text)   gin_trgm_ops);
CREATE INDEX idx_entity_normname_trgm   ON analysis.entity USING gin ((normalized_name::text) gin_trgm_ops);
CREATE UNIQUE INDEX uq_entity_norm      ON analysis.entity (entity_type, normalized_name)
    WHERE normalized_name IS NOT NULL AND merged_into_id IS NULL;  -- adopts E2 UNIQUE(type,normalized_name)

-- ---------------------------------------------------------------------------
-- 2.2  Typed satellites (shared PK = entity.id) — lean, key fields only
-- ---------------------------------------------------------------------------
CREATE TABLE analysis.person (
    id               uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    relationship_type text,                                     -- TraceIQ people.relationship_type
    connection_to    text CHECK (connection_to IN
                       ('petitioner','respondent','child','mutual','third_party','unknown')), -- Zep S2
    role_in_case     text CHECK (role_in_case IN
                       ('user','partner','child','witness','evaluator','attorney',
                        'third_party','neutral','unknown')),     -- E2 entities.role + Zep (clinical labels dropped)
    gender           text,
    is_minor         boolean NOT NULL DEFAULT false,
    is_flagged       boolean NOT NULL DEFAULT false,            -- TraceIQ people.is_flagged
    notes            text                                       -- Zep ORM S3 Person.notes
    -- DEPRECATED off-entity: Zep Person.risk_level → analysis.finding (behavioral lane), HITL
);

CREATE TABLE analysis.organization (
    id            uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    org_type      text,                                         -- court/school/doctor/child_institution/platform/ai_system/employer/agency
    legal_name    citext,
    jurisdiction  text
);

-- Communication / device identifiers are themselves entities (addressable),
-- but also OWNED by a person/org, with bitemporal validity for change/block.
CREATE TABLE analysis.phone (
    id              uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    e164            citext,                                      -- normalized (E2 primary_participant_normalized)
    raw_number      text,
    owner_entity_id uuid REFERENCES analysis.entity(id),
    is_blocked      boolean NOT NULL DEFAULT false,             -- SMS status=64 / call type 6 (E2 §165)
    validity        tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),  -- active_from/active_to
    -- no two simultaneous owners of the same number (changed-number requirement)
    EXCLUDE USING gist (e164 WITH =, validity WITH &&) WHERE (e164 IS NOT NULL)
);
CREATE INDEX idx_phone_owner ON analysis.phone (owner_entity_id);
CREATE INDEX idx_phone_e164  ON analysis.phone ((e164::text));

CREATE TABLE analysis.email (
    id              uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    address         citext,
    owner_entity_id uuid REFERENCES analysis.entity(id),
    validity        tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
    EXCLUDE USING gist (address WITH =, validity WITH &&) WHERE (address IS NOT NULL)
);
CREATE INDEX idx_email_owner ON analysis.email (owner_entity_id);

CREATE TABLE analysis.handle (
    id              uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    platform        text NOT NULL,                              -- fb/snapchat/imessage/gchat/...
    handle          citext NOT NULL,
    owner_entity_id uuid REFERENCES analysis.entity(id),
    is_blocked      boolean NOT NULL DEFAULT false,             -- blocked account (E5 Person/handle)
    validity        tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
    EXCLUDE USING gist (platform WITH =, handle WITH =, validity WITH &&)
);
CREATE INDEX idx_handle_owner ON analysis.handle (owner_entity_id);
CREATE INDEX idx_handle_trgm  ON analysis.handle USING gin ((handle::text) gin_trgm_ops);

CREATE TABLE analysis.device (
    id              uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    make_model      text,
    os              text,
    imei_or_serial  citext,
    owner_entity_id uuid REFERENCES analysis.entity(id)
);
CREATE TABLE analysis.account (
    id              uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    platform        text NOT NULL,
    account_key     citext NOT NULL,
    owner_entity_id uuid REFERENCES analysis.entity(id)
);
CREATE TABLE analysis.vehicle (
    id              uuid PRIMARY KEY REFERENCES analysis.entity(id) ON DELETE CASCADE,
    plate           citext,
    make_model      text,
    owner_entity_id uuid REFERENCES analysis.entity(id)
);

-- ===========================================================================
-- 2.3  ALIASES  (canonical alias records per entity, phonetic+trgm indexed)
--      Adopts E2 entities.aliases[] + Zep ORM Person.aliases (E5 §3) as a
--      first-class, evidence-cited table instead of a bare text[].
-- ===========================================================================
CREATE TABLE analysis.entity_alias (
    id          uuid PRIMARY KEY DEFAULT uuidv7(),
    entity_id   uuid NOT NULL REFERENCES analysis.entity(id) ON DELETE CASCADE,
    alias_text  citext NOT NULL,
    alias_kind  text CHECK (alias_kind IN
                  ('nickname','legal','maiden','handle','misspelling','phonetic','initials','other')),
    confidence  confidence,
    -- phonetic blocking key (fuzzystrmatch) — IMMUTABLE => safe as generated col
    alias_dmeta text GENERATED ALWAYS AS (dmetaphone((alias_text)::text)) STORED,
    provenance  source_ref[] NOT NULL DEFAULT '{}',
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_alias_entity ON analysis.entity_alias (entity_id);
CREATE INDEX idx_alias_trgm   ON analysis.entity_alias USING gin ((alias_text::text) gin_trgm_ops);
CREATE INDEX idx_alias_dmeta  ON analysis.entity_alias (alias_dmeta);

-- ===========================================================================
-- 2.4  ENTITY MENTION  (verbatim surface reference; extracted tier; APPEND-ONLY)
--      Adopts TraceIQ/supabase entity_mentions (E2 §148): mention_text,
--      start_char/end_char, confidence, extraction_method.
-- ===========================================================================
CREATE TABLE analysis.entity_mention (
    id            uuid PRIMARY KEY DEFAULT uuidv7(),
    surface_text  citext NOT NULL,                              -- what literally appeared (mention_text)
    surface_norm  text GENERATED ALWAYS AS (lower((surface_text)::text)) STORED, -- unaccent applied at query time
    mention_kind  text CHECK (mention_kind IN
                    ('name','phone','handle','email','pronoun','partial','address','device','other')),
    -- where it appeared (polymorphic soft ref into evidence/multimodal/message rows)
    subject_type  text,                                         -- 'message'|'ocr_text'|'transcript'|'document'|'source'
    subject_id    uuid,
    start_char    integer,                                      -- E2 entity_mentions.start_char
    end_char      integer,                                      -- E2 entity_mentions.end_char
    context_snippet text,
    extraction_method text,                                     -- 'ner'|'regex'|'parser'|'manual' (E2)
    confidence    confidence,
    mention_dmeta text GENERATED ALWAYS AS (dmetaphone((surface_text)::text)) STORED,
    data_tier     evidence_tier NOT NULL DEFAULT 'extracted',
    provenance    source_ref[]  NOT NULL DEFAULT '{}',
    created_at    timestamptz   NOT NULL DEFAULT now()
);
CREATE INDEX idx_mention_subject ON analysis.entity_mention (subject_type, subject_id);
CREATE INDEX idx_mention_trgm    ON analysis.entity_mention USING gin ((surface_text::text) gin_trgm_ops);
CREATE INDEX idx_mention_dmeta   ON analysis.entity_mention (mention_dmeta);
CREATE INDEX idx_mention_kind    ON analysis.entity_mention (mention_kind);

-- ===========================================================================
-- 2.5  ENTITY RESOLUTION  (mention -> canonical entity; supersedable; HITL)
-- ===========================================================================
CREATE TABLE analysis.entity_resolution (
    id                 uuid PRIMARY KEY DEFAULT uuidv7(),
    mention_id         uuid NOT NULL REFERENCES analysis.entity_mention(id),
    canonical_entity_id uuid NOT NULL REFERENCES analysis.entity(id),
    source_specific_id text,                                    -- id the source used for this referent
    match_method       match_method NOT NULL,                  -- reuse 0004 (exact/resolved/manual)
    resolved_by        text CHECK (resolved_by IN ('rule','model','human')),
    match_score        confidence,
    similarity_metrics jsonb NOT NULL DEFAULT '{}',             -- {trgm, levenshtein, dmetaphone_match, ...}
    -- HITL (C8) — sensitive attributions default to review
    requires_human_review boolean NOT NULL DEFAULT true,
    review_status      review_state NOT NULL DEFAULT 'unreviewed',
    reviewed_by        text,
    reviewed_at        timestamptz,
    review_notes       text,
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    data_tier          evidence_tier NOT NULL DEFAULT 'analytical',
    provenance         source_ref[] NOT NULL DEFAULT '{}',
    sys_period         tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),  -- supersede, never overwrite
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_res_canonical ON analysis.entity_resolution (canonical_entity_id);
CREATE INDEX idx_res_mention   ON analysis.entity_resolution (mention_id);
CREATE INDEX idx_res_review    ON analysis.entity_resolution (review_status);
CREATE INDEX idx_res_open      ON analysis.entity_resolution USING gist (sys_period);
-- one CURRENT resolution per mention (open sys_period); history retained as closed rows
CREATE UNIQUE INDEX uq_res_current ON analysis.entity_resolution (mention_id)
    WHERE upper_inf(sys_period);

-- evidence FOR and AGAINST a resolution/merge (MP 1715-1716; E2 supports/contradicts polarity)
CREATE TABLE analysis.resolution_evidence (
    id             uuid PRIMARY KEY DEFAULT uuidv7(),
    resolution_id  uuid NOT NULL REFERENCES analysis.entity_resolution(id),
    polarity       text NOT NULL CHECK (polarity IN ('supports','contradicts')),
    method         text,                                        -- exact_identifier/trgm/levenshtein/dmetaphone/cooccurrence/manual
    evidence_ref_type text,
    evidence_ref_id   uuid,
    weight         confidence,
    note           text,
    provenance     source_ref[] NOT NULL DEFAULT '{}',
    created_at     timestamptz NOT NULL DEFAULT now()           -- APPEND-ONLY
);
CREATE INDEX idx_resev_res ON analysis.resolution_evidence (resolution_id, polarity);

-- ===========================================================================
-- 2.6  MERGE / SPLIT LOG  (append-only, reversible; MP 1718-1719)
-- ===========================================================================
CREATE TABLE analysis.entity_merge_event (
    id                 uuid PRIMARY KEY DEFAULT uuidv7(),
    op                 text NOT NULL CHECK (op IN ('merge','split')),
    surviving_entity_id uuid NOT NULL REFERENCES analysis.entity(id),
    merged_entity_id   uuid NOT NULL REFERENCES analysis.entity(id),
    actor_id           uuid,                                    -- soft ref to a person/principal
    actor_kind         text CHECK (actor_kind IN ('human','service','agent')),
    rationale          text,
    reversible_to      uuid REFERENCES analysis.entity_merge_event(id),  -- inverse op pointer
    requires_human_review boolean NOT NULL DEFAULT true,
    review_status      review_state NOT NULL DEFAULT 'unreviewed',
    reviewed_by        text,
    reviewed_at        timestamptz,
    provenance         source_ref[] NOT NULL DEFAULT '{}',
    occurred_at        timestamptz NOT NULL DEFAULT now(),      -- APPEND-ONLY
    CONSTRAINT merge_distinct CHECK (surviving_entity_id <> merged_entity_id)
);
CREATE INDEX idx_merge_surv   ON analysis.entity_merge_event (surviving_entity_id);
CREATE INDEX idx_merge_merged ON analysis.entity_merge_event (merged_entity_id);

-- ===========================================================================
-- 2.7  CROSS-STORE CROSSWALK  (build the as-built id_xref forward-declare)
--      PG canonical entity <-> Neo4j node <-> Milvus PK <-> SurrealDB record.
-- ===========================================================================
CREATE TABLE analysis.id_xref (
    id                 uuid PRIMARY KEY DEFAULT uuidv7(),
    canonical_entity_id uuid NOT NULL REFERENCES analysis.entity(id),
    source_system      source_system NOT NULL,                 -- reuse 0004 (postgres/neo4j/milvus/surrealdb)
    native_id          text NOT NULL,                          -- node id / vector pk / surreal id
    match_method       match_method NOT NULL,                  -- reuse 0004
    confidence         confidence,
    is_current         boolean NOT NULL DEFAULT true,
    sys_period         tstzrange NOT NULL DEFAULT tstzrange(now(), NULL),
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_xref_native UNIQUE (source_system, native_id)
);
CREATE INDEX idx_xref_entity ON analysis.id_xref (canonical_entity_id);

-- ---------------------------------------------------------------------------
-- 2.8  Append-only enforcement (immutability for evidence-grade rows)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION analysis.reject_mutation() RETURNS trigger
  LANGUAGE plpgsql AS $$ BEGIN
    RAISE EXCEPTION 'append-only table %.% — % not allowed',
      TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP; END $$;
CREATE TRIGGER trg_mention_append   BEFORE UPDATE OR DELETE ON analysis.entity_mention
  FOR EACH ROW EXECUTE FUNCTION analysis.reject_mutation();
CREATE TRIGGER trg_resev_append     BEFORE UPDATE OR DELETE ON analysis.resolution_evidence
  FOR EACH ROW EXECUTE FUNCTION analysis.reject_mutation();
CREATE TRIGGER trg_merge_append     BEFORE UPDATE OR DELETE ON analysis.entity_merge_event
  FOR EACH ROW EXECUTE FUNCTION analysis.reject_mutation();
-- (review fields on merge_event that legitimately change are applied as NEW append rows
--  or via a separate review-decision table if in-place review status is required.)
```

---

## 3. Decision table

| Table / field | Decision | Source (as-built / paper / prior file) | Note |
|---|---|---|---|
| Schema = `analysis` for all D4 tables | **adopt** (re-home) | as-built E1 §0 boundary | paper's top-level `entity` schema collapsed; derived ⇒ analysis |
| `analysis.entity` (supertype) | **merge** | paper §3.1 + E2 `entities` (§147) + salem/Zep Person/Org (E5) | one addressable supertype, shared-PK satellites |
| `entity.entity_type` | **adapt (ALTER ADD VALUE)** | as-built `0004.entity_type` + E5 gap #1 | extend with forensic kinds; never redefine |
| `entity.normalized_name` + `UNIQUE(type,normalized_name)` | **adopt** | E2 `entities.normalized_name` / UNIQUE | dedup key |
| `entity.merged_into_id` tombstone | **adopt** | paper merge model + MP 1718 | live-entity partial index |
| `entity.sensitivity_tier` | **adapt** | renamed `0004` enum (E1 §5.1 fix) | access classification, not bitemporal |
| `entity.provenance source_ref[]` | **adopt** | `0004.source_ref` composite | avoids evidence↔analysis FK |
| `entity.data_tier / confidence / review_* / safe_for_legal_use` | **adopt** | paper C3/C7/C8 + shared enums | court-safety contract |
| `person` satellite | **merge** | TraceIQ `people` + E2 role + Zep S2/S3 | `role_in_case`,`connection_to`,`is_minor`,`is_party` |
| `person.risk_level` | **deprecate (off-entity)** | Zep S2 `Person.risk_level` (E5 §1) | clinical hypothesis → `analysis.finding`, HITL |
| `organization` satellite | **adopt** | paper §3.1 `entity.organization` | `org_type` text, not enum explosion |
| `phone/email/handle` + validity EXCLUDE | **adapt** | paper §3.1 + A3 §C (changed/blocked) | `btree_gist` no-overlap ownership |
| `phone.is_blocked` / `handle.is_blocked` | **adopt** | E2 §165 (SMS status=64, call type 6) | blocking signal preserved |
| `device/account/vehicle` satellites | **adopt** | paper §3.1 | owner FK to entity |
| `entity_alias` (table) + `alias_dmeta` generated | **adapt** | E2 `entities.aliases[]` + Zep ORM `Person.aliases` (E5 §3) | bare `text[]` → cited table; `dmetaphone` blocking |
| `entity_mention` | **adopt** | E2 `entity_mentions` (§148) + paper §3.2 | `start_char/end_char`,`extraction_method`,`confidence` |
| `entity_mention` lane = `analysis`, append-only | **adapt** | as-built law (evidence=raw only) | immutability by trigger, not by schema |
| `entity_resolution` (+ supersede via `sys_period`) | **adopt** | paper §3.2 + `0004.match_method` | one current resolution per mention |
| `entity_resolution.similarity_metrics jsonb` | **adopt** | fuzzystrmatch+pg_trgm scoring | stores trgm/levenshtein/dmetaphone evidence |
| `resolution_evidence` (supports/contradicts) | **adopt** | paper §3.2 + E2 supports/contradicts polarity | append-only for-and-against |
| `entity_merge_event` (append-only, reversible) | **adopt** | paper §3.2 + MP 1718-1719 | `reversible_to` inverse pointer |
| `id_xref` cross-store crosswalk | **adopt (build forward-declare)** | `0004` `source_system`/`match_method`/`canonical_id` + Zep ORM `zep_node_id`/`ZepEdge` (E5 §3) | PG↔Neo4j↔Milvus↔Surreal identity |
| salem `Incident/Statement/Evidence/Vulnerability/Tactic` as entity kinds | **split (out of D4)** | salem_v3 / E5 §1 | → timeline.event / statement / custody / analysis.finding |
| salem `RELATED_TO` etc. (edges) | **split (out of D4)** | A3 §A | edges are Neo4j/§06, not this PG registry |
| append-only triggers | **adopt** | paper C10 | mention/merge/resolution_evidence immutable |

---

## 4. Migration notes (to reach this on the LIVE DB)

> All DDL targets the single unified PG resource (`agno-postgres:18-duckdb`). **Verify-before-claiming
> (addendum §D.9):** before applying, diff against the LIVE catalog — `\dn` (schemas), `\dT analysis.*`
> and `pg_type` (which `0004` types actually exist; `0004` does NOT auto-apply on an existing `pgdata`
> volume — E1 §5.4), and confirm engine is **PG18** (every PK uses native `uuidv7()`; ungated — E1 §5.5).

1. **Prereq — `0004` applied.** If `pg_type` lacks `entity_type`/`source_system`/`match_method`/
   `confidence`/`source_ref`/`canonical_id`, run `psql -f sql/0004_custom_types.sql` first.
2. **Prereq — shared enums.** `evidence_tier` and `review_state` (paper §0.1) are **not** in `0004`;
   create them once in the D0/shared-types migration:
   `CREATE TYPE evidence_tier AS ENUM ('raw','extracted','inferred','analytical','legal_conclusion');`
   `CREATE TYPE review_state AS ENUM ('unreviewed','in_review','approved','rejected','needs_more_evidence');`
   (guard with `DO $$ … duplicate_object` like `0004`).
3. **Global fix (one-time, cross-domain):** `ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;`
   (the `0004` access enum). The substantive `0003 normalized_record.disclosure_tier` text CHECK
   (`contemporaneous|hindsight|discovered`) is untouched. Coordinate with the temporal domain (D-temporal)
   so both land in the same release.
4. **Type extension:** run the `ALTER TYPE entity_type ADD VALUE …` block (§2.0) **outside a txn**, before
   the table DDL (new enum values aren't usable in the txn that adds them).
5. **Extensions:** confirm `citext`,`pg_trgm`,`fuzzystrmatch`,`btree_gist`,`btree_gin` are present
   (all in `0001`). The `EXCLUDE USING gist (… WITH =, validity WITH &&)` constraints and the
   `dmetaphone()` generated columns hard-depend on `btree_gist` + `fuzzystrmatch` respectively.
6. **Create order:** `analysis.entity` → satellites (`person`,`organization`,`phone`,`email`,`handle`,
   `device`,`account`,`vehicle`) → `entity_alias` → `entity_mention` → `entity_resolution` →
   `resolution_evidence` → `entity_merge_event` → `id_xref` → append-only function + triggers.
   All `CREATE TABLE` are additive (no drops); safe to fold into a single `0005_entities_idres.sql`
   migration applied by hand on the live volume (same pattern as `0003`/`0004`).
7. **Grants / boundary:** the agent **read-only** engine already cannot write `analysis`; ensure the
   ingestion/resolution writer role has `INSERT` on these tables but **no `UPDATE`/`DELETE`** on the three
   append-only tables (defence-in-depth alongside the triggers).
8. **Cross-domain seam (flag for D1 custody):** change `custody.source.{device_origin_id,account_origin_id,
   custodian_id}` from hard FKs into `entity.*` to **soft uuid refs (no FK)**, resolved through this
   registry, so the RO `evidence` lane never FK-depends on writable `analysis`.

### Needs human review
- **`entity_mention` lane placement** — homed in `analysis` (append-only) to honor "evidence = raw only";
  owner may prefer it physically inside `evidence` (RO) as the verbatim extracted surface form. Decision flagged.
- **Sensitive resolutions/merges** — any attribution of an anonymous/blocked account or handle to a party,
  and any row touching a minor, must pass `review_status='approved' AND safe_for_legal_use` before court export.
- **Zep `Person.risk_level` deprecation** — confirm the behavioral `analysis.finding` lane (other domain)
  will own the risk/safety label so it is not lost.
- **D1 custody soft-ref change** (item 8) needs the custody-domain owner's sign-off.
