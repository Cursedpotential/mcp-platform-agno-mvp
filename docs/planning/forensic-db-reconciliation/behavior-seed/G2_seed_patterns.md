# G2 — Behavioral Pattern Seed (from `seed-patterns.ts`)

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
> Source artifact: `dev-resources/Archives/Agno-MCP-Platform-alpha/.claude/worktrees/migration-plan-v8/server/scripts/seed-patterns.ts`
> Source legacy table: `behavioralPatterns` (SQL.js, owner userId=1). Original struct `{name, category, pattern, description, severity}`.
> **Total patterns in source: 253** across **25 categories**.
> **Routing result:** 251 → `detection_pattern` (generic) · 2 → `pattern_lexicon` (sealed child identifiers: `kailah`, `kyla`).

## Court-safety / forensic disclaimers
- All `detection_pattern` rows below are **hypotheses, not facts** → every negative pattern carries `bias_caution = true`.
- Source patterns are **literal case-insensitive substrings** → `match_type = 'literal'` for all 253 (one templated pattern `that's your [condition] talking` kept verbatim as literal; flag for later regex conversion).
- Severity is captured **verbatim** from source. `score` (NOT NULL, 1–10) is derived as `max(1, severity)` so the 0-severity linguistic/neutral markers remain insertable; original `severity` preserved unchanged.
- Child names (`kailah`, `kyla`) routed to `pattern_lexicon` with `sensitivity_tier='sealed'`, `is_case_specific=true`, `lexicon_type='child_identifier'` — **NEVER plaintext in `detection_pattern`**. Generic family phrases (`my daughter`, `our daughter`, `the baby`, `the kid`) are non-identifying templates → kept in `detection_pattern`.

---

## `detection_pattern_set` — seed ONE active set

| col | value |
|---|---|
| name | `behavioral-seed-darvo-coercion` |
| version | `1.0.0` |
| source | `seed-patterns.ts` |
| source_artifact | `.../migration-plan-v8/server/scripts/seed-patterns.ts` |
| description | Surface-level literal pattern library for preliminary behavioral screening (DARVO, coercive-control, manipulation, linguistic markers). MCL linking + deep analysis deferred to meta-analysis phase. |
| is_active | `true` |
| authored_perspective | `owner_protective_parent` |
| valid_from | `now()` |

`UNIQUE(name, version)` satisfied. All `detection_pattern.pattern_set_id` and `pattern_lexicon.pattern_set_id` below FK to this single set.

---

## `behavior_category` — 25 rows

`category_id` = source snake_case key (already snake_case). `source='seed-patterns.ts'`. `default_severity` = modal/representative severity from members. `mcl_factors` = hypothesized MCL 722.23 best-interest factors. `polarity` per enum.

