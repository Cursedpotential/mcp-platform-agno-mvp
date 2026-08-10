"""Generate the transaction-rollback validation harness for sql/0016_working_gate_layer.sql.

The harness is the migration verbatim, with its trailing COMMIT replaced by
probes and a ROLLBACK, so what is tested is exactly what would be applied.

Run:  uv run --no-sync python sql/validation/gen_validate_0016.py
Then: ssh <db-host> "docker exec -i <pg-container> psql -U ai -d ai" \
        < sql/validation/validate_0016_working_gate_layer.sql

Byline: Claude Code - Opus 5 - 2026-08-01
RETARGETED 2026-08-09 (handoff S3f/[S3f]): this file was drafted against
sql/0008_working_schema.sql, which collided with the applied
0008_temporal_clocks_and_provenance.sql and was renumbered to
sql/0016_working_gate_layer.sql on 2026-08-02 (see 0016:4-17 for the
renumbering history; the design is unchanged). Retargeted here — MIGRATION/
OUT below now point at 0016, and the probes' content_sha256 literals were
widened from short hex strings to full 32-byte values because 0016 tightened
candidate_entity/candidate_fact/candidate_event.content_sha256 from TEXT to
`BYTEA NOT NULL CHECK (octet_length(content_sha256) = 32)`. Every other
probe/assertion below still holds verbatim against 0016's actual DDL
(verified structurally + by a scratch-container run, 2026-08-09).
"""

import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
MIGRATION = REPO / "sql" / "0016_working_gate_layer.sql"
OUT = REPO / "sql" / "validation" / "validate_0016_working_gate_layer.sql"

