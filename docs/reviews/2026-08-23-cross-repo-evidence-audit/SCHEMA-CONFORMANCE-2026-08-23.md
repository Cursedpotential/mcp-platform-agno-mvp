# Schema conformance map — does the shape match what was ruled?

> _Byline: Claude Code · Opus 5 · 2026-08-23_

This is **not** a health check. CH-17 in `docs/CHANGE-ORDER.md` already established that all 210
tables are mechanically sound and that five dormant constraints validate clean. This asks a
different question: **does the shape of the database match the decisions the owner actually made?**

Every group of tables gets one of six verdicts:

| Verdict | Meaning |
| --- | --- |
| **CONFORMANT** | The shape matches a ruling. Leave it alone. |
| **INTENDED-FUTURE** | Empty on purpose. The design is ahead of the data, deliberately. Fine. |
| **PARALLEL-DUPLICATE** | Two things do one job. Violates "one implementation per concept". |
| **TEST-RESIDUE** | Rows that a test or probe created and nobody cleaned up. Violates "test data never becomes canonical". |
| **LEGACY-EXITING** | Real, still in use, but on a ruled path out. Not a defect — a countdown. |
| **UNCLEAR** | Cannot be adjudicated from evidence alone. Needs the owner. |

Method: live read-only introspection of PostgreSQL 18.1 at `ai@100.91.190.107:5432` (exact
`count(*)` on all 210 base tables, plus constraints, triggers, foreign keys, table comments, and
extension ownership), cross-checked against `rg` searches of `server/`, `scripts/`, `tests/`,
`workbench/`, and `sql/` for the code that actually reads and writes each table. No writes were
made to the database.

---

## 1. The headline numbers

210 base tables. **44 hold rows; 166 are empty.**

| Schema | Tables | Non-empty |
| --- | ---: | ---: |
| `working` | 88 | 6 |
| `analysis` | 35 | 5 |
| `ai` | 27 | 17 |
| `evidence` | 19 | 2 |
| `public` | 17 | 3 |
| `reference` | 15 | 7 |
| `ops` | 7 | 4 |
| `duckdb` | 2 | 0 |

The 166 empty tables break down as:

| Bucket | Count | Comment |
| --- | ---: | --- |
| **(a) Intended-future** — designed ahead of the data, deliberately | **116** | Legal workflow, third-party projections, walks, raw layer, the parked location lane, reference lookups |
| **(b) Superseded or dead** — nothing will ever write here again | **34** | The `public` legacy island, the retired staging tables, the unwired CDC outbox, the Agno tables we are exiting |
| **(c) Unclear** — cannot rule without the owner | **16** | The version registries and the chat model that lost its data |

The (b) and (c) lists are itemised in §8 and §9.

**The single most important number in this report is not a count of tables. It is this:** the
context lane holds 1,741 rows in a table that no code reads or writes, while the code that
replaced it writes to a table holding zero. The data and the code are in different places.

---

## 2. The evidence spine — CONFORMANT in shape, unrealized in practice

**Group:** `working.normalized_record` (11 rows) and the 15 tables that key off it — `message`,
`message_participant`, `conversation`, `attachment`, `handle`, `account`, `call_log`,
`normalized_record_chunk`, `record_visible_from`, `event_source_record`, `realization_event`,
`realization_event_record`, `message_projection_route`, `third_party_message`, `walk_step`,
plus `analysis.evidence_item`, `analysis.knowledge_evidence_promotion` and
`analysis.timeline_event` reaching in from above.

**Verdict: CONFORMANT.**

This is unambiguously the canonical spine. Fifteen foreign keys point at it from four schemas.
It is the only one of the three message models present in the reproducible bootstrap dump
(`sql/bootstrap/schema_baseline.sql`, 78 hits). It has a full write-read loop in live code:
writers at `server/evidence/store.py:445` and `:459`, `server/evidence/message_projection.py:157`
and `:186`, `server/api/inspect_routes.py:974`; readers across twelve files including
`server/case_management/repository.py`, `server/ingest/query.py`,
`server/evidence/native_activation.py`, and `server/evidence/vector_projection.py`. Most recent
writer commit 2026-08-18; a reader was touched 2026-08-23.

**But three ruled behaviours are shaped correctly and have never actually happened:**

