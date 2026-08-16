# DEBT / STUB Register

> _Byline: Claude Code · Sonnet 5 · 2026-08-09 (docs/registers true-up: knowledge_filters/Weaviate
> correction, agno pin correction, STUB-rule test scoping, parser-lane queue update, justified-custom
> addition, dated audit stamp);
> drift-fix 2026-08-12 (Claude Code · Kimi K3: Milvus "locked + LIVE" row corrected — ADR-0040/D-042 supersession)_
> _2026-08-13 amendment: Codex · GPT-5 (ADR-0053 implementation follow-ups)._
> _2026-08-14 amendment: Claude Code · glm-5.2:cloud (independent-review report corrections — see
> "Report re-verification corrections" below; Wave 0 live inventory + fresh-restore gate — see
> "Wave 0 live inventory findings" below)._
> _2026-08-15 amendment: Codex · GPT-5 (legacy custody-digest readiness verifier debt)._
> _2026-08-16 amendment: Codex · GPT-5 (Swift MVP ingest/Chonkie observed-state tracking)._

## Horizon Swift MVP audit items (2026-08-16)

| Audit item | Observed state | Remaining work / hold |
|---|---|---|
| Agno-owned ingest | **Resolved for the Swift path:** HTTP, folder-walk, and in-process callers share `server.contracts.ingest` / `server.ingest.service`; public contract tests reject Agno/Graphiti/Surreal/AI-SDK imports. Scratch PostgreSQL received both Markdown and an SBV-covered export. | Legacy Agno workflows remain adapters until their separate retirement wave; no retirement is part of Swift MVP. |
| Empty SBV password silently selects Python | **Resolved on the observed Swift surface:** the live `exec-platform-tools` application has a runtime service credential; a guarded scratch receipt completed through `sbv-go:smsbackuprestore-xml` with fallback disabled. | Any future deployment must keep fail-closed credential checks; no production deployment was changed by this proof. |
| Chonkie absent from production lock/runtime | **Resolved:** `chonkie[semantic,code,table]==1.7.0` is a base dependency; production `requirements.txt` contains no torch/transformers stack. Neutral ingest and Agno reader policies execute Chonkie and record versioned IDs with explicit units. Final scratch proof: Markdown 1 logical record → 3 stored chunks; SBV Go 1 → 1; both `chonkie.recursive@1.7.0:1500-chars`. | Neural/Late/Slumber remain remote-only by D-046; the remote executor and chunk-preview GUI are deferred and must never trigger a local torch install. |
| Semantica config-only | **Open.** | Swift Slice 4 must produce observed candidate + provenance rows through a governed promotion boundary with no custody credentials/direct graph writes. |
| Workbench lacks Vercel AI SDK stream | **Open.** | Swift Slice 3 must add the SDK and stream through a framework-neutral `/v1` route. |
| Parked Surreal vs new disposable target | **Held.** Logical adapter/design work is allowed; the parked deployment remains denied. | R12 requires separate target/credential/implementation authority. If not granted, finish the adapter + compose overlay + owner HITL packet only. |

_Byline: Codex · GPT-5 · 2026-08-16._

## Court-readiness compatibility debt (2026-08-15)

- **Version the custody-event digest writer/verifier.** The existing trigger hashes a
  session-timezone-rendered timestamp without recording a construction/timezone version.
  The read-only Matter readiness endpoint safely verifies 2026-era rows by testing the
  complete modern civil-offset grid (105 candidates per event), and the rollback harness
  proves UTC/New_York reader invariance. This bounded compatibility path is acceptable for
  an explicit operator read, but it must not become a high-volume query primitive. Add a
  canonical UTC/versioned construction for new events, reconcile/cache legacy verification,
  and benchmark representative large source chains before activation at scale. Do not
  rewrite or delete historical custody rows.

## Report re-verification corrections (2026-08-14)

