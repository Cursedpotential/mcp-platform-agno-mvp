# Content-chunk and context-thread structural foundation

> _Byline: Codex · GPT-5 · 2026-08-29._
> _Independent structural review: Claude Code · Opus · high effort · 2026-08-29._
> _Remediation: Codex · GPT-5 · 2026-08-29._

STATUS: REMEDIATED LOCALLY AFTER INDEPENDENT REVIEW — SCHEMA CONTRACT ONLY
BUILD_STATUS: FOCUSED STATIC TESTS PASS; ROLLBACK PG18 HARNESS ADDED BUT NOT RUN; NOT APPLIED OR LIVE-VERIFIED

## Outcome

Migration `0047_content_chunk_and_context_thread_foundation.sql` adds the format-neutral
relational foundation requested by the owner. It intentionally contains no chunker, parser,
format router, metadata extractor, thread classifier, backfill, deployment, or live database
write.

The foundation establishes:

- one version-pinned `working.content_chunk_generation` manifest and one generalized
  `working.content_chunk` authority;
- a canonical `context.source_range_locator` range primitive with exact slice hashes, half-open
  UTF-8 byte or Unicode-codepoint coordinates, and exactly one separate typed source-object,
  raw-record, or normalized-record subject link; complete-verbatim chunk sealing accepts only
  DB-verified UTF-8 byte spans over `source_version.original_object_id`, never raw/normalized
  alternate coordinate spaces;
- independent chunk and timeline/event-extraction lineage over that same immutable locator;
- deterministic reassembly receipts and a fail-closed complete-verbatim sealing gate;
- context-first, append-only reviewed classification into `context`, `legal`, or
  `personal_history` only;
- separate mirrored first-party and acquired-third-party context-thread identities, versions,
  ordered message memberships, multi-representation source assertions, and zero-to-many reviewed
  realization assertions;
- separate occurrence, representation-metadata, source-availability, and knowledge-horizon clocks;
- a shared append-only `context.relative_time_anchor` subsystem with typed subject link tables for
  unresolved/approximate temporal placement;
- a PostgreSQL-canonical HITL conflict plane with a versioned Workbench review-case lifecycle,
  current/open-queue projections, typed conflict memberships, versioned adjudication decisions,
  typed supporting provenance, and an independently provisioned NOLOGIN adjudicator capability role;
- reference-only orchestration ledgers for one durable Temporal `ConflictReviewWorkflow` per review
  case, append-only run states, n8n dispatch attempts, idempotent decision signals, reminder/escalation
  policies, and terminal/downstream reconciliation without Temporal payload storage; and
- explicit append-only legacy-chunk cutover maps without renaming or dropping the existing stores.

## VIP invariants preserved

- A logical human thread can cross platforms, source files, platform-local conversation IDs,
  devices, and representations. A source version can support multiple threads and a thread can be
  supported by multiple source versions.
- Native exports, screenshots, OCR-derived views, PDF/HTML/JSON/XML/CSV representations, and
  captures from different devices remain separate immutable provenance rows. No representation is
  deduplicated, merged, or selected as the canonical “best” source.
- First-party threads are anchored to the configured owner. Their primary availability clock is
  each required message/event `occurred_at` timestamp. Thread and realization horizons use the
  greatest availability among all required message and representation memberships; representation
  availability is pinned to its latest covered occurrence and metadata clocks never replace it.
- Acquired-third-party threads require approved acquisition lineage, reject owner participation,
  and use custody-backed acquisition as `source_available_from`. Earlier screenshot capture or
  export metadata cannot backdate availability.
- When a required member lacks an exact clock, that exact message or representation must have its
  own typed, active relative-time anchor. The exact thread/realization horizon remains `NULL`; SQL
  cannot silently ignore the missing clock through `MAX`. Before/after bounds, anchor references,
  contextual sequence, basis, confidence, ambiguity, review, and provenance remain independently
  correctable.
- Earliest knowledge availability is distinct from occurrence and from actual realization. A
  thread version uses the greatest availability time among all required source assertions. Any
  realization link is a reviewed assertion, not a claim that realization occurred.
- Chunking covers the complete immutable source and is independent of event extraction. Event
  extraction never removes text from chunks; timeline candidates retain their own source-range and
  activity-receipt provenance.
- A complete-verbatim generation can seal only when every chunk is `verbatim_span`, has exactly one
  UTF-8-byte locator whose typed subject is `source_version.original_object_id`, PostgreSQL can read
  and hash those retained bytes, its content hash equals that DB-computed slice hash, and the actual
  ordered ranges cover the retained original exactly once without gaps or overlaps. Raw-record,
  normalized-record, and self-asserted receipt coordinate spaces cannot satisfy the seal.
- Parsers, extractors, chunkers, and related tools remain Platform Tools capabilities. The Go
  engine calls Platform Tools directly; migration 0047 adds no duplicate engine implementation.
