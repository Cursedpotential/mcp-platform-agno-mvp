# H-04 — the chunk↔message bridge, and rewiring the Weaviate feed onto it

> _Byline: Claude Code · Opus 5 · 2026-09-05._
> **STATUS: BUILT, NOT DEPLOYED.** Committed on `main`, not pushed, not applied live,
> not redeployed. No Weaviate write has been proven.

## Result first

`working.normalized_record_chunk` was dropped by `sql/0058_the_reckoning.sql:97` under
D-116. Nine code sites and one live SQL function kept naming it. Every one of them was
dead-on-execution: the table does not exist on `platform` (verified live 2026-09-05,
`to_regclass` returned NULL). The whole native-evidence vector feed — enqueue, drain,
activation, reconciliation, and the Workbench read model — could not have run.

Built in this change:

1. `sql/0072_content_chunk_message_bridge.sql` — the Q9 bridge, the queue's missing
   foreign key, and a rewritten enqueue function.
2. All nine Python sites rewired onto `working.content_chunk` **through** the bridge.
3. The Python chunk writer retired fail-closed and quarantined.
4. The embedder contract moved off the NIM-retired `nvidia/nv-embed-v1`.

Nothing was backfilled because there is nothing to backfill: `content_chunk`,
`normalized_record`, `evidence_vector_projection_job` and `content_chunk_generation`
each hold **0 rows** live (counted 2026-09-05).

## The nine-site inventory

| # | Site | Was | Now |
|---|---|---|---|
| 1 | `server/evidence/store.py` (chunk INSERT) | `INSERT INTO working.normalized_record_chunk …` — the only chunk writer | retired: `NotImplementedError`, raised before any validation or I/O |
| 2 | `server/evidence/store.py` `native_projection_jobs_for_artifact` | job ⋈ dropped table ⋈ record | job ⋈ `content_chunk_message` ⋈ `normalized_record`, `count(DISTINCT job.id)` |
| 3 | `server/evidence/native_activation.py` eligibility count | `count(*)` over dropped table, `derived_at<=watermark` | `content_chunk` ⋈ bridge (`is_center`) ⋈ record, `created_at<=watermark` |
| 4 | `server/evidence/native_activation.py` frozen enqueue | `SELECT chunk.id FROM` dropped table | same join as #3 |
| 5 | `server/evidence/native_activation.py` `_postgres_manifest` | dropped table + hard-coded `'nvidia/nv-embed-v1'` | `content_chunk` + `content_chunk_generation` + bridge; embed model/version derived from the module constant |
| 6 | `server/evidence/native_activation.py` canary samples | dropped table | `content_chunk` + bridge |
| 7 | `server/evidence/vector_projection.py` `_project` | dropped table; the one row a drain projects | `content_chunk` + generation + bridge (`is_center`) + record + custody + route |
| 8 | `server/ingest/query.py` `list_items` | `LEFT JOIN` dropped table | `LEFT JOIN` bridge → `content_chunk` → generation; `count(DISTINCT c.id)` |
| 9 | `server/ingest/query.py` `get_item` | `SELECT … FROM` dropped table | `content_chunk` + generation + bridge + record |
| — | `working.enqueue_evidence_vector_projection(uuid[],text)` (live SQL fn) | `SELECT chunk.id FROM working.normalized_record_chunk WHERE normalized_record_id=ANY(...)` | `SELECT DISTINCT bridge.chunk_id FROM working.content_chunk_message WHERE message_id=ANY(...)`; signature and ON CONFLICT requeue semantics unchanged |

Two `projection_kind` defaults carried the string `'normalized_record_chunk'`
(`native_activation.py`, `vector_projection.py`). Both are now `'content_chunk'`. The
projection hash changes as a result; that is free today because zero projections exist.

## Column mapping — `normalized_record_chunk` → `content_chunk`

The two tables are **not** the same shape. Every field the projector needs was
re-sourced honestly rather than dropped:

| Field the projection needs | Old column | New source | Note |
|---|---|---|---|
| `chunk_id` | `chunk.id` | `content_chunk.id` | — |
| `normalized_record_id` | `chunk.normalized_record_id` | `content_chunk_message.message_id` where `is_center` | the bridge exists precisely because this column does not |
| `content`, `content_sha256` | `chunk.*` | `content_chunk.*` | D-124: integrity, never custody |
| `chunker_id` | `chunk.chunker_id` | `content_chunk_generation.chunker_id` | `content_chunk` has no such column; the chunker is a property of the generation |
| `derived_at` / watermark | `chunk.derived_at` | `content_chunk.created_at` | direct successor |
| `source_content_hash` | `chunk.source_content_sha256` | `normalized_record.source_content_sha256` | **honest, not invented.** `content_chunk` has no source-content digest. The message row does, and it is exactly what the field meant: the digest of the source content the chunk derives from. Nothing was fabricated and nothing was dropped. |
| `char_start`, `char_end`, `attrs` | `chunk.*` | **removed** from the `get_item` read model | no successor column. Typed span lineage lives in `working.content_chunk_source_span`, a separate table and a separate concern; wiring it is not this change. |

