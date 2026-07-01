# D6 — Behavioral Findings, Patterns & Detection Config (reconciled)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> Reconciliation domain **D6** of the forensic-DB pass. Scope: the behavioral-analysis
> mini-app's persistence — the **abuse/manipulation/positive taxonomy**, the **detection-pattern
> config** (regex/literal/keyword lexicons as *versioned DATA*, never code), the **case-specific
> lexicons** (child names, places, vulnerability terms), the **MCL 722.23 factor mapping**, and
> the **per-match detection rows** (`pattern_finding`). It sits **below** the synthesized
> `analysis.finding` table (paper §8.3, owned by the findings domain): D6 produces the mechanical,
> attributed, triage-level match records; those roll up into court-facing findings there.
>
> **Ground truth:** E1 (as-built law) + E4 (behavioral ontology) + E2 §D (behavior-detection
> tables) + the addendum + paper §03 (§0 contract, §8 analysis). **Not a blank slate** — every
> table adopts/adapts prior art (`detection_patterns.py`, `seed-patterns.ts`, `behavioral_patterns.ttl`,
> `positive_behaviors.ttl`, `mcl_722_23.ttl`, `messaging_behaviors`/`behavior_categories`), cited inline.

---

## 1. Reconciliation reasoning (the calls that shaped the DDL)

**Schema home = `analysis` (not a new `config`/`behavior` schema).** The as-built security boundary
(E1 §0/§6) admits exactly three schemas: `evidence` (raw, agents RO, connection-enforced),
`analysis` (derived, write-after-approval), `public` (HITL audit + Agno-managed). Detection config
and findings are **derived/curated analytical assets**, not raw evidence and not Agno-runtime
tables — so the whole domain lands in **`analysis`**, distinguished by table-name sub-domain
prefixes (`behavior_*`, `detection_*`, `pattern_*`). Curating the lexicon is itself an *approved
write* into `analysis`, which matches the boundary exactly. The paper's parallel idea of a free-standing
config namespace is dropped per the guardrail (no `core/raw/geo/legal` top-level schemas).

**Config-as-DATA, versioned (the central requirement).** Patterns, keywords, severities, MCL maps
and case-specific terms are **rows**, never hardcoded regex in an engine (E4 Guardrail #5; the
~200-hr curated lexicon). `analysis.detection_pattern_set` is the **version container**: every edit
ships a new set version (append-only, `is_active` flips, `valid_from/valid_to` — never delete, per
the never-delete→`_stale/` rule). Each `pattern_finding` records the **exact set version** it was
produced under, so a court can reproduce which config flagged a message.

