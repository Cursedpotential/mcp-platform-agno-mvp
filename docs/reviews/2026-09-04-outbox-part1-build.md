# ADR-0052 Part 1 build — the PG-CDC outbox spine (PostgreSQL side)

> _Byline: Claude Code · Opus 5 · 2026-09-04._
> Authority: **ADR-0052** (ACCEPTED, owner sign-off 2026-08-12 "sign 52") Part 1 ·
> **D-054** (all 8 owner rulings) · **D-107** (Temporal owns projection fan-out;
> SurrealDB manual-promotion-only) · **D-116** (the reckoning) · **D-124** ·
> owner order 2026-09-04 23:46 (*"I said build it… fix it."*).
> STATUS: **built + live-validated under rollback; NOT committed, NOT applied.**

---

## 1 · Requires vs exists vs missing

| ADR-0052 Part 1 requirement | What already existed | Verdict |
|---|---|---|
| Per-table, full-row transactional outbox for every propagating `working.*` table | `sql/0024` defines `chat_conversation_event`, `chat_message_event`, `chat_chunk_event`, `chat_chunk_lane_event`, `context_asset_event` — **never applied live** (zero such tables in the live `platform` DB), and 3 of the 5 targets were deleted by D-116/`sql/0058` | **MISSING** — rebuilt in `0071` against the post-reckoning source tables |
| Trigger writes the full outbox row in the same transaction | `working.emit_chat_row_event()` is live but **orphan**: zero triggers reference it, its target tables do not exist | **MISSING** — `working.emit_row_event()` supersedes it (old function retained, never-delete rule) |
| `pg_notify` as wakeup, aggregate id only | old function notified with `TG_TABLE_NAME` only (no id) | **MISSING** — now `<event_table>:<id>` |
| DELETE captured | `sql/0024` triggers were `INSERT OR UPDATE` only | **MISSING** — added (ADR ruled INSERT/UPDATE; DELETE added so a delete cannot propagate as silence) |
| Per-sink durable cursor | `sql/0024` `working.chat_cdc_cursor` (never applied; sink list was a hard-coded CHECK) | **MISSING** — `working.cdc_cursor`, FK to a registry instead of a CHECK list |
| Dead-letter table + replay + mandatory alert (D-054 §7) | `sql/0024` `working.chat_projection_dead_letter` (never applied) | **MISSING** — `working.cdc_dead_letter` + `working.cdc_lag()` |
| Sink registry; Surreal never auto-drained (D-107) | sink vocabulary existed only as a CHECK on `working.content_chunk_projection.sink` (`weaviate/semantica/sat_temporal/opensearch/surrealdb`, `sql/0055`+`0058`) | **MISSING** — `working.cdc_sink` with a structural CHECK forcing `surrealdb` to `promotion_only` |
| Horizon fields ride the event, spine never filters | — | **MISSING** — `occurred_at` / `knowledge_time` / `disclosure_tier` columns on every outbox row; no filtering anywhere in the spine |

