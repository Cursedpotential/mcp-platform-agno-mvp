# G1 — Behavioral Pattern Seed Inventory: Analyzer APP

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Source extraction for `analysis` schema seed (detection_pattern_set / behavior_category /
> detection_pattern / pattern_lexicon / behavior_category_mcl). `source='analyzer-app'` on every row.

## Provenance

| Field | Value |
|---|---|
| Primary artifact | `behavior-sources/analyzer-app/app.py` (richest; 50+ regex, HurtLex, BERT, SpaCy) |
| Secondary | `behavior-sources/analyzer-app/app_local.py` (subset of same `ABUSE_PATTERNS` + local AI/ugrep) |
| Tooling-only | `text_miner.py` (ugrep CLI; timestamp regex only — no behavior patterns), `schema_resolver.py` (field-mapping heuristics — no behavior patterns) |
| Default case caption in code | `"Salem v. Kinzel"` (HARD-CODED → routed to sealed lexicon, see below) |
| Authored perspective | **one-party / documenting party** — patterns written to document the *opposing* party's conduct in a custody case. `bias_caution=true` on ALL negative detection_patterns; patterns are HYPOTHESES, not findings. |

### Scoring / risk methodology captured from source (for `notes`, not a table)
- `SEVERITY_WEIGHTS` = base severity per category (used below as both `severity` and `score`).
- Runtime severity boost: `+1` if BERT sentiment == negative; `+min(hurtlex_match_count,2)`; capped at 10.
- Risk roll-up: CRITICAL if avg≥7 or max≥9; HIGH if avg≥6 or max≥7; MODERATE if avg≥4; else LOW.
- Escalation index = `%` change of mean severity, first-half vs second-half of chronologically sorted timeline.
- These are aggregation rules, not patterns — recorded here for the reconciliation addendum only.

---

## TABLE 1 — `detection_pattern_set` (seed ONE active set)

| name | version | source | source_artifact | description | is_active | authored_perspective |
|---|---|---|---|---|---|---|
| `analyzer_app_coercive_control` | `1.0` | analyzer-app | `app.py` (+`app_local.py`) | Forensic coercive-control / verbal-abuse / manipulation regex set (6 top-level types, 14 categories, 67 patterns) ported from the Gradio Behavioral Pattern Analyzer | true | documenting_party |

---

## TABLE 2 — `behavior_category` (14 rows)

`category_polarity` ∈ {negative, positive, neutral, linguistic_marker}; `default_severity` from `SEVERITY_WEIGHTS`; `mcl_factors` = MCL 722.23 best-interest factor codes.

| category_id (snake_case) | label | polarity | default_severity | mcl_factors | aliases | is_case_specific | notes |
|---|---|---|---|---|---|---|---|
| `threats` | Threats / Intimidation | negative | 10 | {k,j} | {threat, intimidation} | false | parent type `verbal_abuse`; DV factor (k) primary |
| `child_weaponization` | Child Weaponization | negative | 9 | {j,k} | {child_weaponization, using_child} | false | parent `coercive_control`; literal child name in one regex → sealed lexicon |
| `monitoring_stalking` | Monitoring / Stalking | negative | 8 | {k,g} | {stalking, surveillance, monitoring} | false | parent `coercive_control` |
| `homophobic_slurs` | Homophobic Slurs | negative | 7 | {f,k} | {homophobic_slurs, anti_gay} | false | parent `verbal_abuse`; generic slur regex stays in detection_pattern |
| `isolation_tactics` | Isolation Tactics | negative | 7 | {j,k} | {isolation, isolating} | false | parent `coercive_control` |
| `gaslighting` | Gaslighting | negative | 7 | {k,g} | {gaslighting, reality_distortion} | false | top-level type (always-on in source) |
| `double_bind` | Double Bind | negative | 7 | {k,j} | {double_bind, contradictory_demand} | false | top-level type (always-on) |
| `character_attacks` | Character Attacks | negative | 6 | {f,k} | {character_attack, name_calling} | false | parent `verbal_abuse` |
| `financial_control` | Financial Control | negative | 6 | {c,k} | {financial_control, economic_abuse} | false | parent `coercive_control`; economic abuse = DV |
| `triangulation` | Triangulation | negative | 6 | {j,k} | {triangulation} | false | top-level type (always-on) |
| `communication_control` | Communication Control | negative | 5 | {j,k} | {communication_control, contact_blocking} | false | parent `coercive_control` |
| `substance_shaming` | Substance Shaming | negative | 5 | {f,g} | {substance_shaming, drug_shaming} | false | parent `verbal_abuse`; shaming language = speaker's moral fitness |
| `mental_health_stigma` | Mental Health Stigma | negative | 5 | {f,g} | {mental_health_stigma, crazy_making} | false | parent `verbal_abuse` |
| `love_bombing` | Love Bombing | negative | 4 | {j,k} | {love_bombing, intermittent_reinforcement} | false | **POLARITY HINT**: surface lexicon is *positive* ("love", "miss", "perfect") but functionally a manipulation/coercive-cycle tactic → category polarity = negative; flag for human review |

