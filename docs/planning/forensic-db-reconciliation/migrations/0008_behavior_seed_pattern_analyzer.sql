-- =====================================================================================
-- 0008_behavior_seed_pattern_analyzer.sql — pattern-analyzer.ts corpus delta (IDEMPOTENT)
-- Byline: Claude Code · 2026-07-04
-- =====================================================================================
--  SOURCE: the pre-Agno pattern-analyzer.ts BUILT_IN_PATTERNS corpus (P2.1 extraction,
--  evidence/config/behavioral_patterns.json) — the ONE G1-G9 fragment the 0006 union
--  did NOT include. This file adds only what 0006+0007 lack: 1 category + the literal
--  phrases absent from the chain, mapped to same-name categories.
--
--  STATUS: COMMITTED but NOT YET APPLIED to live — application is owner-gated (HITL).
--  The live smoke will report live as 'chain applied through 0007' until this runs.
--
--  COURT-SAFETY: same posture as 0006/0007 — every pattern is a HYPOTHESIS
--  (bias_caution=true, authored_perspective='single_party_complainant', symmetric
--  application per Kubicki v. Sharpe). All phrases generic; no identifiers.
--
--  Requires 0006 (detection_pattern_set row) + 0007.
-- =====================================================================================

SET search_path = analysis, ai, public;

-- BLOCK 1 — behavior_category (1 corpus category not in chain)
INSERT INTO analysis.behavior_category
  (category_id, label, polarity, default_severity, mcl_factors, aliases, is_case_specific, source)
SELECT v.category_id, v.label, v.polarity::category_polarity, v.default_severity,
       v.mcl_factors::mcl_factor[], v.aliases::citext[], v.is_case_specific, v.source
FROM (VALUES
 ('emotional_blackmail','Emotional Blackmail','negative',8,'{f,j}','{}',false,'P2.1:pattern-analyzer.ts')
) AS v(category_id, label, polarity, default_severity, mcl_factors, aliases, is_case_specific, source)
ON CONFLICT (category_id) DO UPDATE SET
  label=EXCLUDED.label, polarity=EXCLUDED.polarity, default_severity=EXCLUDED.default_severity,
  mcl_factors=EXCLUDED.mcl_factors, source=EXCLUDED.source;

