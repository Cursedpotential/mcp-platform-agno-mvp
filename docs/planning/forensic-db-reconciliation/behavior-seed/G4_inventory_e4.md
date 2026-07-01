# G4 — Behavior-Detection Seed (E4 → live `analysis` schema)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
>
> Consolidates the canonical category list + documented `detection_patterns.py` (S9, Part 4 of
> `COMPLETE_SCHEMA_PARSER_INVENTORY.md`) and the E4 ontology extract
> (`extracted/E4_behavioral_ontology.md`) into seed rows for the **live** `analysis`-schema tables:
> `detection_pattern_set`, `behavior_category`, `behavior_category_mcl`, `detection_pattern`,
> `pattern_lexicon`. This file is the human-readable seed spec; the SQL blocks are copy-ready.

## 0. Court-safety routing applied (HARD)

1. **Patterns are HYPOTHESES, not facts.** Every negative `detection_pattern` row carries
   `bias_caution = true`. `severity`/`score` are triage priority, never legal weight.
2. **Generic manipulation phrases/regex → `detection_pattern`.**
3. **ANY child name / personal-family identifier / deceased-relative ref / derogatory personal
   epithet / case-specific place → `pattern_lexicon`** with `sensitivity_tier='sealed'`,
   `is_case_specific=true`. NEVER as plaintext in `detection_pattern`.
   - S9 regexes that embedded the child name (`…see (?:her|kailah)`) are **genericized** here —
     the literal name lives only in the sealed `child_identifier` lexicon.
4. **Single source-of-truth set, `is_active=true`.** Authored from one party's perspective →
   `authored_perspective='single_party_complainant'` on the set and on every pattern; must be run
   symmetrically on all parties before any use.
5. Enum literals only: `category_polarity` = negative|positive|neutral|linguistic_marker ·
   `pattern_match_type` = literal|regex · `mcl_factor` = a–l (lowercase; MCL 722.23 A–L) ·
   `sensitivity_tier` = public|restricted|sealed.
6. **J↔K is canonical (statute):** `j` = willingness to facilitate the child's relationship with the
   other parent; `k` = domestic violence. S3/S6 had these swapped — do NOT import their letter tags
   without remap (see E4 §6.2).

---

## 1. `detection_pattern_set` — seed ONE active set

```sql
INSERT INTO analysis.detection_pattern_set
  (name, version, source, source_artifact, description, is_active, authored_perspective, valid_from)
VALUES
  ('casebible_custody_v1', '1.0.0',
   'E4 consolidation (S1 behavioral_patterns.ttl, S4 seed-patterns.ts, S5 behavioral-pattern-analyzer.html, S9 detection_patterns.py)',
   'COMPLETE_SCHEMA_PARSER_INVENTORY.md#part-4 + extracted/E4_behavioral_ontology.md',
   'Canonical 18-category custody manipulation/abuse taxonomy + documented regex/keyword detection rules. Single-party authored; bias_caution on all negative patterns; case-specific identifiers sealed in pattern_lexicon. Patterns are hypotheses for attorney review, not findings.',
   true, 'single_party_complainant', now());
-- UNIQUE(name, version). All FKs below reference this set via name='casebible_custody_v1'.
```

---

## 2. `behavior_category` — 18 canonical + extended

`mcl_factors` are canonical lowercase a–l. The **core 18** (S9 `behavior_categories`) are negative.
`love_bombing` is dual-polarity (manipulation tactic that *also* surfaces as a positive contradiction
anchor) — seeded once as `negative` with `aliases` and a note; its positive face is detected via the
`detectContradictions` pass, not a separate row. Extended rows (positive/neutral/linguistic) give the
polarity enum full coverage.

