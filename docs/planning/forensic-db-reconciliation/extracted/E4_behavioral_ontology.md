# E4 — Behavioral-Analysis Ontology & Pattern-Detection Catalog (Extracted)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Extraction lane **E4** of the forensic-DB reconciliation. This document consolidates the
> **behavioral-analysis mini-app**: the custom abuse/manipulation taxonomy, the detection
> pattern catalog (regex / keyword / severity / score / MCL mapping), the child-name &
> vulnerability keyword lists, the positive-behavior ontology, and how every pattern maps to
> the Michigan MCL 722.23 best-interest factors.

---

## 0. COURT-SAFE GUARDRAILS (read first — applies to everything below)

These are the single most important framing constraints for this entire lane.

1. **Detection ≠ proof.** Every match produced by these patterns is a **hypothesis** — a flag
   that a human analyst/attorney must read in full context and either adopt or discard. A regex
   firing on "you're crazy" is *not* a finding of gaslighting; it is a pointer to a message to
   read. Treat all `severity`/`score` numbers as **triage priority**, not as legal weight.
2. **No automated legal conclusions.** The system must never emit "Party X committed coercive
   control / parental alienation." It may only surface *candidate evidence* tagged by category
   and MCL factor for attorney review (MRE 702 / admissibility is a downstream human decision).
3. **Author/speaker attribution is required before interpretation.** A pattern in an *inbound*
   message means the opposite of the same pattern *outbound*. Many patterns (DARVO-reverse,
   `victim_deference`) only make sense once "who said it" is fixed (see Pass 1 / speaker
   attribution). Counts without attribution are meaningless.
4. **Dual-polarity by design.** Positive patterns (love-bombing, affirmations, apologies) are
   tracked *to detect contradiction over time*, not to exonerate. "I love you" + later
   devaluation/cheating evidence is the signal — never the positive statement alone.
5. **Case-specific terms are DATA, not code.** Child names (Kailah/Kyla), local place names
   (Huckleberry Junction), and party-specific slurs are kept in **config tables** (lexicons),
   loadable/editable without touching the engine. They are reproduced below faithfully because
   they are the user's curated lexicon (~200 hrs of manual curation), but they belong in a
   `behavioral_patterns` / `lexicon` table, never hardcoded into the analyzer.
6. **Bias caution.** This lexicon was authored from one party's perspective for one custody
   matter. It is *adversarially shaped* (e.g. `parental_alienation` keywords assume a particular
   narrative). Any production use must (a) run symmetrically on all parties' messages, and
   (b) flag this provenance so reviewers weigh it. Do not present aggregate "abuse scores" as
   neutral metrics.
7. **Severity 0 = neutral marker, not benign.** Many entries (alcohol terms, certainty/hedge
   words, place names) carry `severity: 0` — they are *statistical/linguistic markers* collected
   for corpus analysis, not abuse indicators. Do not surface them as misconduct.

---

## 1. PROVENANCE / SOURCE MAP

| # | Source artifact | Path | What it contributed |
|---|---|---|---|
| S1 | `behavioral_patterns.ttl` | `dev-resources/Archives/dial-stack/ontologies/behavioral_patterns.ttl` | OWL/Turtle ontology: category classes, pattern regexes, severity, MCL links (opencode iteration, v1.0.0, 2026-03-04) |
| S2 | `positive_behaviors.ttl` | `dev-resources/Archives/dial-stack/ontologies/positive_behaviors.ttl` | Positive-behavior taxonomy (affirmation, expectation-setting, cooperation, dependency-cultivation) |
| S3 | `mcl_722_23.ttl` | `dev-resources/Archives/dial-stack/ontologies/mcl_722_23.ttl` | MCL 722.23 factor classes A–L, weights, evidence types, factor→pattern mapping |
| S4 | `seed-patterns.ts` | `dev-resources/Archives/_project_dirs_loose/seed-patterns.ts` | **The big lexicon** — 308 literal-string patterns across 26 categories, name/category/pattern/description/severity (Drizzle seed) |
| S5 | `behavioral-pattern-analyzer.html` | `dev-resources/Archives/_project_dirs_loose/behavioral-pattern-analyzer.html` | Standalone browser app: `ABUSE_PATTERNS` regex object (coercive_control, verbal_abuse, gaslighting, love_bombing, triangulation, double_bind) + `SEVERITY_WEIGHTS` |
| S6 | `pattern-analyzer.ts` | `dev-resources/Archives/Agno-MCP-Platform-alpha/.claude/worktrees/migration-plan-v8/server/mcp/forensics/pattern-analyzer.ts` | `CommunicationPatternAnalyzer`: 24 built-in modules + `BUILT_IN_PATTERNS` substring sets + MCL weights + contradiction/linguistic analysis |
| S7 | `multi-pass-classifier.ts` | `…/server/mcp/analysis/multi-pass-classifier.ts` | 6-pass pipeline (Pass 0–6) orchestration, severity/confidence aggregation |
| S8 | `priority-screener.ts` | `…/server/mcp/analysis/priority-screener.ts` | **Pass 0** immediate-flag regexes (child name, child ref, call/visit blocking, parenting-time denial, custody interference) |
| S9 | `COMPLETE_SCHEMA_PARSER_INVENTORY.md` Part 4 | `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/Case/COMPLETE_SCHEMA_PARSER_INVENTORY.md` | `detection_patterns.py` DB-schema view: `behavior_categories` (18), `mcl_factors` (A–L), child-name patterns, 11 scored regex rules |
| S10 | `CLAUDE.md` (loose) | `dev-resources/Archives/_project_dirs_loose/CLAUDE.md` | Architecture narrative: 6-pass design, cluster-ID scheme, "256 patterns / 26 categories", priority-flag spec |

