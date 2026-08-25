# Lane 4 — Analysis / Extraction / Promotion Layer: Evidence Inventory

> _Byline: lane-4 agent · Sonnet · 2026-08-24_

EVIDENCE-ONLY. No recommendations. Every claim below is either a live `SELECT`/`information_schema`
result against PG18 `100.91.190.107:5432` db `ai` (read-only session, 2026-08-24) or a `file:line`
citation into `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform`. Anything not
directly observed is marked `UNKNOWN — not verified`.

---

## 1. Analysis schema live truth

**Live query:** `SELECT table_name FROM information_schema.tables WHERE table_schema='analysis'` —
40 objects (35 base tables + 5 views): `completion_evidence, corroboration_flag, court_case,
discovery_request, discovery_request_revision, evidence_item, evidence_task, export, export_item,
export_package, factor_citation, finding, finding_version, human_label, human_label_gold,
knowledge_evidence_promotion, legal_timeline_event, location_assertion, location_contradiction,
matter, matter_knowledge_partition, pattern_finding, redaction, relational_classification,
resolution_evidence, review_decision, review_task, score, task_dependency, task_event,
task_legal_link, task_person, task_revision, time_assertion, timeline_event, vw_court_export,
vw_human_label_long, vw_labeling_progress, vw_message_behavior, vw_open_tasks`.

### Row counts — all 14 requested tables, live, 2026-08-24

| table | row count |
|---|---|
| analysis.timeline_event | 0 |
| analysis.legal_timeline_event | 0 |
| analysis.evidence_item | 0 |
| analysis.finding | 0 |
| analysis.finding_version | 0 |
| analysis.factor_citation | 0 |
| analysis.knowledge_evidence_promotion | 0 |
| analysis.review_task | 0 |
| analysis.review_decision | 0 |
| analysis.relational_classification | 0 |
| analysis.location_assertion | 0 |
| analysis.location_contradiction | 0 |
| analysis.time_assertion | 0 |
| analysis.corroboration_flag | 0 |

**Every one of the 14 target tables is empty.** The analysis schema exists live, fully DDL'd, and
holds zero rows across the board (also confirmed zero: `reference.detection_pattern`=527,
`reference.behavior_category`=164 are seeded/loaded; `working.normalized_record`=0,
`analysis.pattern_finding`=0 — the seed/ontology tables are populated, the analysis/working
runtime tables are not).

### Columns + FKs (condensed; full column lists were pulled live via `information_schema.columns`)

- **timeline_event** (35 cols) — PK `event_id uuid`; no analysis-schema FK constraints found pointing
  out of it in `information_schema.table_constraints` for this table itself (it is the FK *target*
  of `time_assertion.event_id`).
- **legal_timeline_event** (21 cols) — `case_id uuid NOT NULL`, `evidence_item_ids uuid[]`,
  `normalized_record_ids uuid[]` (array refs, not FK-enforced).
- **evidence_item** (42 cols) — `matter_id`/`court_case_id` FKs to `analysis.matter`/`analysis.court_case`
  (added by migration 0030, see §3); `supersedes_item_id` self-FK.
- **finding** (29 cols) — `contradicts_finding_id` self-FK; `subject_refs uuid[]` (array, not FK-enforced).
- **finding_version** (6 cols) — `finding_id` FK → `analysis.finding.id` (`finding_version_finding_id_fkey`).
- **factor_citation** (16 cols) — `evidence_item_id` FK → `analysis.evidence_item.id`;
  `supersedes_citation_id` self-FK.
- **knowledge_evidence_promotion** (19 cols) — multi-column composite FKs into `analysis.evidence_item`,
  `analysis.court_case`, `analysis.matter_knowledge_partition` (constraint
  `knowledge_evidence_promotion_item_scope_fkey` etc. — see §3 for full DDL/guard).
- **review_task** (10 cols) — no outbound FK; `target_id uuid` + `target_kind text` is a polymorphic
  reference, not FK-enforced.
- **review_decision** (18 cols) — `task_id` FK → `analysis.review_task.task_id`.
- **relational_classification** (30 cols) — `subject_id uuid` + `subject_type text` polymorphic,
  not FK-enforced.
- **location_assertion** (16 cols) — `subject_id uuid` + `subject_type text` polymorphic, not FK-enforced.
- **location_contradiction** (13 cols) — `claimed_assertion_id`/`observed_assertion_id` FKs →
  `analysis.location_assertion.id`.
