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

## ATOMICITY — every unit must be assignable to a Temporal Activity

> _Owner directive · 2026-09-02. Binding on every directory below this file.
> Reinforces the 2026-08-25 boundary ruling, ADR-0061, and D-077._

**Write every unit of work so it can be handed to one Temporal Activity, and never
conflate multiple processes into one unit.**

Owner, 2026-09-02: *"Everything needs to be modular so that it can be assigned to
Temporal activities. We can't be conflating or mixing a bunch of processes into one.
Yes, the engine can call individual ones, but it's going to be calling the Activity
more likely than 99.9% of the time."* And: *"Or to be added into an n8n node which
gets run as an activity, however that shape looks."*

Rules, in force everywhere:

1. **One unit does one thing.** A parser parses and does nothing else (owner,
   2026-08-29: *"they parse, they do nothing more"*). A chunker chunks. A hasher
   hashes. If a function does two of those, it is wrong and must be split before it
   is wired to anything.
2. **Hashing is its own Activity family and is never folded into parsing, chunking,
   or normalization.** Custody hashing is separate machinery with its own boundary
   (D-077, four hash moments; see `docs/reference/HASH-TAXONOMY-2026-08-29.md`).
3. **The Activity is the normal caller.** Direct in-process calls stay legitimate —
   but the overwhelmingly common path is invocation *as*, or from *within*, a
   Temporal Activity. Design signatures for that: bounded inputs, bounded outputs,
   no ambient state, no hidden I/O, deterministic given its inputs, safely
   retryable. An Activity may be retried; anything that breaks on a second identical
   call is a defect.
4. **Three call shapes, one unit.** The same unit must serve all of them without
   knowing which is in play: (a) called directly in-process; (b) invoked as a
   Temporal Activity; (c) **wrapped as an n8n node that is itself executed as, or
   from within, an Activity.** n8n owns the visual flow, Temporal owns durability,
   the unit owns one job. A unit that needs to know its caller has a boundary
   violation in it.
5. **Pass references, never payloads.** Source bytes and bundles move by locator
   (`upload://`, `r2://`, sealed `file://`), never through Temporal history, an n8n
   payload, or a PostgreSQL activity request.
6. **No orchestration inside a unit.** Sequencing, fan-out, retries, and human gates
   belong to the workflow (`modules/engine/proffer` (formerly `uiw`, renamed D-140)) and to n8n's visual flow — never
   buried inside a parser, decoder, chunker, or repository method.
7. **New capability = new Activity, registered in the stage graph.** Do not widen an
   existing Activity to cover a second concern because it is convenient.

The test before adding or editing anything here: *could this be scheduled on its own,
retried, wrapped as an n8n node, and reasoned about in isolation?* If not, it is not
finished.

