# WP-D01 / WP-D02 / WP-E02 — Canonical PostgreSQL timeline + PG→Timesketch projector: implementation status

> _Byline: Claude Code · Sonnet 5 · 2026-08-26_
> Closes (partially): [WP-D01, WP-D02, WP-E02](SEMANTIC-AGENT-WORK-PACKAGES.md) ·
> Governing: ADR-0060, D-084, D-085, `TIMESKETCH-FORK-CURATION-HANDOFF.md`,
> `TIMESKETCH-FORK-WP-E01-HANDOFF.md`, `reconciliation-domains/R09-cross-store-reconciliation.md`

## Status: PG schema + generation builder + projector + receipts built and live-verified (rollback-scoped); Timesketch-side importer written and syntax/contract-checked, UNEXECUTED

Scoped packet: "the enforceable D01/D02/E02 foundation" only — immutable PG timeline projection
generations, ordered membership, stable candidate/governed identity, membership/content hashes,
explicit temporal/uncertainty fields, non-null idempotency identity, an authenticated projector
interface, stable Timesketch/OpenSearch document IDs, core-vs-annotation change classification,
replay-safe import, and read-back receipts sufficient for a later R09 reconciliation. **UI and
curation/amendment commands (WP-F01/F02/F03) are explicitly out of scope and were not built.**

## Changed / added files

| Path | What |
|---|---|
| `sql/0035_timeline_projection.sql` | New migration: `timeline` schema — `event_candidate`, `timeline_collection`, `timeline_member`, `timeline_projection_generation`, `timeline_projection_activation`, `timeline_projection_member`, `timeline_projection_receipt`, two manifest/status views, three NOLOGIN roles (`timeline_writer`/`timeline_projector`/`timeline_reader`), default-deny grants, append-only/immutability triggers |
| `server/timeline/__init__.py`, `AGENTS.md`, `db.py`, `hashing.py`, `models.py`, `generation.py`, `projector.py`, `receipts.py`, `cli.py` | New package: the D02 generation builder, the E02 authenticated read/projector interface, the receipt/manifest surface, and `python -m server.timeline` |
| `timesketch-fork/personal_case_authority/importer.py` | New: the real Timesketch-side TS-03/WP-E02 consumer (`TimelineProjector`) — maps PG generation members to `OpenSearchDataStore.import_event` calls with deterministic doc ids, appends PG receipts |
| `timesketch-fork/personal_case_authority/__init__.py`, `README.md` | Modified: doc-drift correction now that `importer.py` exists (was previously described as entirely fixture/interface-only) |
| `tests/test_timeline_projection.py` | New: 15 unit tests (hashing/serialization/pure projection logic) + 4 `@pytest.mark.integration` live rollback-transaction tests |
| `docs/reviews/2026-08-25-schema-audit/SEMANTIC-AGENT-WORK-PACKAGES.md` | Modified: WP-D01/D02/E02 status rows + one immediate-TODO checkbox |
| `docs/reviews/2026-08-25-schema-audit/TIMESKETCH-WP-E02-IMPLEMENTATION-STATUS.md` | This file |

No file outside this list was touched. No applied migration was edited; `0034` was left
untouched/unrenumbered as directed.

## Design notes (what a reviewer needs to know before reading the code)

- **`event_candidate` is deliberately un-FK'd to any specific producer table.** WP-B01 (typed
  AI-chat fan-out) and WP-C02 (context-to-evidence promotion) are themselves listed as "Blocked
  by physical design" in `SEMANTIC-AGENT-WORK-PACKAGES.md` as of this packet. Rather than guess
  their eventual shape, `event_candidate` carries a bounded, generic source envelope
  (`source_system`/`source_record_id`/`source_record_version`/`source_locator jsonb`) any future
  producer can populate without a schema change.
- **`timeline_member`'s `evidence_approved` branch is a polymorphic pointer**
  (`governed_source_schema`/`table`/`pk`), not an FK to `analysis.timeline_event` or any other
  specific table — which table(s) actually qualify as "evidence-approved" is an R00/C02 decision
  this packet does not presume. `server/timeline/generation.py`'s `GOVERNED_SOURCE_RESOLVERS`
  registry is the explicit, code-reviewed extension point for wiring a real one in later; today
  it is empty, so `evidence_approved` members are reported back in
  `GenerationResult.skipped_unresolved_governed_members`, never silently dropped or guessed at.
  This is a genuine limitation of this packet, not a bug: **only `candidate_context` members are
  currently projectable end-to-end**, because nothing upstream produces `evidence_approved` rows
  yet.