Related skills present in workspace (not re-extracted, but part of this mini-app's surface):
`behavioral-pattern-analyzer`, `mcl-factor-mapper`, `mi-best-interest-factors`, `manipulation-patterns`,
`irac-formatter` (scoped under `OTHER_RESOURCES_TO_SORT/AI_Config/`).

**Iteration note:** the same taxonomy was rebuilt at least 4 times — as OWL/Turtle (S1–S3),
as a flat TS seed lexicon (S4), as a standalone HTML regex app (S5), and as a typed module
system (S6–S8). They overlap but disagree on category names, severity scales (1–10 vs 0–100 vs
"Low/Med/High/Critical"), and MCL letter assignments. Section 6 reconciles these.

---

## 2. BEHAVIOR TAXONOMY (full category set)

Two severity conventions appear in the sources; both preserved. **Engine convention:** store a
canonical `severity_1_10` (S4/S1/S9 scale) and derive UI weights. `module_weight_0_100` is the
S6 module-level triage weight.

### 2.1 Negative / abuse categories (core ≥18, per S9 `behavior_categories`)

| category id | label | default sev | MCL factors (canonical) | primary source |
|---|---|---|---|---|
| `gaslighting` | Reality distortion / denial | high (8) | A, F, K | S1,S4,S5,S6,S9 |
| `blame_shifting` | Deflecting responsibility onto victim | high (7–8) | F, J, K | S1,S4,S6,S9 |
| `minimizing` | Downplaying concerns/feelings | med (5–6) | F, J | S1,S4,S6,S9 |
| `love_bombing` | Excessive flattery / premature devotion | med (4–6) | A, F | S1,S2,S4,S5,S6,S9 |
| `stonewalling` | Silent treatment / refusal to communicate | med (7) | F, K | S6,S9 |
| `parental_alienation` | Damaging child–parent bond | critical (9–10) | A, I, J, K | S1,S4,S6,S8,S9 |
| `coercive_control` | Pattern of domination/restriction | critical (8–10) | C, J, K | S1,S5,S9 |
| `financial_abuse` / `financial_control` | Economic abuse / weaponized money | high (6–8) | C, J | S4,S5,S6,S9 |
| `substance_weaponization` | Using substance use as a weapon/label | high (8–9) | B, F, G, K | S4,S9 |
| `reactive_abuse` | Provoked reaction reframed as aggression | high | F, J, K | S9 (skill), narrative |
| `darvo` | Deny · Attack · Reverse Victim & Offender | critical (7–10) | F, J, K | S1,S4,S5,S6,S9 |
| `character_assassination` / `character_attacks` | Degradation / slurs | high (6–9) | B, F, K | S5,S9 |
| `isolation` / `isolation_tactics` | Cutting off support systems | high (7–9) | J, K | S1,S5,S6,S9 |
| `hoovering` | Pulling victim back after discard | med-high | A, F | S9 (skill/narrative) |
| `triangulation` | Third parties used to pressure/shame | med-high (6) | F, J | S5,S9 |
| `parenting_time` | Visitation / handoff interference | critical (8–9) | J, K | S8,S9 |
| `gatekeeping` | Blocking contact/info access | high (8) | J | S9 |
| `special_needs` | Child special-needs (autism/sensory) handling | high (8) | A, C, L | S9 |

### 2.2 Extended / iteration-specific negative categories (from S4 seed lexicon — 26-cat build)

`circular` (circular arguments), `darvo_deny`, `darvo_attack`, `darvo_reverse` (DARVO split into
phases), `overelaboration` (excessive location/time detail → deception marker), `excessive_gratitude`,
`debt_reminders`, `savior_complex`, `substance_alcohol` (sev 0 markers), `substance_weaponized`,
`adderall_control`, `infidelity`, `infidelity_places` (sev 0 markers), `financial_weaponized`,
`sexual_shaming`, `medical_abuse`, `reproductive_coercion`, `victim_deference` (power asymmetry),
`abuser_directives` (power asymmetry), `certainty_absolutes` (sev 0 linguistic), `hedge_words`
(sev 0 linguistic).

### 2.3 Positive categories (dual-polarity — S2, S6)

| category id | label | sev/weight | MCL | note |
|---|---|---|---|---|
| `love_bombing` | (also positive-polarity) | 4–6 / 80 | A,F,L | flagged as manipulation tactic when paired w/ devaluation |
| `affirmations` / `Affirmation` | Praise + emotional validation | low / 50 | — | ExplicitPraise, EmotionalValidation (S2) |
| `future_faking` / `ExpectationSetting` | Grandiose promises (FuturePromise, FinancialAssurance) | 75 | L | |
| `apologies` | Apology/remorse (sincerity tracked over time) | 60 | L | |
| `gift_giving` | Material generosity | 55 | C | |
| `Cooperation` | Info-sharing, flexibility (healthy baseline) | — | A,B,D | S2 — the genuine-cooperation contrast class |
| `DependencyCultivation` / `Rescuing` | "Savior" reliance-building | — | — | overlaps `savior_complex` (S4) |

### 2.4 Neutral / context categories (S6)

| category id | label | weight | MCL |
|---|---|---|---|
| `power_asymmetry` | victim-deference vs abuser-directive dynamics | 60 | J, L |
| `scheduling` | custody schedule / visitation logistics | 40 | A, B, D |
| `child_wellbeing` | child health/education/emotional mentions | 50 | A, B, E, G |
| `overelaboration` | (neutral→deception marker) | 70 | L |
| `certainty_absolutes`, `hedge_words` | linguistic statistical markers | — | — |

---

## 3. DETECTION PATTERN CATALOG (config-table form)

Schema for a `behavioral_patterns` row (reconciled from S4 + S6 + S9):

```
pattern_id     TEXT/INT   -- stable id, e.g. gaslighting_001
category       TEXT       -- FK behavior_categories.id (Section 2)
subcategory    TEXT       -- optional (e.g. darvo_reverse, child_weaponization)
match_type     ENUM       -- 'literal' | 'regex'
pattern        TEXT       -- literal substring OR regex source
keywords       TEXT[]     -- example trigger words/phrases
severity       INT 1..10  -- triage priority (0 = neutral marker)
score          INT 1..10  -- custody-relevance (S9 detection_patterns.py)
mcl_factors    TEXT[]     -- canonical letters A..L
description    TEXT
is_case_specific BOOL     -- TRUE for names/places/slurs (Section 4)
source         TEXT       -- provenance tag S1..S9
```

### 3.1 Ontology-level patterns (S1 `behavioral_patterns.ttl` — regex + severity + MCL)

| pattern_id | category | match_type | pattern (regex) | severity | mcl_factors |
|---|---|---|---|---|---|
| gaslighting.denial | gaslighting | regex | `(?i)(i never\|would never\|did not\|didn't\|never happened)` | 8 | F |
| gaslighting.imagined | gaslighting | regex | `(?i)(imagined\|imagining\|made up\|in your head\|crazy\|insane\|delusional)` | 9 | F,K |
| gaslighting.no_one_believe | gaslighting | regex | `(?i)(no one\|nobody\|will believe\|won't believe\|no one will)` | 10 | A,K |
| blame.your_fault | blame_shifting | regex | `(?i)(your fault\|you made me\|because of you\|you're the reason)` | 8 | F |
| blame.look_what_you | blame_shifting | regex | `(?i)(look what you\|see what you\|this is your\|you caused)` | 7 | F |
| minimizing.not_big_deal | minimizing | regex | `(?i)(not a big deal\|no big deal\|not big deal\|making a big\|overreacting)` | 6 | F |
| minimizing.calm_down | minimizing | regex | `(?i)(calm down\|you need to calm\|just calm\|relax\|settle down)` | 5 | F |
| darvo.deny | darvo_deny | regex | `(?i)(i never\|would never\|that never\|didn't happen\|not true)` | 7 | F |
| darvo.reverse | darvo_reverse | regex | `(?i)(protect.*from you\|you're the\|victim\|abuser\|i need)` | 10 | F,K |
| lovebomb.perfect | love_bombing | regex | `(?i)(perfect\|amazing\|wonderful\|incredible\|soulmate)` | 4 | A |
| lovebomb.forever | love_bombing | regex | `(?i)(forever\|always\|eternal\|never leave\|always be)` | 5 | A |
| lovebomb.give_everything | love_bombing | regex | `(?i)(give.*everything\|all i have\|do anything\|sacrifice)` | 6 | A,F |
| coercive.isolation | coercive_control | regex | `(?i)(isolat\|alone\|no friends\|can't see\|don't need)` | 9 | J,K |
| coercive.financial | coercive_control | regex | `(?i)(money\|finances\|budget\|allowance\|spend\|account)` | 8 | C |
| coercive.monitoring | coercive_control | regex | `(?i)(track\|monitor\|check\|where are\|who are\|location)` | 8 | J,K |
| alienation.badmouth | parental_alienation | regex | `(?i)(your (father\|mother\|dad\|mom)\|bad (father\|mother)\|doesn't love)` | 10 | A,J |
| alienation.interference | parental_alienation | regex | `(?i)(can't see\|not allowed\|refuse\|won't let\|preventing)` | 9 | J |
| overelab.just_left | overelaboration | regex | `(?i)(just (left\|happened\|went)\|before you\|had to)` | 4 | F |

(S1 also records per-category aggregate counts: gaslighting 19, blame_shifting 42, minimizing 32,
darvo 28, love_bombing 15, coercive_control 35, parental_alienation 22, overelaboration 18 — these
are the claimed full-corpus pattern counts behind the "256 patterns / 26 categories" total in S10.)

### 3.2 HTML-app regexes (S5 `ABUSE_PATTERNS` — richer, anchored regex)

`coercive_control.child_weaponization` (severity weight 9):
```
/you('re| are)n('|o)?t (gonna |going to )?(see|have|get) (her|him|the kid|kailah)/i
/(forget about|don't expect to see) (her|him|the kid)/i
/if you (want to see|wanna see) (her|him)/i
/you don't deserve (her|him|to be a (father|dad|parent))/i
/(blocking you|blocked).*?(from|so you can't see) (her|him)/i
```
`coercive_control.communication_control` (5): `/(blocked|blocking) you/i`, `/don't (text|call|contact) me/i`, `/leave me (alone|the fuck alone)/i`, `/lose my number/i`, `/never (talk|speak) to me again/i`
`coercive_control.financial_control` (6): `/you (owe|need to pay|better pay) me/i`, `/where'?s? (the|my) money/i`, `/pay (me|for|child support)/i`, `/(don't|won't) give you (shit|anything|a dime)/i`
`coercive_control.isolation_tactics` (7): `/(everyone|everybody|people) (knows|think|say) you'?re/i`, `/told (everyone|everybody|them) (about|what) you/i`, `/nobody (likes|wants|trusts) you/i`, `/your (family|friends) (knows|know) (what|who) you are/i`
`coercive_control.monitoring_stalking` (8): `/i know (where you|what you|who you)/i`, `/i('m| am) watching you/i`, `/i saw you (at|with)/i`, `/someone told me you/i`
`verbal_abuse.homophobic_slurs` (7): `/\bf+a+g+([og]+(e|o)?t|it)\b/i`, `/\bgay\b.*?\b(ass|bitch|fuck)/i`, `/\bqueer\b/i`
`verbal_abuse.character_attacks` (6): piece of shit/trash/garbage, motherfucker, bitch made/ass, pussy, good for nothing, worthless, pathetic, loser
`verbal_abuse.mental_health_stigma` (5): `/\b(psycho|crazy|insane|mental|nuts)\b/i`, `/\b(sick|twisted|fucked up) (in the head|mentally)/i`, `/need (help|therapy|meds|medication)/i`, `/\bweirdo\b/i`
`verbal_abuse.substance_shaming` (5): `/\b(crackhead|crack head|tweaker|junkie|addict)\b/i`, `/\bhigh (as fuck|af|again)\b/i`, `/on (that shit|drugs|dope)/i`
`verbal_abuse.threats` (10): `/(i'll|i will|gonna) (fuck you up|beat|kill|hurt|destroy)/i`, `/watch your back/i`, `/you('re| are) (gonna|going to) regret/i`, `/better watch out/i`, `/i('ll| will) make you/i`
`gaslighting` (7): that never happened; you're crazy/imagining/making it up; i never said that; you're being/too dramatic/sensitive/emotional; you always exaggerate/overreact; that's not what/how it happened; you're twisting/changing/distorting my words; you know that's not true
`love_bombing` (4): i love you so much; you're the best/amazing/perfect/everything to me; i can't live without you; you're the only one/all i want/need; i miss you so much/baby; come over/here … i need you/baby/please
`triangulation` (6): everyone/people/they think/say/know you're; i told them/everyone about you; he/she/they said/told me you're; my friend/mom/family doesn't like/hates you; (unlike you/at least he/she) treats me/is there for me/cares
`double_bind` (7): if you loved/cared about me … you would/wouldn't; you say … but you don't/never/won't; (come over/see me) … (leave me alone/don't contact)