**Detection = hypothesis, structurally.** Every `pattern_finding` row carries
`requires_human_review DEFAULT true`, `review_status`, `is_verified`, and `safe_for_legal_use
DEFAULT false`, with a CHECK that **bars `safe_for_legal_use` unless `review_status='approved'`**
(E4 Guardrail #1/#2; CONTEXT_PACK §6). `severity`/`score` are **triage priority only**, never legal
weight. `data_tier` is constrained to `inferred`/`analytical` — a regex hit is an *interpretation*,
never `raw` and never auto-promoted to `legal_conclusion` (lane invariant, paper §13).

**Both-parties parity is built in, not bolted on.** `pattern_finding` requires speaker attribution
(`author_party conduct_party`, `author_entity_id`) because a pattern *inbound* means the opposite of
the same pattern *outbound* (E4 Guardrail #3). `detection_pattern.authored_perspective` +
`bias_caution` flag the adversarially-shaped, single-party provenance of the seed lexicon (E4
Guardrail #6) so aggregate "abuse scores" are never surfaced as neutral metrics. Positive / neutral /
love-bombing / repair categories are first-class `category_polarity` values (adopt `positive_behaviors.ttl`),
not an afterthought — they are the contradiction anchors, not exoneration (Guardrail #4).

**Reuse, don't redefine.** `mcl_factor` (enum `a`..`l`) and `confidence` (domain `numeric(4,3)`)
come straight from `0004`. `evidence_tier`/`review_state`/`strength_class`/`conduct_party` are the
shared paper-§0.1 enums (created once in the shared-types migration; referenced here). Only three
genuinely-new enums are introduced (`pattern_match_type`, `category_polarity`, `detection_method`).
The `0004` `disclosure_tier` double-definition is **not** reused here; lexicon sensitivity uses the
renamed `sensitivity_tier` (see migration §4).

**Two known prior-art bugs are carried forward as explicit migration steps, not silently fixed:**
the **J↔K MCL swap** (E4 §6.2 — `mcl_722_23.ttl` labels are swapped vs their definitions; S6 follows
the buggy labels) → seed using statutory-canonical `J=facilitation`, `K=domestic_violence` and remap
any S3/S6-derived tags; and the **`disclosure_tier` rename** (E1 §5.1). Both are flagged needs-human-review.

---

## 2. Reconciled DDL

```sql
-- ============================================================================
-- D6 — Behavioral findings, patterns & detection config
-- Schema: analysis (derived / write-after-approval — as-built boundary, E1 §0/§6)
-- Reuses 0004 types (mcl_factor, confidence) + paper §0.1 shared enums.
-- ============================================================================

-- 0004 + paper §0.1 types are assumed present (created by 0004 / the shared-types
-- migration): mcl_factor, confidence, evidence_tier, review_state, strength_class,
-- conduct_party, sensitivity_tier (renamed from the 0004 disclosure_tier enum, §4).
-- This domain introduces three new enums (idempotent-guarded):

DO $$ BEGIN
  CREATE TYPE pattern_match_type AS ENUM ('literal','regex');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE category_polarity AS ENUM ('negative','positive','neutral','linguistic_marker');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE detection_method AS ENUM
    ('literal','regex','priority_screener','semantic_similarity','model','human','imported');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ----------------------------------------------------------------------------
-- 2.1 analysis.detection_pattern_set — versioned config container (config-as-DATA)
--     Adopt: the "config table, loadable as data" mandate (E4 Guardrail #5, §7).
--     Append-only versioning; never delete a set, deprecate via is_active/valid_to.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis.detection_pattern_set (
    id              uuid PRIMARY KEY DEFAULT uuidv7(),
    name            citext NOT NULL,                       -- e.g. 'salem-custody-lexicon'
    version         text   NOT NULL,                       -- semantic version of the curated set
    source          text,                                  -- provenance tag S1..S9 (E4 §1)
    source_artifact text,                                  -- origin path (seed-patterns.ts, *.ttl)
    description     text,
    is_active       boolean NOT NULL DEFAULT false,        -- exactly the loaded-in-prod version(s)
    authored_perspective text,                             -- whose narrative (bias provenance, E4 #6)
    valid_from      timestamptz NOT NULL DEFAULT now(),
    valid_to        timestamptz,                           -- NULL = current; set on supersede (never delete)
    created_at      timestamptz NOT NULL DEFAULT now(),
    provenance_id   uuid,                                  -- FK -> provenance record (cross-domain, §4)
    UNIQUE (name, version)
);
CREATE INDEX IF NOT EXISTS idx_pattern_set_active
    ON analysis.detection_pattern_set (is_active) WHERE is_active;

-- ----------------------------------------------------------------------------
-- 2.2 analysis.behavior_category — the taxonomy (negative + positive + neutral)
--     Adopt: behavior_categories (E2 §D, the 18) + seed-patterns 26-cat (E4 §2.1/2.2)
--             + positive_behaviors.ttl (E4 §5, dual-polarity) + neutral/linguistic (E4 §2.4).
--     category_id is citext (case-insensitive: gaslighting == Gaslighting).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis.behavior_category (
    category_id      citext PRIMARY KEY,                   -- canonical id, e.g. 'gaslighting'
    label            text NOT NULL,
    description      text,
    polarity         category_polarity NOT NULL,           -- negative/positive/neutral/linguistic_marker
    default_severity smallint NOT NULL DEFAULT 5,          -- canonical 1-10; 0 = neutral marker (E4 #7)
    mcl_factors      mcl_factor[] NOT NULL DEFAULT '{}',   -- reuse 0004 enum (a..l); statutory-canonical
    aliases          citext[] NOT NULL DEFAULT '{}',       -- alienation<->parental_alienation etc (E4 §8.2)
    is_case_specific boolean NOT NULL DEFAULT false,
    source           text,                                 -- S1..S9 provenance tag
    notes            text,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT behavior_category_sev_chk CHECK (default_severity BETWEEN 0 AND 10)
);
CREATE INDEX IF NOT EXISTS idx_behavior_category_polarity
    ON analysis.behavior_category (polarity);
CREATE INDEX IF NOT EXISTS idx_behavior_category_mcl
    ON analysis.behavior_category USING gin (mcl_factors);
CREATE INDEX IF NOT EXISTS idx_behavior_category_alias
    ON analysis.behavior_category USING gin (aliases);

-- ----------------------------------------------------------------------------
-- 2.3 analysis.detection_pattern — the patterns themselves, as DATA, versioned
--     Adopt: seed-patterns.ts (308 literal rows), behavioral_patterns.ttl (regex+sev+MCL),
--             ABUSE_PATTERNS (S5 regex), detection_patterns.py scored rules (E4 §3.1-3.4).
--     match_type literal|regex; severity = triage (0-10); score = custody relevance (S9).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis.detection_pattern (
    id               uuid PRIMARY KEY DEFAULT uuidv7(),
    pattern_set_id   uuid NOT NULL REFERENCES analysis.detection_pattern_set(id),
    category_id      citext NOT NULL REFERENCES analysis.behavior_category(category_id),
    subcategory      text,                                 -- e.g. darvo_reverse, child_weaponization
    match_type       pattern_match_type NOT NULL,
    pattern          text NOT NULL,                        -- literal substring OR regex source
    keywords         text[] NOT NULL DEFAULT '{}',         -- example trigger phrases
    severity         smallint NOT NULL DEFAULT 5,          -- 0-10 triage (0 = neutral marker)
    score            smallint,                             -- 1-10 custody relevance (S9), nullable
    mcl_factors      mcl_factor[] NOT NULL DEFAULT '{}',   -- per-pattern override of category default
    description      text,
    is_case_specific boolean NOT NULL DEFAULT false,       -- TRUE for names/places/slurs
    authored_perspective text,                             -- bias provenance (E4 #6)
    bias_caution     boolean NOT NULL DEFAULT true,        -- adversarially-shaped lexicon flag
    source           text,                                 -- S1..S9
    is_active        boolean NOT NULL DEFAULT true,
    valid_from       timestamptz NOT NULL DEFAULT now(),
    valid_to         timestamptz,                          -- deprecate, never delete
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT detection_pattern_sev_chk   CHECK (severity BETWEEN 0 AND 10),
    CONSTRAINT detection_pattern_score_chk CHECK (score IS NULL OR score BETWEEN 1 AND 10),
    UNIQUE (pattern_set_id, category_id, match_type, pattern)   -- dedupe within a set
);
CREATE INDEX IF NOT EXISTS idx_detection_pattern_cat
    ON analysis.detection_pattern (category_id);
CREATE INDEX IF NOT EXISTS idx_detection_pattern_set
    ON analysis.detection_pattern (pattern_set_id);
CREATE INDEX IF NOT EXISTS idx_detection_pattern_active
    ON analysis.detection_pattern (is_active) WHERE is_active;
CREATE INDEX IF NOT EXISTS idx_detection_pattern_kw
    ON analysis.detection_pattern USING gin (keywords);
CREATE INDEX IF NOT EXISTS idx_detection_pattern_mcl
    ON analysis.detection_pattern USING gin (mcl_factors);
CREATE INDEX IF NOT EXISTS idx_detection_pattern_trgm
    ON analysis.detection_pattern USING gin (pattern gin_trgm_ops);   -- fuzzy pattern lookup

-- ----------------------------------------------------------------------------
-- 2.4 analysis.pattern_lexicon — case-specific term lists as DATA (child/place/vuln)
--     Adopt: child_name_lexicon, child_reference_lexicon, vulnerability_lexicon,
--             place_lexicon (E4 §4). A child-name match is RELEVANCE, not abuse.
--     sensitivity_tier (renamed 0004 enum) gates exposure of minor/intimate terms.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis.pattern_lexicon (
    id               uuid PRIMARY KEY DEFAULT uuidv7(),
    pattern_set_id   uuid NOT NULL REFERENCES analysis.detection_pattern_set(id),
    lexicon_type     text NOT NULL,                        -- child_name|child_reference|vulnerability|place|cluster_topic
    term             text NOT NULL,                        -- canonical term / spelling
    variants         text[] NOT NULL DEFAULT '{}',         -- voice-recognition / spelling variants
    match_type       pattern_match_type NOT NULL DEFAULT 'literal',
    relevance_signal text,                                 -- what a match MEANS (e.g. 'concerns_child')
    severity         smallint NOT NULL DEFAULT 0,          -- usually 0 (relevance, not abuse)
    mcl_factors      mcl_factor[] NOT NULL DEFAULT '{}',
    is_case_specific boolean NOT NULL DEFAULT true,
    sensitivity_tier sensitivity_tier NOT NULL DEFAULT 'restricted',  -- minor names = restricted/sealed
    source           text,
    is_active        boolean NOT NULL DEFAULT true,
    valid_from       timestamptz NOT NULL DEFAULT now(),
    valid_to         timestamptz,
    created_at       timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pattern_lexicon_sev_chk CHECK (severity BETWEEN 0 AND 10)
);
CREATE INDEX IF NOT EXISTS idx_pattern_lexicon_type
    ON analysis.pattern_lexicon (lexicon_type);
CREATE INDEX IF NOT EXISTS idx_pattern_lexicon_variants
    ON analysis.pattern_lexicon USING gin (variants);

-- ----------------------------------------------------------------------------
-- 2.5 analysis.behavior_category_mcl — normalized, queryable category<->MCL map
--     Adopt: mcl_722_23.ttl factor map + E4 §6.3 consensus map.
--     Statutory-canonical letters (J=facilitation, K=domestic_violence) — see §4 J<->K fix.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis.behavior_category_mcl (
    category_id   citext     NOT NULL REFERENCES analysis.behavior_category(category_id),
    factor_code   mcl_factor NOT NULL,                     -- reuse 0004 enum (a..l)
    weight        text,                                    -- High/Med/Critical/Variable (E4 §6.1)
    is_critical   boolean NOT NULL DEFAULT false,          -- J & K are the critical custody factors
    note          text,
    PRIMARY KEY (category_id, factor_code)
);
CREATE INDEX IF NOT EXISTS idx_behavior_category_mcl_factor
    ON analysis.behavior_category_mcl (factor_code);

-- ----------------------------------------------------------------------------
-- 2.6 analysis.pattern_finding — per-match detection rows (the messaging_behaviors table)
--     Adopt/adapt: messaging_behaviors / behaviors (E2 §D), detection_patterns.py output,
--             multi-pass-classifier output (E4 §7). EVERY row is a HYPOTHESIS.
--     Polymorphic subject (message/ocr_text/transcript/event) — runs on any text artifact.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS analysis.pattern_finding (
    id                 uuid PRIMARY KEY DEFAULT uuidv7(),
    -- subject (polymorphic; integrity via trigger, see §3 / paper §14.2)
    subject_type       text NOT NULL,                      -- 'message'|'ocr_text'|'transcript'|'event'
    subject_id         uuid NOT NULL,                      -- -> evidence.message(id) etc (cross-domain)
    -- detection config that produced this row (reproducibility)
    category_id        citext NOT NULL REFERENCES analysis.behavior_category(category_id),
    pattern_id         uuid REFERENCES analysis.detection_pattern(id),  -- NULL for model/semantic pass
    pattern_set_id     uuid REFERENCES analysis.detection_pattern_set(id), -- exact config version
    subcategory        text,
    detection_method   detection_method NOT NULL,
    rule_name          text,                               -- engine rule id (e.g. parenting_time_001)
    -- the match itself
    matched_text       text,                               -- the literal span that matched
    matched_pattern    text,                               -- the pattern that fired (snapshot)
    start_char         integer,
    end_char           integer,
    context_before     text,
    context_after      text,
    -- attribution (REQUIRED before interpretation — E4 #3; both-parties parity)
    author_party       conduct_party,                      -- user/partner/child/third_party/...
    author_entity_id   uuid,                               -- -> entity.person(id) (cross-domain)
    -- triage scores (NOT legal weight)
    confidence         confidence,                         -- reuse 0004 domain [0,1]
    severity           smallint,                           -- 0-10 triage
    score              smallint,                           -- 1-10 custody relevance
    evidence_strength  strength_class,                     -- paper §0.1 shared enum
    -- court-safe gating
    is_verified        boolean NOT NULL DEFAULT false,
    verified_by        text,
    verified_at        timestamptz,
    verification_notes text,
    requires_human_review boolean NOT NULL DEFAULT true,
    review_status      review_state NOT NULL DEFAULT 'unreviewed',
    safe_for_legal_use boolean NOT NULL DEFAULT false,
    -- roll-up + lane + provenance
    finding_id         uuid,                               -- -> analysis.finding(id) (findings domain)
    data_tier          evidence_tier NOT NULL DEFAULT 'inferred',
    provenance_id      uuid,                               -- -> provenance record (cross-domain, §4)
    created_at         timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT pattern_finding_sev_chk    CHECK (severity IS NULL OR severity BETWEEN 0 AND 10),
    CONSTRAINT pattern_finding_score_chk  CHECK (score    IS NULL OR score    BETWEEN 1 AND 10),
    CONSTRAINT pattern_finding_subj_chk   CHECK (subject_type IN ('message','ocr_text','transcript','event')),
    CONSTRAINT pattern_finding_tier_chk   CHECK (data_tier IN ('inferred','analytical')),
    -- court gate: cannot be legal-safe unless approved (E4 #1/#2; lane invariant)
    CONSTRAINT pattern_finding_legal_gate CHECK (safe_for_legal_use = false OR review_status = 'approved')
);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_subject
    ON analysis.pattern_finding (subject_type, subject_id);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_category
    ON analysis.pattern_finding (category_id);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_review
    ON analysis.pattern_finding (review_status);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_author
    ON analysis.pattern_finding (author_party);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_finding
    ON analysis.pattern_finding (finding_id);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_triage
    ON analysis.pattern_finding (severity DESC NULLS LAST, review_status);
CREATE INDEX IF NOT EXISTS idx_pattern_finding_hitl
    ON analysis.pattern_finding (id) WHERE requires_human_review;
CREATE INDEX IF NOT EXISTS idx_pattern_finding_matched_trgm
    ON analysis.pattern_finding USING gin (matched_text gin_trgm_ops);
```

---

## 3. Integrity, symmetry & append-only notes

- **Polymorphic subject FK.** `pattern_finding.(subject_type,subject_id)` trades a declarative FK for
  the ability to flag any text artifact (message/OCR/transcript/event). Enforce with a per-target
  partial-FK trigger (same posture as paper §14.2); acceptable for v1, revisit if drift appears.
- **Symmetry / bias.** Detection MUST be run over **all parties'** messages (E4 #6). `author_party`
  makes per-party rollups queryable; `detection_pattern.bias_caution` + `authored_perspective`
  propagate the single-party-provenance warning so no aggregate "abuse score" is presented as neutral.
- **Dedup.** The same phrase appears as literal (S4), regex (S1/S5) and substring (S6). De-dupe matches
  by `(subject_id, category_id, start_char, matched_text)` at write time to avoid triple-counting
  severity (E4 §8.4) — enforce with a partial unique index once span semantics are fixed.
- **Append-only.** Config sets/patterns/lexicon rows are versioned (`is_active`,`valid_to`), never
  deleted; `pattern_finding` rows are append-only (a re-run under a new `pattern_set_id` inserts new
  rows; old findings retained for provenance).
- **Cross-domain FKs deferred (soft columns).** `provenance_id`, `finding_id`, `subject_id`,
  `author_entity_id` reference tables owned by other reconciliation domains (provenance, findings,
  messaging/evidence, entity). They are declared as `uuid` columns; the hard FKs are added in the
  consolidation migration once those domains' final homes/names are fixed (see §4).

---

## 4. Decision table

| Table / field | Decision | Source (as-built / paper / prior file) | Note |
|---|---|---|---|
| schema = `analysis` for whole domain | **adopt** | as-built E1 §0/§6 boundary | config + findings are derived assets; no new top-level schema |
| `detection_pattern_set` | **adapt** | E4 §7 "loadable config" + never-delete rule | net-new version container making "patterns as DATA, versioned" concrete |
| `behavior_category` | **merge** | E2 §D `behavior_categories` (18) + E4 §2 (26-cat) + `positive_behaviors.ttl` | one taxonomy table, dual-polarity; `category_id` citext + `aliases[]` reconcile name variants |
| `behavior_category.polarity` | **adapt** | E4 §2.3/2.4/5; paper C9 | negative/positive/neutral/linguistic_marker = first-class (full relational cycle) |
| `behavior_category.default_severity` | **adapt** | E4 §8.1 (unify 3 scales → canonical 1-10, 0=neutral) | smallint 0-10; derive UI weights |
| `behavior_category.mcl_factors[]` | **adopt** | E2 `behavior_categories.mcl_factors` + E4 §6.3 | reuse `mcl_factor` (0004 enum) |
| `detection_pattern` | **merge** | `seed-patterns.ts` (S4,308) + `behavioral_patterns.ttl` (S1) + `ABUSE_PATTERNS` (S5) + `detection_patterns.py` (S9) | one config table, `match_type` literal/regex; full set loaded from source, not retyped |
| `detection_pattern.score` | **adopt** | S9 `detection_patterns.py` custody score 1-10 | distinct from triage `severity` |
| `detection_pattern.is_case_specific` / `authored_perspective` / `bias_caution` | **adapt** | E4 #5/#6 guardrails | bias + case-specificity as data |
| `pattern_lexicon` | **adopt** | E4 §4 child_name/child_reference/vulnerability/place lexicons | child-name = relevance not abuse; `sensitivity_tier` gates minor terms |
| `behavior_category_mcl` | **adopt** | `mcl_722_23.ttl` (S3) + E4 §6.3 | normalized junction; statutory-canonical letters |
| MCL factor reference (letters/labels) | **merge/defer** | E2 `mcl_factors` + E4 §6.1 + paper `legal.custody_factor` | single canonical MCL reference — **coordinate with legal domain** (do not double-define); D6 uses the `mcl_factor` enum + junction |
| `pattern_finding` | **adapt** | E2 §D `messaging_behaviors`/`behaviors` + S9 output | per-match hypothesis row; the prompt's target table |
| `pattern_finding` fields (message_id→subject, category, matched_text, confidence, severity, detection_method, is_verified, verified_by/at, verification_notes) | **adopt** | E2 §D `messaging_behaviors` columns | message_id generalized to polymorphic subject |
| `pattern_finding.author_party` / `author_entity_id` | **adapt** | E4 #3 (speaker attribution) + paper `conduct_party` | both-parties parity built in |
| `pattern_finding.{requires_human_review,review_status,safe_for_legal_use}` + legal-gate CHECK | **adapt** | paper C8 + E4 #1/#2 | court-safe gating, structurally enforced |
| `pattern_finding.pattern_set_id` | **adapt** | net-new (reproducibility) | ties each finding to exact config version |
| `pattern_finding.finding_id` | **split** | links low-level match → synthesized `analysis.finding` (paper §8.3) | keeps mechanical detection separate from court-facing finding |
| `mcl_factor` (a..l), `confidence` types | **adopt (reuse)** | `0004` custom types | never redefined |
| `evidence_tier`,`review_state`,`strength_class`,`conduct_party` | **adopt (reuse)** | paper §0.1 shared enums | referenced, created once in shared migration |
| `pattern_match_type`,`category_polarity`,`detection_method` | **adapt (new)** | this domain | only genuinely-new enums |
| `0004 disclosure_tier` enum (public/restricted/sealed) | **deprecate→rename** | E1 §5.1 bug | renamed `sensitivity_tier`; used by `pattern_lexicon.sensitivity_tier` |
| J↔K MCL letters | **adapt (remap)** | E4 §6.2 swap bug | seed statutory-canonical; remap S3/S6-derived tags |
| engine regex hardcoding | **deprecate** | E4 #5 | patterns live in tables, not code |

---

## 5. Migration notes (live `agno-postgres:18-duckdb`)

Acceptance step first (verify-before-claiming): diff against the LIVE DB before applying; confirm
PG18 (`uuidv7()`), and that `0004` types + the shared-types migration are present (E1 §3 apply-once drift).

1. **Prereqs / shared types.** Ensure `0004` is applied (`mcl_factor`, `confidence`) and the
   shared-types migration created `evidence_tier`, `review_state`, `strength_class`, `conduct_party`.
   If `0004` was not hand-applied on the live volume, run it first.
2. **`disclosure_tier` rename (cross-cutting, do once).**
   `ALTER TYPE disclosure_tier RENAME TO sensitivity_tier;` (the `0004` enum public/restricted/sealed).
   Leaves the `0003` `normalized_record.disclosure_tier` TEXT/CHECK column untouched (it is the
   substantive bitemporal one). Then this domain's `pattern_lexicon.sensitivity_tier` resolves.
3. **New enums.** `CREATE TYPE pattern_match_type / category_polarity / detection_method` (guarded).
4. **Create tables** in order: `detection_pattern_set` → `behavior_category` →
   `detection_pattern` → `pattern_lexicon` → `behavior_category_mcl` → `pattern_finding`
   (FK dependency order). All `CREATE TABLE IF NOT EXISTS`; idempotent.
5. **Seed config as DATA (not code).** Load `seed-patterns.ts` (308 rows), `behavioral_patterns.ttl`,
   `ABUSE_PATTERNS` (S5), `detection_patterns.py` scored rules, `positive_behaviors.ttl`, and the
   case-specific lexicons into `detection_pattern_set` v1 (`is_active=true`). **Load from source files,
   do not retype by hand** (E4 §3.4). Tag each row's `source` (S1..S9) and `authored_perspective`.
6. **MCL seed = statutory-canonical.** Seed `behavior_category_mcl` with `J=facilitation`,
   `K=domestic_violence` (E4 §6.1). Add a one-time remap for any imported S3/S6-label-derived `j`/`k`
   tags (E4 §6.2). **Blocking for court use.**
7. **Add cross-domain FKs in consolidation.** Once provenance/findings/messaging/entity domains land,
   add `provenance_id → provenance(...)`, `finding_id → analysis.finding(id)`, the subject partial-FK
   trigger (`subject_id → evidence.message(id)`/`multimodal.ocr_text(id)`/etc.), and
   `author_entity_id → entity.person(id)`.
8. **Append-only enforcement.** Grant no UPDATE/DELETE on `pattern_finding` to the analysis role;
   config edits insert a new `detection_pattern_set` version and flip `is_active` (never delete).
9. **Dedup guard.** After span semantics are confirmed, add
   `CREATE UNIQUE INDEX ... ON analysis.pattern_finding (subject_id, category_id, start_char, end_char, matched_text)`
   to prevent triple-counting (E4 §8.4).

---

## 6. Needs-human-review (carry to consolidated report)

- **J↔K MCL swap (blocking, court-use).** `mcl_722_23.ttl` labels are swapped vs definitions; S6 follows
  the buggy labels. Seed statutory-canonical and remap legacy tags before any court output (E4 §6.2).
- **MCL factor reference home.** D6 references the `mcl_factor` enum + junction but the canonical
  factor-label reference (A–L statutory text) overlaps paper `legal.custody_factor`. Pick ONE home
  (likely `analysis` per boundary) and avoid a second `disclosure_tier`-style double-definition.
- **Single-party lexicon bias.** The seed lexicon is adversarially shaped from one party's perspective;
  production use must run symmetrically and surface `bias_caution`. Reviewer sign-off required before
  any aggregate behavioral metric is shown.
- **Polymorphic subject integrity.** Trigger-based FK on `(subject_type,subject_id)` accepted for v1.