1. **Custody at capture (ruled 2026-08-23) is unrealized on the live rows.** All 11
   `normalized_record` rows have `provenance_id` NULL and `acquisition_id` NULL.
   `evidence.custody_event` and `evidence.acquisition` are both empty. The columns and the
   foreign keys exist; nothing has ever filled them. The pending standalone hasher is exactly
   the gap this measures.
2. **The first-party projection has never run.** `working.message`, `working.conversation`, and
   `working.attachment` are all empty, despite all 11 spine rows having `record_type = 'message'`.
   `message_projection.py` exists and is recent; it has not been run against this data.
3. **The first-party/third-party discriminator is unset.** `normalized_record.message_corpus`
   is NULL on all 11 rows. Its CHECK constraint allows `first_party` or `acquired_third_party`.

None of these are shape defects. They are a "designed but never exercised" gap — expected under
sprint mode, worth naming so nobody reads the empty tables as a design problem.

### 2a. The first-party vs acquired-third-party split (ADR-0059 / D-065) — CONFORMANT

**Group:** `working.message_projection_route`, `working.third_party_conversation`,
`working.third_party_conversation_acquisition`, `working.third_party_message`,
`working.third_party_message_participant`. All empty.

**Verdict: CONFORMANT / INTENDED-FUTURE.** This one is genuinely DB-enforced, exactly as ruled:

- `message_projection_route` carries `UNIQUE (normalized_record_id, projection_kind)` and a CHECK
  restricting `projection_kind` to `first_party` or `acquired_third_party` — one record cannot be
  routed to the same projection twice, and cannot be routed to a projection that does not exist.
- `third_party_message` carries `CHECK (projection_kind = 'acquired_third_party')` plus a
  composite deferrable foreign key back to the route on `(normalized_record_id, projection_kind)`.
  It is structurally impossible to land a first-party message in the third-party projection.
- A `message_projection_validate` trigger fires on `normalized_record`, `message_projection_route`,
  and `third_party_message`.
- Awareness comes from acquisition: `third_party_conversation.source_artifact_id` is a required
  foreign key to `evidence.evidence_hash`, so a third-party conversation cannot exist without a
  custody hash behind it, and its table comment states approval requires "explicit non-owner
  participants and an approved human acquisition link."
- Plural realization is real: `realization_event` / `realization_event_record` is a many-to-many
  with an approval state machine (`proposed` / `approved` / `superseded`) and paired-null CHECKs
  binding `approved_at` and `approved_by` to that state.

This is the best-shaped part of the database. It matches its ruling clause by clause.

### 2b. Walks and horizon (`0027`, `0028`) — INTENDED-FUTURE

`working.walk_run`, `walk_step`, `walk_checkpoint`, `walk_step_retrieval`,
`walk_step_realization_retrieval`, `record_visible_from`. All empty, all referenced by live code
(`server/evidence/derivation.py`, `server/api/native_evidence_search_routes.py`,
`tests/test_temporal_projection_sql_contract.py`). Designed ahead of the data, on purpose.

---

## 3. The context lane — PARALLEL-DUPLICATE, and the data is on the wrong side

This is the most consequential finding in the report.

**Three models exist. Two of them do the same job. None reference each other.**

| Model | Rows | Live writers | Live readers |
| --- | ---: | --- | --- |
| A. `working.normalized_record` + `message` | 11 | 5 files | ~20 sites |
| B. `working.context_record` | **1,741** | **none** | **none** |
| C. `working.chat_conversation` / `chat_message` / `chat_chunk` | **0** | **8 statements, 1 file** | 3 sites |

Model A is the evidence spine (§2) and is a different concern — it carries the whole custody,
provenance, review, and legal apparatus that the context models deliberately lack. There is
**zero** coupling between A and either B or C: no foreign key in either direction, and no Python
file references both. That separation is ruled and documented — the "context is never evidence"
boundary (owner 2026-08-01), stamped into the table comment on `context_record` itself and into
`sql/0021_context_record.sql:21` and `sql/0022_context_assets.sql:18-19`. **That part is correct.**

**The problem is B versus C.**

`working.context_record` carries a table comment that reads, in the live database today:

> "PG source of truth for AI-chat CONTEXT ingest (owner ruling 2026-08-12: PG first,
> change-detection projects to Weaviate). Standalone by design — NO evidence FK... See
> `server/analysis/context_chat_ingest.py` + ADR-0051."