**S5 `SEVERITY_WEIGHTS` table (authoritative for this app):**
`threats:10, child_weaponization:9, monitoring_stalking:8, homophobic_slurs:7, character_attacks:6,
isolation_tactics:7, gaslighting:7, financial_control:6, communication_control:5, substance_shaming:5,
mental_health_stigma:5, love_bombing:4, triangulation:6, double_bind:7`

### 3.3 Scored regex rules (S9 `detection_patterns.py` — has explicit custody `score` 1–10)

| pattern_id | category | mcl_factors | score | regex |
|---|---|---|---|---|
| parenting_time_001 | parenting_time | J | 9 | `you\s+(?:won't\|can't)\s+see\s+(?:her\|kailah)` |
| parenting_time_002 | parenting_time | J, K | 8 | `if\s+you\s+don't.*(?:her\|daughter)` |
| alienation_001 | parental_alienation | K, D | 10 | `dad(?:dy)?\s+(?:is\|doesn't\|won't)` |
| alienation_002 | parental_alienation | K, D | 10 | `who\s+do\s+you\s+want\s+to\s+(?:stay\|live)\s+with` |
| medical_001 | medical | A, J | 8 | `doctor\|hospital\|sick\|medicine` |
| medical_002 | medical | J | 9 | `you\s+don't\s+need\s+to\s+know` |
| character_attack_001 | character_attack | B, F, K | 9 | `drug(?:s)?\|high\|using\|addict` |
| gatekeeping_001 | gatekeeping | J | 8 | `block(?:ed\|ing)?\|stop\s+(?:texting\|calling)` |
| coercive_control_001 | coercive_control | K | 9 | `comply\|do\s+what\s+I\s+(?:say\|tell)` |
| coercive_control_002 | coercive_control | K | 8 | `if\s+you\s+don't\|unless\s+you\|or\s+else` |
| special_needs_001 | special_needs | A, L | 8 | `autism\|autistic\|spectrum\|sensory\|meltdown` |