Source: an independent review report (`docs/reports/mcp-platform-agno-review.md`, Perplexity-sourced,
**kept local/untracked** — findings folded into existing registers here, not committed as a report).
Re-verified against source at commit `5d3fb09` (10 parallel verifiers + smart-explore contradiction sweep).
Two report claims are **REFUTED** and recorded here so they don't re-enter the project as open items:

1. **Report §45 "disclosure_tier hardcode = bug per ADR-0045" — REFUTED (most-wrong finding).**
   ADR-0045 Decision C / N3 says the parser hardcoding of `disclosure_tier=contemporaneous`
   (`server/tools/parsers/messaging/sbv_sms.py:114`, `server/analysis/sbv_transcript.py:111`) is
   **CORRECT** — "extraction cannot know better; the defect is that no derivation layer exists above
   it." The real defect is the **unbuilt derivation/horizon layer** (INVENTORY N1: predicate filters
   on superseded `knowledge_time`; N2: `realized_at`/`acquired_at` zero writers; FD: agent-layer
   pre-filter unbuilt) — NOT the hardcode. Removing the hardcode would CONTRADICT ADR-0045 Decision C.
   The hardcode that WAS reversed (correctly) was the AI-chat **context** lane (sql/0023 / D-056,
   applied) — a different lane from evidence extraction. The report also misnames the file
   (`sbv_sms.py:114`, not `sbv_transcript.py`). Wave 1 builds the derivation layer; the hardcode stays.

2. **Report Addendum A2 "derived horizon tables need a new ADR" — REFUTED.** ADR-0045 §B (signed
   2026-08-09, D-042) already **sanctions version-pinned DERIVED pass materializations** (as-lived
   incremental via `working.walk_ledger` + hindsight on-prompt; single-writer refresher; hash-attested
   to `ops.audit_ledger`) and **amends canon §1** (parallel AUTHORED as-lived/hindsight stores
   FORBIDDEN). No new ADR is needed — the work is to BUILD the already-sanctioned design (Wave 1/3).
   Canon §1 + §3 amended 2026-08-14 to state this (see `PROJECT_CANON.md`).

The remaining report GAPs (GAP-01…GAP-12) were CONFIRMED or PARTIAL against source and are tracked
in the existing rows above / the Wave plan (`C:\Users\matts\.claude\plans\cached-waddling-crayon.md`).
Full re-verification verdict table lives in that plan.

## Wave 0 live inventory findings (2026-08-14)

Source: `scripts/_wave0_inventory.py` + `scripts/_wave0_fresh_restore.py` against tailnet PG
`100.91.190.107:5432` db `ai` (PG 18.1). Full signed baseline:
`docs/INVENTORY-BASELINE-2026-08-14.md`.

1. **Horizon clock = superseded `knowledge_time` (LIVE-CONFIRMED).** `working.horizon_visible`
   filters on `row_knowledge_time <= p_horizon`, NOT ADR-0045 §A's
   `visible_from = COALESCE(realized_at, occurred_at)` — so the predicate is inert. This is
   GAP-04 / INVENTORY N1 confirmed against the **running DB** (previously only source-confirmed).
   **Wave 1** replaces it (clock migration → `realization_event` → `visible_from` derivation).
   Not a new debt row — sharpens the existing N1 finding to "live-verified."

2. **ADR-0045 §A/§B unbuilt** (live-confirmed): `working.realization_event`, `working.walk_ledger`
   do not exist. Wave 1.

3. **ADR-0053 schema BUILT but EMPTY** (live-confirmed): `chat_conversation`/`chat_message`/
   `chat_chunk` (+ lane/embedding/projection) exist, 0 rows; `chat_cdc_cursor` +
   `chat_projection_dead_letter` exist, 0 rows. `working.context_record` still holds **1,741
   rows** — the legacy chat-lane data to migrate into the new tables per ADR-0053.