- **time_assertion** (29 cols) — `event_id` FK → `analysis.timeline_event.event_id`; `superseded_by` self-FK.
- **corroboration_flag** (12 cols) — no outbound FK; `target_id text` + `target_kind text` polymorphic.

---

## 2. Realization events — validates the FK-target question

**Not in `analysis` schema.** Live search across all schemas
(`information_schema.tables WHERE table_name ILIKE '%realization%'`) found it in **`working`**:
`working.realization_event`, `working.realization_event_record`, `working.walk_step_realization_retrieval`.

- **`working.realization_event`** (12 cols, row count **0** live): `id uuid PK`, `case_id text`,
  `kind text`, `realized_at timestamptz`, `trigger_record_id uuid`, `evidence_pointer jsonb`,
  `proposer text`, `approval_state text`, `proposed_at`, `approved_at`, `approved_by`, `notes`.
- **FK target — THE finding**: `realization_event.trigger_record_id` → **`working.normalized_record.id`**
  (constraint `realization_event_trigger_record_id_fkey`, live `information_schema` result).
  `working.normalized_record` is **not messages-only**: its live CHECK constraint
  `normalized_record_record_type_check` is
  `CHECK (record_type = ANY (ARRAY['message','call','event','media']))`. So the FK target today is a
  generic normalized-record table spanning 4 record kinds, not a message-only table — the question's
  premise ("validates whether the FK target today is messages-only") is **false as designed**: the
  schema already generalizes past messages. (Whether every kind is actually populated is moot — the
  table is empty; see below.)
- **`kind` check constraint** (`realization_event_kind_check`, live):
  `CHECK (kind = ANY (ARRAY['contradiction','export_read','told_by_person','manual','betrayal','deceit','gaslighting','pattern_recognition']))`.
- **`approval_state` check**: `ANY (ARRAY['proposed','approved','superseded'])`.
- **`proposer` check**: `ANY (ARRAY['algorithm','owner'])`.
- **Row count: 0** (`working.realization_event`), **0** (`working.realization_event_record`),
  **0** (`working.normalized_record`).
