-- =====================================================================================
-- 0006_behavior_seed.sql — behavioral detection-config DATA seed (IDEMPOTENT, re-runnable)
-- Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30
-- =====================================================================================
--  TARGET: live `analysis` schema (RECONCILED_SCHEMA.sql STEP 12 / migration 0005):
--    analysis.detection_pattern_set, .behavior_category, .detection_pattern,
--    .pattern_lexicon, .behavior_category_mcl.
--  SOURCE: behavior-seed/MERGED_behavior_seed.md — strictly-additive UNION of 9 extraction
--    fragments (G1 analyzer-app, G2 seed-patterns.ts, G3 dial TTL, G4 E4, G5 agno-alpha,
--    G6 dataset[derived], G7 zep_salem v3, G8 conversation logs, G9 onedrive clusters).
--
--  !!! COURT-SAFETY BANNER — READ BEFORE RELYING ON ANY ROW !!!
--    * Every analysis.detection_pattern row is a HYPOTHESIS, not a finding. bias_caution=true
--      on all of them. authored_perspective='single_party_complainant' — these detectors MUST
--      be run SYMMETRICALLY on all parties before use (reactive-abuse / primary-aggressor
--      caveat, Kubicki v. Sharpe, 306 Mich App 525). "When in doubt, don't label."
--    * NO child name, party name, surname, third-party name, deceased-relative reference, or
--      verbatim case quote appears as plaintext anywhere in this file. All such identifiers are
--      routed to analysis.pattern_lexicon with sensitivity_tier='sealed' and seeded as REDACTED
--      PLACEHOLDERS ('[REDACTED:...]') — real values are loaded out-of-band from a secure store,
--      NEVER committed to git. Generic kinship templates / generic slurs / vulnerability classes
--      go to pattern_lexicon at sensitivity_tier='restricted'.
--    * Severity-0 linguistic/neutral markers (certainty/hedge/substance-mention/manic-depressive)
--      are NOT misconduct — relevance/health/statistical signals only.
--
--  RE-RUNNABLE: all writes are INSERT ... ON CONFLICT DO UPDATE. NO destructive statements.
--    Strict FK ordering: set -> categories -> patterns -> lexicon -> mcl.
--    Safe to run inside a single transaction (no enum DDL here; enums pre-exist from 0005).
-- =====================================================================================

SET search_path = analysis, ai, public;  -- ai: custom enum types (category_polarity, mcl_factor, …) live in the ai schema (0004 applied under search_path "$user"=ai)

-- =====================================================================================
-- BLOCK 1 — detection_pattern_set  (ONE active merged set)
-- =====================================================================================
INSERT INTO analysis.detection_pattern_set (name, version, source, source_artifact, description, is_active, authored_perspective)
VALUES (
  'casebible-behavioral', '1.0.0', 'merged G1-G9 behavioral-pattern fragments',
  'G1 analyzer-app app.py(+app_local.py); G2 migration-plan-v8/server/scripts/seed-patterns.ts; '
  'G3 dial behavioral_patterns.ttl+positive_behaviors.ttl+mcl_722_23.ttl; '
  'G4 E4 COMPLETE_SCHEMA_PARSER_INVENTORY.md#part-4+E4_behavioral_ontology.md; '
  'G5 agno-alpha {classifier,multi-pass-classifier,nlp-classifier,priority-screener}.ts; '
  'G7 zep_salem_ontology_v3_final.py; G8 conversation logs; '
  'G9 onedrive coercive_control_pipeline/labels_ontology.json '
  '(G6 behavioral_patterns_dataset folded in as derived/SFT corpus)',
  'Additive superset of nine fragmented behavioral-detection iterations; patterns are hypotheses requiring human review.',
  true,
  'user-side compiled from fragmented iterations; patterns are hypotheses requiring human review'
)
ON CONFLICT (name, version) DO UPDATE SET
  source              = EXCLUDED.source,
  source_artifact     = EXCLUDED.source_artifact,
  description         = EXCLUDED.description,
  is_active           = EXCLUDED.is_active,
  authored_perspective= EXCLUDED.authored_perspective;

-- =====================================================================================
-- BLOCK 2 — behavior_category  (153 distinct category_id)
-- =====================================================================================
INSERT INTO analysis.behavior_category
  (category_id, label, polarity, default_severity, mcl_factors, aliases, is_case_specific, source)
SELECT v.category_id, v.label, v.polarity::category_polarity, v.default_severity,
       v.mcl_factors::mcl_factor[], v.aliases::citext[], v.is_case_specific, v.source
