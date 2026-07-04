# G3 — Turtle Ontology Extraction → analysis schema seed

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
> Source artifacts: `dev-resources/Archives/dial-stack/ontologies/behavioral_patterns.ttl`,
> `positive_behaviors.ttl`, `mcl_722_23.ttl`
> Target: live `analysis` schema (`detection_pattern_set`, `behavior_category`,
> `detection_pattern`, `pattern_lexicon`, `behavior_category_mcl`).
> **Patterns are HYPOTHESES, not facts.** Every negative `detection_pattern` carries `bias_caution=true`.

---

## 0. Court-safety routing result

Scanned all three TTLs for child names, the user's personal/family identifiers, deceased-relative
references, and derogatory personal epithets. **None present** — every pattern in `behavioral_patterns.ttl`
is a *generic* manipulation regex/phrase (e.g. `your (father|mother|dad|mom)` is a generic relationship
token, not a named individual). Therefore:

- **`pattern_lexicon` seed = 0 rows.** No `child_identifier` / `vulnerability_trigger` terms exist in
  these ontologies. The lexicon table is left empty here and is to be populated downstream from
  case-specific material with `sensitivity_tier='sealed'`, `is_case_specific=true`.
- All extracted patterns are routed to `detection_pattern` (generic) only.

## 0b. Source-data caveat — MCL J/K label swap

`mcl_722_23.ttl` has **mislabeled `rdfs:label` on FactorJ and FactorK** (the `rdfs:comment` and
`mcl:factorCode` are authoritative; the human label is wrong):

| code | TTL `rdfs:label` (WRONG) | Authoritative `rdfs:comment` / statute (CORRECT) |
|------|--------------------------|--------------------------------------------------|
| j | "Domestic Violence" | willingness/ability to **facilitate & encourage** the other parent's relationship |
| k | "Parental Cooperation" | any evidence of **domestic violence** |

The `mcl_factor` enum keys off the **code (a–l)**, so mappings below use the statutory meaning, not the
swapped TTL label. Flagged for the reconciliation addendum.

---

## 1. detection_pattern_set (seed ONE active set)

```
id               := uuidv7()
name             := 'dial_behavioral_ontology'
version          := '1.0.0'                     -- from owl:versionInfo of behavioral_patterns ontology
source           := 'dial-stack ontologies'
source_artifact  := 'behavioral_patterns.ttl + positive_behaviors.ttl + mcl_722_23.ttl'
description      := 'Manipulation / abuse / coercive-control + positive-behavior detection set extracted
                     from the Michigan custody DIAL behavioral ontologies (v1.0.0, 2026-03-04). Patterns
                     are hypotheses; map to MCL 722.23 best-interest factors.'
is_active        := true
authored_perspective := 'protective-parent / forensic-analyst (DIAL ontology authoring perspective)'
valid_from       := now()
```
UNIQUE(name,version) satisfied. **Count: 1.**

---

## 2. behavior_category  (category_id snake_case PK)

polarity ∈ {negative, positive, neutral, linguistic_marker}. `default_severity` = rounded midpoint of the
TTL `mcl:severityRange`. `mcl_factors` from each category's `mcl:mapsToMCLFactor` (by code).