- **Real writer code exists**: `server/evidence/realization.py:1-45` (234 lines total) is a real,
  non-stub writer module ("Realization events are separate, plural knowledge atoms... Lifecycle
  (append-only)... propose -> approve -> supersede"), gated by an `@approval` decorator on
  `realization_approve`/`realization_supersede` tools per its own docstring
  (`server/agents/tools/realization_tools.py`, not independently opened in this pass). Also referenced
  in `server/case_management/repository.py`, `server/contracts/case_management.py`,
  `server/contracts/records.py`, `server/evidence/derivation.py`, `server/api/inspect_routes.py`, and
  SQL migrations `sql/0026_realization_event.sql`, `sql/0027_walk_ledger.sql`,
  `sql/0029_pass_grants.sql`, `sql/0023_drop_context_record_disclosure_tier.sql`. The mechanism is
  live-DDL'd and code-wired, but has never been exercised (0 rows both sides of the FK).

---

## 3. The promotion gate — `analysis.knowledge_evidence_promotion`

**Migration**: `sql/0030_matter_case_foundation.sql`. Header (`sql/0030_matter_case_foundation.sql:6-13`):
> `✅ APPLIED TO PROD 2026-08-23 on owner instruction — 100.91.190.107:5432 db=ai ... analysis.matter,
> analysis.court_case, analysis.matter_knowledge_partition and analysis.knowledge_evidence_promotion
> all CREATED; both promotion triggers (knowledge_evidence_promotion_guard,
> knowledge_evidence_promotion_append_only) installed; analysis.evidence_item gained matter_id +
> court_case_id ... its row count was 0 before and 0 after.`

Table DDL: `sql/0030_matter_case_foundation.sql:159-224`. Guard function DDL:
`sql/0030_matter_case_foundation.sql:252-338` (`analysis.guard_knowledge_evidence_promotion`).
Trigger install: `sql/0030_matter_case_foundation.sql:338-343`.

**Live `pg_get_functiondef` of the guard** (`analysis.guard_knowledge_evidence_promotion`,
trigger `knowledge_evidence_promotion_guard`, `BEFORE INSERT`):
- Rejects any row where `NEW.knowledge_lane <> 'evidence'`.
- Rejects if `NEW.source_pointer_hash` doesn't match `analysis.knowledge_evidence_pointer_hash(NEW.source_pointer)`.
- Rejects if the `source_pointer` JSON fields (`matter_id`, `court_case_id`, `partition_key`, `lane`,
  `normalized_record_id`, `evidence_hash_id`, `source_id`) don't exactly match the row's own columns.
- Looks up `analysis.evidence_item` by `NEW.evidence_item_id` and **requires it to already be**
  `review_status = 'unreviewed'`, `hitl_required = true`, `safe_for_legal_use = false`,
  `is_authenticated = false` — i.e. the guard enforces a **pre-condition state**, not a transition.
- Cross-checks `evidence_item`'s scope/provenance columns against the promotion row.
- Looks up `working.normalized_record` by id and requires `case_id`/`artifact_id`/`provenance_id` to
  match the promotion row's `partition_key`/`evidence_hash_id`/`source_run_id`.
- Looks up `evidence.evidence_hash` and requires `algo='sha256'`, `canon_version='h1-rawbytes-v1'`,
  32-byte digest matching `source_pointer->>'sha256'`.
- A second trigger, `knowledge_evidence_promotion_append_only` (`BEFORE UPDATE OR DELETE`), calls
  `working.forbid_mutation()`, whose live body is a **dev gate**: it only raises when
  `current_setting('app.evidence_live', true) = 'on'`; otherwise UPDATE/DELETE pass through silently
  (comment: `-- DEV GATE (0031): armed only when live. Owner ruling 2026-08-24.`).

**What flips evidence status**: grepping `sql/0030_matter_case_foundation.sql` for
`review_status\s*=|UPDATE analysis.evidence_item|safe_for_legal_use\s*=` returns **zero matches**.
The migration contains no UPDATE statement at all (also stated explicitly in its own header:
"Pre-flight confirmed the file contains no DROP/DELETE/TRUNCATE/UPDATE"). **The guard trigger only
validates an INSERT into the promotion ledger; nothing in this migration or its trigger flips
`evidence_item.review_status`/`safe_for_legal_use`/`is_authenticated`.** The promotion table is a
pure append-only audit ledger over already-existing evidence_item rows, not a status-transition
mechanism. Whether some other, unexamined code path (an agent tool, an API route) performs that
UPDATE is `UNKNOWN — not verified in this pass`.

---

## 4. Semantica — where it lives, HTTP surface, formats

**Location**: fully vendored at `server/vendored/semantica/` (a complete upstream Semantica repo
tree — parsers, ingestors, benchmarks, its own `.venv`). Platform-owned integration code lives in
`server/analysis/`: `semantica_wiring.py` (182 ln), `semantica_contracts.py` (177 ln),
`semantica_worker.py` (325 ln), `semantica_candidates.py` (333 ln).

**HTTP surface**: the vendored library ships its own server —
`server/vendored/semantica/semantica/server.py:5-20,58` (`"...using FastAPI and uvicorn"`,
`app = FastAPI(...)`, `uvicorn.run(app, host="0.0.0.0", port=8000)`). Grepping the entire non-vendored
`server/`, `docker/`, `docs/` tree for any reference to this server (`semantica.server`,
`semantica_server`, `semantica/server.py`) found only two hits, both documentation, not wiring:
`docs/reference/agno-memory-and-storage/06-semantica.md:65-66` (describes upstream Semantica's CLI/
server as a capability) and `docs/wiki/skills/orchestration/mcp-protocol.md:27` (a generic example
snippet). **No platform code imports, launches, or calls this FastAPI server.** The platform
integration is entirely **in-process Python**: `server/analysis/semantica_worker.py:33-36` imports
`server.vendored.semantica.semantica.semantic_extract.{event_detector, methods, ner_extractor}`
directly as library calls — there is no CLI invocation and no HTTP round-trip.

**`SBV_BASE_URL` is unrelated to Semantica.** It belongs to a separate service: SBV, "the Go parse
engine for the context lane" (`server/analysis/sbv_transcript.py:2-26`), reached via
`server.tools._sbv_client` (`server/tools/_sbv_client.py:47-48`, default
`http://localhost:8085`, in-cluster `http://platform-tools:8085`). Nothing in `semantica_wiring.py`,
`semantica_worker.py`, `semantica_contracts.py`, or `semantica_candidates.py` references
`SBV_BASE_URL` or the SBV client — confirmed by grep of those four files. SBV and Semantica are
two independent parse/extraction paths.

**Formats it processes, per code — narrower than the vendored library's capability.**
`server/analysis/semantica_contracts.py:17-27` (`ExtractionRecord`) locks its one input field:
`source_raw_table: Literal["working.normalized_record"] = "working.normalized_record"` and
`content: str` (plain text, hash-validated against `content_sha256`). The vendored library's
`server/vendored/semantica/semantica/parse/` directory does contain per-format parsers
(`csv_parser.py`, `docx_parser.py`, `email_parser.py`, `excel_parser.py`, `html_parser.py`,
`image_parser.py`, `json_parser.py`, `pdf_parser.py`, `pptx_parser.py`, `xml_parser.py`,
`docling_parser.py`, `web_parser.py`, `code_parser.py`, `structured_data_parser.py`, plus a
matching `ingest/` layer for API/DB/email/feed/gdrive/HuggingFace/Mongo/repo/Snowflake/stream/web
sources) — **but none of that parse/ingest layer is imported by `semantica_worker.py` or
`semantica_contracts.py`**. The platform's actual Semantica usage is text-in (already-normalized
`working.normalized_record.content`), NER/relation/event-pattern-out — it never touches a raw file
format. `semantica_worker.py:166,228,278` calls only
`_methods.extract_entities_pattern`, `_methods.extract_relations_pattern`, and
`EventDetector.detect_events` (all deterministic pattern/regex methods, no model calls per
`semantica_worker.py:1-9`: "never loads a model provider or store").

