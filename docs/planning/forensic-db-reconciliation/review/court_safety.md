# Court-Safety & Behavioral Review — D6 / D2 / D7 + E4 ontology

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> **Scope reviewed:** `domains/D6-behavioral.md`, `domains/D2-messages.md`,
> `domains/D7-legal-tasks-export.md`, `extracted/E4_behavioral_ontology.md`.
> **Lens:** abuse/behavior labels as hypothesis-not-fact; human-review + `safe_for_legal_use`
> gating; conclusory vocabulary baked into enums; one-sided vs both-parties + full-cycle modeling;
> child/vulnerability terms as versioned DATA vs hardcode; court-export confidence+approval gating;
> the raw→extracted→inferred→finding→legal-conclusion lane separation.

---

## What the reconciliation already gets right (do not regress)

- **Hypothesis-by-construction in D6.** `pattern_finding` carries `requires_human_review DEFAULT true`,
  `review_status`, `is_verified`, `safe_for_legal_use DEFAULT false`, `data_tier` constrained to
  `inferred`/`analytical`, and the gate CHECK `safe_for_legal_use = false OR review_status='approved'`.
  This is the correct pattern and is the bar every other court-facing table should meet.
- **Config-as-DATA, versioned.** `detection_pattern_set` / `detection_pattern` / `pattern_lexicon`
  hold patterns, keywords, child names, places, vulnerability terms as **rows** with append-only
  versioning — never hardcoded regex. `pattern_finding.pattern_set_id` makes "which config flagged it"
  reproducible. Good.
- **Dual-polarity present.** `category_polarity` (negative/positive/neutral/linguistic_marker),
  `cycle_phase` (calm/repair/love_bombing/...), and D2 `relational_classification`
  (love_bombing/repair_attempt/cooperation/neutral indicators) make positive/neutral/repair first-class.
- **Severity-0 markers** and the **J↔K MCL swap** and **`disclosure_tier` double-definition** are all
  explicitly carried as needs-human-review migration steps, not silently "fixed". Good discipline.
- **Both-parties hooks exist** (`author_party`, `conduct_party`, `risk_kind` incl. `self_incrimination`,
  `trigger_kind` incl. `selective_framing`, `completion_evidence.outcome='overcome'`).

The findings below are where the **enforcement does not match the stated guardrail** — i.e. the prose
says "required / gated / propagated" but the DDL leaves a hole a query or an export can walk through.

---

## Findings (most severe first)

### 1. Seed conflates a child's NAME with severity-10 "parental_alienation" abuse, and the migration says load it verbatim
- **Where:** E4 §3.4 seed (`parental_alienation: "kailah":10, "kyla":10, "my daughter":8`), D6 §5 migration
  step 5 ("Load `seed-patterns.ts` (308 rows)… **Load from source files, do not retype by hand**").
- **Problem:** E4 Guardrail (§0.5 / §4) is explicit that a child-name match is a **relevance** signal,
  **not** abuse — `pattern_lexicon.severity DEFAULT 0`. But the S4 seed places the child names *inside*
  the `parental_alienation` category at **severity 10**. Loading the 308 rows verbatim into
  `detection_pattern` imports `kailah → category=parental_alienation, severity=10`. Every bare mention
  of the child's name then produces a severity-10 abuse hit. That is a behavior label treated as fact,
  and it is the single most prejudicial possible mislabel in a custody matter.
- **Fix:** the seed loader must **route child-name / place / vulnerability terms to `pattern_lexicon`
  (severity 0, relevance_signal), never to `detection_pattern` abuse categories**, regardless of the
  source row's category/severity. Add a load-time assertion: no `detection_pattern` row may have
  `is_case_specific=true` AND a child-name term AND severity>0. Flag blocking for any court output.

### 2. D2 `relational_classification` is the "court-safe HITL surface" but lacks the structural legal gate D6 has
- **Where:** D2 §4 table `analysis.relational_classification` (lines ~366–398).
- **Problem:** it has `requires_human_review`, `review_status`, `safe_for_legal_use DEFAULT false`,
  `data_tier DEFAULT 'analytical'` — but **no CHECK constraint** binding `safe_for_legal_use=true` to
  `review_status='approved'`. D6 `pattern_finding` has exactly that gate; this sibling surface (which
  carries the conclusory fields `love_bombing_indicator`, `cycle_phase`, `relational_function`,
  `mcl_factor_hint`) does not. A row can be flipped `safe_for_legal_use=true` while still `unreviewed`.
- **Fix:** add `CONSTRAINT relcls_legal_gate CHECK (safe_for_legal_use=false OR review_status='approved')`
  and restrict the column to a gatekeeper role, identical to D6 §2.6 and D7 `evidence_item_safe_ck`.

### 3. D2 `analysis.message` stores interpretive labels with NO tier / review / hypothesis flag — readable as fact
- **Where:** D2 §4 `analysis.message` cols `surface_sentiment`, `inferred_intent`, `topic`,
  `domain_type`, `relevance`, `custody_relevance`, `evidence_strength`, plus the denormalized
  `has_behaviors` / `behavior_count` / `max_behavior_severity`.