> Parent-type grouping in source: `coercive_control` = {child_weaponization, communication_control, financial_control, isolation_tactics, monitoring_stalking}; `verbal_abuse` = {homophobic_slurs, character_attacks, mental_health_stigma, substance_shaming, threats}; standalone top-level types = {gaslighting, love_bombing, triangulation, double_bind}. Store parent type in `detection_pattern.subcategory` or category `notes`.

### TABLE 2b — `behavior_category_mcl` (28 rows; primary+secondary per category)

| category_id | factor_code | weight | is_critical | note |
|---|---|---|---|---|
| threats | k | primary | true | domestic violence |
| threats | j | secondary | false | undermines co-parenting relationship |
| child_weaponization | j | primary | true | friendly-parent / facilitation of other-parent relationship |
| child_weaponization | k | secondary | false | coercive control via child |
| monitoring_stalking | k | primary | true | DV / surveillance |
| monitoring_stalking | g | secondary | false | mental health of party |
| homophobic_slurs | f | primary | false | moral fitness of speaker |
| homophobic_slurs | k | secondary | false | verbal abuse component of DV |
| isolation_tactics | j | primary | false | isolating from support/other parent |
| isolation_tactics | k | secondary | true | coercive control |
| gaslighting | k | primary | true | psychological/coercive control |
| gaslighting | g | secondary | false | targets victim mental state |
| double_bind | k | primary | true | coercive control |
| double_bind | j | secondary | false | undermines cooperation |
| character_attacks | f | primary | false | moral fitness of speaker |
| character_attacks | k | secondary | false | verbal abuse |
| financial_control | c | primary | false | capacity to provide material needs / support |
| financial_control | k | secondary | true | economic abuse = DV |
| triangulation | j | primary | false | weaponizes third parties vs. other parent |
| triangulation | k | secondary | false | coercive control |
| communication_control | j | primary | false | blocks contact / co-parenting |
| communication_control | k | secondary | false | coercive control |
| substance_shaming | f | primary | false | moral-fitness framing by speaker |
| substance_shaming | g | secondary | false | (alleged) physical/mental health of target |
| mental_health_stigma | f | primary | false | moral fitness of speaker |
| mental_health_stigma | g | secondary | false | targets mental health |
| love_bombing | j | primary | false | part of intermittent-reinforcement coercive cycle |
| love_bombing | k | secondary | false | coercive control |

---

## TABLE 3 — `detection_pattern` (67 rows; all `match_type=regex`, `is_case_specific=false`, `bias_caution=true`, `authored_perspective=documenting_party`, `source=analyzer-app`)

`severity` and `score` both take the category `default_severity`. `mcl_factors` mirror the category. Patterns preserved **verbatim** from source (Python raw-string regex, case-insensitive at runtime). `subcategory` = parent type.