- **Immutability is trigger-enforced, not comment-enforced**, mirroring `sql/0017_append_only_guards.sql`'s
  pattern: `event_candidate`, `timeline_projection_member`, `timeline_projection_receipt`, and
  `timeline_projection_activation` reject every UPDATE/DELETE; `timeline_projection_generation`
  allows exactly one legal UPDATE shape (supersede-only, mirroring 0017's `promotion_revoke_only`).
- **Idempotency is real, not documentation.** `timeline_projection_generation.idempotency_key` is
  `NOT NULL UNIQUE` and deterministic from `content_hash` (`gen:<content_hash>`); `build_generation()`
  looks up an existing row by that key before inserting, so a repeated build with an unchanged
  member set returns the prior generation (`created=False`) instead of a duplicate — proven live
  in `test_live_build_generation_idempotent_and_supersedes_prior`.
- **Stable IDs are replay-safe by construction.** `stable_member_id` is the `timeline_member.id`
  itself (already permanent — the table's own trigger forbids repointing a member's source once
  created); `opensearch_doc_id` is a versioned sha256 of that id, never of the generation. Rebuild
  from the same PG state always targets the same OpenSearch document.
- **Core-vs-annotation change classification** compares each member's `core_content_hash`
  (temporal + display + event_type + lineage) and `annotation_content_hash` (entity_refs +
  verification/privacy/privilege) against its own latest prior-generation values, independent of
  the other hash — `change_class` is `core`/`annotation`/`unchanged`. Proven live with three
  scenarios in `tests/test_timeline_projection.py` (first-seen, annotation-only, core-changed) —
  see unit test names for the exact assertions.
- **The "authenticated projector interface"** (WP-E02 brief) is the DB-role boundary from the
  migration (`timeline_projector`: SELECT-only on candidate/membership tables, INSERT-only on
  every projection/receipt table, no UPDATE/DELETE grant anywhere), not an HTTP endpoint —
  `server/api/main.py` is outside this packet's file boundary, so no route was mounted. This is a
  known, explicit gap; see Blockers below.
- **`server/timeline/` and `timesketch-fork/personal_case_authority/` do not import each other.**
  They are two separate applications with independent dependency graphs (FastAPI/Agno backend vs.
  pinned Timesketch Flask app). The contract between them is the PostgreSQL schema plus the field
  shapes in `models.py`/`authority.py`, matched by hand, not by a shared import.

## Tests executed (this session, this machine)

| Check | Result |
|---|---|
| `uv run ruff check server/timeline tests/test_timeline_projection.py` | Clean |
| `uv run ruff format --check server/timeline tests/test_timeline_projection.py` | Clean |
| `uv run mypy server/timeline tests/test_timeline_projection.py` | `Success: no issues found in 9 source files` |
| `uv run ruff check timesketch-fork/personal_case_authority/importer.py` | Clean (not part of the CI-declared `ruff check server tests` scope; checked locally for hygiene) |
| `python -c "ast.parse(...)"` on `importer.py` | Parses cleanly (Timesketch's own dependency set is not installed in this environment — no deeper check possible without a live Timesketch env) |
| `uv run pytest -q tests/test_timeline_projection.py` (default, unit-only) | **15 passed, 4 deselected** in 0.4s |
| `TIMELINE_PG_LIVE=1 uv run pytest -q -m integration tests/test_timeline_projection.py` | **4 passed, 15 deselected** in ~11s, against the LIVE tailnet PostgreSQL (`100.91.190.107:5432`, db `ai`), each test rollback-scoped |
| Ad-hoc one-off migration apply+verify (before the test suite existed) | Applied `sql/0035_timeline_projection.sql` inside a transaction against the same live PG, listed all 7 tables + 2 views + 3 roles, inserted/verified a row, proved the append-only trigger blocks UPDATE, rolled back; post-rollback `information_schema.tables` count for schema `timeline` = 0 |
| Ad-hoc live receipt capture (below) | Full build→projector→receipt→manifest→activation round-trip, printed real UUIDs/hashes, rolled back |

### Live receipt (one full round-trip, rollback-scoped — 2026-08-26)

```
generation_id: d3d17ffb-1f80-4ac3-8a9a-8bfc954001fe
sequence: 1
created: True
member_count: 1
stable_member_id: 2d308284-449f-4543-8be0-a7ccb8638f00
opensearch_doc_id: 6be36c83380227a1a04276148e91bb269f07248470332cacfc38ae524aac5696
member_content_hash: 1951a3e74af156d0d4e1d584a1b0e7be1c58219b6e5767a5579c213185874d74
core_content_hash: b4c760d9798c332700739fb850d08e9b8a398a7a0c0d30777355c71504c557bb
annotation_content_hash: 3e8d8a269f8865ded17dfe9d5a371955faaab6ffc9c754dae8a16431df0249d4
change_class: core
receipt_id: ff121c8d-d64f-427c-995c-97eaca85c0d3
manifest_rows: 1
manifest[0].member_content_hash == member_content_hash: True
activation_id: fbf7cb63-9851-41b5-bbb9-2a2495c16869
current_active_generation: d3d17ffb-1f80-4ac3-8a9a-8bfc954001fe
ROLLED BACK
post-rollback timeline.* tables (must be 0): 0
```

None of these ids/rows persist on the live database — every check above ran inside a transaction
that was rolled back, and the post-rollback table count was independently re-verified at 0.

## Known limitations / unresolved items (tracked here per the owner result-persistence rule)

1. **No `evidence_approved` source is populated yet.** `GOVERNED_SOURCE_RESOLVERS` is an empty,
   documented extension point — blocked on WP-B01/C02, not on this packet. Only candidate-context
   members can be end-to-end tested today.
2. **`importer.py` is unexecuted.** No live Timesketch/OpenSearch deployment exists in this
   environment, and this session's mandate forbids building/running local containers or duplicate
   infrastructure. The module is written against the real upstream `OpenSearchDataStore.import_event`
   signature and the real, live-verified PG schema, but has never actually written to OpenSearch.
   **A later packet (TS-08/WP-H02, "Production deployment and live proof") must run it against a
   real Coolify-deployed Timesketch fork before any live-projection claim is made.**
3. **No HTTP route mount.** `server/api/main.py` is outside this packet's file boundary. The
   "authenticated projector interface" today is `python -m server.timeline` (CLI) plus the DB-role
   boundary; a future packet that owns routing decides whether/how to expose it over HTTP.
4. **`event_candidate.source_available_from` placeholder.** Candidate availability currently
   defaults to `event_candidate.created_at` (proposal time) — marked `# STUB:` in
   `server/timeline/generation.py` — until WP-B01's typed extraction-run contract supplies a real
   acquisition/extraction timestamp per ADR-0059. **Recommended follow-up for whichever agent next
   owns `docs/DEBT.md`:** add a row for this stub; it was not added here because `docs/DEBT.md` is
   a shared file outside this packet's exclusive-ownership grant and editing it risked colliding
   with concurrent work.
5. **`timeline_projector`/`timeline_writer`/`timeline_reader` roles are schema contracts, not yet
   enforcing guards** — the same caveat `sql/0029_pass_grants.sql` documents for its own roles: the
   app currently connects as the superuser `ai`, so these grants define the target isolation but
   do not yet block a superuser connection. Closing that gap is a connection-model change, not
   something this migration can do alone.
6. **R09/WP-H01 reconciliation itself was not run.** This packet provides the expected-manifest
   view and append-only receipt table R09 needs; it does not implement the R09 reconciler.

## Rollback

Everything in this packet is net-new and additive. To roll back: drop `sql/0035_timeline_projection.sql`'s
objects via a new forward migration (never edit this file in place — add a new numbered one that
`DROP`s the `timeline` schema and its roles); move `server/timeline/` and
`timesketch-fork/personal_case_authority/importer.py` to `to_be_deleted/` (owner-only actual
deletion per repository policy, never `rm`). No existing table, migration, or upstream Timesketch
file was modified — the only touched file outside this packet's new files is
`timesketch/lib/analyzers/__init__.py`, and that edit belongs to WP-E01, not this packet.

## Downstream acknowledgement

None yet. This document is the acknowledgement target for: WP-B01/C02 (once a real governed source
exists, register a `GOVERNED_SOURCE_RESOLVERS` entry), WP-F01/F02/F03 (curation/amendment/UI, which
read this packet's projection generations but do not modify anything here), WP-H01 (R09
reconciliation, which consumes `timeline.vw_projection_expected_manifest` and
`timeline.timeline_projection_receipt`), and WP-H02 (production deployment, which must execute
`importer.py` live for the first time and record the result).
