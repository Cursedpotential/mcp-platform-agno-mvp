# Batch Re-Ingestion ETL Pipeline — Design

> _Byline: data-engineer subagent · via Claude Code Fable 5 · 2026-08-02_

**STATUS: DRAFT — PENDING OWNER APPROVAL.** Nothing here is applied. No code, SQL,
or config was touched to produce this document — it is a design read against the
live repo state on `fix/knowledge-legal-root-and-entity-memory-mode` today.

---

## 0. Answer first

- The DB is empty (`evidence.raw_*`/`evidence.source`/`working.*` = 0 rows); every
  original file survives; everything is re-ingestable. Good — this is a clean
  re-derive, not a recovery.
- **Two things must be fixed before ANY reingest run, batch or not** (Section 1)
  — they are not parser bugs, they are pipeline-integrity gaps:
  1. `server/evidence/workflows.py` (the only *committed*, agno-orchestrated
     ingestion path on this branch) writes to `analysis.normalized_record` — a
     table that no longer exists post-schema-split. It has **not** been updated
     to the raw→working architecture this task brief describes. The pipeline
     that actually implements raw→working (with `ingest_run`/`raw_rejected`
     funnel + reconciliation) exists only as a **scratchpad script**
     (`e2e_stream.py`) on a sibling worktree, never productionized.
  2. The SQL migrations that create `evidence.ingest_run`, `evidence.raw_rejected`,
     the six `evidence.raw_*` tables, and the `working`/`reference`/`ops` schema
     split (numbers 0008–0015) are **applied to the live DB** but **committed on
     a different, unmerged branch** (`chore/sbv-upstream-sync`). This branch's
     own `sql/` only goes 0001–0007 then jumps to 0016, which explicitly
     depends on 0014 having run. Git and Postgres currently disagree about
     which branch owns this schema.
- Phase 0 (one file per format, on `ai_test_ingest`) is **already half-built and
  already run once** this session: `scripts/parser_smoke.py` parses one real
  file per format and reports pass/fail with **no DB write**. Today's result:
  4/6 formats OK, 2/6 fail (messaging-csv, PDF/OCR — root-caused in Section 4).
  Reuse this script; extend it one tier to also write through custody→raw→derive
  on `ai_test_ingest` for the true Phase-0 gate.
- Every reconciliation view named in the task brief (`vw_pipeline_funnel`,
  `vw_reconciliation`, `vw_dropped_records`) is real, applied, and already
  proved itself catching a genuine data-loss bug this session (516 dropped MMS,
  masked by an off-by-one funnel gate before the fix). Reuse them for every
  phase's go/no-go — do not build new counters.

---

## 1. Precondition — fix before Phase 0

A data pipeline is only as trustworthy as its schema lineage. Two lanes wrote
to the **same live Postgres instance** without merging:

| Branch / worktree | What it committed | State |
|---|---|---|
| `chore/sbv-upstream-sync` (worktree `_worktrees\sbv-upstream-sync`) | `sql/0008_temporal_clocks_and_provenance.sql`, `sql/0009_raw_layer_and_derivation.sql` (the six `evidence.raw_*` tables), `sql/0012_pipeline_visibility.sql` (`ingest_run`, `raw_rejected`, funnel/reconciliation views), `sql/0013` (`vw_raw_all` union), `sql/0014` (schema split → `working`/`reference`/`ops`), `sql/0015` (view rebuild) — **all applied live** | Not merged into this branch |
| `fix/knowledge-legal-root-and-entity-memory-mode` (this branch, current checkout) | `sql/0001`–`0007` (base schema, custody, run ledger, gates), `sql/0016_working_gate_layer.sql` (candidate/review/promotion gate — depends on 0014 having run) | Missing 0008–0015 in its own git history |

**Why this blocks a batch job specifically:** a batch reingest that runs
migrations, or that a second agent/session applies against `ai_test_ingest`
from *this* branch's checkout, will not see `evidence.raw_sms` or
`evidence.ingest_run` in its own tracked `sql/` — because those files live on
the other branch. `scripts/make_test_db.py` clones the LIVE schema (so
`ai_test_ingest` is fine today), but the git history backing that schema is
split, and the next migration number collision (0008/0009 were already
claimed twice this session) is one merge away from happening again.

