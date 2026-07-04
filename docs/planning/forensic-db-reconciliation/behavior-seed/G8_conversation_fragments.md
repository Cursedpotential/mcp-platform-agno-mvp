# G8 — Behavioral-Pattern Fragments Mined from Conversation Logs

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> `source = 'conversation-logs'` for every row below.
> **Scope:** NET-NEW only — deltas vs the already-coded structured lists G2 (`seed-patterns.ts`, 25 cat),
> G3 (dial TTL ontologies, 12 cat), G4 (E4 consolidation, 33 cat), G5 (agno-alpha classifiers, ~30 cat).
> These are fractured ideas the owner brainstormed in chat/LIWC-blueprint dumps that were **never fully
> coded** into the seed tables.

## Court-safety routing (HARD — applied to every row)
- Every negative `detection_pattern` row = **HYPOTHESIS, not fact** → `bias_caution = true`,
  `is_case_specific = false`, `authored_perspective = 'single_party_complainant'`.
- Generic manipulation phrases → `detection_pattern`. **Named people / child / places / deceased-relative
  refs / named-target epithets / mental-health-as-weapon tied to a real person → `pattern_lexicon`**
  (`sensitivity_tier = 'sealed'` for identifiers, `'restricted'` for vulnerabilities), `is_case_specific = true`.
- Several net-new categories are **inference-heavy** (mental-health state, "manic/depressive" markers,
  pronoun I-talk). These are flagged `bias_caution = true` and MUST run symmetrically on all parties.

## Sources mined (citations)
- **S-A** `.memsearch/memory/2026-06-01.md` (densest digest; mostly recounts the already-coded
  `seed-patterns.ts` port — little net-new, see note §6).
- **S-B** `dev-resources/Archives/dial-stack/utilities/apps/ConflictAnalysisApp/docs/Beautiful we're going to put all of that into a do....md` (LIWC-modeled blueprint — the richest net-new vein).
- **S-C** `.../ConflictAnalysisApp/docs/Analysis library.md` (JSON pattern dump w/ extra category buckets).
- **S-D** `.../ConflictAnalysisApp/docs/conversation_analysis_report.md` (case-specific narrative → lexicon).
- **S-E** `.../Narcissistic-Abuse-AI-Configs/.../family-navigator.md` (flying-monkeys / family-system roles).
- **S-F** `.../dial-stack/utilities/apps/ml-nlp/Tether/README.md` (covert-abuse multi-label taxonomy).
- **S-G** `C:/Users/matts/.claude/skills/manipulation-patterns/SKILL.md` (4-stage cycle, reverse-DARVO).

---

## A. NET-NEW `behavior_category` candidates (not in any G-list)

`category_id` snake_case. All negative rows carry `bias_caution=true` on their patterns.
`mcl_factor` codes are **canonical** (a–l, MCL 722.23; j=facilitation, k=domestic violence).