**Wiring status**: `semantica_wiring.py:133-149` (`worker_wiring()`) documents the worker as
credential-free (`"store_credentials": []`), candidate-only
(`"forbidden_writes": ["evidence.*", "neo4j", "weaviate", "surrealdb", "graphiti"]`), writing only to
`working.candidate_entity`, `working.candidate_fact`, `working.candidate_event`
(`semantica_candidates.py:3-5,22-40`, real INSERT SQL). Live counts: `working.extraction_run`=0,
`working.candidate_entity`=0, `working.candidate_fact`=0, `working.candidate_event`=0. Grepping
`server/` for `SemanticaPatternWorker` finds it only defined in `semantica_worker.py:120` and
referenced as a string in `semantica_wiring.py:139` — **no pipeline runner, API route, or agent tool
instantiates it**; the only callers are `tests/test_semantica_phase1_worker.py` and
`tests/test_semantica_wiring.py`. **Conclusion: real, tested extraction code exists and is
functionally isolated per its own design docs, but it is not wired into any live/triggered
pipeline** — zero production writes anywhere downstream of it.

---

## 5. Behavioral analysis — `server/analysis/` modules

**Runner**: `server/analysis/detection.py` (405 ln) — "behavioral DETECTION RUNNER"
(`detection.py:1-8`): "Scans every `working.normalized_record` against the seeded behavioral
ontology (`reference.detection_pattern` + `reference.behavior_category`, migration 0006: 512
patterns / 153 categories / 51 lexicon terms) and writes one `analysis.pattern_finding` per
(record × pattern-match)". Court-safety invariants documented inline
(`detection.py:10-25`): symmetric application (no party filter), every finding written as
`bias_caution=true`, `requires_human_review=true`, `is_verified=false`,
`review_status='unreviewed'`, `safe_for_legal_use=false`, `data_tier='inferred'`. Deterministic
literal/regex matching only, no model calls (`detection.py:28`). Related modules present but not
individually traced in this pass: `patterns.py` (285 ln), `cpu_lane_classifier.py` (207 ln),
`lane_classifier.py` (261 ln).

**Config**: `server/analysis/config/behavioral_patterns.json` (878 lines, top-level JSON `dict`
with 4 keys — key names not enumerated in this pass), plus
`server/analysis/config/coercive_control_analyzer_prompt.md` and
`server/analysis/config/court_safe_language_map.json` in the same directory.

**Tables written**: `analysis.pattern_finding` (live row count: **0**). Seed tables it reads are
populated live: `reference.detection_pattern` = **527** rows, `reference.behavior_category` = **164**
rows (both higher than the 512/153 the docstring cites — `UNKNOWN — not verified` whether the extra
rows are a newer seed or drift between doc and DB, not investigated further in this pass).

