# Plan — SAT-RAG messaging retrieval: message-node model + neighbor expansion

> _Byline: Claude Code · Opus 5 · 2026-09-03._
> **STATUS: ITERATING — NOT DONE.** Done only when the owner says so. Nothing below is
> ruled; the ADR is written only after this plan is approved.
> ~~**LlamaIndex is NOT part of this.** No framework is added. Nothing here depends on it.~~
> **CORRECTED 18:1x, owner:** I misread "NO, LLAMAINDEX IS PART OF THIS" as "no LlamaIndex."
> **LlamaIndex and LangGraph are IN.** LlamaIndex = retrieval library (property graph over Neo4j
> `sat-temporal` + Weaviate vector store; nodes from message rows with PREV/NEXT; hierarchical
> expansion). LangGraph = deterministic retrieval state machine (parse → parallel PG/Weaviate/
> Neo4j → timeline verify → synthesis with PG-source-coordinate citations), run as Temporal
> activities, callable by any agent runtime; n8n's agent nodes are LangChain/LangGraph-based so
> the same graph runs inside n8n. ADR-0041's LangGraph rejection rested on "Agno-native
> orchestration," which D-107 retired — supersession note owed. The owner's source document is
> `C:\Users\matts\Downloads\SAT-Graph RAG on a Weaviate + Neo4j + SurrealDB Stack …md`
> (2026-08-26); an Opus reader is extracting its data model, store roles, and framework
> assignments now; the SAT-RAG sections below are to be RE-DERIVED from it, not from my design.
> **Also re-confirmed 18:1x:** DuckDB ELT normalizes exactly as parsed output does — same raw
> table, same contract, same normalize step; only the method of getting to raw differs.

## Context

D-093 ruled the dual-lane SATemporal / Semantica GraphRAG architecture (2026-08-27), D-107
put Temporal in charge of projection (2026-08-29), and migrations 0055/0056/0058/0059 built
the lane schema. What was never written is what a SAT-RAG node IS for messaging and how a
search hit becomes something a person reads. `docs/design/surrealdb-analytical-surface.md:188-200`
names that missing ADR as an open decision. Today: schema applied, five orphaned `.pyc`
files, no source, no worker registration, no callers.

Owner design, 2026-09-03, verbatim: *"It looks at the chunk ID and then uses that to find
the atomic messages in the database and just pulls the appropriate messages. That is not
going to pull the whole chunk. It's utilizing it to narrow it down to where it can find it
atomically."* Owner also said the messaging chunk unit is **unknown** — so the plan must
measure it, not assume it.

Outcome: one approved design that (a) closes the SAT-RAG ADR gap, (b) answers the chunk
barrier question by construction, (c) names the chunk-unit bake-off that gates acceptance.

## The design to be ruled (proposal)

| # | Element | Proposal | Status |
|---|---|---|---|
| 1 | **Evidence unit** | the normalized message row in `working.*` (hub, per the hub-and-mirror model). Content + timestamps immutable (D-136). No column added to it. | proposal |
| 2 | **Search unit** | a small overlapping message-safe window written to `working.content_chunk` as an **index handle**, never a display unit. Candidate default: center message ± N neighbors. Alternatives to bake off: time-gap session window; Chonkie semantic group over a turn-aware pre-split (Chonkie already chosen, `docs/planning/agno-chunking-strategy.md`). | **unmeasured** |
| 3 | **Provenance** | ~~new table `working.content_chunk_message` (name not ruled)~~ **BUILT 2026-09-05** as `sql/0072_content_chunk_message_bridge.sql` per Q9: `(chunk_id, message_id)` PK, `is_center`, `position`, `created_at`, append-only, FKs to `content_chunk` and `normalized_record`. The centre is carried as the `is_center` flag rather than a `center_message_id` column, and `conversation_id`/ordinal are read from the message row (D-136: never duplicated onto the association). `chat_chunk_message` died in 0058; this is its successor. | **built, not deployed** |
| 4 | **Retrieval** | hit → chunk_id → provenance → center_message_id + conversation_id → expand **on the message table** by conversation + ordinal (PREV/NEXT), bounded by K neighbors or a time gap → dedupe on center id, merge overlapping spans → return **messages**, never chunk text. K is a runtime parameter independent of N. | proposal |
| 5 | **Barrier question** | dissolved: expansion never touches chunks. A hit at the edge of chunk A pulls neighboring messages, which exist once in the message table. Overlapping windows dedupe on center id. | by construction |
| 6 | **Graph lane `sat-temporal`** | one node per message row carrying the PG source coordinate (`normalized_record_id` + `content_chunk_id`) with the seven version-stamp fields (`sql/0055:256-272`); `PREV`/`NEXT` from ordinal; `IN_CONVERSATION` edges; no fusion with Semantica `evidence`; lane-labelled results (D-093). ADR-0062 claim-temporal edges are *asserted* order and are NOT duplicated here — these are structural sequence edges. | proposal |
| 7 | **Where it runs** | chunking + provenance = a **new** Go activity beside `chunk_document_activity` (`modules/engine/activities/chunking.go`), not a widening of it (D-130 rule 7). Expansion = one bounded unit callable direct / Temporal Activity / n8n node, consumed by **any** agent runtime. | proposal |
| 8 | **Horizon** | none in this unit. Walks and deltas are SurrealDB-only in analysis (D-073/D-080/D-107). Nobody re-adds a pre-filter here. | already ruled |
| 9 | **Acceptance gate** | bake-off on the Google Voice corpus (plan says ~29.3k raw+sorted; inventory says 7,006 in sorted — dedup explains it; corpus = whatever survives). Compare N ∈ {1,2,3,5}, time-gap sessions, Chonkie semantic. Owner authors a held-out query set from known incidents. Metrics: message-level recall@k, MRR, expansion precision, mean messages returned, duplicate-center rate, **boundary-straddle rate** (no recall penalty allowed), index size, latency. Receipts in `analysis.graphrag_*`. | not run |

