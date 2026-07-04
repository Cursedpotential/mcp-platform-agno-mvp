-- 0005_behavioral_patterns.sql — behavioral pattern library as data (P2.1).
--
-- GENERATED from evidence/config/behavioral_patterns.json by
-- `python -m evidence.patterns` — edit the JSON, not this file.
-- Seed: 28 modules, 249 phrases, 12 MCL factors, 4 contradiction rules.
--
-- Provenance: pre-Agno pattern-analyzer.ts BUILT_IN_MODULES/BUILT_IN_PATTERNS,
-- forensics-router.ts MCL_FACTORS, RESEARCH_BEHAVIORAL_ANALYSIS.md taxonomy
-- (see docs/planning/port-backlog.md Tier 1). needs_review rows have NO MCL
-- mapping by design — statutory mapping is an owner decision.
--
-- Idempotent: re-running upserts the seed. Requires 0002 (analysis schema)
-- and 0004 (mcl_factor enum).

CREATE TABLE IF NOT EXISTS analysis.mcl_factor_ref (
  letter mcl_factor PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT NOT NULL   -- MCL 722.23 statutory language
);

CREATE TABLE IF NOT EXISTS analysis.analysis_module (
  id TEXT PRIMARY KEY,        -- stable module id, e.g. 'gaslighting'
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  polarity TEXT NOT NULL CHECK (polarity IN ('negative','positive','neutral')),
  subcategory TEXT NOT NULL,
  weight INT NOT NULL CHECK (weight BETWEEN 0 AND 100),
  enabled BOOLEAN NOT NULL DEFAULT TRUE,
  mcl_factors mcl_factor[] NOT NULL DEFAULT '{}',
  needs_review BOOLEAN NOT NULL DEFAULT FALSE,  -- owner triage pending
  provenance TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS analysis.pattern_phrase (
  id UUID PRIMARY KEY DEFAULT uuidv7(),
  module_id TEXT NOT NULL REFERENCES analysis.analysis_module(id) ON DELETE CASCADE,
  phrase TEXT NOT NULL,
  kind TEXT NOT NULL DEFAULT 'literal' CHECK (kind IN ('literal','regex')),
  UNIQUE (module_id, phrase)
);
CREATE INDEX IF NOT EXISTS pattern_phrase_module_idx ON analysis.pattern_phrase (module_id);

CREATE TABLE IF NOT EXISTS analysis.contradiction_rule (
  id TEXT PRIMARY KEY,
  positive_module TEXT NOT NULL REFERENCES analysis.analysis_module(id),
  negative_modules TEXT[] NOT NULL DEFAULT '{}',
  description TEXT NOT NULL,
  provenance TEXT NOT NULL DEFAULT ''
);

-- ---- MCL 722.23 factor reference ----
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('a', 'Love, Affection, and Emotional Ties', 'The love, affection, and other emotional ties existing between the parties involved and the child.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('b', 'Capacity to Continue Education', 'The capacity and disposition of the parties involved to give the child love, affection, and guidance and to continue the education and raising of the child in his or her religion or creed.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('c', 'Capacity to Provide', 'The capacity and disposition of the parties involved to provide the child with food, clothing, medical care or other remedial care.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('d', 'Length of Time in Environment', 'The length of time the child has lived in a stable, satisfactory environment, and the desirability of maintaining continuity.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('e', 'Permanence of Family Unit', 'The permanence, as a family unit, of the existing or proposed custodial home or homes.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('f', 'Moral Fitness', 'The moral fitness of the parties involved.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('g', 'Mental and Physical Health', 'The mental and physical health of the parties involved.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('h', 'Home, School, and Community Record', 'The home, school, and community record of the child.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('i', 'Reasonable Preference of Child', 'The reasonable preference of the child, if the court considers the child to be of sufficient age to express preference.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('j', 'Domestic Violence', 'The willingness and ability of each of the parties to facilitate and encourage a close and continuing parent-child relationship between the child and the other parent or the child and the parents. A court may not consider negatively for the purposes of this factor any reasonable action taken by a parent to protect a child or that parent from sexual assault or domestic violence by the child''s other parent.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('k', 'Willingness to Facilitate Relationship', 'Domestic violence, regardless of whether the violence was directed against or witnessed by the child.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;
INSERT INTO analysis.mcl_factor_ref (letter, name, description) VALUES ('l', 'Other Factors', 'Any other factor considered by the court to be relevant to a particular child custody dispute.') ON CONFLICT (letter) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description;

-- ---- Analysis modules ----
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('gaslighting', 'Gaslighting Detection', 'Identifies reality-distorting statements that make the victim question their perception', 'negative', 'manipulation', 90, ARRAY['j'::mcl_factor, 'k'::mcl_factor, 'l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('blame_shifting', 'Blame Shifting', 'Detects patterns where responsibility is deflected onto the victim', 'negative', 'manipulation', 85, ARRAY['j'::mcl_factor, 'l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('minimization', 'Minimization & Dismissal', 'Identifies attempts to downplay concerns, feelings, or events', 'negative', 'manipulation', 75, ARRAY['f'::mcl_factor, 'j'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('threats_intimidation', 'Threats & Intimidation', 'Detects explicit or implicit threats, ultimatums, and intimidating language', 'negative', 'control', 95, ARRAY['j'::mcl_factor, 'l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('isolation_tactics', 'Isolation Tactics', 'Identifies attempts to separate victim from support systems', 'negative', 'control', 85, ARRAY['j'::mcl_factor, 'k'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('financial_control', 'Financial Control', 'Detects financial manipulation and economic abuse patterns', 'negative', 'control', 80, ARRAY['c'::mcl_factor, 'j'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('emotional_blackmail', 'Emotional Blackmail', 'Identifies FOG tactics (Fear, Obligation, Guilt)', 'negative', 'manipulation', 85, ARRAY['f'::mcl_factor, 'j'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('stonewalling', 'Stonewalling & Silent Treatment', 'Detects withdrawal, refusal to communicate, and silent treatment patterns', 'negative', 'control', 70, ARRAY['f'::mcl_factor, 'k'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('parental_alienation', 'Parental Alienation', 'Identifies attempts to damage child-parent relationships', 'negative', 'custody', 95, ARRAY['i'::mcl_factor, 'j'::mcl_factor, 'k'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('projection', 'Projection', 'Detects accusations that mirror the accuser''s own behavior', 'negative', 'manipulation', 75, ARRAY['j'::mcl_factor, 'l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('darvo', 'DARVO (Deny, Attack, Reverse Victim/Offender)', 'Detects the three-stage pattern of denying wrongdoing, attacking the accuser, and reversing victim/offender roles', 'negative', 'manipulation', 95, ARRAY['j'::mcl_factor, 'l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('overelaboration', 'Overelaboration', 'Detects excessive detail about location, timing, and justifications that may indicate deception', 'negative', 'deception', 70, ARRAY['l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('medical_abuse', 'Medical Abuse', 'Identifies weaponization of medication, diagnoses, and mental health status for control', 'negative', 'control', 95, ARRAY['f'::mcl_factor, 'j'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('reproductive_coercion', 'Reproductive Coercion', 'Detects attempts to control reproductive choices, pregnancy as trap, contraception interference', 'negative', 'control', 100, ARRAY['j'::mcl_factor, 'l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('power_asymmetry', 'Power Asymmetry', 'Tracks power dynamics through victim deference vs abuser directives', 'neutral', 'dynamics', 60, ARRAY['j'::mcl_factor, 'l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('love_bombing', 'Love Bombing', 'Identifies excessive flattery, premature declarations of love, and overwhelming affection', 'positive', 'affection', 80, ARRAY['l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('future_faking', 'Future Faking', 'Detects grandiose promises about the future that may not be fulfilled', 'positive', 'promises', 75, ARRAY['l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('affirmations', 'Positive Affirmations', 'Tracks genuine-seeming compliments and supportive statements', 'positive', 'affection', 50, '{}'::mcl_factor[], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('apologies', 'Apologies & Remorse', 'Identifies apologies and expressions of remorse (to track sincerity over time)', 'positive', 'reconciliation', 60, ARRAY['l'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('gift_giving', 'Gift Giving & Generosity', 'Tracks mentions of gifts, financial generosity, and material expressions of love', 'positive', 'affection', 55, ARRAY['c'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('scheduling', 'Scheduling & Custody', 'Identifies discussions about custody schedules, visitation, and parenting time', 'neutral', 'logistics', 40, ARRAY['a'::mcl_factor, 'b'::mcl_factor, 'd'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('child_wellbeing', 'Child Wellbeing Mentions', 'Tracks references to children''s health, education, and emotional state', 'neutral', 'children', 50, ARRAY['a'::mcl_factor, 'b'::mcl_factor, 'e'::mcl_factor, 'g'::mcl_factor], FALSE, 'pattern-analyzer.ts BUILT_IN_MODULES') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('guilt_trip', 'Guilt-Tripping', 'Inducing guilt for control', 'negative', 'manipulation', 50, '{}'::mcl_factor[], TRUE, 'RESEARCH_BEHAVIORAL_ANALYSIS.md (taxonomy table; indicator phrases only)') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('boundary_violation', 'Boundary Violations', 'Ignoring stated limits', 'negative', 'control', 50, '{}'::mcl_factor[], TRUE, 'RESEARCH_BEHAVIORAL_ANALYSIS.md (taxonomy table; indicator phrases only)') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('triangulation', 'Triangulation', 'Using third parties to manipulate', 'negative', 'manipulation', 50, '{}'::mcl_factor[], TRUE, 'RESEARCH_BEHAVIORAL_ANALYSIS.md (taxonomy table; indicator phrases only)') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('word_salad', 'Word Salad', 'Circular, confusing communication to exhaust or evade', 'negative', 'manipulation', 50, '{}'::mcl_factor[], TRUE, 'RESEARCH_BEHAVIORAL_ANALYSIS.md (taxonomy table; indicator phrases only)') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('hoovering', 'Hoovering', 'Pulling the target back in after conflict or discard', 'positive', 'manipulation', 50, '{}'::mcl_factor[], TRUE, 'RESEARCH_BEHAVIORAL_ANALYSIS.md (taxonomy table; indicator phrases only)') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;
INSERT INTO analysis.analysis_module (id, name, description, polarity, subcategory, weight, mcl_factors, needs_review, provenance) VALUES ('intermittent_reinforcement', 'Intermittent Reinforcement', 'Unpredictable rewards amid mistreatment to keep the target off-balance', 'positive', 'manipulation', 50, '{}'::mcl_factor[], TRUE, 'RESEARCH_BEHAVIORAL_ANALYSIS.md (taxonomy table; indicator phrases only)') ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, description = EXCLUDED.description, polarity = EXCLUDED.polarity, subcategory = EXCLUDED.subcategory, weight = EXCLUDED.weight, mcl_factors = EXCLUDED.mcl_factors, needs_review = EXCLUDED.needs_review, provenance = EXCLUDED.provenance;

-- ---- Indicator phrases ----
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'that never happened') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'you''re imagining things') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'you''re crazy') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'you''re being paranoid') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'you''re too sensitive') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'you''re overreacting') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'i never said that') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'you''re making things up') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'that''s not what happened') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'you have a bad memory') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'no one else thinks that') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'everyone agrees with me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'you''re the only one who') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'you always twist things') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('gaslighting', 'you''re delusional') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'this is your fault') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'you made me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'if you hadn''t') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'because of you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'you started it') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'look what you made me do') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'you drove me to') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'you pushed me to') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'this wouldn''t happen if you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'you bring out the worst') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'you''re the reason') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('blame_shifting', 'it''s because you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'it''s not a big deal') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'you''re blowing this out of proportion') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'it wasn''t that bad') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'get over it') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'move on already') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'stop dwelling') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'it''s in the past') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'let it go') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'you''re making a mountain') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'calm down') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'relax') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'chill out') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'it''s nothing') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('minimization', 'don''t be dramatic') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'you''ll regret') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'you''ll be sorry') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'i''ll make sure') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'you''ll never see') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'i''ll take the kids') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'i''ll destroy') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'i''ll ruin') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'you''ll pay for') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'watch what happens') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'don''t test me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'you don''t want to') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'i''ll tell everyone') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'i''ll expose') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'you''ll lose everything') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('threats_intimidation', 'or else') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'your family is toxic') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'your friends don''t care') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'they''re using you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'they''re against us') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'you don''t need them') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'i''m the only one') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'no one understands you like i do') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'they''re jealous') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'they''re trying to break us up') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'you spend too much time with') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'choose me or them') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('isolation_tactics', 'it''s us against the world') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'after everything i''ve done') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'if you loved me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'you owe me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'i sacrificed') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'i gave up everything') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'how could you do this to me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'you''re hurting me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'you''re breaking my heart') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'i can''t live without') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'i''ll hurt myself') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'you''ll destroy me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('emotional_blackmail', 'i thought you cared') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'i''m not talking about this') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'conversation is over') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'i have nothing to say') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'talk to my lawyer') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'don''t contact me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'leave me alone') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'i''m done') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'whatever') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'fine') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'i don''t care') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('stonewalling', 'do what you want') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'your father doesn''t love') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'your mother doesn''t love') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'daddy doesn''t care') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'mommy doesn''t care') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'daddy doesn''t love') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'mommy doesn''t love') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'they abandoned') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'they chose') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'they don''t want to see you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'it''s their fault') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'they''re the bad guy') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'don''t tell them') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'our little secret') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'they''ll be mad at you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'they don''t understand') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('parental_alienation', 'you''re better off without') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('projection', 'you''re the one who') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('projection', 'you always') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('projection', 'you never') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('projection', 'you''re cheating') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('projection', 'you''re lying') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('projection', 'you''re manipulating') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('projection', 'you''re controlling') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('projection', 'you''re abusive') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('projection', 'you''re the narcissist') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('projection', 'you''re gaslighting me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'i never') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'i didn''t') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'that never happened') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'that''s not true') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re making that up') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'i would never') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'that''s a lie') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re crazy') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re lying') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re the abusive one') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re manipulating') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re gaslighting me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re toxic') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re the problem') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re unstable') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re delusional') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'i''m the victim here') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re attacking me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re abusing me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'i''m the one being hurt') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re hurting me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'i''m scared of you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'you''re the aggressor') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('darvo', 'i need protection from you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i''m at') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i''m still at') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i''m heading to') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i''ll be at') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i''m on my way to') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i just left') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i just arrived at') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i left at') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i''ll be back by') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i''ve been here since') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i''ll be done in') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i''m doing this because') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i had to') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i needed to') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'the reason is') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i''m just') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i was just') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'before you ask') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'i know you''re wondering') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'just so you know') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'for the record') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('overelaboration', 'to be clear') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you need your meds') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'did you take your pills') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you''re not thinking clearly') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'it''s the medication talking') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you can''t make decisions') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you''re not well enough') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'i''m holding your meds') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you can''t be trusted with') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you''re bipolar') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you''re borderline') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you''re schizophrenic') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'that''s your condition talking') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you''re having an episode') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you need to be hospitalized') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('medical_abuse', 'you''re unstable') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'i want you pregnant') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'you should get pregnant') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'stop taking birth control') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'i''ll get you pregnant') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'you can''t leave if you''re pregnant') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'a baby will fix us') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'you owe me a child') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'i sabotaged your birth control') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'i''ll take the baby') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'you''ll never see the baby') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'i''ll prove you''re unfit') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'you''re a bad mother') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('reproductive_coercion', 'the baby doesn''t need you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'if that''s okay') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'if you don''t mind') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'is that alright') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'sorry') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'my bad') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'i didn''t mean to') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'i apologize') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'i hope that''s fine') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'let me know if') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'where are you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'what are you doing') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'who are you with') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'come here') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'go there') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'do this') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'stop that') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'tell me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'show me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('power_asymmetry', 'prove it') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'you''re perfect') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'you''re my everything') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'i''ve never felt this way') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'you''re my soulmate') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'we''re meant to be') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'i can''t live without you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'you complete me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'you''re the best thing') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'i''ve never loved anyone like') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'you''re amazing') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'you''re incredible') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'i''m so lucky') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('love_bombing', 'you''re too good for me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'when we get married') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'when we have kids') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'i''m going to buy you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'we''ll travel the world') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'i''ll change') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'things will be different') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'i promise to') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'next time') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'soon we''ll') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'one day we''ll') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'i''ll make it up to you') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('future_faking', 'just wait until') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'i''m sorry') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'i apologize') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'please forgive me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'i was wrong') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'i made a mistake') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'i shouldn''t have') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'i regret') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'i feel terrible') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'i''ll do better') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'give me another chance') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('apologies', 'i didn''t mean to') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('guilt_trip', 'after everything i''ve done') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('guilt_trip', 'you don''t care about me') ON CONFLICT (module_id, phrase) DO NOTHING;
INSERT INTO analysis.pattern_phrase (module_id, phrase) VALUES ('triangulation', 'everyone thinks you''re') ON CONFLICT (module_id, phrase) DO NOTHING;