| category_id | label | polarity | default_severity | mcl_factors | is_case_specific | notes |
|---|---|---|---|---|---|---|
| gaslighting | Gaslighting | negative | 8 | {g,k} | false | reality-denial; psychological abuse |
| blame_shifting | Blame Shifting | negative | 7 | {f} | false | causation/fault attribution |
| minimizing | Minimizing | negative | 6 | {f} | false | trivializing victim experience |
| circular | Circular Arguments | negative | 5 | {l} | false | conversation derailment/termination |
| darvo_deny | DARVO – Deny | negative | 8 | {f} | false | DARVO stage 1 |
| darvo_attack | DARVO – Attack | negative | 9 | {f,k} | false | DARVO stage 2 |
| darvo_reverse | DARVO – Reverse Victim/Offender | negative | 10 | {f,k} | false | DARVO stage 3 |
| overelaboration | Overelaboration / Over-justification | linguistic_marker | 7 | {l} | false | deception/anxiety + location reporting marker |
| love_bombing | Love Bombing | negative | 6 | {l} | false | manipulation via excessive affection |
| excessive_gratitude | Excessive Gratitude | negative | 6 | {l} | false | obligation/debt creation |
| debt_reminders | Debt Reminders | negative | 7 | {f} | false | leveraging past favors |
| savior_complex | Savior Complex | negative | 8 | {f,k} | false | isolation + dependency creation |
| substance_alcohol | Substance – Alcohol (mentions) | neutral | 0 | {g} | false | neutral lexical detection, sev 0 |
| substance_weaponized | Substance – Weaponized | negative | 9 | {f,g} | false | drug slurs / invalidation |
| adderall_control | Adderall / Medication Control | negative | 7 | {c,g,k} | false | medication rationing/control |
| infidelity | Infidelity | negative | 8 | {f} | false | betrayal mentions + denial |
| financial_weaponized | Financial – Weaponized | negative | 8 | {c,f} | false | provider/contribution attacks |
| sexual_shaming | Sexual Shaming | negative | 9 | {f,k} | false | sexual slurs / degradation |
| parental_alienation | Parental Alienation | negative | 10 | {a,j,k} | true | child-rejection + access framing (case-specific) |
| medical_abuse | Medical Abuse | negative | 9 | {c,g,k} | false | diagnosis weaponization / capacity denial |
| reproductive_coercion | Reproductive Coercion | negative | 10 | {f,k} | false | pregnancy coercion / custody threats |
| victim_deference | Power Asymmetry – Victim Deference | linguistic_marker | 6 | {k} | false | permission/approval-seeking marker |
| abuser_directives | Power Asymmetry – Abuser Directives | negative | 7 | {k} | false | command/surveillance language |
| certainty_absolutes | Statistical – Certainty/Absolutes | linguistic_marker | 0 | {l} | false | absolute-language marker, sev 0 |
| hedge_words | Statistical – Hedge Words | linguistic_marker | 0 | {l} | false | uncertainty-language marker, sev 0 |

### `behavior_category_mcl` — factor linkage (hypotheses)

| category_id | factor_code | weight | is_critical | note |
|---|---|---|---|---|
| gaslighting | g | high | false | erodes mental health |
| gaslighting | k | medium | false | coercive-control / DV signal |
| blame_shifting | f | medium | false | moral fitness |
| minimizing | f | low | false | moral fitness |
| circular | l | low | false | other factor |
| darvo_deny | f | medium | false | moral fitness |
| darvo_attack | f | high | false | moral fitness |
| darvo_attack | k | medium | false | DV pattern |
| darvo_reverse | f | high | true | offender/victim inversion |
| darvo_reverse | k | high | true | DV pattern |
| overelaboration | l | low | false | linguistic marker |
| love_bombing | l | low | false | manipulation marker |
| excessive_gratitude | l | low | false | obligation marker |
| debt_reminders | f | medium | false | moral fitness |
| savior_complex | f | medium | false | moral fitness |
| savior_complex | k | high | false | isolation = coercive control |
| substance_alcohol | g | low | false | health (neutral mention) |
| substance_weaponized | f | medium | false | moral fitness |
| substance_weaponized | g | medium | false | health weaponization |
| adderall_control | c | medium | false | medical care control |
| adderall_control | g | medium | false | health |
| adderall_control | k | high | false | coercive control |
| infidelity | f | medium | false | moral fitness |
| financial_weaponized | c | medium | false | capacity to provide |
| financial_weaponized | f | medium | false | moral fitness |
| sexual_shaming | f | high | false | moral fitness / degradation |
| sexual_shaming | k | medium | false | DV / emotional abuse |
| parental_alienation | a | high | true | emotional ties |
| parental_alienation | j | high | true | facilitation of other-parent relationship |
| parental_alienation | k | medium | false | DV / coercive control |
| medical_abuse | c | medium | false | medical care |
| medical_abuse | g | high | true | health weaponization |
| medical_abuse | k | high | false | coercive control |
| reproductive_coercion | f | high | true | moral fitness |
| reproductive_coercion | k | high | true | reproductive coercion = DV |
| victim_deference | k | medium | false | power asymmetry marker |
| abuser_directives | k | high | false | surveillance / coercive control |
| certainty_absolutes | l | low | false | linguistic marker |
| hedge_words | l | low | false | linguistic marker |

---

## `pattern_lexicon` — SEALED (routed out of `detection_pattern`)

`pattern_set_id` → seed set. `match_type='literal'`, `is_case_specific=true`, `sensitivity_tier='sealed'`, `source='seed-patterns.ts'`.

