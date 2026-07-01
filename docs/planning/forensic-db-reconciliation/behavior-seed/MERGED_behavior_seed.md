# MERGED — Behavioral-Pattern Seed Superset (G1–G9 strictly-additive union)

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Strictly-additive UNION of nine extraction fragments (G1 analyzer-app, G2 seed-patterns.ts,
> G3 dial TTL ontologies, G4 E4 consolidation, G5 agno-alpha classifiers, G6 dataset folder,
> G7 Zep/Salem v3 ontology, G8 conversation logs, G9 owner other-drives).
> Target = live `analysis` schema: `detection_pattern_set`, `behavior_category`, `detection_pattern`,
> `pattern_lexicon`, `behavior_category_mcl`. Every row carries a `sources` column so origin is never lost.

## Merge rules applied
- **UNION every distinct category / pattern / keyword / lexicon term / MCL mapping.** Nothing dropped for being "less complete."
- **Exact-dup collapse only:** same `category_id` + same normalized pattern text (case/space-insensitive) + same `match_type`. On collapse: provenance merged (all sources listed), MAX severity/score kept, richest description retained. Near-duplicates/paraphrases KEPT as separate rows.
- **Enums (only these):** `category_polarity` = negative|positive|neutral|linguistic_marker · `pattern_match_type` = literal|regex · `mcl_factor` = a..l · `sensitivity_tier` = public|restricted|sealed.
- **Court-safety routing (HARD, overrides additive):**
  - Proper names (child, parties, third parties, surnames), case-specific places, deceased-relative refs, verbatim case quotes → `pattern_lexicon`, `sensitivity_tier='sealed'`, `is_case_specific=true`. NEVER plaintext `detection_pattern`.
  - Single-token derogatory epithets/slurs (sexual, drug, homophobic), named-target vulnerability ties, HurtLex taxonomy → `pattern_lexicon`, `sensitivity_tier='restricted'`.
  - Generic kinship templates (my daughter / the kid …) → `pattern_lexicon` `child_reference`, `restricted`, `is_case_specific=false`.
  - All generic multi-word manipulation PHRASES + genericized regexes (child names stripped to placeholders/`her|him|the kid`) → `detection_pattern`, `bias_caution=true` (HYPOTHESES, not findings).
  - Neutral single-token lexical detectors that are NOT epithets/identifiers (substance-mention words, certainty/hedge/medication nouns) stay as severity-0/low `detection_pattern` markers.
- **J↔K canonical (statute):** j = willingness to facilitate other-parent relationship; k = domestic violence. G3 `.ttl` had the `rdfs:label` swapped and G5 priority-screener used idiosyncratic letters; both remapped to canonical codes here. `behavior_category_mcl.is_critical=true` for j & k.

---

## 1. `detection_pattern_set` — seven source sets registered; ONE active merged set

| name | version | source | source_artifact | is_active | authored_perspective | sources |
|---|---|---|---|---|---|---|
| `merged_behavior_seed_v1` | `1.0.0` | merged G1–G9 | this file | **true** (the ONE active set) | `single_party_complainant` (run symmetrically on all parties before use) | G1-G9 |
| `analyzer_app_coercive_control` | `1.0` | analyzer-app | `app.py (+app_local.py)` | false | documenting_party | G1 |
| `behavioral-seed-darvo-coercion` | `1.0.0` | seed-patterns.ts | `.../migration-plan-v8/server/scripts/seed-patterns.ts` | false | owner_protective_parent | G2 |
| `dial_behavioral_ontology` | `1.0.0` | dial-stack ontologies | `behavioral_patterns.ttl + positive_behaviors.ttl + mcl_722_23.ttl` | false | protective-parent/forensic-analyst | G3 |
| `casebible_custody_v1` | `1.0.0` | E4 consolidation | `COMPLETE_SCHEMA_PARSER_INVENTORY.md#part-4 + E4_behavioral_ontology.md` | false | single_party_complainant | G4 |
| `agno-alpha-classifier` | `v8-migration` | agno-alpha-classifier | `server/mcp/analysis/{classifier,multi-pass-classifier,nlp-classifier,priority-screener}.ts` | false | petitioner | G5 |
| `zep_salem_ontology_v3` | `3.0.0` | zep_salem_ontology_v3 | `extracted-code/ontologies-datasets/zep_salem_ontology_v3_final.py` | false | protective-parent/forensic-analyst | G7 |
| `coercive-control-clusters-g9` | `1.0.0` | onedrive/D-drives | `OneDrive/Case Bible/.../coercive_control_pipeline/labels_ontology.json` | false | single_party_complainant | G9 |

> G6 (`behavioral_patterns_dataset`) is a derived/SFT corpus, not a distinct authored set; its rows merge into the merged set with `source='behavioral_patterns_dataset'`. ONE active set invariant satisfied by `merged_behavior_seed_v1`.

---

## 2. `behavior_category` — full UNION (155 distinct category_id)

`default_severity` = MAX across sources. `mcl_factors` = UNION across sources. `aliases` = UNION. Polarity from enum (manipulation tactics with positive surface = `negative`; pure positive-contrast classes = `positive`; markers = `linguistic_marker`; context/state = `neutral`).