**Reused, NOT duplicated** (owner's one-authored-spine rule — none of these *is* the outbox):

- `working.content_chunk_projection` — per-`(chunk, sink)` **fresh-ingest projection state**. A sink-state table. Untouched.
- `working.evidence_vector_projection_job` — vector-projection work queue, owned by migration `0070` (concurrent agent). Untouched.
- `canon.recompute_queue` — re-projection **after an approved canon change**; D-116 states this is deliberately a separate process from fresh ingest. Untouched.

---

## 2 · What was built

`sql/0071_pg_cdc_outbox_spine.sql` (466 lines), idempotent DDL, one transaction:

- **`working.cdc_sink`** — sink registry (data, not an enum). Seeds `weaviate`, `semantica`, `sat_temporal`, `opensearch`, `extraction`, `surrealdb`. Two CHECKs: `auto_drain` XOR `promotion_only`, and `sink_id <> 'surrealdb' OR (auto_drain = FALSE AND promotion_only = TRUE)` — **D-107 as a constraint, not a comment**.
- **`working.cdc_source`** — outbox registry, one row per source table. Registered: `context_record`, `normalized_record`, `content_chunk`, `chat_conversation`, `chat_message`, `context_asset`.
- **Six outbox tables** `working.<table>_event`, each with its own IDENTITY sequence (never `LIKE INCLUDING ALL` — that would make independent lanes contend for one counter): `event_id`, `operation` (`INSERT|UPDATE|DELETE`), `source_pk`, `row_data` (full row), `source_generation`, `occurred_at`, `knowledge_time`, `disclosure_tier`, `xact_id`, `created_at`. Indexed `(created_at, event_id)` and `(source_pk)`.
- **`working.emit_row_event()`** + six `AFTER INSERT OR UPDATE OR DELETE … FOR EACH ROW` triggers named `<table>_outbox`.
- **`working.cdc_cursor`** (per sink × outbox), **`working.cdc_dead_letter`** (+ open-rows partial index).
- **Helpers**: `cdc_claim_batch`, `cdc_ack`, `cdc_dead_letter_event`, `cdc_reset_cursor`, `cdc_lag()`.
- **Grants** to `platform_worker`; a post-condition `DO` block that raises if any outbox, trigger, or the D-107 invariant is missing.

### Deliberate deviation from the build brief

The brief asked for `status` / `processed_at` / `error` **columns on the outbox**. The outbox here has none, deliberately: one event fans out to *many* sinks, so per-sink progress belongs on `working.cdc_cursor` and per-sink failure on `working.cdc_dead_letter` — this is ADR-0052's "subscribers hold their own cursors" (invariant 4). A status column on a shared event would bake one sink's progress into every sink's event. The "pending predicate" is therefore `event_id > cursor.last_event_id`, served by the outbox primary key.

---

## 3 · Part 2 — the drainer contract (Go / Temporal; **not built here**)

Part 2 lives in `modules/engine/` and is a Temporal Activity family. It must **acknowledge and honour** the following.

**Invariants Part 2 must not break**

1. NOTIFY is a **wakeup only**. Correctness is outbox + cursor. The worker **also polls on a timer**; a worker that was down, or a notification sent with no listener, is healed by the next poll. (Pre-mortem #1.)
2. **Never** write a sink inline from a parse path. The spine is the only propagation route.
3. **Never** filter by `occurred_at` / `disclosure_tier` / `visible_from` in the drainer. Those ride the event as payload for read-side, agent-bound horizon filters (canon §1, ADR-0052 invariant 3). On Weaviate, horizon filters must be **dict filters** — `agno.filters` FilterExpr lists are silently dropped.
4. **D-107**: `surrealdb` is `promotion_only`. Draining it may only raise a **promotion candidate** for an explicit owner decision. `cdc_claim_batch` refuses it unless the caller passes `p_allow_promotion_only => TRUE`.
5. Each Activity is retryable. `cdc_ack` is monotonic and idempotent by construction; a re-ack of an already-acked batch is a no-op.
6. Alert on `open_dead_letters > 0` is **mandatory** (D-054 §7). Without it the dead-letter table is a black hole.

**The exact SQL a drainer runs** (one Activity invocation = one transaction):

```sql
BEGIN;

-- 1 · claim. FOR UPDATE SKIP LOCKED is taken on the CURSOR row inside this
--     function, so a second worker on the same lane gets zero rows, not a
--     duplicate batch. Returns zero rows (not an error) when the lane is held.
SELECT event_id, operation, source_pk, row_data,
       source_generation, occurred_at, knowledge_time, disclosure_tier, created_at
  FROM working.cdc_claim_batch(
         p_sink_id     => 'weaviate',
         p_event_table => 'context_record_event',
         p_limit       => 500);

-- 2a · success for the whole batch: advance past the highest event_id handled.
SELECT working.cdc_ack('weaviate', 'context_record_event', $max_event_id);

-- 2b · poison pill (retry budget exhausted on ONE event): quarantine the full
--      payload and advance the cursor PAST it, so one bad row never stalls the
--      lane. Nothing is dropped.
SELECT working.cdc_dead_letter_event(
         'weaviate', 'context_record_event', $event_id,
         $row_data::jsonb, 'sink_error', $error_text, $attempts);

COMMIT;
```

Rebuild / contamination recovery (an audited operator act, ADR-0047 — the caller writes the ledger row):

```sql
SELECT working.cdc_reset_cursor('weaviate', 'context_record_event', 0);
```

Status surface for the operator console `cdc-status` panel:

```sql
SELECT * FROM working.cdc_lag();
-- sink_id, source_event_table, auto_drain, promotion_only,
-- last_event_id, max_event_id, pending, open_dead_letters, last_advanced_at
```

Listener wakeup: `LISTEN working_cdc;` — payload is `<event_table>:<source_pk>`, an id only. Treat it as "poll now", never as the data.

---

## 4 · Live validation (platform PG, `100.91.190.107:5432`, db `platform`) — zero net writes

Every step ran inside ONE transaction that ended in `ROLLBACK`. Verbatim results:

| Step | Result |
|---|---|
| 0 preflight | spine objects live before apply: **0** |
| 1 apply `0071` | applied, no exception |
| 2 apply `0071` **again in the same txn** | re-applied, no exception → **idempotent** |
| sinks | `extraction/T/F · opensearch/T/F · sat_temporal/T/F · semantica/T/F · surrealdb/F/T · weaviate/T/F` |
| outbox tables / triggers | 8 `*_event` tables in `working` (6 new + 2 pre-existing `candidate_event`, `realization_event`); **6** `*_outbox` triggers |
| 3 throwaway INSERT into `working.context_record` | id `e66b65d3-…` |
| 4 outbox row in the SAME txn | `(1, 'INSERT', e66b65d3-…, occurred_at✓, knowledge_time✓, xact_id✓)` |
| 5 UPDATE emits | `(1,'INSERT'), (2,'UPDATE')` |
| 6 claim / ack / re-claim | claim → 2 rows; `cdc_ack` → `2`; re-claim → **0**; cursor `('weaviate','context_record_event',2)` |
| 7 dead-letter | dead letter written `('semantica', 3, 'sink_error')`; semantica cursor advanced to **3** (past the poison row) |
| 8 **D-107** | `cdc_claim_batch('surrealdb', …)` **refused**: `sink surrealdb is promotion_only (D-107); pass p_allow_promotion_only => TRUE and write a promotion CANDIDATE, never the sink itself`. Explicit opt-in returns 3 candidate rows. |
| 9 DELETE emits + status | `DELETE 1 · INSERT 1 · UPDATE 2`; `cdc_lag()` reports per-sink pending and `open_dead_letters=1` for semantica |
| 10 ROLLBACK | spine objects after rollback: **0**; `working.context_record` rows: **0** |

**Defect found and fixed by this validation:** `cdc_dead_letter_event` called `cdc_ack`, which raised `cdc_ack: no cursor for (semantica, context_record_event) -- claim first` when no cursor row existed yet. `cdc_ack` now upserts the cursor (`ON CONFLICT … GREATEST`), which also makes it retry-safe as a Temporal Activity.

**Test suite (`uv run --no-sync pytest -q`, 304.72s):** `26 failed, 1455 passed, 27 skipped, 10 deselected, 1 error`. A grep of the failure list for `cdc|outbox|0071` returns **0** — every failure is pre-existing and unrelated (deploy contracts, `test_opencode_ops_platform_cutover`, `test_surreal_phase1_workspace`, `test_ingest_port`, `test_universal_import_deploy_contract`, `test_uiw_repair_workflow_contract`). No test in `tests/` references the spine's schema, so none needed updating.

**Not proven end-to-end:** an INSERT into `working.normalized_record` needs a real `evidence.evidence_hash` custody parent (`normalized_record_artifact_id_fkey`, plus `evidence_hash_subject_ck` requiring a real subject). Fabricating a custody row for a smoke test was refused. Its `normalized_record_outbox` trigger is proven to exist and be attached (trigger count + the migration's own post-condition block); the emit path itself is table-driven and identical to the one proven on `context_record`.

---

## 5 · What remains before this is live

1. `git add sql/0071_pg_cdc_outbox_spine.sql docs/reviews/2026-09-04-outbox-part1-build.md` → commit → push (**not done — stop-before-git instruction**).
2. Apply via the repo's migration path (an `apply_0071_live.py` in the shape of `scripts/apply_0054_live.py`), including a `public.schema_version` ledger row. Note: that ledger is currently **empty** on live — the ledger true-up is a separate concern, not this migration's.
3. Coolify redeploy of anything that must see the new objects.
4. Part 2: the Go/Temporal drainer + the operator-console `cdc-status` panel + the mandatory dead-letter alert.
5. Phase 2 of ADR-0052: retire the inline Weaviate write in `server/evidence/workflows.py` behind the spine.

Open follow-ups worth an owner decision, deliberately **not** taken here: whether `working.chat_conversation` / `working.chat_message` remain propagation sources post-reckoning (they are live and empty), and whether `context.*` tables join the spine.