| lexicon_type | term | variants | relevance_signal | severity | mcl_factors | note (verbatim source name · description) |
|---|---|---|---|---|---|---|
| child_identifier | `kailah` | {`kyla`} | parental_alienation | 10 | {a,j,k} | `Alienation: Kailah` · "Child name mention" |
| child_identifier | `kyla` | {`kailah`} | parental_alienation | 10 | {a,j,k} | `Alienation: Kyla` · "Child name variant" |

---

## `detection_pattern` — 251 rows, grouped by category (verbatim)

Columns: **name** · **pattern** (verbatim, literal) · **description** (verbatim) · **severity** (verbatim) · score=`max(1,severity)`. All rows: `match_type='literal'`, `bias_caution=true`, `is_case_specific=false`, `source='seed-patterns.ts'`, `is_active=true`. (Cross-category duplicate patterns e.g. `that never happened`, `you're crazy`, `you're just high`, `this is the drugs talking`, `always`, `everything` are permitted by `UNIQUE(pattern_set_id,category_id,match_type,pattern)`.)

### gaslighting (10) — severity default 8

| name | pattern | description | severity |
|---|---|---|---|
| Gaslighting: Denial | `i never said that` | Denying previous statements | 8 |
| Gaslighting: Imagined | `you imagined` | Suggesting victim fabricated memories | 8 |
| Gaslighting: Paranoid | `you're paranoid` | Labeling concerns as paranoia | 7 |
| Gaslighting: Never Happened | `that never happened` | Denying events | 9 |
| Gaslighting: No One Believe | `no one will believe` | Threatening credibility | 9 |
| Gaslighting: Crazy | `you're crazy` | Questioning sanity | 9 |
| Gaslighting: Just High | `you're just high` | Blaming substance use | 8 |
| Gaslighting: Just Kidding | `just kidding` | Dismissing as joke | 6 |
| Gaslighting: Overreacting | `you're overreacting` | Invalidating emotions | 7 |
| Gaslighting: Drugs Talking | `this is the drugs talking` | Attributing to substances | 8 |

### blame_shifting (7)

| name | pattern | description | severity |
|---|---|---|---|
| Blame: Your Fault | `this is your fault` | Direct blame | 7 |
| Blame: You Made Me | `you made me` | Claiming causation | 8 |
| Blame: Because of You | `because of you` | Attributing outcomes | 7 |
| Blame: You Started | `you started this` | Initiation claim | 6 |
| Blame: Always Do This | `you always do this` | Pattern accusation | 7 |
| Blame: If You Hadn't | `if you hadn't` | Conditional fault | 7 |
| Blame: Made Me Do | `look what you made me do` | Forced action claim | 9 |

### minimizing (8)

| name | pattern | description | severity |
|---|---|---|---|
| Minimizing: Not Big Deal | `not a big deal` | Trivializing | 6 |
| Minimizing: Too Sensitive | `you're too sensitive` | Sensitivity attack | 7 |
| Minimizing: Calm Down | `calm down` | Dismissing emotions | 5 |
| Minimizing: Being Dramatic | `you're being dramatic` | Drama accusation | 6 |
| Minimizing: Get Over It | `get over it` | Demanding move on | 7 |
| Minimizing: Making Scene | `stop making a scene` | Scene shaming | 6 |
| Minimizing: Just Joke | `it was just a joke` | Joke defense | 6 |
| Minimizing: Relax | `relax` | Dismissal | 5 |

### circular (7)

| name | pattern | description | severity |
|---|---|---|---|
| Circular: What's Point | `what even is the point` | Point dismissal | 5 |
| Circular: Not The Point | `that's not the point` | Point shifting | 6 |
| Circular: Keep Changing | `you keep changing` | Changing accusation | 6 |
| Circular: Know What I Mean | `you know what i mean` | Vague understanding | 5 |
| Circular: Anyway | `anyway` | Termination | 5 |
| Circular: Whatever | `whatever` | Dismissal | 5 |
| Circular: Not High School | `we're not in high school` | Maturity shaming | 6 |

### darvo_deny (7)