**Owner-flagged over-flagging rework — recorded, exact quotes**:
- `docs/reviews/2026-08-23-cross-repo-evidence-audit/ISSUES-AND-TODO.md:227` (ISS-049):
  > "The behavioral-analysis mechanism over-flags and needs a full rework. Owner ruling 2026-08-23:
  > 'that whole analysis is broken… the mechanism is bad, it over-flags everything, that whole
  > process has to be reworked.' ... Do not invest further in the custom ontology (ISS-045, ISS-046)
  > until the mechanism is redesigned."
- `docs/EVIDENCE_MERGE_MAP.md:388`: "per owner ruling 2026-08-23 the behavioral-analysis mechanism
  over-flags and..." (line truncated at grep boundary; full context not re-pulled in this pass).
- `docs/HANDOFF-2026-08-24-ingest-testing.md:71`: "SMS behavioral analysis rework — over-flags
  everything; whole process reworked later."

---

## 6. Surreal projection status

**Code presence**: grepping `server/` (non-vendored) for `surreal` (case-insensitive) hits:
`server/agents/factory.py`, `server/agents/providers.py`, `server/analysis/semantica_candidates.py`
(only as a name in a "does NOT touch" list, see §4/§7), `server/analysis/semantica_wiring.py`,
`server/api/main.py`, `server/api/workflow_registry.py`, `server/core/session.py`,
`server/temporal/workflows.py`, `server/temporal/__init__.py`. Individual line-level roles in each
file were **not traced in this pass** — flagging as `UNKNOWN — not verified` beyond confirming the
string's presence in those 9 files.

**Phase-1 runner**: `docker/surreal-phase1-runner/` exists with a real source tree —
`Dockerfile`, `fixtures/`, `pyproject.toml`, `queries/`, `schema/`, `src/horizon_surreal_phase1/`,
`tests/`, `uv.lock` — i.e. a packaged Python project, not a stub directory.

**Newest handoff STATUS line** — `docs/pending-review/handoffs/HANDOFF-2026-08-17-R14-phase1-surreal-live-core-pass.md`
is the newest file in `docs/pending-review/handoffs/` by filename date (confirmed by directory
listing sorted; no handoff dated after 2026-08-17 exists in that directory). Its exact status lines
(`HANDOFF-2026-08-17-R14-phase1-surreal-live-core-pass.md:11-12`):
> `STATUS: CORE LIVE GATES PASS; FULL R13 GATE SET PARTIAL; TARGET STOPPED`
> `BUILD_STATUS: 20 ISOLATED TESTS PASS; FOCUSED RUFF PASS; FULL REPOSITORY SUITE NOT RERUN`

**Newer-than-R14 information found elsewhere (not a handoff file, but dated later and directly
on-point)** — the untracked working file `docs/COMPACT-SUMMARY-2026-08-24.md` (git status: `??`,
i.e. present in the worktree but not committed) records a live, still-open contradiction, quoted
verbatim:
> `docs/COMPACT-SUMMARY-2026-08-24.md:749`: "#14: OWNER — BLOCKING. SurrealDB formally RETIRED
> (ADR-0043, owner ruling 2026-08-06) yet `data-surreal-phase1-t0-r1` is live in Coolify production
> and was ordered promoted 2026-08-20. Needs owner ruling."
> `docs/COMPACT-SUMMARY-2026-08-24.md:845`: "**#14 OWNER — BLOCKING**: 'SurrealDB is formally RETIRED
> (ADR-0043, owner ruling 2026-08-06) — yet `data-surreal-phase1-t0-r1` is live in Coolify production
> and was ordered promoted on 2026-08-20. These cannot both be current intent.'"

This is a document claim, not independently re-verified against live Coolify state in this pass
(no Coolify API call was made) — marking the "live in Coolify production" half as
`UNKNOWN — not independently verified`, reporting only that the newest on-disk document states it
as an open, owner-blocking contradiction as of 2026-08-24.

---

## 7. Neo4j graph — what writes today, Semantica wiring status

**Grep `server/` (non-vendored) for `neo4j`** hits exactly 3 files:
`server/analysis/graphiti_case_client.py`, `server/analysis/semantica_candidates.py`,
`server/analysis/semantica_wiring.py`.

