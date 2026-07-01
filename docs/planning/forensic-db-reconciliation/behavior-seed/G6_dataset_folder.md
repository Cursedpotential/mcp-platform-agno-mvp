# G6 — behavioral_patterns_dataset (dedicated dataset folder)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_

**Source:** `behavioral_patterns_dataset` (`temp_patterns.json` + `unsloth_dataset.jsonl` + `generate_unsloth_data.cjs`)
**source_artifact:** `E:/AI_Workspace/Projects/behavioral_patterns_dataset/temp_patterns.json`

- `temp_patterns.json` — 191 structured pattern objects `{name,category,pattern,description,severity}` (JS-object style, eval-parsed).
- `unsloth_dataset.jsonl` — 191 labeled SFT examples; verified **fully derived** from temp_patterns (`input=pattern`, `output={name,category,description,severity}`) via `generate_unsloth_data.cjs`. No patterns/categories beyond temp_patterns.
- Mapping system instruction (from .cjs): *"Analyze the following text and extract the forensic behavioral pattern, category, and severity score (1-10) based on MCL 722.23 factors. Output a strict JSON object."*

**Pattern count: 191. Distinct categories: 37. match_type = literal for all (verbatim phrase/keyword triggers).**

Court-safety routing legend: **DP** = `detection_pattern` (bias_caution=true, treat as HYPOTHESIS); **LEX/sealed** = `pattern_lexicon` sensitivity_tier=sealed (identifiers, is_case_specific=true); **LEX/restricted** = `pattern_lexicon` sensitivity_tier=restricted (derogatory epithets / vulnerability triggers, is_case_specific=true).

## Patterns (verbatim)