| name | pattern | description | severity |
|---|---|---|---|
| DARVO: I Never | `i never` | Denial | 8 |
| DARVO: I Didn't | `i didn't` | Denial | 8 |
| DARVO: Never Happened | `that never happened` | Event denial | 9 |
| DARVO: Not True | `that's not true` | Truth denial | 8 |
| DARVO: Making Up | `you're making that up` | Fabrication accusation | 9 |
| DARVO: Would Never | `i would never` | Character defense | 7 |
| DARVO: That's Lie | `that's a lie` | Lie accusation | 9 |

### darvo_attack (9)

| name | pattern | description | severity |
|---|---|---|---|
| DARVO: You're Crazy | `you're crazy` | Sanity attack | 9 |
| DARVO: You're Lying | `you're lying` | Liar accusation | 9 |
| DARVO: You're Abusive | `you're the abusive one` | Abuser projection | 10 |
| DARVO: You're Manipulating | `you're manipulating` | Manipulation accusation | 9 |
| DARVO: You're Gaslighting | `you're gaslighting me` | Gaslighting accusation | 10 |
| DARVO: You're Toxic | `you're toxic` | Toxic label | 9 |
| DARVO: You're Problem | `you're the problem` | Problem projection | 9 |
| DARVO: You're Unstable | `you're unstable` | Instability claim | 9 |
| DARVO: You're Delusional | `you're delusional` | Delusion accusation | 9 |

### darvo_reverse (8)

| name | pattern | description | severity |
|---|---|---|---|
| DARVO: I'm Victim | `i'm the victim here` | Victim claim | 10 |
| DARVO: You're Attacking | `you're attacking me` | Attack claim | 10 |
| DARVO: You're Abusing | `you're abusing me` | Abuse claim | 10 |
| DARVO: I'm Being Hurt | `i'm the one being hurt` | Hurt claim | 10 |
| DARVO: You're Hurting | `you're hurting me` | Hurt accusation | 10 |
| DARVO: I'm Scared | `i'm scared of you` | Fear claim | 10 |
| DARVO: You're Aggressor | `you're the aggressor` | Aggressor label | 10 |
| DARVO: Need Protection | `i need protection from you` | Protection need | 10 |

### overelaboration (22) — polarity linguistic_marker

| name | pattern | description | severity |
|---|---|---|---|
| Overelaboration: I'm At | `i'm at` | Location reporting | 7 |
| Overelaboration: Still At | `i'm still at` | Continued presence | 7 |
| Overelaboration: Heading To | `i'm heading to` | Movement reporting | 7 |
| Overelaboration: Will Be At | `i'll be at` | Future location | 7 |
| Overelaboration: On Way | `i'm on my way to` | In-transit | 7 |
| Overelaboration: Just Left | `i just left` | Departure | 7 |
| Overelaboration: Just Arrived | `i just arrived at` | Arrival | 7 |
| Overelaboration: Left At | `i left at` | Departure time | 7 |
| Overelaboration: Back By | `i'll be back by` | Return time | 7 |
| Overelaboration: Been Here Since | `i've been here since` | Duration | 7 |
| Overelaboration: Done In | `i'll be done in` | Completion time | 7 |
| Overelaboration: Doing Because | `i'm doing this because` | Justification | 8 |
| Overelaboration: Had To | `i had to` | Necessity | 8 |
| Overelaboration: Needed To | `i needed to` | Need explanation | 8 |
| Overelaboration: Reason Is | `the reason is` | Reasoning | 8 |
| Overelaboration: I'm Just | `i'm just` | Minimizing justification | 7 |
| Overelaboration: Was Just | `i was just` | Past justification | 7 |
| Overelaboration: Before You Ask | `before you ask` | Pre-emptive | 8 |
| Overelaboration: Know Wondering | `i know you're wondering` | Anticipating | 8 |
| Overelaboration: Just So Know | `just so you know` | Pre-emptive info | 7 |
| Overelaboration: For Record | `for the record` | Documenting | 7 |
| Overelaboration: To Be Clear | `to be clear` | Over-clarifying | 7 |

### love_bombing (12)