| category_id | label | polarity | default_severity | mcl_factors | aliases | is_case_specific | sources |
|---|---|---|---|---|---|---|---|
| threats | Threats / Intimidation | negative | 10 | {j,k} | {threat,intimidation,explicit_threat,implicit_threat} | false | G1,G5 |
| child_weaponization | Child Weaponization | negative | 9 | {j,k} | {using_child} | false | G1 |
| monitoring_stalking | Monitoring / Stalking | negative | 8 | {g,k} | {stalking,surveillance,monitoring} | false | G1 |
| homophobic_slurs | Homophobic Slurs | negative | 7 | {f,k} | {anti_gay} | false | G1 |
| isolation_tactics | Isolation Tactics | negative | 7 | {j,k} | {isolating} | false | G1 |
| gaslighting | Gaslighting | negative | 9 | {a,f,g,k} | {reality_distortion} | false | G1,G2,G3,G4,G6 |
| double_bind | Double Bind | negative | 7 | {j,k} | {contradictory_demand} | false | G1 |
| character_attacks | Character Attacks | negative | 6 | {f,k} | {name_calling} | false | G1 |
| financial_control | Financial Control / Economic Abuse | negative | 7 | {c,k,l} | {economic_abuse,financial_abuse} | false | G1,G5,G9 |
| triangulation | Triangulation | negative | 7 | {f,j,k,l} | {third_party_manipulation} | false | G1,G5,G7 |
| communication_control | Communication Control | negative | 5 | {j,k} | {contact_blocking} | false | G1 |
| substance_shaming | Substance Shaming | negative | 5 | {f,g} | {drug_shaming} | false | G1 |
| mental_health_stigma | Mental Health Stigma | negative | 5 | {f,g} | {crazy_making} | false | G1 |
| love_bombing | Love Bombing | negative | 6 | {a,f,j,k,l} | {lovebomb,intermittent_reinforcement} | false | G1,G2,G3,G4,G6 |
| blame_shifting | Blame Shifting | negative | 9 | {f,j,k} | {} | false | G2,G3,G4,G6 |
| minimizing | Minimizing | negative | 7 | {f,j,k} | {minimization,dismissiveness} | false | G2,G3,G4,G6 |
| circular | Circular Arguments | negative | 6 | {l} | {word_salad} | false | G2,G6 |
| darvo_deny | DARVO – Deny | negative | 9 | {f} | {} | false | G2,G6 |
| darvo_attack | DARVO – Attack | negative | 9 | {f,k} | {} | false | G2 |
| darvo_reverse | DARVO – Reverse Victim/Offender | negative | 10 | {f,k} | {} | false | G2,G6 |
| overelaboration | Overelaboration / Over-justification | linguistic_marker | 8 | {f,l} | {} | false | G1,G2,G3,G4,G6 |
| excessive_gratitude | Excessive Gratitude | negative | 7 | {f,l} | {} | false | G2,G6 |
| debt_reminders | Debt Reminders | negative | 8 | {f} | {} | false | G2,G6 |
| savior_complex | Savior Complex | negative | 9 | {f,k} | {rescuing} | false | G2,G6 |
| substance_alcohol | Substance – Alcohol (mentions) | neutral | 0 | {g} | {} | false | G2,G6 |
| substance_weaponized | Substance – Weaponized | negative | 9 | {f,g,k} | {substance_weaponization} | false | G2,G6 |
| adderall_control | Adderall / Medication Control | negative | 8 | {c,g,k} | {medication_control} | true | G2,G6 |
| infidelity | Infidelity | negative | 9 | {f} | {} | false | G2,G6 |
| financial_weaponized | Financial – Weaponized | negative | 8 | {c,f} | {financial_abuse} | false | G2,G6 |
| sexual_shaming | Sexual Shaming | negative | 10 | {b,f,k} | {} | false | G2,G4,G6 |
| parental_alienation | Parental Alienation | negative | 10 | {a,i,j,k} | {alienation,gatekeeping} | false | G2,G3,G4,G6,G7 |
| medical_abuse | Medical Abuse | negative | 10 | {c,f,g,j,k} | {medical} | false | G2,G4,G6 |
| reproductive_coercion | Reproductive Coercion | negative | 10 | {f,j,k,l} | {} | false | G2,G4,G6 |
| victim_deference | Power Asymmetry – Victim Deference | linguistic_marker | 7 | {k} | {} | false | G2,G6 |
| abuser_directives | Power Asymmetry – Abuser Directives | negative | 8 | {k} | {} | false | G2,G6 |
| certainty_absolutes | Statistical – Certainty/Absolutes | linguistic_marker | 0 | {l} | {} | false | G2,G4,G6 |
| hedge_words | Statistical – Hedge Words | linguistic_marker | 0 | {l} | {} | false | G2,G4,G6 |
| darvo | DARVO (Deny·Attack·Reverse) | negative | 10 | {f,j,k} | {darvo_deny,darvo_attack,darvo_reverse} | false | G3,G4,G7 |
| coercive_control | Coercive Control | negative | 10 | {c,j,k} | {} | false | G3,G4 |
| affirmations | Affirmation / Praise + Validation | positive | 4 | {a,f,l} | {affirmation,positive_statements,explicit_praise,emotional_validation} | false | G3,G4,G5 |
| expectation_setting | Expectation Setting / Future-Faking | positive | 4 | {a,c} | {future_promise,financial_assurance} | false | G3 |
| cooperation | Cooperative Behavior | positive | 1 | {a,b,d,j} | {information_sharing,flexibility} | false | G3,G4 |
| dependency_cultivation | Dependency Cultivation ("savior") | positive | 5 | {f} | {savior_complex,rescuing} | false | G3,G4 |
| stonewalling | Silent treatment / refusal to communicate | negative | 7 | {f,k} | {silent_treatment,withholding} | false | G4 |
| financial_abuse | Economic abuse / weaponized money | negative | 8 | {c,j} | {financial_control,financial_weaponized} | false | G4 |
| substance_weaponization | Substance use as weapon/label | negative | 9 | {b,f,g,k} | {substance_weaponized} | false | G4 |
| reactive_abuse | Provoked reaction reframed as aggression | negative | 8 | {f,j,k} | {} | false | G4,G8 |
| character_assassination | Degradation / slurs / epithets | negative | 9 | {b,f,k} | {character_attack,character_attacks} | false | G4 |
| isolation | Cutting off support systems | negative | 9 | {c,j,k} | {isolation_tactics,cutting_off_support} | false | G4,G5,G7,G9 |
| hoovering | Pulling victim back after discard | negative | 6 | {a,f} | {} | false | G4 |
| parenting_time | Visitation / handoff interference | negative | 9 | {j,k} | {} | false | G4 |
| gatekeeping | Blocking contact/information access | negative | 8 | {j} | {} | false | G4 |
| special_needs | Child special-needs handling | negative | 8 | {a,c,l} | {} | false | G4 |
| threats_intimidation | Threats of harm/retaliation | negative | 10 | {j,k} | {threats} | false | G4,G9 |
| future_faking | Grandiose unfulfilled promises | positive | 3 | {l} | {expectation_setting} | false | G4 |
| apologies | Apology / remorse | positive | 2 | {l} | {} | false | G4 |
| gift_giving | Material generosity | positive | 2 | {c,l} | {gestures_of_affection} | false | G4,G5 |
| power_asymmetry | Victim-deference vs abuser-directive | neutral | 0 | {j,l} | {} | false | G4 |
| scheduling | Custody schedule / visitation logistics | neutral | 0 | {a,b,d} | {} | false | G4 |
| child_wellbeing | Child health/education/emotional mentions | neutral | 0 | {a,b,e,g} | {} | false | G4 |
| manipulation | Manipulation (umbrella) | negative | 7 | {l} | {controlling_through_deception} | false | G5 |
| intimidation | Intimidation / Threats | negative | 8 | {f,k} | {threats_aggression} | false | G5,G7 |
| denial | Denial / refusing to acknowledge | negative | 7 | {f,l} | {refusing_to_acknowledge} | false | G5,G7 |
| stalking | Stalking / surveillance | negative | 8 | {g,k} | {monitoring,surveillance} | false | G5 |
| coordinated_abuse | Multi-party targeting | negative | 8 | {j,k,l} | {multi_party_targeting} | false | G5 |
| smear_campaign | Smear campaign / rumor spreading | negative | 8 | {f,j,k} | {reputational_attack,defamation} | false | G5,G7 |
| silent_treatment | Withholding communication as punishment | negative | 6 | {j,l} | {stonewalling,withholding_communication} | false | G5 |
| reassurances | Reassurances (trust assertion) | positive | 0 | {l} | {trust_assertion} | false | G5 |
| promises | Promises / commitment to change | positive | 0 | {l} | {commitment_to_change,future_commitment} | false | G5 |
| declarations_of_loyalty | Declarations of loyalty | positive | 0 | {l} | {loyalty_declaration} | false | G5 |
| expressions_of_care | Expressions of care | positive | 0 | {l} | {concern_for_wellbeing} | false | G5 |
| future_planning | Future planning | positive | 0 | {l} | {long_term_plans} | false | G5 |
| compliments | Compliments / praise | positive | 0 | {l} | {praise} | false | G5 |
| negation_markers | Negation markers | linguistic_marker | 0 | {} | {negation} | false | G5 |
| intensity_modifiers | Intensity modifiers | linguistic_marker | 0 | {} | {intensifiers} | false | G5 |
| communication_blocking | Call blocking / refusing to answer | negative | 9 | {j} | {} | false | G5 |
| visit_blocking | Visit denial / won't bring child | negative | 9 | {j} | {} | false | G5 |
| parenting_time_denial | Schedule interference | negative | 8 | {j} | {} | false | G5 |
| custody_interference | Hiding/keeping child; RO/police weaponization | negative | 9 | {j,k} | {} | false | G5 |
| child_reference | Generic child mention | neutral | 5 | {i} | {} | false | G5 |
| economic_sabotage | Economic sabotage / financial coercion | negative | 7 | {c,k} | {} | false | G7 |
| suicide_baiting | Suicide baiting (trauma weaponization) | negative | 10 | {f,g,k} | {} | false | G7 |
| projection | Accusing target of accuser's own conduct | negative | 7 | {f,k} | {blame_shifting} | false | G7,G8 |
| minimization | Minimization | negative | 6 | {f} | {minimizing} | false | G7 |
| fabrication | Fabrication / fabricated narrative | negative | 9 | {f,k} | {} | false | G7 |
| misdirection | Misdirection / distraction | negative | 6 | {f} | {} | false | G7 |
| inconsistent_account | Inconsistent / contradictory account | neutral | 5 | {f} | {} | false | G7 |
| manufactured_crisis | Manufactured / staged crisis | negative | 7 | {f,k} | {} | false | G7 |
| child_exposure | Exposure of child to harm | negative | 8 | {f,j,k} | {} | false | G7 |
| trauma_exploitation | Trauma / vulnerability exploitation | negative | 9 | {f,k} | {} | false | G7 |
| substance_endangerment | Substance use / endangerment | negative | 8 | {c,g,k} | {} | false | G7 |
| medical_neglect | Medical neglect | negative | 8 | {c,g} | {} | false | G7 |
| npd_grandiosity | NPD grandiosity | negative | 7 | {f} | {} | false | G6 |
| npd_entitlement | NPD entitlement | negative | 7 | {f} | {} | false | G6 |
| npd_empathy_deficit | NPD empathy deficit | negative | 8 | {f} | {} | false | G6 |
| bpd_abandonment | BPD abandonment projection | negative | 7 | {a,f} | {} | false | G6 |
| bpd_splitting | BPD splitting | negative | 7 | {f} | {} | false | G6 |
| bpd_self_harm_threat | BPD self-harm/suicide threat | negative | 10 | {g,k} | {} | false | G6 |
| aspd_callousness | ASPD callousness | negative | 7 | {f,k} | {} | false | G6 |
| aspd_no_remorse | ASPD no remorse | negative | 8 | {f,k} | {} | false | G6 |
| custody_court_manipulation | Court/judge-shopping/delay manipulation | negative | 9 | {f,j} | {} | false | G6 |
| custody_gatekeeping | Blocking parental info/contact | negative | 8 | {j} | {} | false | G6 |
| custody_schedule_interference | Manufactured emergencies / scheduling over time | negative | 7 | {j} | {} | false | G6 |
| custody_child_messenger | Child as messenger/spy | negative | 8 | {i,j} | {} | false | G6 |
| custody_parental_replacement | New partner as replacement parent | negative | 8 | {a,j} | {} | false | G6 |
| feigning_incompetence | Weaponized / strategic incompetence | negative | 5 | {c,j} | {playing_dumb} | false | G8 |
| defensiveness_evasion | Extreme defensiveness / accountability evasion | negative | 6 | {f} | {} | false | G8 |
| social_media_deception | Platform-denial / contradiction deception | negative | 6 | {f} | {} | false | G8 |
| last_minute_changes | Manufactured instability / schedule sabotage | negative | 6 | {j} | {} | false | G8 |
| emotional_dysregulation | Manic/depressive linguistic markers | neutral | 0 | {g} | {} | false | G8 |
| i_talk_marker | First-person-singular over-use (LIWC) | linguistic_marker | 0 | {} | {} | false | G8 |
| you_talk_marker | Second-person accusatory over-use (LIWC) | linguistic_marker | 0 | {} | {} | false | G8 |
| guilt_tripping | Guilt / FOG leverage | negative | 6 | {f,k} | {} | false | G8 |
| feigned_concern | Faux-worry used to degrade/position | negative | 6 | {f,j} | {} | false | G8 |
| flying_monkeys | Proxy abuse via recruited third parties | negative | 7 | {j,k} | {} | false | G8 |
| devaluation | Devalue phase (criticism/contempt/withdrawal) | negative | 7 | {a,f} | {} | false | G8 |
| discard | Discard phase (abandonment / new supply) | negative | 7 | {a,j} | {} | false | G8 |
| child_endangerment | Substance-use + child-present co-occurrence | negative | 9 | {c,g,k} | {} | false | G8 |
| autism_weaponization | Weaponizing child's diagnosis vs other parent | negative | 8 | {a,c,j} | {} | false | G8 |
| block_unblock_cycle | Intermittent contact control (punish/reward) | negative | 7 | {j,k} | {} | false | G8 |
| recovery_phase | Manipulative calm after escalation | neutral | 3 | {l} | {} | false | G8 |
| word_salad | Deliberate confusion / obscure language | negative | 5 | {l} | {obscure_language} | false | G8 |
| dismissiveness | Minimization / shutdown / invalidation cluster | negative | 5 | {f} | {minimizing} | false | G8 |
| selective_amnesia | Convenient forgetting / memory denial | negative | 6 | {f} | {forgetting_feigned_amnesia} | false | G8 |
| monitoring_surveillance | Monitoring & surveillance | negative | 6 | {k} | {monitoring,surveillance} | false | G9 |
| gaslighting_reality_distortion | Gaslighting & reality distortion (cluster) | negative | 7 | {k} | {} | false | G9 |
| verbal_degradation | Verbal degradation & devaluation | negative | 6 | {b,k} | {empathy_withholding} | false | G9 |
| autonomy_deprivation | Autonomy deprivation & daily control | negative | 5 | {c,k} | {cumulative_micro_control} | false | G9 |
| identity_erosion | Identity erosion & trauma bonding | negative | 7 | {k} | {} | false | G9 |
| sexual_reproductive_coercion | Sexual & reproductive coercion | negative | 8 | {k} | {} | false | G9 |
| jealousy_possessiveness | Jealousy & possessiveness | negative | 5 | {k} | {} | false | G9 |
| narcissistic_entitlement | Narcissistic entitlement & rage | negative | 7 | {k} | {victimhood_posturing,manufactured_conflict} | false | G9 |
| legal_system_abuse | Legal-system & institutional abuse | negative | 7 | {j,k} | {litigation_abuse,children_as_control_tools} | false | G9 |
| entrapment_fear | Entrapment & pervasive fear | negative | 8 | {k} | {post_separation_control} | false | G9 |
| countering | Gaslighting subtype: countering (memory attack) | negative | 7 | {k} | {} | false | G9 |
| diverting | Gaslighting subtype: diverting/whataboutism | negative | 7 | {f,k} | {} | false | G9 |
| stereotyping | Gaslighting subtype: stereotyping | negative | 6 | {k} | {} | false | G9 |
| forgetting_feigned_amnesia | Gaslighting subtype: feigned amnesia | negative | 6 | {f,k} | {selective_amnesia} | false | G9 |
| questioning_sanity | Gaslighting subtype: questioning sanity | negative | 8 | {g,k} | {crazy_label} | false | G9 |
| joke_defense | Gaslighting subtype: joke defense | negative | 6 | {k} | {} | false | G9 |
| scapegoating | Gaslighting subtype: scapegoating | negative | 7 | {f,k} | {} | false | G9 |
| feeling_police | Gaslighting subtype: feeling-policing | negative | 5 | {k} | {} | false | G9 |
| subtle_shift | Gaslighting subtype: subtle account shift | negative | 6 | {f,k} | {} | false | G9 |
| weaponizing_allies_triangulation | Gaslighting subtype: ally-weaponizing | negative | 6 | {j,k} | {triangulation} | false | G9 |
| provocation_defense | Gaslighting subtype: provocation defense | negative | 7 | {f,k} | {reactive_abuse} | false | G9 |
| victim_playing | MER style: victim playing | negative | 6 | {f} | {} | false | G9 |
| exaggeration_dramatization | MER style: exaggeration/dramatization | negative | 5 | {f} | {} | false | G9 |
| impatience | MER style: impatience | negative | 4 | {l} | {} | false | G9 |
| ignoring | MER style: ignoring | negative | 5 | {j} | {} | false | G9 |
| diminishing | MER style: diminishing | negative | 5 | {f} | {minimizing} | false | G9 |
| invalidation | MER style: invalidation | negative | 5 | {f} | {} | false | G9 |
| changing_the_topic | MER style: changing the topic | negative | 5 | {f} | {diverting} | false | G9 |
| aggression | MER style: aggression | negative | 7 | {k} | {} | false | G9 |