4. **PARTIALLY RESOLVED — bootstrap captured; current-image replay still drifts.** Commit
   `2b37a4b` added `sql/bootstrap/schema_baseline.sql`, so the earlier action to locate and
   capture the out-of-band DDL is complete. A 2026-08-16 observed restore into the isolated
   `horizon_scratch` PostgreSQL service exposed two remaining defects:
   (a) the dump creates `pg_duckdb` before `pg_stat_statements` and PostGIS, causing the current
   `ghcr.io/cursedpotential/agno-postgres` image to reject their extension-script `GRANT`s as
   MotherDuck-table operations; pre-creating every conventional extension before `pg_duckdb`
   made the structure-only restore succeed; and (b) the captured file does not contain
   `ops.audit_ledger` even though `sql/README.md` said it did. Applying `0019`–`0020`, then
   `0021`–`0030` in reviewed order completed the scratch schema. **Still open:** regenerate or
   wrap the baseline with deterministic extension ordering, an explicit included-migration
   manifest, and an empty-database regression test. Do not call the baseline alone a verified
   current-image bootstrap until that gate passes.

> **2026-08-09 audit** (docs/registers true-up pass): all "resolved" rows below re-checked
> against the tree and still verified resolved (parser/extractor modules present under
> `server/tools/parsers/{messaging,ai_chat,generic}/` + `server/tools/extractors/`; the
> `docker/tools/tools/facade.py` facade still `load_builtin_tools()`-backed — spot-checked,
> not exhaustively re-run). Planned rows re-verified open: "Evidence schemas populated by a
> real pipeline" (P2/P4), `evals/cases.py` still `CASES: tuple[Case, ...] = ()`, and Backups
> (pg_dump + neo4j dump → R2) still has no recurring implementation — `scripts/backup_ovhdata_hot.sh`
> exists but is a one-time host-retirement snapshot (Postgres/SurrealDB/Weaviate only, explicitly
> skips Neo4j/Milvus to a cold-copy phase), not the recurring R2 lane this row tracks. The
> session's rejection list (items 1–6, owner planning session 2026-08-09) was re-reviewed and
> HELD — no reversals — with one addition: the derivation engine joins the "justified custom"
> list below (see TD-JC).

**Rule:** No code ships incomplete-and-silent. Any unavoidable stub gets a
grep-able `# STUB:` marker in code AND a row here. **Scope: non-test code only**
(`server/`, `docker/`, `evals/`, `scripts/`) — `grep -rn "# STUB:" server docker
evals scripts` must match this table exactly. Keep this current as part of
every change. Test doubles (fake engines, stub clients, etc. used *by* tests
to isolate a unit) are a different thing — mark those `# TEST-DOUBLE:` in
`tests/`, not `# STUB:`; they don't belong in this register because they are
never incomplete-and-silent in production, they're deliberate test fixtures
(corrected 2026-08-09 — `tests/test_run_ledger.py:61` and
`tests/test_custody.py:19` were mistagged `# STUB:` and re-tagged
`# TEST-DOUBLE:` for exactly this reason).

## Active stubs (intentional, marked)

| Marker | File | What | Why deferred | Returns with |
|---|---|---|---|---|
| _(none)_ | | | | |

## ADR-0053 implementation follow-ups

| Item | Current safe behavior | Required completion |
|---|---|---|
| CDC worker/replay/alert | PG projection plans and outbox/cursor/dead-letter schema are durable; drains are manual | standalone worker, replay tool, count>0 alert, operator status |
| Classifier quality | deterministic keyword baseline; ambiguity/failure falls back to searchable context | human-labeled evaluation, semantic/LLM challenger, sampled high-confidence audit |
| OCR/VLM selection | lightweight extractor seam plus optional Docling; failures remain visible | benchmark Mistral/Kimi/GLM/other providers on representative private data; record cost/privacy/quality |
| Multimodal embedding | schema represents native/text/OCR/transcript/keyframe projections | implement and evaluate image/audio/video embedders without replacing original bytes |
| Timeline extraction | ingest succeeds without premature facts | entity/claim/time/event candidate workers, bulk consolidation, investigation-register UI |
| Horizon walks | no horizon values are stamped on raw chat | separately design as-experienced versus hindsight walk tables/views after timeline population |