| category_id | label | polarity | default_severity | mcl_factors | source class | notes |
|---|---|---|---|---|---|---|
| gaslighting | Gaslighting | negative | 8 | {a,f,k} | bp:GaslightingCategory | range 6-10; patternCount 19 |
| blame_shifting | Blame Shifting | negative | 7 | {f,k} | bp:BlameShiftingCategory | range 5-9; patternCount 42 |
| minimizing | Minimizing | negative | 6 | {f,k} | bp:MinimizingCategory | range 4-7; patternCount 32 |
| darvo | DARVO | negative | 9 | {f,j,k} | bp:DARVOCategory | "Deny, Attack, Reverse Victim & Offender"; range 7-10; patternCount 28 |
| love_bombing | Love Bombing | positive | 5 | {a,f} | bp:LoveBombingCategory | surface-positive but **manipulation-flagged**: "Excessive positive behavior can be manipulation tactic"; range 4-6 |
| coercive_control | Coercive Control | negative | 9 | {c,j,k} | bp:CoerciveControlCategory | range 8-10; patternCount 35 |
| parental_alienation | Parental Alienation | negative | 9 | {a,i,j} | bp:ParentalAlienationCategory | range 8-10; patternCount 22 |
| overelaboration | Overelaboration | neutral | 4 | {f} | bp:OverelaborationCategory | direct subclass of BehavioralPattern; "Excessive explanation can indicate deception"; range 3-5 |
| affirmation | Affirmation | positive | 4 | {a,f} | bpos:Affirmation | positive-behavior taxonomy; "Love Bombing seed" — praise + emotional validation |
| expectation_setting | Expectation Setting | positive | 4 | {a,c} | bpos:ExpectationSetting | "Future Faking & Expectation Setting" — future promise + financial assurance |
| cooperation | Cooperative Behavior | positive | 0 | {b,j} | bpos:Cooperation | genuine co-parenting baseline — info sharing + flexibility |
| dependency_cultivation | Dependency Cultivation | positive | 4 | {f} | bpos:DependencyCultivation | "Savior complex" — rescuing to build reliance |

`source` column for all rows := `'behavioral_patterns.ttl/positive_behaviors.ttl'`. `is_case_specific=false`,
`aliases='{}'` unless noted. **Count: 12** (8 negative/neutral/love-bombing + 4 positive-taxonomy).

### Positive-behavior taxonomy detail (positive_behaviors.ttl leaves → category notes)

These 6 leaves carry no regex/keywords in the TTL (label+comment only); they are recorded as
sub-taxonomy on their parent `behavior_category`, NOT as `detection_pattern` rows (no pattern text exists):

- **affirmation** → `ExplicitPraise` ("Direct compliments re character, parenting, capabilities"),
  `EmotionalValidation` ("Acknowledging the other party's feelings as valid").
- **expectation_setting** → `FuturePromise` ("Grandiose/concrete promises re future living, finances, harmony"),
  `FinancialAssurance` ("Promises to provide, support, cover costs").
- **cooperation** → `InformationSharing` ("Proactively sharing medical/educational/scheduling info"),
  `Flexibility` ("Agreeing to reasonable schedule changes without leveraging them").
- **dependency_cultivation** → `Rescuing` ("Solving a problem the other party could solve, building reliance").

---

## 3. detection_pattern  (generic regex only — all match_type='regex')

UNIQUE(pattern_set_id,category_id,match_type,pattern). `pattern_set_id` = the set from §1.
All negative-polarity rows: `bias_caution=true`, `is_case_specific=false`, `is_active=true`,
`authored_perspective='forensic-analyst'`, `source='behavioral_patterns.ttl'`. `score` defaulted to `severity`.

