# G5 — agno-alpha classifiers: net-new extraction

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
> `source = 'agno-alpha-classifier'` for every row below.
> Scope: net-new vs the same-worktree `server/scripts/seed-patterns.ts` (the 200+ literal seed already covers
> gaslighting, blame_shifting, minimizing, circular, darvo_*, overelaboration, love_bombing, excessive_gratitude,
> debt_reminders, savior_complex, substance_alcohol, substance_weaponized, adderall_control, infidelity,
> financial_weaponized, sexual_shaming, parental_alienation, medical_abuse, reproductive_coercion,
> victim_deference, abuser_directives, certainty_absolutes, hedge_words). Only deltas are recorded here.

Sources read:
- `.../migration-plan-v8/server/mcp/analysis/classifier.ts` (LLM classifier — pattern taxonomy + scale)
- `.../migration-plan-v8/server/mcp/analysis/multi-pass-classifier.ts` (6-pass NLP + scoring formulas)
- `.../migration-plan-v8/server/mcp/analysis/nlp-classifier.ts` (NLP-only scoring formulas)
- `.../migration-plan-v8/server/mcp/analysis/priority-screener.ts` (Pass-0; imported by multi-pass — regex + MCL links)

---

## A. detection_pattern_set (seed ONE active set)

| name | version | source | source_artifact | authored_perspective | description |
|---|---|---|---|---|---|
| `agno-alpha-classifier` | `v8-migration` | agno-alpha-classifier | `server/mcp/analysis/{classifier,multi-pass-classifier,nlp-classifier,priority-screener}.ts` | petitioner | Behavioral taxonomy + scoring logic harvested from the alpha multi-pass classifier subsystem. |

`is_active=true`. All negative `detection_pattern` rows under this set carry `bias_caution=true`; patterns are HYPOTHESES, not findings.

---

## B. behavior_category — NET-NEW categories (not present as seed categories)

snake_case `category_id` / `polarity` / `default_severity` (0-10) / `mcl_factors` / `aliases`.
From `classifier.ts` `NEGATIVE_PATTERNS` / `POSITIVE_PATTERNS` arrays + screener flag types.

### Negative (polarity=negative)
| category_id | default_severity | mcl_factors | aliases | notes |
|---|---|---|---|---|
| `manipulation` | 7 | (l) | controlling_through_deception | alpha umbrella term; broader than gaslighting/darvo |
| `intimidation` | 8 | (k) | threats_aggression | "threats, aggressive language" |
| `threats` | 8 | (k) | explicit_threat, implicit_threat | distinct from intimidation; harm threats |
| `isolation` | 7 | (j),(l) | cutting_off_support | "cutting victim off from support" — coercive-control lane |
| `financial_control` | 7 | (c),(l) | financial_abuse | restricting access to money/resources — NOTE: seed `financial_weaponized` is *verbal* effort/contribution attacks; this is *access restriction*, keep separate |
| `denial` | 7 | (l) | refusing_to_acknowledge | broader than seed `darvo_deny`; "refusing to acknowledge wrongdoing" |
| `stalking` | 8 | (g),(k) | monitoring, surveillance | "unwanted monitoring or following" |
| `coordinated_abuse` | 8 | (j),(k),(l) | multi_party_targeting | "multiple people targeting victim" |
| `smear_campaign` | 7 | (f),(j) | reputational_attack, defamation | "spreading false information" |
| `silent_treatment` | 6 | (j),(l) | stonewalling, withholding_communication | "withholding communication as punishment" |
| `triangulation` | 7 | (j),(l) | third_party_manipulation | "using third parties to manipulate" |