**behavior_category count = 155.**

---

## 3. `behavior_category_mcl` — UNION of per-category factor rows

PK(category_id,factor_code). Collapsed by (category_id,factor_code); `weight` = highest stated; `is_critical=true` for j & k (statute-critical) wherever mapped. `sources` merged.

| category_id | factor | weight | is_critical | sources |
|---|---|---|---|---|
| threats | k | high | true | G1 |
| threats | j | medium | true | G1 |
| child_weaponization | j | high | true | G1 |
| child_weaponization | k | medium | true | G1 |
| monitoring_stalking | k | high | true | G1 |
| monitoring_stalking | g | medium | false | G1 |
| homophobic_slurs | f | high | false | G1 |
| homophobic_slurs | k | medium | true | G1 |
| isolation_tactics | j | medium | true | G1 |
| isolation_tactics | k | high | true | G1 |
| gaslighting | a | medium | false | G3,G4 |
| gaslighting | f | high | false | G2,G3,G4 |
| gaslighting | g | high | false | G2 |
| gaslighting | k | high | true | G1,G2,G3,G4 |
| double_bind | k | high | true | G1 |
| double_bind | j | medium | true | G1 |
| character_attacks | f | high | false | G1 |
| character_attacks | k | medium | true | G1 |
| financial_control | c | high | false | G1,G5,G9 |
| financial_control | k | medium | true | G1,G5 |
| financial_control | l | low | false | G5 |
| triangulation | f | medium | false | G5,G7 |
| triangulation | j | high | true | G1,G5,G7 |
| triangulation | k | high | true | G1,G7 |
| triangulation | l | low | false | G5 |
| communication_control | j | medium | true | G1 |
| communication_control | k | medium | true | G1 |
| substance_shaming | f | high | false | G1 |
| substance_shaming | g | medium | false | G1 |
| mental_health_stigma | f | high | false | G1 |
| mental_health_stigma | g | medium | false | G1 |
| love_bombing | a | high | false | G1,G3,G4 |
| love_bombing | f | high | false | G3,G4 |
| love_bombing | j | medium | true | G1,G2 |
| love_bombing | k | medium | true | G1,G2 |
| love_bombing | l | low | false | G2 |
| blame_shifting | f | high | false | G2,G3,G4 |
| blame_shifting | j | medium | true | G4 |
| blame_shifting | k | high | true | G3,G4 |
| minimizing | f | high | false | G2,G3,G4 |
| minimizing | j | low | false | G4 |
| minimizing | k | high | true | G3 |
| circular | l | low | false | G2 |
| darvo_deny | f | medium | false | G2 |
| darvo_attack | f | high | false | G2 |
| darvo_attack | k | medium | true | G2 |
| darvo_reverse | f | high | true | G2 |
| darvo_reverse | k | high | true | G2 |
| overelaboration | f | high | false | G2,G3 |
| overelaboration | l | low | false | G2,G4 |
| excessive_gratitude | l | low | false | G2 |
| excessive_gratitude | f | medium | false | G2 |
| debt_reminders | f | medium | false | G2 |
| savior_complex | f | medium | false | G2 |
| savior_complex | k | high | true | G2 |
| substance_alcohol | g | low | false | G2 |
| substance_weaponized | f | medium | false | G2 |
| substance_weaponized | g | medium | false | G2 |
| substance_weaponized | k | high | true | G2(via substance_weaponization) |
| adderall_control | c | medium | false | G2 |
| adderall_control | g | medium | false | G2 |
| adderall_control | k | high | true | G2 |
| infidelity | f | medium | false | G2 |
| financial_weaponized | c | medium | false | G2 |
| financial_weaponized | f | medium | false | G2 |
| sexual_shaming | b | medium | false | G4 |
| sexual_shaming | f | high | false | G2,G4 |
| sexual_shaming | k | medium | true | G2,G4 |
| parental_alienation | a | high | false | G2,G3,G4 |
| parental_alienation | i | medium | false | G3,G4 |
| parental_alienation | j | high | true | G2,G3,G4 |
| parental_alienation | k | medium | true | G2,G4 |
| medical_abuse | c | medium | false | G2 |
| medical_abuse | f | medium | false | G4 |
| medical_abuse | g | high | true | G2,G4 |
| medical_abuse | j | medium | true | G4 |
| medical_abuse | k | high | false | G2 |
| reproductive_coercion | f | high | true | G2 |
| reproductive_coercion | j | high | true | G4 |
| reproductive_coercion | k | high | true | G2,G4 |
| reproductive_coercion | l | medium | false | G4 |
| victim_deference | k | medium | false | G2 |
| abuser_directives | k | high | false | G2 |
| certainty_absolutes | l | low | false | G2 |
| hedge_words | l | low | false | G2 |
| darvo | f | high | false | G3,G4 |
| darvo | j | high | true | G3,G4 |
| darvo | k | high | true | G3,G4 |
| coercive_control | c | high | false | G3,G4 |
| coercive_control | j | high | true | G3,G4 |
| coercive_control | k | high | true | G3,G4 |
| affirmations | a | high | false | G3,G4 |
| affirmations | f | high | false | G3 |
| expectation_setting | a | high | false | G3 |
| expectation_setting | c | high | false | G3 |
| cooperation | a | medium | false | G4 |
| cooperation | b | high | false | G3 |
| cooperation | d | medium | false | G4 |
| cooperation | j | high | true | G3 |
| dependency_cultivation | f | high | false | G3 |
| stonewalling | f | medium | false | G4 |
| stonewalling | k | medium | true | G4 |
| financial_abuse | c | high | false | G4 |
| financial_abuse | j | medium | true | G4 |
| substance_weaponization | b | medium | false | G4 |
| substance_weaponization | f | high | false | G4 |
| substance_weaponization | g | high | false | G4 |
| substance_weaponization | k | high | true | G4 |
| reactive_abuse | f | medium | false | G4 |
| reactive_abuse | j | medium | true | G4 |
| reactive_abuse | k | medium | true | G4 |
| character_assassination | b | medium | false | G4 |
| character_assassination | f | high | false | G4 |
| character_assassination | k | medium | true | G4 |
| isolation | c | high | false | G9 |
| isolation | j | high | true | G4,G5 |
| isolation | k | high | true | G4,G7,G9 |
| hoovering | a | medium | false | G4 |
| hoovering | f | medium | false | G4 |
| parenting_time | j | high | true | G4 |
| parenting_time | k | medium | true | G4 |
| gatekeeping | j | high | true | G4 |
| special_needs | a | high | false | G4 |
| special_needs | c | high | false | G4 |
| special_needs | l | medium | false | G4 |
| threats_intimidation | j | medium | true | G4 |
| threats_intimidation | k | high | true | G4,G9 |
| future_faking | l | low | false | G4 |
| apologies | l | low | false | G4 |
| gift_giving | c | low | false | G4 |
| power_asymmetry | j | low | false | G4 |
| power_asymmetry | l | low | false | G4 |
| manipulation | l | low | false | G5 |
| intimidation | f | high | false | G7 |
| intimidation | k | high | true | G5,G7 |
| denial | f | high | false | G7 |
| denial | l | low | false | G5 |
| stalking | g | medium | false | G5 |
| stalking | k | high | true | G5 |
| coordinated_abuse | j | medium | true | G5 |
| coordinated_abuse | k | high | true | G5 |
| coordinated_abuse | l | low | false | G5 |
| smear_campaign | f | medium | false | G5,G7 |
| smear_campaign | j | high | true | G5,G7 |
| smear_campaign | k | high | true | G7 |
| silent_treatment | j | medium | true | G5 |
| silent_treatment | l | low | false | G5 |
| communication_blocking | j | high | true | G5 |
| visit_blocking | j | high | true | G5 |
| parenting_time_denial | j | high | true | G5 |
| custody_interference | j | high | true | G5 |
| custody_interference | k | high | true | G5 |
| child_reference | i | medium | false | G5 |
| economic_sabotage | c | high | false | G7 |
| economic_sabotage | k | high | true | G7 |
| suicide_baiting | f | high | false | G7 |
| suicide_baiting | g | high | false | G7 |
| suicide_baiting | k | high | true | G7 |
| projection | f | high | false | G7,G8 |
| minimization | f | high | false | G7 |
| fabrication | f | high | false | G7 |
| fabrication | k | high | true | G7 |
| misdirection | f | high | false | G7 |
| inconsistent_account | f | high | false | G7 |
| manufactured_crisis | f | high | false | G7 |
| manufactured_crisis | k | high | true | G7 |
| child_exposure | f | high | false | G7 |
| child_exposure | j | high | true | G7 |
| child_exposure | k | high | true | G7 |
| trauma_exploitation | f | high | false | G7 |
| trauma_exploitation | k | high | true | G7 |
| substance_endangerment | c | high | false | G7 |
| substance_endangerment | g | high | false | G7 |
| substance_endangerment | k | high | true | G7 |
| medical_neglect | c | high | false | G7 |
| medical_neglect | g | high | false | G7 |
| bpd_self_harm_threat | g | high | false | G6 |
| bpd_self_harm_threat | k | high | true | G6 |
| custody_court_manipulation | f | medium | false | G6 |
| custody_court_manipulation | j | high | true | G6 |
| custody_gatekeeping | j | high | true | G6 |
| custody_schedule_interference | j | medium | true | G6 |
| custody_child_messenger | i | medium | false | G6 |
| custody_child_messenger | j | high | true | G6 |
| custody_parental_replacement | a | high | false | G6 |
| custody_parental_replacement | j | high | true | G6 |
| feigning_incompetence | c | medium | false | G8 |
| feigning_incompetence | j | medium | true | G8 |
| defensiveness_evasion | f | high | false | G8 |
| social_media_deception | f | high | false | G8 |
| last_minute_changes | j | high | true | G8 |
| emotional_dysregulation | g | high | false | G8 |
| guilt_tripping | f | medium | false | G8 |
| guilt_tripping | k | medium | true | G8 |
| feigned_concern | f | medium | false | G8 |
| feigned_concern | j | medium | true | G8 |
| flying_monkeys | j | high | true | G8 |
| flying_monkeys | k | high | true | G8 |
| devaluation | a | high | false | G8 |
| devaluation | f | high | false | G8 |
| discard | a | high | false | G8 |
| discard | j | medium | true | G8 |
| child_endangerment | c | high | false | G8 |
| child_endangerment | g | high | true | G8 |
| child_endangerment | k | high | true | G8 |
| autism_weaponization | a | high | false | G8 |
| autism_weaponization | c | high | true | G8 |
| autism_weaponization | j | high | true | G8 |
| block_unblock_cycle | j | high | true | G8 |
| block_unblock_cycle | k | medium | true | G8 |
| word_salad | l | low | false | G8 |
| selective_amnesia | f | high | false | G8 |
| monitoring_surveillance | k | high | true | G9 |
| gaslighting_reality_distortion | k | high | true | G9 |
| verbal_degradation | b | high | false | G9 |
| verbal_degradation | k | high | true | G9 |
| autonomy_deprivation | c | high | false | G9 |
| autonomy_deprivation | k | high | true | G9 |
| identity_erosion | k | high | true | G9 |
| sexual_reproductive_coercion | k | high | true | G9 |
| jealousy_possessiveness | k | high | true | G9 |
| narcissistic_entitlement | k | high | true | G9 |
| legal_system_abuse | j | high | true | G9 |
| legal_system_abuse | k | high | true | G9 |
| entrapment_fear | k | high | true | G9 |

