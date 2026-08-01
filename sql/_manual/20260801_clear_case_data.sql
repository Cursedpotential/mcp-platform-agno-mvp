-- 20260801_clear_case_data.sql   — AS RUN, 2026-08-01 16:12
--
-- Byline: Claude Code · Opus 5 (1M) · 2026-08-01
--
-- MANUAL / OWNER-RUN, ALREADY EXECUTED. Kept out of sql/ numbering so a migration
-- runner can never replay it. This file was corrected after execution to match what
-- actually happened — the first draft was wrong in two ways, both discovered only by
-- running it (see "WHAT THE FIRST DRAFT GOT WRONG").
--
-- PURPOSE
--   Clear the re-derivable CASE DATA ahead of the full reprocess, preserving
--   everything that cannot be regenerated.
--
-- BACKUPS TAKEN BEFORE EXECUTION (both verified):
--   E:\AI_Workspace\_db_backups\20260801-pre-case-data-dump\   CSV, 18 tables, 10,694 rows
--   E:\AI_Workspace\_db_backups\20260801-pgdump\               pg_dump -Fc: ai (2.6M),
--       traceiq (12M), postgres, globals. PGDMP header verified, sha256 MANIFEST.json.
--
-- RESULT: 7,753 rows cleared. All preserved tables verified unchanged before COMMIT.
--
-- ============================================================================
-- WHAT THE FIRST DRAFT GOT WRONG
--
-- 1. analysis.human_label.message_id is the PRIMARY KEY, not merely an ON DELETE
--    CASCADE foreign key. The table had NO identity of its own, so clearing
--    analysis.message would not have orphaned the 1,918 hand-labelled rows — it
--    would have DELETED them. Dropping the FK alone was not enough; the primary key
--    had to be repointed onto a durable key first.
--
-- 2. evidence.source carries a write-once trigger enforcing the never-delete rule
--    ("DELETE blocked -> _stale"). The guard fired and stopped the run. It was NOT
--    worked around: the custody spine (evidence.source + evidence.evidence_hash) is
--    excluded instead.
-- ============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- STEP 1 — Give human_label its own identity. MUST precede any delete.
--
-- (conversation_key, seq) was verified UNIQUE across all 1,918 rows and becomes the
-- primary key. Content hash is NOT usable as identity — only 1,747 of 1,918 message
-- texts are distinct (duplicates like "ok"), so it collides.
--
-- The table already stores everything it needs to stand alone: conversation_key, seq,
-- occurred_at, who, message_text, labels, severity, notes, labeled_by.
-- ---------------------------------------------------------------------------

ALTER TABLE analysis.human_label DROP CONSTRAINT IF EXISTS human_label_message_id_fkey;
ALTER TABLE analysis.human_label DROP CONSTRAINT IF EXISTS human_label_pkey;
ALTER TABLE analysis.human_label ALTER COLUMN message_id DROP NOT NULL;

ALTER TABLE analysis.human_label
  ADD CONSTRAINT human_label_pkey PRIMARY KEY (conversation_key, seq);

ALTER TABLE analysis.human_label
  ADD COLUMN IF NOT EXISTS relink_status TEXT NOT NULL DEFAULT 'unlinked'
    CHECK (relink_status IN ('unlinked','linked','ambiguous'));

-- Existing message_id UUIDs are LEFT IN PLACE as a record of the prior link rather
-- than erased. relink_status is what tells a re-ingest they no longer resolve.
UPDATE analysis.human_label SET relink_status = 'unlinked';

COMMENT ON TABLE analysis.human_label IS
  'Owner-authored ground-truth labels. INDEPENDENT of analysis.message since '
  '2026-08-01: primary key repointed to (conversation_key, seq) and the ON DELETE '
  'CASCADE FK dropped. Previously message_id was BOTH the PK and a cascading FK, so '
  'clearing analysis.message would have deleted all 1918 rows outright. message_id is '
  'now a nullable historical pointer; relink_status tracks re-association after '
  're-ingest.';

-- ---------------------------------------------------------------------------
-- STEP 2 — Clear re-derivable case data, children before parents.
--
-- DELETE rather than TRUNCATE: TRUNCATE would need CASCADE, which is precisely the
-- behaviour that endangered human_label.
-- ---------------------------------------------------------------------------

DELETE FROM analysis.message_participant;   -- 3836
DELETE FROM analysis.message;               -- 1918
DELETE FROM analysis.normalized_record;     -- 1947
DELETE FROM analysis.conversation;          --    1
DELETE FROM analysis.corroboration_flag;    --    1
DELETE FROM analysis.workflow_run_stage;    --   40
DELETE FROM analysis.workflow_run;          --   10

-- ---------------------------------------------------------------------------
-- DELIBERATELY NOT CLEARED — the custody spine (32 rows).
--
--   evidence.source          write-once trigger enforces never-delete. Correct guard;
--                            not worked around.
--   evidence.evidence_hash   the H1/H2/H3 custody record for those sources. Removing
--                            hashes while their sources survive would leave the chain
--                            inconsistent, so both stay.
--
-- Re-ingest dedupes on sha256, and evidence.source already carries
-- supersedes_source_id / custody_status for exactly this situation.
--
-- ALSO PRESERVED — hand-built and human-authored, not regenerable:
--   analysis.human_label            1918
--   analysis.detection_pattern       527
--   analysis.behavior_category_mcl   225
--   analysis.behavior_category       164
--   analysis.pattern_lexicon          51
--   analysis.custody_factor           12
--   analysis.topic_code               10
--   analysis.detection_pattern_set     1
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- STEP 3 — Verify before committing. The runner asserted every KEPT count was
-- unchanged and every CLEARED table was empty, and would ROLLBACK otherwise.
-- ---------------------------------------------------------------------------

SELECT 'CLEARED (expect 0)' AS section, 'message_participant' AS t, count(*) FROM analysis.message_participant
UNION ALL SELECT 'CLEARED', 'message',            count(*) FROM analysis.message
UNION ALL SELECT 'CLEARED', 'normalized_record',  count(*) FROM analysis.normalized_record
UNION ALL SELECT 'CLEARED', 'conversation',       count(*) FROM analysis.conversation
UNION ALL SELECT 'CLEARED', 'workflow_run',       count(*) FROM analysis.workflow_run
UNION ALL SELECT 'KEPT (must be unchanged)', 'human_label', count(*) FROM analysis.human_label
UNION ALL SELECT 'KEPT', 'detection_pattern',     count(*) FROM analysis.detection_pattern
UNION ALL SELECT 'KEPT', 'behavior_category',     count(*) FROM analysis.behavior_category
UNION ALL SELECT 'KEPT', 'behavior_category_mcl', count(*) FROM analysis.behavior_category_mcl
UNION ALL SELECT 'KEPT', 'pattern_lexicon',       count(*) FROM analysis.pattern_lexicon
UNION ALL SELECT 'KEPT', 'custody_factor',        count(*) FROM analysis.custody_factor
UNION ALL SELECT 'KEPT', 'topic_code',            count(*) FROM analysis.topic_code
UNION ALL SELECT 'KEPT (custody spine)', 'evidence.source',   count(*) FROM evidence.source
UNION ALL SELECT 'KEPT (custody spine)', 'evidence_hash',     count(*) FROM evidence.evidence_hash
ORDER BY 1 DESC, 2;

-- human_label MUST read 1918. If it does not, ROLLBACK and restore from
-- E:\AI_Workspace\_db_backups\20260801-pgdump\ai_20260801.dump (pg_restore).

COMMIT;
