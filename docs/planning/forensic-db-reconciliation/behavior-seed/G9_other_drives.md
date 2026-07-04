# G9 — Behavioral-Pattern Fragments Mined from the OWNER'S OTHER DRIVES

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> `source = 'onedrive/D-drives'` for every row below.
> **Scope:** NET-NEW only — deltas vs the already-coded sources G1–G8 (analyzer app, `seed-patterns.ts`
> 25-cat, dial TTL 12-cat, E4 33-cat, agno-alpha classifiers ~30-cat, dataset 37-cat, Zep v3 ontology,
> conversation fragments). Roots scanned (text/note files only; evidence/binary dirs excluded):
> `C:/Users/matts/OneDrive/Case Bible`, `D:/casebible`, `D:/Backup`.

## Root reachability
- `C:/Users/matts/OneDrive/Case Bible` — **OK** (richest; all unique structured assets live here).
- `D:/casebible` — **OK but EMPTY** of behavior/pattern/ontology text files (0 filename + 0 content hits).
- `D:/Backup` — **OK**; contains the `Case Bible BACKUP 2026-03-12/` mirror + `D:/Backup/Court/`
  + `D:/Backup/Documents/`. All behavior assets here are **older duplicates** of the OneDrive copies
  (same `coercive_control_pipeline/`, same Gemini taxonomy, same forensic-analysis docs). No net-new
  beyond OneDrive; cited only where it is the cleaner copy.

## Court-safety routing (HARD — applied to every row)
- Every negative `detection_pattern` row = **HYPOTHESIS, not fact** → `bias_caution = true`,
  `authored_perspective = 'single_party_complainant'`. `severity`/`score` = triage priority, never legal weight.
- Generic manipulation phrases → `detection_pattern`. **Named people / child / case-specific places /
  deceased-relative refs / named-target epithets / real verbatim case quotes → `pattern_lexicon`**
  (`sensitivity_tier='sealed'` for identifiers/places, `'restricted'` for vulnerabilities),
  `is_case_specific=true`. Identifiers are **referenced, never reproduced as plaintext** in this doc.
- The `Primary-vs-Reactive-Abuse` source introduces a **REACTIVE-ABUSE caveat**: a pattern hit on the
  documenting party may be a defensive/reactive response, not primary aggression. All patterns MUST run
  symmetrically on all parties; reinforces `bias_caution=true` system-wide.

