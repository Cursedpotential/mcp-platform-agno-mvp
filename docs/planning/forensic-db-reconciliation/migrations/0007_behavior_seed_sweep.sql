-- =====================================================================================
-- 0007_behavior_seed_sweep.sql — sweep-2026-07-03 ontology delta (IDEMPOTENT, re-runnable)
-- Byline: Claude Code · 2026-07-04
-- =====================================================================================
--  GENERATED FROM THE LIVE DB (read-only export) — the 2026-07-03 local sweep applied
--  these rows directly to live PG without a committed migration; this file captures them
--  so the repo migration chain (0005+0006+0007) reproduces live. Sources swept:
--  expanded-pattern-library, research-behavioral-analysis, app.py escalation_index,
--  pronoun-ratio-analysis.
--
--  COURT-SAFETY: same posture as 0006 — every pattern is a HYPOTHESIS (bias_caution=true,
--  authored_perspective='single_party_complainant', symmetric application per Kubicki v.
--  Sharpe). All rows generic (is_case_specific=false); NO lexicon values exported —
--  sealed identifiers stay out-of-band by design.
--
--  Requires 0005 (schema) + 0006 (base seed: the detection_pattern_set row).
-- =====================================================================================

SET search_path = analysis, ai, public;

-- BLOCK 1 — behavior_category (11 sweep categories)
INSERT INTO analysis.behavior_category
  (category_id, label, polarity, default_severity, mcl_factors, aliases, is_case_specific, source)
SELECT v.category_id, v.label, v.polarity::category_polarity, v.default_severity,
       v.mcl_factors::mcl_factor[], v.aliases::citext[], v.is_case_specific, v.source
FROM (VALUES
 ('boundary_testing','Boundary testing','negative',6,'{k}','{}',false,'sweep-2026-07-03:expanded-pattern-library'),
 ('boundary_violation','Boundary violation','negative',7,'{k}','{}',false,'sweep-2026-07-03:research-behavioral-analysis'),
 ('cycle_honeymoon','Cycle of abuse: reconciliation/honeymoon','negative',4,'{k}','{}',false,'sweep-2026-07-03:expanded-pattern-library'),
 ('cycle_tension','Cycle of abuse: tension-building','negative',5,'{k}','{}',false,'sweep-2026-07-03:expanded-pattern-library'),
 ('escalation','Escalation over time','negative',7,'{k}','{}',false,'sweep-2026-07-03:app.py-escalation_index'),
 ('guilt_trip','Guilt-tripping','negative',6,'{k}','{}',false,'sweep-2026-07-03:research-behavioral-analysis'),
 ('intermittent_reinforcement','Intermittent reinforcement','negative',8,'{k}','{}',false,'sweep-2026-07-03:research-behavioral-analysis'),
 ('interruption','Interruption / conversational dominance','linguistic_marker',3,'{l}','{}',false,'sweep-2026-07-03:expanded-pattern-library'),
 ('mirroring','Mirroring / agreement-bombing','negative',5,'{j,k}','{}',false,'sweep-2026-07-03:expanded-pattern-library'),
 ('premature_intimacy','Premature intimacy / rushing','negative',5,'{k}','{}',false,'sweep-2026-07-03:expanded-pattern-library'),
 ('pronoun_ratio','Pronoun-ratio linguistic marker','linguistic_marker',0,'{l}','{}',false,'sweep-2026-07-03:pronoun-ratio-analysis')
) AS v(category_id, label, polarity, default_severity, mcl_factors, aliases, is_case_specific, source)
ON CONFLICT (category_id) DO UPDATE SET
  label=EXCLUDED.label, polarity=EXCLUDED.polarity, default_severity=EXCLUDED.default_severity,
  mcl_factors=EXCLUDED.mcl_factors, aliases=EXCLUDED.aliases,
  is_case_specific=EXCLUDED.is_case_specific, source=EXCLUDED.source;

-- BLOCK 2 — detection_pattern (15 sweep patterns; set = casebible-behavioral 1.0.0)
INSERT INTO analysis.detection_pattern
  (pattern_set_id, category_id, match_type, pattern, severity, score, bias_caution, is_active,
   is_case_specific, authored_perspective, source)
SELECT s.id, v.category_id, v.match_type::pattern_match_type, v.pattern, v.severity,
       GREATEST(coalesce(v.severity,1),1)::smallint, true, true, v.is_case_specific,
       'single_party_complainant', v.source
FROM analysis.detection_pattern_set s
CROSS JOIN (VALUES
 ('boundary_violation','regex','i don''?(t| ?not) (care|give a (fuck|shit)) what you (said|want|think)',7,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('boundary_violation','regex','i''?(ll| will) (do|say) (what|whatever) i want',7,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('boundary_violation','regex','i''?m (coming|showing up|going to be there) (whether|even if) you (like it or not|want|say)',8,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('boundary_violation','regex','you can''?(t| ?not) (tell|stop) me',7,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('guilt_trip','regex','after (all|everything) i''?(ve| have) (sacrificed|put up with)',6,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('guilt_trip','regex','after (everything|all) i''?(ve| have) (done|did) for you',6,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('guilt_trip','regex','how could you (do this|treat me) (to me|like this)',6,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('guilt_trip','regex','i (gave up|sacrificed) (everything|so much|my life) for you',7,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('guilt_trip','regex','i''?m the one (who|thats|that''?s) (suffering|hurting|struggling)',5,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('guilt_trip','regex','you''?(d| would) be (nothing|lost|homeless) without me',7,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('premature_intimacy','regex','i can''?(t| ?not) (live|imagine (my )?life) without you',6,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('premature_intimacy','regex','i''?(ve| have) never felt (this|like this) (way )?(about anyone )?before',5,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('premature_intimacy','regex','no one (has ever|will ever) (understand|love|get) (me|you)',5,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('premature_intimacy','regex','we''?re (meant to be|made for each other)',5,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2'),
 ('premature_intimacy','regex','you''?re my soulmate',5,false,'sweep-2026-07-03:app.py+expanded-pattern-library:v2')
) AS v(category_id, match_type, pattern, severity, is_case_specific, source)
WHERE s.name='casebible-behavioral' AND s.version='1.0.0'
ON CONFLICT (pattern_set_id, category_id, match_type, pattern) DO UPDATE SET
  severity=EXCLUDED.severity, score=EXCLUDED.score, source=EXCLUDED.source,
  is_active=EXCLUDED.is_active, bias_caution=true;