| # | category_id | label | polarity | default_severity | mcl_factors | source | notes / why net-new |
|---|---|---|---|---|---|---|---|
| 1 | `feigning_incompetence` | Weaponized / strategic incompetence | negative | 5 | {c,j} | S-B,S-C | "playing dumb" to offload labor & parenting duties — no analogue in any list |
| 2 | `defensiveness_evasion` | Extreme defensiveness / accountability evasion | negative | 6 | {f} | S-B | pre-DARVO over-reaction to non-accusatory questions; **bias_caution: overlaps darvo_attack — do NOT double-count** |
| 3 | `social_media_deception` | Platform-denial / contradiction deception | negative | 6 | {f} | S-B,S-C | "I don't even use Snapchat / you can check my phone"; pairs w/ contradiction detector |
| 4 | `last_minute_changes` | Manufactured instability / schedule sabotage | negative | 6 | {j} | S-B,S-C | distinct from neutral `scheduling`; weaponized cancellation to destabilize co-parenting |
| 5 | `emotional_dysregulation` | Manic/depressive linguistic markers | neutral | 0 | {g} | S-C | LIWC clinical-state inference; **HIGH bias_caution — never a misconduct finding, relevance/health signal only** |
| 6 | `i_talk_marker` | First-person-singular over-use (LIWC) | linguistic_marker | 0 | {} | S-B,S-C | high I-talk ↔ self-preoccupation/victimhood/grandiosity; G5 had negation/intensity but NOT pronoun markers |
| 7 | `you_talk_marker` | Second-person accusatory over-use (LIWC) | linguistic_marker | 0 | {} | S-B,S-C | you-talk + blame ↔ projection/accusation co-occurrence flag |
| 8 | `projection` | Accusing target of the accuser's own conduct | negative | 7 | {f} | S-B,S-F | "abuser (as projection)"; Tether lists Projection as standalone multi-label; no standalone row exists |
| 9 | `guilt_tripping` | Guilt / FOG (Fear-Obligation-Guilt) leverage | negative | 6 | {f,k} | S-F | Tether standalone; existing debt_reminders/excessive_gratitude cover obligation, not FOG-guilt |
| 10 | `feigned_concern` | Faux-worry used to degrade / position | negative | 6 | {f,j} | S-B | "I'm worried about him" weaponized to smear; sub of character_assassination/smear |
| 11 | `flying_monkeys` | Proxy abuse via recruited third parties | negative | 7 | {j,k} | S-E,S-G | named construct distinct from triangulation/coordinated_abuse; also a recovery target |
| 12 | `devaluation` | Devalue phase (criticism/contempt/withdrawal) | negative | 7 | {a,f} | S-G | abuse-cycle stage 2 — only love_bombing(idealize)/hoovering coded; devaluation missing |
| 13 | `discard` | Discard phase (abandonment threat / new supply) | negative | 7 | {a,j} | S-G | abuse-cycle stage 3; "new supply", sudden coldness; missing from all lists |
| 14 | `child_endangerment` | Substance-use + child-present co-occurrence | negative | 9 | {c,g,k} | S-C,S-D | DUI w/ child in car co-occurrence detector; distinct from substance_* lexical |
| 15 | `autism_weaponization` | Weaponizing child's diagnosis vs other parent | negative | 8 | {a,c,j} | S-C,S-D | "you can't handle his autism" + appointment-blocking; finer than special_needs/medical_abuse; **child's specific condition → restricted lexicon** |
| 16 | `block_unblock_cycle` | Intermittent contact control (punish/reward) | negative | 7 | {j,k} | S-D | strategic blocking↔unblocking cycle = intermittent reinforcement; finer than gatekeeping |
| 17 | `recovery_phase` | Manipulative calm after escalation | neutral | 3 | {l} | S-F | Tether "Recovery Phase"; the false-calm before hoover; cycle-tracking marker |
| 18 | `word_salad` | Deliberate confusion / obscure language | negative | 5 | {l} | S-F | Tether "Obscure Language"; confusion-by-design, finer than `circular` |
| 19 | `dismissiveness` | Minimization / shutdown / invalidation cluster | negative | 5 | {f} | S-F | Tether multi-label; overlaps `minimizing` — fold as alias unless multi-label kept separate |
| 20 | `selective_amnesia` | Convenient forgetting / memory denial | negative | 6 | {f} | S-B | "I forgot / can't remember / misremembering" as denial tactic; sub-lane of gaslighting + feigning_incompetence |

### A-mcl (suggested `behavior_category_mcl` rows, corrected canonical factors)
```
feigning_incompetence: c(medium,F), j(medium,T 'offloads parenting')
defensiveness_evasion:  f(high,F)
social_media_deception: f(high,F 'deception → moral fitness')
last_minute_changes:    j(high,T 'impairs co-parenting reliability')
emotional_dysregulation:g(high,F 'health factor — relevance only, NOT misconduct')
projection:             f(high,F)
guilt_tripping:         f(medium,F), k(medium,T 'coercive-control lane')
feigned_concern:        f(medium,F), j(medium,T)
flying_monkeys:         j(high,T), k(high,T)
devaluation:            a(high,F 'erodes emotional ties'), f(high,F)
discard:                a(high,F), j(medium,T)
child_endangerment:     c(high,F), g(high,T 'safety'), k(high,T 'endangerment=DV lane')
autism_weaponization:   a(high,F), c(high,T 'medical care'), j(high,T)
block_unblock_cycle:    j(high,T), k(medium,T)
word_salad:             l(low,F)
selective_amnesia:      f(high,F)
```