-- ---- Contradiction rules ----
INSERT INTO analysis.contradiction_rule (id, positive_module, negative_modules, description, provenance) VALUES ('love_bomb_devalue', 'love_bombing', ARRAY['gaslighting', 'blame_shifting', 'minimization', 'threats_intimidation'], 'Idealize->devalue proximity reversal (love-bombing followed by devaluation)', 'pattern-analyzer.ts detectContradictions') ON CONFLICT (id) DO UPDATE SET positive_module = EXCLUDED.positive_module, negative_modules = EXCLUDED.negative_modules, description = EXCLUDED.description, provenance = EXCLUDED.provenance;
INSERT INTO analysis.contradiction_rule (id, positive_module, negative_modules, description, provenance) VALUES ('promise_broken', 'future_faking', '{}', 'Promise -> broken commitment (requires temporal follow-up evidence)', 'RESEARCH_BEHAVIORAL_ANALYSIS.md contradiction logic') ON CONFLICT (id) DO UPDATE SET positive_module = EXCLUDED.positive_module, negative_modules = EXCLUDED.negative_modules, description = EXCLUDED.description, provenance = EXCLUDED.provenance;
INSERT INTO analysis.contradiction_rule (id, positive_module, negative_modules, description, provenance) VALUES ('apology_repeat', 'apologies', '{}', 'Apology -> repetition of the apologized-for behavior', 'RESEARCH_BEHAVIORAL_ANALYSIS.md contradiction logic') ON CONFLICT (id) DO UPDATE SET positive_module = EXCLUDED.positive_module, negative_modules = EXCLUDED.negative_modules, description = EXCLUDED.description, provenance = EXCLUDED.provenance;
INSERT INTO analysis.contradiction_rule (id, positive_module, negative_modules, description, provenance) VALUES ('affirmation_devaluation', 'affirmations', ARRAY['gaslighting', 'blame_shifting', 'minimization'], 'Affirmation -> devaluation reversal', 'RESEARCH_BEHAVIORAL_ANALYSIS.md contradiction logic') ON CONFLICT (id) DO UPDATE SET positive_module = EXCLUDED.positive_module, negative_modules = EXCLUDED.negative_modules, description = EXCLUDED.description, provenance = EXCLUDED.provenance;