That comment is **stale and now actively misleading.** Commit `5ea3ede` (2026-08-13,
"redesign chat knowledge ingestion") introduced `sql/0024_chat_conversation_and_message.sql` and
repointed `context_chat_ingest.py` — the very file the comment names — at Model C. Today
`context_chat_ingest.py:199-457` writes eight INSERT/UPDATE statements against
`chat_conversation`, `chat_message`, `chat_chunk`, `chat_chunk_message`, `chat_chunk_lane`,
`chat_chunk_projection`, and `chat_chunk_embedding`. It does not contain a single statement
against `context_record`. Repo-wide, **`working.context_record` appears in zero SQL statements**;
all eight Python occurrences are docstrings, comments, or a table-name string in an allowlist.

The 1,741 rows were never migrated across.

**It gets worse in a specific and dangerous way.** Two live tool front doors still advertise the
orphaned table:

- `server/tools/ingest/context_drain.py:2,47` — the registered tool `ingest.context-drain`
  describes itself as draining `working.context_record`. At `:58` it imports
  `sync_pending_context`, which reads `working.chat_chunk_projection` — Model C.
- `scripts/drain_context.py:1,18` — the CLI docstring makes the same claim.

So an operator running the documented drain tool against a "pending" backlog is told they are
draining the 1,741 rows and is in fact draining an empty table.

**And retiring `context_record` is not free.** All 1,741 rows have `weaviate_synced_at` and
`graphiti_synced_at` populated — zero pending on either. Those rows are the sole PostgreSQL copy
backing content that is already live in Weaviate and Graphiti. Dropping the table without
migrating first would leave downstream vector and graph content with no source of truth in the
canonical store. (Graphiti is itself retiring, which reduces but does not eliminate the exposure.)

**Verdict: PARALLEL-DUPLICATE.** Two implementations of one concept, the newer one ruled by
ADR-0053 and `sql/0024`, the older one holding all the data and all the stale documentation.

**Recommendation, plain English:** Model C (`chat_conversation` / `chat_message` / `chat_chunk`) is
the winner — it is newer, it is what the code writes, it is what ADR-0053 rules, and it has the
richer shape (per-message rows, chunk lanes, tags, embeddings). Do three things in one move:
(1) migrate the 1,741 `context_record` rows into the chat model so the data and the code are in
the same place; (2) fix the two tool descriptions that still name the dead table, before someone
trusts them; (3) only then mark `context_record` superseded with a dated comment, the same way
`sql/0016` handled the staging tables — do not drop it, and do not touch it until Weaviate and
Graphiti have been re-sourced from the new home.

### 3a. Chat CDC outbox — PARALLEL-DUPLICATE (unwired half) + TEST-RESIDUE

**Group:** `working.chat_conversation_event` (1 row), `chat_message_event` (2),
`chat_chunk_event` (1), `chat_chunk_lane_event` (1), `chat_cdc_cursor` (0),
`chat_projection_dead_letter` (0), `context_asset_event` (0), `chat_chunk_tag` (0).

These are defined only at `sql/0024_chat_conversation_and_message.sql:306-372` and have **zero
application-code hits anywhere**. Database triggers write into them; nothing consumes them. Half
of the CDC design shipped as pure DDL. `chat_chunk_projection` is the one outbox-family table
that has code (four sites in `context_chat_ingest.py`).

The five rows they hold are test residue. Reading `chat_conversation_event` directly:

> `"title": "Ingestion readiness probe (DELETE ME)"`, `"external_id": "zzz-readiness-probe-2026-08-23"`,
> ingested 2026-08-24 from a scratchpad file.

The base rows were purged after the probe — correct, per the purge-test-data rule. But the outbox
is append-only by design, so the events survived and cannot be deleted through the normal path.
**Test data has become permanent in an append-only ledger.** This is a live instance of the
hard rule biting, and it needs an owner decision rather than an agent's improvisation.

### 3b. Context assets — CONFORMANT

`working.context_asset`, `context_archive`, `context_asset_message`, `context_asset_derivation`,
`context_asset_projection`. Real writers and readers, all in `server/analysis/context_assets.py`
(`:254`, `:304`, `:331`, `:348`, `:392`, `:409`, `:417`), entered via
`server/analysis/chat_archive.py:197`, last writer commit 2026-08-13. This family correctly binds
to Model C — `context_asset_message.message_id` is a foreign key to `chat_message`. It is the one
cross-model link in the entire context lane, and it points at the winner.

---

## 4. Two candidate/staging systems — PARALLEL-DUPLICATE, already adjudicated in SQL

