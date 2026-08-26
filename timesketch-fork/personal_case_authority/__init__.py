"""Personal-case authority-state scaffolding (WP-E01, fixture/interface-only).

This package is an **isolated extension module** (ADR-0060: "isolating your changes
in new modules ... instead of rewriting core files") added on top of the pinned
upstream `google/timesketch` snapshot. It does not modify any upstream file and is
not imported by any upstream code path — nothing here runs unless a later packet
explicitly wires it in.

Scope, deliberately narrow for WP-E01:

- ``authority.py`` types the D-084/D-085 authority-state model (candidate/context-only
  vs evidence-approved vs amendment-candidate) and the ADR-0060 canonical timeline
  mapping contract (``display_at_utc``, ``display_summary``, stable source IDs,
  temporal uncertainty, authority/verification/dispute/privacy flags, projection
  generation/hash) as plain dataclasses and enums.
- ``fixtures.py`` provides one example instance per authority state so later packets
  (TS-05 fork UI, TS-06 re-review) have something concrete to render/test against
  before TS-03's real PostgreSQL projector exists.
- ``importer.py`` (added WP-E02, 2026-08-26) is the REAL TS-03/WP-E02 projector: reads a
  sealed PostgreSQL generation (``sql/0035_timeline_projection.sql``, validated live in a
  rollback transaction by ``server/timeline/``'s test suite), maps each member through the
  ADR-0060 contract into an upstream ``OpenSearchDataStore.import_event`` call with a
  deterministic doc id, and appends a PG receipt per member. UNEXECUTED end-to-end (no live
  Timesketch/OpenSearch deployed this session) -- see its own module docstring and
  ``docs/reviews/2026-08-25-schema-audit/TIMESKETCH-WP-E02-IMPLEMENTATION-STATUS.md``.

What this package explicitly is NOT:

- Not a database layer for ``authority.py``/``fixtures.py`` specifically -- those two stay
  fixture/interface-only, no PostgreSQL connection, no OpenSearch client, no ORM. Fields mirror
  the ADR-0060 contract's *names*, not any live schema -- final column names are frozen by R00,
  not here (per SEMANTIC-AGENT-WORK-PACKAGES.md: "Final schema names require R00 review and
  forward migrations; this handoff freezes responsibilities and authority, not spelling").
  ``importer.py`` is the exception: it IS the real database/OpenSearch layer, deliberately kept
  in its own file so the two fixture modules stay trivially importable with zero dependencies.
- ``CurationCommandSink`` in ``authority.py`` is still ``typing.Protocol``-only -- TS-04
  (WP-F01) implements it for real against PostgreSQL; nothing in this package writes curation
  commands yet.
"""