FROM (VALUES
 ('threats','Threats / Intimidation','negative',10,'{j,k}','{threat,intimidation,explicit_threat,implicit_threat}',false,'G1,G5'),
 ('child_weaponization','Child Weaponization','negative',9,'{j,k}','{using_child}',false,'G1'),
 ('monitoring_stalking','Monitoring / Stalking','negative',8,'{g,k}','{stalking,surveillance,monitoring}',false,'G1'),
 ('homophobic_slurs','Homophobic Slurs','negative',7,'{f,k}','{anti_gay}',false,'G1'),
 ('isolation_tactics','Isolation Tactics','negative',7,'{j,k}','{isolating}',false,'G1'),
 ('gaslighting','Gaslighting','negative',9,'{a,f,g,k}','{reality_distortion}',false,'G1,G2,G3,G4,G6'),
 ('double_bind','Double Bind','negative',7,'{j,k}','{contradictory_demand}',false,'G1'),
 ('character_attacks','Character Attacks','negative',6,'{f,k}','{name_calling}',false,'G1'),
 ('financial_control','Financial Control / Economic Abuse','negative',7,'{c,k,l}','{economic_abuse,financial_abuse}',false,'G1,G5,G9'),
 ('triangulation','Triangulation','negative',7,'{f,j,k,l}','{third_party_manipulation}',false,'G1,G5,G7'),
 ('communication_control','Communication Control','negative',5,'{j,k}','{contact_blocking}',false,'G1'),
 ('substance_shaming','Substance Shaming','negative',5,'{f,g}','{drug_shaming}',false,'G1'),
 ('mental_health_stigma','Mental Health Stigma','negative',5,'{f,g}','{crazy_making}',false,'G1'),
 ('love_bombing','Love Bombing','negative',6,'{a,f,j,k,l}','{lovebomb,intermittent_reinforcement}',false,'G1,G2,G3,G4,G6'),
 ('blame_shifting','Blame Shifting','negative',9,'{f,j,k}','{}',false,'G2,G3,G4,G6'),
 ('minimizing','Minimizing','negative',7,'{f,j,k}','{minimization,dismissiveness}',false,'G2,G3,G4,G6'),
 ('circular','Circular Arguments','negative',6,'{l}','{word_salad}',false,'G2,G6'),
 ('darvo_deny','DARVO - Deny','negative',9,'{f}','{}',false,'G2,G6'),
 ('darvo_attack','DARVO - Attack','negative',9,'{f,k}','{}',false,'G2'),
 ('darvo_reverse','DARVO - Reverse Victim/Offender','negative',10,'{f,k}','{}',false,'G2,G6'),
 ('overelaboration','Overelaboration / Over-justification','linguistic_marker',8,'{f,l}','{}',false,'G1,G2,G3,G4,G6'),
 ('excessive_gratitude','Excessive Gratitude','negative',7,'{f,l}','{}',false,'G2,G6'),
 ('debt_reminders','Debt Reminders','negative',8,'{f}','{}',false,'G2,G6'),
 ('savior_complex','Savior Complex','negative',9,'{f,k}','{rescuing}',false,'G2,G6'),
 ('substance_alcohol','Substance - Alcohol (mentions)','neutral',0,'{g}','{}',false,'G2,G6'),
 ('substance_weaponized','Substance - Weaponized','negative',9,'{f,g,k}','{substance_weaponization}',false,'G2,G6'),
 ('adderall_control','Adderall / Medication Control','negative',8,'{c,g,k}','{medication_control}',true,'G2,G6'),
 ('infidelity','Infidelity','negative',9,'{f}','{}',false,'G2,G6'),
 ('financial_weaponized','Financial - Weaponized','negative',8,'{c,f}','{financial_abuse}',false,'G2,G6'),
 ('sexual_shaming','Sexual Shaming','negative',10,'{b,f,k}','{}',false,'G2,G4,G6'),
 ('parental_alienation','Parental Alienation','negative',10,'{a,i,j,k}','{alienation,gatekeeping}',false,'G2,G3,G4,G6,G7'),
 ('medical_abuse','Medical Abuse','negative',10,'{c,f,g,j,k}','{medical}',false,'G2,G4,G6'),
 ('reproductive_coercion','Reproductive Coercion','negative',10,'{f,j,k,l}','{}',false,'G2,G4,G6'),
 ('victim_deference','Power Asymmetry - Victim Deference','linguistic_marker',7,'{k}','{}',false,'G2,G6'),
 ('abuser_directives','Power Asymmetry - Abuser Directives','negative',8,'{k}','{}',false,'G2,G6'),
 ('certainty_absolutes','Statistical - Certainty/Absolutes','linguistic_marker',0,'{l}','{}',false,'G2,G4,G6'),
 ('hedge_words','Statistical - Hedge Words','linguistic_marker',0,'{l}','{}',false,'G2,G4,G6'),
 ('darvo','DARVO (Deny-Attack-Reverse)','negative',10,'{f,j,k}','{darvo_deny,darvo_attack,darvo_reverse}',false,'G3,G4,G7'),
 ('coercive_control','Coercive Control','negative',10,'{c,j,k}','{}',false,'G3,G4'),
 ('affirmations','Affirmation / Praise + Validation','positive',4,'{a,f,l}','{affirmation,positive_statements,explicit_praise,emotional_validation}',false,'G3,G4,G5'),
 ('expectation_setting','Expectation Setting / Future-Faking','positive',4,'{a,c}','{future_promise,financial_assurance}',false,'G3'),
 ('cooperation','Cooperative Behavior','positive',1,'{a,b,d,j}','{information_sharing,flexibility}',false,'G3,G4'),
 ('dependency_cultivation','Dependency Cultivation (savior)','positive',5,'{f}','{savior_complex,rescuing}',false,'G3,G4'),
 ('stonewalling','Silent treatment / refusal to communicate','negative',7,'{f,k}','{silent_treatment,withholding}',false,'G4'),
 ('financial_abuse','Economic abuse / weaponized money','negative',8,'{c,j}','{financial_control,financial_weaponized}',false,'G4'),
 ('substance_weaponization','Substance use as weapon/label','negative',9,'{b,f,g,k}','{substance_weaponized}',false,'G4'),
 ('reactive_abuse','Provoked reaction reframed as aggression','negative',8,'{f,j,k}','{}',false,'G4,G8'),
 ('character_assassination','Degradation / slurs / epithets','negative',9,'{b,f,k}','{character_attack,character_attacks}',false,'G4'),
 ('isolation','Cutting off support systems','negative',9,'{c,j,k}','{isolation_tactics,cutting_off_support}',false,'G4,G5,G7,G9'),
 ('hoovering','Pulling victim back after discard','negative',6,'{a,f}','{}',false,'G4'),
 ('parenting_time','Visitation / handoff interference','negative',9,'{j,k}','{}',false,'G4'),
 ('gatekeeping','Blocking contact/information access','negative',8,'{j}','{}',false,'G4'),
 ('special_needs','Child special-needs handling','negative',8,'{a,c,l}','{}',false,'G4'),
 ('threats_intimidation','Threats of harm/retaliation','negative',10,'{j,k}','{threats}',false,'G4,G9'),
 ('future_faking','Grandiose unfulfilled promises','positive',3,'{l}','{expectation_setting}',false,'G4'),
 ('apologies','Apology / remorse','positive',2,'{l}','{}',false,'G4'),
 ('gift_giving','Material generosity','positive',2,'{c,l}','{gestures_of_affection}',false,'G4,G5'),
 ('power_asymmetry','Victim-deference vs abuser-directive','neutral',0,'{j,l}','{}',false,'G4'),
 ('scheduling','Custody schedule / visitation logistics','neutral',0,'{a,b,d}','{}',false,'G4'),
 ('child_wellbeing','Child health/education/emotional mentions','neutral',0,'{a,b,e,g}','{}',false,'G4'),
 ('manipulation','Manipulation (umbrella)','negative',7,'{l}','{controlling_through_deception}',false,'G5'),
 ('intimidation','Intimidation / Threats','negative',8,'{f,k}','{threats_aggression}',false,'G5,G7'),
 ('denial','Denial / refusing to acknowledge','negative',7,'{f,l}','{refusing_to_acknowledge}',false,'G5,G7'),
 ('stalking','Stalking / surveillance','negative',8,'{g,k}','{monitoring,surveillance}',false,'G5'),
 ('coordinated_abuse','Multi-party targeting','negative',8,'{j,k,l}','{multi_party_targeting}',false,'G5'),
 ('smear_campaign','Smear campaign / rumor spreading','negative',8,'{f,j,k}','{reputational_attack,defamation}',false,'G5,G7'),
 ('silent_treatment','Withholding communication as punishment','negative',6,'{j,l}','{stonewalling,withholding_communication}',false,'G5'),
 ('reassurances','Reassurances (trust assertion)','positive',0,'{l}','{trust_assertion}',false,'G5'),
 ('promises','Promises / commitment to change','positive',0,'{l}','{commitment_to_change,future_commitment}',false,'G5'),
 ('declarations_of_loyalty','Declarations of loyalty','positive',0,'{l}','{loyalty_declaration}',false,'G5'),
 ('expressions_of_care','Expressions of care','positive',0,'{l}','{concern_for_wellbeing}',false,'G5'),
 ('future_planning','Future planning','positive',0,'{l}','{long_term_plans}',false,'G5'),
 ('compliments','Compliments / praise','positive',0,'{l}','{praise}',false,'G5'),
 ('negation_markers','Negation markers','linguistic_marker',0,'{}','{negation}',false,'G5'),
 ('intensity_modifiers','Intensity modifiers','linguistic_marker',0,'{}','{intensifiers}',false,'G5'),
 ('communication_blocking','Call blocking / refusing to answer','negative',9,'{j}','{}',false,'G5'),
 ('visit_blocking','Visit denial / will not bring child','negative',9,'{j}','{}',false,'G5'),
 ('parenting_time_denial','Schedule interference','negative',8,'{j}','{}',false,'G5'),
 ('custody_interference','Hiding/keeping child; RO/police weaponization','negative',9,'{j,k}','{}',false,'G5'),
 ('child_reference','Generic child mention','neutral',5,'{i}','{}',false,'G5'),
 ('economic_sabotage','Economic sabotage / financial coercion','negative',7,'{c,k}','{}',false,'G7'),
 ('suicide_baiting','Suicide baiting (trauma weaponization)','negative',10,'{f,g,k}','{}',false,'G7'),
 ('projection','Accusing target of accusers own conduct','negative',7,'{f,k}','{blame_shifting}',false,'G7,G8'),
 ('minimization','Minimization','negative',6,'{f}','{minimizing}',false,'G7'),
 ('fabrication','Fabrication / fabricated narrative','negative',9,'{f,k}','{}',false,'G7'),
 ('misdirection','Misdirection / distraction','negative',6,'{f}','{}',false,'G7'),
 ('inconsistent_account','Inconsistent / contradictory account','neutral',5,'{f}','{}',false,'G7'),
 ('manufactured_crisis','Manufactured / staged crisis','negative',7,'{f,k}','{}',false,'G7'),
 ('child_exposure','Exposure of child to harm','negative',8,'{f,j,k}','{}',false,'G7'),
 ('trauma_exploitation','Trauma / vulnerability exploitation','negative',9,'{f,k}','{}',false,'G7'),
 ('substance_endangerment','Substance use / endangerment','negative',8,'{c,g,k}','{}',false,'G7'),
 ('medical_neglect','Medical neglect','negative',8,'{c,g}','{}',false,'G7'),
 ('npd_grandiosity','NPD grandiosity','negative',7,'{f}','{}',false,'G6'),
 ('npd_entitlement','NPD entitlement','negative',7,'{f}','{}',false,'G6'),
 ('npd_empathy_deficit','NPD empathy deficit','negative',8,'{f}','{}',false,'G6'),
 ('bpd_abandonment','BPD abandonment projection','negative',7,'{a,f}','{}',false,'G6'),
 ('bpd_splitting','BPD splitting','negative',7,'{f}','{}',false,'G6'),
 ('bpd_self_harm_threat','BPD self-harm/suicide threat','negative',10,'{g,k}','{}',false,'G6'),
 ('aspd_callousness','ASPD callousness','negative',7,'{f,k}','{}',false,'G6'),
 ('aspd_no_remorse','ASPD no remorse','negative',8,'{f,k}','{}',false,'G6'),
 ('custody_court_manipulation','Court/judge-shopping/delay manipulation','negative',9,'{f,j}','{}',false,'G6'),
 ('custody_gatekeeping','Blocking parental info/contact','negative',8,'{j}','{}',false,'G6'),
 ('custody_schedule_interference','Manufactured emergencies / scheduling over time','negative',7,'{j}','{}',false,'G6'),
 ('custody_child_messenger','Child as messenger/spy','negative',8,'{i,j}','{}',false,'G6'),
 ('custody_parental_replacement','New partner as replacement parent','negative',8,'{a,j}','{}',false,'G6'),
 ('feigning_incompetence','Weaponized / strategic incompetence','negative',5,'{c,j}','{playing_dumb}',false,'G8'),
 ('defensiveness_evasion','Extreme defensiveness / accountability evasion','negative',6,'{f}','{}',false,'G8'),
 ('social_media_deception','Platform-denial / contradiction deception','negative',6,'{f}','{}',false,'G8'),
 ('last_minute_changes','Manufactured instability / schedule sabotage','negative',6,'{j}','{}',false,'G8'),
 ('emotional_dysregulation','Manic/depressive linguistic markers','neutral',0,'{g}','{}',false,'G8'),
 ('i_talk_marker','First-person-singular over-use (LIWC)','linguistic_marker',0,'{}','{}',false,'G8'),
 ('you_talk_marker','Second-person accusatory over-use (LIWC)','linguistic_marker',0,'{}','{}',false,'G8'),
 ('guilt_tripping','Guilt / FOG leverage','negative',6,'{f,k}','{}',false,'G8'),
 ('feigned_concern','Faux-worry used to degrade/position','negative',6,'{f,j}','{}',false,'G8'),
 ('flying_monkeys','Proxy abuse via recruited third parties','negative',7,'{j,k}','{}',false,'G8'),
 ('devaluation','Devalue phase (criticism/contempt/withdrawal)','negative',7,'{a,f}','{}',false,'G8'),
 ('discard','Discard phase (abandonment / new supply)','negative',7,'{a,j}','{}',false,'G8'),
 ('child_endangerment','Substance-use + child-present co-occurrence','negative',9,'{c,g,k}','{}',false,'G8'),
 ('autism_weaponization','Weaponizing childs diagnosis vs other parent','negative',8,'{a,c,j}','{}',false,'G8'),
 ('block_unblock_cycle','Intermittent contact control (punish/reward)','negative',7,'{j,k}','{}',false,'G8'),
 ('recovery_phase','Manipulative calm after escalation','neutral',3,'{l}','{}',false,'G8'),
 ('word_salad','Deliberate confusion / obscure language','negative',5,'{l}','{obscure_language}',false,'G8'),
 ('dismissiveness','Minimization / shutdown / invalidation cluster','negative',5,'{f}','{minimizing}',false,'G8'),
 ('selective_amnesia','Convenient forgetting / memory denial','negative',6,'{f}','{forgetting_feigned_amnesia}',false,'G8'),
 ('monitoring_surveillance','Monitoring & surveillance','negative',6,'{k}','{monitoring,surveillance}',false,'G9'),
 ('gaslighting_reality_distortion','Gaslighting & reality distortion (cluster)','negative',7,'{k}','{}',false,'G9'),
 ('verbal_degradation','Verbal degradation & devaluation','negative',6,'{b,k}','{empathy_withholding}',false,'G9'),
 ('autonomy_deprivation','Autonomy deprivation & daily control','negative',5,'{c,k}','{cumulative_micro_control}',false,'G9'),
 ('identity_erosion','Identity erosion & trauma bonding','negative',7,'{k}','{}',false,'G9'),
 ('sexual_reproductive_coercion','Sexual & reproductive coercion','negative',8,'{k}','{}',false,'G9'),
 ('jealousy_possessiveness','Jealousy & possessiveness','negative',5,'{k}','{}',false,'G9'),
 ('narcissistic_entitlement','Narcissistic entitlement & rage','negative',7,'{k}','{victimhood_posturing,manufactured_conflict}',false,'G9'),
 ('legal_system_abuse','Legal-system & institutional abuse','negative',7,'{j,k}','{litigation_abuse,children_as_control_tools}',false,'G9'),
 ('entrapment_fear','Entrapment & pervasive fear','negative',8,'{k}','{post_separation_control}',false,'G9'),
 ('countering','Gaslighting subtype: countering (memory attack)','negative',7,'{k}','{}',false,'G9'),
 ('diverting','Gaslighting subtype: diverting/whataboutism','negative',7,'{f,k}','{}',false,'G9'),
 ('stereotyping','Gaslighting subtype: stereotyping','negative',6,'{k}','{}',false,'G9'),
 ('forgetting_feigned_amnesia','Gaslighting subtype: feigned amnesia','negative',6,'{f,k}','{selective_amnesia}',false,'G9'),
 ('questioning_sanity','Gaslighting subtype: questioning sanity','negative',8,'{g,k}','{crazy_label}',false,'G9'),
 ('joke_defense','Gaslighting subtype: joke defense','negative',6,'{k}','{}',false,'G9'),
 ('scapegoating','Gaslighting subtype: scapegoating','negative',7,'{f,k}','{}',false,'G9'),
 ('feeling_police','Gaslighting subtype: feeling-policing','negative',5,'{k}','{}',false,'G9'),
 ('subtle_shift','Gaslighting subtype: subtle account shift','negative',6,'{f,k}','{}',false,'G9'),
 ('weaponizing_allies_triangulation','Gaslighting subtype: ally-weaponizing','negative',6,'{j,k}','{triangulation}',false,'G9'),
 ('provocation_defense','Gaslighting subtype: provocation defense','negative',7,'{f,k}','{reactive_abuse}',false,'G9'),
 ('victim_playing','MER style: victim playing','negative',6,'{f}','{}',false,'G9'),
 ('exaggeration_dramatization','MER style: exaggeration/dramatization','negative',5,'{f}','{}',false,'G9'),
 ('impatience','MER style: impatience','negative',4,'{l}','{}',false,'G9'),
 ('ignoring','MER style: ignoring','negative',5,'{j}','{}',false,'G9'),
 ('diminishing','MER style: diminishing','negative',5,'{f}','{minimizing}',false,'G9'),
 ('invalidation','MER style: invalidation','negative',5,'{f}','{}',false,'G9'),
 ('changing_the_topic','MER style: changing the topic','negative',5,'{f}','{diverting}',false,'G9'),
 ('aggression','MER style: aggression','negative',7,'{k}','{}',false,'G9')
) AS v(category_id, label, polarity, default_severity, mcl_factors, aliases, is_case_specific, source)
ON CONFLICT (category_id) DO UPDATE SET
  label            = EXCLUDED.label,
  polarity         = EXCLUDED.polarity,
  default_severity = EXCLUDED.default_severity,
  mcl_factors      = EXCLUDED.mcl_factors,
  aliases          = EXCLUDED.aliases,
  is_case_specific = EXCLUDED.is_case_specific,
  source           = EXCLUDED.source;