---

## B. NET-NEW `detection_pattern` rows (generic phrases — all `bias_caution=true`)

`match_type='literal'` unless noted. None contain names/identifiers.

### B1 — defensiveness_evasion (S-B)
| pattern | severity |
|---|---|
| `why are you attacking me` | 7 |
| `i can't believe you're asking me that` | 6 |
| `after everything i do for you` | 7 |
| `here we go again` | 5 |
| `i don't have to explain myself to you` | 7 |
keywords[]: {attacked, judging, interrogating, accusing, seriously, unbelievable}

### B2 — reactive_abuse "gotcha" sub-patterns (extends existing `reactive_abuse`; phrases net-new) (S-B,S-C)
| pattern | severity |
|---|---|
| `see, you're losing it` | 8 |
| `this is what i have to deal with` | 7 |
| `you're the crazy one` | 8 |
| `i'm going to record this` | 8 |
| `look at you, you're having an episode` | 9 |
| `what are you going to do about it` | 7 |
| `see? this is why no one likes you` | 8 |
| `look at you, getting all worked up` | 7 |
condescending-term keywords (provocation): {buddy, sweetie, pal}; dismissive-laughter-in-reply: {lol, lmao, haha}

### B3 — feigning_incompetence (S-B,S-C)
| pattern | severity |
|---|---|
| `i'm not smart like you` | 5 |
| `you know i'm bad at this stuff` | 5 |
| `i never graduated, what do you expect` | 5 |
| `just tell me what to do` | 4 |
keywords[]: {dumb, "don't know how", "don't understand", confused, forgot, "can't remember"}

### B4 — social_media_deception + contradiction (S-B,S-C)
| pattern | severity |
|---|---|
| `i don't even use snapchat` | 6 |
| `i never send pictures` | 6 |
| `you can check my phone` | 5 |
salacious_content keywords: {nudes, pics, pictures, sexy, hot, videos, selfie}
> Pairs with the **platform-denial regex** (net-new contradiction detector): prior mention of
> `\b(snap|snapchat)\b` AND later `(?i)\b(i don'?t|i never)\s+(use|have)\s+snap(chat)?\b` → contradiction flag.

### B5 — last_minute_changes (S-B,S-C)
| pattern | severity |
|---|---|
| `change of plans` | 5 |
| `something came up` | 5 |
| `have to cancel` | 6 |
| `we're not doing that anymore` | 7 |
| `you'll have to figure it out` | 7 |
keywords[]: {"can't make it", "not going to work", "i decided to do"}

### B6 — child_endangerment (DUI-minimization; co-occurrence) (S-C,S-D)
| pattern | severity |
|---|---|
| `i only had one` | 7 |
| `i'm fine to drive` | 9 |
| `i can handle it` | 6 |
| `stop worrying` | 5 |
child_endangerment_flags (co-occur w/ substance_alcohol): {drive, driving, car, "pick up", daycare, school}

### B7 — emotional_dysregulation markers — severity 0, **bias_caution HIGH** (S-C)
| subcategory | keywords/phrases | sev |
|---|---|---|
| manic_indicators | {"brilliant idea", "i can solve everything", pressured_speech, grandiosity} | 0 |
| depressive_indicators | {"what's the point", "it will never get better", "i'm a failure", "i can't do anything right"} | 0 |

### B8 — gaslighting / selective_amnesia extra phrasings (extend existing gaslighting) (S-B)
| pattern | severity |
|---|---|
| `you're twisting my words` | 7 |
| `you have issues` | 6 |
| `that's not how it happened` | 7 |
| `you're misremembering` | 8 |
| `you're confused` | 7 |
keywords[]: {forgetting, confused, misremembering}

### B9 — projection / feigned_concern character-attack phrasings (S-B)
| category | pattern | severity |
|---|---|---|
| feigned_concern | `i'm worried about him` | 6 |
| projection | `he's obsessed with me` | 7 |
| projection | `she is completely unstable` | 7 |
| character_assassination | `everyone can see what you're like` | 7 |
mental_health_weapon keywords (net-new vs G4): {weirdo, psycho, loser, pathetic, fool, liar}
severe-abuse keywords (net-new rows): {"bitch made", "ain't shit", "good for nothing", motherfucker, "piece of shit"}