New and real in the `get_item` read model: `is_center`, `member_position`,
`derivation_mode`.

## Why `is_center` is the join

The 2026-08-29 dual-graph rule requires every projection row to carry the PostgreSQL
source coordinate (`normalized_record_id` + `content_chunk_id`). A window chunk covers
several messages, so "which message is this chunk's coordinate" needs an answer that is
deterministic, not arbitrary. `is_center` is that answer, and the migration enforces at
most one centre per chunk. Consequence: one job resolves to exactly one message row, so
the drain still writes exactly one Weaviate object per job.

## Migration 0072 — what it does beyond the bridge

- **Re-anchors the queue.** `working.evidence_vector_projection_job.chunk_id` had **no
  foreign key at all** — verified live, zero `contype='f'` constraints on the table.
  0058 dropped its referent and took the constraint with it. 0072 adds
  `evidence_vector_projection_job_chunk_fk → working.content_chunk(id) ON DELETE CASCADE`.
  Zero rows, so no validation risk.
- **Append-only enforcement.** A `BEFORE UPDATE` trigger refuses rewrites (Q9). DELETE is
  reachable only by CASCADE from a deleted chunk or message — deliberate, so a rebuilt
  generation does not strand association rows.
- **Grants** mirror `working.content_chunk`'s live grants (`platform_runtime` SELECT/INSERT,
  `context_review_adjudicator` SELECT, `platform_app` full) plus `projection_refresher`
  SELECT, which the drain needs to resolve a job's message.
- **Self-verification block** refuses to commit if the bridge is missing, if the dropped
  table has somehow returned, if the FK was not added, or if the function still names the
  dropped table.

Two constraints were added that Q9 did not explicitly rule, both derived from what a
message-window chunk *is*: distinct `position` per chunk, and at most one `is_center` per
chunk. Neither requires a centre to exist, so composed / `unverified_derived` chunks are
unaffected. Flagging them as assumptions for the owner.

## Embedder

`nvidia/nv-embed-v1` (4096-d) was end-of-lifed on NIM 2026-08-25 (HTTP 410). The guard in
`server/core/evidence_vector_store.py` demanded it, so the lane would have failed loudly
on first use. Now `nvidia/nemotron-3-embed-1b` at 2048-d, symmetric, both overridable via
`EVIDENCE_EMBED_MODEL` / `EVIDENCE_EMBED_DIM` (no settings entry exists for this lane —
`server/core/settings.py` carries only the legacy NIM fallback ids — so an env override
with a fail-loud default is the honest knob; a non-integer or non-positive dimension
raises at import). The fail-loud guard in `NativeEvidenceProjector.__init__` is unchanged.

This is safe without a collection version bump: `EvidenceChunkV1` **does not exist** in
Weaviate — `GET http://100.91.190.107:8081/v1/schema` returned seven classes
(`Evidence_knowledge`, `Relationship_timeline_knowledge`, `Platform_code_knowledge`,
`Platform_context`, `Personal_history_knowledge`, `Legal_knowledge`, `Platform_knowledge`),
none of them `EvidenceChunk*`. The collection will be created fresh at 2048-d. **If it is
ever created at another dimension it must be dropped and rebuilt** — a mismatched
dimension is a hard Weaviate error, not a silent downgrade.

`server/analysis/semantica_wiring.py` and `server/core/session.py` still carry
`nv-embed-v1` for the *other* (Agno knowledge / semantica) lanes. Out of scope here and
left untouched; they are separate consumers with their own live stores. **Open item.**

## The Python chunk writer is retired

`store_record_batch(records, chunks, …)` now raises `NotImplementedError` on a non-empty
`chunks` list, before any record validation or database access. D-130: a record writer
does not also chunk. The writer is the Go message-window chunker Temporal Activity
(redesign plan Stage 3), which will write `content_chunk` + `content_chunk_message`. The
signature is unchanged so callers keep compiling and fail loudly instead of silently.