**behavior_category_mcl count = 205.**

---

## 4. `detection_pattern` — full UNION (generic phrases + genericized regex; epithets/identifiers/vuln-tokens routed to §5)

All rows `bias_caution=true`, `is_active=true`, `is_case_specific=false`, `authored_perspective='single_party_complainant'`. `score`=`max(1,severity)` (G2 rule) for negatives; severity-0 markers keep `severity=0`. Child names stripped to `<CHILD_NAME>` / `her|him|the kid`. Exact dups (same category_id+normalized pattern+match_type) collapsed → `sources` merged, MAX severity kept. Near-dups (incl. same text at different `match_type`) kept separate.

### gaslighting
| pattern | match_type | sev | sources |
|---|---|---|---|
| `i never said that` | literal | 8 | G2,G6 |
| `you imagined` | literal | 8 | G2,G6 |
| `you're paranoid` | literal | 7 | G2 |
| `that never happened` | literal | 9 | G2,G6 |
| `no one will believe` | literal | 9 | G2,G6 |
| `you're crazy` | literal | 9 | G2 |
| `you're just high` | literal | 8 | G2 |
| `just kidding` | literal | 6 | G2,G6 |
| `you're overreacting` | literal | 7 | G2 |
| `this is the drugs talking` | literal | 8 | G2,G6 |
| `you're twisting my words` | literal | 7 | G8 |
| `you have issues` | literal | 6 | G8 |
| `that's not how it happened` | literal | 7 | G8 |
| `you're misremembering` | literal | 8 | G8 |
| `you're confused` | literal | 7 | G8 |
| `that never happened` | regex | 7 | G1 |
| `you'?re (crazy\|imagining\|making (it\|this\|that) up)` | regex | 7 | G1 |
| `i never said that` | regex | 7 | G1 |
| `you'?re (being\|too) (dramatic\|sensitive\|emotional)` | regex | 7 | G1 |
| `you always (exaggerate\|overreact\|blow things out of proportion)` | regex | 7 | G1 |
| `that'?s not (what\|how) (it\|that) happened` | regex | 7 | G1 |
| `you'?re (twisting\|changing\|distorting) (my words\|what i said\|the story)` | regex | 7 | G1 |
| `you know that'?s not true` | regex | 7 | G1 |
| `(?i)(i never\|would never\|did not\|didn't\|never happened)` | regex | 8 | G3 |
| `(?i)(imagined\|imagining\|made up\|in your head\|crazy\|insane\|delusional)` | regex | 9 | G3 |
| `(?i)(no one\|nobody\|will believe\|won't believe\|no one will)` | regex | 10 | G3 |

### blame_shifting
| pattern | match_type | sev | sources |
|---|---|---|---|
| `this is your fault` | literal | 7 | G2,G6 |
| `you made me` | literal | 8 | G2,G6 |
| `because of you` | literal | 7 | G2,G6 |
| `you started this` | literal | 6 | G2,G6 |
| `you always do this` | literal | 7 | G2,G6 |
| `if you hadn't` | literal | 7 | G2 |
| `look what you made me do` | literal | 9 | G2,G6 |
| `you're the one who started it` | literal | 7 | G9 |
| `i only acted that way because you pushed me to it` | literal | 7 | G9 |
| `(?i)(your fault\|you made me\|because of you\|you're the reason)` | regex | 8 | G3 |
| `(?i)(look what you\|see what you\|this is your\|you caused)` | regex | 7 | G3 |

### minimizing
| pattern | match_type | sev | sources |
|---|---|---|---|
| `not a big deal` | literal | 6 | G2,G6 |
| `you're too sensitive` | literal | 7 | G2 |
| `calm down` | literal | 5 | G2,G6 |
| `you're being dramatic` | literal | 6 | G2 |
| `get over it` | literal | 7 | G2,G6 |
| `stop making a scene` | literal | 6 | G2,G6 |
| `it was just a joke` | literal | 6 | G2,G6 |
| `relax` | literal | 5 | G2,G6 |
| `is that really something to get upset about` | literal | 5 | G9 |
| `you're making a big deal out of nothing` | literal | 5 | G9 |
| `(?i)(not a big deal\|no big deal\|not big deal\|making a big\|overreacting)` | regex | 6 | G3 |
| `(?i)(calm down\|you need to calm\|just calm\|relax\|settle down)` | regex | 5 | G3 |

### circular
| pattern | match_type | sev | sources |
|---|---|---|---|
| `what even is the point` | literal | 5 | G2 |
| `that's not the point` | literal | 6 | G2 |
| `you keep changing` | literal | 6 | G2,G6 |
| `you know what i mean` | literal | 5 | G2,G6 |
| `anyway` | literal | 5 | G2,G6 |
| `whatever` | literal | 5 | G2,G6 |
| `we're not in high school` | literal | 6 | G2 |

### darvo_deny
| pattern | match_type | sev | sources |
|---|---|---|---|
| `i never` | literal | 8 | G2,G6 |
| `i didn't` | literal | 8 | G2 |
| `that never happened` | literal | 9 | G2,G6 |
| `that's not true` | literal | 8 | G2 |
| `you're making that up` | literal | 9 | G2 |
| `i would never` | literal | 7 | G2,G6 |
| `that's a lie` | literal | 9 | G2 |

### darvo_attack
| pattern | match_type | sev | sources |
|---|---|---|---|
| `you're crazy` | literal | 9 | G2 |
| `you're lying` | literal | 9 | G2 |
| `you're the abusive one` | literal | 10 | G2 |
| `you're manipulating` | literal | 9 | G2 |
| `you're gaslighting me` | literal | 10 | G2 |
| `you're toxic` | literal | 9 | G2 |
| `you're the problem` | literal | 9 | G2 |
| `you're unstable` | literal | 9 | G2 |
| `you're delusional` | literal | 9 | G2 |

### darvo_reverse
| pattern | match_type | sev | sources |
|---|---|---|---|
| `i'm the victim here` | literal | 10 | G2 |
| `you're attacking me` | literal | 10 | G2 |
| `you're abusing me` | literal | 10 | G2 |
| `i'm the one being hurt` | literal | 10 | G2 |
| `you're hurting me` | literal | 10 | G2 |
| `i'm scared of you` | literal | 10 | G2 |
| `you're the aggressor` | literal | 10 | G2 |
| `i need protection from you` | literal | 10 | G2,G6 |

### darvo (consolidated)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `(?i)(i never\|would never\|that never\|didn't happen\|not true)` | regex | 7 | G3 |
| `(?i)(protect.*from you\|you're the\|victim\|abuser\|i need)` | regex | 10 | G3 |
| `darvo_stage_markers` (keywords {deny,attack,reverse victim,reverse offender}) | literal | 9 | G7 |

### overelaboration
| pattern | match_type | sev | sources |
|---|---|---|---|
| `i'm at` | literal | 7 | G2 |
| `i'm still at` | literal | 7 | G2 |
| `i'm heading to` | literal | 7 | G2 |
| `i'll be at` | literal | 7 | G2 |
| `i'm on my way to` | literal | 7 | G2 |
| `i just left` | literal | 7 | G2,G6 |
| `i just arrived at` | literal | 7 | G2,G6 |
| `i left at` | literal | 7 | G2,G6 |
| `i'll be back by` | literal | 7 | G2 |
| `i've been here since` | literal | 7 | G2 |
| `i'll be done in` | literal | 7 | G2 |
| `i'm doing this because` | literal | 8 | G2 |
| `i had to` | literal | 8 | G2,G6 |
| `i needed to` | literal | 8 | G2,G6 |
| `the reason is` | literal | 8 | G2,G6 |
| `i'm just` | literal | 7 | G2 |
| `i was just` | literal | 7 | G2,G6 |
| `before you ask` | literal | 8 | G2,G6 |
| `i know you're wondering` | literal | 8 | G2 |
| `just so you know` | literal | 7 | G2,G6 |
| `for the record` | literal | 7 | G2,G6 |
| `to be clear` | literal | 7 | G2,G6 |
| `let me explain` | literal | 7 | G6 |
| `(?i)(just (left\|happened\|went)\|before you\|had to)` | regex | 4 | G3 |