-- =====================================================================================
-- BLOCK 3 — detection_pattern  (generic phrases + genericized regex; HYPOTHESES, bias_caution=true)
--   pattern_set_id resolved via subselect against the 'casebible-behavioral' v1.0.0 set.
--   score = GREATEST(severity,1) (G2 latent-weight rule). Split into sub-blocks so no two
--   rows in one statement share (category_id,match_type,pattern); cross-block collisions are
--   resolved by ON CONFLICT DO UPDATE.
-- =====================================================================================

-- 3a — gaslighting
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('gaslighting','literal','i never said that',8,'G2,G6'),
 ('gaslighting','literal','you imagined',8,'G2,G6'),
 ('gaslighting','literal','you''re paranoid',7,'G2'),
 ('gaslighting','literal','that never happened',9,'G2,G6'),
 ('gaslighting','literal','no one will believe',9,'G2,G6'),
 ('gaslighting','literal','you''re crazy',9,'G2'),
 ('gaslighting','literal','you''re just high',8,'G2'),
 ('gaslighting','literal','just kidding',6,'G2,G6'),
 ('gaslighting','literal','you''re overreacting',7,'G2'),
 ('gaslighting','literal','this is the drugs talking',8,'G2,G6'),
 ('gaslighting','literal','you''re twisting my words',7,'G8'),
 ('gaslighting','literal','you have issues',6,'G8'),
 ('gaslighting','literal','that''s not how it happened',7,'G8'),
 ('gaslighting','literal','you''re misremembering',8,'G8'),
 ('gaslighting','literal','you''re confused',7,'G8'),
 ('gaslighting','regex','that never happened',7,'G1'),
 ('gaslighting','regex','you''?re (crazy|imagining|making (it|this|that) up)',7,'G1'),
 ('gaslighting','regex','i never said that',7,'G1'),
 ('gaslighting','regex','you''?re (being|too) (dramatic|sensitive|emotional)',7,'G1'),
 ('gaslighting','regex','you always (exaggerate|overreact|blow things out of proportion)',7,'G1'),
 ('gaslighting','regex','that''?s not (what|how) (it|that) happened',7,'G1'),
 ('gaslighting','regex','you''?re (twisting|changing|distorting) (my words|what i said|the story)',7,'G1'),
 ('gaslighting','regex','you know that''?s not true',7,'G1'),
 ('gaslighting','regex','(?i)(i never|would never|did not|didn''t|never happened)',8,'G3'),
 ('gaslighting','regex','(?i)(imagined|imagining|made up|in your head|crazy|insane|delusional)',9,'G3'),
 ('gaslighting','regex','(?i)(no one|nobody|will believe|won''t believe|no one will)',10,'G3')
) AS v(category_id, match_type, pattern, severity, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3b — blame_shifting, minimizing, circular
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('blame_shifting','literal','this is your fault',7,'G2,G6'),
 ('blame_shifting','literal','you made me',8,'G2,G6'),
 ('blame_shifting','literal','because of you',7,'G2,G6'),
 ('blame_shifting','literal','you started this',6,'G2,G6'),
 ('blame_shifting','literal','you always do this',7,'G2,G6'),
 ('blame_shifting','literal','if you hadn''t',7,'G2'),
 ('blame_shifting','literal','look what you made me do',9,'G2,G6'),
 ('blame_shifting','literal','you''re the one who started it',7,'G9'),
 ('blame_shifting','literal','i only acted that way because you pushed me to it',7,'G9'),
 ('blame_shifting','regex','(?i)(your fault|you made me|because of you|you''re the reason)',8,'G3'),
 ('blame_shifting','regex','(?i)(look what you|see what you|this is your|you caused)',7,'G3'),
 ('minimizing','literal','not a big deal',6,'G2,G6'),
 ('minimizing','literal','you''re too sensitive',7,'G2'),
 ('minimizing','literal','calm down',5,'G2,G6'),
 ('minimizing','literal','you''re being dramatic',6,'G2'),
 ('minimizing','literal','get over it',7,'G2,G6'),
 ('minimizing','literal','stop making a scene',6,'G2,G6'),
 ('minimizing','literal','it was just a joke',6,'G2,G6'),
 ('minimizing','literal','relax',5,'G2,G6'),
 ('minimizing','literal','is that really something to get upset about',5,'G9'),
 ('minimizing','literal','you''re making a big deal out of nothing',5,'G9'),
 ('minimizing','regex','(?i)(not a big deal|no big deal|not big deal|making a big|overreacting)',6,'G3'),
 ('minimizing','regex','(?i)(calm down|you need to calm|just calm|relax|settle down)',5,'G3'),
 ('circular','literal','what even is the point',5,'G2'),
 ('circular','literal','that''s not the point',6,'G2'),
 ('circular','literal','you keep changing',6,'G2,G6'),
 ('circular','literal','you know what i mean',5,'G2,G6'),
 ('circular','literal','anyway',5,'G2,G6'),
 ('circular','literal','whatever',5,'G2,G6'),
 ('circular','literal','we''re not in high school',6,'G2')
) AS v(category_id, match_type, pattern, severity, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3c — darvo_deny, darvo_attack, darvo_reverse, darvo (regex)
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('darvo_deny','literal','i never',8,'G2,G6'),
 ('darvo_deny','literal','i didn''t',8,'G2'),
 ('darvo_deny','literal','that never happened',9,'G2,G6'),
 ('darvo_deny','literal','that''s not true',8,'G2'),
 ('darvo_deny','literal','you''re making that up',9,'G2'),
 ('darvo_deny','literal','i would never',7,'G2,G6'),
 ('darvo_deny','literal','that''s a lie',9,'G2'),
 ('darvo_attack','literal','you''re crazy',9,'G2'),
 ('darvo_attack','literal','you''re lying',9,'G2'),
 ('darvo_attack','literal','you''re the abusive one',10,'G2'),
 ('darvo_attack','literal','you''re manipulating',9,'G2'),
 ('darvo_attack','literal','you''re gaslighting me',10,'G2'),
 ('darvo_attack','literal','you''re toxic',9,'G2'),
 ('darvo_attack','literal','you''re the problem',9,'G2'),
 ('darvo_attack','literal','you''re unstable',9,'G2'),
 ('darvo_attack','literal','you''re delusional',9,'G2'),
 ('darvo_reverse','literal','i''m the victim here',10,'G2'),
 ('darvo_reverse','literal','you''re attacking me',10,'G2'),
 ('darvo_reverse','literal','you''re abusing me',10,'G2'),
 ('darvo_reverse','literal','i''m the one being hurt',10,'G2'),
 ('darvo_reverse','literal','you''re hurting me',10,'G2'),
 ('darvo_reverse','literal','i''m scared of you',10,'G2'),
 ('darvo_reverse','literal','you''re the aggressor',10,'G2'),
 ('darvo_reverse','literal','i need protection from you',10,'G2,G6'),
 ('darvo','regex','(?i)(i never|would never|that never|didn''t happen|not true)',7,'G3'),
 ('darvo','regex','(?i)(protect.*from you|you''re the|victim|abuser|i need)',10,'G3')
) AS v(category_id, match_type, pattern, severity, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3d — overelaboration, love_bombing
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('overelaboration','literal','i''m at',7,'G2'),
 ('overelaboration','literal','i''m still at',7,'G2'),
 ('overelaboration','literal','i''m heading to',7,'G2'),
 ('overelaboration','literal','i''ll be at',7,'G2'),
 ('overelaboration','literal','i''m on my way to',7,'G2'),
 ('overelaboration','literal','i just left',7,'G2,G6'),
 ('overelaboration','literal','i just arrived at',7,'G2,G6'),
 ('overelaboration','literal','i left at',7,'G2,G6'),
 ('overelaboration','literal','i''ll be back by',7,'G2'),
 ('overelaboration','literal','i''ve been here since',7,'G2'),
 ('overelaboration','literal','i''ll be done in',7,'G2'),
 ('overelaboration','literal','i''m doing this because',8,'G2'),
 ('overelaboration','literal','i had to',8,'G2,G6'),
 ('overelaboration','literal','i needed to',8,'G2,G6'),
 ('overelaboration','literal','the reason is',8,'G2,G6'),
 ('overelaboration','literal','i''m just',7,'G2'),
 ('overelaboration','literal','i was just',7,'G2,G6'),
 ('overelaboration','literal','before you ask',8,'G2,G6'),
 ('overelaboration','literal','i know you''re wondering',8,'G2'),
 ('overelaboration','literal','just so you know',7,'G2,G6'),
 ('overelaboration','literal','for the record',7,'G2,G6'),
 ('overelaboration','literal','to be clear',7,'G2,G6'),
 ('overelaboration','literal','let me explain',7,'G6'),
 ('overelaboration','regex','(?i)(just (left|happened|went)|before you|had to)',4,'G3'),
 ('love_bombing','literal','perfect',5,'G2,G6'),
 ('love_bombing','literal','amazing',5,'G2,G6'),
 ('love_bombing','literal','soulmate',6,'G2,G6'),
 ('love_bombing','literal','can''t live without you',7,'G2'),
 ('love_bombing','literal','always',5,'G2,G6'),
 ('love_bombing','literal','forever',5,'G2,G6'),
 ('love_bombing','literal','everything',5,'G2,G6'),
 ('love_bombing','literal','desperate',6,'G2,G6'),
 ('love_bombing','literal','need you',6,'G2,G6'),
 ('love_bombing','literal','you''re the only one who understands me',6,'G2'),
 ('love_bombing','literal','i''ve never felt this way before',6,'G2'),
 ('love_bombing','literal','i want to give you everything',6,'G2,G6'),
 ('love_bombing','regex','i love you so much',4,'G1'),
 ('love_bombing','regex','you''?re (the best|amazing|perfect|everything to me)',4,'G1'),
 ('love_bombing','regex','i can''?t live without you',4,'G1'),
 ('love_bombing','regex','you''?re (the only one|all i (want|need))',4,'G1'),
 ('love_bombing','regex','i miss you (so much|baby)',4,'G1'),
 ('love_bombing','regex','come (over|here).*?(i need you|baby|please)',4,'G1'),
 ('love_bombing','regex','(?i)(perfect|amazing|wonderful|incredible|soulmate)',4,'G3'),
 ('love_bombing','regex','(?i)(forever|always|eternal|never leave|always be)',5,'G3'),
 ('love_bombing','regex','(?i)(give.*everything|all i have|do anything|sacrifice)',6,'G3')
) AS v(category_id, match_type, pattern, severity, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3e — excessive_gratitude, debt_reminders, savior_complex
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('excessive_gratitude','literal','i owe you everything',6,'G2,G6'),
 ('excessive_gratitude','literal','i could never repay you',6,'G2,G6'),
 ('excessive_gratitude','literal','i don''t deserve you',5,'G2'),
 ('excessive_gratitude','literal','you''ve done so much for me',5,'G2'),
 ('excessive_gratitude','literal','i''m so grateful',4,'G2'),
 ('excessive_gratitude','literal','thank you for everything',4,'G2,G6'),
 ('excessive_gratitude','literal','i don''t know what i''d do without you',6,'G2'),
 ('excessive_gratitude','literal','you saved me',7,'G2,G6'),
 ('excessive_gratitude','literal','i owe you my life',7,'G2,G6'),
 ('debt_reminders','literal','remember when i',7,'G2,G6'),
 ('debt_reminders','literal','after all i''ve done',8,'G2'),
 ('debt_reminders','literal','i was there for you when',7,'G2,G6'),
 ('debt_reminders','literal','don''t forget i',7,'G2'),
 ('debt_reminders','literal','i helped you',6,'G2,G6'),
 ('debt_reminders','literal','i gave you',6,'G2,G6'),
 ('savior_complex','literal','i''ll protect you',7,'G2'),
 ('savior_complex','literal','i''ll keep you safe',7,'G2'),
 ('savior_complex','literal','i won''t let anyone hurt you',7,'G2'),
 ('savior_complex','literal','you need me',8,'G2,G6'),
 ('savior_complex','literal','i''ll take care of you',6,'G2'),
 ('savior_complex','literal','i''ll fix this',6,'G2'),
 ('savior_complex','literal','let me handle it',6,'G2,G6'),
 ('savior_complex','literal','i''ll make it better',5,'G2'),
 ('savior_complex','literal','trust me to protect you',7,'G2,G6'),
 ('savior_complex','literal','everyone else will hurt you',9,'G2,G6'),
 ('savior_complex','literal','the world is dangerous',8,'G2,G6'),
 ('savior_complex','literal','you can''t trust anyone but me',9,'G2'),
 ('savior_complex','literal','they''re all out to get you',9,'G2'),
 ('savior_complex','literal','i''m the only one who cares',8,'G2')
) AS v(category_id, match_type, pattern, severity, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3f — substance_alcohol (neutral sev-0 markers), substance_weaponized, adderall_control, infidelity
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('substance_alcohol','literal','drink',0,'G2,G6'),
 ('substance_alcohol','literal','drank',0,'G2,G6'),
 ('substance_alcohol','literal','drunk',0,'G2,G6'),
 ('substance_alcohol','literal','buzzed',0,'G2,G6'),
 ('substance_alcohol','literal','tipsy',0,'G2,G6'),
 ('substance_alcohol','literal','wasted',0,'G2,G6'),
 ('substance_alcohol','literal','bottle',0,'G2,G6'),
 ('substance_alcohol','literal','wine',0,'G2,G6'),
 ('substance_alcohol','literal','beer',0,'G2,G6'),
 ('substance_alcohol','literal','liquor',0,'G2,G6'),
 ('substance_alcohol','literal','vodka',0,'G2,G6'),
 ('substance_alcohol','literal','tequila',0,'G2,G6'),
 ('substance_alcohol','literal','hungover',0,'G2,G6'),
 ('substance_alcohol','literal','fireball',0,'G2,G6'),
 ('substance_weaponized','literal','you''re just high',8,'G2'),
 ('substance_weaponized','literal','are you on something',8,'G2,G6'),
 ('substance_weaponized','literal','this is the drugs talking',8,'G2,G6'),
 ('substance_weaponized','regex','\b(crackhead|crack head|tweaker|junkie|addict)\b',5,'G1'),
 ('substance_weaponized','regex','\bhigh (as fuck|af|again)\b',5,'G1'),
 ('substance_weaponized','regex','on (that shit|drugs|dope)',5,'G1'),
 ('adderall_control','literal','adderall',7,'G2,G6'),
 ('adderall_control','literal','addy',7,'G2,G6'),
 ('adderall_control','literal','pills',6,'G2,G6'),
 ('adderall_control','literal','script',6,'G2,G6'),
 ('adderall_control','literal','share',7,'G2,G6'),
 ('adderall_control','literal','split',7,'G2,G6'),
 ('adderall_control','literal','your turn',8,'G2,G6'),
 ('adderall_control','literal','how many did you take',8,'G2,G6'),
 ('adderall_control','literal','i''m holding onto them for you',9,'G2'),
 ('adderall_control','literal','you can''t control yourself',9,'G2'),
 ('infidelity','literal','cheating',8,'G2,G6'),
 ('infidelity','literal','cheated',8,'G2,G6'),
 ('infidelity','literal','slept with',8,'G2,G6'),
 ('infidelity','literal','affair',9,'G2,G6'),
 ('infidelity','literal','secret',6,'G2,G6'),
 ('infidelity','literal','seeing someone',8,'G2,G6'),
 ('infidelity','literal','loyal',5,'G2,G6'),
 ('infidelity','literal','faithful',5,'G2,G6'),
 ('infidelity','literal','he''s just a friend',6,'G2'),
 ('infidelity','literal','we just work together',6,'G2,G6'),
 ('infidelity','literal','you''re being jealous',7,'G2'),
 ('infidelity','literal','why don''t you trust me',7,'G2')
) AS v(category_id, match_type, pattern, severity, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3g — financial cluster, sexual_shaming, parental_alienation (phrase/regex), coercive-control regex,
--       character, mental_health/substance_shaming, threats/double_bind, triangulation, homophobic
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('financial_weaponized','literal','you don''t do anything',8,'G2'),
 ('financial_weaponized','literal','i''m the one who works hard',7,'G2'),
 ('financial_weaponized','literal','what do i get out of this',8,'G2,G6'),
 ('financial_weaponized','literal','it''s your responsibility to provide',8,'G2'),
 ('financial_control','regex','you (owe|need to pay|better pay) me',6,'G1'),
 ('financial_control','regex','where''?s? (the|my) money',6,'G1'),
 ('financial_control','regex','pay (me|for|child support)',6,'G1'),
 ('financial_control','regex','(don''t|won''t) give you (shit|anything|a dime)',6,'G1'),
 ('coercive_control','regex','(?i)(money|finances|budget|allowance|spend|account)',8,'G3'),
 ('sexual_shaming','literal','no wonder everyone leaves you',10,'G2,G6'),
 ('sexual_shaming','literal','to think i ever did',9,'G2,G6'),
 ('parental_alienation','literal','doesn''t want to see you',10,'G2'),
 ('parental_alienation','literal','i have to protect the children from you',10,'G2,G6'),
 ('parental_alienation','regex','you don''t deserve (her|him|to be a (father|dad|parent))',9,'G1'),
 ('parental_alienation','regex','(forget about|don''t expect to see) (her|him|the kid)',9,'G1'),
 ('parental_alienation','regex','if you (want to see|wanna see) (her|him)',9,'G1'),
 ('parental_alienation','regex','you(''re| are)n(''|o)?t (gonna |going to )?(see|have|get) (her|him|the kid|<CHILD_NAME>)',9,'G1'),
 ('parental_alienation','regex','(blocking you|blocked).*?(from|so you can''t see) (her|him)',9,'G1'),
 ('parental_alienation','regex','(?i)(your (father|mother|dad|mom)|bad (father|mother)|doesn''t love)',10,'G3'),
 ('parental_alienation','regex','(?i)(can''t see|not allowed|refuse|won''t let|preventing)',9,'G3'),
 ('parental_alienation','regex','dad(?:dy)?\s+(?:is|doesn''t|won''t)|mom(?:my)?\s+(?:is|doesn''t|won''t)',10,'G4'),
 ('parental_alienation','regex','who\s+do\s+you\s+want\s+to\s+(?:stay|live)\s+with',10,'G4'),
 ('communication_control','regex','(blocked|blocking) you',5,'G1'),
 ('communication_control','regex','don''t (text|call|contact) me',5,'G1'),
 ('communication_control','regex','leave me (alone|the fuck alone)',5,'G1'),
 ('communication_control','regex','lose my number',5,'G1'),
 ('communication_control','regex','never (talk|speak) to me again',5,'G1'),
 ('isolation_tactics','regex','(everyone|everybody|people) (knows|think|say) you''?re',7,'G1'),
 ('isolation_tactics','regex','told (everyone|everybody|them) (about|what) you',7,'G1'),
 ('isolation_tactics','regex','nobody (likes|wants|trusts) you',7,'G1'),
 ('isolation_tactics','regex','your (family|friends) (knows|know) (what|who) you are',7,'G1'),
 ('monitoring_stalking','regex','i know (where you|what you|who you)',8,'G1'),
 ('monitoring_stalking','regex','i(''m| am) watching you',8,'G1'),
 ('monitoring_stalking','regex','i saw you (at|with)',8,'G1'),
 ('monitoring_stalking','regex','someone told me you',8,'G1'),
 ('coercive_control','regex','(?i)(isolat|alone|no friends|can''t see|don''t need)',9,'G3'),
 ('coercive_control','regex','(?i)(track|monitor|check|where are|who are|location)',8,'G3'),
 ('coercive_control','regex','comply|do\s+what\s+I\s+(?:say|tell)',9,'G4'),
 ('coercive_control','regex','if\s+you\s+don''t|unless\s+you|or\s+else',8,'G4'),
 ('character_attacks','regex','piece of (shit|trash|garbage)',6,'G1'),
 ('character_attacks','regex','\b(motherfucker|mother fucker)\b',6,'G1'),
 ('character_attacks','regex','bitch (made|ass)',6,'G1'),
 ('character_attacks','regex','\bpussy\b',6,'G1'),
 ('character_attacks','regex','good for nothing',6,'G1'),
 ('character_attacks','regex','worthless',6,'G1'),
 ('character_attacks','regex','pathetic',6,'G1'),
 ('character_attacks','regex','loser',6,'G1'),
 ('character_assassination','regex','drug(?:s)?|high|using|addict',9,'G4'),
 ('character_assassination','literal','everyone can see what you''re like',7,'G8'),
 ('mental_health_stigma','regex','\b(psycho|crazy|insane|mental|nuts)\b',5,'G1'),
 ('mental_health_stigma','regex','\b(sick|twisted|fucked up) (in the head|mentally)',5,'G1'),
 ('mental_health_stigma','regex','need (help|therapy|meds|medication)',5,'G1'),
 ('mental_health_stigma','regex','\bweirdo\b',5,'G1'),
 ('substance_shaming','regex','\b(crackhead|crack head|tweaker|junkie|addict)\b',5,'G1'),
 ('substance_shaming','regex','\bhigh (as fuck|af|again)\b',5,'G1'),
 ('substance_shaming','regex','on (that shit|drugs|dope)',5,'G1'),
 ('threats','regex','(i''ll|i will|gonna) (fuck you up|beat|kill|hurt|destroy)',10,'G1'),
 ('threats','regex','watch your back',10,'G1'),
 ('threats','regex','you(''re| are) (gonna|going to) regret',10,'G1'),
 ('threats','regex','better watch out',10,'G1'),
 ('threats','regex','i(''ll| will) make you',10,'G1'),
 ('double_bind','regex','if you (loved|cared about) me.*?you (would|wouldn''t)',7,'G1'),
 ('double_bind','regex','you say.*?but you (don''t|never|won''t)',7,'G1'),
 ('double_bind','regex','(come over|see me).*?(leave me alone|don''t contact)',7,'G1'),
 ('triangulation','regex','(everyone|people|they) (think|say|know) you''?re',6,'G1'),
 ('triangulation','regex','i told (them|everyone|her|him) about you',6,'G1'),
 ('triangulation','regex','(he|she|they) (said|told me|thinks) you''?re',6,'G1'),
 ('triangulation','regex','my (friend|mom|family).*?(doesn''t like|hates|thinks) you',6,'G1'),
 ('triangulation','regex','(unlike you|at least|he|she).*(treats me|is there for me|cares)',6,'G1'),
 ('homophobic_slurs','regex','\bf+a+g+([og]+(e|o)?t|it)\b',7,'G1'),
 ('homophobic_slurs','regex','\bgay\b.*?\b(ass|bitch|fuck)',7,'G1'),
 ('homophobic_slurs','regex','\bqueer\b',7,'G1')
) AS v(category_id, match_type, pattern, severity, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3h — medical_abuse, reproductive_coercion, victim_deference, abuser_directives, certainty, hedge
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('medical_abuse','literal','you need your meds',9,'G2,G6'),
 ('medical_abuse','literal','did you take your pills',8,'G2,G6'),
 ('medical_abuse','literal','you''re not thinking clearly',9,'G2'),
 ('medical_abuse','literal','it''s the medication talking',9,'G2'),
 ('medical_abuse','literal','you can''t make decisions',10,'G2'),
 ('medical_abuse','literal','you''re not well enough',9,'G2'),
 ('medical_abuse','literal','i''m holding your meds',10,'G2'),
 ('medical_abuse','literal','you can''t be trusted with',9,'G2'),
 ('medical_abuse','literal','you''re bipolar',9,'G2'),
 ('medical_abuse','literal','you''re borderline',9,'G2'),
 ('medical_abuse','literal','you''re schizophrenic',9,'G2'),
 ('medical_abuse','regex','that''s your .* talking',9,'G2'),
 ('medical_abuse','literal','you''re having an episode',9,'G2'),
 ('medical_abuse','literal','you need to be hospitalized',10,'G2,G6'),
 ('medical_abuse','literal','you''re unstable',9,'G2'),
 ('medical_abuse','regex','doctor|hospital|sick|medicine',8,'G4'),
 ('medical_abuse','regex','you\s+don''t\s+need\s+to\s+know',9,'G4'),
 ('reproductive_coercion','literal','i want you pregnant',10,'G2,G6'),
 ('reproductive_coercion','literal','you should get pregnant',10,'G2,G6'),
 ('reproductive_coercion','literal','stop taking birth control',10,'G2,G6'),
 ('reproductive_coercion','literal','i''ll get you pregnant',10,'G2'),
 ('reproductive_coercion','literal','you can''t leave if you''re pregnant',10,'G2'),
 ('reproductive_coercion','literal','a baby will fix us',9,'G2,G6'),
 ('reproductive_coercion','literal','you owe me a child',10,'G2,G6'),
 ('reproductive_coercion','literal','i sabotaged your birth control',10,'G2,G6'),
 ('reproductive_coercion','literal','i''ll take the baby',10,'G2'),
 ('reproductive_coercion','literal','you''ll never see the baby',10,'G2'),
 ('reproductive_coercion','literal','i''ll prove you''re unfit',10,'G2'),
 ('reproductive_coercion','literal','you''re a bad mother',9,'G2'),
 ('reproductive_coercion','literal','the baby doesn''t need you',10,'G2'),
 ('victim_deference','literal','if that''s okay',7,'G2'),
 ('victim_deference','literal','if you don''t mind',7,'G2'),
 ('victim_deference','literal','is that alright',7,'G2,G6'),
 ('victim_deference','literal','sorry',6,'G2,G6'),
 ('victim_deference','literal','my bad',6,'G2,G6'),
 ('victim_deference','literal','i didn''t mean to',6,'G2'),
 ('victim_deference','literal','i apologize',6,'G2,G6'),
 ('victim_deference','literal','i hope that''s fine',7,'G2'),
 ('victim_deference','literal','let me know if',6,'G2,G6'),
 ('abuser_directives','literal','where are you',8,'G2,G6'),
 ('abuser_directives','literal','what are you doing',8,'G2,G6'),
 ('abuser_directives','literal','who are you with',8,'G2,G6'),
 ('abuser_directives','literal','come here',7,'G2,G6'),
 ('abuser_directives','literal','go there',7,'G2,G6'),
 ('abuser_directives','literal','do this',7,'G2,G6'),
 ('abuser_directives','literal','stop that',7,'G2,G6'),
 ('abuser_directives','literal','tell me',7,'G2,G6'),
 ('abuser_directives','literal','show me',8,'G2,G6'),
 ('abuser_directives','literal','prove it',8,'G2,G6'),
 ('certainty_absolutes','literal','always',0,'G2,G6'),
 ('certainty_absolutes','literal','never',0,'G2,G6'),
 ('certainty_absolutes','literal','nothing',0,'G2,G6'),
 ('certainty_absolutes','literal','everything',0,'G2,G6'),
 ('certainty_absolutes','literal','everyone',0,'G2,G6'),
 ('certainty_absolutes','literal','nobody',0,'G2,G6'),
 ('certainty_absolutes','literal','fact',0,'G2,G6'),
 ('certainty_absolutes','literal','obviously',0,'G2,G6'),
 ('certainty_absolutes','literal','clearly',0,'G2,G6'),
 ('certainty_absolutes','literal','literally',0,'G2,G6'),
 ('hedge_words','literal','maybe',0,'G2,G6'),
 ('hedge_words','literal','perhaps',0,'G2,G6'),
 ('hedge_words','literal','possibly',0,'G2,G6'),
 ('hedge_words','literal','might',0,'G2,G6'),
 ('hedge_words','literal','could',0,'G2,G6'),
 ('hedge_words','literal','i think',0,'G2,G6'),
 ('hedge_words','literal','i guess',0,'G2,G6'),
 ('hedge_words','literal','sort of',0,'G2,G6'),
 ('hedge_words','literal','kind of',0,'G2,G6'),
 ('hedge_words','literal','probably',0,'G2,G6')
) AS v(category_id, match_type, pattern, severity, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3i — parenting_time/gatekeeping/special_needs, communication_blocking, visit_blocking,
--       parenting_time_denial, custody_interference, child_reference (low-sev generic markers)
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('parenting_time','regex','you\s+(?:won''t|can''t)\s+see\s+(?:her|him|the\s+kid)',9,'G4'),
 ('parenting_time','regex','if\s+you\s+don''t.*(?:her|him|daughter|son)',8,'G4'),
 ('gatekeeping','regex','block(?:ed|ing)?|stop\s+(?:texting|calling)',8,'G4'),
 ('special_needs','regex','autism|autistic|spectrum|sensory|meltdown',8,'G4'),
 ('communication_blocking','regex','\bblock(ed|ing)?\s+(your|his|the)?\s*call',9,'G5'),
 ('communication_blocking','regex','\bcan''?t\s+call',8,'G5'),
 ('communication_blocking','regex','\bwon''?t\s+(let|allow)\s+(you|him)\s+call',9,'G5'),
 ('communication_blocking','regex','\bno\s+phone\s+(calls?|contact)',9,'G5'),
 ('communication_blocking','regex','\bstop\s+calling',8,'G5'),
 ('communication_blocking','regex','\bignor(e|ed|ing)\s+(your|his|the)?\s*call',8,'G5'),
 ('communication_blocking','regex','\brefus(e|ed|ing)\s+to\s+answer',8,'G5'),
 ('visit_blocking','regex','\bblock(ed|ing)?\s+(your|his|the)?\s*visit',9,'G5'),
 ('visit_blocking','regex','\bcan''?t\s+see\s+(her|him)',9,'G5'),
 ('visit_blocking','regex','\bwon''?t\s+(let|allow)\s+(you|him)\s+(see|visit)',9,'G5'),
 ('visit_blocking','regex','\bno\s+visitation',9,'G5'),
 ('visit_blocking','regex','\bcancel(ed|ing)?\s+(your|his|the)?\s*(visit|time)',8,'G5'),
 ('visit_blocking','regex','\bdenied?\s+(your|his)?\s*(visit|time|access)',9,'G5'),
 ('visit_blocking','regex','\bkeep(ing)?\s+(her|him)\s+from',9,'G5'),
 ('visit_blocking','regex','\bwon''?t\s+bring\s+(her|him)',9,'G5'),
 ('visit_blocking','regex','\brefus(e|ed|ing)\s+to\s+(bring|drop\s+off)',9,'G5'),
 ('parenting_time_denial','regex','\bno\s+parenting\s+time',8,'G5'),
 ('parenting_time_denial','regex','\bdenied?\s+parenting\s+time',8,'G5'),
 ('parenting_time_denial','regex','\binterfere?\s+with\s+(your|his)\s+time',8,'G5'),
 ('parenting_time_denial','regex','\bnot\s+(your|his)\s+weekend',8,'G5'),
 ('parenting_time_denial','regex','\bchanged?\s+(the|our)\s+schedule',7,'G5'),
 ('custody_interference','regex','\bhide?\s+(her|him|the\s+child)',9,'G5'),
 ('custody_interference','regex','\bmy\s+child\s+now',9,'G5'),
 ('custody_interference','regex','\bnot\s+(your|his)\s+(daughter|child|kid)',9,'G5'),
 ('custody_interference','regex','\bstay\s+away\s+from',8,'G5'),
 ('custody_interference','regex','\bno\s+contact',8,'G5'),
 ('custody_interference','regex','\brestraining\s+order',9,'G5'),
 ('custody_interference','regex','\bcall(ed|ing)?\s+(the\s+)?police',8,'G5'),
 ('child_reference','literal','my daughter',8,'G2,G5,G6'),
 ('child_reference','literal','our daughter',7,'G2,G5,G6'),
 ('child_reference','literal','the baby',6,'G2,G5,G6'),
 ('child_reference','literal','our child',5,'G5'),
 ('child_reference','literal','my kid',4,'G5'),
 ('child_reference','literal','the kid',6,'G2,G6')
) AS v(category_id, match_type, pattern, severity, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3j — G6 personality-disorder + custody categories (literal)
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, 'literal'::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', 'G6'
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('npd_grandiosity','better parent',7),
 ('npd_grandiosity','everyone agrees',5),
 ('npd_grandiosity','lucky to have me',6),
 ('npd_grandiosity','gave you the best years',5),
 ('npd_entitlement','i deserve',7),
 ('npd_empathy_deficit','makes me look',8),
 ('npd_empathy_deficit','being too dramatic',6),
 ('bpd_abandonment','going to abandon',6),
 ('bpd_abandonment','already abandoned',7),
 ('bpd_splitting','with me or against me',7),
 ('bpd_splitting','pure evil',6),
 ('bpd_splitting','never really loved',7),
 ('bpd_self_harm_threat','end it all',10),
 ('aspd_callousness','deserved it',7),
 ('aspd_no_remorse','you made me do',8),
 ('aspd_no_remorse','forced my hand',6),
 ('custody_court_manipulation','different judge',7),
 ('custody_court_manipulation','drag it out',8),
 ('custody_court_manipulation','game the system',9),
 ('custody_gatekeeping','none of your business',6),
 ('custody_gatekeeping','not allowed to see',8),
 ('custody_gatekeeping','without asking you',7),
 ('custody_schedule_interference','emergency came up',6),
 ('custody_schedule_interference','already made plans',7),
 ('custody_child_messenger','tell your dad',7),
 ('custody_child_messenger','find out what',8),
 ('custody_parental_replacement','real dad',8),
 ('custody_parental_replacement','real family',8),
 ('custody_parental_replacement','change their name',7)
) AS v(category_id, pattern, severity)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3k — G8 conversation-log net-new phrases (separate statement: avoids cross-section dup collisions)
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', 'G8'
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('defensiveness_evasion','literal','why are you attacking me',7),
 ('defensiveness_evasion','literal','i can''t believe you''re asking me that',6),
 ('defensiveness_evasion','literal','after everything i do for you',7),
 ('defensiveness_evasion','literal','here we go again',5),
 ('defensiveness_evasion','literal','i don''t have to explain myself to you',7),
 ('reactive_abuse','literal','see, you''re losing it',8),
 ('reactive_abuse','literal','this is what i have to deal with',7),
 ('reactive_abuse','literal','you''re the crazy one',8),
 ('reactive_abuse','literal','i''m going to record this',8),
 ('reactive_abuse','literal','look at you, you''re having an episode',9),
 ('reactive_abuse','literal','what are you going to do about it',7),
 ('reactive_abuse','literal','see? this is why no one likes you',8),
 ('reactive_abuse','literal','look at you, getting all worked up',7),
 ('feigning_incompetence','literal','i''m not smart like you',5),
 ('feigning_incompetence','literal','you know i''m bad at this stuff',5),
 ('feigning_incompetence','literal','i never graduated, what do you expect',5),
 ('feigning_incompetence','literal','just tell me what to do',4),
 ('social_media_deception','literal','i don''t even use snapchat',6),
 ('social_media_deception','literal','i never send pictures',6),
 ('social_media_deception','literal','you can check my phone',5),
 ('social_media_deception','regex','(?i)\b(i don''?t|i never)\s+(use|have)\s+snap(chat)?\b',6),
 ('last_minute_changes','literal','change of plans',5),
 ('last_minute_changes','literal','something came up',5),
 ('last_minute_changes','literal','have to cancel',6),
 ('last_minute_changes','literal','we''re not doing that anymore',7),
 ('last_minute_changes','literal','you''ll have to figure it out',7),
 ('child_endangerment','literal','i only had one',7),
 ('child_endangerment','literal','i''m fine to drive',9),
 ('child_endangerment','literal','i can handle it',6),
 ('child_endangerment','literal','stop worrying',5),
 ('emotional_dysregulation','literal','brilliant idea',0),
 ('emotional_dysregulation','literal','i can solve everything',0),
 ('emotional_dysregulation','literal','what''s the point',0),
 ('emotional_dysregulation','literal','it will never get better',0),
 ('emotional_dysregulation','literal','i''m a failure',0),
 ('emotional_dysregulation','literal','i can''t do anything right',0),
 ('selective_amnesia','literal','you''re confused',7),
 ('feigned_concern','literal','i''m worried about him',6),
 ('projection','literal','he''s obsessed with me',7),
 ('projection','literal','she is completely unstable',7),
 ('devaluation','literal','nothing you do is good enough',7),
 ('devaluation','literal','moving the goalposts',7),
 ('devaluation','literal','nothing is ever good enough',6),
 ('discard','literal','new supply',7),
 ('discard','literal','blaming you for the relationship failure',6)
) AS v(category_id, match_type, pattern, severity)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3l — G9 12-tactic gaslighting subtype phrases + platform-denial detector (with subcategory)
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, subcategory, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.subcategory, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', 'G9'
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('countering',NULL,'literal','you have a terrible memory',7),
 ('countering',NULL,'literal','you''re putting words in my mouth',7),
 ('countering',NULL,'literal','you''re misremembering',7),
 ('gaslighting_reality_distortion','withholding','literal','i don''t know what you''re talking about',6),
 ('gaslighting_reality_distortion','withholding','literal','you''re not making any sense',6),
 ('gaslighting_reality_distortion','withholding','literal','are you done',6),
 ('minimizing','trivializing','literal','you''re making a big deal out of nothing',5),
 ('denial',NULL,'literal','you''re imagining things',7),
 ('denial',NULL,'literal','there''s no proof of that',7),
 ('diverting',NULL,'literal','what about that time you',7),
 ('diverting',NULL,'literal','you''re just trying to distract from your own mistakes',7),
 ('stereotyping',NULL,'literal','you''re being hysterical',6),
 ('stereotyping',NULL,'literal','it must be that time of the month',6),
 ('stereotyping',NULL,'literal','what do you know, you''re just a kid',6),
 ('forgetting_feigned_amnesia',NULL,'literal','i have no recollection of that',6),
 ('forgetting_feigned_amnesia',NULL,'literal','are you sure that even happened',6),
 ('forgetting_feigned_amnesia',NULL,'literal','my memory of that is completely different',6),
 ('questioning_sanity',NULL,'literal','you''re losing your mind',8),
 ('questioning_sanity',NULL,'literal','you need to get help',8),
 ('questioning_sanity',NULL,'literal','everyone thinks you''re unstable',8),
 ('questioning_sanity',NULL,'literal','you sound crazy right now',8),
 ('questioning_sanity',NULL,'literal','you seem unstable',8),
 ('questioning_sanity',NULL,'literal','everyone thinks you''re paranoid',8),
 ('joke_defense',NULL,'literal','i was just kidding, can''t you take a joke',6),
 ('joke_defense',NULL,'literal','you''re too uptight',6),
 ('joke_defense',NULL,'literal','lighten up, it wasn''t serious',6),
 ('scapegoating',NULL,'literal','it''s always your fault',7),
 ('scapegoating',NULL,'literal','if it weren''t for you everything would be fine',7),
 ('scapegoating',NULL,'literal','we all know who the real problem is',7),
 ('future_faking',NULL,'literal','things will be different once',6),
 ('future_faking',NULL,'literal','i promise i''ll change, you just have to be patient',6),
 ('feeling_police',NULL,'literal','you shouldn''t feel that way',5),
 ('feeling_police',NULL,'literal','there''s no reason to be upset',5),
 ('feeling_police',NULL,'literal','why would you let that bother you',5),
 ('minimizing','overreaction_accusation','literal','you''re overreacting',5),
 ('minimizing','overreaction_accusation','literal','you''re too sensitive',5),
 ('minimizing','overreaction_accusation','literal','don''t be so dramatic',5),
 ('minimizing','overreaction_accusation','literal','making a mountain out of a molehill',5),
 ('gaslighting','categorical_denial','literal','you''re making that up',8),
 ('gaslighting','categorical_denial','literal','you must have imagined it',8),
 ('subtle_shift',NULL,'literal','that''s not how it happened',6),
 ('subtle_shift',NULL,'literal','what i actually said was',6),
 ('subtle_shift',NULL,'literal','you''re twisting my words',6),
 ('weaponizing_allies_triangulation',NULL,'regex','\b(\w+) agrees with me\b',6),
 ('weaponizing_allies_triangulation',NULL,'literal','everyone knows that you',6),
 ('weaponizing_allies_triangulation',NULL,'literal','we were just talking about how you',6),
 ('provocation_defense',NULL,'literal','you provoked me',7),
 ('provocation_defense',NULL,'literal','you pushed me to it',7),
 ('social_media_deception','platform_contradiction','regex','(?i)\b(i don''?t|i never)\s+(use|have)\s+(snap(chat)?|insta(gram)?|tiktok)\b',6)
) AS v(category_id, subcategory, match_type, pattern, severity)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  subcategory=EXCLUDED.subcategory, severity=EXCLUDED.severity, score=EXCLUDED.score,
  source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3m — positive-contrast classes (severity 0, explicit latent score=3 for contradiction phase)
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, 'literal'::pattern_match_type, v.pattern, 0::smallint, 3::smallint,
       true, true, false, 'single_party_complainant', 'G5'
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('reassurances','i''d never lie'),
 ('reassurances','you can trust me'),
 ('reassurances','i''m faithful'),
 ('declarations_of_loyalty','you''re my everything'),
 ('declarations_of_loyalty','i only love you')
) AS v(category_id, pattern)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- 3n — keyword-set detectors (pattern = label, keywords[] carries the cue set)
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, keywords, severity, score, bias_caution, is_active, is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, 'literal'::pattern_match_type, v.pattern, v.keywords::text[], v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false, 'single_party_complainant', 'G7'
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('darvo','darvo_stage_markers','{deny,attack,"reverse victim","reverse offender"}',9),
 ('economic_sabotage','financial_coercion_modes','{"conditional aid",sabotage,"dependency creation",allowance,"cut off"}',7),
 ('parental_alienation','gatekeeping_actions','{"blocked access","disparaged parent","refused meds","not allowed","won''t let"}',9),
 ('triangulation','triangulation_roles','{"flying monkey",triangulate,go-between,proxy}',7),
 ('smear_campaign','smear_intent','{"ruin reputation","gain sympathy","cover tracks",isolate}',8),
 ('fabrication','fabricated_narrative_clusters','{"abuse narrative","sobriety claim","victim stance","good mother"}',9),
 ('misdirection','distraction_goals','{"distract from drug use","sabotage work","garner sympathy"}',6),
 ('trauma_exploitation','exploitation_mechanisms','{"triggering ptsd",shaming,"threat of recurrence"}',9),
 ('substance_endangerment','substance_context','{maintenance,party,lethal,"drunk driving",driving,alcohol,amphetamines,cocaine,mdma,cannabis,poly_substance}',8)
) AS v(category_id, pattern, keywords, severity)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  keywords=EXCLUDED.keywords, severity=EXCLUDED.severity, score=EXCLUDED.score,
  source=EXCLUDED.source, is_active=EXCLUDED.is_active, bias_caution=true;