**Actual writer**: `server/analysis/graphiti_case_client.py:1-20` — "minimal Graphiti MCP client,
CASE lane only." Docstring: "AI-chat context must land in Graphiti's `memory` Neo4j database (case
lane), never the `neo4j` platform/dev database and never the `evidence` database (ADR-0036:
`memory` = graphiti_writer, `evidence` = semantica_writer, permission-isolated by design)." Protocol:
MCP streamable-HTTP JSON-RPC over stdlib `urllib`, endpoint `GRAPHITI_CASE_URL` default
`http://100.91.190.107:8073/mcp` (`graphiti_case_client.py:29`), writes DozerDB database `memory`
per the module's own verification note (`graphiti_case_client.py:18-20`: "verified live 2026-08-01
... writes DozerDB database `memory`"). **This is Graphiti's write path, not Semantica's.**

**Semantica → Neo4j is aspirational, not wired, by the code's own admission**:
- `server/analysis/semantica_candidates.py:3-5`: "The worker never imports this module. The
  PostgreSQL adapter can write only the existing `working.extraction_run` and `working.candidate_*`
  tables. It has no custody, Neo4j, Weaviate, Surreal, or promotion operation."
- `server/analysis/semantica_wiring.py:95-101` (`graph_store_config()` docstring): "Approval-gated
  downstream graph-projector config, never worker config. A platform-owned projector is the eventual
  writer, permission-isolated from Graphiti's `memory` database. Semantica emits pending PostgreSQL
  candidates only and never receives this credential or writes either graph directly."
- `server/analysis/semantica_wiring.py:146`: worker's `forbidden_writes` list explicitly includes
  `"neo4j"`.
- `server/analysis/semantica_worker.py:1-9`: "no persistence or projection capability... never loads
  a model provider or store."

**The `evidence` Neo4j database name that ADR-0036 reserves for a future `semantica_writer` role has
no live writer in code today** — it is a documented target role, not an implemented connection.
Corroborated by row counts: `working.candidate_entity`/`candidate_fact`/`candidate_event` are all
0 live, so even the PostgreSQL-side candidate output that would eventually feed a graph projector
has never been produced.

---

## 8-line summary

1. All 14 requested `analysis` schema tables plus `analysis.pattern_finding` are live-DDL'd but
   **100% empty** (row count 0, verified by direct `SELECT count(*)`) — the schema is real, the
   runtime data is not.
2. `realization_event` lives in `working`, not `analysis`; its FK target is
   `working.normalized_record` (record_type check: message/call/event/media) — **not messages-only
   by design**, though it too is empty (0 rows both sides).
3. The `knowledge_evidence_promotion` guard trigger (migration 0030, applied to prod 2026-08-23) is
   a strict INSERT-time validator requiring evidence already be unreviewed/HITL/unsafe/unauthenticated
   — it validates a pre-state, it does **not** flip any evidence status; no UPDATE exists anywhere in
   that migration.
4. Semantica is fully vendored with its own FastAPI server, but that server is **never invoked** —
   platform wiring is in-process Python calling only pattern-based NER/relation/event methods over
   already-normalized text; `SBV_BASE_URL` belongs to an unrelated Go service, not Semantica.
5. Semantica's own code (`semantica_wiring.py`, `semantica_worker.py`, `semantica_candidates.py`)
   explicitly forbids and never performs Neo4j/Weaviate/Surreal writes; `SemanticaPatternWorker` is
   only invoked from its own tests, never from a pipeline/route/agent tool.
6. Behavioral detection (`detection.py`) is real, symmetric, deterministic code writing to
   `analysis.pattern_finding` (0 rows live); the owner ruled it broken 2026-08-23 ("over-flags
   everything, that whole process has to be reworked" — `ISSUES-AND-TODO.md:227`).
7. SurrealDB phase-1 has a real packaged runner (`docker/surreal-phase1-runner/`); the newest handoff
   (R14, 2026-08-17) reports `STATUS: CORE LIVE GATES PASS; FULL R13 GATE SET PARTIAL; TARGET
   STOPPED`; the newer untracked `COMPACT-SUMMARY-2026-08-24.md` records an unresolved owner-blocking
   contradiction (ADR-0043 retirement vs. a live promoted Coolify target) as of 2026-08-24.
8. Neo4j's only live writer today is Graphiti's `memory` database via
   `graphiti_case_client.py`; the `evidence` database reserved for a future Semantica graph projector
   (ADR-0036) has no implemented writer in code.