The removed code is quarantined verbatim, never deleted:
`.review_hold/store_normalized_record_chunk_writer_retired_20260905.txt`.

## Tests

Old coverage on this path was mock-only, which is exactly why nine dead sites survived
0058 unnoticed — a mock cannot tell you a table does not exist. New file
`tests/test_h04_content_chunk_message_bridge.py` asserts against the **emitted SQL text**:
no module emits `FROM|JOIN|INTO|UPDATE|TABLE working.normalized_record_chunk`; every chunk
reader joins the bridge; the drain resolves one message per job through `is_center`; the
`projection_kind` default is `'content_chunk'`; the writer is retired and quarantined; the
embedder contract is the live NIM model; 0072 declares the ruled shape.

One `integration`-marked live test applies 0072 inside a transaction, applies it a second
time to prove idempotency, asserts the FK, calls the rewritten function with `[]` and with
a random uuid, asserts the blank-reason guard raises, then ROLLs BACK and re-asserts the
table is absent. It deliberately does **not** insert a minimal end-to-end chain: reaching
`working.normalized_record` requires an `evidence.evidence_hash` row, and fabricating a
custody digest to satisfy a test is precisely what custody exists to prevent.

`tests/test_native_evidence_projection.py` had its stale `nv-embed-v1` / `4096` assertions
amended.

## Validation (real output)

```
$ uv run --no-sync ruff check server tests
All checks passed!

$ uv run --no-sync ruff format --check server tests
317 files already formatted

$ uv run --no-sync mypy server
Success: no issues found in 179 source files

$ uv run --no-sync pytest -q tests/test_h04_content_chunk_message_bridge.py \
    tests/test_native_evidence_projection.py tests/test_message_projection.py \
    tests/test_temporal_projection_sql_contract.py \
    tests/test_exec_native_evidence_cutover_contract.py \
    tests/test_0047_content_chunk_and_context_thread_foundation.py
68 passed, 2 deselected in 19.30s

$ uv run --no-sync pytest -q -m integration tests/test_h04_content_chunk_message_bridge.py
1 passed, 13 deselected in 1.42s      # live PG, applied twice in a txn, ROLLBACK
```

Live schema probe (db `platform`, host `100.91.190.107`, credentials via the repo's own
`server/core/url.py` resolution; no value printed):

```
db: platform
regclass working.normalized_record_chunk   None          <- dropped by 0058
regclass working.content_chunk             working.content_chunk
regclass working.content_chunk_message     None          <- 0072 not applied yet
rows working.content_chunk                 0
rows working.normalized_record             0
rows working.evidence_vector_projection_job 0
rows working.content_chunk_generation      0
fn working.enqueue_evidence_vector_projection(uuid[],text)
job FK (contype='f'):                      (none)
```

Grep proof — zero executable references left:

```
$ grep -rn "normalized_record_chunk" server/          # only comments/docstrings/guards
$ grep -rn "normalized_record_chunk" sql/ | grep -v bootstrap/schema_baseline \
    | grep -vE "sql/(0026|0029|0047|0058|0065)_"      # only 0072's own comments + guards
```

## Honest exceptions

- **`tests/test_ingest_port.py` fails, and it failed before this change.**
  14 failures, all `ValidationError: lane — Input should be <IngestLane.context>`.
  `server/contracts/ingest.py:84` at `HEAD` declares
  `lane: Literal[IngestLane.context]`; the test passes `IngestLane.platform` /
  `.evidence`. Neither file is in this changeset. Not fixed here — pre-existing breakage
  on `main`, and possibly owned by the concurrent `modules/engine/**` work.
- **Not deployed.** Nothing was pushed, no migration was applied live, no container was
  redeployed, and no Weaviate object was ever written. The Weaviate feed is *correct*, not
  *proven*.

## Before this is live

1. `git push` (deliberately not done).
2. Apply `sql/0071_pg_cdc_outbox_spine.sql` then `sql/0072_content_chunk_message_bridge.sql`
   to `platform`. 0071 is also unapplied.
3. Coolify redeploy of the API/worker (env-literal rendering: a redeploy is required, not a
   restart).
4. Create `EvidenceChunkV1` at 2048-d via the activation path, then a **real Weaviate write
   probe** — one object in, one object read back, dimension confirmed.
5. Stage 3: the Go message-window chunker Activity, the only writer of `content_chunk` +
   `content_chunk_message`. Until it exists, nothing populates the bridge and the feed
   stays correct-but-empty.
6. Decide the `nv-embed-v1` question for `semantica_wiring.py` / `session.py`.
