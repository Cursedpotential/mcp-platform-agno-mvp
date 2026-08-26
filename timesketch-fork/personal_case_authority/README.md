# personal_case_authority/

Fixture/interface-only scaffolding for the D-084/D-085 authority-state model
(candidate/context-only vs evidence-approved vs amendment-candidate) and the
ADR-0060 canonical timeline mapping contract. See `authority.py` module docstring
for the full explanation of what this is and is not.

Runtime-verified 2026-08-26: `from personal_case_authority import fixtures` imports
cleanly and all three fixtures construct without error (Python 3, stdlib only — no
dependency on Timesketch's own requirements, no DB, no network).

Not imported by any Timesketch code path. Not part of upstream. Isolated per
ADR-0060 so it never conflicts with an upstream re-pin.

**2026-08-26 (WP-E02):** `importer.py` added — the real PG->Timesketch projector
(`TimelineProjector`), reading `sql/0035_timeline_projection.sql`'s sealed generations and
importing them via upstream's own `OpenSearchDataStore.import_event`. Syntax-checked
(`ast.parse`) and cross-referenced against the real upstream import-event signature and the
live-verified PG schema; **not executed end-to-end** — no Timesketch/OpenSearch deployment
exists yet in this environment. See its module docstring and
`docs/reviews/2026-08-25-schema-audit/TIMESKETCH-WP-E02-IMPLEMENTATION-STATUS.md`.

Next packet that touches this: TS-04 (WP-F01) implements `CurationCommandSink` for real against
PostgreSQL. A future deployment packet (TS-08/WP-H02) provisions live Timesketch/OpenSearch and
proves `importer.py` end-to-end.