### B10 — devaluation / discard cycle sub-patterns (S-G)
| category | pattern | severity |
|---|---|---|
| devaluation | `moving the goalposts` / "nothing you do is good enough" | 7 |
| devaluation | `nothing is ever good enough` | 6 |
| discard | `new supply` (third-party replacement reference) | 7 |
| discard | `blaming you for the relationship failure` | 6 |

---

## C. NET-NEW `pattern_lexicon` (SEALED / RESTRICTED — court-safety)

| lexicon_type | term | variants | sensitivity_tier | relevance_signal | mcl_factors | source | note |
|---|---|---|---|---|---|---|---|
| party_identifier | (opposing co-parent given name: **"Katrina"**) | {} | **sealed** | subject_of_proceeding | {} | S-D | NET-NEW — only child names sealed so far; adult-party name must NEVER be plaintext detection_pattern |
| vulnerability_trigger | (child's specific condition tied to named child: "his autism") | {autistic, "his autism", "sensory"} | **restricted** | child_health_vulnerability | {a,c} | S-C,S-D | generic clinical "autism/autistic/sensory" stays in `special_needs` detection_pattern; only the **named-child tie** is restricted |
| vulnerability_trigger | (named-target homophobic epithets directed at the user) | {faggot, fagget, "sick fagot"} | **restricted** | identity_based_slur_at_party | {f,k} | S-D | generic identity-slur regex stays in `character_assassination`; the **named-target usage record** is restricted |

> Already-sealed (NOT net-new, for cross-ref): `kailah`/`kyla` (child) and `huckleberry junction`/`huck's`
> (infidelity place) — present in G2/G4/G5.

---

## D. NET-NEW relationship-cycle / methodology / scoring notes (no single row — meta)

1. **4-stage Narcissistic Abuse Cycle as a temporal SEQUENCE** (S-G): `idealization(love_bombing) →
   devaluation → discard → hoovering`, **repeating**. Individual stages exist as categories, but the
   cycle *edge/sequence* + court-context rule ("expect **hoovering before mediation/court dates**;
   performative 'good behavior' for the court") is net-new. → model as a `pattern_sequence` / cycle edge.
2. **3-step Reactive-Abuse Cycle** (S-C): `provocation("the Poke") → reaction → gotcha`. Provocation
   triggers = {character_assassination, infidelity_accusations, feigned_incompetence}; reaction
   indicators = {angry, upset, pissed, exclamation_points, all_caps}; gotcha = the B2 phrases. Net-new
   ordered triple.
3. **FOG framework** (Fear / Obligation / Guilt) (S-F) as an umbrella over guilt_tripping + debt_reminders.
4. **Cross-thread contradiction detection** (S-B): compare `User↔Subject` vs `Subject↔Friend` threads,
   flag logical opposites (e.g. "no money for bills" vs "bought designer shoes"). Extends G5 contradiction
   logic with the *multi-thread* comparison + designer-shoes worked example.
5. **LIWC methodology** as the authoring frame for the whole lexicon (pronoun analysis, certainty,
   I-talk/you-talk) (S-B) — justifies the §A6/§A7 pronoun markers.
6. **Reverse-DARVO strategy** (S-G) — a *response* playbook, not a detection row; note for the analysis app.
7. **Tether risk-estimation tiers** (S-F): `early | escalating | high-risk` + abuse score 0–100 +
   motif tags for repeat patterns — an alternative escalation axis to G5's `negative|hostile|abusive`.
8. **Case escalation timeline** (S-D, case-specific): 2018-19 early manipulation → 2020-21 post-birth-control
   infidelity → 2022-23 CPS/custody weaponization → 2024 violent threats. (Timeline lane, not a pattern row.)

---

## §6 Note — S-A (2026-06-01 digest) yielded ~0 net-new
The densest digest is a play-by-play of porting the **already-coded** `seed-patterns.ts` (the 191/253/300+
counts, SetFit/GLiNER2/Unsloth training-data plans). Its only forensic-indicator nugget is the
`sms_backup_parser.py` "Blocked Call Indicators" — already represented by `communication_blocking`
(G5). No net-new behavior categories. Recorded here so the vein isn't re-mined.