| name | pattern | description | severity |
|---|---|---|---|
| Love Bombing: Perfect | `perfect` | Excessive praise | 5 |
| Love Bombing: Amazing | `amazing` | Excessive praise | 5 |
| Love Bombing: Soulmate | `soulmate` | Premature commitment | 6 |
| Love Bombing: Can't Live Without | `can't live without you` | Dependency claim | 7 |
| Love Bombing: Always | `always` | Forever promise | 5 |
| Love Bombing: Forever | `forever` | Forever promise | 5 |
| Love Bombing: Everything | `everything` | Totality claim | 5 |
| Love Bombing: Desperate | `desperate` | Intensity | 6 |
| Love Bombing: Need You | `need you` | Dependency | 6 |
| Love Bombing: Only One Understands | `you're the only one who understands me` | Unique understanding | 6 |
| Love Bombing: Never Felt This Way | `i've never felt this way before` | Uniqueness claim | 6 |
| Love Bombing: Give Everything | `i want to give you everything` | Grand promise | 6 |

### excessive_gratitude (9)

| name | pattern | description | severity |
|---|---|---|---|
| Gratitude: Owe Everything | `i owe you everything` | Creating obligation | 6 |
| Gratitude: Never Repay | `i could never repay you` | Unpayable debt | 6 |
| Gratitude: Don't Deserve | `i don't deserve you` | False humility | 5 |
| Gratitude: Done So Much | `you've done so much for me` | Emphasizing contributions | 5 |
| Gratitude: So Grateful | `i'm so grateful` | Excessive gratitude | 4 |
| Gratitude: Thank Everything | `thank you for everything` | Blanket gratitude | 4 |
| Gratitude: What Would I Do | `i don't know what i'd do without you` | Dependency | 6 |
| Gratitude: Saved Me | `you saved me` | Savior positioning | 7 |
| Gratitude: Owe Life | `i owe you my life` | Extreme debt | 7 |

### debt_reminders (6)

| name | pattern | description | severity |
|---|---|---|---|
| Debt: Remember When | `remember when i` | Past favor reminder | 7 |
| Debt: After All Done | `after all i've done` | Leveraging past | 8 |
| Debt: Was There | `i was there for you when` | Support reminder | 7 |
| Debt: Don't Forget | `don't forget i` | Ensuring memory | 7 |
| Debt: I Helped | `i helped you` | Assistance reminder | 6 |
| Debt: I Gave | `i gave you` | Gift reminder | 6 |

### savior_complex (14)

| name | pattern | description | severity |
|---|---|---|---|
| Savior: Protect You | `i'll protect you` | Protector positioning | 7 |
| Savior: Keep Safe | `i'll keep you safe` | Safety promise | 7 |
| Savior: Won't Let Hurt | `i won't let anyone hurt you` | Protection claim | 7 |
| Savior: You Need Me | `you need me` | Dependency claim | 8 |
| Savior: Take Care | `i'll take care of you` | Caretaking promise | 6 |
| Savior: Fix This | `i'll fix this` | Problem-solver | 6 |
| Savior: Let Me Handle | `let me handle it` | Control taking | 6 |
| Savior: Make Better | `i'll make it better` | Solution promise | 5 |
| Savior: Trust To Protect | `trust me to protect you` | Trust demand | 7 |
| Savior: Everyone Else Hurt | `everyone else will hurt you` | World as dangerous | 9 |
| Savior: World Dangerous | `the world is dangerous` | Fear creation | 8 |
| Savior: Can't Trust Anyone | `you can't trust anyone but me` | Trust destruction | 9 |
| Savior: Out To Get | `they're all out to get you` | Paranoia creation | 9 |
| Savior: Only One Cares | `i'm the only one who cares` | Exclusive care | 8 |

### substance_alcohol (14) — polarity neutral, severity 0 (lexical detection)

| name | pattern | description | severity |
|---|---|---|---|
| Substance: Drink | `drink` | Alcohol mention | 0 |
| Substance: Drank | `drank` | Alcohol mention | 0 |
| Substance: Drunk | `drunk` | Intoxication | 0 |
| Substance: Buzzed | `buzzed` | Intoxication | 0 |
| Substance: Tipsy | `tipsy` | Intoxication | 0 |
| Substance: Wasted | `wasted` | Intoxication | 0 |
| Substance: Bottle | `bottle` | Alcohol container | 0 |
| Substance: Wine | `wine` | Alcohol type | 0 |
| Substance: Beer | `beer` | Alcohol type | 0 |
| Substance: Liquor | `liquor` | Alcohol type | 0 |
| Substance: Vodka | `vodka` | Alcohol type | 0 |
| Substance: Tequila | `tequila` | Alcohol type | 0 |
| Substance: Hungover | `hungover` | After-effects | 0 |
| Substance: Fireball | `fireball` | Alcohol brand | 0 |