```sql
-- category_id (snake_case PK) | label | polarity | default_severity 0-10 | mcl_factors | aliases | case_specific
INSERT INTO analysis.behavior_category
 (category_id, label, description, polarity, default_severity, mcl_factors, aliases, is_case_specific, source, notes) VALUES
-- ===== CORE 18 (negative) =====
('gaslighting','Reality distortion / denial','Denying events, calling the other party crazy/imagining; "no one will believe you".','negative',8,'{a,f,k}','{}',false,'S1,S4,S5,S6,S9',NULL),
('blame_shifting','Deflecting responsibility onto the victim','"Your fault / you made me / because of you".','negative',8,'{f,j,k}','{}',false,'S1,S4,S6,S9',NULL),
('minimizing','Downplaying concerns/feelings','"Not a big deal / calm down / overreacting / just a joke".','negative',6,'{f,j}','{}',false,'S1,S4,S6,S9',NULL),
('love_bombing','Excessive flattery / premature devotion','Manipulation tactic; dual-polarity contradiction anchor when paired with later devaluation.','negative',6,'{a,f}','{lovebomb}',false,'S1,S2,S4,S5,S6,S9','Dual-polarity: positive face tracked via contradiction detection, not exoneration.'),
('stonewalling','Silent treatment / refusal to communicate','"Conversation is over / talk to my lawyer / i''m done / whatever".','negative',7,'{f,k}','{}',false,'S6,S9',NULL),
('parental_alienation','Damaging the child–parent bond','Badmouthing the other parent, interference, coaching the child.','negative',10,'{a,i,j,k}','{alienation}',false,'S1,S4,S6,S8,S9',NULL),
('coercive_control','Pattern of domination/restriction','Isolation, monitoring, financial restriction, compliance demands.','negative',10,'{c,j,k}','{}',false,'S1,S5,S9',NULL),
('financial_abuse','Economic abuse / weaponized money','"You owe me / where''s my money / won''t give you a dime".','negative',8,'{c,j}','{financial_control,financial_weaponized}',false,'S4,S5,S6,S9',NULL),
('substance_weaponization','Using substance use as a weapon/label','"Crackhead / tweaker / junkie / this is the drugs talking".','negative',9,'{b,f,g,k}','{substance_weaponized}',false,'S4,S9',NULL),
('reactive_abuse','Provoked reaction reframed as the victim''s aggression','Speaker-attribution-dependent; only meaningful once author is fixed.','negative',8,'{f,j,k}','{}',false,'S9',NULL),
('darvo','Deny · Attack · Reverse Victim & Offender','3-phase sequence detected within message or 3–5 msg window.','negative',10,'{f,j,k}','{darvo_deny,darvo_attack,darvo_reverse}',false,'S1,S4,S5,S6,S9',NULL),
('character_assassination','Degradation / slurs / epithets','"Piece of shit / worthless / pathetic" + identity-based slurs.','negative',9,'{b,f,k}','{character_attack,character_attacks}',false,'S5,S9','Identity-based slurs routed to sealed lexicon, not plaintext here.'),
('isolation','Cutting off support systems','"Nobody likes you / your family knows what you are / told everyone".','negative',9,'{j,k}','{isolation_tactics}',false,'S1,S5,S6,S9',NULL),
('hoovering','Pulling the victim back after discard','Re-engagement after devaluation/no-contact.','negative',6,'{a,f}','{}',false,'S9',NULL),
('triangulation','Third parties used to pressure/shame','"Everyone thinks / he/she said / unlike you, they care".','negative',6,'{f,j}','{}',false,'S5,S9',NULL),
('parenting_time','Visitation / handoff interference','Blocking calls/visits, denying parenting time.','negative',9,'{j,k}','{}',false,'S8,S9',NULL),
('gatekeeping','Blocking contact/information access','"Blocked / stop texting / you don''t need to know".','negative',8,'{j}','{}',false,'S9',NULL),
('special_needs','Child special-needs (autism/sensory) handling','Relevance + fitness signal; generic terms only (no personal vulnerability data).','negative',8,'{a,c,l}','{}',false,'S9','Generic clinical terms = relevance; personal vulnerability triggers go to sealed lexicon.'),
-- ===== EXTENDED negatives (S4/S5 build) =====
('medical_abuse','Diagnosis/medication weaponized for control','"Holding your meds / you need to be hospitalized / you''re bipolar".','negative',9,'{f,g,j}','{medical}',false,'S4,S9',NULL),
('reproductive_coercion','Coercion re: pregnancy/birth control','"Stop taking birth control / you''ll never see the baby / i''ll prove you''re unfit".','negative',10,'{j,k,l}','{}',false,'S4',NULL),
('threats_intimidation','Threats of harm/retaliation','"I''ll fuck you up / watch your back / you''ll regret".','negative',10,'{j,k}','{threats}',false,'S5',NULL),
('sexual_shaming','Sexual degradation','"Slut / whore / freak / disgusting".','negative',9,'{b,f,k}','{}',false,'S4',NULL),
-- ===== POSITIVE (dual-polarity contradiction anchors, S2/S6) =====
('affirmations','Praise + emotional validation','ExplicitPraise, EmotionalValidation — tracked for contradiction over time.','positive',2,'{a}','{affirmation}',false,'S2,S6',NULL),
('future_faking','Grandiose unfulfilled promises','FuturePromise / FinancialAssurance; "i''ll change / things will be different".','positive',3,'{l}','{expectation_setting}',false,'S2,S6',NULL),
('apologies','Apology / remorse','Sincerity tracked via apology→repeat cycle detection.','positive',2,'{l}','{}',false,'S2,S6',NULL),
('gift_giving','Material generosity','Tracked as leverage/dependency signal when paired with control.','positive',2,'{c}','{}',false,'S4,S6',NULL),
('cooperation','Genuine co-parenting baseline','InformationSharing + Flexibility — the good-faith contrast class.','positive',1,'{a,b,d}','{}',false,'S2',NULL),
('dependency_cultivation','"Savior" reliance-building','Rescuing / "you need me / you can''t trust anyone but me".','positive',5,'{}','{savior_complex,rescuing}',false,'S2,S4,S6','Positive-surface but manipulative; overlaps savior_complex.'),
-- ===== NEUTRAL / context (S6) =====
('power_asymmetry','Victim-deference vs abuser-directive dynamics','Pronoun/deference split; meaningful only with speaker attribution.','neutral',0,'{j,l}','{}',false,'S6',NULL),
('scheduling','Custody schedule / visitation logistics','Neutral logistics context.','neutral',0,'{a,b,d}','{}',false,'S6',NULL),
('child_wellbeing','Child health/education/emotional mentions','Relevance/context signal.','neutral',0,'{a,b,e,g}','{}',false,'S6',NULL),
('overelaboration','Excessive location/time detail (deception marker)','Statistical marker; neutral corpus feature, not misconduct.','neutral',0,'{l}','{}',false,'S1,S4,S6',NULL),
-- ===== LINGUISTIC markers (severity 0, S4/S6) =====
('certainty_absolutes','Certainty/absolute lexicon','always/never/everyone/obviously — corpus statistical marker only.','linguistic_marker',0,'{}','{}',false,'S4,S6','Guardrail #7: severity 0 = neutral marker, not benign misconduct.'),
('hedge_words','Hedge lexicon','maybe/perhaps/i think/probably — corpus statistical marker only.','linguistic_marker',0,'{}','{}',false,'S4,S6','Severity 0 statistical marker.');
```

