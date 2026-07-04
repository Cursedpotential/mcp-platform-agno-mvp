# G7 — Zep/Salem v3 Ontology Extraction → analysis schema seed

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
> Source artifact: `extracted-code/ontologies-datasets/zep_salem_ontology_v3_final.py`
> (`source='zep_salem_ontology_v3'`). Companion files inert: `dataset_loader.py` (config-only,
> 55 lines: MySQL/HurtLex/ontology-dir env constants, no pattern data) and `test_gliner.py`
> (5-line stdin echo stub) contribute **nothing** behavioral.
> Target: live `analysis` schema (`detection_pattern_set`, `behavior_category`, `detection_pattern`,
> `pattern_lexicon`, `behavior_category_mcl`).
> **Patterns are HYPOTHESES, not facts.** Every negative `detection_pattern` carries `bias_caution=true`.

---

## 0. What this source IS (and is not)

This is **not a pattern library** like the G3 `.ttl` files. It is a **Zep Cloud / Graphiti
knowledge-graph schema** (`zep_cloud.external_clients.ontology`) for the *Salem v. Kinzel* Michigan
custody case — i.e. the **entity / relationship / timeline lane** (the same lane the project routes to
Graphiti, per `MEMORY_ARCHITECTURE.md`). It defines:

- **5 entity types** (Zep cap = 10): `Person`, `Location`, `Incident`, `Statement`, `Vulnerability`.
- **8 edge types** (Zep cap = 10): `CoerciveTactic`, `SpreadsRumor`, `Contradicts`, `ExposedTo`,
  `Facilitated`, `Exploits`, `WasAt`, `MadeStatement` (registered as `USED_TACTIC`, `SPREADS_RUMOR`,
  `CONTRADICTS`, `EXPOSED_CHILD`, `AFFECTED_ACCESS`, `TARGETED_WOUND`, `WAS_AT`, `MADE_STATEMENT`).

There are **zero regex/keyword patterns** in this file. The behavioral signal lives in the **controlled
vocabularies of the pydantic field `description=` enums** (e.g. `tactic_type`, `darvo_stage`,
`deception_strategy`, `strategic_goal`, `event_type`). Those vocabularies are what seed
`behavior_category` (and a small generic `detection_pattern` keyword set). The schema also carries
**case-specific named persons and trauma content** that route to `pattern_lexicon` under seal.

**Primary contribution to the relational analysis schema = `behavior_category` taxonomy + MCL mappings +
a sealed/restricted `pattern_lexicon` of case identifiers and vulnerabilities.** The entity/edge graph
structure itself stays in the Zep/Graphiti lane and is NOT relationally re-seeded here.

---

## 0b. Court-safety routing result (CRITICAL — this source is case-specific)

Unlike G3 (all generic), this ontology embeds **named individuals and real trauma**:

| token in source | kind | routing | tier |
|---|---|---|---|
| `Matt` (Location.owner / told_to / Vulnerability.owner examples) | petitioner/father personal identifier | `pattern_lexicon` | **sealed** |
| `Catrina` (Location.owner example) | respondent/mother personal identifier | `pattern_lexicon` | **sealed** |
| `Dennis` (Location.owner example) | third-party personal identifier | `pattern_lexicon` | **sealed** |
| `her_mother`, `friend_name` (Statement.told_to) | family/relational identifiers | `pattern_lexicon` | **sealed** |
| `2009 Suicide Attempt` (Vulnerability.description example) | vulnerability trigger | `pattern_lexicon` | **restricted** |
| `Mother's Suicide` (Vulnerability.description example) | deceased-relative ref + vulnerability | `pattern_lexicon` | **sealed** |
| `suicide_baiting` (CoerciveTactic.tactic_type) | tactic LABEL (generic) | `behavior_category` (ok) — but any *content* invoking the trauma → lexicon | n/a / restricted |

- **No child name appears** in the ontology. The child is referenced only by the structural role
  `child` / `Child` (Person.connection_to, EXPOSED_CHILD edge). Nothing child-identifying to seal here,
  but any downstream population of the `child` role MUST go to `pattern_lexicon sensitivity_tier='sealed'`.
- The illustrative names above are example values inside field `description=` strings, not a data roster.
  They are nonetheless personal identifiers and are listed as **sealed `pattern_lexicon` seed candidates**
  (§4). They are **NEVER** to be emitted as plaintext `detection_pattern`.
- All behavioral *categories/tactics* (the enum vocabularies) are generic → `behavior_category` /
  generic `detection_pattern` with `bias_caution=true`.