| category_id | subcategory | pattern (regex) | severity/score | mcl_factors | source class |
|---|---|---|---|---|---|
| gaslighting | denial | `(?i)(i never\|would never\|did not\|didn't\|never happened)` | 8 | {f} | bp:Denial |
| gaslighting | imagined | `(?i)(imagined\|imagining\|made up\|in your head\|crazy\|insane\|delusional)` | 9 | {f,k} | bp:Imagined |
| gaslighting | no_one_believe | `(?i)(no one\|nobody\|will believe\|won't believe\|no one will)` | 10 | {a,k} | bp:NoOneBelieve |
| blame_shifting | your_fault | `(?i)(your fault\|you made me\|because of you\|you're the reason)` | 8 | {f} | bp:YourFault |
| blame_shifting | look_what_you | `(?i)(look what you\|see what you\|this is your\|you caused)` | 7 | {f} | bp:LookWhatYou |
| minimizing | not_big_deal | `(?i)(not a big deal\|no big deal\|not big deal\|making a big\|overreacting)` | 6 | {f} | bp:NotBigDeal |
| minimizing | calm_down | `(?i)(calm down\|you need to calm\|just calm\|relax\|settle down)` | 5 | {f} | bp:CalmDown |
| darvo | darvo_deny | `(?i)(i never\|would never\|that never\|didn't happen\|not true)` | 7 | {f} | bp:DARVODeny |
| darvo | darvo_reverse | `(?i)(protect.*from you\|you're the\|victim\|abuser\|i need)` | 10 | {f,k} | bp:DARVOReverse |
| love_bombing | perfect | `(?i)(perfect\|amazing\|wonderful\|incredible\|soulmate)` | 4 | {a} | bp:Perfect |
| love_bombing | forever | `(?i)(forever\|always\|eternal\|never leave\|always be)` | 5 | {a} | bp:Forever |
| love_bombing | give_everything | `(?i)(give.*everything\|all i have\|do anything\|sacrifice)` | 6 | {a,f} | bp:GiveEverything |
| coercive_control | isolation | `(?i)(isolat\|alone\|no friends\|can't see\|don't need)` | 9 | {j,k} | bp:Isolation |
| coercive_control | financial_control | `(?i)(money\|finances\|budget\|allowance\|spend\|account)` | 8 | {c} | bp:FinancialControl |
| coercive_control | monitoring | `(?i)(track\|monitor\|check\|where are\|who are\|location)` | 8 | {j,k} | bp:Monitoring |
| parental_alienation | bad_mouth_parent | `(?i)(your (father\|mother\|dad\|mom)\|bad (father\|mother)\|doesn't love)` | 10 | {a,j} | bp:BadMouthParent |
| parental_alienation | interference | `(?i)(can't see\|not allowed\|refuse\|won't let\|preventing)` | 9 | {j} | bp:Interference |
| overelaboration | just_left | `(?i)(just (left\|happened\|went)\|before you\|had to)` | 4 | {f} | bp:JustLeft |

bias_caution note: `love_bombing` rows are surface-positive but are manipulation hypotheses →
`bias_caution=true` set on them as well. `overelaboration` (neutral) likewise `bias_caution=true`.
**Count: 18.** (Positive-taxonomy leaves yield no detection_pattern rows — no pattern text in source.)

`keywords[]` per row = the TTL `mcl:exampleWords` list (carried verbatim as the literal keyword array;
e.g. gaslighting/denial keywords = {'i never','would never','did not','didn''t','never happened'}).

---

## 4. pattern_lexicon

**0 rows.** No child identifiers / personal / deceased-relative / epithet terms exist in the source
ontologies (see §0). Reserved for downstream case-specific seeding (`sensitivity_tier='sealed'`,
`is_case_specific=true`, `lexicon_type ∈ {child_identifier, vulnerability_trigger}`).

---

## 5. behavior_category_mcl  (category_id, factor_code, weight, is_critical, note)

PK(category_id,factor_code). `weight` = the MCL factor's statutory weight from `mcl_722_23.ttl`
(`mcl:weight`). `is_critical=true` for factors j & k (TTL `mcl:weight "Critical"`).