### Positive (polarity=positive) — kept for later *contradiction* analysis
| category_id | default_severity | mcl_factors | aliases | notes |
|---|---|---|---|---|
| `affirmations` | 0 | (l) | positive_statements | benign-on-surface; reclassifiable |
| `reassurances` | 0 | (l) | trust_assertion | examples below → keywords |
| `promises` | 0 | (l) | commitment_to_change, future_commitment | |
| `declarations_of_loyalty` | 0 | (l) | loyalty_declaration | examples below → keywords |
| `expressions_of_care` | 0 | (l) | concern_for_wellbeing | |
| `future_planning` | 0 | (l) | long_term_plans | "marriage, children" |
| `compliments` | 0 | (l) | praise | appearance/personality praise |
| `gift_giving` | 0 | (l) | gestures_of_affection | |

> `apologies` (positive) overlaps seed `victim_deference` apology phrases — fold as alias, do not duplicate.
> `love_bombing` already seeded — skip.

### Linguistic markers (polarity=linguistic_marker, default_severity=0) — NET-NEW lexicons
Seed already has `certainty_absolutes` + `hedge_words`. These two are new:
| category_id | aliases | notes |
|---|---|---|
| `negation_markers` | negation | drives gaslighting/sarcasm scoring |
| `intensity_modifiers` | intensifiers | severity amplifier |

(Also surfaced but lighter: `imperative_markers`, `question_markers` — see §E feature detectors.)