---

## 3. `behavior_category_mcl` — per-category factor weights

`is_critical=true` only for statutory **critical** factors j (facilitation) and k (domestic violence)
where that factor is the dominant one for the category. PK(category_id, factor_code).

```sql
INSERT INTO analysis.behavior_category_mcl (category_id, factor_code, weight, is_critical, note) VALUES
('gaslighting','a','medium',false,NULL),('gaslighting','f','high',false,'moral fitness'),('gaslighting','k','high',true,'DV pattern'),
('blame_shifting','f','high',false,NULL),('blame_shifting','j','medium',true,NULL),('blame_shifting','k','medium',true,NULL),
('minimizing','f','high',false,NULL),('minimizing','j','low',false,NULL),
('love_bombing','a','medium',false,NULL),('love_bombing','f','medium',false,NULL),
('stonewalling','f','medium',false,NULL),('stonewalling','k','medium',true,NULL),
('parental_alienation','a','high',false,NULL),('parental_alienation','i','medium',false,'child preference'),('parental_alienation','j','high',true,'core J pattern'),('parental_alienation','k','high',true,NULL),
('coercive_control','c','high',false,NULL),('coercive_control','j','high',true,NULL),('coercive_control','k','high',true,'core DV pattern'),
('financial_abuse','c','high',false,NULL),('financial_abuse','j','medium',true,NULL),
('substance_weaponization','b','medium',false,NULL),('substance_weaponization','f','high',false,NULL),('substance_weaponization','g','high',false,'health'),('substance_weaponization','k','high',true,NULL),
('reactive_abuse','f','medium',false,NULL),('reactive_abuse','j','medium',true,NULL),('reactive_abuse','k','medium',true,NULL),
('darvo','f','high',false,NULL),('darvo','j','high',true,NULL),('darvo','k','high',true,NULL),
('character_assassination','b','medium',false,NULL),('character_assassination','f','high',false,NULL),('character_assassination','k','medium',true,NULL),
('isolation','j','high',true,NULL),('isolation','k','high',true,NULL),
('hoovering','a','medium',false,NULL),('hoovering','f','medium',false,NULL),
('triangulation','f','medium',false,NULL),('triangulation','j','medium',true,NULL),
('parenting_time','j','high',true,'core J pattern'),('parenting_time','k','medium',true,NULL),
('gatekeeping','j','high',true,'core J pattern'),
('special_needs','a','high',false,NULL),('special_needs','c','high',false,'medical care'),('special_needs','l','medium',false,NULL),
('medical_abuse','f','medium',false,NULL),('medical_abuse','g','high',false,NULL),('medical_abuse','j','medium',true,NULL),
('reproductive_coercion','j','high',true,NULL),('reproductive_coercion','k','high',true,NULL),('reproductive_coercion','l','medium',false,NULL),
('threats_intimidation','j','medium',true,NULL),('threats_intimidation','k','high',true,'core DV'),
('sexual_shaming','b','medium',false,NULL),('sexual_shaming','f','high',false,NULL),('sexual_shaming','k','medium',true,NULL);
```