- PostgreSQL is approval authority. Temporal owns durable wait/state/timer coordination; short
  activities dispatch through n8n. n8n may select and invoke swappable human-review services,
  Workbench UI flows, or notifications, but it cannot approve or overwrite a decision. Workbench is
  the primary review surface.

## Negative chunker contract (documentation only)

Commit/reference `f2e9d2a` records that the vendored **Semantica** `StructuralChunker` rebuilds its
`.text` field: the measured reconstruction omitted 176 characters and 24 of 35 rebuilt texts were
non-verbatim. This is not a Chonkie result. Rebuilt text cannot satisfy the complete-verbatim seal;
exact original-byte offsets remain authoritative. No chunker is selected or implemented here.

## Independent-review remediation

Claude Opus requested changes. Migration 0047 was revised before integration:

- complete-verbatim seals now prove every span against the retained original object byte space;
- exact locator validation hashes DB-resident UTF-8 byte or Unicode-codepoint slices and fails
  closed when retained bytes are unavailable or the PostgreSQL substring range would overflow;
- required `NULL` clocks require per-message/per-source typed relative anchors and keep exact
  aggregate horizons `NULL` instead of relying on null-ignoring `MAX`;
- realization membership is symmetric: first- and third-party assertions can name required
  messages and representations, and both populations contribute to the greatest-source clock;
- every PL/pgSQL function pins `search_path`; visibility-dependent `regclass::text` grant logic was
  removed;
- 0047 idempotently creates the safe NOLOGIN `context_review_adjudicator` role, gives
  `platform_admin` administration of it, rejects runtime membership, and creates no login/password;
- PostgreSQL roles and relation prerequisites are checked before DDL; runtime, adjudicator, and
  existing timeline-role privileges are explicit and default-deny;
- review cases now have a stable `case_key`, append-only versions, decision-bound resolution,
  current-case and open-queue views, and an adjudicator-only lifecycle transition guard; and
- the missing generation lookup index was added to chunk source spans.

## Validation

Executed from the repository root:

```text
uv run pytest -q tests/test_0047_content_chunk_and_context_thread_foundation.py
uv run pytest -q tests/test_0047_content_chunk_and_context_thread_foundation.py -m "not integration"
uv run pytest -q tests/test_0047_content_chunk_and_context_thread_foundation.py -m integration
uv run ruff check tests/test_0047_content_chunk_and_context_thread_foundation.py
uv run ruff format --check tests/test_0047_content_chunk_and_context_thread_foundation.py
git diff --check -- sql/0047_content_chunk_and_context_thread_foundation.sql tests/test_0047_content_chunk_and_context_thread_foundation.py docs/reviews/2026-08-29-content-chunk-context-thread-foundation.md
```

The focused non-integration run passed **21 tests**. The integration selection found the executable
rollback-only PostgreSQL 18 behavior test and skipped it because
`PLATFORM_0047_TEST_SERVICE` was not bound in this session (**1 skipped**). The harness accepts a
libpq service name rather than a password or raw connection string, applies 0047 inside a
transaction, exercises runtime/adjudicator lifecycle and timeline ACLs, and always rolls back.

The focused test asserts the migration target guard, additive-only behavior, generation/manifest
contracts, typed locator shape, exact reassembly seal gate, immutable triggers, no global chunk-hash
uniqueness, no evidence lane, separate party populations, owner/acquisition rules, cross-platform
M:N representation support, independent clocks, relative-time typed links, independent timeline
provenance, the typed HITL conflict plane and reference-only orchestration ledgers, legacy cutover
maps, and the Platform Tools boundary.

## Explicit limitations and next gates

- The migration has not been applied to `platform`; SQL DDL, catalog ownership, triggers, and
  privileges therefore remain unverified against a PostgreSQL 18 server. The rollback harness is
  present but was not executed because no validation service binding was available.
- No legacy `chat_chunk` or `normalized_record_chunk` rows have been backfilled. The maps are empty
  by design until a receipt-bearing backfill/cutover plan is approved.
- No generation/manifest, chunk, source locator, thread, source-equivalence, relative-time, or
  realization rows have been produced.
- Review proposal, dispatch, signal, and reconciliation tables grant `platform_runtime` exact
  `SELECT`/`INSERT` rights, but final decisions and their typed provenance exclude runtime writes.
  `context_review_adjudicator` is a separate NOLOGIN role, is never granted to runtime, and final
  decisions require an activity receipt. No review table grants update/delete. Core chunk/thread
  runtime grants and timeline writer/projector grants are explicit. An authenticated reviewer
  identity still must be granted the adjudicator capability out of band; 0047 deliberately creates
  no login and no password.
- The structural contract does not select a chunker or schema-class variant. The parallel schema
  registry and chunk-strategy lanes remain authoritative for those choices.
- Production completion still requires review, an exact apply/validate runner, PostgreSQL role and
  prerequisite validation, migration application to `platform` only, backfill/cutover receipts,
  mandatory integration tests, Coolify deployment where applicable, and live proof.
