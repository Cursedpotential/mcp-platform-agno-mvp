-- 20260801_clear_case_data.sql
--
-- Byline: Claude Code · Opus 5 (1M) · 2026-08-01
--
-- MANUAL / OWNER-RUN. Not a numbered migration — this is a one-off data operation,
-- deliberately kept out of sql/ so a migration runner can never replay it.
--
-- PURPOSE
--   Clear the re-derivable CASE DATA ahead of the full reprocess, while preserving
--   everything that cannot be regenerated.
--
-- PRECONDITION — ALREADY DONE 2026-08-01:
--   Full backup of all 18 non-empty tables (10,694 rows) at
--     E:\AI_Workspace\_db_backups\20260801-pre-case-data-dump\
--   with MANIFEST.json. Verify it exists before running this.
--
-- *** THE HAZARD THIS SCRIPT EXISTS TO AVOID ***
--   analysis.human_label has an ON DELETE CASCADE foreign key to analysis.message.
--   Deleting from analysis.message WITHOUT first dropping that constraint SILENTLY
--   DESTROYS all 1,918 hand-labelled ground-truth rows — the gold set built after
--   both detection passes over-flagged. It cannot be regenerated. Step 1 below is
--   therefore mandatory and must run BEFORE any delete.
--
-- WHAT IS PRESERVED (do not touch):
--   analysis.human_label            1918   owner-authored ground truth
--   analysis.detection_pattern       527   detection pattern library
--   analysis.behavior_category_mcl   225   behaviour -> MCL factor mapping
--   analysis.behavior_category       164   behavioural ontology
--   analysis.pattern_lexicon          51
--   analysis.custody_factor           12
--   analysis.topic_code               10
--   analysis.detection_pattern_set     1
--
-- WHAT IS CLEARED (all re-derivable from the original exports):
--   analysis.message_participant    3836
--   analysis.normalized_record      1947
--   analysis.message                1918
--   analysis.workflow_run_stage       40
--   evidence.evidence_hash            29
--   analysis.workflow_run             10
--   evidence.source                    3
--   analysis.conversation              1
--   analysis.corroboration_flag        1
--
-- Run inside the transaction. Inspect the final counts BEFORE you COMMIT.

BEGIN;

-- ---------------------------------------------------------------------------
-- STEP 1 — Make human_label independent. MUST run before any delete.
--
-- human_label already stores everything it needs to stand alone: conversation_key,
-- seq, occurred_at, who, message_text, labels, severity, notes, labeled_by. The
-- message_id column is a convenience pointer, not the identity.
--
-- (conversation_key, seq) was verified UNIQUE across all 1918 rows and is the
-- durable re-link key. NOTE: content hash is NOT usable as the key — only 1747 of
-- 1918 message texts are distinct (duplicates like "ok"), so it would collide.
-- ---------------------------------------------------------------------------

ALTER TABLE analysis.human_label
  DROP CONSTRAINT IF EXISTS human_label_message_id_fkey;

ALTER TABLE analysis.human_label
  ADD COLUMN IF NOT EXISTS relink_status TEXT NOT NULL DEFAULT 'unlinked'
    CHECK (relink_status IN ('unlinked','linked','ambiguous'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_human_label_durable
  ON analysis.human_label(conversation_key, seq);

COMMENT ON TABLE analysis.human_label IS
  'Owner-authored ground-truth labels. INDEPENDENT of analysis.message: stores its own '
  'message_text, conversation_key, seq, occurred_at and who, so it survives any rebuild '
  'of the message tables. The ON DELETE CASCADE FK to analysis.message was DROPPED '
  '2026-08-01 - it would have silently deleted all 1918 rows on a case-data clear. '
  'Durable key is (conversation_key, seq), verified unique. message_id is a convenience '
  'pointer only, re-established after re-ingest; relink_status tracks that.';

-- Clear the now-dangling convenience pointers. The labels themselves are untouched.
UPDATE analysis.human_label
   SET message_id = NULL,
       relink_status = 'unlinked';

-- ---------------------------------------------------------------------------
-- STEP 2 — Clear case data, children before parents.
-- DELETE rather than TRUNCATE: TRUNCATE ignores per-row FK checks and would need
-- CASCADE, which is exactly the behaviour that endangered human_label.
-- ---------------------------------------------------------------------------

DELETE FROM analysis.message_participant;
DELETE FROM analysis.message;
DELETE FROM analysis.normalized_record;
DELETE FROM analysis.conversation;
DELETE FROM analysis.corroboration_flag;
DELETE FROM analysis.workflow_run_stage;
DELETE FROM analysis.workflow_run;
DELETE FROM evidence.evidence_hash;
DELETE FROM evidence.source;

-- ---------------------------------------------------------------------------
-- STEP 3 — Verify BEFORE committing. Expected: first block all 0, second block
-- unchanged at the counts shown in the header.
-- ---------------------------------------------------------------------------

SELECT 'CLEARED (expect 0)' AS section, 'message_participant' AS t, count(*) FROM analysis.message_participant
UNION ALL SELECT 'CLEARED', 'message',            count(*) FROM analysis.message
UNION ALL SELECT 'CLEARED', 'normalized_record',  count(*) FROM analysis.normalized_record
UNION ALL SELECT 'CLEARED', 'conversation',       count(*) FROM analysis.conversation
UNION ALL SELECT 'CLEARED', 'workflow_run',       count(*) FROM analysis.workflow_run
UNION ALL SELECT 'CLEARED', 'evidence_hash',      count(*) FROM evidence.evidence_hash
UNION ALL SELECT 'CLEARED', 'source',             count(*) FROM evidence.source
UNION ALL SELECT 'KEPT (must be unchanged)', 'human_label',      count(*) FROM analysis.human_label
UNION ALL SELECT 'KEPT', 'detection_pattern',     count(*) FROM analysis.detection_pattern
UNION ALL SELECT 'KEPT', 'behavior_category',     count(*) FROM analysis.behavior_category
UNION ALL SELECT 'KEPT', 'behavior_category_mcl', count(*) FROM analysis.behavior_category_mcl
UNION ALL SELECT 'KEPT', 'pattern_lexicon',       count(*) FROM analysis.pattern_lexicon
UNION ALL SELECT 'KEPT', 'custody_factor',        count(*) FROM analysis.custody_factor
UNION ALL SELECT 'KEPT', 'topic_code',            count(*) FROM analysis.topic_code
ORDER BY 1 DESC, 2;

-- human_label MUST read 1918. If it does not, ROLLBACK immediately and restore from
-- E:\AI_Workspace\_db_backups\20260801-pre-case-data-dump\analysis.human_label.csv

-- COMMIT;     -- <-- uncomment and run once the counts above look right
-- ROLLBACK;   -- <-- otherwise