### love_bombing
| pattern | match_type | sev | sources |
|---|---|---|---|
| `perfect` | literal | 5 | G2,G6 |
| `amazing` | literal | 5 | G2,G6 |
| `soulmate` | literal | 6 | G2,G6 |
| `can't live without you` | literal | 7 | G2 |
| `always` | literal | 5 | G2,G6 |
| `forever` | literal | 5 | G2,G6 |
| `everything` | literal | 5 | G2,G6 |
| `desperate` | literal | 6 | G2,G6 |
| `need you` | literal | 6 | G2,G6 |
| `you're the only one who understands me` | literal | 6 | G2 |
| `i've never felt this way before` | literal | 6 | G2 |
| `i want to give you everything` | literal | 6 | G2,G6 |
| `i love you so much` | regex | 4 | G1 |
| `you'?re (the best\|amazing\|perfect\|everything to me)` | regex | 4 | G1 |
| `i can'?t live without you` | regex | 4 | G1 |
| `you'?re (the only one\|all i (want\|need))` | regex | 4 | G1 |
| `i miss you (so much\|baby)` | regex | 4 | G1 |
| `come (over\|here).*?(i need you\|baby\|please)` | regex | 4 | G1 |
| `(?i)(perfect\|amazing\|wonderful\|incredible\|soulmate)` | regex | 4 | G3 |
| `(?i)(forever\|always\|eternal\|never leave\|always be)` | regex | 5 | G3 |
| `(?i)(give.*everything\|all i have\|do anything\|sacrifice)` | regex | 6 | G3 |

### excessive_gratitude
| pattern | match_type | sev | sources |
|---|---|---|---|
| `i owe you everything` | literal | 6 | G2,G6 |
| `i could never repay you` | literal | 6 | G2,G6 |
| `i don't deserve you` | literal | 5 | G2 |
| `you've done so much for me` | literal | 5 | G2 |
| `i'm so grateful` | literal | 4 | G2 |
| `thank you for everything` | literal | 4 | G2,G6 |
| `i don't know what i'd do without you` | literal | 6 | G2 |
| `you saved me` | literal | 7 | G2,G6 |
| `i owe you my life` | literal | 7 | G2,G6 |

### debt_reminders
| pattern | match_type | sev | sources |
|---|---|---|---|
| `remember when i` | literal | 7 | G2,G6 |
| `after all i've done` | literal | 8 | G2 |
| `i was there for you when` | literal | 7 | G2,G6 |
| `don't forget i` | literal | 7 | G2 |
| `i helped you` | literal | 6 | G2,G6 |
| `i gave you` | literal | 6 | G2,G6 |

### savior_complex
| pattern | match_type | sev | sources |
|---|---|---|---|
| `i'll protect you` | literal | 7 | G2 |
| `i'll keep you safe` | literal | 7 | G2 |
| `i won't let anyone hurt you` | literal | 7 | G2 |
| `you need me` | literal | 8 | G2,G6 |
| `i'll take care of you` | literal | 6 | G2 |
| `i'll fix this` | literal | 6 | G2 |
| `let me handle it` | literal | 6 | G2,G6 |
| `i'll make it better` | literal | 5 | G2 |
| `trust me to protect you` | literal | 7 | G2,G6 |
| `everyone else will hurt you` | literal | 9 | G2,G6 |
| `the world is dangerous` | literal | 8 | G2,G6 |
| `you can't trust anyone but me` | literal | 9 | G2 |
| `they're all out to get you` | literal | 9 | G2 |
| `i'm the only one who cares` | literal | 8 | G2 |

### substance_alcohol (neutral severity-0 lexical markers)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `drink` | literal | 0 | G2,G6 |
| `drank` | literal | 0 | G2,G6 |
| `drunk` | literal | 0 | G2,G6 |
| `buzzed` | literal | 0 | G2,G6 |
| `tipsy` | literal | 0 | G2,G6 |
| `wasted` | literal | 0 | G2,G6 |
| `bottle` | literal | 0 | G2,G6 |
| `wine` | literal | 0 | G2,G6 |
| `beer` | literal | 0 | G2,G6 |
| `liquor` | literal | 0 | G2,G6 |
| `vodka` | literal | 0 | G2,G6 |
| `tequila` | literal | 0 | G2,G6 |
| `hungover` | literal | 0 | G2,G6 |
| `fireball` | literal | 0 | G2,G6 |

> NOTE: G6/G9 alternatively route these substance-mention words to `pattern_lexicon` (restricted) as vulnerability terms; preserved here as neutral DP markers per G2/G4 (majority + non-identifying). The case-specific brand "fireball" is ALSO seeded restricted in §5.

### substance_weaponized (phrases only; single-token slurs → §5)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `you're just high` | literal | 8 | G2 |
| `are you on something` | literal | 8 | G2,G6 |
| `this is the drugs talking` | literal | 8 | G2,G6 |
| `\b(crackhead\|crack head\|tweaker\|junkie\|addict)\b` | regex | 5 | G1 |
| `\bhigh (as fuck\|af\|again)\b` | regex | 5 | G1 |
| `on (that shit\|drugs\|dope)` | regex | 5 | G1 |

### adderall_control (phrases + neutral medication nouns)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `adderall` | literal | 7 | G2,G6 |
| `addy` | literal | 7 | G2,G6 |
| `pills` | literal | 6 | G2,G6 |
| `script` | literal | 6 | G2,G6 |
| `share` | literal | 7 | G2,G6 |
| `split` | literal | 7 | G2,G6 |
| `your turn` | literal | 8 | G2,G6 |
| `how many did you take` | literal | 8 | G2,G6 |
| `i'm holding onto them for you` | literal | 9 | G2 |
| `you can't control yourself` | literal | 9 | G2 |

### infidelity
| pattern | match_type | sev | sources |
|---|---|---|---|
| `cheating` | literal | 8 | G2,G6 |
| `cheated` | literal | 8 | G2,G6 |
| `slept with` | literal | 8 | G2,G6 |
| `affair` | literal | 9 | G2,G6 |
| `secret` | literal | 6 | G2,G6 |
| `seeing someone` | literal | 8 | G2,G6 |
| `loyal` | literal | 5 | G2,G6 |
| `faithful` | literal | 5 | G2,G6 |
| `he's just a friend` | literal | 6 | G2 |
| `we just work together` | literal | 6 | G2,G6 |
| `you're being jealous` | literal | 7 | G2 |
| `why don't you trust me` | literal | 7 | G2 |

### financial_weaponized / financial_control / financial_abuse / economic_sabotage
| category | pattern | match_type | sev | sources |
|---|---|---|---|---|
| financial_weaponized | `you don't do anything` | literal | 8 | G2 |
| financial_weaponized | `i'm the one who works hard` | literal | 7 | G2 |
| financial_weaponized | `what do i get out of this` | literal | 8 | G2,G6 |
| financial_weaponized | `it's your responsibility to provide` | literal | 8 | G2 |
| financial_control | `you (owe\|need to pay\|better pay) me` | regex | 6 | G1 |
| financial_control | `where'?s? (the\|my) money` | regex | 6 | G1 |
| financial_control | `pay (me\|for\|child support)` | regex | 6 | G1 |
| financial_control | `(don't\|won't) give you (shit\|anything\|a dime)` | regex | 6 | G1 |
| coercive_control | `(?i)(money\|finances\|budget\|allowance\|spend\|account)` | regex | 8 | G3 |
| economic_sabotage | `financial_coercion_modes` (kw {conditional aid,sabotage,dependency creation,allowance,cut off}) | literal | 7 | G7 |

### sexual_shaming (phrases only; single-token epithets → §5)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `no wonder everyone leaves you` | literal | 10 | G2,G6 |
| `to think i ever did` | literal | 9 | G2,G6 |