| System | Tables | Rows | Live code |
| --- | --- | ---: | --- |
| 1 (old) | `working.extraction_candidate`, `record_observation`, `extraction_batch` | 0 | **none** |
| 2 (new) | `working.candidate_entity`, `candidate_fact`, `candidate_event`, `extraction_run`, `review_decision`, `promotion`, `source_provenance` | 0 | writer exists, gated |

System 1 carries an explicit, dated supersession stamp in the live database. From
`sql/0016_working_gate_layer.sql:525-530`, visible today as a table comment:

> "SUPERSEDED by working.candidate_entity / candidate_fact / candidate_event (sql/0016,
> 2026-08-02). Was empty at supersession. Do not write here."

The migration header at `:34-38` adds: "SUPERSEDES (structurally, not by deletion)... both
verified 0 rows live on 2026-08-02."

**Verdict: System 1 is LEGACY-EXITING — and it is already handled correctly.** This is what
formal retirement is supposed to look like: a dated comment, in the database, naming the
successor, retained rather than dropped under the never-delete rule. No further action is needed.

**Verdict: System 2 is INTENDED-FUTURE, with a caveat.** Its writer is real
(`server/analysis/semantica_candidates.py:25-63`) but its own docstring says "the worker never
imports this module," and `server/analysis/semantica_wiring.py:148` marks it
"APPROVALS-gated; fixture/in-process adapter only." Its only callers are a fixture script and a
test. `working.promotion` has no application code at all — DDL plus an append-only trigger.

**Recommendation:** leave both as they are. System 1 needs no further ceremony. The one small
correction to make elsewhere: `working.extraction_run` belongs to System 2, not System 1 — it was
created by `sql/0016:124`, and prior notes that grouped it with the retired tables were wrong.

---

## 5. Two run ledgers — the provenance backbone points at the empty one

| Ledger | Rows | Owner module | Referenced by |
| --- | ---: | --- | ---: |
| `ops.workflow_run` / `_stage` / `_review_action` | 2 / 8 / 1 | `server/evidence/run_ledger.py` (all writes) | **3 tables** |
| `ops.processing_run` | **0** | `server/analysis/detection.py:338` only | **35 tables** |

`ops.workflow_run*` is the live ledger. One module owns every write (`run_ledger.py:81` through
`:370`); it drives `server/api/run_routes.py`, `inspect_routes.py`, `evidence/workflows.py`,
`evidence/custody.py`, and the workbench UI types. D-067 rules it the authoritative run report.
Its two rows are real chat-transcript runs from 2026-08-14 (one failed, one completed).

`ops.processing_run` is empty — and **thirty-five tables across five schemas hang their
provenance on it**, including `working.normalized_record.provenance_id`,
`analysis.evidence_item.source_run_id`, `analysis.knowledge_evidence_promotion.source_run_id`,
`analysis.timeline_event.ingest_run_id`, `analysis.finding.provenance_id`,
`reference.detection_pattern_set.provenance_id`, and the entire location lane.

This is the reason all 11 spine rows have NULL provenance: the foreign key they would use points
at a table nothing populates.

**Verdict: PARALLEL-DUPLICATE by gravity.** These are not literal duplicates — they have genuinely
different granularity (one is orchestration stages, the other is a per-analysis provenance row).
But the ruled-authoritative ledger is referenced by 3 tables and the unruled one by 35, which
means the schema's provenance backbone and the owner's orchestration ruling point in opposite
directions. As Temporal takes over orchestration under D-067, that gap widens rather than closes.

There is a second problem underneath it: **`ops.processing_run` has no DDL in `sql/` at all.** Its
only in-repo definition is
`docs/planning/forensic-db-reconciliation/migrations/0005_forensic_reconciliation.sql:610`, a
script whose own header says it was "RUN BY HAND on the live (non-empty) volume."

**Recommendation:** this needs an owner ruling, not an agent's guess (question 2 in §10). The two
credible shapes are: fold provenance into `ops.workflow_run` and repoint the 35 foreign keys as
part of the Temporal cutover — one ledger, matching "one implementation per concept"; or keep both
and write down, in the decision log, that `workflow_run` is orchestration and `processing_run` is
analysis provenance, then actually start populating `processing_run`. What is not tenable is the
current state, where the most-referenced ledger in the schema has never held a row.