## DuckDB ELT — owner ruling 2026-09-03 (source: the "elt process" conversation, reconciled)

Owner, verbatim: *"if the file doesn't have to be parsed and just extracted, then why would it be
post-parse? It would replace it, but the existing processes remain as backups if there's a
failure. Go is still gonna be the orchestrator, still gonna call it — it's very likely gonna
begin in that workflow, so it needs to be able to make those queries."*

| Rule | Consequence |
|---|---|
| **Extract vs parse is the split, not file class.** If a file only needs EXTRACTION (its records are already rows: JSON/JSONL/CSV/Parquet; XML/HTML where regex over `read_text` yields the fields), DuckDB ELT is the **primary** path and REPLACES the Go/Python decoder for it. | Router column: `extract-only?` decided at classify, per file. |
| **Existing Go/Python parsers remain as failure fallback**, not as a parallel first-class path. | One primary per file; fallback only on logged ELT failure (same shape as ADR-0052 Q3's Go→Python fallback). No rewrite of any parser. |
| **Go stays the orchestrator and the caller.** The workflow begins in Go; Go must be able to issue the DuckDB queries. | `duckdb_elt_activity` in `modules/engine/activities/`: input = locator + SQL template id + target table; runs the query through the PG connection (pg_duckdb) so the result lands in PG in the same transaction as the per-table outbox row (ADR-0052). No hashing, chunking, or projection inside it (D-130). |
| **Files that must be PARSED** (PDF, images/OCR, docx layout, screenshots, anything opaque) stay with Go/Python decoders. DuckDB has nothing for them beyond `read_text` on `word/document.xml`. | unchanged |
| **In-database chunking** (`string_split` + `UNNEST`) is a **candidate in the §9 bake-off**, not canon. | third candidate beside the Go message-window chunker and Chonkie |
| **R2 pushdown vs block scratch:** splittable/columnar AND a subset scan → query R2 directly with pushdown; opaque, or full-text needed → materialize to block scratch first (the gateway already does this). | write it as a rule in the routing table so it stops being re-derived |
| **Superseded content from that conversation, NOT carried:** LangGraph/LlamaIndex retrieval (ADR-0041; owner 2026-09-03 "no LlamaIndex"); RRF fusion across stores (D-093 no-fusion; walks are Surreal-only D-073/D-080); "Agno agent drains the outbox" (Temporal activity drains it). | — |

Already canon and simply confirmed by that conversation: PG is truth; Weaviate/Neo4j are
outbox-fed projections (ADR-0052, D-054); every projection row carries the PG id + hash
(2026-08-29 source-coordinate rule); Temporal owns durability one activity per step; n8n at
the perimeter (D-130); SAT graph in Neo4j `sat-temporal` (D-093).

Execution additions (after approval): (8) `duckdb_elt_activity` + SQL template registry
(one template per extract-only class; templates are files, reviewable, versioned);
(9) routing-table column `extract-only?` + fallback-on-failure edge in the stage graph;
(10) the DuckDB `markdown` community extension evaluated on the ~18 Lost-and-Found markdown
chats before it is adopted (context-only lane, D-082).

## Anti-patterns (binding if ruled)

- Never render a chunk. Never expand across conversations. Never widen K to "show the thread" without an explicit caller parameter.
- Never hash chunks for custody: `content_sha256` is verification only (D-124, D-130 rule 2).
- Never mutate a working row; provenance is its own table.
- Preview/HITL shows the **expanded messages with the chunk boundary drawn** so parser and chunker defects are visible (D-135/D-136).

## Review round 2 — the owner's SAT-Graph document vs this plan (Opus reader, 18:24)

Source: `C:\Users\matts\Downloads\SAT-Graph RAG on a Weaviate + Neo4j + SurrealDB Stack …md`
(owner-supplied 2026-08-26). **The plan's "SAT-RAG messaging retrieval" table is NOT this
document's design and must be re-derived from it.** Deltas, all owed:

1. `sat-temporal` node labels = **Item / Version / Action / TextUnit / Theme / ItemType**
   (doc:22-29,41). "One node per message" is struck as the sole model.
2. Messaging mapping to be RULED: conversation = Item, message = TextUnit is the inference;
   the doc maps the psych domain, not messaging (doc:41).
3. **Action** (the causal event: deletion, edit, retraction, contradiction?) is absent from the
   plan. Without it there is no "what changed and why." Owner must define Action for messaging.
4. Both temporal encodings (doc:43): PREV/NEXT on edges for light facts; Version chain +
   HAS_CURRENT for consequential material.
5. Expansion moves to **Cypher**: getItemAncestors / getItemHierarchy / getItemHistory /
   getActionsBySource as four composable primitives (doc:45). Not a SQL join on the hub.
6. Weaviate is the mandatory entry point; two styles as separate callables: concept-first and
   chunk-direct (doc:49). TextUnits are what gets embedded (doc:27).
7. Every Weaviate object carries the governing Version's validity window; **temporal filter
   first, semantic rank second** (doc:51,95). Plan has no validity window anywhere.
8. Maximal determinism rule: one LLM resolution step at entry, zero LLM in traversal (doc:29,68).
9. STAR-RAG rule-graph + PPR = deferred stage with the doc's own size trigger (doc:97).
10. TG-RAG incremental re-summarization cost becomes an acceptance metric (doc:33).
11. **Surreal conflict to rule:** doc = live per-query aggregation surface (doc:57,70);
    D-107 = manual-promotion-only. Plan currently cites both. One wins.
12. Eval discipline from the doc: graph-integrity checks + must/must-not-mention grounding
    tests (doc:77,98).
13. LlamaIndex appears once as prior art (doc:37); its dependency status is the OWNER'S ruling
    (18:1x), not the document's. LangGraph: zero mentions; its basis is the elt-process
    conversation + n8n's LangChain-based agent nodes.
14. No Codex "re-split" (Neo4j→Semantica, Weaviate+Surreal→SAT) exists in the repo; both lanes
    live in Neo4j (`evidence`, `sat-temporal`, sql/0055:254). Claim dropped.

Open rulings from the document (questions only): conversation=Item? · what is an Action for
messaging? · do immutable messages have Versions at all? · Weaviate mandatory entry vs direct
message path? · D-107 vs live Surreal? · which store holds Theme and is it shared with the
Semantica extractor (D-093 fusion risk)? · validity-window source for messaging without
Versions? · psych mapping in scope now? · PPR now or at size trigger?

> **Owner corrections 18:3x, binding on rounds 2–4:** (1) the SAT-Graph doc is a GUIDE for how
> the frameworks work together, not a bible — adapt its shape to what is true here; never quote
> it line-for-line or code-for-code; ask intent, don't assume it. (2) Anything dated January
> 2026 is superseded by any later ruling — "if we've changed it since January, we've changed it."
> Round-3 items sourced only from the January design docs are DEMOTED to "not carried unless the
> owner says so": #1 fingerprint matcher, #5 timezone field, #6 status decoder, PII flag.
> #3 interactive preview survives on its own 2026-09-02 D-135 ruling, not on the January doc.
> (3) Permission rules applied 18:3x in `.claude/settings.local.json`: docs/plans/memory free,
> git writes ask, code/SQL/deploy/AGENTS denied until a named build lifts a path.

## Review round 5 — owner's review / gap-analysis docs vs repo TODAY (Sonnet reader, 18:4x)

CLOSED since those reviews: MCL factor j/k label inversion; held migrations 0026-30 + 0057-65
(all applied, D-108–D-121); fresh-schema reproducibility (baseline + template DB); `_stale/`
and `timesketch-fork/` out of tree. edisc.md == edisc (1).md. handoffs-v2 H-00/02a/08a/09
closed per the repo's own validation; H-01/02/03/04/05/06/07/08/11 still pending there.
OPEN-UNTRACKED (nowhere in DEBT / DECISION_LOG / registers), sequenced:
1. [foundation] CI job: build empty DB from `schema_baseline_20260830.sql`, diff.
2. [foundation] CI grep gate against `content_hash` regrowth (19 server + 10 sql files still).
3. [foundation] Rule migrations 0040/0041/0044/0045/0046: restore or renumber (G-04).
4. [foundation] Execute the inventoried docs cleanup: Semantica cookbook, 4 `.bak-*`, collapse
   DEBT/DECISION_LOG/COORDINATION/CHANGE-ORDER/MASTER-TODO/URGENT-TODO/BUILD_PLAN into one
   status source.
5. [before filing] RAG citation-grounding validator: elusion sampling, `grounding_check` /
   `generated_claim` schema, release gate. (= round-4 items 2/3.)
6. [first ingest] Verify/apply `0006_behavior_seed.sql` on live (BIF tagging blocker).
7. [first ingest] Dual atomic + contextual embedding projections with `context_thread_id`
   (= the chunk-handle / expansion design, once re-derived from the SAT guide).
8. [first ingest] D-123 desktop client / SBV→custody bridge — designed, not built.
9. [post-promotion] Stable exhibit-ID service; EDRM/Opticon/Concordance load-file export.
10. [post-promotion] Closed-world citation contract (reject unretrieved span ids).
11. [post-promotion] Court-release enforceable freeze/sign transaction (view is read-only now).
12. [later] Ed25519-signed custody chain; Tether behavioral models; SBV absorption into
    `modules/engine/decode/` (D-131, still a `replace` in go.mod).
OPEN-TRACKED, unchanged, owner-aware: agno_app role cutover; horizon predicate still
`knowledge_time` (DEBT Wave-0 #1); Semantica activation held; native evidence-vector cutover
held; immutability guards switchable by design (D-110/D-127/D-128); naming (D-137).

---

## THE SEQUENTIAL GUIDE — one list, in order, owner-checkable

> Built 18:4x from rounds 1–5. Each line: what · why it's here · who does it · gate.
> Status marks: ☐ open · ◐ in progress · ☑ done (only when the owner says) · ✖ struck.
> Model routing per owner: reasoning → Opus, mechanical → Sonnet, never Fable inline.

> **2026-09-05 09:3x — LIVE CHAIN RESULT** (full record: `docs/reviews/2026-09-05-ingest-day-live-chain.md`).
> **Proven end to end through the tool gateway to the HITL repair gate**, on a real Temporal run
> (`rehearsal-20260905-r2e-1788612588`): register → retain from `r2://` → assess via gateway
> (repair.detect 200, repair.preview 200, 99 clean chunks) → `awaiting_repair_decision`. After the
> decision (`rehearsal-20260905-r2f-1788614408`): resolve, capture metadata, fingerprint,
> inventory, extract metadata, select_parser all COMPLETED; **execute_parser FAILED** on a NUL
> byte (0x00) in the synthetic fixture reaching a PG TEXT column. Stage 2 (gateway live) = ☑.
> Stage 1 items B2/B3/B4 = ☑ built + applied live (0071/0072). New Stage-0 ruling needed: NUL
> handling (see Q19 on the desk). Permission rules restored to the 2026-09-04 ruling.
> Commits: ad5f820 · 8ed3191 · fa51dde · cc182a9 · 5eda234 · 3952814 · 26a36da · d06e169 ·
> c3d5475 · 77e6033 · 72a121e · 7feea1f.

### Stage 0 — Rulings that unlock everything (owner, via the Decision Desk)
- ☐ **Q19 NUL bytes in raw records (new 2026-09-05):** PostgreSQL TEXT cannot hold 0x00; the
  synthetic SMS XML has one in element 8 and the parse dies at the raw insert. D-136 says content
  is immutable — the byte-exact record stays in the envelope bytes / H2; the question is the TEXT
  rendering: (A) substitute U+FFFD + flag `had_nul` on the row; (B) store raw text as BYTEA and
  render at read; (C) reject the record to `raw.raw_rejected` with reason. Owner rules.
- ☑ **Q1 RULED 2026-09-04 23:4x = C** ("my lean is C… make it work the same way and
  everything checkable again"). Mechanism: DuckDB templates use `read_text` → self-split into
  records with a running byte offset → decode columns FROM the record text → activity builds the
  standard `parser.RawRecordEnvelope` with a `Locator` byte range → H2 over the raw record bytes
  → same `PersistRawGeneration` path as every Go parser. Add nullable `byte_start`/`byte_end` to
  the raw content tables, filled whenever the envelope carried a range (all DuckDB records + Go
  range parsers), null for StoredBytes-only parsers. Re-verification: offsets present → seek +
  hash + compare (fast lane); null → re-parse with pinned parser version + compare (slow lane).
  Retire `h2-rawelement-duckdb-json-v1`; ELT rows carry the real `h2-rawelement-v1`. Cost:
  `read_text` is whole-file; multi-GB XML needs block scratch + streaming (ties to Q3).
- ☐ Q2 router tie-break · Q3 ELT unit (file vs package) · Q5 Google Voice first-run path.
- ☐ SAT-Graph mapping for messaging: conversation = Item? message = TextUnit? what is an Action?
  do immutable messages have Versions? (round-2 questions)
- ☐ Surreal: D-107 manual-promotion-only vs the guide's live aggregation surface. One wins.
- ☐ Q6 chunk bake-off before or after first ingest · Q7 chunker unit split · Q8 ordinal.
- ☐ Which January-era items, if any, are re-adopted (fingerprint matcher, tz field, decoder).

### Stage 1 — Foundation (no ingest yet)  [Sonnet unless marked]
> **2026-09-05 05:5x — PUSHED to origin/main at `5eda234`** (owner: "commit… push… Clean. Done."):
> `ad5f820` outbox 0071 · `8ed3191` gateway slice (Go 1.26 pins, tsnet embed assets, worker→gateway
> contract + fail-closed token, platform-tools contexts + materialize mount) · `fa51dde` worker token
> mount · `cc182a9`/`5eda234` H-04 bridge 0072 + Weaviate feed rewire + nemotron 2048. Live deploy run
> in progress (migrations → platform-tools → gateway → worker → rehearsal); result lands in
> `docs/reviews/2026-09-05-live-deploy-run.md`. Blocked by permission rules, NOT worked around:
> root `AGENTS.md` compose-context drift line; `deploy/compose.yaml` platform-tools block
> (`context: ..`, `dockerfile: deploy/docker/tools/Dockerfile`). Both owed.

- ☐ Apply the docs-only permission rules — DONE 18:3x (`.claude/settings.local.json`).
- ☐ Write ADR-0063 from the SAT guide + Stage-0 rulings [Opus]; supersession note on ADR-0041
  (Agno-native orchestration → D-107; LangGraph now in); D-138 in DECISION_LOG.
- ☐ Drift fixes: `modules/engine/AGENTS.md:34-38`; `surrealdb-analytical-surface.md:188-200`;
  ingest-simplification-plan chunk-unit lines; ADR index rows 0062+0063; memory note scope.
- ☐ CI: empty-DB baseline build + `content_hash` grep gate (round-5 #1/#2).
- ☐ Rule + fix migration holes 0040/0041/0044-0046 (round-5 #3).
- ☑ **BUILT, NOT DEPLOYED** (2026-09-05, Claude Code · Opus 5) — Migration:
  `working.content_chunk_message` provenance/bridge table (Q9), rollback-validated live.
  `sql/0072_content_chunk_message_bridge.sql`: PK `(chunk_id, message_id)`, FKs both ways
  (`content_chunk`, `normalized_record`, both `ON DELETE CASCADE`), `is_center`, `position`,
  `created_at`, append-only UPDATE trigger, index on `message_id`, `≤1` centre and distinct
  positions per chunk. It also re-anchors `evidence_vector_projection_job.chunk_id` — that FK
  had been silently gone since 0058 dropped its referent (verified live: zero `contype='f'`
  rows on the table) — and rewrites `working.enqueue_evidence_vector_projection(uuid[],text)`
  to select through the bridge. Validated live: applied twice in one txn, FK asserted, the
  function called with `[]` and with a random uuid (0, 0), blank reason raised
  `VECTOR_PROJECTION_REASON_REQUIRED`, then ROLLBACK. **Not yet applied to the live database.**
- ☐ Migration/outbox: ADR-0052 Part 1 outbox table (B3) — required before any projection.
- ☑ **BUILT, NOT DEPLOYED** (2026-09-05, Claude Code · Opus 5) — Rewired the Weaviate feed off
  the dropped `normalized_record_chunk` → `content_chunk` via the bridge (B2). Nine code sites
  plus the SQL function; zero executable references to the dropped table remain in `server/`
  or in any non-history migration. `chunker_id` now comes from `content_chunk_generation`,
  `source_content_hash` from the message row's own `source_content_sha256` (`content_chunk`
  has neither column), the frozen watermark compares `content_chunk.created_at`, and the
  `projection_kind` default is `'content_chunk'`. The embedder contract moved off the
  NIM-retired `nvidia/nv-embed-v1`/4096-d to `nvidia/nemotron-3-embed-1b`/2048-d — safe
  because `EvidenceChunkV1` does not exist in Weaviate yet (verified live). The Python chunk
  writer in `server/evidence/store.py` is retired fail-closed; the Go message-window chunker
  Activity (Stage 3, below) is the writer. Full record:
  `docs/reviews/2026-09-05-h04-bridge-and-weaviate-feed-rewire.md`.
- ☐ Register `execute_structured_elt_activity` in the worker + extend to emit the standard
  `RawRecordEnvelope` per Q1 (B6, Q1) [Go — needs deny lifted on `modules/engine/**`].
- ☐ Fact/claim ID scheme + AI-GEN source category + `kind` field on normalized record
  (round-4 #4/#5) — schema decision [Opus draft, owner rule].

### Stage 2 — Gateway live (owner + Sonnet)
- ☐ Owner: mint `tag:docker` Tailscale auth key → `/data/agno/secrets/tool-gateway/ts-authkey`;
  add materialize mount to platform-tools (bounces it) (B5).
- ☐ Deploy tool-gateway via Coolify; verify `svc:tool-gateway` on the tailnet; rehearsal passes
  `assess_source_repair`.

### Stage 3 — First real ingest: Google Voice (~29k HTML + 502 MP3)
- ☐ Route per Q5; classify emits file class + extract-only? + tentative group + package.
- ☐ Message-window chunker activity (new, per Q7) + provenance rows; provisional window if Q6=A.
- ☐ Embedding activity: outbox → Weaviate, nemotron-3-embed-1b 2048-d; TextUnit objects carry
  validity window + PG source coordinate.
- ☐ `group_conversations` pass 2 via `registry.id_xref` as-of message date (pre-mortem #4).
- ☐ Near-duplicate marker native-export ↔ screenshot-OCR (round-3 #7, kept: recent ruling on
  corroboration both directions).
- ☐ Interactive preview: N records, per-field fix, "10 more", chunk boundary drawn (D-135).
  HITL = Temporal Signal + wait_condition (round-3 #4).
- ☐ Singleton/detail-stability flag at extraction (round-4 #6).
- ☐ Verify/apply `0006_behavior_seed.sql` (round-5 #6).
- ☐ Assert `record_count > 0` on every parsed file; ELT-vs-decoder count disagreement handled
  per Q4.

### Stage 4 — Retrieval layer (LlamaIndex + LangGraph, as Temporal activities)  [Opus design]
- ☐ Neo4j `sat-temporal`: Item/Version/Action/TextUnit/Theme/ItemType labels per Stage-0
  mapping; PREV/NEXT light edges + Version chain/HAS_CURRENT for consequential; edge-label
  discipline (Q12); PG source coordinate + 7 version-stamp fields on every node/edge.
- ☐ LlamaIndex: PropertyGraphIndex over `sat-temporal` + Weaviate vector store; nodes from
  message rows; the four Cypher primitives as composable retrievers; concept-first and
  chunk-direct entry callables; temporal-filter-first.
- ☐ LangGraph state machine: multi-query expansion → parallel PG / Weaviate / Neo4j →
  timeline verify → independent verification pass that can disagree → block/warn/escalate on
  unsupported → synthesis with PG-coordinate citations → scope report. Caller-blind unit;
  also runnable inside n8n agent nodes.
- ☐ D-093 no-fusion between lanes preserved; lane-labelled envelopes; comparison join only.
- ☐ Maximal determinism rule: one LLM step at entry, zero in traversal.
- ☐ Chunk-window bake-off on Google Voice (Q6): recall@k, MRR, expansion precision,
  boundary-straddle, TG-RAG incremental re-index cost; owner rules N.

### Stage 5 — Promotion to evidence (owner-gated)
- ☐ `promote` activity: re-read sealed original, H1/H2/H3 over envelope bytes, write
  `evidence.*` mirrors + `working_evidence_link` (never mutate working; never re-embed).
- ☐ Promotion unit per Q10; verdict per artifact; conversation group as review unit.
- ☐ `verified`/`disputed` flag on projection rows (round-4 #8); corrected-fact propagation
  (round-4 #9); review gate before consequential use (round-4 #10).
- ☐ Stable exhibit IDs; closed-world citation contract; court-release freeze/sign txn;
  EDRM/load-file export (round-5 #9–11).
- ☐ Daubert/Frye + admissibility documentation pass over the custody code (round-3 #8).

### Stage 6 — Later
- ☐ STAR-RAG rule graph + PPR at the guide's size trigger.
- ☐ Ed25519-signed custody chain; Tether models; SBV absorption (D-131); agno_app role
  cutover; horizon predicate → ADR-0059 source-class; Semantica activation; native
  evidence-vector cutover; repo/legal/client names (D-137, forked session).

## Review round 4 — retrieval / verification context docs (Sonnet reader, 18:3x)

Sources (recent, Aug 2026): multi-query retrieval transcript (origin of "Temporal as brain, n8n
as hands", n8n MCP Server Trigger exposing workflows atomically to a LangGraph agent — this is
where LangGraph legitimacy comes from); Mary Technology verification whitepaper; Legal Fact
Management guide; timesketch/@court transcript; prompt-refinement 2026-08-29 (two captures).
Retrieval-layer REQUIREMENTS not in the plan (all recent, all live):
1. [foundation] Multi-query expansion stage before first retrieval when recall is weak.
2. [foundation] A verification pass structurally independent of the generator, able to DISAGREE
   (whitepaper control c).
3. [foundation] Defined response on unsupported/conflicting material: block / warn / escalate,
   never silent absorption (control d).
4. [foundation] Deterministic fact/claim-level ID scheme distinct from message ids
   (SRC-/EV-/CL-/… from 2026-08-29), and an AI-GEN source category — "the dominant
   hallucination vector is my own past output getting promoted to your decision."
5. [before ingest] Source-hierarchy field (`kind`: conversation vs summary/derived) on the
   normalized record.
6. [first ingest] Singleton/detail-stability flag at extraction (SINGLETON_SPECIFIC) marking
   high-risk grounding targets.
7. [post-promotion] Scope report with every retrieval answer: what was searched, excluded,
   unresolved (control b).
8. [post-promotion] `verified` / `disputed` reviewer flag on the projection/chunk row (not the
   hub — D-136).
9. [post-promotion] Corrected-fact propagation into later retrieval outputs.
10. Consequential use (filing/affidavit/export) requires a review gate the caller cannot skip.
Plus: retrieval never applies a horizon filter (D-073/D-080); retrieval unit is caller-blind
(D-130). One flag: SocialListeningAPI file carries a live API key — unrelated, not reproduced.

## Review round 3 — owner's ingest design docs vs this plan (Sonnet reader, 18:27)

Sources: conversation_ingestion_system_design.md (2026-01-06), Claude chat-pipeline-for-PG.md,
archive-triage-parser-schema-lineage-2026-08-09.md, doc-classify-*.md, temporal.md,
Instance-level MCP.md, forensic-software-editor.md (all in Downloads).

GAPS (sequence bucket in brackets):
1. [before ingest] Known-schema fingerprint matcher for UNREGISTERED export formats — plan has
   only static registered parsers, no discovery path.
2. [before ingest] Unmerged `feat/messaging-parsers-owner-custom` iMessage attachment-leakage
   guard (549-line variant) — merge or reject before iMessage is in a batch.
3. [first ingest] **Interactive preview loop**: batch of N records, per-field manual fix, "show
   10 more" (design:314-424). Plan has one approve/reject gate. This IS the D-135 preview.
4. [first ingest] HITL mechanism = Temporal Signal + `wait_condition` (push), per temporal.md.
   Plan names no mechanism.
5. ✖ ~~UTC→US/Eastern timezone normalization field~~ — STRUCK 18:5x, owner: keep BOTH the
   original (raw `tz_offset_min`, verbatim `source_timestamp_raw`) and the normalized UTC
   `occurred_at`; local time is a VIEW, never a column. Already built: `analysis.time_assertion`
   (`tz_offset_minutes`, `tz_source` ∈ exif/export_header/assumed_local/device_setting/unknown).
6. [first ingest] SMS/MMS status/type integer → label decoder.
7. [first ingest] Near-duplicate marker for the same conversation as native export + screenshot
   OCR (DuplicationMarker in the design) beside chunk hashing.
8. [after promotion] Daubert/Frye four-factor + court-admissibility documentation pass over the
   custody/promotion code (forensic-software-editor.md) — no deliverable produces it.
9. [after promotion] Integration contract evidence.* → `LegalSourcePackage` consumer.
FLAGS: PII transformer in the Jan design conflicts with "no redaction during work" — needs
re-ruling before build. LiteLLM/Supabase/Qdrant appendices are dead (ADR-0042, D-042).
A Downloads file carries a live n8n bearer token — not tracked; rotation awareness only.

## Review round 1 — corrections to the synthesis below (2026-09-03, 3 Sonnet reviewers + Opus orchestrator)

**Owner ruling 14:29:** DuckDB ELT output lands in `raw.*` ("Yes, it gets written to raw"), then the
existing normalize/persist/verify gates. The diagram below drawing ELT → hub directly is STRUCK.

**Owner ruling 14:30:** the ELT "cannot honor byte-exact construction" comment is a DESIGN ERROR
inherited from a different platform/agent without this repo's context, not a constraint to design
around. "It needs to ELT into raw. It needs to serve the same function as the parsers, with the
same contract and the same workflow." → ELT is a parser: same raw-landing contract, same
normalize/verify gates, same promotion path. The "decoder becomes the promotion-path extractor"
proposal (item 4 below) is STRUCK. Whatever the parser→raw contract requires (incl. any byte-span
fields, if ruled), the ELT template must emit too, or it fails the contract like any other parser.
Standing rule: when a design was authored on another platform, reconcile it against current
rulings before adopting a single claim from it.

Verified defects in the synthesis (kept visible, not silently fixed):
1. `execute_structured_elt_activity` ALREADY EXISTS (`modules/engine/activities/elt_structured.go`,
   `postgres/elt_structured_repository.go`, 2026-09-02); unregistered in the worker. Step (8) is
   "register + extend", not greenfield.
2. The ADR-0052 outbox is NOT built ("nothing below is built"). "Hub write + outbox row in one txn"
   depends on it. The txn pattern is proven in the ELT repository; the table is missing.
3. Proposed ELT signature lacked an idempotency coordinate; existing specs carry RequestID/Attempt
   or IngestRunID (D-130 r3). A free-text target table is new, riskier architecture.
4. **Load-bearing (orchestrator):** H2 is defined over raw record BYTES pre-decode. DuckDB decodes
   before PG sees rows (`elt_structured_repository.go:9-24` says so). ELT-extracted files cannot
   yield H2 spans → promotion fails closed on them. Consequence: the Go decoder is not retired to
   fallback; it becomes the PROMOTION-PATH EXTRACTOR + divergence check. OPEN: must `raw.*` carry
   byte offsets; which extractor promotion re-parses under.
5. Tool gateway is built + tested, NOT deployed. Diagram must not draw it live.
6. `evidence.*` ≠ the link table. Mirrors get rows; `working_evidence_link` is separate.
7. Chunker step bundled chunk + provenance + hash = 3 jobs (D-130 r1). Split or rule the contract.
8. Weaviate feed (`server/evidence/vector_projection.py`, enqueue fn) reads the DROPPED
   `working.normalized_record_chunk` → raises today. Rewire to `working.content_chunk` is real work.
9. PREV/NEXT (structural) and ADR-0062 claim edges (asserted) both land in `sat-temporal`; no edge
   label discipline stated. Needs a naming rule.
10. `modules/engine/AGENTS.md:34-38` still asserts ingest-time custody order + "normalized text skips
    parse" — superseded; same-turn drift fix owed.
11. "Add an ordinal to the hub row" re-litigates D-116; `thread_ordinal` on the context-thread
    projection is the consistent source.
12. Reversibility inverts priority: byte spans / source coordinate / link shape are Type-1 — rule
    first. Chunk window / Chonkie / Weaviate schema are Type-2 — measure later.
13. Constraint (ToC) = operator review at promotion. Chunking must be adequate, not optimal, before
    first promotion.
14. Pre-mortem #1 for Google Voice: HTML qualifies as BOTH extract-only and the registered parser's
    target; router has no tie-break. #5: one-activity-per-file vs set-based ELT glob conflict.

## Coherent architecture — reconciling everything discussed today (synthesis — SUPERSEDED IN PART, see above)

> Five things were designed today in separate threads and never stated as one system.
> This section is that one system. Nothing here overrides an owner ruling; it wires
> the rulings together and names the seams between them.

**The single organizing principle:** every store downstream of PostgreSQL is a
**projection with a PG source coordinate**, written by exactly one path, never fused
with another store's output. That rule (2026-08-29 dual-graph design; D-093 no-fusion;
ADR-0052 outbox) is what makes DuckDB-ELT, the message-window chunker, and the
SAT-RAG graph nodes compatible instead of competing.

```
                         ┌─────────────────────────┐
  R2 (cold) ── locator ──▶  Tool Gateway (tsnet)    │  D-132/D-134 — acquires bytes,
                         │  acquisition.SchemeRouter│  never parses
                         └────────────┬────────────┘
                                      │ local path
                    ┌─────────────────┼─────────────────┐
                    ▼                                    ▼
       EXTRACT-ONLY (rows already exist)        MUST-PARSE (opaque)
       JSON/JSONL/CSV/Parquet, XML/HTML-as-text  PDF, images/OCR, docx layout
                    │                                    │
       duckdb_elt_activity (PRIMARY)            Go/Python decoders (PRIMARY,
       pg_duckdb query, one Activity,           unchanged, per-format, one
       writes normalized rows + outbox row      job each — D-130)
       in one PG transaction                              │
                    │  on failure ──────────────▶  same Go/Python decoder
                    │                              (FALLBACK, not parallel)
                    └─────────────────┬──────────────────┘
                                      ▼
                        working.normalized_record  (THE HUB)
                        content + timestamps IMMUTABLE (D-136)
                                      │
                        message-window chunker Activity (NEW, D-130 rule 7)
                        writes working.content_chunk +
                        working.content_chunk_message provenance
                        (unit: bake-off, §9 — N-neighbor / session / Chonkie)
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                  ▼
              Weaviate           Neo4j `sat-temporal`   SurrealDB
           (hybrid search,     message nodes + PREV/NEXT  (manual promotion
            outbox-fed,        edges, PG source coord,     ONLY, D-107;
            points at hub —    lane-labelled, no fusion    walks + horizon
            no re-embed at      with Semantica `evidence`   deltas live HERE
            promotion)          graph (D-093)                and ONLY here —
                    │                 │                     D-073/D-080)
                    └────────hit → chunk_id → provenance → center_message_id
                             → expand ON THE MESSAGE TABLE (PREV/NEXT,
                               conversation_id + ordinal), dedupe on center id
                             → return MESSAGES, never chunk text
                                      │
                                      ▼
                     Retrieval unit: one bounded callable
                     (direct / Temporal Activity / n8n node — D-130 rule 4)
                     consumed by ANY agent runtime (Agno is one adapter
                     under replacement, not the audience — 2026-09-03)
                                      │
                                      ▼
                        evidence.* (link table, promotion-time ONLY —
                        hub-and-mirror, D-069, ingest-simplification-plan.md)
```

**How each thread reconciles:**

| Thread | Where it sits | Why it doesn't conflict |
|---|---|---|
| DuckDB ELT (this conversation) | Primary path for extract-only classes, Go-orchestrated, one Activity | It writes to the same hub table the Go decoders write to. Downstream (chunker, graph, search) cannot tell which path produced a row — the hub contract is the interface. |
| Message-window chunk + SAT-RAG node model (this session, →ADR-0063 draft) | One stage below the hub, feeding all three projections | Chunk = index handle only, never a store's unit of truth. Graph nodes are messages, not chunks — this is what makes Neo4j and Weaviate agree on what a "hit" is. |
| Hub-and-mirror / evidence promotion (2026-09-03 pivot) | After everything above, on owner action only | Vectors and graph edges point at the working row; promotion adds a link row, never re-embeds, never re-runs extraction on the hub side. |
| Horizon walks / delta (project canon, D-073/D-080) | SurrealDB, analysis phase, exclusively | Confirmed again here so nothing upstream (chunking, retrieval expansion, DuckDB ELT) ever applies a horizon filter. That filter has exactly one home. |
| Atomicity (D-130) | Every box in the diagram is one Activity or wraps as one n8n node | The gateway, the ELT query, the chunker, and the expansion unit all satisfy "callable direct / Activity / n8n node, doesn't know its caller." |
| LlamaIndex | **Not in this diagram.** | Owner ruling 2026-09-03: no. Struck from the ADR draft and this synthesis. |
| Rename (propria) | Orthogonal — naming, not architecture | Doesn't touch this diagram; tracked separately (D-137, forked session). |

**What is still a bake-off, not a ruling, inside this diagram:** the chunk window unit
(N/session/Chonkie, §9), the expansion ordinal source, and the provenance table's exact
shape. Everything else in the diagram is either already ruled (cited above) or newly
proposed in this plan and awaiting approval.

## Genuinely open — owner rulings needed

1. Window unit and N — measured by the bake-off, not chosen here.
2. Expansion ordinal: `first_party_context_thread_message.thread_ordinal` exists; `normalized_record` has no per-conversation ordinal. Add one to the hub row, or key on the thread projection?
3. Provenance table name/shape.
4. May expansion step outside a sealed D-093 manifest's membership, and how are such neighbors labelled?
5. Does the same contract later serve AI-chat (`working.chat_message`)? Out of scope now; ADR-0053 §3 stands.

## Execution steps — only after the owner approves this plan

Every step runs as a subagent on owner command. Nothing writes before that.

1. **Write ADR-0063** `docs/adr/0063-sat-rag-message-node-model-and-neighbor-expansion.md`, Status *Proposed — ITERATING*, from the table above. Draft text already exists in this session's transcript and is reused verbatim minus every LlamaIndex mention.
2. **Append D-138** to `docs/DECISION_LOG.md` (check the tail: D-137 is the propria ruling; the ingest plan still tells a future session to append "D-137" for custody-at-promotion — renumber whichever lands second).
3. **Same-turn drift fixes:** `docs/design/surrealdb-analytical-surface.md:188-200` (gap → pointer to ADR-0063); `docs/planning/2026-09-03-ingest-simplification-plan.md:71,78-80` (chunk unit = ADR-0063 window under evaluation; Phase 3 chunk stage emits provenance rows); `docs/adr/README.md` (append 0062 AND 0063 — index stops at 0061); memory note `dont-relitigate-chunking-pipeline-adr-0053.md` (messaging unit tracked in ADR-0063, not settled); `docs/adr/0041:34-36` dated note that "Agno-native orchestration" is superseded by D-107.
4. ~~**Migration** `sql/00NN_content_chunk_message_provenance.sql` — the provenance table; zero-net-write validated (apply in a txn, count, rollback) against live PG before apply.~~ **DONE 2026-09-05** as `sql/0072_content_chunk_message_bridge.sql`, rollback-validated live exactly as specified (applied twice in one txn, function exercised, ROLLBACK, absence re-asserted). Still to do: push → apply live → redeploy. See `docs/reviews/2026-09-05-h04-bridge-and-weaviate-feed-rewire.md`.
5. **Go: message-window chunker activity** — new unit, emits chunk rows + provenance rows + `content_sha256`; registered in the stage graph; `go build/vet/test` green.
6. **Go or Python: expansion unit** — input (chunk_id | message_id, K | gap), output message rows + boundary metadata; wrapped as Temporal Activity + n8n binding via the existing flow-binding registry.
7. **Bake-off harness** — runs the §9 comparison on Google Voice, writes receipts, produces the metrics table; owner rules N and the unit; ADR flips to Accepted only then.

## Verification

- Steps 1–3: `git grep` for the old gap paragraph and stale index rows returns nothing; ADR index row present; DECISION_LOG tail correct.
- Step 4: rollback-validated migration output captured in the review doc.
- Step 5: unit test proves every message in a conversation appears in ≥1 chunk and every chunk's provenance rows resolve; boundary messages appear in ≥2 chunks; no chunk crosses a conversation.
- Step 6: live test on ingested Google Voice: a hit at a known chunk edge returns the neighboring messages with no duplicate rows; results contain zero chunk text.
- Step 7: metrics table persisted under `docs/reviews/`; owner ruling recorded before any status change.