| # | name | category | pattern | description | severity | polarity | route | sensitivity_tier | is_case_specific | routing reason |
|---|------|----------|---------|-------------|----------|----------|-------|------------------|------------------|----------------|
| 1 | Gaslighting: Denial | gaslighting | `i never said that` | Denying previous statements | 8 | negative | DP | — | false | generic manipulation phrase |
| 2 | Gaslighting: Imagined | gaslighting | `you imagined` | Suggesting victim fabricated memories | 8 | negative | DP | — | false | generic manipulation phrase |
| 3 | Gaslighting: Never Happened | gaslighting | `that never happened` | Denying events | 9 | negative | DP | — | false | generic manipulation phrase |
| 4 | Gaslighting: No One Believe | gaslighting | `no one will believe` | Threatening credibility | 9 | negative | DP | — | false | generic manipulation phrase |
| 5 | Gaslighting: Just Kidding | gaslighting | `just kidding` | Dismissing as joke | 6 | negative | DP | — | false | generic manipulation phrase |
| 6 | Gaslighting: Drugs Talking | gaslighting | `this is the drugs talking` | Attributing to substances | 8 | negative | DP | — | false | generic manipulation phrase |
| 7 | Blame: Your Fault | blame_shifting | `this is your fault` | Direct blame | 7 | negative | DP | — | false | generic manipulation phrase |
| 8 | Blame: You Made Me | blame_shifting | `you made me` | Claiming causation | 8 | negative | DP | — | false | generic manipulation phrase |
| 9 | Blame: Because of You | blame_shifting | `because of you` | Attributing outcomes | 7 | negative | DP | — | false | generic manipulation phrase |
| 10 | Blame: You Started | blame_shifting | `you started this` | Initiation claim | 6 | negative | DP | — | false | generic manipulation phrase |
| 11 | Blame: Always Do This | blame_shifting | `you always do this` | Pattern accusation | 7 | negative | DP | — | false | generic manipulation phrase |
| 12 | Blame: Made Me Do | blame_shifting | `look what you made me do` | Forced action claim | 9 | negative | DP | — | false | generic manipulation phrase |
| 13 | Minimizing: Not Big Deal | minimizing | `not a big deal` | Trivializing | 6 | negative | DP | — | false | generic manipulation phrase |
| 14 | Minimizing: Calm Down | minimizing | `calm down` | Dismissing emotions | 5 | negative | DP | — | false | generic manipulation phrase |
| 15 | Minimizing: Get Over It | minimizing | `get over it` | Demanding move on | 7 | negative | DP | — | false | generic manipulation phrase |
| 16 | Minimizing: Making Scene | minimizing | `stop making a scene` | Scene shaming | 6 | negative | DP | — | false | generic manipulation phrase |
| 17 | Minimizing: Just Joke | minimizing | `it was just a joke` | Joke defense | 6 | negative | DP | — | false | generic manipulation phrase |
| 18 | Minimizing: Relax | minimizing | `relax` | Dismissal | 5 | negative | DP | — | false | generic manipulation phrase |
| 19 | Circular: Keep Changing | circular | `you keep changing` | Changing accusation | 6 | negative | DP | — | false | generic manipulation phrase |
| 20 | Circular: Know What I Mean | circular | `you know what i mean` | Vague understanding | 5 | negative | DP | — | false | generic manipulation phrase |
| 21 | Circular: Anyway | circular | `anyway` | Termination | 5 | negative | DP | — | false | generic manipulation phrase |
| 22 | Circular: Whatever | circular | `whatever` | Dismissal | 5 | negative | DP | — | false | generic manipulation phrase |
| 23 | DARVO: I Never | darvo_deny | `i never` | Denial | 8 | negative | DP | — | false | generic manipulation phrase |
| 24 | DARVO: Never Happened | darvo_deny | `that never happened` | Event denial | 9 | negative | DP | — | false | generic manipulation phrase |
| 25 | DARVO: Would Never | darvo_deny | `i would never` | Character defense | 7 | negative | DP | — | false | generic manipulation phrase |
| 26 | DARVO: Need Protection | darvo_reverse | `i need protection from you` | Protection need | 10 | negative | DP | — | false | generic manipulation phrase |
| 27 | Overelaboration: Just Left | overelaboration | `i just left` | Departure | 7 | negative | DP | — | false | generic manipulation phrase |
| 28 | Overelaboration: Just Arrived | overelaboration | `i just arrived at` | Arrival | 7 | negative | DP | — | false | generic manipulation phrase |
| 29 | Overelaboration: Left At | overelaboration | `i left at` | Departure time | 7 | negative | DP | — | false | generic manipulation phrase |
| 30 | Overelaboration: Had To | overelaboration | `i had to` | Necessity | 8 | negative | DP | — | false | generic manipulation phrase |
| 31 | Overelaboration: Needed To | overelaboration | `i needed to` | Need explanation | 8 | negative | DP | — | false | generic manipulation phrase |
| 32 | Overelaboration: Reason Is | overelaboration | `the reason is` | Reasoning | 8 | negative | DP | — | false | generic manipulation phrase |
| 33 | Overelaboration: Was Just | overelaboration | `i was just` | Past justification | 7 | negative | DP | — | false | generic manipulation phrase |
| 34 | Overelaboration: Before You Ask | overelaboration | `before you ask` | Pre-emptive | 8 | negative | DP | — | false | generic manipulation phrase |
| 35 | Overelaboration: Just So Know | overelaboration | `just so you know` | Pre-emptive info | 7 | negative | DP | — | false | generic manipulation phrase |
| 36 | Overelaboration: For Record | overelaboration | `for the record` | Documenting | 7 | negative | DP | — | false | generic manipulation phrase |
| 37 | Overelaboration: To Be Clear | overelaboration | `to be clear` | Over-clarifying | 7 | negative | DP | — | false | generic manipulation phrase |
| 38 | Overelaboration: Let Me Explain | overelaboration | `let me explain` | Unprompted explanation | 7 | negative | DP | — | false | generic manipulation phrase |
| 39 | Love Bombing: Perfect | love_bombing | `perfect` | Excessive praise | 5 | negative | DP | — | false | generic manipulation phrase |
| 40 | Love Bombing: Amazing | love_bombing | `amazing` | Excessive praise | 5 | negative | DP | — | false | generic manipulation phrase |
| 41 | Love Bombing: Soulmate | love_bombing | `soulmate` | Premature commitment | 6 | negative | DP | — | false | generic manipulation phrase |
| 42 | Love Bombing: Always | love_bombing | `always` | Forever promise | 5 | negative | DP | — | false | generic manipulation phrase |
| 43 | Love Bombing: Forever | love_bombing | `forever` | Forever promise | 5 | negative | DP | — | false | generic manipulation phrase |
| 44 | Love Bombing: Everything | love_bombing | `everything` | Totality claim | 5 | negative | DP | — | false | generic manipulation phrase |
| 45 | Love Bombing: Desperate | love_bombing | `desperate` | Intensity | 6 | negative | DP | — | false | generic manipulation phrase |
| 46 | Love Bombing: Need You | love_bombing | `need you` | Dependency | 6 | negative | DP | — | false | generic manipulation phrase |
| 47 | Love Bombing: Give Everything | love_bombing | `i want to give you everything` | Grand promise | 6 | negative | DP | — | false | generic manipulation phrase |
| 48 | Gratitude: Owe Everything | excessive_gratitude | `i owe you everything` | Creating obligation | 6 | negative | DP | — | false | generic manipulation phrase |
| 49 | Gratitude: Never Repay | excessive_gratitude | `i could never repay you` | Unpayable debt | 6 | negative | DP | — | false | generic manipulation phrase |
| 50 | Gratitude: Thank Everything | excessive_gratitude | `thank you for everything` | Blanket gratitude | 4 | negative | DP | — | false | generic manipulation phrase |
| 51 | Gratitude: Saved Me | excessive_gratitude | `you saved me` | Savior positioning | 7 | negative | DP | — | false | generic manipulation phrase |
| 52 | Gratitude: Owe Life | excessive_gratitude | `i owe you my life` | Extreme debt | 7 | negative | DP | — | false | generic manipulation phrase |
| 53 | Debt: Remember When | debt_reminders | `remember when i` | Past favor reminder | 7 | negative | DP | — | false | generic manipulation phrase |
| 54 | Debt: Was There | debt_reminders | `i was there for you when` | Support reminder | 7 | negative | DP | — | false | generic manipulation phrase |
| 55 | Debt: I Helped | debt_reminders | `i helped you` | Assistance reminder | 6 | negative | DP | — | false | generic manipulation phrase |
| 56 | Debt: I Gave | debt_reminders | `i gave you` | Gift reminder | 6 | negative | DP | — | false | generic manipulation phrase |
| 57 | Savior: You Need Me | savior_complex | `you need me` | Dependency claim | 8 | negative | DP | — | false | generic manipulation phrase |
| 58 | Savior: Let Me Handle | savior_complex | `let me handle it` | Control taking | 6 | negative | DP | — | false | generic manipulation phrase |
| 59 | Savior: Trust To Protect | savior_complex | `trust me to protect you` | Trust demand | 7 | negative | DP | — | false | generic manipulation phrase |
| 60 | Savior: Everyone Else Hurt | savior_complex | `everyone else will hurt you` | World as dangerous | 9 | negative | DP | — | false | generic manipulation phrase |
| 61 | Savior: World Dangerous | savior_complex | `the world is dangerous` | Fear creation | 8 | negative | DP | — | false | generic manipulation phrase |
| 62 | Substance: Drink | substance_alcohol | `drink` | Alcohol mention | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 63 | Substance: Drank | substance_alcohol | `drank` | Alcohol mention | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 64 | Substance: Drunk | substance_alcohol | `drunk` | Intoxication | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 65 | Substance: Buzzed | substance_alcohol | `buzzed` | Intoxication | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 66 | Substance: Tipsy | substance_alcohol | `tipsy` | Intoxication | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 67 | Substance: Wasted | substance_alcohol | `wasted` | Intoxication | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 68 | Substance: Bottle | substance_alcohol | `bottle` | Alcohol container | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 69 | Substance: Wine | substance_alcohol | `wine` | Alcohol type | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 70 | Substance: Beer | substance_alcohol | `beer` | Alcohol type | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 71 | Substance: Liquor | substance_alcohol | `liquor` | Alcohol type | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 72 | Substance: Vodka | substance_alcohol | `vodka` | Alcohol type | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 73 | Substance: Tequila | substance_alcohol | `tequila` | Alcohol type | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 74 | Substance: Hungover | substance_alcohol | `hungover` | After-effects | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 75 | Substance: Fireball | substance_alcohol | `fireball` | Alcohol brand | 0 | negative | LEX/restricted | restricted | true | substance vulnerability term |
| 76 | Substance Weapon: Crackhead | substance_weaponized | `crackhead` | Drug slur | 9 | negative | LEX/restricted | restricted | true | drug slur/epithet |
| 77 | Substance Weapon: Tweaker | substance_weaponized | `tweaker` | Drug slur | 9 | negative | LEX/restricted | restricted | true | drug slur/epithet |
| 78 | Substance Weapon: Addict | substance_weaponized | `addict` | Drug label | 8 | negative | LEX/restricted | restricted | true | drug slur/epithet |
| 79 | Substance Weapon: Junkie | substance_weaponized | `junkie` | Drug slur | 9 | negative | LEX/restricted | restricted | true | drug slur/epithet |
| 80 | Substance Weapon: User | substance_weaponized | `user` | Drug label | 7 | negative | LEX/restricted | restricted | true | drug slur/epithet |
| 81 | Substance Weapon: On Something | substance_weaponized | `are you on something` | Accusation | 8 | negative | DP | — | false | substance accusation phrase |
| 82 | Substance Weapon: Drugs Talking | substance_weaponized | `this is the drugs talking` | Invalidation | 8 | negative | DP | — | false | substance accusation phrase |
| 83 | Adderall: Adderall | adderall_control | `adderall` | Medication mention | 7 | negative | LEX/restricted | restricted | true | medication term (vulnerability) |
| 84 | Adderall: Addy | adderall_control | `addy` | Medication slang | 7 | negative | LEX/restricted | restricted | true | medication term (vulnerability) |
| 85 | Adderall: Pills | adderall_control | `pills` | Medication generic | 6 | negative | LEX/restricted | restricted | true | medication term (vulnerability) |
| 86 | Adderall: Script | adderall_control | `script` | Prescription | 6 | negative | LEX/restricted | restricted | true | medication term (vulnerability) |
| 87 | Adderall: Share | adderall_control | `share` | Medication sharing | 7 | negative | DP | — | false | medication-control phrase |
| 88 | Adderall: Split | adderall_control | `split` | Medication splitting | 7 | negative | DP | — | false | medication-control phrase |
| 89 | Adderall: Your Turn | adderall_control | `your turn` | Medication rationing | 8 | negative | DP | — | false | medication-control phrase |
| 90 | Adderall: How Many | adderall_control | `how many did you take` | Medication monitoring | 8 | negative | DP | — | false | medication-control phrase |
| 91 | Infidelity: Cheating | infidelity | `cheating` | Infidelity mention | 8 | negative | DP | — | false | generic manipulation phrase |
| 92 | Infidelity: Cheated | infidelity | `cheated` | Infidelity past | 8 | negative | DP | — | false | generic manipulation phrase |
| 93 | Infidelity: Slept With | infidelity | `slept with` | Sexual involvement | 8 | negative | DP | — | false | generic manipulation phrase |
| 94 | Infidelity: Affair | infidelity | `affair` | Relationship betrayal | 9 | negative | DP | — | false | generic manipulation phrase |
| 95 | Infidelity: Secret | infidelity | `secret` | Hidden behavior | 6 | negative | DP | — | false | generic manipulation phrase |
| 96 | Infidelity: Seeing Someone | infidelity | `seeing someone` | Other relationship | 8 | negative | DP | — | false | generic manipulation phrase |
| 97 | Infidelity: Loyal | infidelity | `loyal` | Loyalty claim | 5 | negative | DP | — | false | generic manipulation phrase |
| 98 | Infidelity: Faithful | infidelity | `faithful` | Faithfulness claim | 5 | negative | DP | — | false | generic manipulation phrase |
| 99 | Infidelity: Just Work | infidelity | `we just work together` | Denial | 6 | negative | DP | — | false | generic manipulation phrase |
| 100 | Financial Weapon: What Do I Get | financial_weaponized | `what do i get out of this` | Transactional | 8 | negative | DP | — | false | generic manipulation phrase |
| 101 | Sexual Shame: Slut | sexual_shaming | `slut` | Sexual slur | 10 | negative | LEX/restricted | restricted | true | derogatory personal epithet |
| 102 | Sexual Shame: Whore | sexual_shaming | `whore` | Sexual slur | 10 | negative | LEX/restricted | restricted | true | derogatory personal epithet |
| 103 | Sexual Shame: Pervert | sexual_shaming | `pervert` | Sexual slur | 9 | negative | LEX/restricted | restricted | true | derogatory personal epithet |
| 104 | Sexual Shame: Disgusting | sexual_shaming | `disgusting` | Degradation | 8 | negative | LEX/restricted | restricted | true | derogatory personal epithet |
| 105 | Sexual Shame: Sick | sexual_shaming | `sick` | Degradation | 8 | negative | LEX/restricted | restricted | true | derogatory personal epithet |
| 106 | Sexual Shame: Nasty | sexual_shaming | `nasty` | Degradation | 8 | negative | LEX/restricted | restricted | true | derogatory personal epithet |
| 107 | Sexual Shame: Freak | sexual_shaming | `freak` | Sexual slur | 9 | negative | LEX/restricted | restricted | true | derogatory personal epithet |
| 108 | Sexual Shame: Used | sexual_shaming | `used` | Degradation | 9 | negative | LEX/restricted | restricted | true | derogatory personal epithet |
| 109 | Sexual Shame: Cheap | sexual_shaming | `cheap` | Degradation | 8 | negative | LEX/restricted | restricted | true | derogatory personal epithet |
| 110 | Sexual Shame: Everyone Leaves | sexual_shaming | `no wonder everyone leaves you` | Abandonment threat | 10 | negative | DP | — | false | shaming phrase |
| 111 | Sexual Shame: To Think | sexual_shaming | `to think i ever did` | Regret expression | 9 | negative | DP | — | false | shaming phrase |
| 112 | Alienation: Protect From You | parental_alienation | `i have to protect the children from you` | Protection justification | 10 | negative | DP | — | false | generic alienation phrase |
| 113 | Alienation: Kailah | parental_alienation | `kailah` | Child name mention | 10 | negative | LEX/sealed | sealed | true | child name (identifier) |
| 114 | Alienation: Kyla | parental_alienation | `kyla` | Child name variant | 10 | negative | LEX/sealed | sealed | true | child name (identifier) |
| 115 | Alienation: My Daughter | parental_alienation | `my daughter` | Possessive child reference | 8 | negative | LEX/sealed | sealed | true | family identifier |
| 116 | Alienation: Our Daughter | parental_alienation | `our daughter` | Child reference | 7 | negative | LEX/sealed | sealed | true | family identifier |
| 117 | Alienation: The Baby | parental_alienation | `the baby` | Child reference | 6 | negative | LEX/sealed | sealed | true | family identifier |
| 118 | Alienation: The Kid | parental_alienation | `the kid` | Child reference | 6 | negative | LEX/sealed | sealed | true | family identifier |
| 119 | Medical: Need Meds | medical_abuse | `you need your meds` | Medication control | 9 | negative | LEX/restricted | restricted | true | health/medication vulnerability |
| 120 | Medical: Take Pills | medical_abuse | `did you take your pills` | Medication monitoring | 8 | negative | LEX/restricted | restricted | true | health/medication vulnerability |
| 121 | Medical: Need Hospitalized | medical_abuse | `you need to be hospitalized` | Institutionalization threat | 10 | negative | LEX/restricted | restricted | true | health/medication vulnerability |
| 122 | Reproductive: Want Pregnant | reproductive_coercion | `i want you pregnant` | Pregnancy demand | 10 | negative | LEX/restricted | restricted | true | reproductive vulnerability |
| 123 | Reproductive: Should Get Pregnant | reproductive_coercion | `you should get pregnant` | Pregnancy pressure | 10 | negative | LEX/restricted | restricted | true | reproductive vulnerability |
| 124 | Reproductive: Stop Birth Control | reproductive_coercion | `stop taking birth control` | Contraception interference | 10 | negative | LEX/restricted | restricted | true | reproductive vulnerability |
| 125 | Reproductive: Baby Fix | reproductive_coercion | `a baby will fix us` | Baby as solution | 9 | negative | LEX/restricted | restricted | true | reproductive vulnerability |
| 126 | Reproductive: Owe Child | reproductive_coercion | `you owe me a child` | Child as debt | 10 | negative | LEX/restricted | restricted | true | reproductive vulnerability |
| 127 | Reproductive: Sabotaged | reproductive_coercion | `i sabotaged your birth control` | Contraception sabotage | 10 | negative | LEX/restricted | restricted | true | reproductive vulnerability |
| 128 | Deference: Is Alright | victim_deference | `is that alright` | Approval seeking | 7 | negative | DP | — | false | generic manipulation phrase |
| 129 | Deference: Sorry | victim_deference | `sorry` | Apologetic | 6 | negative | DP | — | false | generic manipulation phrase |
| 130 | Deference: My Bad | victim_deference | `my bad` | Apologetic | 6 | negative | DP | — | false | generic manipulation phrase |
| 131 | Deference: I Apologize | victim_deference | `i apologize` | Apologetic | 6 | negative | DP | — | false | generic manipulation phrase |
| 132 | Deference: Let Me Know | victim_deference | `let me know if` | Deferential | 6 | negative | DP | — | false | generic manipulation phrase |
| 133 | Directive: Where Are You | abuser_directives | `where are you` | Location demand | 8 | negative | DP | — | false | generic manipulation phrase |
| 134 | Directive: What Doing | abuser_directives | `what are you doing` | Activity demand | 8 | negative | DP | — | false | generic manipulation phrase |
| 135 | Directive: Who With | abuser_directives | `who are you with` | Company demand | 8 | negative | DP | — | false | generic manipulation phrase |
| 136 | Directive: Come Here | abuser_directives | `come here` | Movement command | 7 | negative | DP | — | false | generic manipulation phrase |
| 137 | Directive: Go There | abuser_directives | `go there` | Movement command | 7 | negative | DP | — | false | generic manipulation phrase |
| 138 | Directive: Do This | abuser_directives | `do this` | Action command | 7 | negative | DP | — | false | generic manipulation phrase |
| 139 | Directive: Stop That | abuser_directives | `stop that` | Prohibition command | 7 | negative | DP | — | false | generic manipulation phrase |
| 140 | Directive: Tell Me | abuser_directives | `tell me` | Information demand | 7 | negative | DP | — | false | generic manipulation phrase |
| 141 | Directive: Show Me | abuser_directives | `show me` | Proof demand | 8 | negative | DP | — | false | generic manipulation phrase |
| 142 | Directive: Prove It | abuser_directives | `prove it` | Evidence demand | 8 | negative | DP | — | false | generic manipulation phrase |
| 143 | Certainty: Always | certainty_absolutes | `always` | Absolute claim | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 144 | Certainty: Never | certainty_absolutes | `never` | Absolute claim | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 145 | Certainty: Nothing | certainty_absolutes | `nothing` | Absolute claim | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 146 | Certainty: Everything | certainty_absolutes | `everything` | Absolute claim | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 147 | Certainty: Everyone | certainty_absolutes | `everyone` | Absolute claim | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 148 | Certainty: Nobody | certainty_absolutes | `nobody` | Absolute claim | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 149 | Certainty: Fact | certainty_absolutes | `fact` | Certainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 150 | Certainty: Obviously | certainty_absolutes | `obviously` | Certainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 151 | Certainty: Clearly | certainty_absolutes | `clearly` | Certainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 152 | Certainty: Literally | certainty_absolutes | `literally` | Certainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 153 | Hedge: Maybe | hedge_words | `maybe` | Uncertainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 154 | Hedge: Perhaps | hedge_words | `perhaps` | Uncertainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 155 | Hedge: Possibly | hedge_words | `possibly` | Uncertainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 156 | Hedge: Might | hedge_words | `might` | Uncertainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 157 | Hedge: Could | hedge_words | `could` | Uncertainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 158 | Hedge: I Think | hedge_words | `i think` | Uncertainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 159 | Hedge: I Guess | hedge_words | `i guess` | Uncertainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 160 | Hedge: Sort Of | hedge_words | `sort of` | Uncertainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 161 | Hedge: Kind Of | hedge_words | `kind of` | Uncertainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 162 | Hedge: Probably | hedge_words | `probably` | Uncertainty marker | 0 | linguistic_marker | DP | — | false | generic manipulation phrase |
| 163 | NPD: Parenting Superiority | npd_grandiosity | `better parent` | Claims of parenting superiority | 7 | negative | DP | — | false | generic manipulation phrase |
| 164 | NPD: Everyone Agrees | npd_grandiosity | `everyone agrees` | Claims universal support without evidence | 5 | negative | DP | — | false | generic manipulation phrase |
| 165 | NPD: Lucky To Have Me | npd_grandiosity | `lucky to have me` | Frames relationship as privilege | 6 | negative | DP | — | false | generic manipulation phrase |
| 166 | NPD: Best Years | npd_grandiosity | `gave you the best years` | Martyrdom framing | 5 | negative | DP | — | false | generic manipulation phrase |
| 167 | NPD: I Deserve | npd_entitlement | `i deserve` | Entitlement claim | 7 | negative | DP | — | false | generic manipulation phrase |
| 168 | NPD: Makes Me Look | npd_empathy_deficit | `makes me look` | Self-centering in crisis | 8 | negative | DP | — | false | generic manipulation phrase |
| 169 | NPD: Too Dramatic | npd_empathy_deficit | `being too dramatic` | Invalidating emotions | 6 | negative | DP | — | false | generic manipulation phrase |
| 170 | BPD: Going To Abandon | bpd_abandonment | `going to abandon` | Projecting abandonment | 6 | negative | DP | — | false | generic manipulation phrase |
| 171 | BPD: Already Abandoned | bpd_abandonment | `already abandoned` | Reframing custody as abandonment | 7 | negative | DP | — | false | generic manipulation phrase |
| 172 | BPD: With Or Against | bpd_splitting | `with me or against me` | Binary loyalty demand | 7 | negative | DP | — | false | generic manipulation phrase |
| 173 | BPD: Pure Evil | bpd_splitting | `pure evil` | All-or-nothing characterization | 6 | negative | DP | — | false | generic manipulation phrase |
| 174 | BPD: Never Loved | bpd_splitting | `never really loved` | Rewriting relationship history | 7 | negative | DP | — | false | generic manipulation phrase |
| 175 | BPD: End It All | bpd_self_harm_threat | `end it all` | Suicide threat | 10 | negative | DP | — | false | generic manipulation phrase |
| 176 | ASPD: Deserved It | aspd_callousness | `deserved it` | Justifying harm | 7 | negative | DP | — | false | generic manipulation phrase |
| 177 | ASPD: Made Me Do It | aspd_no_remorse | `you made me do` | Blaming victim for abuse | 8 | negative | DP | — | false | generic manipulation phrase |
| 178 | ASPD: Forced My Hand | aspd_no_remorse | `forced my hand` | Justifying harmful actions | 6 | negative | DP | — | false | generic manipulation phrase |
| 179 | Custody: Different Judge | custody_court_manipulation | `different judge` | Judge shopping intent | 7 | negative | DP | — | false | generic manipulation phrase |
| 180 | Custody: Drag It Out | custody_court_manipulation | `drag it out` | Explicit delay tactic | 8 | negative | DP | — | false | generic manipulation phrase |
| 181 | Custody: Game The System | custody_court_manipulation | `game the system` | Admission of manipulation | 9 | negative | DP | — | false | generic manipulation phrase |
| 182 | Custody: None Of Your Business | custody_gatekeeping | `none of your business` | Blocking parental information | 6 | negative | DP | — | false | generic manipulation phrase |
| 183 | Custody: Not Allowed To See | custody_gatekeeping | `not allowed to see` | Blocking contact | 8 | negative | DP | — | false | generic manipulation phrase |
| 184 | Custody: Without Asking You | custody_gatekeeping | `without asking you` | Unilateral decisions | 7 | negative | DP | — | false | generic manipulation phrase |
| 185 | Custody: Emergency Came Up | custody_schedule_interference | `emergency came up` | Manufactured emergencies | 6 | negative | DP | — | false | generic manipulation phrase |
| 186 | Custody: Already Made Plans | custody_schedule_interference | `already made plans` | Scheduling over custody time | 7 | negative | DP | — | false | generic manipulation phrase |
| 187 | Custody: Tell Your Dad | custody_child_messenger | `tell your dad` | Using child to communicate | 7 | negative | DP | — | false | generic manipulation phrase |
| 188 | Custody: Find Out What | custody_child_messenger | `find out what` | Child as spy | 8 | negative | DP | — | false | generic manipulation phrase |
| 189 | Custody: Real Dad | custody_parental_replacement | `real dad` | New partner as replacement | 8 | negative | DP | — | false | generic manipulation phrase |
| 190 | Custody: Real Family | custody_parental_replacement | `real family` | Redefining family | 8 | negative | DP | — | false | generic manipulation phrase |
| 191 | Custody: Change Name | custody_parental_replacement | `change their name` | Name change pressure | 7 | negative | DP | — | false | generic manipulation phrase |