Also worth noting: `server/temporal/` writes nothing to `ops.*` today. `activities.py:4-5`
self-describes as "INERT... registered on a worker, never dispatched to by the live path yet,"
and `workflows.py:195,201` describe replacing the `gate_state` write with Temporal signals as a
future phase. D-067 is ruled but not yet built, which is consistent with the plan.

---

## 6. One case versus multi-matter machinery — mostly quiet, one loud spot

`analysis.matter` (1 row), `analysis.court_case` (1), `analysis.matter_knowledge_partition` (1).
Three tables, three rows, exactly as "it's just me and it's one case" implies.

**The question the owner actually asked is whether the shape is quiet.** The answer is: quiet in
one place, loud in the other.

**Quiet — `analysis.evidence_item`. CONFORMANT.** `matter_id` and `court_case_id` are both
nullable, with `CHECK ((matter_id IS NULL) = (court_case_id IS NULL))` — supply both or neither.
Nothing forces an evidence item to know a matter exists. This is exactly "invisible plumbing."

**Loud — `analysis.knowledge_evidence_promotion`. Non-conformant to rule 1, arguably justified.**
All three of `matter_id`, `court_case_id`, and `partition_key` are `NOT NULL` **with no default**.
Four foreign keys carry `matter_id` through composite keys. The `guard_knowledge_evidence_promotion`
trigger cross-checks matter and case identity in seven separate places, and requires the
`source_pointer` JSON to *repeat* `matter_id`, `court_case_id`, and `partition_key` and match the
columns exactly. Every promotion — the one action that turns knowledge into evidence — must
explicitly name a matter, a case, and a partition, or it is rejected.

**Verdict: UNCLEAR — needs the owner (question 1 in §10).** There is a real argument for the
loudness: promotion is the legal boundary, it is append-only, and pinning scope there is
defensible even in a one-case world. There is an equally real argument that the ruling said
suppressed and quiet, and this is the opposite. A trivial fix exists if the owner wants quiet —
default the three columns from the single `matter_knowledge_partition` row so callers never type
them — and it would not weaken the guard at all.

Everything else in the D-060 guard is **CONFORMANT** and well-built: it forces promoted evidence to
start `unreviewed`, HITL-required, unsafe for legal use, and unauthenticated; it verifies the
source-pointer hash; and it is append-only via `working.forbid_mutation()`. That is exactly
"evidence status only by explicit promotion." Zero rows so far — nothing has ever been promoted.

---

## 7. Test residue in production

### 7a. `ai.*` Agno knowledge tables — TEST-RESIDUE, confirmed

| Table | Rows | Content | Verdict |
| --- | ---: | --- | --- |
| `ai.casebible_evidence_test_contents` | 1 | "4-Ways-to-Use-Cursor-AI-for-Free" | **TEST-RESIDUE** |
| `ai.casebible_ingest_test_contents` | 2 | "agents", the same Cursor article — both `status = failed` | **TEST-RESIDUE** |
| `ai.casebible_ingest_test2_contents` | 2 | same two documents, retried, `status = completed` | **TEST-RESIDUE** |

Three tables, five rows, zero case relevance. The "test2" naming makes the story obvious: a smoke
test failed, was retried into a second table, and both were left standing.

`ai.platform_knowledge_contents` (20 rows) is **partially** residue: it contains
`ingest-smoke-test` (2026-06-20), and four documents re-ingested identically on three separate
dates (2026-08-01, 08-04, 08-11) — `perplexity-platform-followup-links`,
`v2-verification-and-repo-insights`, `agno-mcp-platform-mvp-handoff-guide-v8.1`,
`perplexity-framework-selection-agno-vs-haystack`. Twelve of its twenty rows are duplicate churn.

**Recommendation:** purge the three `*_test*` tables and the `ingest-smoke-test` row, and
de-duplicate `platform_knowledge_contents` to one copy per document. This is the
"purge the test data on success" rule, four to eight weeks overdue.

### 7b. `ai.casebible_evidence_contents` (24 rows) — NOT test data. LEGACY-EXITING, with a naming hazard.

This one is real. Sampling the 24 rows: `ChatGPT - Custody Case Opposing Party`,
`As-a-forensic-psychologist-is-likely-going-to-have`, `ChatGPT-Legal-AI---Custody-II` and `III`,
`ChatGPT-Personality-disorders-outcomes`, `Can-I-apply-for-a-fee-waiver`, plus fifteen more
ChatGPT conversation exports, all ingested 2026-06-25, all `status = completed`.