**Recommendation (owner decision, not autonomous):** merge or rebase
`chore/sbv-upstream-sync`'s `sql/0008`–`0015` into this branch before treating
`sql/0016` as buildable-on-top, and renumber forward from 0017. This is a
20-minute `git merge`/cherry-pick + a`sql/` diff review, not a schema redesign
— the DDL is already proven against the live DB.

---

## 2. Stage map

Every stage: **who writes, what tables, how it survives a re-run, how it fails.**

| # | Stage | Writer (code) | Tables touched | Idempotency | Failure behavior |
|---|---|---|---|---|---|
| 0 | Acquire | human / file drop | none | n/a — files never move once acquired | n/a |
| 1 | Custody (H1) | `server/evidence/custody.py::ingest_artifact()` — **sole writer** of `evidence.*` custody tables | `evidence.source` (write-once trigger `source_immutable`), `evidence.evidence_hash` (level H1) | sha256 dedupe: re-ingesting identical bytes returns the **existing** `artifact_id` (`duplicate=True`); blob path embeds the hash so a second write is a no-op | Exception before any row lands for a genuinely new file; nothing partial to clean up. SBV path adds H2 (per-record)/H3 (chain) via `record_evidence_hash()` only on a verified H1 cross-check match — mismatch records `integrity_violation`, never fabricates H2/H3. |
| 2 | Ledger open | ingest driver (today: scratchpad `e2e_stream.py`; needs productionizing — see §1) | `evidence.ingest_run` (status=`running`, `count_claimed` = file's declared count) | one row per attempt; re-running an already-failed file opens a **new** row | Written on a **separate AUTOCOMMIT connection**, deliberately outside the main transaction, so a crash/rollback anywhere downstream still leaves this row — proven this session (a real `relation does not exist` failure showed up correctly in `vw_ingest_history` as `status='failed'`). |
| 3 | Parse | registry-resolved parser (`server/tools/parsers/**`, e.g. `sms_xml.py`) | none directly — in-memory transform, streamed via `iterparse` where the format allows | pure function of file bytes; re-running just re-parses | Tool raises → caller marks the tool's attempt failed; `registry.resolve()` returns same-capability alternates (substitution), except `sms-xml`'s primary/fallback pair which **pauses instead of silently substituting** (owner mandate — see §5). |
| 4 | Reject/reconcile | parser's `on_reject` callback | `evidence.raw_rejected` (reason CHECK: `no_timestamp_no_counterparty`, `dedup_duplicate_in_source`, `parser_returned_none`, `unmapped_element`, `malformed`, `operator_excluded`) | one row per refused record, at the moment of refusal, never batched-then-lost; `ON DELETE RESTRICT` protects the audit trail from a cascading delete | A rejection is data, not an error — the row lands whether or not the overall run later fails. |
| 5 | Raw store | same parser/derive step | one of `evidence.raw_sms` / `raw_imessage` / `raw_facebook` / `raw_csv` / `raw_ai_chat` / `raw_phone` (FK → `evidence.source`) | dedupe key `(device_id, medium, content_hash)` **NULLS NOT DISTINCT**; guarded by `NOT EXISTS` so re-deriving the same file is a no-op, not a duplicate append (this is the fix that made a 667 MB re-run land bit-for-bit reconciled) | **Completion gate is `raw == parsed − collisions`**, not `raw == parsed` — the earlier equality gate rolled back a *correct* run because dedupe legitimately makes `raw < parsed`. Get this comparison right in any batch runner; getting it wrong either false-fails good runs or false-passes bad ones. |
| 6 | Derive spine + projections | a "derive" step reading `evidence.raw_*` only | `working.normalized_record` (spine), `working.message`/`conversation`/`attachment`/`call_log` (projections), `working.event_source_record` (attestation link — same message from multiple sources = one spine row, all sources recorded) | **Fully re-derivable from raw alone** — `rebuild_cost` = "re-derive from raw" per `vw_layer_map`. Safe to truncate+rebuild wholesale after a derivation-logic change. `NOT EXISTS` guards make repeat runs no-ops. | Re-run the derive step; nothing upstream is touched. **Scope every derived write/count to the current `source_id`** — an earlier bug filtered attestation inserts only on table name, not source, and fabricated 445 false "corroborated" records by re-attesting an unrelated earlier file's rows. |
| 7 | Extract candidates (Semantica/NER) | **not yet wired** — schema exists (`sql/0016`), extractor code does not | `working.extraction_run`, `working.candidate_entity`/`candidate_fact`/`candidate_event`, `working.source_provenance` (six clocks, append-only revisions) | `content_sha256` unique dedup index per source row within a run; a model/extractor version change opens a **new** `extraction_run` — old candidates are never mutated, only superseded | `extraction_run.status='failed'` with partial `stats` jsonb; candidates already inserted stay, traceable to the run that produced them (a bad model version can be mass-rejected by `extraction_run_id`, not hunted row by row). |
| 8 | HITL review gate | human, via `working.review_decision` | `working.review_decision` (append-only), `candidate_*.review_state` | A correction is a **new** `review_decision` row, never an `UPDATE` — "who approved this, on what basis" must survive later edits. `working.review_queue` view is the reviewer's worklist (pending, lowest-confidence-first). | No review UI exists yet for this layer. **Recommend reusing the existing `mode='supervised'` gate primitive** (`analysis.workflow_run.gate_state` / `read_gate`/`set_gate` in `run_ledger.py`) rather than inventing a second HITL mechanism — the poll-with-24h-abort-ceiling pattern already works and is tested. |
| 9 | Promote per lane | promotion step, reads **approved-only** candidates | `working.promotion` (lane ∈ `as_lived`/`hindsight`/`consolidated`/`support`; `target_system` DB-enforced to match lane) | `promotion_live_idx` unique on `(candidate, lane, target)` WHERE not revoked — re-promoting an already-live candidate is a conflict, not a duplicate write. Revocation is a new row (`revoked_at` set), never a delete. | CHECK constraints make `promoted_at IS NULL OR review_state = 'approved'` structural — a promotion of an unapproved candidate cannot physically insert. |
| 10 | Fan-out | per-target adapter (Graphiti / Neo4j-Semantica / SurrealDB / Weaviate) | external stores, not Postgres | Each target's push is independent; retried with the existing bounded-backoff pattern (`server/evidence/store.py::_retry_async`/`_retry_sync`, already classifies Weaviate/Milvus/DB transient errors — generalize to Graphiti/Surreal/Neo4j clients) | **`as_lived` (Graphiti) promotion must be withheld until `working.current_provenance.realized_at_state = 'confirmed'`** — promoting on acquisition/ingestion time instead of `realized_at` destroys the belief-state record the whole knowledge-horizon mechanism depends on (AGENTS.md §WHY). This is the single easiest way to quietly break the project's actual point. |

**Two ledgers, different altitude — do not conflate them:**
`analysis.workflow_run`/`workflow_run_stage` (the C0 operator-console ledger,
`server/evidence/run_ledger.py`) is per-agno-workflow-run, stage-level
telemetry, and already has the supervised-gate/abort/retry machinery built and
tested. `evidence.ingest_run`/`raw_rejected` is per-**file**, funnel-count
telemetry, autocommit-safe. They currently have **no cross-reference** —
recommend adding a nullable `workflow_run_id` column to `evidence.ingest_run` so
a batch run's per-file funnel rows can be joined back to the orchestrating
workflow run that produced them.

---

## 3. Phase plan

### Phase 0 — smoke, one file per format, `ai_test_ingest`

- **Harness:** extend `scripts/parser_smoke.py` (already exists, already run,
  currently parse-only/writes-nothing) one tier further: parse → custody →
  raw → derive, still against `ai_test_ingest` (schema-only clone, real row
  counts via `query_to_xml`, never `n_live_tup`).
- **Owner review artifact:** `scripts/evidence_pipeline_report.py`, run with
  `--no-content` (a prior report leaked a real name/DOB/SSN into
  `docs/reports/*` — that directory is gitignored now; keep it that way for
  every phase).
- **Go criteria (per format):**
  - `vw_reconciliation` shows `RECONCILED` (claimed = raw + rejected) for that
    file's `ingest_run` row.
  - `vw_dropped_records` has zero rows for that file with a reason **not** on
    an owner-reviewed allowlist.
  - `vw_pipeline_funnel` shows `count_raw > 0` (not stuck at zero).
- **No-go today (already known, from the last real smoke run):** messaging-csv
  and PDF-via-`extract.text` fail smoke. Do not advance either format to
  Phase 1 until Section 4's fixes land and re-pass smoke.
- **4/6 formats already pass** (sms-xml calls + sms, facebook-json,
  imessage-html) — these can proceed to Phase 1 independently; formats do not
  have to move as a batch.

### Phase 1 — one file per format, live `ai` DB

- Same go/no-go as Phase 0, run against the real database instead of the
  clone, PLUS:
  - Confirm the real R2 blob write path (custody stage) and the
    `evidence.source` write-once trigger both behave against production
    infrastructure, not the test clone's simplified path.
  - Confirm the derive step actually populates `working.normalized_record`
    (Phase 0 already proved this against the clone; Phase 1 proves it against
    the box the case actually depends on).
  - **Gate:** Section 1's branch/migration reconciliation must be resolved
    before this phase starts — Phase 1 writes to the live DB and a git-history
    gap here is a "which migration owns this table" argument you do not want
    mid-ingest.

### Phase 2 — full-corpus volume, ordered by parser confidence

Order (best-proven first):

1. `sms-xml` — already proven end-to-end this session at real volume
   (13,664/13,664 claimed=parsed reconciled on a 667 MB Android export, after
   the bodyless-MMS fix).
2. `facebook-json`, `imessage-html` — passed smoke, not yet run at volume.
3. `messaging-csv` — **blocked**, fix required (§4.1).
4. `documents.extract-text` / `imessage_pdf` — **blocked**, fix required (§4.2).
5. `ai_chat/*` (chatminer-backed + 2 custom parsers) — routes to the
   **knowledge** engine only (`server/evidence/store.py::ingest_into_knowledge`,
   domain-tagged Weaviate), never to `evidence.raw_*`. Not "Phase 2 volume" in
   the evidence sense at all — track separately so it never gets swept into
   the same batch runner that touches custody tables.

**Go/no-go per format-batch:**

- `vw_reconciliation` = `RECONCILED` for **every** `ingest_run` row of that
  format, not just an aggregate.
- `vw_dropped_records` = zero unexplained rows.
- **Content spot-check, not just count reconciliation** — the funnel matching
  (claimed=raw+rejected) does not by itself prove correctness. This session's
  own incident is the proof: after the first fix, counts were 13,663 vs
  13,664 — a single dropped MMS whose only text part was a lone `'\n'`
  character. The count was *almost* right, which is exactly the shape of bug
  a numbers-only gate misses. Pull N random `working.normalized_record` rows
  per format-batch and manually diff against the source raw record before
  declaring a batch clean.

---

## 4. Known blockers — fix before Phase 2 (with effort)

### 4.1 `messaging-csv` rejects SMS Backup & Restore CSV (262 files)

**Root cause, read directly from `server/tools/parsers/messaging/messaging_csv.py`:**

- `looks_like_messages_csv()` gates acceptance on `has_ts` matching one of
  `_TS_KEYS` — a fixed alias list (`"date"`, `"date sent"`, `"timestamp"`, …).
  SMS Backup & Restore's actual timestamp column is `readable_date`, which is
  **not in that list** (no substring match — exact key match only after
  whitespace normalization). The file fails the `accepts()` gate before
  parsing even starts.
- Secondary, once the timestamp fix lands: `_direction()` expects the `type`
  column to hold word tokens (`sent`/`received`/…); SMS Backup & Restore
  encodes `type` as the same **numeric protocol code** (`1`=received,
  `2`=sent) that the sibling `sms_xml.py` already decodes via its
  `_SMS_TYPE` table. Right now a numeric `type` value just fails to match any
  direction token and silently returns `direction=None` (not a hard reject,
  but a data-quality loss — direction is inferable and shouldn't be dropped).

**Fix:** add `"readable_date"` to `_TS_KEYS`; route numeric `type` values
through `_SMS_TYPE` (share the table with `sms_xml.py` instead of duplicating
it). **Effort: small — 1–2 hours** including a regression test against a real
sample file; no schema change, no migration.

### 4.2 PDF OCR stack missing

**Root cause:** `server/tools/extractors/extract_text.py` already implements
the full tiered design (native pypdf/pdfplumber → pytesseract+pdf2image OCR
fallback → optional heavy-provider escalation), with graceful imports so a
missing library degrades to a clear error instead of a crash. The gap is
**deployment, not code**: `pytesseract` + the system `tesseract-ocr` and
`poppler-utils` binaries are not installed in the runtime image/venv this
pipeline runs in.

**Fix:** add the two system packages to the relevant container image (wherever
this parser executes — currently the platform-tools/facade image) and
`pytesseract`/`pdf2image` to the pinned Python deps; verify against one real
scanned PDF; confirm CPU-only cost is acceptable (no GPU per the hardware
constraint — Tesseract is CPU-native, so this should be free). **Effort:
small–medium — 2–4 hours** including image rebuild + redeploy + one
end-to-end verify.

### 4.3 Malformed-XML fallback defeats streaming

**Root cause:** `sms_xml.py` streams the primary parse via
`ET.iterparse` (clears elements as it goes — this is what makes multi-GB
backups safe). Its sanitize-and-retry fallback, triggered only on a
`ET.ParseError` (stray ampersands, common in these dumps), calls
`path.read_text(encoding="utf-8", errors="replace")` — loading the **entire
file into memory** before re-parsing.

**Fix:** either (a) a chunked/generator-based sanitizer that still feeds
`iterparse` incrementally, or (b) switch the fallback to `lxml`'s
`recover=True` mode, which tolerates malformed XML without a whole-file
materialize step. **Effort: medium — 4–8 hours** including a synthetic
large-malformed-file regression test. **Lower priority than 4.1/4.2** — this
is a tail-risk path (only triggers on genuinely malformed input) and no file
in the current corpus has hit it yet; don't block Phase 2 start on this one,
but fix it before running the single largest/oldest exports where malformed
XML is most likely.

---

## 5. Reprocessing semantics — what re-runs, what never does

| Layer | Rebuild cost | Re-run behavior |
|---|---|---|
| `evidence.source` / `evidence.evidence_hash` | n/a — **never rewritten** | Write-once trigger (`source_immutable`). Re-ingesting the same file dedupes to the existing `artifact_id`; it does not create a second custody row. |
| `evidence.raw_*` | Re-parse originals | A parser fix (e.g., the CSV fix in §4.1) should make re-running against the same source file a safe **re-derive**, not a duplicate append — this requires a natural-key/`NOT EXISTS` guard on the raw insert (already the pattern used for the sms-xml fix this session; apply the same discipline when backfilling CSV/PDF). |
| `working.*` (spine, projections, links, gate-layer candidates) | Re-derive from raw only | Fully disposable and rebuildable — safe to `TRUNCATE`+rebuild after a derivation-logic change, since raw is the only source of truth. **Exception:** `working.review_decision` and `working.promotion` are human judgement, append-only, and must **never** be wiped by a working-layer rebuild. A rebuild that regenerates `candidate_*` rows must re-associate old approvals by `content_sha256` (or force re-review) — never silently drop an existing approval because its underlying row got a new UUID. |
| `working.extraction_run` / candidates | Versioned by `extractor` + `extractor_version` + `model_id` | A model/extractor change is a **new** `extraction_run`; old candidates are left in place (untouched history) or explicitly marked `review_state='superseded'` by a fresh pass — never edited in place. This is what lets a bad model version's output be identified and mass-rejected without touching anything a human already approved. |
| `analysis.*` (human-gated: `human_label`, `human_label_gold`, findings) | Not rebuildable by this pipeline at all | **1,918 rows survived today's wipe on purpose.** A batch reingest must never touch `analysis.*`. If a re-derive changes an ID that a label references, that is a breaking change requiring an explicit, reviewed remap — never a silent drop. |
| `reference.*` (curated taxonomy) | Re-seed from source, but not by ingestion | 990 rows survived the wipe. Only touched by taxonomy curation work, never by the reingest pipeline. |

---

## 6. Anti-goals

- **No dual stores per knowledge horizon.** Graphiti / Semantica-Neo4j /
  SurrealDB are **destinations for the same gated fact**, not parallel
  corpora. A single approved candidate can legitimately promote into more
  than one lane (`promotion_live_idx`'s composite key on `(candidate, lane,
  target)` exists precisely for that), but there is exactly **one** gated
  source (`working.candidate_*` + `working.promotion`) — never a second
  per-store staging table.
- **No automatic writes past the HITL gate.** Every fan-out write (stage 10)
  must trace to an approved `working.review_decision` **and** a
  `working.promotion` row. A pipeline that pushes a candidate to
  Graphiti/Neo4j/SurrealDB directly off `review_state='approved'` without
  going through the promotion ledger violates the gate even if the human
  judgement was correct — the ledger is the only durable record of what
  crossed and when.
- **No AI chats in evidence lanes.** The chatminer-backed `ai_chat/*` parsers
  (9 chatminer, 2 custom: claude.ai export JSON, Claude Code JSONL) route to
  the **knowledge** engine only — never `evidence.raw_*`/`evidence.source`/
  `working.normalized_record`. This is already structurally true (the
  chat-transcript workflow is a separate code path from sms-xml), but a batch
  runner must not accidentally point an AI-chat file at the evidence-side
  parser registry, since `registry.resolve()` matches on capability string,
  not on "is this evidence" — a mis-tagged capability could cross the line.
- **No silent substitution.** `sms_xml`'s existing behavior — primary (~~SBV~~ pure-Python; SBV DEMOTED 2026-08-02 (gap-review P0-1: unscoped /api/activity))
  parser failure **pauses** the run with explicit options rather than
  auto-falling-back — must be preserved in batch mode. A batch runner must
  default `allow_fallback=False` across the whole corpus; a backup parse must
  never be indistinguishable from the primary in the stored record (the
  existing `alt_parse`/`alt_parse_detail` flagging already does this — reuse
  it, don't bypass it for throughput).
- **No PII in git.** `evidence_pipeline_report.py` already leaked a real
  name/DOB/SSN once this session before `docs/reports/*` was gitignored and
  `--no-content` added. Any batch-reingest tooling that emits a report or log
  artifact defaults to content-redacted output; raw content stays in the DB
  and the R2 blob store, never in a committed file.

---

## 7. Open questions for the owner

1. **Merge order for §1's branch split** — cherry-pick `sql/0008`–`0015`
   forward onto this branch before renumbering `sql/0017`+, or rebase this
   branch onto `chore/sbv-upstream-sync`? Either works; picking one avoids a
   second migration-number collision.
2. **Who owns productionizing `e2e_stream.py`** into the real orchestrated
   ingestion path — extend `server/evidence/workflows.py`'s existing
   agno-`Step` pattern (reuse `on_error="fail"`, the ledger-wrapping, the
   supervised-gate primitive) or keep it a standalone script? The stage map
   in §2 assumes it becomes a real workflow so the operator-console ledger and
   the ingest-run ledger can cross-reference (§2's `workflow_run_id` note).
3. **Extraction stage (§2 row 7) has no extractor implementation yet** — this
   design assumes Semantica/NER lands before Phase 2 volume runs need it, but
   Phases 0/1 (raw→working only, no extraction) do not depend on it. Confirm
   whether Phase 2 should wait for the extractor or proceed raw→working-only
   and backfill extraction later as its own pass.