### child_weaponization (subcategory `coercive_control`) — sev/score 9, mcl {j,k}
| # | pattern (verbatim) | note |
|---|---|---|
| 1 | `you('re| are)n('|o)?t (gonna |going to )?(see|have|get) (her\|him\|the kid\|<CHILD_NAME>)` | **SANITIZED**: source literal `kailah` REMOVED → routed to sealed lexicon (`child_identifier`). Stored regex uses `<CHILD_NAME>` placeholder; runtime expands from lexicon. |
| 2 | `(forget about\|don't expect to see) (her\|him\|the kid)` | |
| 3 | `if you (want to see\|wanna see) (her\|him)` | |
| 4 | `you don't deserve (her\|him\|to be a (father\|dad\|parent))` | |
| 5 | `(blocking you\|blocked).*?(from\|so you can't see) (her\|him)` | app.py only |

### communication_control (subcategory `coercive_control`) — sev/score 5, mcl {j,k}
| # | pattern | note |
|---|---|---|
| 1 | `(blocked\|blocking) you` | |
| 2 | `don't (text\|call\|contact) me` | |
| 3 | `leave me (alone\|the fuck alone)` | |
| 4 | `lose my number` | |
| 5 | `never (talk\|speak) to me again` | app.py only |

### financial_control (subcategory `coercive_control`) — sev/score 6, mcl {c,k}
| # | pattern | note |
|---|---|---|
| 1 | `you (owe\|need to pay\|better pay) me` | |
| 2 | `where'?s? (the\|my) money` | |
| 3 | `pay (me\|for\|child support)` | |
| 4 | `(don't\|won't) give you (shit\|anything\|a dime)` | app.py only |

### isolation_tactics (subcategory `coercive_control`) — sev/score 7, mcl {j,k}
| # | pattern | note |
|---|---|---|
| 1 | `(everyone\|everybody\|people) (knows\|think\|say) you'?re` | |
| 2 | `told (everyone\|everybody\|them) (about\|what) you` | |
| 3 | `nobody (likes\|wants\|trusts) you` | |
| 4 | `your (family\|friends) (knows\|know) (what\|who) you are` | app.py only |

### monitoring_stalking (subcategory `coercive_control`) — sev/score 8, mcl {k,g}
| # | pattern | note |
|---|---|---|
| 1 | `i know (where you\|what you\|who you)` | |
| 2 | `i('m\| am) watching you` | |
| 3 | `i saw you (at\|with)` | |
| 4 | `someone told me you` | app.py only |

### homophobic_slurs (subcategory `verbal_abuse`) — sev/score 7, mcl {f,k}
| # | pattern | note |
|---|---|---|
| 1 | `\bf+a+g+([og]+(e\|o)?t\|it)\b` | generic slur regex (not a personal identifier) → stays in detection_pattern |
| 2 | `\bgay\b.*?\b(ass\|bitch\|fuck)` | |
| 3 | `\bqueer\b` | app.py only |

### character_attacks (subcategory `verbal_abuse`) — sev/score 6, mcl {f,k}
| # | pattern | note |
|---|---|---|
| 1 | `piece of (shit\|trash\|garbage)` | |
| 2 | `\b(motherfucker\|mother fucker)\b` | |
| 3 | `bitch (made\|ass)` | app.py only |
| 4 | `\bpussy\b` | app.py only |
| 5 | `good for nothing` | app.py only |
| 6 | `worthless` | |
| 7 | `pathetic` | |
| 8 | `loser` | |

### mental_health_stigma (subcategory `verbal_abuse`) — sev/score 5, mcl {f,g}
| # | pattern | note |
|---|---|---|
| 1 | `\b(psycho\|crazy\|insane\|mental\|nuts)\b` | |
| 2 | `\b(sick\|twisted\|fucked up) (in the head\|mentally)` | app.py only |
| 3 | `need (help\|therapy\|meds\|medication)` | |
| 4 | `\bweirdo\b` | app.py only |