### substance_weaponized (8)

| name | pattern | description | severity |
|---|---|---|---|
| Substance Weapon: Crackhead | `crackhead` | Drug slur | 9 |
| Substance Weapon: Tweaker | `tweaker` | Drug slur | 9 |
| Substance Weapon: Addict | `addict` | Drug label | 8 |
| Substance Weapon: Junkie | `junkie` | Drug slur | 9 |
| Substance Weapon: User | `user` | Drug label | 7 |
| Substance Weapon: Just High | `you're just high` | Invalidation | 8 |
| Substance Weapon: On Something | `are you on something` | Accusation | 8 |
| Substance Weapon: Drugs Talking | `this is the drugs talking` | Invalidation | 8 |

### adderall_control (10)

| name | pattern | description | severity |
|---|---|---|---|
| Adderall: Adderall | `adderall` | Medication mention | 7 |
| Adderall: Addy | `addy` | Medication slang | 7 |
| Adderall: Pills | `pills` | Medication generic | 6 |
| Adderall: Script | `script` | Prescription | 6 |
| Adderall: Share | `share` | Medication sharing | 7 |
| Adderall: Split | `split` | Medication splitting | 7 |
| Adderall: Your Turn | `your turn` | Medication rationing | 8 |
| Adderall: How Many | `how many did you take` | Medication monitoring | 8 |
| Adderall: Holding For You | `i'm holding onto them for you` | Medication control | 9 |
| Adderall: Can't Control | `you can't control yourself` | Control justification | 9 |

### infidelity (12)

| name | pattern | description | severity |
|---|---|---|---|
| Infidelity: Cheating | `cheating` | Infidelity mention | 8 |
| Infidelity: Cheated | `cheated` | Infidelity past | 8 |
| Infidelity: Slept With | `slept with` | Sexual involvement | 8 |
| Infidelity: Affair | `affair` | Relationship betrayal | 9 |
| Infidelity: Secret | `secret` | Hidden behavior | 6 |
| Infidelity: Seeing Someone | `seeing someone` | Other relationship | 8 |
| Infidelity: Loyal | `loyal` | Loyalty claim | 5 |
| Infidelity: Faithful | `faithful` | Faithfulness claim | 5 |
| Infidelity: Just Friend | `he's just a friend` | Denial | 6 |
| Infidelity: Just Work | `we just work together` | Denial | 6 |
| Infidelity: Being Jealous | `you're being jealous` | Invalidation | 7 |
| Infidelity: Don't Trust | `why don't you trust me` | Trust questioning | 7 |

### financial_weaponized (4)

| name | pattern | description | severity |
|---|---|---|---|
| Financial Weapon: Don't Do Anything | `you don't do anything` | Contribution attack | 8 |
| Financial Weapon: I Work Hard | `i'm the one who works hard` | Effort comparison | 7 |
| Financial Weapon: What Do I Get | `what do i get out of this` | Transactional | 8 |
| Financial Weapon: Your Responsibility | `it's your responsibility to provide` | Obligation claim | 8 |

### sexual_shaming (11)

| name | pattern | description | severity |
|---|---|---|---|
| Sexual Shame: Slut | `slut` | Sexual slur | 10 |
| Sexual Shame: Whore | `whore` | Sexual slur | 10 |
| Sexual Shame: Pervert | `pervert` | Sexual slur | 9 |
| Sexual Shame: Disgusting | `disgusting` | Degradation | 8 |
| Sexual Shame: Sick | `sick` | Degradation | 8 |
| Sexual Shame: Nasty | `nasty` | Degradation | 8 |
| Sexual Shame: Freak | `freak` | Sexual slur | 9 |
| Sexual Shame: Used | `used` | Degradation | 9 |
| Sexual Shame: Cheap | `cheap` | Degradation | 8 |
| Sexual Shame: Everyone Leaves | `no wonder everyone leaves you` | Abandonment threat | 10 |
| Sexual Shame: To Think | `to think i ever did` | Regret expression | 9 |