---

## 4. `detection_pattern` — documented generic regex rules

All rows `pattern_set_id` = casebible_custody_v1, `authored_perspective='single_party_complainant'`,
`is_active=true`, `is_case_specific=false`, and (all negative) `bias_caution=true`. Child names removed
from regexes (genericized to `her|him|the kid`); the name match is the sealed lexicon's job.
`UNIQUE(pattern_set_id, category_id, match_type, pattern)`.

### 4a. S9 `detection_patterns.py` scored rules (custody `score` 1–10)

```sql
-- category_id | subcategory | match_type | pattern | severity | score | mcl_factors | source
INSERT INTO analysis.detection_pattern
 (pattern_set_id, category_id, subcategory, match_type, pattern, severity, score, mcl_factors, description, is_case_specific, authored_perspective, bias_caution, source, is_active)
SELECT id, v.* FROM analysis.detection_pattern_set s,
(VALUES
 ('parenting_time','parenting_time_001','regex','you\s+(?:won''t|can''t)\s+see\s+(?:her|him|the\s+kid)',9,9,'{j}'::mcl_factor[],'Threat to deny visitation (child name genericized → sealed lexicon).',false,'single_party_complainant',true,'S9'),
 ('parenting_time','parenting_time_002','regex','if\s+you\s+don''t.*(?:her|him|daughter|son)',8,8,'{j,k}'::mcl_factor[],'Conditional visitation threat.',false,'single_party_complainant',true,'S9'),
 ('parental_alienation','alienation_001','regex','dad(?:dy)?\s+(?:is|doesn''t|won''t)|mom(?:my)?\s+(?:is|doesn''t|won''t)',10,10,'{j,k}'::mcl_factor[],'Badmouthing the other parent to the child (J/K canonical; S9 listed K,D).',false,'single_party_complainant',true,'S9'),
 ('parental_alienation','alienation_002','regex','who\s+do\s+you\s+want\s+to\s+(?:stay|live)\s+with',10,10,'{i,j}'::mcl_factor[],'Coaching child preference (J/I canonical; S9 listed K,D).',false,'single_party_complainant',true,'S9'),
 ('medical_abuse','medical_001','regex','doctor|hospital|sick|medicine',8,8,'{a,j}'::mcl_factor[],'Medical-context relevance signal.',false,'single_party_complainant',true,'S9'),
 ('medical_abuse','medical_002','regex','you\s+don''t\s+need\s+to\s+know',9,9,'{j}'::mcl_factor[],'Withholding medical info (gatekeeping overlap).',false,'single_party_complainant',true,'S9'),
 ('character_assassination','character_attack_001','regex','drug(?:s)?|high|using|addict',9,9,'{b,f,k}'::mcl_factor[],'Substance-based character attack.',false,'single_party_complainant',true,'S9'),
 ('gatekeeping','gatekeeping_001','regex','block(?:ed|ing)?|stop\s+(?:texting|calling)',8,8,'{j}'::mcl_factor[],'Blocking contact.',false,'single_party_complainant',true,'S9'),
 ('coercive_control','coercive_control_001','regex','comply|do\s+what\s+I\s+(?:say|tell)',9,9,'{k}'::mcl_factor[],'Compliance demand.',false,'single_party_complainant',true,'S9'),
 ('coercive_control','coercive_control_002','regex','if\s+you\s+don''t|unless\s+you|or\s+else',8,8,'{k}'::mcl_factor[],'Conditional threat / ultimatum.',false,'single_party_complainant',true,'S9'),
 ('special_needs','special_needs_001','regex','autism|autistic|spectrum|sensory|meltdown',8,8,'{a,l}'::mcl_factor[],'Special-needs relevance (generic clinical terms).',false,'single_party_complainant',true,'S9')
) AS v(category_id, subcategory, match_type, pattern, severity, score, mcl_factors, description, is_case_specific, authored_perspective, bias_caution, source)
WHERE s.name='casebible_custody_v1';
```