| category_id | factor_code | weight | is_critical | note |
|---|---|---|---|---|
| gaslighting | a | High | false | gaslighting erodes emotional ties |
| gaslighting | f | High | false | dishonesty/manipulation → moral fitness |
| gaslighting | k | Critical | true | reality-distortion as emotional-abuse evidence |
| blame_shifting | f | High | false | manipulation → moral fitness |
| blame_shifting | k | Critical | true | abuse-pattern marker |
| minimizing | f | High | false | dishonesty → moral fitness |
| minimizing | k | Critical | true | minimizing abuse |
| darvo | f | High | false | manipulation → moral fitness |
| darvo | j | Critical | true | reversal interferes w/ co-parenting facilitation |
| darvo | k | Critical | true | DARVO as abuse-pattern evidence |
| love_bombing | a | High | false | excessive affection display |
| love_bombing | f | High | false | manipulation-tactic caveat |
| coercive_control | c | High | false | financial control → provision capacity |
| coercive_control | j | Critical | true | isolation/monitoring interferes w/ relationship |
| coercive_control | k | Critical | true | coercive control = domestic violence |
| parental_alienation | a | High | false | damages emotional ties |
| parental_alienation | i | Medium | false | coaching distorts child's preference |
| parental_alienation | j | Critical | true | core interference w/ other parent |
| overelaboration | f | High | false | possible deception → moral fitness |
| affirmation | a | High | false | (inferred) praise/validation ↔ emotional ties; love-bombing seed |
| affirmation | f | High | false | (inferred) flagged when weaponized |
| expectation_setting | a | High | false | (inferred) future-faking ↔ emotional ties |
| expectation_setting | c | High | false | (inferred) financial assurance ↔ provision capacity |
| cooperation | b | High | false | (inferred) guidance/continuity baseline |
| cooperation | j | Critical | true | (inferred) genuine facilitation of other-parent relationship |
| dependency_cultivation | f | High | false | (inferred) savior-complex manipulation → moral fitness |

Rows marked **(inferred)** are not explicit `mcl:mapsToMCLFactor` triples in the TTL (positive_behaviors.ttl
carries no MCL links); they are reasoned from the parent category's manipulation/factor semantics and
flagged for review. The 8 negative/neutral/love-bombing categories' mappings are **explicit** from
`bp:*Category mcl:mapsToMCLFactor`. **Count: 26** (19 explicit + 7 inferred-positive).

---

## 6. MCL 722.23 best-interest factor definitions (a–l) — from mcl_722_23.ttl

| code | weight | factor (corrected statutory meaning) | rdfs:comment (TTL) | mapped behavioral patterns (TTL) |
|---|---|---|---|---|
| a | High | Love & emotional ties | love, affection, other emotional ties between parties and child | love_bombing, emotional_withholding, parental_alienation |
| b | High | Capacity to give love & guidance | capacity/disposition to give love, affection, guidance; education, culture, religion | cultural_manipulation, religious_coercion |
| c | High | Capacity to provide for needs | capacity to provide food, clothing, medical/remedial care | financial_neglect, medical_neglect |
| d | Medium | Length of residence / continuity | time child has lived in a stable, satisfactory environment; continuity | frequent_moves, unstable_living |
| e | Medium | Permanence of family unit/home | permanence of existing/proposed custodial home(s) | housing_instability |
| f | High | Moral fitness | moral fitness of the parties | gaslighting, manipulation, coercive_control, DARVO, pathological_lying |
| g | High | Mental & physical health | mental and physical health of the parties | mental_health_issues, substance_abuse, narcissistic_traits, borderline_traits |
| h | Medium | Home, school & community record | home, school, community record of the child | — |
| i | Medium | Child's reasonable preference | reasonable preference of the child if of sufficient age | parental_alienation, coaching_child |
| j | Critical | Willingness to facilitate other-parent relationship | willingness/ability to facilitate & encourage a close, continuing parent–child relationship with the other parent | domestic_violence, parental_alienation, interference |
| k | Critical | Domestic violence | any evidence of domestic violence, whether or not directed at / witnessed by the child | domestic_violence, physical_abuse, emotional_abuse, control_patterns, isolation |
| l | Variable | Any other relevant factor | any other factor the court considers relevant to the particular dispute | — |

> NOTE: TTL `rdfs:label` for j ("Domestic Violence") and k ("Parental Cooperation") are SWAPPED relative to
> their own `rdfs:comment` and the statute; the table above uses the corrected meaning keyed to `factorCode`.

TTL severity-band reference (`mcl:numericValue`): Low=1, Medium=5, High=8, Critical=10.