### parental_alienation (6 in `detection_pattern`; 2 child-name rows → `pattern_lexicon`)

| name | pattern | description | severity |
|---|---|---|---|
| Alienation: Doesn't Want See | `doesn't want to see you` | Child rejection claim | 10 |
| Alienation: Protect From You | `i have to protect the children from you` | Protection justification | 10 |
| Alienation: My Daughter | `my daughter` | Possessive child reference | 8 |
| Alienation: Our Daughter | `our daughter` | Child reference | 7 |
| Alienation: The Baby | `the baby` | Child reference | 6 |
| Alienation: The Kid | `the kid` | Child reference | 6 |

> ROUTED OUT (sealed lexicon, see `pattern_lexicon` above): `Alienation: Kailah` (`kailah`, sev 10), `Alienation: Kyla` (`kyla`, sev 10).

### medical_abuse (15)

| name | pattern | description | severity |
|---|---|---|---|
| Medical: Need Meds | `you need your meds` | Medication control | 9 |
| Medical: Take Pills | `did you take your pills` | Medication monitoring | 8 |
| Medical: Not Thinking Clearly | `you're not thinking clearly` | Cognitive invalidation | 9 |
| Medical: Medication Talking | `it's the medication talking` | Invalidation | 9 |
| Medical: Can't Make Decisions | `you can't make decisions` | Capacity denial | 10 |
| Medical: Not Well Enough | `you're not well enough` | Health gatekeeping | 9 |
| Medical: Holding Meds | `i'm holding your meds` | Medication control | 10 |
| Medical: Can't Be Trusted | `you can't be trusted with` | Trust denial | 9 |
| Medical: Bipolar | `you're bipolar` | Diagnosis weaponization | 9 |
| Medical: Borderline | `you're borderline` | Diagnosis weaponization | 9 |
| Medical: Schizophrenic | `you're schizophrenic` | Diagnosis weaponization | 9 |
| Medical: Condition Talking | `that's your [condition] talking` | Invalidation | 9 |
| Medical: Having Episode | `you're having an episode` | Crisis claim | 9 |
| Medical: Need Hospitalized | `you need to be hospitalized` | Institutionalization threat | 10 |
| Medical: Unstable | `you're unstable` | Mental health attack | 9 |

> Note: `that's your [condition] talking` retains the literal `[condition]` placeholder verbatim. Flag for later `match_type='regex'` conversion (e.g. `that's your .* talking`).

### reproductive_coercion (13)

| name | pattern | description | severity |
|---|---|---|---|
| Reproductive: Want Pregnant | `i want you pregnant` | Pregnancy demand | 10 |
| Reproductive: Should Get Pregnant | `you should get pregnant` | Pregnancy pressure | 10 |
| Reproductive: Stop Birth Control | `stop taking birth control` | Contraception interference | 10 |
| Reproductive: Get You Pregnant | `i'll get you pregnant` | Pregnancy threat | 10 |
| Reproductive: Can't Leave Pregnant | `you can't leave if you're pregnant` | Pregnancy as trap | 10 |
| Reproductive: Baby Fix | `a baby will fix us` | Baby as solution | 9 |
| Reproductive: Owe Child | `you owe me a child` | Child as debt | 10 |
| Reproductive: Sabotaged | `i sabotaged your birth control` | Contraception sabotage | 10 |
| Reproductive: Take Baby | `i'll take the baby` | Custody threat | 10 |
| Reproductive: Never See Baby | `you'll never see the baby` | Access threat | 10 |
| Reproductive: Prove Unfit | `i'll prove you're unfit` | Fitness attack | 10 |
| Reproductive: Bad Mother | `you're a bad mother` | Parenting attack | 9 |
| Reproductive: Baby Doesn't Need | `the baby doesn't need you` | Necessity denial | 10 |

### victim_deference (9) — polarity linguistic_marker

| name | pattern | description | severity |
|---|---|---|---|
| Deference: If Okay | `if that's okay` | Permission seeking | 7 |
| Deference: If Don't Mind | `if you don't mind` | Permission seeking | 7 |
| Deference: Is Alright | `is that alright` | Approval seeking | 7 |
| Deference: Sorry | `sorry` | Apologetic | 6 |
| Deference: My Bad | `my bad` | Apologetic | 6 |
| Deference: Didn't Mean | `i didn't mean to` | Apologetic | 6 |
| Deference: I Apologize | `i apologize` | Apologetic | 6 |
| Deference: Hope Fine | `i hope that's fine` | Approval seeking | 7 |
| Deference: Let Me Know | `let me know if` | Deferential | 6 |