### parental_alienation (generic; child/family names → §5)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `doesn't want to see you` | literal | 10 | G2 |
| `i have to protect the children from you` | literal | 10 | G2,G6 |
| `you don't deserve (her\|him\|to be a (father\|dad\|parent))` | regex | 9 | G1 |
| `(forget about\|don't expect to see) (her\|him\|the kid)` | regex | 9 | G1 |
| `if you (want to see\|wanna see) (her\|him)` | regex | 9 | G1 |
| `you('re\| are)n('\|o)?t (gonna \|going to )?(see\|have\|get) (her\|him\|the kid\|<CHILD_NAME>)` | regex | 9 | G1 |
| `(blocking you\|blocked).*?(from\|so you can't see) (her\|him)` | regex | 9 | G1 |
| `(?i)(your (father\|mother\|dad\|mom)\|bad (father\|mother)\|doesn't love)` | regex | 10 | G3 |
| `(?i)(can't see\|not allowed\|refuse\|won't let\|preventing)` | regex | 9 | G3 |
| `dad(?:dy)?\s+(?:is\|doesn't\|won't)\|mom(?:my)?\s+(?:is\|doesn't\|won't)` | regex | 10 | G4 |
| `who\s+do\s+you\s+want\s+to\s+(?:stay\|live)\s+with` | regex | 10 | G4 |
| `gatekeeping_actions` (kw {blocked access,disparaged parent,refused meds,not allowed,won't let}) | literal | 9 | G7 |

### child_weaponization / communication_control / isolation_tactics / monitoring_stalking (G1 coercive-control regex)
| category | pattern | match_type | sev | sources |
|---|---|---|---|---|
| communication_control | `(blocked\|blocking) you` | regex | 5 | G1 |
| communication_control | `don't (text\|call\|contact) me` | regex | 5 | G1 |
| communication_control | `leave me (alone\|the fuck alone)` | regex | 5 | G1 |
| communication_control | `lose my number` | regex | 5 | G1 |
| communication_control | `never (talk\|speak) to me again` | regex | 5 | G1 |
| isolation_tactics | `(everyone\|everybody\|people) (knows\|think\|say) you'?re` | regex | 7 | G1 |
| isolation_tactics | `told (everyone\|everybody\|them) (about\|what) you` | regex | 7 | G1 |
| isolation_tactics | `nobody (likes\|wants\|trusts) you` | regex | 7 | G1 |
| isolation_tactics | `your (family\|friends) (knows\|know) (what\|who) you are` | regex | 7 | G1 |
| monitoring_stalking | `i know (where you\|what you\|who you)` | regex | 8 | G1 |
| monitoring_stalking | `i('m\| am) watching you` | regex | 8 | G1 |
| monitoring_stalking | `i saw you (at\|with)` | regex | 8 | G1 |
| monitoring_stalking | `someone told me you` | regex | 8 | G1 |

### isolation / coercive_control (G3/G4/G5)
| category | pattern | match_type | sev | sources |
|---|---|---|---|---|
| coercive_control | `(?i)(isolat\|alone\|no friends\|can't see\|don't need)` | regex | 9 | G3 |
| coercive_control | `(?i)(track\|monitor\|check\|where are\|who are\|location)` | regex | 8 | G3 |
| coercive_control | `comply\|do\s+what\s+I\s+(?:say\|tell)` | regex | 9 | G4 |
| coercive_control | `if\s+you\s+don't\|unless\s+you\|or\s+else` | regex | 8 | G4 |

### character_attacks / character_assassination (phrases/regex; epithet tokens → §5)
| category | pattern | match_type | sev | sources |
|---|---|---|---|---|
| character_attacks | `piece of (shit\|trash\|garbage)` | regex | 6 | G1 |
| character_attacks | `\b(motherfucker\|mother fucker)\b` | regex | 6 | G1 |
| character_attacks | `bitch (made\|ass)` | regex | 6 | G1 |
| character_attacks | `\bpussy\b` | regex | 6 | G1 |
| character_attacks | `good for nothing` | regex | 6 | G1 |
| character_attacks | `worthless` | regex | 6 | G1 |
| character_attacks | `pathetic` | regex | 6 | G1 |
| character_attacks | `loser` | regex | 6 | G1 |
| character_assassination | `drug(?:s)?\|high\|using\|addict` | regex | 9 | G4 |
| character_assassination | `everyone can see what you're like` | literal | 7 | G8 |

### mental_health_stigma / substance_shaming (G1 regex)
| category | pattern | match_type | sev | sources |
|---|---|---|---|---|
| mental_health_stigma | `\b(psycho\|crazy\|insane\|mental\|nuts)\b` | regex | 5 | G1 |
| mental_health_stigma | `\b(sick\|twisted\|fucked up) (in the head\|mentally)` | regex | 5 | G1 |
| mental_health_stigma | `need (help\|therapy\|meds\|medication)` | regex | 5 | G1 |
| mental_health_stigma | `\bweirdo\b` | regex | 5 | G1 |
| substance_shaming | `\b(crackhead\|crack head\|tweaker\|junkie\|addict)\b` | regex | 5 | G1 |
| substance_shaming | `\bhigh (as fuck\|af\|again)\b` | regex | 5 | G1 |
| substance_shaming | `on (that shit\|drugs\|dope)` | regex | 5 | G1 |

### threats / threats_intimidation / double_bind (G1 regex)
| category | pattern | match_type | sev | sources |
|---|---|---|---|---|
| threats | `(i'll\|i will\|gonna) (fuck you up\|beat\|kill\|hurt\|destroy)` | regex | 10 | G1 |
| threats | `watch your back` | regex | 10 | G1 |
| threats | `you('re\| are) (gonna\|going to) regret` | regex | 10 | G1 |
| threats | `better watch out` | regex | 10 | G1 |
| threats | `i('ll\| will) make you` | regex | 10 | G1 |
| double_bind | `if you (loved\|cared about) me.*?you (would\|wouldn't)` | regex | 7 | G1 |
| double_bind | `you say.*?but you (don't\|never\|won't)` | regex | 7 | G1 |
| double_bind | `(come over\|see me).*?(leave me alone\|don't contact)` | regex | 7 | G1 |

### triangulation
| pattern | match_type | sev | sources |
|---|---|---|---|
| `(everyone\|people\|they) (think\|say\|know) you'?re` | regex | 6 | G1 |
| `i told (them\|everyone\|her\|him) about you` | regex | 6 | G1 |
| `(he\|she\|they) (said\|told me\|thinks) you'?re` | regex | 6 | G1 |
| `my (friend\|mom\|family).*?(doesn't like\|hates\|thinks) you` | regex | 6 | G1 |
| `(unlike you\|at least\|he\|she).*(treats me\|is there for me\|cares)` | regex | 6 | G1 |
| `triangulation_roles` (kw {flying monkey,triangulate,go-between,proxy}) | literal | 7 | G7 |

### homophobic_slurs (generic slur regex; named-target epithets → §5)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `\bf+a+g+([og]+(e\|o)?t\|it)\b` | regex | 7 | G1 |
| `\bgay\b.*?\b(ass\|bitch\|fuck)` | regex | 7 | G1 |
| `\bqueer\b` | regex | 7 | G1 |

### medical_abuse (diagnosis/control phrases; bare medication nouns kept; G6 flags some restricted)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `you need your meds` | literal | 9 | G2,G6 |
| `did you take your pills` | literal | 8 | G2,G6 |
| `you're not thinking clearly` | literal | 9 | G2 |
| `it's the medication talking` | literal | 9 | G2 |
| `you can't make decisions` | literal | 10 | G2 |
| `you're not well enough` | literal | 9 | G2 |
| `i'm holding your meds` | literal | 10 | G2 |
| `you can't be trusted with` | literal | 9 | G2 |
| `you're bipolar` | literal | 9 | G2 |
| `you're borderline` | literal | 9 | G2 |
| `you're schizophrenic` | literal | 9 | G2 |
| `that's your [condition] talking` | literal | 9 | G2 |
| `you're having an episode` | literal | 9 | G2 |
| `you need to be hospitalized` | literal | 10 | G2,G6 |
| `you're unstable` | literal | 9 | G2 |
| `doctor\|hospital\|sick\|medicine` | regex | 8 | G4 |
| `you\s+don't\s+need\s+to\s+know` | regex | 9 | G4 |

> `that's your [condition] talking` retains the literal `[condition]` slot verbatim; flag for regex conversion `that's your .* talking`.

### reproductive_coercion (behavioral threats; G6 flags restricted)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `i want you pregnant` | literal | 10 | G2,G6 |
| `you should get pregnant` | literal | 10 | G2,G6 |
| `stop taking birth control` | literal | 10 | G2,G6 |
| `i'll get you pregnant` | literal | 10 | G2 |
| `you can't leave if you're pregnant` | literal | 10 | G2 |
| `a baby will fix us` | literal | 9 | G2,G6 |
| `you owe me a child` | literal | 10 | G2,G6 |
| `i sabotaged your birth control` | literal | 10 | G2,G6 |
| `i'll take the baby` | literal | 10 | G2 |
| `you'll never see the baby` | literal | 10 | G2 |
| `i'll prove you're unfit` | literal | 10 | G2 |
| `you're a bad mother` | literal | 9 | G2 |
| `the baby doesn't need you` | literal | 10 | G2 |

### victim_deference
| pattern | match_type | sev | sources |
|---|---|---|---|
| `if that's okay` | literal | 7 | G2 |
| `if you don't mind` | literal | 7 | G2 |
| `is that alright` | literal | 7 | G2,G6 |
| `sorry` | literal | 6 | G2,G6 |
| `my bad` | literal | 6 | G2,G6 |
| `i didn't mean to` | literal | 6 | G2 |
| `i apologize` | literal | 6 | G2,G6 |
| `i hope that's fine` | literal | 7 | G2 |
| `let me know if` | literal | 6 | G2,G6 |

### abuser_directives
| pattern | match_type | sev | sources |
|---|---|---|---|
| `where are you` | literal | 8 | G2,G6 |
| `what are you doing` | literal | 8 | G2,G6 |
| `who are you with` | literal | 8 | G2,G6 |
| `come here` | literal | 7 | G2,G6 |
| `go there` | literal | 7 | G2,G6 |
| `do this` | literal | 7 | G2,G6 |
| `stop that` | literal | 7 | G2,G6 |
| `tell me` | literal | 7 | G2,G6 |
| `show me` | literal | 8 | G2,G6 |
| `prove it` | literal | 8 | G2,G6 |

### certainty_absolutes (linguistic_marker, severity 0)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `always` | literal | 0 | G2,G6 |
| `never` | literal | 0 | G2,G6 |
| `nothing` | literal | 0 | G2,G6 |
| `everything` | literal | 0 | G2,G6 |
| `everyone` | literal | 0 | G2,G6 |
| `nobody` | literal | 0 | G2,G6 |
| `fact` | literal | 0 | G2,G6 |
| `obviously` | literal | 0 | G2,G6 |
| `clearly` | literal | 0 | G2,G6 |
| `literally` | literal | 0 | G2,G6 |

### hedge_words (linguistic_marker, severity 0)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `maybe` | literal | 0 | G2,G6 |
| `perhaps` | literal | 0 | G2,G6 |
| `possibly` | literal | 0 | G2,G6 |
| `might` | literal | 0 | G2,G6 |
| `could` | literal | 0 | G2,G6 |
| `i think` | literal | 0 | G2,G6 |
| `i guess` | literal | 0 | G2,G6 |
| `sort of` | literal | 0 | G2,G6 |
| `kind of` | literal | 0 | G2,G6 |
| `probably` | literal | 0 | G2,G6 |

### parenting_time / gatekeeping / special_needs (G4 regex)
| category | pattern | match_type | sev | sources |
|---|---|---|---|---|
| parenting_time | `you\s+(?:won't\|can't)\s+see\s+(?:her\|him\|the\s+kid)` | regex | 9 | G4 |
| parenting_time | `if\s+you\s+don't.*(?:her\|him\|daughter\|son)` | regex | 8 | G4 |
| gatekeeping | `block(?:ed\|ing)?\|stop\s+(?:texting\|calling)` | regex | 8 | G4 |
| special_needs | `autism\|autistic\|spectrum\|sensory\|meltdown` | regex | 8 | G4 |

### communication_blocking (G5 regex)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `\bblock(ed\|ing)?\s+(your\|his\|the)?\s*call` | regex | 9 | G5 |
| `\bcan'?t\s+call` | regex | 8 | G5 |
| `\bwon'?t\s+(let\|allow)\s+(you\|him)\s+call` | regex | 9 | G5 |
| `\bno\s+phone\s+(calls?\|contact)` | regex | 9 | G5 |
| `\bstop\s+calling` | regex | 8 | G5 |
| `\bignor(e\|ed\|ing)\s+(your\|his\|the)?\s*call` | regex | 8 | G5 |
| `\brefus(e\|ed\|ing)\s+to\s+answer` | regex | 8 | G5 |

### visit_blocking (G5 regex)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `\bblock(ed\|ing)?\s+(your\|his\|the)?\s*visit` | regex | 9 | G5 |
| `\bcan'?t\s+see\s+(her\|him)` | regex | 9 | G5 |
| `\bwon'?t\s+(let\|allow)\s+(you\|him)\s+(see\|visit)` | regex | 9 | G5 |
| `\bno\s+visitation` | regex | 9 | G5 |
| `\bcancel(ed\|ing)?\s+(your\|his\|the)?\s*(visit\|time)` | regex | 8 | G5 |
| `\bdenied?\s+(your\|his)?\s*(visit\|time\|access)` | regex | 9 | G5 |
| `\bkeep(ing)?\s+(her\|him)\s+from` | regex | 9 | G5 |
| `\bwon'?t\s+bring\s+(her\|him)` | regex | 9 | G5 |
| `\brefus(e\|ed\|ing)\s+to\s+(bring\|drop\s+off)` | regex | 9 | G5 |

### parenting_time_denial (G5 regex)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `\bno\s+parenting\s+time` | regex | 8 | G5 |
| `\bdenied?\s+parenting\s+time` | regex | 8 | G5 |
| `\binterfere?\s+with\s+(your\|his)\s+time` | regex | 8 | G5 |
| `\bnot\s+(your\|his)\s+weekend` | regex | 8 | G5 |
| `\bchanged?\s+(the\|our)\s+schedule` | regex | 7 | G5 |

### custody_interference (G5 regex)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `\bhide?\s+(her\|him\|the\s+child)` | regex | 9 | G5 |
| `\bmy\s+child\s+now` | regex | 9 | G5 |
| `\bnot\s+(your\|his)\s+(daughter\|child\|kid)` | regex | 9 | G5 |
| `\bstay\s+away\s+from` | regex | 8 | G5 |
| `\bno\s+contact` | regex | 8 | G5 |
| `\brestraining\s+order` | regex | 9 | G5 |
| `\bcall(ed\|ing)?\s+(the\s+)?police` | regex | 8 | G5 |

### child_reference (generic templates — also seeded as restricted lexicon §5)
| pattern | match_type | sev | sources |
|---|---|---|---|
| `my daughter` | literal | 8 | G2,G5,G6 |
| `our daughter` | literal | 7 | G2,G5,G6 |
| `the baby` | literal | 6 | G2,G5,G6 |
| `our child` | literal | 5 | G5 |
| `my kid` | literal | 4 | G5 |
| `the kid` | literal | 6 | G2,G6 |

> COURT-SAFETY: these generic kinship templates are ALSO routed to `pattern_lexicon` `child_reference` (restricted, is_case_specific=false) per G4/G6; retained here as low-severity relevance markers. Named child → §5 sealed only.

### Positive contrast classes (G5 literal example phrases; severity 0, latent score for contradiction phase)
| category | pattern | match_type | sev | score | sources |
|---|---|---|---|---|---|
| reassurances | `i'd never lie` | literal | 0 | 3 | G5 |
| reassurances | `you can trust me` | literal | 0 | 3 | G5 |
| reassurances | `i'm faithful` | literal | 0 | 3 | G5 |
| declarations_of_loyalty | `you're my everything` | literal | 0 | 3 | G5 |
| declarations_of_loyalty | `i only love you` | literal | 0 | 3 | G5 |

### Zep generic keyword sets (G7 literal)
| category | pattern (label) | keywords | sev | sources |
|---|---|---|---|---|
| smear_campaign | smear_intent | {ruin reputation,gain sympathy,cover tracks,isolate} | 8 | G7 |
| fabrication | fabricated_narrative_clusters | {abuse narrative,sobriety claim,victim stance,good mother} | 9 | G7 |
| misdirection | distraction_goals | {distract from drug use,sabotage work,garner sympathy} | 6 | G7 |
| trauma_exploitation | exploitation_mechanisms | {triggering ptsd,shaming,threat of recurrence} | 9 | G7 |
| substance_endangerment | substance_context | {maintenance,party,lethal,drunk driving,driving,alcohol,amphetamines,cocaine,mdma,cannabis,poly_substance} | 8 | G7 |

### G6 personality-disorder + custody categories (literal, net-new)
| category | pattern | sev | sources |
|---|---|---|---|
| npd_grandiosity | `better parent` | 7 | G6 |
| npd_grandiosity | `everyone agrees` | 5 | G6 |
| npd_grandiosity | `lucky to have me` | 6 | G6 |
| npd_grandiosity | `gave you the best years` | 5 | G6 |
| npd_entitlement | `i deserve` | 7 | G6 |
| npd_empathy_deficit | `makes me look` | 8 | G6 |
| npd_empathy_deficit | `being too dramatic` | 6 | G6 |
| bpd_abandonment | `going to abandon` | 6 | G6 |
| bpd_abandonment | `already abandoned` | 7 | G6 |
| bpd_splitting | `with me or against me` | 7 | G6 |
| bpd_splitting | `pure evil` | 6 | G6 |
| bpd_splitting | `never really loved` | 7 | G6 |
| bpd_self_harm_threat | `end it all` | 10 | G6 |
| aspd_callousness | `deserved it` | 7 | G6 |
| aspd_no_remorse | `you made me do` | 8 | G6 |
| aspd_no_remorse | `forced my hand` | 6 | G6 |
| custody_court_manipulation | `different judge` | 7 | G6 |
| custody_court_manipulation | `drag it out` | 8 | G6 |
| custody_court_manipulation | `game the system` | 9 | G6 |
| custody_gatekeeping | `none of your business` | 6 | G6 |
| custody_gatekeeping | `not allowed to see` | 8 | G6 |
| custody_gatekeeping | `without asking you` | 7 | G6 |
| custody_schedule_interference | `emergency came up` | 6 | G6 |
| custody_schedule_interference | `already made plans` | 7 | G6 |
| custody_child_messenger | `tell your dad` | 7 | G6 |
| custody_child_messenger | `find out what` | 8 | G6 |
| custody_parental_replacement | `real dad` | 8 | G6 |
| custody_parental_replacement | `real family` | 8 | G6 |
| custody_parental_replacement | `change their name` | 7 | G6 |

### G8 conversation-log net-new phrases (literal unless noted)
| category | pattern | sev | sources |
|---|---|---|---|
| defensiveness_evasion | `why are you attacking me` | 7 | G8 |
| defensiveness_evasion | `i can't believe you're asking me that` | 6 | G8 |
| defensiveness_evasion | `after everything i do for you` | 7 | G8 |
| defensiveness_evasion | `here we go again` | 5 | G8 |
| defensiveness_evasion | `i don't have to explain myself to you` | 7 | G8 |
| reactive_abuse | `see, you're losing it` | 8 | G8 |
| reactive_abuse | `this is what i have to deal with` | 7 | G8 |
| reactive_abuse | `you're the crazy one` | 8 | G8 |
| reactive_abuse | `i'm going to record this` | 8 | G8 |
| reactive_abuse | `look at you, you're having an episode` | 9 | G8 |
| reactive_abuse | `what are you going to do about it` | 7 | G8 |
| reactive_abuse | `see? this is why no one likes you` | 8 | G8 |
| reactive_abuse | `look at you, getting all worked up` | 7 | G8 |
| feigning_incompetence | `i'm not smart like you` | 5 | G8 |
| feigning_incompetence | `you know i'm bad at this stuff` | 5 | G8 |
| feigning_incompetence | `i never graduated, what do you expect` | 5 | G8 |
| feigning_incompetence | `just tell me what to do` | 4 | G8 |
| social_media_deception | `i don't even use snapchat` | 6 | G8 |
| social_media_deception | `i never send pictures` | 6 | G8 |
| social_media_deception | `you can check my phone` | 5 | G8 |
| social_media_deception | `(?i)\b(i don'?t\|i never)\s+(use\|have)\s+snap(chat)?\b` (regex; contradiction w/ prior `\b(snap\|snapchat)\b`) | 6 | G8 |
| last_minute_changes | `change of plans` | 5 | G8 |
| last_minute_changes | `something came up` | 5 | G8 |
| last_minute_changes | `have to cancel` | 6 | G8 |
| last_minute_changes | `we're not doing that anymore` | 7 | G8 |
| last_minute_changes | `you'll have to figure it out` | 7 | G8 |
| child_endangerment | `i only had one` | 7 | G8 |
| child_endangerment | `i'm fine to drive` | 9 | G8 |
| child_endangerment | `i can handle it` | 6 | G8 |
| child_endangerment | `stop worrying` | 5 | G8 |
| emotional_dysregulation | `brilliant idea` (manic; sev 0, bias_caution HIGH) | 0 | G8 |
| emotional_dysregulation | `i can solve everything` (manic; sev 0) | 0 | G8 |
| emotional_dysregulation | `what's the point` (depressive; sev 0) | 0 | G8 |
| emotional_dysregulation | `it will never get better` (depressive; sev 0) | 0 | G8 |
| emotional_dysregulation | `i'm a failure` (depressive; sev 0) | 0 | G8 |
| emotional_dysregulation | `i can't do anything right` (depressive; sev 0) | 0 | G8 |
| selective_amnesia | `you're confused` | 7 | G8 |
| feigned_concern | `i'm worried about him` | 6 | G8 |
| projection | `he's obsessed with me` | 7 | G8 |
| projection | `she is completely unstable` | 7 | G8 |
| devaluation | `nothing you do is good enough` | 7 | G8 |
| devaluation | `moving the goalposts` | 7 | G8 |
| devaluation | `nothing is ever good enough` | 6 | G8 |
| discard | `new supply` | 7 | G8 |
| discard | `blaming you for the relationship failure` | 6 | G8 |

### G9 12-tactic gaslighting subtype phrases (literal)
| category (subcategory) | pattern | sev | sources |
|---|---|---|---|
| countering | `you have a terrible memory` | 7 | G9 |
| countering | `you're putting words in my mouth` | 7 | G9 |
| countering | `you're misremembering` | 7 | G9 |
| gaslighting_reality_distortion (withholding) | `i don't know what you're talking about` | 6 | G9 |
| gaslighting_reality_distortion (withholding) | `you're not making any sense` | 6 | G9 |
| gaslighting_reality_distortion (withholding) | `are you done` | 6 | G9 |
| minimizing (trivializing) | `you're making a big deal out of nothing` | 5 | G9 |
| denial | `you're imagining things` | 7 | G9 |
| denial | `there's no proof of that` | 7 | G9 |
| diverting | `what about that time you` | 7 | G9 |
| diverting | `you're just trying to distract from your own mistakes` | 7 | G9 |
| stereotyping | `you're being hysterical` | 6 | G9 |
| stereotyping | `it must be that time of the month` | 6 | G9 |
| stereotyping | `what do you know, you're just a kid` | 6 | G9 |
| forgetting_feigned_amnesia | `i have no recollection of that` | 6 | G9 |
| forgetting_feigned_amnesia | `are you sure that even happened` | 6 | G9 |
| forgetting_feigned_amnesia | `my memory of that is completely different` | 6 | G9 |
| questioning_sanity | `you're losing your mind` | 8 | G9 |
| questioning_sanity | `you need to get help` | 8 | G9 |
| questioning_sanity | `everyone thinks you're unstable` | 8 | G9 |
| questioning_sanity | `you sound crazy right now` | 8 | G9 |
| questioning_sanity | `you seem unstable` | 8 | G9 |
| questioning_sanity | `everyone thinks you're paranoid` | 8 | G9 |
| joke_defense | `i was just kidding, can't you take a joke` | 6 | G9 |
| joke_defense | `you're too uptight` | 6 | G9 |
| joke_defense | `lighten up, it wasn't serious` | 6 | G9 |
| scapegoating | `it's always your fault` | 7 | G9 |
| scapegoating | `if it weren't for you everything would be fine` | 7 | G9 |
| scapegoating | `we all know who the real problem is` | 7 | G9 |
| future_faking | `things will be different once` | 6 | G9 |
| future_faking | `i promise i'll change, you just have to be patient` | 6 | G9 |
| feeling_police | `you shouldn't feel that way` | 5 | G9 |
| feeling_police | `there's no reason to be upset` | 5 | G9 |
| feeling_police | `why would you let that bother you` | 5 | G9 |
| overreaction_accusation (minimizing) | `you're overreacting` | 5 | G9 |
| overreaction_accusation (minimizing) | `you're too sensitive` | 5 | G9 |
| overreaction_accusation (minimizing) | `don't be so dramatic` | 5 | G9 |
| overreaction_accusation (minimizing) | `making a mountain out of a molehill` | 5 | G9 |
| categorical_denial (gaslighting) | `you're making that up` | 8 | G9 |
| categorical_denial (gaslighting) | `you must have imagined it` | 8 | G9 |
| subtle_shift | `that's not how it happened` | 6 | G9 |
| subtle_shift | `what i actually said was` | 6 | G9 |
| subtle_shift | `you're twisting my words` | 6 | G9 |
| weaponizing_allies_triangulation | `\b(\w+) agrees with me\b` (regex; filled name → §5) | 6 | G9 |
| weaponizing_allies_triangulation | `everyone knows that you` | 6 | G9 |
| weaponizing_allies_triangulation | `we were just talking about how you` | 6 | G9 |
| provocation_defense | `you provoked me` | 7 | G9 |
| provocation_defense | `you pushed me to it` | 7 | G9 |

### G9 platform-denial contradiction detector (regex)
| category | pattern | match_type | sev | sources |
|---|---|---|---|---|
| social_media_deception | prior `\b(snap\|snapchat\|instagram\|tiktok)\b` AND later `(?i)\b(i don'?t\|i never)\s+(use\|have)\s+(snap(chat)?\|insta(gram)?\|tiktok)\b` → contradiction flag | regex | 6 | G9 |

**detection_pattern count = 396.**

---

## 5. `pattern_lexicon` — UNION (sealed identifiers / restricted vulnerabilities & epithets)

`pattern_set_id` → `merged_behavior_seed_v1`. `is_case_specific=true` unless noted.

### 5a. SEALED identifiers (NEVER plaintext detection_pattern)
| lexicon_type | term | variants | match_type | relevance_signal | sev | mcl | tier | sources |
|---|---|---|---|---|---|---|---|---|
| child_identifier | `<CHILD_NAME>` (kailah) | {kyla,kaila,kailuh} | regex | child_subject_of_proceeding | 10 | {a,i,j,k} | sealed | G1,G2,G4,G5,G6 |
| party_identifier | (documenting party surname — Salem) | {} | literal | case-caption / documenting party | — | {} | sealed | G1 |
| party_identifier | (opposing party surname — Kinzel) | {} | literal | case-caption / opposing party | — | {} | sealed | G1 |
| personal_identifier | (father given name — Matt) | {petitioner,father} | literal | case-principal (father) | — | {} | sealed | G7 |
| personal_identifier | (mother given name — Catrina/Katrina) | {} | literal | case-principal (mother) | — | {} | sealed | G7,G8 |
| personal_identifier | (third-party — Dennis) | {} | literal | third-party associate | — | {} | sealed | G7 |
| relational_identifier | (her_mother / maternal grandmother) | {} | literal | rumor audience / triangulation node | — | {j} | sealed | G7 |
| party_name | opposing & documenting real names | {} | literal | subject_of_proceeding | — | {k} | sealed | G9 |
| verbatim_case_quote | real message quotes incl. slurs/epithets | {} | literal | actual evidence text | — | {k} | sealed | G9 |
| infidelity_place | (named bar/venue — huckleberry junction) | {huck's,hucks} | literal | location_corroboration | 0 | {f,k} | sealed | G4,G9 |
| vulnerability_trigger | (deceased-relative ref — mother's suicide) | {deceased relative} | literal | targeted wound + deceased-relative ref | 9 | {f,g,k} | sealed | G7 |
| vulnerability_trigger | (derogatory child epithet — "little shit") | {} | literal | derogatory_child_reference | 7 | {f,k} | sealed | G4 |

### 5b. RESTRICTED vulnerabilities / named-target epithets
| lexicon_type | term | variants | match_type | relevance_signal | sev | mcl | tier | sources |
|---|---|---|---|---|---|---|---|---|
| vulnerability_trigger | (2009 suicide attempt) | {} | literal | targeted wound (Factor K/F) | 9 | {f,g,k} | restricted | G7 |
| vulnerability_trigger | (named-child condition — "his autism") | {autistic,sensory} | literal | child_health_vulnerability | — | {a,c} | restricted | G8 |
| vulnerability_trigger | (named-target homophobic epithets at user) | {faggot,fagget,"sick fagot"} | literal | identity_based_slur_at_party | — | {f,k} | restricted | G8 |
| case_substance_detail | (case-specific drink brand — fireball) | {} | literal | intoxication/lifestyle marker | — | {k} | restricted | G9 |
| weaponized_substance_phrasing | "this is the drugs talking","are you on something","you can't control yourself" | {} | literal | substance-as-weapon (tied to real allegation) | — | {g,k} | restricted | G9 |
| medication_control | adderall/"addy"/"i'm holding onto them for you" | {} | literal | medication-as-control | — | {g} | restricted | G9 |

### 5c. RESTRICTED single-token derogatory epithets / slurs (routed out of detection_pattern per HARD rule)
| lexicon_type | term | category origin | sev | mcl | tier | sources |
|---|---|---|---|---|---|---|
| sexual_epithet | slut | sexual_shaming | 10 | {b,f,k} | restricted | G2,G6 |
| sexual_epithet | whore | sexual_shaming | 10 | {b,f,k} | restricted | G2,G6 |
| sexual_epithet | pervert | sexual_shaming | 9 | {b,f,k} | restricted | G2,G6 |
| sexual_epithet | freak | sexual_shaming | 9 | {b,f,k} | restricted | G2,G6 |
| sexual_epithet | disgusting | sexual_shaming | 8 | {b,f,k} | restricted | G2,G6 |
| sexual_epithet | sick | sexual_shaming | 8 | {b,f,k} | restricted | G2,G6 |
| sexual_epithet | nasty | sexual_shaming | 8 | {b,f,k} | restricted | G2,G6 |
| sexual_epithet | used | sexual_shaming | 9 | {b,f,k} | restricted | G2,G6 |
| sexual_epithet | cheap | sexual_shaming | 8 | {b,f,k} | restricted | G2,G6 |
| drug_slur | crackhead | substance_weaponized | 9 | {f,g,k} | restricted | G2,G6 |
| drug_slur | tweaker | substance_weaponized | 9 | {f,g,k} | restricted | G2,G6 |
| drug_slur | junkie | substance_weaponized | 9 | {f,g,k} | restricted | G2,G6 |
| drug_slur | addict | substance_weaponized | 8 | {f,g,k} | restricted | G2,G6 |
| drug_slur | user | substance_weaponized | 7 | {f,g,k} | restricted | G2,G6 |

### 5d. RESTRICTED generic kinship references (is_case_specific=false)
| lexicon_type | term | sev | mcl | tier | sources |
|---|---|---|---|---|---|
| child_reference | my daughter / our daughter / your daughter / the baby / the kid / the child / our child / my kid / my child | 8 | {a} | restricted | G4,G6 |

### 5e. RESTRICTED HurtLex hate-speech category taxonomy (16 codes; runtime lemmas from external AGPL `hurtlex_EN.tsv`)
| lexicon_type | term (code → label) | tier | sources |
|---|---|---|---|
| hurtlex_category | ps → ethnic_slurs | restricted | G1 |
| hurtlex_category | rci → locations | restricted | G1 |
| hurtlex_category | pa → professions | restricted | G1 |
| hurtlex_category | ddf → physical_disabilities | restricted | G1 |
| hurtlex_category | dmc → cognitive_disabilities | restricted | G1 |
| hurtlex_category | is → social_economic | restricted | G1 |
| hurtlex_category | or → plants | restricted | G1 |
| hurtlex_category | an → animals | restricted | G1 |
| hurtlex_category | asm → male_sexuality | restricted | G1 |
| hurtlex_category | asf → female_sexuality | restricted | G1 |
| hurtlex_category | pr → prostitution | restricted | G1 |
| hurtlex_category | om → moral_behavioral | restricted | G1 |
| hurtlex_category | qas → generic_insults | restricted | G1 |
| hurtlex_category | cds → derogatory_words | restricted | G1 |
| hurtlex_category | re → criminal | restricted | G1 |
| hurtlex_category | svp → social_political | restricted | G1 |

### 5f. PUBLIC sentiment-cue lexicons (G1 SpaCy; is_case_specific=false, tier=public)
| lexicon_type | terms | tier | sources |
|---|---|---|---|
| sentiment_cue_negative | hate, angry, fuck, shit, kill, hurt, destroy | public | G1 |
| sentiment_cue_positive | love, miss, please, sorry, want, need | public | G1 |

**pattern_lexicon count = 71** (12 sealed identifiers/places/trauma + 6 restricted vulnerabilities/named-epithets + 14 restricted single-token epithets + 1 kinship-template row [9 terms] + 16 HurtLex codes + 2 public sentiment rows [13 terms] + 20 named-individual/quote candidate rows folded above). Counting discrete lexicon rows as listed = 51 rows; expanding the multi-term kinship + sentiment rows to individual terms = 71 distinct terms.

---

## 6. FINAL COUNTS
- **behavior_category:** 155
- **detection_pattern:** 396
- **pattern_lexicon:** 51 rows / 71 distinct terms
- **behavior_category_mcl:** 205

## 7. Court-safety notes
- Every negative `detection_pattern` row = `bias_caution=true`, HYPOTHESIS not finding; `authored_perspective='single_party_complainant'` — MUST be run symmetrically on all parties (reactive-abuse / primary-aggressor caveat from G9 *Kubicki v. Sharpe*, 306 Mich App 525).
- All child names → sealed `child_identifier`; regexes carry `<CHILD_NAME>` placeholder (G1/G4/G5 genericization). Party/third-party/surname/deceased-relative/verbatim-quote → sealed. Named-target epithets, named-child conditions, case substance/medication/place details → restricted/sealed.
- Single-token sexual/drug/homophobic epithets and HurtLex lemmas routed OUT of `detection_pattern` into restricted `pattern_lexicon`; only multi-word abusive PHRASES and genericized slur DETECTORS remain in `detection_pattern`.
- Generic kinship templates ("my daughter"/"the kid") seeded as restricted `child_reference` (is_case_specific=false) in addition to low-severity DP markers.
- Severity-0 linguistic/neutral markers (certainty/hedge/substance-mention/manic-depressive/I-talk/you-talk) are NOT misconduct findings (Guardrail #7) — relevance/health/statistical signals only; `emotional_dysregulation` carries HIGH bias_caution.
- J↔K remapped to canonical statute (G3 `.ttl` label-swap bug + G5 idiosyncratic letters corrected); `is_critical=true` on j & k.
- Folding recommendation: adopt G9 `coercive_control_guideline.md` labeling-discipline thresholds ("when in doubt, don't label") as the canonical `bias_caution` justification text in the reconciliation addendum.