### 3.4 Literal-string seed lexicon (S4 `seed-patterns.ts` — 308 patterns / 26 categories)

Stored verbatim as `match_type='literal'`. Severity per entry. The full set is in S4; representative
high-signal rows (category → pattern : severity) — **load the full 308 from source, do not retype by hand:**

- **gaslighting:** "i never said that":8, "you imagined":8, "you're paranoid":7, "that never happened":9, "no one will believe":9, "you're crazy":9, "you're just high":8, "this is the drugs talking":8
- **blame_shifting:** "this is your fault":7, "you made me":8, "because of you":7, "you always do this":7, "look what you made me do":9
- **minimizing:** "not a big deal":6, "you're too sensitive":7, "calm down":5, "get over it":7, "it was just a joke":6
- **circular:** "that's not the point":6, "you keep changing":6, "whatever":5, "we're not in high school":6
- **darvo_deny:** "i never":8, "that never happened":9, "you're making that up":9, "that's a lie":9
- **darvo_attack:** "you're the abusive one":10, "you're gaslighting me":10, "you're toxic":9, "you're the problem":9, "you're delusional":9
- **darvo_reverse:** "i'm the victim here":10, "you're attacking me":10, "you're abusing me":10, "i'm scared of you":10, "i need protection from you":10
- **overelaboration:** "i'm at":7, "i just left":7, "before you ask":8, "for the record":7, "to be clear":7, "i had to":8 (22 location/justification/pre-emptive markers)
- **love_bombing:** "soulmate":6, "can't live without you":7, "you're the only one who understands me":6, "i want to give you everything":6
- **excessive_gratitude:** "i owe you everything":6, "you saved me":7, "i owe you my life":7, "i don't know what i'd do without you":6
- **debt_reminders:** "after all i've done":8, "i was there for you when":7, "remember when i":7
- **savior_complex:** "you need me":8, "you can't trust anyone but me":9, "they're all out to get you":9, "i'm the only one who cares":8, "everyone else will hurt you":9
- **substance_alcohol** (sev 0 markers): drink, drunk, wasted, wine, beer, vodka, tequila, hungover, fireball …
- **substance_weaponized:** "crackhead":9, "tweaker":9, "junkie":9, "addict":8, "are you on something":8
- **adderall_control:** "adderall":7, "your turn":8, "how many did you take":8, "i'm holding onto them for you":9, "you can't control yourself":9
- **infidelity:** "cheating":8, "affair":9, "slept with":8, "seeing someone":8, "he's just a friend":6, "you're being jealous":7
- **infidelity_places** (sev 0, **case-specific**): "huckleberry junction", "huck's", "hucks"
- **financial_weaponized:** "you don't do anything":8, "what do i get out of this":8, "it's your responsibility to provide":8
- **sexual_shaming:** "slut":10, "whore":10, "freak":9, "disgusting":8, "no wonder everyone leaves you":10
- **parental_alienation:** "doesn't want to see you":10, "i have to protect the children from you":10, "kailah":10, "kyla":10, "my daughter":8, "our daughter":7, "the baby":6
- **medical_abuse:** "you need your meds":9, "you're not thinking clearly":9, "i'm holding your meds":10, "you can't make decisions":10, "you need to be hospitalized":10, "you're bipolar/borderline/schizophrenic":9
- **reproductive_coercion:** "i want you pregnant":10, "stop taking birth control":10, "i sabotaged your birth control":10, "you can't leave if you're pregnant":10, "you owe me a child":10, "i'll take the baby":10, "you'll never see the baby":10, "i'll prove you're unfit":10
- **victim_deference:** "if that's okay":7, "sorry":6, "i apologize":6, "i didn't mean to":6 (apology/permission markers)
- **abuser_directives:** "where are you":8, "who are you with":8, "show me":8, "prove it":8, "come here":7, "tell me":7
- **certainty_absolutes** (sev 0 linguistic): always, never, everything, everyone, obviously, clearly, literally, fact
- **hedge_words** (sev 0 linguistic): maybe, perhaps, possibly, might, could, i think, i guess, sort of, kind of, probably