---

## 1. detection_pattern_set (ONE row — NOT the active one)

```
id               := uuidv7()
name             := 'zep_salem_ontology_v3'
version          := '3.0.0'                       -- "ZEP ONTOLOGY v3", cleaned 2025-12-11
source           := 'zep_salem_ontology_v3'
source_artifact  := 'extracted-code/ontologies-datasets/zep_salem_ontology_v3_final.py'
description      := 'Case-specific (Salem v. Kinzel) Zep/Graphiti forensic knowledge-graph ontology v3.
                    Entity/edge schema; behavioral taxonomy harvested from controlled-vocabulary enums.
                    Hypotheses; map to MCL 722.23. Case-specific — NOT the active generic detection set.'
is_active        := false        -- the single active set is G3 'dial_behavioral_ontology'; this is case-scoped
authored_perspective := 'protective-parent / forensic-analyst (petitioner-father perspective)'
```
UNIQUE(name,version) satisfied. **`is_active=false`** — the "ONE active set" invariant stays with the
generic G3 set; this case-specific set is registered inactive (or as an overlay), pending owner decision
in the reconciliation addendum. **Count: 1 (inactive).**

> Authored perspective is explicitly the petitioner/father's protective framing
> (`is_replacement_candidate`, `matt_abuse_narrative` as the *opposing* narrative, `strategic_goal` framed
> as respondent's manipulation). This is a one-sided forensic lens → all derived negative patterns get
> `bias_caution=true` and are HYPOTHESES.

---

## 2. behavior_category (from enum vocabularies)

polarity ∈ {negative, positive, neutral, linguistic_marker}; `default_severity` 0–10; `mcl_factor` a–l.
`source='zep_salem_ontology_v3'`, `is_case_specific=false` for the generic tactic categories
(`true` only where noted). **OVERLAP** column flags categories that duplicate a G3 `behavior_category`
(same PK should MERGE, not double-insert — add Zep terms as `aliases[]`).

| category_id | label | polarity | sev | mcl_factors | source field (enum) | OVERLAP vs G3 |
|---|---|---|---|---|---|---|
| intimidation | Intimidation / Threats | negative | 8 | {f,k} | CoerciveTactic.tactic_type=`intimidation`; Incident.event_type=`threat` | new (subsumes coercive_control) |
| isolation | Isolation | negative | 8 | {j,k} | CoerciveTactic.tactic_type=`isolation` | partial → G3 coercive_control/isolation |
| economic_sabotage | Economic Sabotage / Financial Coercion | negative | 7 | {c,k} | CoerciveTactic.tactic_type=`economic_sabotage`; financial_mode=`conditional_aid,sabotage,dependency_creation`; Incident.event_type=`financial_coercion` | new (G3 only had financial_control under coercive_control) |
| suicide_baiting | Suicide Baiting | negative | 10 | {f,g,k} | CoerciveTactic.tactic_type=`suicide_baiting` | **NEW** — trauma weaponization |
| triangulation | Triangulation | negative | 7 | {j,k} | CoerciveTactic.tactic_type=`triangulation`; Person.role_in_case=`flying_monkey` | **NEW** |
| smear_campaign | Smear Campaign / Rumor Spreading | negative | 8 | {f,j,k} | SpreadsRumor edge (intent=isolate/ruin_reputation/gain_sympathy/cover_tracks) | **NEW** |
| darvo | DARVO | negative | 9 | {f,j,k} | Statement.darvo_stage=`deny,attack,reverse_victim,reverse_offender` | **MERGE → G3 darvo** |
| projection | Projection | negative | 7 | {f,k} | Statement.deception_strategy=`projection` | partial → G3 blame_shifting |
| minimization | Minimization | negative | 6 | {f} | Statement.deception_strategy=`minimization`; Incident strategic framing | **MERGE → G3 minimizing** |
| fabrication | Fabrication / Fabricated Narrative | negative | 9 | {f,k} | Statement.deception_strategy=`fabrication`; topic_cluster (e.g. abuse_narrative, sobriety_claim, victim_stance, good_mother) | **NEW** (G3 had no fabrication category) |
| misdirection | Misdirection / Distraction | negative | 6 | {f} | Statement.deception_strategy=`misdirection`; Incident.strategic_goal=`distract_from_drug_use` | **NEW** |
| denial | Denial | negative | 6 | {f} | Statement.deception_strategy=`denial` | partial → G3 gaslighting/denial subcat |
| inconsistent_account | Inconsistent / Contradictory Account | neutral | 5 | {f} | Statement.inconsistency_flag, contradicts_evidence; CONTRADICTS edge (lie_detected/projection/hypocritical_standard) | partial → G3 gaslighting (contradiction signal) |
| manufactured_crisis | Manufactured / Staged Crisis | negative | 7 | {f,k} | Incident.is_manufactured + strategic_goal=`sabotage_work,prevent_exchange,garner_sympathy` | **NEW** |
| parental_alienation | Parental Alienation / Gatekeeping | negative | 9 | {a,i,j} | Facilitated.action=`blocked_access,disparaged_parent,refused_meds`; gatekeeping_subtype=`punitive,exclusionary,possessive` | **MERGE → G3 parental_alienation** |
| child_exposure | Exposure of Child to Harm | negative | 8 | {f,j,k} | ExposedTo edge (impact=regression/distress/sleep_issue/illness); Incident.event_type=`withholding,medical_neglect` | **NEW** |
| trauma_exploitation | Trauma / Vulnerability Exploitation | negative | 9 | {f,k} | Exploits edge (mechanism=triggering_ptsd,shaming,threat_of_recurrence) | **NEW** |
| substance_endangerment | Substance Use / Endangerment | negative | 8 | {c,g,k} | Incident.event_type=`substance_use,drunk_driving`; substances_involved; context_of_use=`lethal` | **NEW** (G3 factor g had no seeded category) |
| medical_neglect | Medical Neglect | negative | 8 | {c,g} | Incident.event_type=`medical_neglect`; Facilitated.action=`refused_meds` | **NEW** |

`is_case_specific=false` for all (these are generic behavioral labels). **Count: 19**
(of which ~4 MERGE into existing G3 PKs as alias enrichment; ~11 are genuinely NEW relative to G3,
chiefly the coercive-control sub-tactics, fabrication/manufactured-crisis, trauma-exploitation, and the
**substance / medical-neglect / child-exposure** lane the .ttl set never seeded).

---

## 3. detection_pattern (generic keyword sets only — NO regex in source)

The ontology has **no regex/phrase patterns**. The only `detection_pattern`-eligible content is the
generic enum vocabulary, recorded as `match_type='literal'` keyword sets so a downstream matcher can flag
the *tactic vocabulary* in narrative text. All rows: `bias_caution=true`, `is_case_specific=false`,
`is_active=false` (inherits the inactive set), `authored_perspective='forensic-analyst'`,
`source='zep_salem_ontology_v3'`, `score:=severity`. UNIQUE(pattern_set_id,category_id,match_type,pattern).

| category_id | subcategory | match_type | pattern (label) | keywords[] | sev | mcl_factors |
|---|---|---|---|---|---|---|
| darvo | darvo_stages | literal | darvo_stage_markers | {deny,attack,reverse victim,reverse offender} | 9 | {f,j,k} |
| economic_sabotage | financial_mode | literal | financial_coercion_modes | {conditional aid,sabotage,dependency creation,allowance,cut off} | 7 | {c,k} |
| triangulation | flying_monkey | literal | triangulation_roles | {flying monkey,triangulate,go-between,proxy} | 7 | {j,k} |
| smear_campaign | rumor_intent | literal | smear_intent | {ruin reputation,gain sympathy,cover tracks,isolate} | 8 | {f,j,k} |
| fabrication | topic_cluster | literal | fabricated_narrative_clusters | {abuse narrative,sobriety claim,victim stance,good mother} | 9 | {f,k} |
| misdirection | strategic_goal | literal | distraction_goals | {distract from drug use,sabotage work,garner sympathy} | 6 | {f} |
| parental_alienation | gatekeeping | literal | gatekeeping_actions | {blocked access,disparaged parent,refused meds,not allowed,won't let} | 9 | {a,i,j} |
| trauma_exploitation | mechanism | literal | exploitation_mechanisms | {triggering ptsd,shaming,threat of recurrence} | 9 | {f,k} |
| substance_endangerment | context_of_use | literal | substance_context | {maintenance,party,lethal,drunk driving,driving} | 8 | {c,g,k} |

> NOTE on `suicide_baiting`: the **tactic label** is generic and may seed a `behavior_category`, but its
> keyword vocabulary invokes self-harm/trauma content and is **NOT** emitted as a plaintext
> `detection_pattern`. Any concrete suicide-baiting phrasing → `pattern_lexicon`,
> `lexicon_type='vulnerability_trigger'`, `sensitivity_tier='restricted'`, `is_case_specific=true`.

**Count: 9 generic literal keyword sets.** (No regex; all `bias_caution=true`.) The substance/medical
vocabularies (`alcohol, amphetamines, cocaine, mdma, cannabis, poly_substance`) are recorded as keywords
on `substance_endangerment` (generic substance names, not personal identifiers → `detection_pattern` ok).

---

## 4. pattern_lexicon (case-specific — SEALED / RESTRICTED)

This is the **distinctive** contribution: G3 produced **0** lexicon rows; this case ontology produces the
sealed/restricted identifier + vulnerability seed. `pattern_set_id` = the §1 set. `is_case_specific=true`,
`match_type='literal'`. **All persons → sealed; vulnerabilities → restricted (deceased-relative → sealed).**

| lexicon_type | term | variants[] | relevance_signal | sev | mcl_factors | sensitivity_tier |
|---|---|---|---|---|---|---|
| personal_identifier | Matt | {petitioner,father} | case-principal (father) | — | {} | **sealed** |
| personal_identifier | Catrina | {respondent,mother} | case-principal (mother) | — | {} | **sealed** |
| personal_identifier | Dennis | {} | third-party associate | — | {} | **sealed** |
| relational_identifier | her_mother | {maternal grandmother} | rumor audience / triangulation node | — | {j} | **sealed** |
| vulnerability_trigger | 2009 suicide attempt | {} | targeted wound (Factor K/F) | 9 | {f,g,k} | **restricted** |
| vulnerability_trigger | mother's suicide | {deceased relative} | targeted wound + deceased-relative ref | 9 | {f,g,k} | **sealed** |

Notes:
- These six are the **illustrative values** present in the source's field `description=` strings; they are
  seeded as **candidates** flagged for owner confirmation against the real case roster. They prove the
  routing contract (named persons/trauma NEVER become plaintext `detection_pattern`).
- `child` role exists structurally with **no name** → nothing to seal yet, but the downstream `child`
  identifier MUST land here with `sensitivity_tier='sealed'`.
- `Vulnerability` entity categories (`past_trauma, insecurity, medical_history, family_loss`) are the
  generic taxonomy for this lexicon_type and are recorded as `lexicon_type='vulnerability_trigger'` class
  labels (restricted), distinct from the concrete trauma instances above.

**Count: 6 seed candidates (4 sealed identifiers + 2 vulnerabilities).**

---

## 5. behavior_category_mcl (category_id, factor_code, weight, is_critical, note)

PK(category_id,factor_code). `weight` reuses the G3/`mcl_722_23.ttl` scale (High/Critical/Medium);
`is_critical=true` for **j** and **k** (statute-critical). MCL factors are taken from the ontology's
explicit `mcl_factor` enum (`c,f,g,j,k`) plus the edge→factor comments (ExposedTo→F, Facilitated→J,
Exploits→K/F). Rows for MERGE categories defer to G3's existing mapping; only the **NEW** categories add rows.

| category_id | factor_code | weight | is_critical | note |
|---|---|---|---|---|
| intimidation | f | High | false | manipulation/threat → moral fitness |
| intimidation | k | Critical | true | intimidation = domestic violence evidence |
| isolation | j | Critical | true | isolation blocks other-parent relationship |
| isolation | k | Critical | true | isolation as coercive-control / DV |
| economic_sabotage | c | High | false | financial sabotage → provision capacity |
| economic_sabotage | k | Critical | true | economic abuse as DV pattern |
| suicide_baiting | f | High | false | weaponizing trauma → moral fitness |
| suicide_baiting | g | High | false | mental-health endangerment |
| suicide_baiting | k | Critical | true | suicide baiting = emotional abuse / DV |
| triangulation | j | Critical | true | flying-monkey proxies interfere w/ co-parenting |
| triangulation | k | Critical | true | triangulation as control pattern |
| smear_campaign | f | High | false | reputational lies → moral fitness |
| smear_campaign | j | Critical | true | smear isolates / alienates other parent |
| fabrication | f | High | false | fabricated narrative → moral fitness |
| fabrication | k | Critical | true | false-abuse claims as DV/control evidence |
| misdirection | f | High | false | distraction/deception → moral fitness |
| manufactured_crisis | f | High | false | staged crises → moral fitness |
| manufactured_crisis | k | Critical | true | manufactured crisis as control tactic |
| child_exposure | f | High | false | exposing child to harm → moral fitness |
| child_exposure | j | Critical | true | withholding/exposure interferes w/ relationship |
| child_exposure | k | Critical | true | child witnessing harm = DV factor |
| trauma_exploitation | f | High | false | exploiting wounds → moral fitness |
| trauma_exploitation | k | Critical | true | trauma weaponization = emotional abuse |
| substance_endangerment | c | High | false | endangerment undermines provision/care |
| substance_endangerment | g | High | false | substance abuse → physical/mental health (Factor G) |
| substance_endangerment | k | Critical | true | drunk-driving/endangerment as DV/safety |
| medical_neglect | c | High | false | neglect of medical care → provision capacity |
| medical_neglect | g | High | false | medical neglect → health factor |
| projection | f | High | false | projection → moral fitness (defer to G3 blame_shifting) |
| denial | f | High | false | denial → moral fitness (defer to G3 gaslighting) |
| inconsistent_account | f | High | false | contradiction signal → possible deception |

**Count: 31 rows** across the NEW + partial categories. Factor **G (mental & physical health)** is the
mapping this source uniquely lights up — the .ttl set (G3) mapped substance/health to factor g in the
*definitions* table but seeded **no behavior_category** for it; this ontology supplies the
`substance_endangerment` / `medical_neglect` / `suicide_baiting` categories that actually exercise factor g.

---

## 6. MCL linkage in the ontology (how it ties to MCL/behaviors)

- **Direct enum:** `Incident.mcl_factor` description = "Michigan Best Interest Factor: c, f, g, j, k" —
  the ontology hard-codes the 5 factors its events map to.
- **Edge→factor comments (authoritative intent):**
  - `ExposedTo` (EXPOSED_CHILD) → **Factor F (Moral Fitness)**.
  - `Facilitated` (AFFECTED_ACCESS) → **Factor J (Willingness to facilitate)**.
  - `Exploits` (TARGETED_WOUND) → **Factor K/F** (weaponization of trauma).
  - `Vulnerability` entity → **Factor K/F** ("Historical traumas Respondent targets").
- The ontology stays consistent with the **corrected** statutory meaning of j (facilitation) and k (DV) —
  i.e. it does NOT carry the G3 `.ttl` j/k `rdfs:label` swap bug; its comments use the right semantics.
- Factors **a, b, d, e, h, i, l** are NOT referenced by this ontology (it is event/incident-centric, not a
  full best-interest map). Factor **i** (child's preference) is added here only via the
  `parental_alienation` MERGE (coaching distorts preference), consistent with G3.

---

## 7. Overlap vs the G3 `.ttl` ontologies (net-new signal)

**Overlap / MERGE (same concept, enrich G3 PK with Zep `aliases[]`, do not double-seed):**
`darvo`, `minimizing`↔`minimization`, `parental_alienation`, `coercive_control`↔(`isolation`+`intimidation`),
`gaslighting`↔(`denial`+`inconsistent_account` contradiction signal), `blame_shifting`↔`projection`.

**NET-NEW behavioral content this source contributes (not in G3):**
1. **Coercive-control sub-tactics broken out** — `suicide_baiting`, `triangulation`, `economic_sabotage`,
   `intimidation` as first-class categories (G3 collapsed these into one `coercive_control`).
2. **`smear_campaign` / rumor-spreading** with intent+audience semantics (G3 had none).
3. **`fabrication` / fabricated-narrative + `manufactured_crisis` / `misdirection`** — staged-crisis and
   false-narrative lane absent from G3.
4. **`trauma_exploitation`** edge — explicit weaponization-of-vulnerability category + Factor K/F link.
5. **Substance / safety lane** — `substance_endangerment`, `medical_neglect`, `child_exposure` —
   exercising **MCL Factor G** which G3 defined but never seeded a category for.
6. **A populated `pattern_lexicon`** (sealed identifiers + restricted vulnerabilities) — G3 produced 0;
   this is the source that proves and seeds the court-safety sealing contract.
7. **Entity/edge graph schema** (Person/Location/Incident/Statement/Vulnerability + 8 typed edges) — this
   belongs in the **Zep/Graphiti lane**, not the relational analysis schema, and is recorded as context
   only (timeline/inconsistency/presence tracking: `WasAt`, `Contradicts`, `MadeStatement`).

**Structural divergence:** G3 is a generic regex pattern library (literal/regex `detection_pattern`-heavy,
lexicon-empty); G7 is a case-specific KG schema (taxonomy + sealed lexicon-heavy, pattern-text-empty).
They are **complementary**: G3 = the active generic detector; G7 = the case-scoped category/MCL/lexicon
overlay (inactive set) that extends the taxonomy into the coercive-control sub-tactics, fabrication,
trauma-exploitation, and substance/health (Factor G) lanes.