_Byline: Codex · GPT-5 · 2026-08-13._

> 2026-06-12: the entire **Cloud Drive Cleanup agent** (not just `trash_cloud_file`)
> was removed from the active topology — owner decision: cloud cleanup is a separate
> future feature, not part of the evidence platform. It returns, fully toolled,
> with the Drive/OneDrive MCP integration. Empty `drive_*_tools` placeholders
> remain in `server/agents/providers.py` for that feature (still true as of this
> doc-sync pass, 2026-07-10).

> When a stub is added: add a `# STUB: <tag>` comment at the code site and a row above.
> When resolved: remove both.

## Known debt (tracked, scheduled in the plan)

| Item | Status | Where |
|---|---|---|
| Backend atomic tools (parsers/extractors) attached | **resolved 2026-07-10** — real chatminer-backed parsers exist under `server/tools/parsers/{messaging,ai_chat,generic}/` + `server/tools/extractors/`, registry populated | P2 — `server/tools/registry.py` |
| Evidence schemas populated by a real pipeline | planned | P2/P4 — `server/evidence/*` |
| `tools-facade` populated (was `PORTED={}`) | **resolved 2026-07-10** — `load_builtin_tools()`-backed, real registry + SBV proxy surface | P2 — `docker/tools/tools/facade.py` |
| Evals populated (was `CASES=()`) | planned (still `CASES: tuple[Case, ...] = ()` as of 2026-07-10) | P5 — `evals/cases.py` |
| Backups (pg_dump + neo4j dump → R2) | planned | P5 |
| Self-hosted evidence vector store (Qdrant/Milvus) | ~~**resolved 2026-07-11** — Milvus is the locked platform-wide vector substrate (ADR-0026/ADR-0027), self-hosted + LIVE on the `data-vector` Coolify app~~ **Corrected 2026-08-12:** ADR-0026/0027 were SUPERSEDED by ADR-0040 (Weaviate LOCKED 2026-07-27) — Weaviate is THE vector store. The Milvus→Weaviate cutover was ruled VERIFIED 2026-08-09 (D-042; pymilvus removed from the image); the `data-vector` Milvus app is DOWN deliberately since 2026-08-10 (6th embedded-etcd corruption — docs/COORDINATION.md). The "Qdrant" framing was stale. Evidence-text-embeddings *ingestion* at scale is still future work, tracked as "Evidence schemas populated by a real pipeline" above. | future → `docs/adr/0040-vector-substrate-revisit-weaviate-pgvector-milvus.md` (supersedes `docs/adr/0026`, `docs/adr/0027`) |
| Part 2 multi-pass analysis engine | next round | future |
| V2 slim Graphiti image; multi-user auth | deferred | future |
| Knowledge text embedder (`nvidia/nv-embed-v1`) calls NVIDIA NIM **direct**, not through the Portkey gateway | owner decision 2026-08-01: direct for now, Portkey later | `server/core/session.py` — see the TODO above `_EMBED_TEXT_BASE_URL`; target config already exists and is verified live at `docker/gateway/portkey/configs/embed.json` (reused as-is by Graphiti's own Portkey cutover) |

## Agno-native audit (2026-06-11) — STOP reinventing; use native (no code written yet)

~~Pinned `agno==2.6.9`; latest is 2.6.13~~ — **corrected 2026-08-09: `requirements.txt` currently
pins `agno==2.8.7`** (verified by grep against the live file; not the `2.8.0` other docs — AGENTS.md,
CONVENTIONS.md, canon §8 — still cite as current, itself a drift this pass did not chase down
further; flag for a follow-up sync). Audit below was verified against the 2.6.9 wheel + skill
references at the time it was written and has not been re-run against 2.8.7; treat the specific
API surfaces named as needing re-verification, not as stale in spirit. **Reinvented /
about-to-reinvent things Agno provides natively — switch before building P1–P5:**

| We built/planned | Native Agno (use this instead) |
|---|---|
| Custom `approval_request` table + `/v1/approval-requests` routes | `@approval(type="required")` decorator (`agno.approval.decorator`) + auto-mounted **`/approvals`** router (list/resolve/count/status/delete) + `PostgresDb.create_approval/get_approvals/update_approval` + agents `/continue` w/ `require_approval_resolved`. **Recorded, queryable, blocking approval — exactly our HITL intent. DROP the custom table+routes.** |
| Domain-separated knowledge via custom per-domain plumbing (ADR-0020) | `knowledge_filters` + `enable_agentic_knowledge_filters` on Agent. **Dict filters ONLY on Weaviate** (the locked platform vector substrate, ADR-0040) — `Knowledge.search(filters={"domain": "legal_strategy", "disclosure_tier": ...})`. Corrected 2026-08-09: ~~`Knowledge.search(filters=[EQ("domain","legal_strategy")])` (`agno.filters` `FilterExpr` list)~~ — agno's Weaviate adapter SILENTLY DROPS `FilterExpr` lists (`log_warning` + `filters=None`); source = `AGENTS.md`'s own Weaviate-specific landmine paragraph ("verified in agno 2.8.0 source, 2026-08-02"), not `docs/reference/agno-memory-and-storage/02-knowledge-and-retrieval.md:1195` (that push-down table documents Milvus, a different adapter with different filter support). Metadata tags + dict filters; agents can pick dict filter *values* agentically (`enable_agentic_knowledge_filters`), never a `FilterExpr`. |
| Custom DAG executor for evidence workflows (ADR-0017) | `agno.workflow` `Step/Steps/Parallel/Condition/Loop/Router`. **Router = agent re-composition on failure; Loop = retry; Condition = branch; `Step(executor=fn)` = arbitrary code.** Registry can stay; orchestration is native. |
| Bespoke tool registry / `tools-facade` | `Toolkit` (`agno.tools.toolkit`) + `MCPToolbox` (`agno.tools.mcp`, DB-fleet tool filtering). Atomic tools = Toolkits/MCP. |
| Custom eval harness (P5) | `agno.eval`: `AccuracyEval`, `AgentAsJudgeEval`, `ReliabilityEval` (tool-call assertions), `PerformanceEval`. |

**Justified custom (NO native equivalent — keep):** `db/embedder.py` NimEmbedder (no native NVIDIA
embedder; query/passage), `db/reranker.py` NvidiaReranker (no native NVIDIA reranker; Cohere leaks).
(Now `server/core/embedder.py` / `server/core/reranker.py` — ADR-0033 `db/` → `server/core/`.)
Added 2026-08-09: the **checkpoint-derivation engine** (ADR-0045, Decision B) — the sole
grant-locked refresher that materializes version-pinned derived-pass checkpoints from the one
canonical factual store, one predicate, two schedules (as-lived incremental / hindsight
on-prompt), every derivation hash-attested to `ops.audit_ledger`. No Agno-native equivalent
exists for version-pinned, hash-attested, single-writer derivation of bitemporal knowledge-horizon
checkpoints — this is the platform's own knowledge-horizon mechanism (`AGENTS.md` §"WHY THIS
EXISTS"), not a generic capability an off-the-shelf component provides.

**Under-used native worth adopting:** `output_schema` (Pydantic) for normalized/analysis records;
`tool_hooks` for custody/audit wrapping; native Knowledge readers/chunkers for ingestion.

**Action:** ~~upgrade to 2.6.13~~ ✅ — ~~rewrite P1 to native `@approval` + `/approvals`~~ ✅ (2026-06-12);
base P2/P3 workflows on native Workflow; P5 evals on `agno.eval`. Updates ADR-0017/0020/0021.

## Resolved (kept for provenance)

| Item | Resolution | Date |
|---|---|---|
| Embedding query/passage mismatch | `db/embedder.py` NimEmbedder — passage default, query-path override | 2026-06-11 |
| Ephemeral pg_duckdb R2 secret | `ensure_duckdb_r2_secret()` runs at API startup (survives DB recreate) | 2026-06-11 |
| HITL row persist + decision→continue (P1) | NATIVE: agno upgraded 2.6.9→2.6.13; `apply_db_modification` = `@approval` + `@tool(requires_confirmation=True)` — pause persists a pending row (`agno.run.approval`), `POST /approvals/{id}/resolve` records the decision, run-continue is gated by `require_approval_resolved`. Custom `approval_request` table+routes removed (`app/main.py`); legacy tables marked in `sql/0002_schema.sql` | 2026-06-12 |
| `apply_db_modification` was `NotImplementedError` | Real write: executes ONE statement against an allowlisted schema (`DB_WRITE_SCHEMAS` env, default `analysis`; `evidence` hard-denied regardless of config), search_path pinned to the validated target, rejects `evidence.*` references, rolls back on error (`agents/factory.py`; allowlist added 2026-07-29) | 2026-06-12 |
| `trash_cloud_file` stub + Cloud Drive Cleanup agent | Removed from active topology entirely (owner decision) — separate future feature | 2026-06-12 |

## Parser-lane follow-ups (from the 2026-08-02 gap review — owner: "ensure these go on a list")

Source: docs/HANDOFF-2026-08-02-sbv-chatminer-parser-gap-review.md (phases + acceptance criteria there).

0. **ADR-0044 §4 blob ban is UNENFORCED in code (found 2026-08-10 pre-mortem sweep; assign to
   S7's registry/contract task).** `transcripts.markdown`
   (`server/tools/parsers/generic/whole_file_fallback.py:25`) registers plain
   `capability="parse.transcript"`, so the whole-file speaker-blending fallback is resolvable
   by `build_chat_transcript_workflow.parse_step` (`server/evidence/workflows.py:533`) — a
   workflow that runs custody + store steps. ADR-0044 says the whole-file parser is
   "last resort only and BANNED for evidence." Fix options, decide inside S7 (the right gate
   depends on the chat-transcript workflow's lane semantics, which S7 owns): (a) capability
   split — fallback moves to `parse.context_transcript`, context lane
   (`server/analysis/context_chat_ingest.py:118`) resolves both, evidence workflows resolve
   only `parse.transcript`; or (b) store-boundary guard — evidence/store rejects records whose
   `parser_id == "transcripts.markdown"` (ban enforced where the harm happens). Either way add
   the guard TEST: fail if `transcripts.markdown` is reachable from an evidence-lane workflow.

0b. **Python SMS-XML parser must go iterative and spill to a FILE, not memory (owner directive,
   2026-08-10: "the python sms parser still needs to be fixed at some point — it's supposed to be
   iterative and it's supposed to write directly to a file and not into memory … even though it's
   a backup").** Two distinct defects in
   `server/tools/parsers/messaging/sms_xml.py`:

   - **(i) Records accumulate in memory even on the happy path.** `_collect()` (`:279`) streams the
     *XML* correctly — `iterparse` + `elem.clear()` — but appends every record to an `out` list.
     `parse()` (`:311`) then hands that whole list to `records_out()` (`:321`). Memory scales with
     record count, not file size. **The streaming generator already exists** — `iter_records()`
     (`:238`) yields, and its docstring says it exists "so a caller can batch straight into the raw
     layer with flat memory." `parse()` simply does not use it.
   - **(ii) The malformed-XML fallback is the worst case.** `:291-301` does
     `ET.fromstring(_sanitize_xml(path.read_text(...)))` — the whole file as a string *plus* a full
     DOM. The code already admits it: the inline comment says "more RAM, last resort," and
     `iter_records`' own docstring (`:252-255`) calls it "exactly what streaming exists to avoid …
     rather than silently ballooning to multi-GB."

   **Required shape:** `parse()` drives `iter_records()` and writes records straight to a file
   (NDJSON spill), returning a path + counts rather than an inline list. The malformed path must
   sanitize incrementally instead of materializing the document.

   **Contract implication — do not skip.** `records_out()` returns records inline, so a spill-to-file
   mode changes the atomic tool's output contract. Per ADR-0049 the tool must stay callable **both**
   in a workflow **and** atomically over the API, so both callers need to handle the new shape.

   **This is NOT closed by the ADR-0049 routing fix.** Routing sends normal traffic to the Go
   `smsXMLImporter`; this parser remains the fallback, and a fallback that exhausts memory is not a
   real fallback. **Unverified, check before assuming otherwise:** whether the Go decoder handles
   *malformed* dumps at all — its `Detect` only requires `.xml` plus `<smses`/`<calls` in the head,
   so it may accept a malformed file and fail differently. If Go cannot repair them, this Python
   path is load-bearing rather than a backup. rel: ADR-0049 (memory criterion), owner statement
   "go is critical for files that could blow out a memory store".

1. ~~**Go-side import-scoping (review Phase 1):** SBV upload returns
   `{job_id, import_id}`; messages/calls carry import_id; add
   `GET /api/imports/:id/activity`; bind progress + hashes to the same id;
   custody reconciliation becomes mandatory for the forensic tier. This is the
   restore condition for the 2026-08-02 SBV demotion (DECISION_LOG).~~
   **LANDED — PR #18 (`aacf21c`, merged 2026-08-06).** `server/tools/_sbv_client.py`
   is import-scoped throughout (`import_id` on `import_detail`/`import_records`/
   `import_rejections`/`import_attachments`/`hashes`, verified 2026-08-09).
   This is the basis for **SBV's promotion back to primary** (owner directive
   2026-08-05; D-040, `docs/DECISION_LOG.md`).
2. **Streaming/batch ingestion contract (review Phase 2) — PARTIAL, open item
   tracked in S7:** the **SBV path** now has its own import-scoped
   reconciliation (item 1, landed) — but the **generic/cross-parser**
   contract this row originally scoped is still open: iterator/batch parser
   protocol with backpressure; a real `evidence.raw_rejected` WRITER (the
   table + indexes exist since sql/0012 and `server/tools/parsers/messaging/
   sms_xml.py` + `server/tools/repair/types.py` reference the table by name,
   but no code path currently `INSERT`s into it — verified 2026-08-09, zero
   writers found); `record_count_claimed` capture; claimed = accepted +
   rejected + accounted-duplicate gate; replace the in-memory multipart
   upload for non-SBV parsers.
3. **Registry priority/quality metadata (review Phase 3) — open, S7:** explicit
   `priority` / `quality_tier` / `streaming` / `custody_capabilities` /
   `max_safe_size` on the tool contract; golden corpora per format;
   primary/fallback equivalence tests; SBV shadow-comparison harness.
4. **ChatMiner hardening (review Phase 4) — open, S7:** rename `message_hash` →
   `content_fingerprint` (full digest, never custody); deterministic IDs from
   (artifact H1, parser version, source indices); tz-aware UTC timestamps;
   bounded detection probes instead of whole-file reads.
5. **Repair-layer wiring — open, S7:** adopt `server/tools/repair/` one format
   at a time (SMS XML first, then CSV) only AFTER the ledger/rejection/
   reconciliation writers of item 2 exist — the observability contract is the
   acceptance criterion. Coordinate with the repair-layer chat (their branch:
   feat/stream-repair-layer — landed in part via PR #18's governed repair
   slice, item 1 above; item 2's generic writer is still the gate for
   adopting `server/tools/repair/` beyond SBV).
