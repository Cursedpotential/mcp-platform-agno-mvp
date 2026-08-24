# Verification: MCL Best-Interest Factor (j)/(k) Inversion Claim

> Byline: Claude Code · Sonnet 5 · 2026-08-23

## Overall verdict on the headline claim

**CONFIRMED.** The (j)/(k) name/description inversion is real, live, and unambiguous in
`Agno-MCP-Platform/server/analysis/config/behavioral_patterns.json` as it exists on disk right now.
It has NOT been corrected.

---

## Claim Set A — the (j)/(k) inversion

File: `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform/server/analysis/config/behavioral_patterns.json`

### 1 & 2. The inversion itself — CONFIRMED

Full `mcl_factors` array as it exists on disk (lines 12-73):

```
letter: a  name: "Love, Affection, and Emotional Ties"
letter: b  name: "Capacity to Continue Education"
letter: c  name: "Capacity to Provide"
letter: d  name: "Length of Time in Environment"
letter: e  name: "Permanence of Family Unit"
letter: f  name: "Moral Fitness"
letter: g  name: "Mental and Physical Health"
letter: h  name: "Home, School, and Community Record"
letter: i  name: "Reasonable Preference of Child"
letter: j  name: "Domestic Violence"                          <-- WRONG NAME
letter: k  name: "Willingness to Facilitate Relationship"     <-- WRONG NAME
letter: l  name: "Other Factors"
```

Verbatim (j) entry, line 58-62:
```json
{
  "letter": "j",
  "name": "Domestic Violence",
  "description": "The willingness and ability of each of the parties to facilitate and
  encourage a close and continuing parent-child relationship between the child and the
  other parent or the child and the parents. A court may not consider negatively for the
  purposes of this factor any reasonable action taken by a parent to protect a child or
  that parent from sexual assault or domestic violence by the child's other parent."
}
```
Line 60: `name` = "Domestic Violence". Lines 61: `description` = the MCL 722.23(j)
facilitate-relationship text (this IS the real (j) text). **The `name` field is wrong; the
`description` field is correct for what (j) actually is.**

Verbatim (k) entry, line 63-67:
```json
{
  "letter": "k",
  "name": "Willingness to Facilitate Relationship",
  "description": "Domestic violence, regardless of whether the violence was directed
  against or witnessed by the child."
}
```
Line 65: `name` = "Willingness to Facilitate Relationship". Line 66: `description` = the
real MCL 722.23(k) domestic-violence text. **Same pattern, mirrored: `name` wrong,
`description` correct.**

**This is a clean swap of the two `name` fields only — the `description` fields are each
individually correct for their letter.** Anyone reading the `name` column alone (e.g. a
generated report header, a UI label, an exhibit table that renders `name`) would print
"(j) Domestic Violence" over facilitate-relationship evidence and "(k) Willingness to
Facilitate Relationship" over domestic-violence evidence — i.e. exactly backwards. Anyone
reading only `description` gets the correct statutory text. This is a real defect with
concrete court-facing consequence IF any consumer renders `name` as the factor label
(which is the entire purpose of a `name` field).

No `git blame`/history check was run (out of scope — "do NOT edit anything"), but the file
as it stands on disk, on this branch, right now, has NOT been corrected.

### 3. Category (module) → letter mappings — PARTIAL, not cleanly "correct"

Full module list with every `mcl_factors` array as it exists on disk (id — polarity —
mcl_factors):

| module id | polarity | mcl_factors |
|---|---|---|
| gaslighting | negative | j, k, l |
| blame_shifting | negative | j, l |
| minimization | negative | f, j |
| threats_intimidation | negative | j, l |
| isolation_tactics | negative | j, k |
| financial_control | negative | c, j |
| emotional_blackmail | negative | f, j |
| stonewalling | negative | f, k |
| parental_alienation | negative | i, j, k |
| projection | negative | j, l |
| darvo | negative | j, l |
| overelaboration | negative | l |
| medical_abuse | negative | f, j |
| reproductive_coercion | negative | j, l |
| power_asymmetry | neutral | j, l |
| love_bombing | positive | l |
| future_faking | positive | l |
| affirmations | positive | (none) |
| apologies | positive | l |
| gift_giving | positive | c |
| scheduling | neutral | a, b, d |
| child_wellbeing | neutral | a, b, e, g |
| guilt_trip (needs_review) | negative | (none) |
| boundary_violation (needs_review) | negative | (none) |
| triangulation (needs_review) | negative | (none) |
| word_salad (needs_review) | negative | (none) |
| hoovering (needs_review) | positive | (none) |
| intermittent_reinforcement (needs_review) | positive | (none) |