That is genuine case material. **But it is AI-chat context sitting in a table whose name says
"evidence", reached through the Agno Knowledge layer, with no promotion record behind it.**
`analysis.knowledge_evidence_promotion` has zero rows, so nothing here was ever promoted.
This is precisely the state D-060 was written to prevent — evidence status acquired by naming
convention instead of by an explicit, guarded, HITL-required act.

**Verdict: LEGACY-EXITING.** Agno Knowledge is on its way out (ruled intent 8), which resolves
this by attrition. Two things to do before it goes: make sure the 24 conversations exist in the
canonical context lane (§3) before the Agno layer is switched off — right now this table may be
their only home; and do not let the "evidence" in the name follow them anywhere.

### 7c. `evidence.source` (3 rows) and `evidence.evidence_hash` (3 rows) — TEST-RESIDUE

All three hash rows are labelled proof runs, in their own metadata:

- `/tmp/sms-real-sample.xml`, `"workflow": "sms-xml"`, 2026-08-11
- `/tmp/evidence-import-.../conversations.json`, `"source": "chatgpt-proof-20260812"`, 2026-08-12
- `/tmp/run-ledger-.../...md`, `"label": "native-pg-zero-skip-proof"`, `"validation_run": true`, 2026-08-14

All three are `/tmp/` paths from validation harnesses. **These are the only rows in the entire
19-table `evidence` schema.** The custody-bearing store contains nothing but proof-run artifacts,
and `evidence.custody_event` — which the 2026-08-23 mandate makes non-optional — is empty even for
these three.

**Recommendation:** purge all three after confirming nothing downstream cites their hashes, and
treat the empty `custody_event` as the acceptance test for the standalone hasher: the first real
capture should produce a source row, a hash row, **and** a custody event, or the hasher is not done.

---

## 8. The (b) bucket — superseded or dead (34 tables)

Nothing will write to these again. All are retained under the never-delete rule.

**`public` legacy island — LEGACY-EXITING (3):** `agent_run`, `approval_request`,
`transcript_insight`. Created by `sql/0002_schema.sql:23,37,72`, which carries an explicit
comment at `:17-20`: "LEGACY (2026-06-12): agent_run + approval_request are SUPERSEDED by the
native agno approvals store... no code writes here anymore." Confirmed: zero code references.
`server/api/main.py:171` records the route removal. Handled correctly; no action.

**Retired staging — LEGACY-EXITING (3):** `working.extraction_candidate`,
`working.record_observation`, `working.extraction_batch`. See §4. Handled correctly; no action.

**Unwired CDC outbox — PARALLEL-DUPLICATE (7):** `working.chat_conversation_event`,
`chat_message_event`, `chat_chunk_event`, `chat_chunk_lane_event`, `chat_cdc_cursor`,
`chat_projection_dead_letter`, `context_asset_event`. DDL with no consumers. See §3a.

**Orphaned context model — PARALLEL-DUPLICATE (1):** `working.context_record`. Not empty
(1,741 rows) but code-dead. See §3.

**Agno tables we are exiting — LEGACY-EXITING (9 empty of 27):** `ai.agno_approvals`,
`agno_component_configs`, `agno_component_links`, `agno_components`, `agno_eval_runs`,
`agno_knowledge`, `agno_memories`, `agno_schedule_runs`, `agno_schedules`, plus
`ai.evidence_knowledge_contents`. Legacy runtime, not architecture (ruled intent 8). Note that
`agno_memories` being empty is consistent with the known `EntityMemoryConfig` no-op.

**Test-residue tables — TEST-RESIDUE (3):** the three `ai.casebible_*_test*` tables from §7a.

**`working.promotion` — UNCLEAR-leaning-dead (1):** created by `sql/0016:438`, protected by an
append-only trigger at `sql/0017:43-67`, referenced by no application code whatsoever.

---

## 9. The (c) bucket — unclear (16 tables)

These share one root cause. `docs/planning/forensic-db-reconciliation/migrations/0005_forensic_reconciliation.sql`
was **applied by hand to the live volume** and created twelve-plus objects the numbered `sql/00NN`
chain has never seen. `sql/README.md:12-14` already admits the numbered migrations "are not an
empty-database bootstrap path after 0007." So these tables exist, but the repository does not
contain the migration that made them.