### abuser_directives (10)

| name | pattern | description | severity |
|---|---|---|---|
| Directive: Where Are You | `where are you` | Location demand | 8 |
| Directive: What Doing | `what are you doing` | Activity demand | 8 |
| Directive: Who With | `who are you with` | Company demand | 8 |
| Directive: Come Here | `come here` | Movement command | 7 |
| Directive: Go There | `go there` | Movement command | 7 |
| Directive: Do This | `do this` | Action command | 7 |
| Directive: Stop That | `stop that` | Prohibition command | 7 |
| Directive: Tell Me | `tell me` | Information demand | 7 |
| Directive: Show Me | `show me` | Proof demand | 8 |
| Directive: Prove It | `prove it` | Evidence demand | 8 |

### certainty_absolutes (10) — polarity linguistic_marker, severity 0

| name | pattern | description | severity |
|---|---|---|---|
| Certainty: Always | `always` | Absolute claim | 0 |
| Certainty: Never | `never` | Absolute claim | 0 |
| Certainty: Nothing | `nothing` | Absolute claim | 0 |
| Certainty: Everything | `everything` | Absolute claim | 0 |
| Certainty: Everyone | `everyone` | Absolute claim | 0 |
| Certainty: Nobody | `nobody` | Absolute claim | 0 |
| Certainty: Fact | `fact` | Certainty marker | 0 |
| Certainty: Obviously | `obviously` | Certainty marker | 0 |
| Certainty: Clearly | `clearly` | Certainty marker | 0 |
| Certainty: Literally | `literally` | Certainty marker | 0 |

### hedge_words (10) — polarity linguistic_marker, severity 0

| name | pattern | description | severity |
|---|---|---|---|
| Hedge: Maybe | `maybe` | Uncertainty marker | 0 |
| Hedge: Perhaps | `perhaps` | Uncertainty marker | 0 |
| Hedge: Possibly | `possibly` | Uncertainty marker | 0 |
| Hedge: Might | `might` | Uncertainty marker | 0 |
| Hedge: Could | `could` | Uncertainty marker | 0 |
| Hedge: I Think | `i think` | Uncertainty marker | 0 |
| Hedge: I Guess | `i guess` | Uncertainty marker | 0 |
| Hedge: Sort Of | `sort of` | Uncertainty marker | 0 |
| Hedge: Kind Of | `kind of` | Uncertainty marker | 0 |
| Hedge: Probably | `probably` | Uncertainty marker | 0 |

---

## Category counts (verbatim from source)

| category | count |
|---|---|
| gaslighting | 10 |
| blame_shifting | 7 |
| minimizing | 8 |
| circular | 7 |
| darvo_deny | 7 |
| darvo_attack | 9 |
| darvo_reverse | 8 |
| overelaboration | 22 |
| love_bombing | 12 |
| excessive_gratitude | 9 |
| debt_reminders | 6 |
| savior_complex | 14 |
| substance_alcohol | 14 |
| substance_weaponized | 8 |
| adderall_control | 10 |
| infidelity | 12 |
| financial_weaponized | 4 |
| sexual_shaming | 11 |
| parental_alienation | 8 (6 detection_pattern + 2 sealed lexicon) |
| medical_abuse | 15 |
| reproductive_coercion | 13 |
| victim_deference | 9 |
| abuser_directives | 10 |
| certainty_absolutes | 10 |
| hedge_words | 10 |
| **TOTAL** | **253** |