Assessment against the claim: the letter *usage* is not scrambled the way the `name`
fields are — the letters themselves are drawn from the correct alphabet and applied by
theme, not swapped wholesale. But the claim's framing ("gatekeeping maps to j, violence/
safety maps to k") oversimplifies what's actually there:

- `j` is used broadly as a general "negative/controlling behavior" tag across 13 of the
  16 populated negative modules (gaslighting, blame_shifting, minimization,
  threats_intimidation, isolation_tactics, financial_control, emotional_blackmail,
  parental_alienation, projection, darvo, medical_abuse, reproductive_coercion,
  power_asymmetry) — not narrowly reserved for facilitation/gatekeeping conduct.
- `k` is used far more sparingly, on only 4 modules (gaslighting, isolation_tactics,
  stonewalling, parental_alienation), none of which is a dedicated "domestic
  violence/physical safety" category — there is no module in this file named anything
  like "physical_abuse" or "domestic_violence." The closest thematic fit for physical
  threats, `threats_intimidation`, is tagged `j, l` — **not** `k` — which cuts against a
  clean "violence maps to k" reading.
- `parental_alienation` (the module most squarely about interfering with the other
  parent's relationship — textbook factor-j conduct) carries **both** j and k, not j
  alone.

**Verdict: PARTIAL.** The letters are not swapped/inverted the way the `name` fields are,
but the mapping is not the clean 1:1 "gatekeeping→j / violence→k" split the claim implies
either — `j` functions as a catch-all negative-conduct tag and `k` is applied narrowly and
inconsistently, with the one module most clearly about literal threats/intimidation not
tagged `k` at all.

### Full factor letter inventory — a through l

All twelve letters (a)-(l) are present in `mcl_factors` (lines 12-73 of
behavioral_patterns.json) — none are missing from this file. (Contrast with Claim Set B
below, where the *separate* `edisc.md` document's table is missing (i).)

---

## Claim 4 — does `patterns.py` validate factor letters, and would it catch the inversion?

File: `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform/server/analysis/patterns.py`

**What it validates: pure set membership of individual letters, nothing about
name/description pairing.**

Line 41:
```python
MCL_LETTERS = set("abcdefghijkl")
```

Line 210-212 (inside `validate_chain`):
```python
letters = set(c.mcl_factors.strip("{}").split(",")) - {""}
if not letters <= MCL_LETTERS:
    errs.append(f"{c.category_id}: invalid MCL letters {sorted(letters - MCL_LETTERS)}")
```

This checks that every letter used in a `behavior_category.mcl_factors` array is a member
of the 12-letter set `{a..l}`. It has no concept of a factor's `name` or `description` at
all — those fields don't even exist in the `Category`/`DetectionPattern` dataclasses this
module parses (see the `Category` dataclass at line 47-54, which has `mcl_factors: str`
but no `name`/`label` beyond the category's own `label` field, which is the *behavior
category's* label like "Gaslighting Detection," not the MCL factor's label).

The only place `patterns.py` touches `behavioral_patterns.json` (the file with the
inverted names) is `cross_check_corpus()` (line ~254), which diffs `corpus["modules"]`
(category ids + phrases) against the live migration chain — it never reads
`corpus["mcl_factors"]` (the factor name/description table) at all. **Confirmed by
`Grep` of the module: `corpus["mcl_factors"]` is referenced nowhere in `patterns.py`.**

**Verdict: would NOT catch the inversion.** The validator only confirms a letter is one of
a-l; it performs zero semantic check that a factor's `name` matches its `description`, or
that either matches MCL 722.23. A name/description swap on two already-valid letters (j
and k, both members of the set) passes this validation trivially.

---

## Claim Set B — `edisc.md`'s own taxonomy defect

File: `C:/Users/matts/Downloads/edisc.md` (confirmed present, 25,303 bytes, modified
2026-08-23 11:29)

### 5. "Twelve factors," eleven-row table — CONFIRMED

Line 92: `Every extracted event must map to one of the twelve Michigan Best Interest
Factors under MCL 722.23:`

The table that immediately follows (lines 94-106) verbatim:

```
| Factor | Coverage |
|---|---|
| (a) Emotional Ties | ... |
| (b) Capacity for Guidance/Education | ... |
| (c) Capacity for Medical/Material Needs | ... |
| (d) Continuity in Stable Environment | ... |
| (e) Permanence as a Family Unit | ... |
| (f) Moral Fitness | ... |
| (g) Mental and Physical Health | ... |
| (h) Home, School, Community Record | ... |
| (j) Facilitation of Co-Parent Relationship | ... |
| (k) Domestic Violence/Safety | ... |
| (l) Any Other Relevant Factor | ... |
```

Letters present: a, b, c, d, e, f, g, h, j, k, l — **11 rows**. Letter **(i)** — "the
reasonable preference of the child, if the court considers the child to be of sufficient
age to express preference" — is genuinely absent from the table.

**Verdict: CONFIRMED.** The document asserts "twelve" factors, delivers eleven, and the
specific missing one is (i), the child's stated preference — itself a substantively
significant factor to drop silently from a statutory-tagging schema.

**Side note relevant to Claim Set A:** this document's own (j)/(k) row *content* is
correct per MCL 722.23 — (j) = facilitation, (k) = domestic violence/safety — the
opposite of the inversion found in `behavioral_patterns.json`. This is a different, unrelated
defect (an omission, not an inversion) in a different, unrelated file (guidance prose, not
live application config).

---

## Claim Set C — factor plumbing

### 6. Are factors event/claim-level links (with rationale/span/reviewer/version), or only
category-level attributes? — REFUTED as stated (a linking table exists and is live), with
one real gap (no explicit span column)

`grep -rn "mcl_factor"` across the repo (excluding a stale nested worktree
`.claude/worktrees/wf_2f37bdc8-dea-3/`, which is an unrelated in-progress copy) turns up:

- `server/analysis/config/behavioral_patterns.json` — `mcl_factors` as an attribute of
  each behavior-pattern *module* (category-level), confirming half the claim.
- `docs/planning/forensic-db-reconciliation/migrations/0005_forensic_reconciliation.sql` —
  defines, among others:
  - `analysis.behavior_category.mcl_factors` (category-level, line 1398).
  - `analysis.factor_citation` (line 1543-1560) — **this is an event/claim-level link**:

    ```sql
    CREATE TABLE IF NOT EXISTS analysis.factor_citation (
        id uuid PRIMARY KEY DEFAULT uuidv7(),
        evidence_item_id uuid NOT NULL REFERENCES analysis.evidence_item(id),
        factor mcl_factor NOT NULL REFERENCES analysis.custody_factor(factor),
        legal_issue_id uuid REFERENCES analysis.legal_issue(id),
        supports_factor boolean NOT NULL,
        strength text NOT NULL DEFAULT 'moderate' CHECK (strength IN
          ('weak','moderate','strong','decisive')),
        supporting_text text, relevance_explanation text,
        assertion_type assertion_type NOT NULL DEFAULT 'analytical_finding',
        confidence confidence, is_hypothesis boolean NOT NULL DEFAULT false,
        review_status review_state NOT NULL DEFAULT 'unreviewed',
        safe_for_legal_use boolean NOT NULL DEFAULT false,
        supersedes_citation_id uuid REFERENCES analysis.factor_citation(id),
        created_by text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
        UNIQUE (evidence_item_id, factor, supports_factor),
        ...
    );
    ```
  - `analysis.legal_issue_factor` (line 1497-1500) links a `legal_issue` to a factor with
    `element_note` (a rationale field).
  - `analysis.legal_timeline_event.mcl_factors` (line 1576) — array of factors on a
    timeline event.

  This migration is **applied and live**: `STATUS.md` line 17-18: `## ✅ APPLIED to live
  PG — 2026-06-30 ~09:55 EDT (owner approved "apply")` ... `psql exit 0, zero errors`.

`factor_citation` carries: a **rationale** (`supporting_text`, `relevance_explanation`), a
**reviewer** signal (`review_status`, plus `evidence_item.reviewed_by`/`reviewed_at` on
the record it cites), and links to an individual `evidence_item_id` (not just a category).
It does **not** carry an explicit character-offset **span** column, and it does not carry
an explicit per-row **version** column (though the `evidence_item` it references does
carry `schema_version`/`ontology_version`/`prompt_version`).

**Verdict: REFUTED as a blanket claim** — a live, applied table does link individual
evidence items to individual statutory factors with rationale and reviewer fields, so
"factors are ONLY attributes of behavior categories, never linked event-to-factor" is
false. **PARTIAL on the specific four attributes** — rationale and reviewer are present;
explicit span (character offsets) and an explicit version field on the citation row itself
are genuinely absent.

### 7. "Contradiction rules are UNHOMED" — CONFIRMED, verbatim

`server/analysis/patterns.py`, docstring lines 17-19:
```
The corpus JSON's contradiction_rules remain UNHOMED — the live schema has no
contradiction table yet; that is a pending owner decision, tracked here.
```

And in code, `cross_check_corpus()` returns (near the function's end):
```python
"unhomed_contradiction_rules": [r["id"] for r in corpus.get("contradiction_rules", [])],
```
— the key is literally named `unhomed_contradiction_rules`, and the module's `__main__`
block prints `"... {len(report['unhomed_contradiction_rules'])} contradiction rules
unhomed"`.

Cross-checked against the live migration chain: `grep` for a contradiction table in
`0005_forensic_reconciliation.sql`/`RECONCILED_SCHEMA.sql` returns none — no
`contradiction` table exists in the applied schema. The 4 `contradiction_rules` entries in
`behavioral_patterns.json` (`love_bomb_devalue`, `promise_broken`, `apology_repeat`,
`affirmation_devaluation`, lines 839-877) have nowhere live to land.

**Verdict: CONFIRMED**, word-for-word.

### 8. "Newest ontology migration documented as not applied" — CONFIRMED

File: `docs/planning/forensic-db-reconciliation/migrations/0008_behavior_seed_pattern_analyzer.sql`,
lines 8-11 (status header):
```
--  STATUS: COMMITTED but NOT YET APPLIED to live — application is owner-gated (HITL).
--  The live smoke will report live as 'chain applied through 0007' until this runs.
```

This is the newest file in the `migrations/0006_behavior_seed.sql` /
`0007_behavior_seed_sweep.sql` / `0008_behavior_seed_pattern_analyzer.sql` chain (0005 is
schema-only/base; 0006-0008 carry ontology data, per `patterns.py`'s own docstring: "0008
* pattern-analyzer.ts corpus delta (committed, NOT yet applied)"). 0006 and 0007 both have
apply confirmations in `STATUS.md`; 0008 has none — only the "COMMITTED but NOT YET
APPLIED" header, corroborated by `patterns.py` line 12 (`"0008_* pattern-analyzer.ts
corpus delta (committed, NOT yet applied)"`).

**Verdict: CONFIRMED**, quoted exactly above.

### 9. Modules marked `needs_review` — CONFIRMED, locations given

`server/analysis/config/behavioral_patterns.json`:
- Line 10 (meta.note): `"needs_review=true modules carry NO MCL mapping and few phrases —
  owner triage required"`
- Six modules carry `"needs_review": true`:
  - `guilt_trip` (line 769)
  - `boundary_violation` (line 782)
  - `triangulation` (line 797)
  - `word_salad` (line 810)
  - `hoovering` (line 823)
  - `intermittent_reinforcement` (line 836)

All six of these modules also have `"mcl_factors": []` (empty) — consistent with the
meta note's description, and consistent with Claim 3's observation that the letter
mappings are incomplete/thin in places, though this is a coverage gap, not an inversion.

**Verdict: CONFIRMED.**

---

## Summary table

| # | Claim | Verdict | Key evidence |
|---|---|---|---|
| 1 | (j) named "Domestic Violence," described as facilitate-relationship | CONFIRMED | `behavioral_patterns.json:59-61` |
| 2 | (k) named "Willingness to Facilitate," described as domestic violence | CONFIRMED | `behavioral_patterns.json:64-66` |
| 3 | Category mappings use letters correctly (gatekeeping→j, violence→k) | PARTIAL | module table above; `j` is a broad catch-all, `k` is sparse and inconsistent, `threats_intimidation` is tagged j not k |
| 4 | `patterns.py` validation would catch the inversion | REFUTED | `patterns.py:41,210-212` — set-membership only, no name/description check |
| 5 | edisc.md claims 12 factors, lists 11, missing (i) | CONFIRMED | `edisc.md:92,94-106` |
| 6 | No event/claim-level factor link w/ rationale, span, reviewer, version | REFUTED (linking table exists, live) / PARTIAL (span & row-level version absent) | `0005_forensic_reconciliation.sql:1543-1560` (`analysis.factor_citation`); applied per `STATUS.md:17-18` |
| 7 | Contradiction rules UNHOMED | CONFIRMED | `patterns.py:17-19`, `unhomed_contradiction_rules` key |
| 8 | Newest migration documented not-applied | CONFIRMED | `0008_behavior_seed_pattern_analyzer.sql:10` |
| 9 | Modules marked needs_review | CONFIRMED | `behavioral_patterns.json:10,769,782,797,810,823,836` |