### substance_shaming (subcategory `verbal_abuse`) — sev/score 5, mcl {f,g}
| # | pattern | note |
|---|---|---|
| 1 | `\b(crackhead\|crack head\|tweaker\|junkie\|addict)\b` | |
| 2 | `\bhigh (as fuck\|af\|again)\b` | |
| 3 | `on (that shit\|drugs\|dope)` | app.py only |

### threats (subcategory `verbal_abuse`) — sev/score 10, mcl {k,j}
| # | pattern | note |
|---|---|---|
| 1 | `(i'll\|i will\|gonna) (fuck you up\|beat\|kill\|hurt\|destroy)` | |
| 2 | `watch your back` | |
| 3 | `you('re\| are) (gonna\|going to) regret` | |
| 4 | `better watch out` | app.py only |
| 5 | `i('ll\| will) make you` | app.py only |

### gaslighting (top-level) — sev/score 7, mcl {k,g}
| # | pattern | note |
|---|---|---|
| 1 | `that never happened` | |
| 2 | `you'?re (crazy\|imagining\|making (it\|this\|that) up)` | |
| 3 | `i never said that` | |
| 4 | `you'?re (being\|too) (dramatic\|sensitive\|emotional)` | |
| 5 | `you always (exaggerate\|overreact\|blow things out of proportion)` | app.py only |
| 6 | `that'?s not (what\|how) (it\|that) happened` | app.py only |
| 7 | `you'?re (twisting\|changing\|distorting) (my words\|what i said\|the story)` | app.py only |
| 8 | `you know that'?s not true` | app.py only |

### love_bombing (top-level) — sev/score 4, mcl {j,k} — **polarity hint: surface-positive lexicon**
| # | pattern | note |
|---|---|---|
| 1 | `i love you so much` | |
| 2 | `you'?re (the best\|amazing\|perfect\|everything to me)` | |
| 3 | `i can'?t live without you` | |
| 4 | `you'?re (the only one\|all i (want\|need))` | app.py only |
| 5 | `i miss you (so much\|baby)` | app.py only |
| 6 | `come (over\|here).*?(i need you\|baby\|please)` | app.py only |

### triangulation (top-level) — sev/score 6, mcl {j,k}
| # | pattern | note |
|---|---|---|
| 1 | `(everyone\|people\|they) (think\|say\|know) you'?re` | |
| 2 | `i told (them\|everyone\|her\|him) about you` | |
| 3 | `(he\|she\|they) (said\|told me\|thinks) you'?re` | app.py only |
| 4 | `my (friend\|mom\|family).*?(doesn't like\|hates\|thinks) you` | app.py only |
| 5 | `(unlike you\|at least\|he\|she).*(treats me\|is there for me\|cares)` | app.py only |

### double_bind (top-level) — sev/score 7, mcl {k,j}
| # | pattern | note |
|---|---|---|
| 1 | `if you (loved\|cared about) me.*?you (would\|wouldn't)` | |
| 2 | `you say.*?but you (don't\|never\|won't)` | |
| 3 | `(come over\|see me).*?(leave me alone\|don't contact)` | app.py only |

---

## TABLE 4 — `pattern_lexicon` (32 rows; `source=analyzer-app`, `pattern_set_id`→the seed set)

### 4a. Court-safety SEALED identifiers (`is_case_specific=true`, `sensitivity_tier=sealed`) — NEVER plaintext in detection_pattern
| term | variants | lexicon_type | match_type | relevance_signal | severity | mcl_factors | note |
|---|---|---|---|---|---|---|---|
| `kailah` | {kailah} | child_identifier | literal | child name extracted from `child_weaponization` regex #1 in app.py | 9 | {j,k} | the child; redacted out of detection_pattern → `<CHILD_NAME>` placeholder |
| `Salem` | {salem} | party_identifier | literal | hard-coded default case caption `Salem v. Kinzel` (documenting party / user surname) | — | {} | caption metadata; sealed |
| `Kinzel` | {kinzel} | party_identifier | literal | hard-coded default case caption `Salem v. Kinzel` (opposing party) | — | {} | caption metadata; sealed |