-- =====================================================================================
-- BLOCK 4 — pattern_lexicon  (sealed identifiers / restricted vulnerabilities & generic slurs)
--   COURT-SAFETY: every sealed row is a REDACTED placeholder. No real PII committed here.
-- =====================================================================================

-- 4a — SEALED identifiers (redacted placeholders; real values loaded out-of-band)
INSERT INTO analysis.pattern_lexicon
  (pattern_set_id, lexicon_type, term, variants, match_type, relevance_signal, severity, mcl_factors, is_case_specific, sensitivity_tier, source)
SELECT s.id, v.lexicon_type, v.term, v.variants::text[], v.match_type::pattern_match_type,
       v.relevance_signal, v.severity, v.mcl_factors::mcl_factor[], true, 'sealed'::sensitivity_tier, v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('child_identifier','[REDACTED:child_identifier]','{}','regex','child_subject_of_proceeding',10,'{a,i,j,k}','G1,G2,G4,G5,G6'),
 ('party_identifier','[REDACTED:documenting_party_surname]','{}','literal','case-caption / documenting party',0,'{}','G1'),
 ('party_identifier','[REDACTED:opposing_party_surname]','{}','literal','case-caption / opposing party',0,'{}','G1'),
 ('personal_identifier','[REDACTED:father_given_name]','{}','literal','case-principal (father)',0,'{}','G7'),
 ('personal_identifier','[REDACTED:mother_given_name]','{}','literal','case-principal (mother)',0,'{}','G7,G8'),
 ('personal_identifier','[REDACTED:third_party_associate]','{}','literal','third-party associate',0,'{}','G7'),
 ('relational_identifier','[REDACTED:maternal_grandmother]','{}','literal','rumor audience / triangulation node',0,'{j}','G7'),
 ('party_name','[REDACTED:party_real_names]','{}','literal','subject_of_proceeding',0,'{k}','G9'),
 ('verbatim_case_quote','[REDACTED:verbatim_case_quotes]','{}','literal','actual evidence text',0,'{k}','G9'),
 ('infidelity_place','[REDACTED:named_venue]','{}','literal','location_corroboration',0,'{f,k}','G4,G9'),
 ('vulnerability_trigger','[REDACTED:deceased_relative_suicide_ref]','{}','literal','targeted wound + deceased-relative ref',9,'{f,g,k}','G7'),
 ('vulnerability_trigger','[REDACTED:derogatory_child_epithet]','{}','literal','derogatory_child_reference',7,'{f,k}','G4')
) AS v(lexicon_type, term, variants, match_type, relevance_signal, severity, mcl_factors, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
  AND NOT EXISTS (SELECT 1 FROM analysis.pattern_lexicon pl
                  WHERE pl.pattern_set_id=s.id AND pl.lexicon_type=v.lexicon_type AND pl.term=v.term);

-- 4b — RESTRICTED vulnerabilities / named-target classes (case-specific descriptors, redacted where PII)
INSERT INTO analysis.pattern_lexicon
  (pattern_set_id, lexicon_type, term, variants, match_type, relevance_signal, severity, mcl_factors, is_case_specific, sensitivity_tier, source)
SELECT s.id, v.lexicon_type, v.term, v.variants::text[], 'literal'::pattern_match_type,
       v.relevance_signal, v.severity, v.mcl_factors::mcl_factor[], true, 'restricted'::sensitivity_tier, v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('vulnerability_trigger','[REDACTED:2009_suicide_attempt]','{}','targeted wound (Factor K/F)',9,'{f,g,k}','G7'),
 ('vulnerability_trigger','[REDACTED:named_child_condition]','{}','child_health_vulnerability',0,'{a,c}','G8'),
 ('homophobic_epithet','faggot','{fagget,fag}','identity_based_slur_at_party',7,'{f,k}','G8'),
 ('case_substance_detail','fireball','{}','intoxication/lifestyle marker',0,'{k}','G9'),
 ('weaponized_substance_phrasing','this is the drugs talking','{"are you on something","you can''t control yourself"}','substance-as-weapon (tied to allegation)',0,'{g,k}','G9'),
 ('medication_control','adderall','{addy,"i''m holding onto them for you"}','medication-as-control',0,'{g}','G9')
) AS v(lexicon_type, term, variants, relevance_signal, severity, mcl_factors, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
  AND NOT EXISTS (SELECT 1 FROM analysis.pattern_lexicon pl
                  WHERE pl.pattern_set_id=s.id AND pl.lexicon_type=v.lexicon_type AND pl.term=v.term);

-- 4c — RESTRICTED single-token derogatory epithets / slurs (generic; routed OUT of detection_pattern)
INSERT INTO analysis.pattern_lexicon
  (pattern_set_id, lexicon_type, term, match_type, relevance_signal, severity, mcl_factors, is_case_specific, sensitivity_tier, source)
SELECT s.id, v.lexicon_type, v.term, 'literal'::pattern_match_type, v.origin, v.severity,
       v.mcl_factors::mcl_factor[], false, 'restricted'::sensitivity_tier, v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('sexual_epithet','slut','sexual_shaming',10,'{b,f,k}','G2,G6'),
 ('sexual_epithet','whore','sexual_shaming',10,'{b,f,k}','G2,G6'),
 ('sexual_epithet','pervert','sexual_shaming',9,'{b,f,k}','G2,G6'),
 ('sexual_epithet','freak','sexual_shaming',9,'{b,f,k}','G2,G6'),
 ('sexual_epithet','disgusting','sexual_shaming',8,'{b,f,k}','G2,G6'),
 ('sexual_epithet','sick','sexual_shaming',8,'{b,f,k}','G2,G6'),
 ('sexual_epithet','nasty','sexual_shaming',8,'{b,f,k}','G2,G6'),
 ('sexual_epithet','used','sexual_shaming',9,'{b,f,k}','G2,G6'),
 ('sexual_epithet','cheap','sexual_shaming',8,'{b,f,k}','G2,G6'),
 ('drug_slur','crackhead','substance_weaponized',9,'{f,g,k}','G2,G6'),
 ('drug_slur','tweaker','substance_weaponized',9,'{f,g,k}','G2,G6'),
 ('drug_slur','junkie','substance_weaponized',9,'{f,g,k}','G2,G6'),
 ('drug_slur','addict','substance_weaponized',8,'{f,g,k}','G2,G6'),
 ('drug_slur','user','substance_weaponized',7,'{f,g,k}','G2,G6')
) AS v(lexicon_type, term, origin, severity, mcl_factors, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
  AND NOT EXISTS (SELECT 1 FROM analysis.pattern_lexicon pl
                  WHERE pl.pattern_set_id=s.id AND pl.lexicon_type=v.lexicon_type AND pl.term=v.term);

-- 4d — RESTRICTED generic kinship references (is_case_specific=false; generic templates only)
INSERT INTO analysis.pattern_lexicon
  (pattern_set_id, lexicon_type, term, variants, match_type, relevance_signal, severity, mcl_factors, is_case_specific, sensitivity_tier, source)
SELECT s.id, 'child_reference', 'my daughter',
       '{"our daughter","your daughter","the baby","the kid","the child","our child","my kid","my child"}'::text[],
       'literal'::pattern_match_type, 'generic_kinship_reference', 8, '{a}'::mcl_factor[],
       false, 'restricted'::sensitivity_tier, 'G4,G6'
FROM analysis.detection_pattern_set s
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
  AND NOT EXISTS (SELECT 1 FROM analysis.pattern_lexicon pl
                  WHERE pl.pattern_set_id=s.id AND pl.lexicon_type='child_reference' AND pl.term='my daughter');

-- 4e — RESTRICTED HurtLex hate-speech category taxonomy (16 codes; runtime lemmas external)
INSERT INTO analysis.pattern_lexicon
  (pattern_set_id, lexicon_type, term, match_type, relevance_signal, is_case_specific, sensitivity_tier, source)
SELECT s.id, 'hurtlex_category', v.code, 'literal'::pattern_match_type, v.label,
       false, 'restricted'::sensitivity_tier, 'G1'
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('ps','ethnic_slurs'),('rci','locations'),('pa','professions'),('ddf','physical_disabilities'),
 ('dmc','cognitive_disabilities'),('is','social_economic'),('or','plants'),('an','animals'),
 ('asm','male_sexuality'),('asf','female_sexuality'),('pr','prostitution'),('om','moral_behavioral'),
 ('qas','generic_insults'),('cds','derogatory_words'),('re','criminal'),('svp','social_political')
) AS v(code, label)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
  AND NOT EXISTS (SELECT 1 FROM analysis.pattern_lexicon pl
                  WHERE pl.pattern_set_id=s.id AND pl.lexicon_type='hurtlex_category' AND pl.term=v.code);