**Version registries (5), all empty, zero code:** `public.prompt_registry`, `model_version`,
`schema_version`, `ontology_version`, `classification_version`. These exist to serve
`ops.processing_run`'s five `*_version_id` columns — a ledger that has never held a row (§5).
Their fate follows the run-ledger ruling.

**Work-product memory (6), all empty, zero code:** `public.memory_items`, `decision_log`,
`session_summaries`, `open_questions`, `decision_precedent`, `change_log`. These were designed as
a database-side memory and decision layer. In practice that job is done by `docs/DECISION_LOG.md`,
`docs/CHANGE-ORDER.md`, and the file-based memory lane. **Caution on `change_log`:** a live
database trigger reads it to build a hash chain (`sql/bootstrap/schema_baseline.sql:819`). Do not
drop it without disarming that trigger first.

**Two orphans with rows and no migration source (2):**

- **`public.canon_registry` (4 rows) — the highest-value orphan in the database.** It holds the
  custody-hash canon: `h1-rawbytes-v1` (active), `h2-canonical-v2` (active, "CURRENT canon for
  ALL new ingests"), `h3-chain-v1` (active, "PROVEN 2026-07-02... 1918/1918 links recomputed"),
  and `h2-filebound-v1` marked `lost` with the note "THE loss that motivated this table." Each row
  carries the exact recipe, the reference implementation path, and test vectors. **This is
  irreplaceable governance data, and repo-wide search finds it in exactly one file — the pg_dump
  baseline.** There is no migration that creates it and no code that reads it. If this database
  were rebuilt from `sql/`, the canon registry would not exist.
- **`public.app_setting` (4 rows)** — clustering thresholds (time gap 7200s, similarity 0.6,
  embedding model `all-MiniLM-L6-v2`, cluster id format). Same provenance hole, lower stakes, and
  note the embedding model recorded here is not the one the platform now uses.

**Recommendation:** the fix for all sixteen is one action, not sixteen — capture the hand-run
script's surviving objects into a numbered migration so the repository can rebuild what is
actually live. `canon_registry` should be first and should also get a reader, because a canon
nothing consults is a canon that will drift.

---

## 10. Everything else, briefly

**`duckdb.extensions`, `duckdb.tables` — CONFORMANT (not ours).** Both are owned by the
`pg_duckdb` extension — confirmed live via `pg_depend.deptype = 'e'`. Created as a side effect of
`CREATE EXTENSION pg_duckdb` at `sql/0001_init_extensions.sql:38`. Zero rows is the correct empty
state. Do not add them to a migration; do not count them against us.
`public.spatial_ref_sys` (8,500 rows) is PostGIS's own table, same story.

**The location / Timeline lane — INTENDED-FUTURE (owner-parked, ~17 tables).**
`working.gps_track`, `stay_point`, `location`, `waypoint_device_split`, `geocode_request`,
`geocode_resolution`, `geocode_result`, `home_base`, `vehicle`, `device`, `device_ownership`;
`evidence.gps_point`, `raw_trip`, `raw_visit`, `raw_path`, `raw_activity`; `reference.geofence`;
`ops.geocode_audit`. All empty with **zero code references** — which is the correct state, because
the Takeout Timeline integration is owner-parked and is not to be proposed. Empty here is
compliance, not rot.

**The raw layer — INTENDED-FUTURE.** `evidence.raw_sms`, `raw_imessage`, `raw_facebook`,
`raw_ai_chat`, `raw_csv`, `raw_phone`, `raw_rejected`. Empty, but wired — referenced by
`server/tools/parsers/messaging/sms_xml.py`, `server/tools/repair/types.py`, and
`scripts/evidence_pipeline_report.py`.

**Legal workflow (`analysis.*`) — INTENDED-FUTURE (28 tables).** `discovery_request` (+revision),
`export` / `export_item` / `export_package`, `finding` / `finding_version`, `review_task` /
`review_decision`, `redaction`, `score`, the five `task_*` tables, `factor_citation`,
`completion_evidence`, `corroboration_flag`, `resolution_evidence`, `legal_timeline_event`,
`pattern_finding`, `relational_classification`, `location_assertion`, `location_contradiction`,
`time_assertion`, `timeline_event`. Nearly all have zero code references. They are the downstream
half of a pipeline whose upstream half has not run yet, and several carry correct append-only
triggers already. Nothing to do until evidence actually flows.

**Reference data — CONFORMANT.** `detection_pattern` (527), `behavior_category_mcl` (225),
`behavior_category` (164), `pattern_lexicon` (51), `custody_factor` (12), `topic_code` (10),
`detection_pattern_set` (1). Real curated content. Eight empty lookups
(`format_resolver`, `geofence`, `knowledge_tag`, `legal_issue`, `legal_issue_factor`,
`lexicon_sync`, `relative_rule`, `score_band_config`) are intended-future.

**`analysis.human_label` (1,918) and `human_label_gold` (1,918) — CONFORMANT.** Not a duplicate.
`human_label_gold` has the identical column set plus `legacy_message_id` and `archived_at` — it is
an immutable archive snapshot taken when message identifiers were relinked. This is
human-curated ground truth, which the rules class as precious. Preserved, not deleted. Correct.

**Naming split, `disclosure_horizon` vs `disclosure_tier` — UNCLEAR, already logged as TODO-213.**
Verified live and the split is exactly as recorded: the knowledge-timing concept exists under two
names and two typings — a proper enum `disclosure_horizon` on `analysis.time_assertion` and
`analysis.timeline_event`, and a plain `TEXT` + CHECK `disclosure_tier` on
`working.normalized_record` and its views. **Both carry the identical value set**
(`contemporaneous`, `hindsight`, `discovered`), so the vocabulary conforms; only the column name
and the type differ. Separately confirmed clean: the access concept is correctly named
`sensitivity_tier` everywhere it appears (nine tables and views), with values
`public` / `restricted` / `sealed`. The old collision is genuinely gone. No new finding here —
TODO-213 already has the right consolidation direction and is correctly owner-gated.

---

## 11. Owner questions

Five questions. Everything else in this report either needs no decision or is already decided.

**1. The promotion gate insists on naming a matter and a case. Should it?**
Every other table treats the single matter as optional plumbing, exactly as you ruled. The
knowledge-to-evidence promotion ledger is the one exception: it requires a matter, a court case,
and a partition on every row, with no defaults, and its guard checks them seven times.
*Leave it loud:* promotion stays the one place scope is stated explicitly, which is defensible for
the legal boundary but is the opposite of "suppressed and quiet."
*Make it quiet:* default all three from the single partition row so no caller ever types them,
with the guard unchanged — costs one small migration and nothing else.

**2. One run ledger or two?**
Thirty-five tables across five schemas hang their provenance on a ledger that has never held a
row, while the ledger you ruled authoritative is referenced by three tables and holds two rows.
*One ledger:* fold provenance into the authoritative one and repoint all thirty-five foreign keys
during the Temporal cutover — matches "one implementation per concept," but touches a lot at once.
*Two ledgers:* write down that one is orchestration and the other is analysis provenance, then
actually start populating the second — cheaper now, but leaves two run concepts to keep straight
forever.

**3. The context lane's data and its code are in different tables. Migrate, or start fresh?**
1,741 AI-chat rows sit in the old table with no code; the new table the code writes to is empty.
The old rows are already projected into Weaviate and Graphiti and are their only source of truth
in Postgres.
*Migrate:* move the 1,741 rows into the new model, keep the downstream projections intact.
*Start fresh:* re-ingest from the original exports and let the old table go cold — cleaner, but
only safe if you still hold every original export, and it means Weaviate content is temporarily
unsourced.

**4. Five rows of a test probe are stuck in an append-only ledger. What now?**
The probe on 24 August wrote conversations titled "Ingestion readiness probe (DELETE ME)". The
base rows were purged as the rules require, but the change-event ledger is append-only by design,
so the events survive and no normal path can remove them.
*Leave them:* the ledger stays honestly append-only, and permanent test rows sit in it forever.
*Truncate the event tables:* they have zero consumers today and zero real data, so nothing breaks
— but it establishes that append-only ledgers can be reset, which is a precedent worth choosing
deliberately.

**5. The custody-hash canon lives only in the live database, with no migration and no reader.**
The four-row registry holding your hash recipes, test vectors, and the record of the one lost
canon exists nowhere in the repository except a captured database dump. Rebuild from source and it
is gone. Nothing in the codebase reads it.
*Capture it:* write the hand-applied objects into a numbered migration and add a startup check
that compares the running hasher against the registry — the canon becomes enforceable.
*Leave it:* it is backed up with the database, and the recipes are also written in the plugin
tooling — but a canon nothing consults is a canon that drifts.