-- BLOCK 2 — detection_pattern (134 pattern-analyzer literal phrases absent from chain)
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active,
   is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, 'literal'::pattern_match_type, v.pattern, v.severity,
       GREATEST(v.severity,1)::smallint, true, true, false,
       'single_party_complainant', 'P2.1:pattern-analyzer.ts'
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('apologies','give me another chance',6),
 ('apologies','i feel terrible',6),
 ('apologies','i made a mistake',6),
 ('apologies','i regret',6),
 ('apologies','i shouldn''t have',6),
 ('apologies','i was wrong',6),
 ('apologies','i''ll do better',6),
 ('apologies','i''m sorry',6),
 ('apologies','please forgive me',6),
 ('blame_shifting','it''s because you',8),
 ('blame_shifting','this wouldn''t happen if you',8),
 ('blame_shifting','you bring out the worst',8),
 ('blame_shifting','you drove me to',8),
 ('blame_shifting','you pushed me to',8),
 ('blame_shifting','you started it',8),
 ('blame_shifting','you''re the reason',8),
 ('emotional_blackmail','after everything i''ve done',8),
 ('emotional_blackmail','how could you do this to me',8),
 ('emotional_blackmail','i can''t live without',8),
 ('emotional_blackmail','i gave up everything',8),
 ('emotional_blackmail','i sacrificed',8),
 ('emotional_blackmail','i thought you cared',8),
 ('emotional_blackmail','i''ll hurt myself',8),
 ('emotional_blackmail','if you loved me',8),
 ('emotional_blackmail','you owe me',8),
 ('emotional_blackmail','you''ll destroy me',8),
 ('emotional_blackmail','you''re breaking my heart',8),
 ('future_faking','i promise to',8),
 ('future_faking','i''ll change',8),
 ('future_faking','i''ll make it up to you',8),
 ('future_faking','i''m going to buy you',8),
 ('future_faking','just wait until',8),
 ('future_faking','next time',8),
 ('future_faking','one day we''ll',8),
 ('future_faking','soon we''ll',8),
 ('future_faking','things will be different',8),
 ('future_faking','we''ll travel the world',8),
 ('future_faking','when we get married',8),
 ('future_faking','when we have kids',8),
 ('gaslighting','everyone agrees with me',9),
 ('gaslighting','no one else thinks that',9),
 ('gaslighting','that''s not what happened',9),
 ('gaslighting','you always twist things',9),
 ('gaslighting','you have a bad memory',9),
 ('gaslighting','you''re being paranoid',9),
 ('gaslighting','you''re making things up',9),
 ('gaslighting','you''re the only one who',9),
 ('guilt_trip','after everything i''ve done',5),
 ('guilt_trip','you don''t care about me',5),
 ('isolation_tactics','choose me or them',8),
 ('isolation_tactics','i''m the only one',8),
 ('isolation_tactics','it''s us against the world',8),
 ('isolation_tactics','no one understands you like i do',8),
 ('isolation_tactics','they''re against us',8),
 ('isolation_tactics','they''re jealous',8),
 ('isolation_tactics','they''re trying to break us up',8),
 ('isolation_tactics','they''re using you',8),
 ('isolation_tactics','you don''t need them',8),
 ('isolation_tactics','you spend too much time with',8),
 ('isolation_tactics','your family is toxic',8),
 ('isolation_tactics','your friends don''t care',8),
 ('love_bombing','i can''t live without you',8),
 ('love_bombing','i''m so lucky',8),
 ('love_bombing','i''ve never felt this way',8),
 ('love_bombing','i''ve never loved anyone like',8),
 ('love_bombing','we''re meant to be',8),
 ('love_bombing','you complete me',8),
 ('love_bombing','you''re amazing',8),
 ('love_bombing','you''re incredible',8),
 ('love_bombing','you''re my soulmate',8),
 ('love_bombing','you''re perfect',8),
 ('love_bombing','you''re the best thing',8),
 ('love_bombing','you''re too good for me',8),
 ('medical_abuse','that''s your condition talking',10),
 ('minimization','chill out',8),
 ('minimization','don''t be dramatic',8),
 ('minimization','it wasn''t that bad',8),
 ('minimization','it''s in the past',8),
 ('minimization','it''s not a big deal',8),
 ('minimization','it''s nothing',8),
 ('minimization','let it go',8),
 ('minimization','move on already',8),
 ('minimization','stop dwelling',8),
 ('minimization','you''re blowing this out of proportion',8),
 ('minimization','you''re making a mountain',8),
 ('parental_alienation','daddy doesn''t care',10),
 ('parental_alienation','daddy doesn''t love',10),
 ('parental_alienation','don''t tell them',10),
 ('parental_alienation','it''s their fault',10),
 ('parental_alienation','mommy doesn''t care',10),
 ('parental_alienation','mommy doesn''t love',10),
 ('parental_alienation','our little secret',10),
 ('parental_alienation','they abandoned',10),
 ('parental_alienation','they chose',10),
 ('parental_alienation','they don''t understand',10),
 ('parental_alienation','they don''t want to see you',10),
 ('parental_alienation','they''ll be mad at you',10),
 ('parental_alienation','they''re the bad guy',10),
 ('parental_alienation','you''re better off without',10),
 ('parental_alienation','your father doesn''t love',10),
 ('parental_alienation','your mother doesn''t love',10),
 ('projection','you always',8),
 ('projection','you never',8),
 ('projection','you''re abusive',8),
 ('projection','you''re cheating',8),
 ('projection','you''re controlling',8),
 ('projection','you''re the narcissist',8),
 ('projection','you''re the one who',8),
 ('stonewalling','conversation is over',7),
 ('stonewalling','do what you want',7),
 ('stonewalling','don''t contact me',7),
 ('stonewalling','fine',7),
 ('stonewalling','i don''t care',7),
 ('stonewalling','i have nothing to say',7),
 ('stonewalling','i''m done',7),
 ('stonewalling','i''m not talking about this',7),
 ('stonewalling','leave me alone',7),
 ('stonewalling','talk to my lawyer',7),
 ('threats_intimidation','don''t test me',10),
 ('threats_intimidation','i''ll destroy',10),
 ('threats_intimidation','i''ll expose',10),
 ('threats_intimidation','i''ll make sure',10),
 ('threats_intimidation','i''ll ruin',10),
 ('threats_intimidation','i''ll take the kids',10),
 ('threats_intimidation','i''ll tell everyone',10),
 ('threats_intimidation','or else',10),
 ('threats_intimidation','watch what happens',10),
 ('threats_intimidation','you don''t want to',10),
 ('threats_intimidation','you''ll be sorry',10),
 ('threats_intimidation','you''ll lose everything',10),
 ('threats_intimidation','you''ll never see',10),
 ('threats_intimidation','you''ll pay for',10),
 ('threats_intimidation','you''ll regret',10),
 ('triangulation','everyone thinks you''re',5)
) AS v(category_id, pattern, severity)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source, bias_caution=true;