- **Problem:** these sit as ordinary TEXT columns on the message row alongside the verbatim content,
  with no `data_tier`, no `review_status`, no `safe_for_legal_use`, no `is_hypothesis`. `inferred_intent`
  and `custody_relevance` are conclusory interpretations. The decision table calls them "hints… authoritative
  labels live in D4 behind HITL", but **nothing structural** stops a query/export from selecting
  `message.inferred_intent` and presenting it as extracted fact at the same altitude as the message text.
  The raw→inferred lane is collapsed onto one row with no marker.
- **Fix:** either drop these from `message` and force all interpretation through the gated
  `relational_classification` / `pattern_finding` surfaces, or annotate each as `*_hint` with an explicit
  `evidence_tier`-tagged, non-court-readable comment **and** exclude them from any agent court-read grant
  (mirror D7 step 6: agent court reads hit `vw_court_export` only, never base tables).

### 4. Speaker attribution is "required" in prose but `pattern_finding.author_party` is nullable with no enforcing CHECK
- **Where:** D6 §1 ("`pattern_finding` requires speaker attribution") + E4 Guardrail #3
  ("Author/speaker attribution is **required before interpretation**… Counts without attribution are
  meaningless"); but D6 §2.6 declares `author_party conduct_party` and `author_entity_id uuid` with **no
  NOT NULL and no CHECK**.
- **Problem:** a `pattern_finding` can be inserted, reviewed, approved, and rolled into `finding_id`
  with `author_party = NULL`. An inbound vs outbound pattern means the opposite thing; an approved
  finding with no attribution directly violates the guardrail and enables one-sided "abuse counts" that
  cannot tell who spoke. Both-parties parity is *enabled* but not *enforced*.
- **Fix:** add `CHECK (safe_for_legal_use=false OR author_party IS NOT NULL)` (attribution mandatory
  before legal use), and ideally before `review_status` can reach `approved`.

### 5. D7 court-facing `factor_citation` / `legal_timeline_event` carry legal-conclusion assertions but have no `safe_for_legal_use` gate or export view
- **Where:** D7 §2.2 `factor_citation` and §2.3 `legal_timeline_event`; §4 export view `vw_court_export`.
- **Problem:** the export trip-wire (`safe_for_legal_use` + `evidence_item_safe_ck` + `vw_court_export`)
  guards **only `evidence_item`**. `factor_citation` is the legally-critical "this item supports/contradicts
  MCL factor K (domestic violence)" assertion (`assertion_type` may be `legal_conclusion`) yet has only a
  bare `review_status` TEXT — no `safe_for_legal_use`, no CHECK, no export view. `legal_timeline_event`
  likewise allows `assertion_type='legal_conclusion'` with only `review_status`. Separately,
  `evidence_item.confidence_tier` is a free `TEXT CHECK('high','medium','low')` **not bound** to the
  numeric `confidence` domain, so the export gate `confidence_tier IN ('high','medium')` is bypassable by
  typing 'high' on a `confidence=0.10` row. The confidence gate is therefore advisory, not enforced.
- **Fix:** (a) extend the `safe_for_legal_use` + approved-gate CHECK to `factor_citation` and any
  court-consumed assertion table, or route them through their own gated view; (b) add a CHECK/trigger
  deriving or validating `confidence_tier` against `confidence` (e.g. `confidence>=0.6 ⇒ 'high'`) so the
  export confidence gate cannot be defeated by a mislabeled tier.

### 6. Single-party / adversarial-lexicon `bias_caution` does not propagate to `pattern_finding`, so per-party aggregates surface without the warning
- **Where:** D6 §3 ("`detection_pattern.bias_caution` + `authored_perspective` propagate the
  single-party-provenance warning so no aggregate 'abuse score' is presented as neutral"); but
  `pattern_finding` (§2.6) has **no `bias_caution` / `authored_perspective` column**.
- **Problem:** E4 Guardrail #6 requires that aggregate behavioral metrics never be presented as neutral
  because the seed lexicon is adversarially shaped from one party's narrative. `bias_caution` lives on
  the *pattern* row, but the *finding* row (what gets counted, joined, charted per `author_party`) does
  not carry it. Any `GROUP BY author_party, category` over `pattern_finding` produces an "abuse score"
  with the provenance warning stripped — exactly the failure the guardrail names.
- **Fix:** denormalize `bias_caution` + `authored_perspective` onto `pattern_finding` at write time (or
  expose only via a view that joins them and refuses to emit aggregates without the flag), and require
  reviewer sign-off before any cross-party aggregate is rendered.

---

## Cross-cutting recommendations
- **One gate, applied uniformly.** Promote D6's `(safe_for_legal_use=false OR review_status='approved')`
  CHECK to a shared idiom and apply it to *every* table whose rows can reach a court surface
  (`relational_classification`, `factor_citation`, `legal_timeline_event`, `evidence_item` — done).
- **Lane discipline on message subtype.** Interpretive columns must never live un-tiered next to verbatim
  content; tag or relocate them so a raw message and an `inferred_intent` are never the same altitude.
- **Attribution + bias as preconditions, not metadata.** Make `author_party` and `bias_caution`
  travel with the finding and gate legal use on them — both-parties parity has to be enforced, not merely
  representable.
- **Seed loader is a court-safety boundary.** The verbatim-load step (D6 §5.5) must apply guardrail
  routing (child/place/vuln → `pattern_lexicon` sev 0; reject sev>0 child-name abuse rows) or it will
  import the very fact-as-truth mislabels the ontology warns against.