### 3.5 Module-level catalog (S6 `BUILT_IN_PATTERNS` — substring sets per module)

S6 defines 24 modules (Section 2) each with a `patterns[]` substring list and `examples[]`. It uses
**lowercase MCL letters** and a 0–100 `weight`. Notable module→pattern sets not already above:
`emotional_blackmail` (FOG: "after everything i've done", "if you loved me", "you owe me", "i'll hurt
myself"), `projection` ("you're the one who", "you're cheating", "you're the narcissist"),
`stonewalling` ("conversation is over", "talk to my lawyer", "i'm done", "whatever"),
`future_faking` ("when we get married", "i'll change", "things will be different"),
`power_asymmetry` (deference + directive split). Full substring lists are in S6 lines 360–768.

---

## 4. CHILD-NAME & VULNERABILITY KEYWORD LISTS (case-specific config tables)

> **Guardrail:** these are `is_case_specific=TRUE` lexicon rows. A child-name match is a *relevance*
> signal (this message concerns the child), **not** an abuse signal. Spelling variants exist because
> of voice-transcription artifacts.

**`child_name_lexicon`** (S8 regex + S9 list):
```
/\bkailah\b/gi   -- canonical spelling
/\bkyla\b/gi     -- voice-recognition variant
/\bkaila\b/gi    -- common variant
/\bkailuh\b/gi   -- voice-recognition variant
\blittle\s+shit\b  -- derogatory child reference (S9; context-dependent)
```
**`child_reference_lexicon`** (generic, severity 8, MCL A):
`my daughter, our daughter, your daughter, the baby, the kid, the child, our child, my kid, my child`

**`vulnerability_lexicon`** (special-needs / health vulnerability — MCL A,C,G,L):
`autism, autistic, spectrum, sensory, meltdown` (S9 special_needs_001) ·
medical/mental-health diagnosis terms weaponizable for control: `bipolar, borderline, schizophrenic,
episode, hospitalized, meds, medication, pills, adderall, script` (S4 medical_abuse / adderall_control)

**`place_lexicon`** (case-specific locations, severity 0 — corroboration markers only):
`huckleberry junction, huck's, hucks` (alleged infidelity location, S4)

**Cluster-ID topic codes** (S10 — conversation segmentation vocabulary, 6-char):
`KAILAH (daughter), VISITS (parenting time), CALLS, SCHOOL, MONEY, HEALTH, SUBST, INFID, THREAT, GENRL`
Platform codes: `SMS, FB, IMSG, MAIL, CHAT, WA, DISC, SNAP`. Cluster format `PLAT_YYMM_TOPIC_iii`
(e.g. `SMS_2401_KAILAH_001`).

---

## 5. POSITIVE-BEHAVIOR ONTOLOGY (S2 + S6 — dual-polarity)

Class tree (`positive_behaviors.ttl`):
```
PositiveBehaviorPattern
├─ Affirmation
│  ├─ ExplicitPraise        — direct compliments re: character/parenting/capability
│  └─ EmotionalValidation   — acknowledging the other party's feelings as valid
├─ ExpectationSetting        (a.k.a. "future faking" when unfulfilled)
│  ├─ FuturePromise         — grandiose promises re: living/finances/family harmony
│  └─ FinancialAssurance    — promises to provide / cover costs
├─ Cooperation               (the healthy co-parenting baseline / contrast class)
│  ├─ InformationSharing     — proactively sharing medical/educational/scheduling info
│  └─ Flexibility            — agreeing to reasonable schedule changes w/o leverage
└─ DependencyCultivation     (the "savior" complex)
   └─ Rescuing               — solving problems the other party could solve, building reliance
```
**Why tracked:** positive statements are the *contradiction anchors*. S6 `detectContradictions()`
flags: (a) love-bombing within 2000 chars of devaluation (gaslighting/blame/minimization/threats);
(b) an apology followed within 3000 chars by the same negative behavior — the apology→repeat cycle.
`Cooperation` is the genuine-good-faith class that distinguishes real co-parenting from
`DependencyCultivation`/`love_bombing` manipulation. MCL: praise/validation→A; promises→L;
apologies→L; gift_giving/financial assurance→C; cooperation→A,B,D.

---

## 6. MCL 722.23 FACTOR REFERENCE + PATTERN→FACTOR MAPPING

### 6.1 Canonical factor table (statute order A–L)

| code | canonical label (statute) | weight | abuse patterns that implicate it |
|---|---|---|---|
| A | Love, affection & emotional ties | High | parental_alienation, love_bombing, emotional_withholding, child_reference |
| B | Capacity/disposition to give love, guidance, education, religion | High | character_assassination, cultural/religious coercion, substance_weaponization |
| C | Capacity to provide food, clothing, medical care | High | financial_abuse, financial_control, medical/financial neglect, special_needs |
| D | Length of time in stable satisfactory environment (continuity) | Med | housing/living instability, frequent moves |
| E | Permanence of family unit of proposed custodial home | Med | housing instability |
| F | Moral fitness of the parties | High | gaslighting, darvo, coercive_control, minimizing, blame_shifting, infidelity, pathological lying |
| G | Mental & physical health of the parties | High | medical_abuse, substance_abuse, diagnosis-weaponization |
| H | Home, school & community record of the child | Med | child_wellbeing, school record |
| I | Reasonable preference of the child (if of sufficient age) | Med | parental_alienation, coaching the child |
| J | **Willingness to facilitate & encourage** the child's relationship with the other parent | **Critical** | parental_alienation, parenting_time, gatekeeping, isolation, interference |
| K | Evidence of **domestic violence** (against or witnessed by child) | **Critical** | coercive_control, threats, physical/emotional abuse, isolation, control patterns |
| L | Any other relevant factor | Variable | special_needs, overelaboration/deception, unique circumstances |

### 6.2 ⚠️ KNOWN MAPPING DISCREPANCY (must reconcile before any court use)

The sources **disagree on J vs K**, and one source has them swapped:

- **Canonical (statute & S9 inventory):** **J = Willingness to Facilitate the Relationship**;
  **K = Domestic Violence**.
- **S3 `mcl_722_23.ttl` BUG:** `FactorJ` carries `rdfs:label "Domestic Violence"` but its
  `rdfs:comment` is the *facilitation* text; `FactorK` carries `rdfs:label "Parental Cooperation"`
  but its comment is the *domestic-violence* text. **The labels are swapped relative to the comments.**
  The comments (definitions) are correct; the labels are wrong. Engine must key on the statutory
  definition, not the S3 label.
- **S6 `pattern-analyzer.ts`** uses lowercase letters and treats `j`=domestic violence,
  `k`=facilitate — i.e. it follows S3's *labels* (the buggy side). Any data tagged by S6 needs a
  **J↔K remap** to the canonical convention above.

**Action for reconciliation:** adopt the statutory definitions (6.1) as canonical; add a migration
that remaps S6/S3-label-derived `j`/`k` tags to canonical `J`/`K`. This is the same
`disclosure_tier`-style off-by-one class of bug noted in the forensic-DB addendum — flag it explicitly.

### 6.3 Pattern→factor map (consensus, canonical letters)

```
gaslighting            → A, F, K
blame_shifting         → F, J, K
minimizing             → F, J
darvo                  → F, J, K
coercive_control       → C, J, K
parental_alienation    → A, I, J, K
parenting_time         → J, K
gatekeeping            → J
isolation              → J, K
threats_intimidation   → J, K
financial_abuse        → C, J
medical_abuse          → F, G, J
substance_weaponization→ B, F, G, K
reproductive_coercion  → J, K, L
character_assassination→ B, F, K
special_needs          → A, C, L
overelaboration        → L (deception marker)
love_bombing (pos)     → A, F, L
apologies/affirmations → L
cooperation/scheduling → A, B, D
child_wellbeing        → A, B, E, G
```

---

## 7. ENGINE ARCHITECTURE (how patterns are applied — S6/S7/S8)

**6-pass pipeline (surface-level, NO LLM until meta-analysis):**
- **Pass 0 — PriorityScreener (S8):** immediate HIGH-severity flags for child-name, child-ref,
  call/visit blocking, parenting-time denial, custody interference. Severity 8–10, sets
  `immediate_severity` that *overrides* computed severity. Non-negotiable per S10.
- **Pass 1 — spaCy:** structure, entities, **speaker attribution** (PERSON entities), question/
  imperative detection.
- **Pass 2 — NLTK VADER:** sentiment, negation, intensity modifiers.
- **Pass 3 — Pattern Analyzer (S6):** built-in modules + DB-seeded custom patterns + MCL tagging.
- **Pass 4 — TextBlob:** polarity + subjectivity → **sarcasm detection** (high subjectivity +
  polarity contradicting negative patterns).
- **Pass 5 — Sentence Transformers:** semantic similarity to known pattern examples (placeholder/
  partial in S7).
- **Pass 6 — Keyword extraction.**
- **Aggregation:** consensus sentiment vote across sources; `negative_count ≥5 → "abusive"`,
  `≥3 → "hostile"`; severity = `max(computed, priority.immediate_severity)`; confidence from
  passes-completed ratio + pattern/sentiment agreement.

**DARVO sequence detection:** look for all three phases (deny→attack→reverse) within one message
or a 3–5 message window; severity 9–10. S6 splits DARVO into `darvo_deny`(80)/`darvo_attack`(90)/
`darvo_reverse`(100) sub-severities.

**Linguistic markers (S6):** pronoun ratio (I-talk vs you-talk; high "you" → blame/accusation),
hedge-vs-certainty ratio (abusers skew certainty-absolute; victims skew hedge), sentence-length
overelaboration score. These are *neutral* corpus features, not abuse findings (Guardrail #7).

**User custom patterns:** loaded via `loadUserConfig(userId)` from the `behavioral_patterns` table
**before** analysis runs — they are additive to built-ins and are the bulk of the ~200-hr curated
lexicon. They must be loadable as data (Guardrail #5).

---

## 8. RECONCILIATION NOTES / OPEN ITEMS

1. **Severity scale unification** — three scales coexist (1–10 in S1/S4/S9; 0–100 module weight in
   S6; Low/Med/High/Critical→1/5/8/10 in S3). Store canonical 1–10; derive the rest.
2. **Category-name normalization** — `alienation`↔`parental_alienation`, `character_attack`↔
   `character_assassination`, `medical`↔`medical_abuse`, `financial_control`↔`financial_abuse`↔
   `financial_weaponized`. Pick canonical IDs (Section 2) and alias the rest.
3. **J↔K remap migration** — see 6.2; blocking for court use.
4. **De-dup across sources** — the same phrase ("that never happened", "i need protection from you")
   appears as literal (S4), regex (S1/S5), and module-substring (S6). Engine should dedupe matches
   by (category, normalized_text, position) to avoid triple-counting severity.
5. **Pattern count truth** — S10 claims "256 patterns / 26 categories"; S4 actually contains 308
   literal rows; S1 claims 256+ across its aggregate counts. Treat counts as approximate.
6. **Symmetry requirement** — run on all parties (Guardrail #6); current lexicon is single-party.
7. **`detection_patterns.py` is the named single-source-of-truth** in S9 but only 11 scored rules
   were captured in the inventory; the full file (`/tmp/detection_patterns.py`, 320+ lines) should
   be located and merged if recoverable.