## Richest source files (ranked)
1. **`OneDrive/Case Bible/Archives/_TECH_ASSETS/coercive_control_pipeline/labels_ontology.json`** — 14-cluster
   coercive-control ontology with a 3-axis **attack-dimension** taxonomy + 41 member behaviors + academic
   citations (PMC reviews). Companions: `behaviors_normalized.jsonl` (40 labeled behaviors w/ source_url),
   `coercive_control_guideline.md` (annotation rules + label/don't-label thresholds + near-miss examples),
   `dataset_stats.json` (label frequency distribution). **The single most valuable net-new asset.**
2. **`OneDrive/Case Bible/Raw AI Chats/‎Gemini - Gaslighting Tactics A Detailed Taxonomy.md`** — 12-tactic
   gaslighting subtype taxonomy, each with identifying phrases.
3. **`OneDrive/Case Bible/transcript/salenma/Gaslighting_and_Deceit_Detection_Rules-2026-04-15-20-47-07 - Copy.md`** —
   structured rule-set (Categories → Rules → keywords) for a behavior-analysis engine.
4. **`OneDrive/Case Bible/abusive language dictionary.md`** — JSON pattern dict; generic buckets overlap
   G2/G6, but carries **case-specific lexicon** (infidelity place, weaponized-substance phrasing) + a
   platform-denial *contradiction detector* (regex logic).
5. **`OneDrive/Case Bible/wiki/tools/ai-workspace-tools/manipulative-expression-recognition.md`** — MER tool
   manipulation-style label set (open-source levitation/MER).
6. **`OneDrive/Case Bible/drive-download-20251216T101619Z-3-001 - 1/Primary-vs-Reactive-Abuse.md`** —
   primary-vs-reactive aggressor framework + MCL 722.23(k) + *Kubicki v. Sharpe* case law (net-new
   MCL mapping + bias concept). Body contains real case quotes/slurs/names → routed sealed.

---

## A. `detection_pattern_set` — seed ONE set (NOT active; secondary corpus)

| col | value |
|---|---|
| name | `coercive-control-clusters-g9` |
| version | `1.0.0` |
| source | `onedrive/D-drives` |
| source_artifact | `OneDrive/Case Bible/Archives/_TECH_ASSETS/coercive_control_pipeline/labels_ontology.json` |
| description | 14-cluster coercive-control ontology (3 attack dimensions) + 12-tactic gaslighting taxonomy + deceit-detection rule-set, harvested from the owner's OneDrive/D: research drives. Academic-grounded (PMC reviews, Anah/Broxtowe). |
| authored_perspective | `single_party_complainant` |
| is_active | **false** (only ONE active set allowed; this is a reconciliation/merge candidate, not the live set) |

---

## B. `behavior_category` — NET-NEW categories

### B1. The 14 coercive-control clusters (from `labels_ontology.json`)
The **`attack_dimension` axis is net-new** (`AUTONOMY` / `IDENTITY_SELF_WORTH` / `TERROR_HELPLESSNESS`) and
is captured in `notes` (no enum column exists for it). All polarity = `negative`. `is_case_specific=false`.

| category_id (snake_case) | label | attack_dim (→notes) | default_severity | mcl_factors | member behaviors (→ aliases) | net-new vs G1–G8 |
|---|---|---|---|---|---|---|
| `isolation` | Isolation / Cutting Off Support | AUTONOMY | 7 | c,k | social isolation; relationship destruction; information/resource control | dim-axis + "relationship destruction" sub |
| `monitoring_surveillance` | Monitoring & Surveillance | AUTONOMY | 6 | k | movement monitoring; digital surveillance; intimate-partner stalking | **NET-NEW category** |
| `financial_control` | Financial Control / Economic Abuse | AUTONOMY | 6 | c | financial withholding; economic sabotage; **debt weaponization** | "debt weaponization" sub net-new |
| `gaslighting_reality_distortion` | Gaslighting & Reality Distortion | IDENTITY_SELF_WORTH | 7 | k | gaslighting; manipulation/denial; shame & confusion induction | dim-axis framing |
| `verbal_degradation` | Verbal Degradation & Devaluation | IDENTITY_SELF_WORTH | 6 | b,k | verbal degradation; partner devaluation; **empathy withholding**; dismissal/invalidation | "empathy withholding" sub net-new |
| `threats_intimidation` | Threats & Intimidation | TERROR_HELPLESSNESS | 8 | k | harm threats (victim/children/pets); intimidation displays; rule-enforcement-via-threats | dim-axis |
| `autonomy_deprivation` | Autonomy Deprivation & Daily Control | AUTONOMY | 5 | c | appearance control; interpersonal dominance; **cumulative micro-control** | "cumulative micro-control" concept net-new |
| `identity_erosion` | Identity Erosion & Trauma Bonding | IDENTITY_SELF_WORTH | 7 | k | identity erosion; **emotional manipulation cycles (love-bomb↔devalue intermittent reinforcement)** | trauma-bonding/intermittent-reinforcement net-new |
| `sexual_reproductive_coercion` | Sexual & Reproductive Coercion | AUTONOMY | 8 | k | sexual coercion; reproductive coercion (contraception sabotage) | (overlaps G-reproductive; keep) |
| `jealousy_possessiveness` | Jealousy & Possessiveness | AUTONOMY | 5 | k | jealousy/accusation; possessive jealousy (victim-as-property) | **NET-NEW category** |
| `narcissistic_entitlement` | Narcissistic Entitlement & Rage | TERROR_HELPLESSNESS | 7 | k | narcissistic rage; revenge/vengefulness; entitlement to compliance; narcissistic-injury response; **victimhood posturing**; **manufactured conflict** | "victimhood posturing" + "manufactured conflict" subs net-new |
| `legal_system_abuse` | Legal-System & Institutional Abuse | TERROR_HELPLESSNESS | 7 | j,k | legal-system weaponization (frivolous filings, false reports); **children as control tools** | **NET-NEW category** (post-separation litigation abuse) |
| `entrapment_fear` | Entrapment & Pervasive Fear | TERROR_HELPLESSNESS | 8 | k | entrapment creation; **pervasive fear conditioning (hypervigilance)**; **post-separation control** | **NET-NEW category** (cumulative trauma state) |

> Note: this ontology is **attack-dimension-organized** (harm to victim), which complements the
> existing **tactic-organized** seeds. On merge, map each existing tactic category → its attack_dimension.

### B2. Gaslighting SUBTYPES (from the 12-tactic taxonomy) — net-new subcategories
Routed as `behavior_category` children of `gaslighting_reality_distortion` (via `subcategory` on
`detection_pattern`) OR as standalone categories. polarity=`negative`, mcl_factor `k`. **Net-new subtypes**
not already enumerated in G1–G8: `countering`, `diverting`, `stereotyping`, `forgetting_feigned_amnesia`,
`questioning_sanity`, `joke_defense`, `scapegoating`, `feeling_police`, `subtle_shift`,
`weaponizing_allies_triangulation`, `provocation_defense`. (Already-covered: denial, trivializing/minimizing,
blame-shifting, future-faking, withholding/silent-treatment.)

### B3. MER manipulation styles (from `manipulative-expression-recognition.md`) — net-new labels
`victim_playing`, `exaggeration_dramatization`, `impatience`, `ignoring`, `diminishing`, `invalidation`,
`changing_the_topic`, `aggression`. (Several overlap B1/B2; net-new vs G1–G8: `victim_playing`,
`exaggeration_dramatization`, `impatience`.)

---

## C. `detection_pattern` — NET-NEW patterns (generic; bias_caution=true)

### C1. 12-tactic gaslighting phrases (match_type=`literal`, severity 6–8, set=`coercive-control-clusters-g9`)
| subcategory | pattern (verbatim, lowercased) | keywords | sev |
|---|---|---|---|
| countering | `you have a terrible memory` ; `you're putting words in my mouth` ; `you're misremembering` | memory, misremember | 7 |
| withholding | `i don't know what you're talking about` ; `you're not making any sense` ; `are you done` | — | 6 |
| trivializing | `is that really something to get upset about` ; `you're making a big deal out of nothing` | — | 5 |
| denial | `you're imagining things` ; `there's no proof of that` | imagine, proof | 7 |
| diverting | `what about that time you` ; `you're just trying to distract from your own mistakes` | what about, distract | 7 |
| stereotyping | `you're being hysterical` ; `it must be that time of the month` ; `what do you know, you're just a kid` | hysterical | 6 |
| blame_shifting | `you're the one who started it` ; `i only acted that way because you pushed me to it` | started it, pushed me | 7 |
| forgetting_feigned_amnesia | `i have no recollection of that` ; `are you sure that even happened` ; `my memory of that is completely different` | recollection | 6 |
| questioning_sanity | `you're losing your mind` ; `you need to get help` ; `everyone thinks you're unstable` | losing your mind, unstable | 8 |
| joke_defense | `i was just kidding, can't you take a joke` ; `you're too uptight` ; `lighten up, it wasn't serious` | just kidding, lighten up | 6 |
| scapegoating | `it's always your fault` ; `if it weren't for you everything would be fine` ; `we all know who the real problem is` | always your fault | 7 |
| future_faking | `things will be different once` ; `i promise i'll change, you just have to be patient` | i'll change, be patient | 6 |

### C2. Deceit-detection rule keywords (from `Gaslighting_and_Deceit_Detection_Rules…md`)
| rule / subcategory | keywords (verbatim) | sev |
|---|---|---|
| overreaction_accusation | "you're overreacting","you're too sensitive","calm down","don't be so dramatic","making a mountain out of a molehill" | 5 |
| feeling_police (NET-NEW) | "you shouldn't feel that way","there's no reason to be upset","why would you let that bother you" | 5 |
| categorical_denial | "i never said that","that never happened","you're making that up","you must have imagined it" | 8 |
| subtle_shift (NET-NEW) | "that's not how it happened","what i actually said was","you're twisting my words" | 6 |
| withholding_information (deceit by omission) | behavioral cue: vague/incomplete answers, subject-change on specifics | 6 |
| crazy_label | "you sound crazy right now","you seem unstable","everyone thinks you're paranoid" | 8 |
| weaponizing_allies_triangulation (NET-NEW) | "[name] agrees with me","everyone knows that you","we were just talking about how you" | 6 |
| provocation_defense (NET-NEW) | admits behavior but "you provoked me" / "you pushed me to it" framing | 7 |

> `[name] agrees with me` — the **template slot** is generic (keep in `detection_pattern` as a regex
> `\b(\w+) agrees with me\b`, match_type=`regex`); any **real filled name** at ingest → sealed lexicon.

### C3. Platform-denial CONTRADICTION DETECTOR (from `abusive language dictionary.md`) — net-new logic
A two-part **regex** detector (net-new as a *match_type=regex* pattern, not a phrase):
prior mention of `\b(snap|snapchat|instagram|tiktok)\b` **AND** later
`(?i)\b(i don'?t|i never)\s+(use|have)\s+(snap(chat)?|insta(gram)?|tiktok)\b` → flag
`contradiction / platform-denial`. severity 6, bias_caution=true. (Generic; the *platforms* are generic,
the contradiction is the signal.)

---

## D. `pattern_lexicon` — case-specific terms (identifiers/places → sealed; vulnerabilities → restricted)

> Reproduced **only as routing rows** — actual identifier strings are NOT written here as plaintext.

| lexicon_type | term (referenced, not reproduced) | match_type | sensitivity_tier | mcl | source | note |
|---|---|---|---|---|---|---|
| infidelity_place | named bar/venue ("huckleberry…"/"huck's" variants) in `abusive language dictionary.md` | literal | **sealed** | k | abusive language dictionary.md | case-specific place → identifies parties/location |
| case_substance_detail | case-specific drink brand used as infidelity/intoxication marker ("fireball") | literal | **restricted** | k | abusive language dictionary.md | case detail; vulnerability/lifestyle marker |
| weaponized_substance_phrasing | "this is the drugs talking","are you on something","you can't control yourself" (substance-as-weapon) | literal | **restricted** | g,k | abusive language dictionary.md | mental-health/substance weaponization → restricted (generic phrasing, but tied to real substance allegations) |
| medication_control | adderall/"addy"/"i'm holding onto them for you" control phrasing | literal | **restricted** | g | abusive language dictionary.md | medication-as-control; vulnerability trigger |
| party_name | opposing & documenting party real names | literal | **sealed** | k | Primary-vs-Reactive-Abuse.md | real names in case caption / quotes |
| verbatim_case_quote | real message quotes incl. slurs/epithets (e.g. homophobic slur, profane attacks) | literal | **sealed** | k | Primary-vs-Reactive-Abuse.md | actual evidence text → never plaintext detection_pattern |

---

## E. `behavior_category_mcl` — NET-NEW MCL mappings

- **MCL 722.23(k) — domestic violence / primary-aggressor** (`Primary-vs-Reactive-Abuse.md`):
  net-new explicit link of *coercive-control clusters* → factor **`k`** with `is_critical=true` for
  `threats_intimidation`, `entrapment_fear`, `legal_system_abuse`. Source cites
  *Kubicki v. Sharpe*, 306 Mich App 525 (2014) (court must identify **primary aggressor**) — captured in
  `note`. Adds the **primary-vs-reactive** distinction as a `note` caveat (reactive ≠ primary; lowers
  weight / inverts perpetrator inference → reinforces `bias_caution`).
- **`legal_system_abuse` → factor `j`** (willingness to facilitate the child's relationship w/ the other
  parent) + `k` — children-as-control-tools / false CPS reports map to BOTH j and k.
- **`financial_control` / `isolation` / `autonomy_deprivation` → factor `c`** (capacity to provide
  material needs / stability) where economic sabotage impairs provision.
- Attack-dimension → MCL crosswalk (for `note`): `AUTONOMY`→{c}, `IDENTITY_SELF_WORTH`→{b}, all clusters
  with fear/violence→{k}.

---

## F. Reconciliation notes
- The `coercive_control_guideline.md` thresholds ("when in doubt don't label"; "false positives that
  pathologize normal conflict are as harmful as false negatives"; near-miss/do-NOT-label examples) are the
  **strongest court-safety annotation rules found in any source** — recommend folding into the
  reconciliation addendum as the canonical labeling-discipline text and as `bias_caution` justification.
- `dataset_stats.json` gives an empirical **label-frequency prior** (ENTRAPMENT_FEAR 11, AUTONOMY_DEPRIVATION 9,
  MONITORING 9, ISOLATION 8 …) usable to seed default screening priority, not legal weight.
- `D:/casebible` is empty of behavior assets; `D:/Backup` is a dated duplicate mirror — **no unique rows**
  beyond OneDrive. Treat OneDrive `coercive_control_pipeline/` as canonical for this corpus.