### 4b. S1 `behavioral_patterns.ttl` regexes (severity → score mirrored)

`gaslighting.denial|imagined|no_one_believe`, `blame.your_fault|look_what_you`,
`minimizing.not_big_deal|calm_down`, `darvo.deny`(→darvo)/`darvo.reverse`(→darvo, child-protection
phrasing kept generic), `lovebomb.perfect|forever|give_everything`,
`coercive.isolation|financial|monitoring`, `alienation.badmouth|interference`, `overelab.just_left`.
Load verbatim from E4 §3.1 (17 rows) as `match_type='regex'`, `bias_caution=true`,
`mcl_factors` per the canonical map. **Do not retype by hand — bulk-load from S1.**

### 4c. S5 `ABUSE_PATTERNS` anchored regexes (S5 `SEVERITY_WEIGHTS` authoritative for this app)

Load E4 §3.2 modules as `detection_pattern` rows:
`coercive_control.child_weaponization`(9)→category coercive_control (**name `kailah` stripped** from
`/…(see|have|get) (her|him|the kid)/i`), `.communication_control`(5), `.financial_control`(6)→
financial_abuse, `.isolation_tactics`(7)→isolation, `.monitoring_stalking`(8)→coercive_control,
`verbal_abuse.character_attacks`(6)/`.mental_health_stigma`(5)/`.substance_shaming`(5)→
character_assassination/substance_weaponization, `verbal_abuse.threats`(10)→threats_intimidation,
`gaslighting`(7), `love_bombing`(4), `triangulation`(6), `double_bind`(7)→coercive_control.
`verbal_abuse.homophobic_slurs`(7): the slur regex is a **generic identity-slur regex** → keep in
detection_pattern (category character_assassination), but any *named-target* epithet → sealed lexicon.