## Distinct categories (37) — for `behavior_category`

`default_severity` = max severity observed in this dataset for the category (clamped 0-10). `polarity`: linguistic_marker for marker-only categories, else negative.

| category_id (snake_case) | count | default_severity (max) | polarity | notes |
|---|---|---|---|---|
| abuser_directives | 10 | 8 | negative |  |
| adderall_control | 8 | 8 | negative | case-specific medication-control; med terms -> lexicon restricted |
| aspd_callousness | 1 | 7 | negative |  |
| aspd_no_remorse | 2 | 8 | negative |  |
| blame_shifting | 6 | 9 | negative |  |
| bpd_abandonment | 2 | 7 | negative |  |
| bpd_self_harm_threat | 1 | 10 | negative |  |
| bpd_splitting | 3 | 7 | negative |  |
| certainty_absolutes | 10 | 0 | linguistic_marker | severity 0 linguistic markers |
| circular | 4 | 6 | negative |  |
| custody_child_messenger | 2 | 8 | negative |  |
| custody_court_manipulation | 3 | 9 | negative |  |
| custody_gatekeeping | 3 | 8 | negative |  |
| custody_parental_replacement | 3 | 8 | negative |  |
| custody_schedule_interference | 2 | 7 | negative |  |
| darvo_deny | 3 | 9 | negative |  |
| darvo_reverse | 1 | 10 | negative |  |
| debt_reminders | 4 | 7 | negative |  |
| excessive_gratitude | 5 | 7 | negative |  |
| financial_weaponized | 1 | 8 | negative | single pattern in this dataset |
| gaslighting | 6 | 9 | negative |  |
| hedge_words | 10 | 0 | linguistic_marker | severity 0 linguistic markers |
| infidelity | 9 | 9 | negative |  |
| love_bombing | 9 | 6 | negative |  |
| medical_abuse | 3 | 10 | negative | health-vulnerability -> lexicon restricted |
| minimizing | 6 | 7 | negative |  |
| npd_empathy_deficit | 2 | 8 | negative |  |
| npd_entitlement | 1 | 7 | negative |  |
| npd_grandiosity | 4 | 7 | negative |  |
| overelaboration | 12 | 8 | negative |  |
| parental_alienation | 7 | 10 | negative | child names (kailah/kyla) + family identifiers -> lexicon SEALED, is_case_specific |
| reproductive_coercion | 6 | 10 | negative | reproductive-vulnerability -> lexicon restricted |
| savior_complex | 5 | 9 | negative |  |
| sexual_shaming | 11 | 10 | negative | derogatory epithets -> lexicon restricted; phrases -> DP |
| substance_alcohol | 14 | 0 | negative | all severity 0 = neutral mention detector; vulnerability terms -> lexicon restricted |
| substance_weaponized | 7 | 9 | negative | drug slurs -> lexicon restricted; accusation phrases -> DP |
| victim_deference | 5 | 7 | negative |  |
