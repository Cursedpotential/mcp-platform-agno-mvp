# server/timeline/ — canonical timeline + Timesketch projection (WP-D01/D02/E02)

> Nested map. Parent: `../AGENTS.md`. Root: `../../AGENTS.md`.
> _Byline: Claude Code · Sonnet 5 · 2026-08-26_

## What's here

The physical realization of ADR-0060 / D-084 / D-085 for **schema + projector only**: canonical
timeline membership (WP-D01), immutable projection generations (WP-D02), and the PG-side half of
the PG→Timesketch projector (WP-E02). Migration: `sql/0035_timeline_projection.sql`.

| File | Role |
|---|---|
| `models.py` | Dataclasses mirroring the ADR-0060 canonical mapping contract (no DB access) |
| `hashing.py` | Canonical serialization + versioned, domain-tagged sha256 hashing |
| `db.py` | Lazy SQLAlchemy engine, separate from `server.core.session`'s heavier Agno stack |
| `generation.py` | `build_generation()` — the D02 builder: reads `timeline.timeline_member`, computes hashes/change-class, writes one immutable sealed generation, idempotent via `content_hash`-derived `idempotency_key` |
| `receipts.py` | Append-only receipt writer + the two manifest reads (R09/WP-H01 reconciliation surface) |
| `projector.py` | `PostgresTimelineProjectionSource.fetch_generation()` — the authenticated read interface the Timesketch-fork importer consumes |
| `cli.py` | `python -m server.timeline build-generation` / `show-manifest` |

## Scope boundary (do not expand without a new packet)

- **No curation/amendment commands.** `timeline_curation_batch/item`, `timeline_amendment_candidate`
  are WP-F01/F02 — not built here, not imported here.
- **No Timesketch/OpenSearch write.** That lives in
  `timesketch-fork/personal_case_authority/importer.py` (a separate application/dependency
  graph) and consumes `PostgresTimelineProjectionSource` by shape, not by import.
- **No `evidence_approved` auto-resolution.** WP-C02 (context-to-evidence promotion) and WP-B01
  (typed extraction fan-out) are themselves blocked upstream; `generation.py`'s
  `GOVERNED_SOURCE_RESOLVERS` registry is the explicit, code-reviewed extension point for when
  R00 names the real governed source table(s) — no dynamic SQL against a data-supplied table name.
- **No route mount.** `server/api/main.py` is out of this packet's file boundary; `cli.py` is the
  operable interface until a later packet wires an HTTP route.

## Dependency direction

Imports `server.contracts`-style light deps only: `server.core.url` (for `db_url`) and
SQLAlchemy. Does **not** import `server.evidence`, `server.agents`, or `server.api` — timeline
projection reads a generic polymorphic pointer into governed sources, never those packages'
internals directly (see `sql/0035_timeline_projection.sql`'s header for why).

## Relevant docs

- ADR-0060 — the Timesketch fork decision this package physically implements
- `docs/reviews/2026-08-25-schema-audit/TIMESKETCH-FORK-CURATION-HANDOFF.md` — the full contract (TS-00..TS-08)
- `docs/reviews/2026-08-25-schema-audit/reconciliation-domains/R09-cross-store-reconciliation.md` — the reconciliation lane this package's receipts/manifests feed
- `docs/reviews/2026-08-25-schema-audit/TIMESKETCH-WP-E02-IMPLEMENTATION-STATUS.md` — this packet's own status/handoff