PROBES = r"""
-- ===========================================================================
-- VALIDATION HARNESS - generated, do not hand-edit.
-- Everything above this line is sql/0016_working_gate_layer.sql verbatim, minus
-- its trailing COMMIT. Everything below probes it and then ROLLS BACK, so a
-- run against production writes nothing.
-- ===========================================================================

\echo '=== OBJECTS in working ==='
SELECT table_name, table_type FROM information_schema.tables
 WHERE table_schema = 'working' ORDER BY table_type, table_name;

\echo '=== INDEX / CHECK COUNTS ==='
SELECT (SELECT count(*) FROM pg_indexes WHERE schemaname='working') AS indexes,
       (SELECT count(*) FROM pg_constraint c JOIN pg_namespace n ON n.oid=c.connamespace
         WHERE n.nspname='working' AND c.contype='c') AS check_constraints;

\echo '=== SMOKE: happy path ==='
INSERT INTO working.extraction_run (extractor, extractor_version, source_summary)
VALUES ('probe','0.0.0','validation only') RETURNING id AS run_id \gset

INSERT INTO working.source_provenance
  (source_raw_table, source_raw_id, occurred_at, export_created_at, acquired_at,
   ingested_at, realized_at, realized_at_state, realized_at_source,
   acquisition_method, acquisition_authority, source_device, device_custodian, asserted_by)
VALUES ('evidence.raw_sms','1',
        now() - interval '3 years', now() - interval '2 years',
        now() - interval '1 year',  now() - interval '11 months',
        now() - interval '6 months', 'confirmed', 'ai-chat 2026-02-11 line 88',
        'household_device','parent_guardian','hand-me-down phone','daughter','owner');

INSERT INTO working.candidate_entity
  (extraction_run_id, source_raw_table, source_raw_id, entity_type, name,
   normalized_name, confidence, content_sha256)
VALUES (:'run_id','evidence.raw_sms','1','person','Probe Person','probe person',0.9,
        decode(repeat('ab',32),'hex'))
RETURNING id AS ent_id \gset

INSERT INTO working.candidate_event
  (extraction_run_id, source_raw_table, source_raw_id, event_type, summary,
   occurred_at, validity, content_sha256, primary_entity_id)
VALUES (:'run_id','evidence.raw_sms','1','contact','probe event', now(),
        tstzrange(now() - interval '1 day', now(), '[)'), decode(repeat('cd',32),'hex'), :'ent_id');

SELECT kind, label, review_state FROM working.review_queue ORDER BY kind;

\echo '--- knowledge_gap: the delta between sent and understood ---'
SELECT source_raw_id, justify_interval(gap) AS gap, acquisition_method,
       acquisition_authority, producible FROM working.knowledge_gap;

\echo '--- current_provenance returns the NEWEST revision ---'
INSERT INTO working.source_provenance
  (source_raw_table, source_raw_id, revision, occurred_at, acquired_at,
   realized_at, realized_at_state, acquisition_authority, asserted_by, acquisition_notes)
VALUES ('evidence.raw_sms','1', 2, now() - interval '3 years', now() - interval '1 year',
        now() - interval '5 months','corrected','unclear','owner','authority reconsidered');
SELECT revision, realized_at_state, acquisition_authority
  FROM working.current_provenance WHERE source_raw_id = '1';

\set ON_ERROR_STOP off

\echo '--- NEG 1: promote without approval ---'
SAVEPOINT n1;
UPDATE working.candidate_entity SET promoted_at = now(),
       promoted_to_table='analysis.entity', promoted_to_id='x' WHERE id = :'ent_id';
ROLLBACK TO SAVEPOINT n1;

\echo '--- NEG 2: half-complete promotion ---'
SAVEPOINT n2;
UPDATE working.candidate_entity SET review_state='approved' WHERE id = :'ent_id';
UPDATE working.candidate_entity SET promoted_at = now() WHERE id = :'ent_id';
ROLLBACK TO SAVEPOINT n2;

\echo '--- NEG 3: event with no time at all ---'
SAVEPOINT n3;
INSERT INTO working.candidate_event
  (extraction_run_id, source_raw_table, source_raw_id, event_type, summary, content_sha256)
VALUES (:'run_id','evidence.raw_sms','2','contact','no time given', decode(repeat('ef',32),'hex'));
ROLLBACK TO SAVEPOINT n3;

\echo '--- NEG 4: duplicate candidate ---'
SAVEPOINT n4;
INSERT INTO working.candidate_entity
  (extraction_run_id, source_raw_table, source_raw_id, entity_type, name,
   normalized_name, content_sha256)
VALUES (:'run_id','evidence.raw_sms','1','person','Probe Person','probe person',
        decode(repeat('ab',32),'hex'));
ROLLBACK TO SAVEPOINT n4;

\echo '--- NEG 5: acquired BEFORE the export was taken ---'
SAVEPOINT n5;
INSERT INTO working.source_provenance
  (source_raw_table, source_raw_id, export_created_at, acquired_at, asserted_by)
VALUES ('evidence.raw_sms','99', now(), now() - interval '1 year','owner');
ROLLBACK TO SAVEPOINT n5;

\echo '--- NEG 6: realized BEFORE acquired ---'
SAVEPOINT n6;
INSERT INTO working.source_provenance
  (source_raw_table, source_raw_id, acquired_at, realized_at, realized_at_state, asserted_by)
VALUES ('evidence.raw_sms','98', now(), now() - interval '1 year','confirmed','owner');
ROLLBACK TO SAVEPOINT n6;

\echo '--- NEG 7: realized_at set but state left unset ---'
SAVEPOINT n7;
INSERT INTO working.source_provenance
  (source_raw_table, source_raw_id, realized_at, asserted_by)
VALUES ('evidence.raw_sms','97', now(),'owner');
ROLLBACK TO SAVEPOINT n7;

\echo '--- NEG 8: provenance asserted by a MODEL, not a human ---'
SAVEPOINT n8;
INSERT INTO working.source_provenance
  (source_raw_table, source_raw_id, asserted_by, asserted_by_kind)
VALUES ('evidence.raw_sms','96','nemotron-extractor','model');
ROLLBACK TO SAVEPOINT n8;

\echo '--- POSITIVE: approve, then promote into BOTH passes ---'
SAVEPOINT p1;
UPDATE working.candidate_entity
   SET review_state='approved', promoted_at=now(),
       promoted_to_table='analysis.entity', promoted_to_id='abc' WHERE id = :'ent_id';
INSERT INTO working.review_decision (candidate_kind, candidate_id, decision, reviewer, prior_state)
VALUES ('entity', :'ent_id','approved','owner','pending');
INSERT INTO working.promotion (candidate_kind, candidate_id, lane, target_system, target_ref, promoted_by)
VALUES ('entity', :'ent_id','hindsight','semantica_graph','node:123','owner'),
       ('entity', :'ent_id','as_lived','graphiti_memory','ep:456','owner'),
       ('entity', :'ent_id','consolidated','surrealdb','entity:789','owner'),
       ('entity', :'ent_id','support','weaviate','uuid:abc','owner');
SELECT lane, target_system FROM working.promotion ORDER BY lane;

\echo '--- NEG 9: hindsight material routed into the AS-LIVED lane ---'
SAVEPOINT n9;
INSERT INTO working.promotion (candidate_kind, candidate_id, lane, target_system, target_ref, promoted_by)
VALUES ('entity', :'ent_id','hindsight','graphiti_memory','ep:999','owner');
ROLLBACK TO SAVEPOINT n9;

\echo '--- NEG 10: as_lived sent to the hindsight graph ---'
SAVEPOINT n10;
INSERT INTO working.promotion (candidate_kind, candidate_id, lane, target_system, target_ref, promoted_by)
VALUES ('entity', :'ent_id','as_lived','semantica_graph','node:999','owner');
ROLLBACK TO SAVEPOINT n10;

\echo '--- NEG 11: duplicate live promotion, same lane + target ---'
SAVEPOINT n11;
INSERT INTO working.promotion (candidate_kind, candidate_id, lane, target_system, target_ref, promoted_by)
VALUES ('entity', :'ent_id','as_lived','graphiti_memory','ep:dup','owner');
ROLLBACK TO SAVEPOINT n11;

\echo '--- NEG 12: promotion with no lane at all ---'
SAVEPOINT n12;
INSERT INTO working.promotion (candidate_kind, candidate_id, target_system, target_ref, promoted_by)
VALUES ('entity', :'ent_id','postgres','row:1','owner');
ROLLBACK TO SAVEPOINT n12;
\set ON_ERROR_STOP on

\echo '=== ROLLING BACK EVERYTHING ==='
ROLLBACK;

\echo '=== POST-ROLLBACK: 0016''s own tables must be GONE (schema predates it, from 0014) ==='
-- Retargeting note: the old 0008 draft created `working` fresh in its own
-- transaction, so rollback removed the whole schema. 0016 runs AFTER 0014
-- (which owns the schema and extraction_candidate/record_observation), so a
-- correct rollback leaves the schema and 0014's tables in place and removes
-- only what 0016 itself added.
SELECT count(*) AS gate_layer_tables_after_rollback
  FROM information_schema.tables
 WHERE table_schema = 'working'
   AND table_name IN ('extraction_run','source_provenance','candidate_entity',
                       'candidate_fact','candidate_event','review_decision','promotion');
"""


def main() -> int:
    src = MIGRATION.read_text(encoding="utf-8").rstrip()
    if not src.endswith("COMMIT;"):
        print("ERROR: migration does not end with COMMIT; refusing to generate", file=sys.stderr)
        return 1
    OUT.write_text(src[: -len("COMMIT;")] + PROBES, encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO)} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