### 4d. S4 `seed-patterns.ts` literal lexicon (308 rows / 26 categories)

`match_type='literal'`, one row per phrase, `severity` per entry, mapped to canonical `category_id`
via the §2 `aliases`. **Bulk-load all 308 from S4** (E4 §3.4); do not hand-retype. Severity-0
entries (`substance_alcohol`, `certainty_absolutes`, `hedge_words`, `infidelity_places`) seed under
the `linguistic_marker`/neutral categories. **Exception (routing):** `infidelity_places`
("huckleberry junction/huck''s/hucks"), the child names in `parental_alienation`
("kailah"/"kyla"/"my daughter"), and named slurs do **NOT** load as literal detection_pattern rows —
they route to `pattern_lexicon` §5.

---

## 5. `pattern_lexicon` — sealed case-specific identifiers (NEVER in detection_pattern)

```sql
INSERT INTO analysis.pattern_lexicon
 (pattern_set_id, lexicon_type, term, variants, match_type, relevance_signal, severity, mcl_factors, is_case_specific, sensitivity_tier, source)
SELECT s.id, v.* FROM analysis.detection_pattern_set s,
(VALUES
 -- child identifiers (relevance, NOT abuse) — sealed
 ('child_identifier','kailah','{kyla,kaila,kailuh}'::text[],'regex','child_mention',0,'{a}'::mcl_factor[],true,'sealed','S8,S9'),
 -- derogatory child epithet — sealed
 ('vulnerability_trigger','little shit','{}'::text[],'literal','derogatory_child_reference',7,'{f,k}'::mcl_factor[],true,'sealed','S9'),
 -- case-specific place (alleged infidelity location) — corroboration marker, severity 0, sealed
 ('vulnerability_trigger','huckleberry junction','{huck''s,hucks}'::text[],'literal','location_corroboration',0,'{f}'::mcl_factor[],true,'sealed','S4')
) AS v(lexicon_type, term, variants, match_type, relevance_signal, severity, mcl_factors, is_case_specific, sensitivity_tier, source)
WHERE s.name='casebible_custody_v1';

-- Generic kinship references = relevance only (NOT names) → restricted, not case-specific
INSERT INTO analysis.pattern_lexicon
 (pattern_set_id, lexicon_type, term, variants, match_type, relevance_signal, severity, mcl_factors, is_case_specific, sensitivity_tier, source)
SELECT s.id, 'child_reference', t, '{}'::text[], 'literal', 'child_mention', 8, '{a}'::mcl_factor[], false, 'restricted', 'S9'
FROM analysis.detection_pattern_set s,
 unnest(ARRAY['my daughter','our daughter','your daughter','the baby','the kid','the child','our child','my kid','my child']) t
WHERE s.name='casebible_custody_v1';
```

Vulnerability terms that are **generic clinical vocabulary** (`autism, sensory, meltdown, bipolar,
borderline, episode, hospitalized, meds, adderall, script`) stay as generic `detection_pattern`
rows (§4a `special_needs_001`, §4d `medical_abuse`/`adderall_control`) at `sensitivity_tier`
default — they are not personal identifiers. Only the user's/child's *named* personal/medical/place
identifiers are sealed above.

---

## 6. Open reconciliation items (carry-forward)

- **J↔K remap** before importing any S3/S6-letter-tagged data (E4 §6.2) — blocking for court use.
- **De-dup** identical phrases across S1(regex)/S4(literal)/S5(regex)/S6(substring) by
  (category, normalized_text, position).
- **Full-file recovery:** S9 names `detection_patterns.py` (320+ lines) as SSOT but only 11 scored
  rules + 9 child-name patterns were captured in the inventory; locate full file and merge.
- **Symmetry:** run on all parties before producing any aggregate; current lexicon is single-party.