-- 4f — PUBLIC sentiment-cue lexicons (is_case_specific=false, tier=public)
INSERT INTO analysis.pattern_lexicon
  (pattern_set_id, lexicon_type, term, variants, match_type, relevance_signal, is_case_specific, sensitivity_tier, source)
SELECT s.id, v.lexicon_type, v.lexicon_type, v.variants::text[], 'literal'::pattern_match_type,
       'sentiment_cue', false, 'public'::sensitivity_tier, 'G1'
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('sentiment_cue_negative','{hate,angry,fuck,shit,kill,hurt,destroy}'),
 ('sentiment_cue_positive','{love,miss,please,sorry,want,need}')
) AS v(lexicon_type, variants)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
  AND NOT EXISTS (SELECT 1 FROM analysis.pattern_lexicon pl
                  WHERE pl.pattern_set_id=s.id AND pl.lexicon_type=v.lexicon_type AND pl.term=v.lexicon_type);

-- =====================================================================================
-- BLOCK 5 — behavior_category_mcl  (per-category MCL 722.23 factor mappings)
--   is_critical computed = (factor_code IN ('j','k')) per statute-critical rule (J=facilitation
--   of other-parent relationship, K=domestic violence). note carries source provenance.
-- =====================================================================================
INSERT INTO analysis.behavior_category_mcl (category_id, factor_code, weight, is_critical, note)
SELECT v.category_id, v.factor_code::mcl_factor, v.weight, (v.factor_code IN ('j','k')), 'src: '||v.source
FROM (VALUES
 ('threats','k','high','G1'),('threats','j','medium','G1'),
 ('child_weaponization','j','high','G1'),('child_weaponization','k','medium','G1'),
 ('monitoring_stalking','k','high','G1'),('monitoring_stalking','g','medium','G1'),
 ('homophobic_slurs','f','high','G1'),('homophobic_slurs','k','medium','G1'),
 ('isolation_tactics','j','medium','G1'),('isolation_tactics','k','high','G1'),
 ('gaslighting','a','medium','G3,G4'),('gaslighting','f','high','G2,G3,G4'),('gaslighting','g','high','G2'),('gaslighting','k','high','G1,G2,G3,G4'),
 ('double_bind','k','high','G1'),('double_bind','j','medium','G1'),
 ('character_attacks','f','high','G1'),('character_attacks','k','medium','G1'),
 ('financial_control','c','high','G1,G5,G9'),('financial_control','k','medium','G1,G5'),('financial_control','l','low','G5'),
 ('triangulation','f','medium','G5,G7'),('triangulation','j','high','G1,G5,G7'),('triangulation','k','high','G1,G7'),('triangulation','l','low','G5'),
 ('communication_control','j','medium','G1'),('communication_control','k','medium','G1'),
 ('substance_shaming','f','high','G1'),('substance_shaming','g','medium','G1'),
 ('mental_health_stigma','f','high','G1'),('mental_health_stigma','g','medium','G1'),
 ('love_bombing','a','high','G1,G3,G4'),('love_bombing','f','high','G3,G4'),('love_bombing','j','medium','G1,G2'),('love_bombing','k','medium','G1,G2'),('love_bombing','l','low','G2'),
 ('blame_shifting','f','high','G2,G3,G4'),('blame_shifting','j','medium','G4'),('blame_shifting','k','high','G3,G4'),
 ('minimizing','f','high','G2,G3,G4'),('minimizing','j','low','G4'),('minimizing','k','high','G3'),
 ('circular','l','low','G2'),
 ('darvo_deny','f','medium','G2'),
 ('darvo_attack','f','high','G2'),('darvo_attack','k','medium','G2'),
 ('darvo_reverse','f','high','G2'),('darvo_reverse','k','high','G2'),
 ('overelaboration','f','high','G2,G3'),('overelaboration','l','low','G2,G4'),
 ('excessive_gratitude','l','low','G2'),('excessive_gratitude','f','medium','G2'),
 ('debt_reminders','f','medium','G2'),
 ('savior_complex','f','medium','G2'),('savior_complex','k','high','G2'),
 ('substance_alcohol','g','low','G2'),
 ('substance_weaponized','f','medium','G2'),('substance_weaponized','g','medium','G2'),('substance_weaponized','k','high','G2 via substance_weaponization'),
 ('adderall_control','c','medium','G2'),('adderall_control','g','medium','G2'),('adderall_control','k','high','G2'),
 ('infidelity','f','medium','G2'),
 ('financial_weaponized','c','medium','G2'),('financial_weaponized','f','medium','G2'),
 ('sexual_shaming','b','medium','G4'),('sexual_shaming','f','high','G2,G4'),('sexual_shaming','k','medium','G2,G4'),
 ('parental_alienation','a','high','G2,G3,G4'),('parental_alienation','i','medium','G3,G4'),('parental_alienation','j','high','G2,G3,G4'),('parental_alienation','k','medium','G2,G4'),
 ('medical_abuse','c','medium','G2'),('medical_abuse','f','medium','G4'),('medical_abuse','g','high','G2,G4'),('medical_abuse','j','medium','G4'),('medical_abuse','k','high','G2'),
 ('reproductive_coercion','f','high','G2'),('reproductive_coercion','j','high','G4'),('reproductive_coercion','k','high','G2,G4'),('reproductive_coercion','l','medium','G4'),
 ('victim_deference','k','medium','G2'),
 ('abuser_directives','k','high','G2'),
 ('certainty_absolutes','l','low','G2'),
 ('hedge_words','l','low','G2'),
 ('darvo','f','high','G3,G4'),('darvo','j','high','G3,G4'),('darvo','k','high','G3,G4'),
 ('coercive_control','c','high','G3,G4'),('coercive_control','j','high','G3,G4'),('coercive_control','k','high','G3,G4'),
 ('affirmations','a','high','G3,G4'),('affirmations','f','high','G3'),
 ('expectation_setting','a','high','G3'),('expectation_setting','c','high','G3'),
 ('cooperation','a','medium','G4'),('cooperation','b','high','G3'),('cooperation','d','medium','G4'),('cooperation','j','high','G3'),
 ('dependency_cultivation','f','high','G3'),
 ('stonewalling','f','medium','G4'),('stonewalling','k','medium','G4'),
 ('financial_abuse','c','high','G4'),('financial_abuse','j','medium','G4'),
 ('substance_weaponization','b','medium','G4'),('substance_weaponization','f','high','G4'),('substance_weaponization','g','high','G4'),('substance_weaponization','k','high','G4'),
 ('reactive_abuse','f','medium','G4'),('reactive_abuse','j','medium','G4'),('reactive_abuse','k','medium','G4'),
 ('character_assassination','b','medium','G4'),('character_assassination','f','high','G4'),('character_assassination','k','medium','G4'),
 ('isolation','c','high','G9'),('isolation','j','high','G4,G5'),('isolation','k','high','G4,G7,G9'),
 ('hoovering','a','medium','G4'),('hoovering','f','medium','G4'),
 ('parenting_time','j','high','G4'),('parenting_time','k','medium','G4'),
 ('gatekeeping','j','high','G4'),
 ('special_needs','a','high','G4'),('special_needs','c','high','G4'),('special_needs','l','medium','G4'),
 ('threats_intimidation','j','medium','G4'),('threats_intimidation','k','high','G4,G9'),
 ('future_faking','l','low','G4'),
 ('apologies','l','low','G4'),
 ('gift_giving','c','low','G4'),
 ('power_asymmetry','j','low','G4'),('power_asymmetry','l','low','G4'),
 ('manipulation','l','low','G5'),
 ('intimidation','f','high','G7'),('intimidation','k','high','G5,G7'),
 ('denial','f','high','G7'),('denial','l','low','G5'),
 ('stalking','g','medium','G5'),('stalking','k','high','G5'),
 ('coordinated_abuse','j','medium','G5'),('coordinated_abuse','k','high','G5'),('coordinated_abuse','l','low','G5'),
 ('smear_campaign','f','medium','G5,G7'),('smear_campaign','j','high','G5,G7'),('smear_campaign','k','high','G7'),
 ('silent_treatment','j','medium','G5'),('silent_treatment','l','low','G5'),
 ('communication_blocking','j','high','G5'),
 ('visit_blocking','j','high','G5'),
 ('parenting_time_denial','j','high','G5'),
 ('custody_interference','j','high','G5'),('custody_interference','k','high','G5'),
 ('child_reference','i','medium','G5'),
 ('economic_sabotage','c','high','G7'),('economic_sabotage','k','high','G7'),
 ('suicide_baiting','f','high','G7'),('suicide_baiting','g','high','G7'),('suicide_baiting','k','high','G7'),
 ('projection','f','high','G7,G8'),
 ('minimization','f','high','G7'),
 ('fabrication','f','high','G7'),('fabrication','k','high','G7'),
 ('misdirection','f','high','G7'),
 ('inconsistent_account','f','high','G7'),
 ('manufactured_crisis','f','high','G7'),('manufactured_crisis','k','high','G7'),
 ('child_exposure','f','high','G7'),('child_exposure','j','high','G7'),('child_exposure','k','high','G7'),
 ('trauma_exploitation','f','high','G7'),('trauma_exploitation','k','high','G7'),
 ('substance_endangerment','c','high','G7'),('substance_endangerment','g','high','G7'),('substance_endangerment','k','high','G7'),
 ('medical_neglect','c','high','G7'),('medical_neglect','g','high','G7'),
 ('bpd_self_harm_threat','g','high','G6'),('bpd_self_harm_threat','k','high','G6'),
 ('custody_court_manipulation','f','medium','G6'),('custody_court_manipulation','j','high','G6'),
 ('custody_gatekeeping','j','high','G6'),
 ('custody_schedule_interference','j','medium','G6'),
 ('custody_child_messenger','i','medium','G6'),('custody_child_messenger','j','high','G6'),
 ('custody_parental_replacement','a','high','G6'),('custody_parental_replacement','j','high','G6'),
 ('feigning_incompetence','c','medium','G8'),('feigning_incompetence','j','medium','G8'),
 ('defensiveness_evasion','f','high','G8'),
 ('social_media_deception','f','high','G8'),
 ('last_minute_changes','j','high','G8'),
 ('emotional_dysregulation','g','high','G8'),
 ('guilt_tripping','f','medium','G8'),('guilt_tripping','k','medium','G8'),
 ('feigned_concern','f','medium','G8'),('feigned_concern','j','medium','G8'),
 ('flying_monkeys','j','high','G8'),('flying_monkeys','k','high','G8'),
 ('devaluation','a','high','G8'),('devaluation','f','high','G8'),
 ('discard','a','high','G8'),('discard','j','medium','G8'),
 ('child_endangerment','c','high','G8'),('child_endangerment','g','high','G8'),('child_endangerment','k','high','G8'),
 ('autism_weaponization','a','high','G8'),('autism_weaponization','c','high','G8'),('autism_weaponization','j','high','G8'),
 ('block_unblock_cycle','j','high','G8'),('block_unblock_cycle','k','medium','G8'),
 ('word_salad','l','low','G8'),
 ('selective_amnesia','f','high','G8'),
 ('monitoring_surveillance','k','high','G9'),
 ('gaslighting_reality_distortion','k','high','G9'),
 ('verbal_degradation','b','high','G9'),('verbal_degradation','k','high','G9'),
 ('autonomy_deprivation','c','high','G9'),('autonomy_deprivation','k','high','G9'),
 ('identity_erosion','k','high','G9'),
 ('sexual_reproductive_coercion','k','high','G9'),
 ('jealousy_possessiveness','k','high','G9'),
 ('narcissistic_entitlement','k','high','G9'),
 ('legal_system_abuse','j','high','G9'),('legal_system_abuse','k','high','G9'),
 ('entrapment_fear','k','high','G9')
) AS v(category_id, factor_code, weight, source)
ON CONFLICT (category_id, factor_code) DO UPDATE SET
  weight=EXCLUDED.weight, is_critical=EXCLUDED.is_critical, note=EXCLUDED.note;

-- =====================================================================================
-- END 0006_behavior_seed.sql
-- =====================================================================================