### 4b. Sentiment cue lexicons (SpaCy `analyze_with_spacy`; generic, `is_case_specific=false`, `sensitivity_tier=public`)
| term | lexicon_type | match_type | relevance_signal | polarity hint |
|---|---|---|---|---|
| `hate` | sentiment_cue_negative | literal | SpaCy negative_words set | negative / linguistic_marker |
| `angry` | sentiment_cue_negative | literal | SpaCy negative_words set | negative |
| `fuck` | sentiment_cue_negative | literal | SpaCy negative_words set | negative |
| `shit` | sentiment_cue_negative | literal | SpaCy negative_words set | negative |
| `kill` | sentiment_cue_negative | literal | SpaCy negative_words set | negative |
| `hurt` | sentiment_cue_negative | literal | SpaCy negative_words set | negative |
| `destroy` | sentiment_cue_negative | literal | SpaCy negative_words set | negative |
| `love` | sentiment_cue_positive | literal | SpaCy positive_words set | positive |
| `miss` | sentiment_cue_positive | literal | SpaCy positive_words set | positive |
| `please` | sentiment_cue_positive | literal | SpaCy positive_words set | positive |
| `sorry` | sentiment_cue_positive | literal | SpaCy positive_words set | positive |
| `want` | sentiment_cue_positive | literal | SpaCy positive_words set | positive |
| `need` | sentiment_cue_positive | literal | SpaCy positive_words set | positive |

### 4c. HurtLex hate-speech category taxonomy (16 rows; `lexicon_type=hurtlex_category`, `sensitivity_tier=restricted`, `is_case_specific=false`)
> NOTE: individual HurtLex terms (3000+ EN lemmas, conservative+inclusive levels) are loaded at runtime from the external AGPL dataset `hurtlex_EN.tsv` (v1.2) — **not present in source code**, so only the category taxonomy is seeded here. `match_type=literal` (lemma membership). Polarity negative.
| term (category code → label) | relevance_signal |
|---|---|
| `ps` → ethnic_slurs | negative stereotypes / ethnic slurs |
| `rci` → locations | geographic/origin slurs |
| `pa` → professions | profession-based insult |
| `ddf` → physical_disabilities | ableist (physical) |
| `dmc` → cognitive_disabilities | ableist (cognitive) |
| `is` → social_economic | class/economic slur |
| `or` → plants | dehumanizing (plant) |
| `an` → animals | dehumanizing (animal) |
| `asm` → male_sexuality | sexual slur (male) |
| `asf` → female_sexuality | sexual slur (female) |
| `pr` → prostitution | prostitution slur |
| `om` → moral_behavioral | moral/behavioral insult |
| `qas` → generic_insults | generic insult |
| `cds` → derogatory_words | derogatory |
| `re` → criminal | criminal framing |
| `svp` → social_political | social/political slur |

---

## Routing decisions applied (court-safety, hard rule)
1. `kailah` (child name in `child_weaponization` regex #1) → **REMOVED** from detection_pattern, stored as `pattern_lexicon` `child_identifier`, `sensitivity_tier=sealed`, `is_case_specific=true`. detection_pattern regex now carries `<CHILD_NAME>` placeholder.
2. Hard-coded case caption `Salem v. Kinzel` → `Salem` + `Kinzel` to `pattern_lexicon` `party_identifier`, `sealed`. Never seeded as detection text.
3. Generic slurs (fag/gay/queer/crackhead/etc.) and all manipulation phrases → remain in `detection_pattern` (generic hypotheses, not personal identifiers).
4. Every negative `detection_pattern`: `bias_caution=true`, `authored_perspective=documenting_party`. Patterns are HYPOTHESES; the source app is one-party advocacy tooling.
5. HurtLex terms intentionally NOT enumerated (external AGPL dataset, restricted tier) — taxonomy only.