### Custody/alienation FINE-GRAINED categories (from priority-screener; finer than seed `parental_alienation`)
| category_id | polarity | default_severity | mcl_factors (CORRECTED — see §F caution) | notes |
|---|---|---|---|---|
| `communication_blocking` | negative | 9 | (j) | call blocking / refusing to answer |
| `visit_blocking` | negative | 9 | (j) | visit denial / won't bring child |
| `parenting_time_denial` | negative | 8 | (j) | schedule interference, "not your weekend" |
| `custody_interference` | negative | 9 | (j),(k) | hiding/keeping child, "my child now", police/RO weaponization |
| `child_reference` | neutral | 5 | (i) | generic child mention (routes to lexicon if it's a NAME — see §D) |

---

## C. detection_pattern — NET-NEW patterns (generic; all negative rows `bias_caution=true`)

### C1. Positive-pattern example phrases (literal) from `classifier.ts` system prompt
| category_id | match_type | pattern | keywords | severity | score |
|---|---|---|---|---|---|
| reassurances | literal | `i'd never lie` | {i'd never lie, i would never lie} | 0 | 3 |
| reassurances | literal | `you can trust me` | {you can trust me, trust me} | 0 | 3 |
| reassurances | literal | `i'm faithful` | {i'm faithful, i am faithful} | 0 | 3 |
| declarations_of_loyalty | literal | `you're my everything` | {you're my everything} | 0 | 3 |
| declarations_of_loyalty | literal | `i only love you` | {i only love you} | 0 | 3 |

(Severity 0 = benign surface; `score` reserved for the contradiction-meta phase, where these flip to love-bombing/manipulation evidence — see §E reclassification logic.)

### C2. Custody-interference REGEX (from priority-screener) — generic only, child-name alternations STRIPPED to lexicon
All `match_type=regex`, `is_case_specific=false`, `bias_caution=true`, mcl_factors per §B-corrected.
Child-name branches (`kailah|kyla`) removed from each source regex and rehomed in §D.

| category_id | pattern (regex, child-names stripped) | severity |
|---|---|---|
| communication_blocking | `\bblock(ed\|ing)?\s+(your\|his\|the)?\s*call` | 9 |
| communication_blocking | `\bcan'?t\s+call` | 8 |
| communication_blocking | `\bwon'?t\s+(let\|allow)\s+(you\|him)\s+call` | 9 |
| communication_blocking | `\bno\s+phone\s+(calls?\|contact)` | 9 |
| communication_blocking | `\bstop\s+calling` | 8 |
| communication_blocking | `\bignor(e\|ed\|ing)\s+(your\|his\|the)?\s*call` | 8 |
| communication_blocking | `\brefus(e\|ed\|ing)\s+to\s+answer` | 8 |
| visit_blocking | `\bblock(ed\|ing)?\s+(your\|his\|the)?\s*visit` | 9 |
| visit_blocking | `\bcan'?t\s+see\s+(her\|him)` | 9 |
| visit_blocking | `\bwon'?t\s+(let\|allow)\s+(you\|him)\s+(see\|visit)` | 9 |
| visit_blocking | `\bno\s+visitation` | 9 |
| visit_blocking | `\bcancel(ed\|ing)?\s+(your\|his\|the)?\s*(visit\|time)` | 8 |
| visit_blocking | `\bdenied?\s+(your\|his)?\s*(visit\|time\|access)` | 9 |
| visit_blocking | `\bkeep(ing)?\s+(her\|him)\s+from` | 9 |
| visit_blocking | `\bwon'?t\s+bring\s+(her\|him)` | 9 |
| visit_blocking | `\brefus(e\|ed\|ing)\s+to\s+(bring\|drop\s+off)` | 9 |
| parenting_time_denial | `\bno\s+parenting\s+time` | 8 |
| parenting_time_denial | `\bdenied?\s+parenting\s+time` | 8 |
| parenting_time_denial | `\binterfere?\s+with\s+(your\|his)\s+time` | 8 |
| parenting_time_denial | `\bnot\s+(your\|his)\s+weekend` | 8 |
| parenting_time_denial | `\bchanged?\s+(the\|our)\s+schedule` | 7 |
| custody_interference | `\bhide?\s+(her\|him\|the\s+child)` | 9 |
| custody_interference | `\bmy\s+child\s+now` | 9 |
| custody_interference | `\bnot\s+(your\|his)\s+(daughter\|child\|kid)` | 9 |
| custody_interference | `\bstay\s+away\s+from` | 8 |
| custody_interference | `\bno\s+contact` | 8 |
| custody_interference | `\brestraining\s+order` | 9 |
| custody_interference | `\bcall(ed\|ing)?\s+(the\s+)?police` | 8 |

### C3. Generic child-reference phrases (NOT names — safe as detection_pattern)
| category_id | match_type | pattern | severity |
|---|---|---|---|
| child_reference | literal | `my daughter` | 5 |
| child_reference | literal | `our daughter` | 5 |
| child_reference | literal | `the baby` | 4 |
| child_reference | literal | `our child` | 5 |
| child_reference | literal | `my kid` | 4 |

---

## D. pattern_lexicon — SEALED (court-safety routing)

`sensitivity_tier='sealed'`, `is_case_specific=true`. Child NAMES + variants pulled out of the
priority-screener `child_name` regex group and out of the C2 regexes. NEVER store these as plaintext
detection_pattern. `lexicon_type='child_identifier'`.

| lexicon_type | term | variants | match_type | relevance_signal | mcl_factors |
|---|---|---|---|---|---|
| child_identifier | (child given name) | {kailah, kyla, kaila, kailuh} | regex | child_subject_of_proceeding | (i) |

> `kaila` = common spelling variant; `kailuh` = noted in source as a voice-recognition/transcription variant.
> Any other personal/family identifiers, deceased-relative references, or derogatory epithets encountered in
> the corpus follow the same routing (`lexicon_type='vulnerability_trigger'` for the latter).

---

## E. Scoring / severity / scale logic (NET-NEW — no analogue in seed-patterns)

This is the meat the literal seed lacks. Capture as `behavior_category_mcl` weights + processing notes.

**E1. 5-level sentiment scale (all three classifiers):** `positive | neutral | negative | hostile | abusive`.
Seed has no sentiment axis. `hostile`/`abusive` are escalation tiers of negative, decided by negative-pattern count.

**E2. classifier.ts severity bands (LLM):** 1-3 minor/normal conflict · 4-6 concerning/potential manipulation ·
7-8 clear abuse · 9-10 severe/immediate concern. High-severity threshold = `>=7`.

**E3. multi-pass severity formula:** start 5; `+0.8` per negative pattern; polarity `< -0.5 → +2`,
`< -0.2 → +1`; sarcasm `+1.5`; **negation + positive polarity → +1 (gaslighting indicator)**; clamp `<=10`;
then `max(computed, priority.immediate_severity)`.

**E4. multi-pass sentiment escalation:** negative_pattern_count `>=5 → abusive`, `>=3 → hostile`, else `negative`.

**E5. nlp-classifier severity formula:** no neg patterns → `1`; else `avg(neg.severity)` `+ min(count*0.5, 3)`, clamp `<=10`.
Sentiment escalation here uses `>5 → abusive`, `>2 → hostile`.

**E6. Sarcasm heuristic (multi-pass Pass 4):** `subjectivity > 0.7` AND negative-pattern present AND
`polarity > 0.2` ⇒ `sarcasm_detected=true` (+1.5 severity). Polarity averaged across VADER + TextBlob.

**E7. Confidence formulas:** multi-pass `= passes_completed/6 (+0.2 if pattern↔sentiment agree)`;
nlp `= avg( min(totalMatches*0.1, 0.9), sentiment.confidence )`.

**E8. Positive→manipulative RECLASSIFICATION (key forensic logic):** surface-positive patterns
(love_bombing, reassurances, declarations_of_loyalty…) are flagged at severity 0 but flip to manipulation
evidence in meta-analysis when contradicted by later conduct (e.g. "I'm faithful" Day-1 vs infidelity Day-3).
This is why the positive categories in §B exist. Store the latent weight in `detection_pattern.score` (1-10),
distinct from surface `severity`.

**E9. Pass-0 priority override:** any custody/alienation/communication-blocking flag forces `immediate_severity 8-10`
and bypasses normal scoring (priority screener).

**E10. 6-pass NLP pipeline (provenance, not a row):** spaCy (entities/attribution) → NLTK-VADER
(sentiment/negation) → pattern-analyzer (custom+MCL) → TextBlob (polarity/subjectivity/sarcasm) →
sentence-transformers (semantic similarity) → keyword extraction. Multi-tool *consensus* sentiment by majority vote.

---

## F. MCL mapping — CORRECTION CAUTION (must not copy alpha verbatim)

The alpha `priority-screener.ts` uses an **idiosyncratic, INCORRECT** MCL letter mapping that does NOT match
MCL 722.23 best-interest factors. Do not import its letters literally:

| alpha code says | alpha letter | CORRECT MCL 722.23 letter | canonical meaning |
|---|---|---|---|
| "Child's wishes" | `a` | **`i`** | reasonable preference of the child |
| "Willingness to facilitate relationship" | `k` | **`j`** | willingness to facilitate/encourage close parent-child relationship |
| domestic-violence flavored interference | (unused) | **`k`** | domestic violence |

All §B/§C mcl_factors above are stated in **corrected** canonical form. The `behavior_category_mcl` rows
should therefore tie alienation/blocking categories to factor **`j`** (`is_critical=true`, weight `high`),
add **`k`** where DV/threats co-occur, and child-preference/`child_reference` to **`i`**.

---

## G. behavior_category_mcl — suggested rows (corrected)
| category_id | factor_code | weight | is_critical | note |
|---|---|---|---|---|
| communication_blocking | j | high | true | call blocking impairs other-parent contact |
| visit_blocking | j | high | true | visit denial |
| parenting_time_denial | j | high | true | schedule interference |
| custody_interference | j | high | true | hiding/withholding child |
| custody_interference | k | high | true | police/RO weaponization, DV overlap |
| child_reference | i | medium | false | child preference lane |
| isolation | j | medium | false | severs support incl. co-parent |
| coordinated_abuse | k | high | true | multi-party targeting |
| stalking | k | high | true | surveillance/DV |
| smear_campaign | f | medium | false | moral-fitness lane |
