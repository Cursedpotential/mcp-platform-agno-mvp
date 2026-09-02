<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# Repo Re-Review — Consistency, Gap Closure, and Documentation Efficiency

Substantial progress is real and verifiable: the schema reckoning landed, CI was restored and extended, and the identity-home problem was actually fixed. But three structural gaps remain open, and the `docs/` tree has become the single largest source of drift in the repository — roughly 46 MB and 700+ files, of which the majority is stale, duplicated, or vendored content that does not belong in a project docs directory.

## What Has Actually Been Closed

The changes since the 08-31 analysis packet are not cosmetic — the load-bearing findings from those attachments were executed.

- **Identity got a home, then got a better one.** Migration `0057` moved the 8 identity tables into `reference`, closing the "backwards FK" anomaly where all 7 `evidence.raw_* → working.device` arrows pointed at a wipeable layer. Migration `0062` then split again into a dedicated `registry` schema on the owner's vocabulary ruling (D-120), because identity tables are "the most linked-TO tables" and belong apart from standalone lookups.
- **The reckoning executed.** `0058_the_reckoning.sql` exists in tree, followed by `0059` (identity trust state), `0060` (test reset), `0061` (confidence-gated tiers), `0063` (retire superseded legacy), and `0064` (park geo lane) — the geo family flagged as PARKED in the table accounting is now backed up to `sql/parked/geo_lane_parked_20260831.sql` rather than lingering as dead weight.
- **The stale-baseline trap is fixed.** `schema_baseline_20260830.sql` replaced the 2026-08-10 `pg_dump` that caused deleted tables to resurrect on every rebuild (D-113). The new baseline is generated from PostgreSQL's own DDL serializers, builds in ~11 seconds, and the README now states the rule explicitly: migrations 0001–0055 are history, not build steps.
- **CI was restored and materially strengthened.** `.github/workflows/validate.yml` and `.gitattributes` — both accidentally deleted in the owner's directory move — are back. The workflow now carries three jobs: Python lint/type/test, a new Go engine job (build/vet/test against `modules/engine`), and the GAP-021 mandatory integration job that *fails rather than skips* when secrets are absent, precisely because a silently-skipped live suite used to read as a green check.
- **The compile break is fixed.** H-02a (`undefined: reference` in `parser/registry.go`) was resolved in `9da8815`, plus a second wave of the same sweep damage found in 12 Python files.
- **Repo restructure landed.** `engine/`, `workbench/`, and `forks/` are now grouped under `modules/`, with `sbv` converted to a proper git submodule of `sbv-forensic` rather than a vendored copy.


## Gaps That Remain Open

### The discovery-delay lever was identified but never pulled

The systems analysis named this the highest-value cheap move available: damage scales with discovery delay, not error severity, and "a test that runs in two minutes converts a 12-hour delay into a 2-minute one." There is still **no CI job that builds the schema from `schema_baseline_20260830.sql` against an empty database**. The scripts exist (`generate_schema_baseline.py`, `_wave0_fresh_restore.py`) but nothing in `validate.yml` invokes them. This is the one falsifiable test the entire root-cause chain pointed at, and it is the gap most worth closing next.

### Naming rules are declared but unenforced

The blueprint made `content_sha256` the only permitted hash column name and explicitly banned `content_hash`. There are still **309 occurrences of `content_hash` across 20+ files**, including `server/timeline/hashing.py`, `server/evidence/vector_projection.py`, `server/contracts/records.py`, and `server/core/evidence_vector_store.py`. Some are legitimately different concepts, but the ban has no linter, no grep gate, and no CI check — which means it will regrow exactly like the FK lattice did.

### Migration chain has five permanent holes

Numbers `0040`, `0041`, `0044`, `0045`, and `0046` do not exist in `sql/`. The dispatch plan already flagged `0045` as a merge-conflict casualty needing an owner ruling (restore a canonical file or renumber the supersession chain), but four others are undocumented. Since the baseline now supersedes 0001–0055 this is low-risk operationally, yet it is a permanent audit hole in a system whose entire premise is provenance.

### Test expectations still assert the pre-move schema

`tests/test_0043_context_source_matter_binding.py` and `tests/test_0054_platform_case_registry.py` still assert `analysis.court_case` and `analysis.matter`. These are frozen-file static checks, so they may be intentional — but nothing in the files says so, which means the next agent to read them cannot tell a deliberate pin from stale drift.

### Wave 3+ work is entirely untouched

H-01 (custody unification across 30 parsers), H-04 (vector cutover), H-05 (retrieval seam), H-07 (pg_duckdb), and H-03 (production write-protection) all remain PENDING. Also outstanding: the 27 pre-existing pytest failures from the AgentOS retirement rework, and `working.enqueue_evidence_vector_projection` still targeting the dropped `normalized_record_chunk`.

## The Documentation Directory Is the Biggest Remaining Liability

This is where the "write more documentation" reinforcing loop from the systems analysis is most visibly still running. `docs/` is 46 MB — and the code it documents is a fraction of that.

### Category 1 — Not documentation at all (~22 MB, delete immediately)

`docs/wiki/project-docs/components/infrastructure/semantica/cookbook/` is a **vendored copy of the Semantica library's cookbook**, including 18 MB of `use_cases/` with biomedical datasets, chunk fixtures, and notebook data. This is upstream third-party content checked into a private forensic platform's docs tree. It has no bearing on the project, cannot be maintained, and inflates every clone, every grep, and every agent context window that touches `docs/`.

Alongside it: `docs/wiki/.plannotator/` (1.6 MB of tool-generated plan history from February–March 2026, organized by Windows user paths like `cusersmattsprojectsthebigone`) and `docs/wiki/_TO_BE_DELETED/` — a directory whose own name is the disposition ruling, still present in tree.

### Category 2 — Backup files committed to git (delete, git is the backup)

```
docs/URGENT-TODO.md.bak-20260824b
docs/URGENT-TODO.md.bak-20260824c
docs/URGENT-TODO.md.bak-20260824d
docs/n8n-model-and-node-notes.md.bak-20260824
```

Four `.bak-*` files sitting beside their live counterparts. These are exactly the "state outside version control" pattern the Kepner-Tregoe analysis identified as the failure boundary — except here the state is *inside* version control and duplicated.

### Category 3 — Overlapping status registers with no single source of truth

This is the consistency problem, not just a tidiness problem. The following all claim some form of current-state authority:


| Document | Size | Claimed role |
| :-- | :-- | :-- |
| `PROJECT_CANON.md` | 54 KB | "Durable source of truth" |
| `DECISION_LOG.md` | 136 KB | D-001–D-121 rulings |
| `CHANGE-ORDER.md` | 54 KB | Change register |
| `COORDINATION.md` | 46 KB | "Append-only coordination history" |
| `MASTER-TODO-2026-08-18.md` | 17 KB | "Authoritative production resume ledger" |
| `URGENT-TODO.md` | 26 KB | Urgent items |
| `BUILD_PLAN.md` | 19 KB | "Forward entry point" |
| `DEBT.md` | 34 KB | Debt register |
| `INDEX.md` | 7 KB | Document map |
| `HANDOFFS.md` + 7 dated `HANDOFF-*.md` | ~215 KB | Per-lane handoffs |

`INDEX.md` alone carries **eight stacked amendment bylines** correcting earlier statements, and contains strikethrough-then-correction passages like "~~The worktree is clean.~~ **Corrected 2026-08-18... the worktree is currently DIRTY**". A document that requires eight corrections to remain accurate is not an index; it is a changelog pretending to be a map.

`MASTER-TODO-2026-08-18.md` is still labeled authoritative but is two weeks stale and predates the entire D-108–D-121 reckoning — and it ships with a companion, `OWNER-REVIEW-2026-08-18-verified-todo-audit.md`, whose stated job is to contradict it. Two documents where one disagrees with the other, both indexed as current, is the documentation equivalent of the six conversation models.

### Category 4 — Already-triaged but not yet executed

The `awaiting-verification-inventory-20260901.md` already did the hard work: **75 files triaged into 13 verified→archive, ~37 stale→quarantine, ~25 still-pending→keep**. The ruling exists; the moves have not happened. `docs/awaiting-verification/` still holds 75 files across 6 subdirectories. That same inventory also surfaced a tooling defect worth noting — 5 of 11 files in `summaries/` contain **zero content**.

Similarly, `docs/DOC_CLEANUP_MANIFEST-2026-08-15.md` and `docs/DOC_DEBT.md` are prior cleanup plans that were written and not executed. Writing a third cleanup plan without executing the first two would be Fixes That Fail, on schedule.

### Category 5 — Historical research that should be archived, not deleted

`docs/research/integration-audit-2026-08-24/` (9 MB), `docs/reviews/2026-08-23-cross-repo-evidence-audit/` (720 KB), `docs/reviews/2026-08-25-schema-audit/` (216 KB), `docs/planning/forensic-db-architecture/` (1.6 MB), and `docs/planning/forensic-db-reconciliation/` (1.4 MB). These have genuine historical value — the schema audit is where GAP-021 came from, and the CI workflow cites it by path. They should move under a dated archive with a one-page index rather than being deleted or left in the active tree.

## Recommended Consolidation

The target is a docs tree an agent can hold in context, with one document per question.

**Delete outright (~24 MB):** the vendored Semantica cookbook, `.plannotator/` history, `_TO_BE_DELETED/`, and the four `.bak-*` files. None of these are referenced by code, CI, or the canon.

**Collapse the status registers to four.** Keep `PROJECT_CANON.md` (what is true and locked), `DECISION_LOG.md` (why, D-numbered, append-only), `DEBT.md` (what is broken), and one forward document. Fold `MASTER-TODO`, `URGENT-TODO`, `BUILD_PLAN`, and the loose `HANDOFF-*.md` files into that single forward document, with the superseded originals moved to the dated archive. `CHANGE-ORDER.md` and `COORDINATION.md` are both append-only histories and should merge or be explicitly scoped so they cannot both claim the same events.

**Rewrite `INDEX.md` from scratch.** Do not amend it a ninth time. It should be under 100 lines, contain no strikethroughs, and every row should be verifiable in under a minute. A stale index is worse than no index because it directs agents to wrong sources with apparent authority.

**Execute the inventory that already exists.** The 75-file disposition is ruled; move the 13 to `docs/archive/` with the verification note attached, move the 37 stale to a dated quarantine, leave 25 in place. Delete the 5 empty `summaries/` files and file the generator defect.

**Add the two cheap enforcement gates.** A CI step that builds an empty database from the current baseline (closes the discovery-delay gap), and a grep gate that fails on new `content_hash` introductions (stops the naming lattice from regrowing). Both are minutes of work and both convert "Matt must verify this" into "a test verifies this" — which is the stated purpose of the whole exercise.

**Move `docs/reference/agno-memory-and-storage/` out.** 436 KB of upstream Agno library documentation for a dependency the canon describes as retired-in-progress. Link to upstream instead.

The net effect: `docs/` goes from ~46 MB and 700+ files to roughly 2–3 MB of genuinely project-specific material, with a dated archive holding the historical audits. That is the difference between documentation an agent reads and documentation an agent skips.

<span style="display:none">[^1_1][^1_10][^1_11][^1_2][^1_3][^1_4][^1_5][^1_6][^1_7][^1_8][^1_9]</span>

<div align="center">⁂</div>

[^1_1]: SCHEMA-SYSTEMS-ANALYSIS-2026-08-31.html

[^1_2]: SYSTEMS-ANALYSIS-2026-08-31.html

[^1_3]: TABLE-ACCOUNTING-2026-08-31.html

[^1_4]: TARGET-SCHEMA-BLUEPRINT.html

[^1_5]: uncommitted-2026-08-31-NEW-MIGRATIONS.sql

[^1_6]: UNCOMMITTED-WORK-2026-08-31.html

[^1_7]: VERIFICATION-2026-08-31-postmortem-audit.html

[^1_8]: Uncommitted-Work-Report.html

[^1_9]: 00-INDEX.md

[^1_10]: MCP-Platform-Repo-Review-Tweaks-and-Consolidation-Opportunities.md

[^1_11]: Platform-Post-Mortem-and-Recovery-Plan-1.md


---

# Comprehensive Gap Register, Agent Dispatch Plan, and Documentation Disposition Report

Below is the full report: every open gap with a fix order and agent assignment, then a file-by-file documentation disposition list. Evidence is drawn from the current repo state as of the 2026-09-01 commits.

## Part 1 — Where the repo actually stands

The 2026-09-01 session closed a meaningful slab of work. T-0 (owner directory moves committed as `82258c6`), H-02a (Go and Python identifier damage from the `registry`→`reference` sweep repaired, `9da8815` + `e8a00ed`), H-08a (migration 0062 registry split applied plus a follow-on 0065 drift repair, `cc53a0e`), H-00 residual, H-09 doc hygiene (`4cbdce4`), H-11 Surreal design doc (`6e6d1c8`), and the `tests/_reports/` consolidation are all done.

Two structural changes landed after that: the owner restructure into `modules/` with `deploy/docker/` (`45e49a3`), and `modules/forks/sbv` converted from a gitignored nested repo into a real git submodule of `Cursedpotential/sbv-forensic` (`92ca38b`, `b6bdfe7`). Root now shows `.gitmodules` present, `modules/`, `deploy/`, and no stray `engine/`, `workbench/`, `docker/`, `contracts/`, `_stale/`, or `to_be_deleted/` — the parking lots really are out of the tree.

Best practices that are now genuinely observed:

- CI has three jobs — Python validate, a new Go engine job (build/vet/test against `modules/engine`), and the mandatory GAP-021 live integration job with a no-all-skipped gate and a published 90-day receipt.
- The integration job fails, not skips, on missing secrets — deliberately, because a silently skipped live suite used to read as green.
- A real migration ledger exists (`ops.migration_ledger`) after `public.schema_version` destroyed migration state once (D-109).
- The schema builds from one baseline file in ~11s, and the baseline was regenerated from live twice after 0062/0065.
- The parked geo lane was backed up and restore-proven 10/10 before removal (D-121).
- `.gitattributes` and `.editorconfig` line-ending prevention are in place, and `pyproject` ruff/mypy/pytest excludes cover the nested repos.


## Part 2 — The gap register, in fix order

### Tier 0 — Blocking correctness and integrity (do first, mostly serial)

**G-01 · CI cannot pass: `SUBMODULE_TOKEN` missing.** The Go job checks out submodules with `${{ secrets.SUBMODULE_TOKEN || github.token }}`, and `github.token` cannot read the private `sbv-forensic` repo; `modules/engine/go.mod` replaces `github.com/lowcarbdev/sbv` with `../forks/sbv`, so the engine cannot build without those sources. Every push is currently red on the Go job.
*Fix:* owner adds a PAT with read access to `sbv-forensic` as repo secret `SUBMODULE_TOKEN`. Owner-only, five minutes, unblocks everything else.

**G-02 · GAP-021 integration secrets not provisioned.** Seven secrets are required (`TS_OAUTH_CLIENT_ID`, `TS_OAUTH_CLIENT_SECRET`, `INTEGRATION_DB_USER/PASS`, `INTEGRATION_SBV_BASE_URL/SERVICE_USER/SERVICE_PASS`); until they exist the job fails by design.
*Fix:* owner action, same sitting as G-01.

**G-03 · 27 pre-existing pytest failures.** Deploy/cutover contract drift from the AgentOS retirement rework: ingest_port ×14, opencode_ops ×6, deploy contracts, db_url, surreal_phase1, uiw webhooks, and a format_engine_override teardown flake.
*Fix:* one dedicated triage lane; classify each as stale-expectation vs real regression before H-02 gates on the suite.

**G-04 · `sql/0045` merge-conflict casualty.** Only `.broken-historical` and `.incoming-conflict` variants ever existed and have now been moved out with `to_be_deleted/`; the ledger has no 0045 row; `tests/test_0048_*.py` module-skips with that reason. The numbering chain has a hole between 0043 and 0047.
*Fix:* owner ruling — restore a canonical 0045 or formally renumber the supersession chain, then un-skip the test.

**G-05 · `working.enqueue_evidence_vector_projection` targets a dropped table.** It still writes to `normalized_record_chunk`, which no longer exists; explicitly deferred to H-04.
*Fix:* fold into the vector-cutover work; it is a latent `UndefinedTable` on the same class as the 0065 bug already found and fixed.

**G-06 · `agno_app` role cutover still not switched.** A non-superuser role was created live with scoped grants across eight schemas and verified non-superuser, but the app still connects as superuser `ai` (`rolsuper=True`, `rolbypassrls=True`, owns all 253 objects), so `sql/0029`'s grants are inert and the append-only guards in `0017` are bypassable.
*Fix:* owner sets `DB_USER`/`DB_PASS` to `agno_app` in Coolify and **redeploys** — env values bake into the rendered compose, so a bare restart will not pick it up. This is the single cheapest integrity win in the register.

### Tier 1 — Structural duplication and custody unification

**G-07 · Two-runtime parser/chunker/hash duplication (H-01).** Parsing, chunking, hashing, and ingest orchestration all exist in both Go and Python — 30 Python parsers versus the Go adapters, a 705-line Python chunker set versus `modules/engine/chunk`, and `server/ingest/service.py`'s own `PostgresReceiptJournal` paralleling but not sharing the Temporal stagegraph receipts. Two ingest paths means two custody stories and two chunk-ID vocabularies.[^2_1]
*Fix (do not rewrite either side):* declare the Go UIW the only custody-authoritative writer; demote Python parsers to format extractors invoked through `select_parser_activity`/`execute_parser_activity` (the N8N-backed seam already exists); register Python chunkers as `chunk.Adapter` capabilities so `ChunkerID`/`ChunkerVersion` receipts stay uniform.[^2_1]

**G-08 · Python-parsed formats produce no H2/H3.** Only SBV does; under D-069 this moves to promotion, which fixes it structurally.

**G-09 · Two H2 canons and two H3 chains.** `h2-canonical-v2` in `public.canon_registry` versus `h2-rawelement-v1` in `custody.py`; and two H3 constructions (SBV Go genesis-empty vs Case Bible genesis-H1) that both remain correct but share the non-disambiguating tag `h3-chain-v1`.
*Fix:* distinct tags plus a crosswalk, before any further chain writes.

**G-10 · Python SMS-XML parser still memory-bound.** `_collect()` streams the XML correctly but appends every record to a list, and the malformed-XML fallback does `ET.fromstring(read_text())` — whole file as string plus full DOM. The streaming generator `iter_records()` already exists and `parse()` simply does not use it.
*Fix:* drive `iter_records()`, spill to NDJSON, return path + counts; note this changes the atomic tool's output contract, and ADR-0049 requires it stay callable both in-workflow and atomically.

**G-11 · ADR-0044 §4 blob ban unenforced in code.** `transcripts.markdown` registers plain `capability="parse.transcript"`, so the whole-file speaker-blending fallback is resolvable by an evidence-lane workflow that runs custody and store steps — while the ADR says it is "BANNED for evidence".
*Fix:* either capability split (`parse.context_transcript`) or a store-boundary guard rejecting `parser_id == "transcripts.markdown"`, plus a test that fails if it is reachable from an evidence-lane workflow.

**G-12 · No `evidence.raw_rejected` writer.** The table and indexes have existed since `sql/0012` and two modules reference it by name, but zero code paths INSERT into it.

### Tier 2 — Held activations (implemented, not live)

Every row in the Horizon Swift MVP audit table follows the same pattern: contract-tested locally, activation held. Recommended order, cheapest-integrity-first:


| \# | Held item | What is actually blocked | Suggested lane |
| :-- | :-- | :-- | :-- |
| 1 | `agno_app` role cutover | Config-only; removes a live integrity gap | Owner |
| 2 | Native evidence vectors (D-066) | Collection creation, PG-chunk backfill, count/hash/canary receipt, `EvidenceChunks` alias switch, reader rebinding, deploy — each needs its release gate | Build lane (H-04) |
| 3 | Semantica activation | PG adapter contract-tested; no DB write, worker deploy, credentials, projection, or live corpus run | Build lane (H-06) |
| 4 | ContextForge/Portkey MCP consolidation | Separate PG database/role on ovh-files, SQLite registry migration, hosted/enterprise Portkey control plane (OSS gateway is insufficient proof), correlated audit traces | Infra lane, largest |
| 5 | AgentOS production-host slice | Deploy and live-prove exec, Workbench, branch-scoped LibreChat; then replace `server/evidence/workflows.py` and Agno Knowledge/provider/vector/session ownership | Owner-gated |
| 6 | Workbench Vercel AI SDK stream | Owner approval plus `PORTKEY_CONFIG`/credentials before advancing `workbench/sprint` | Owner-gated |
| 7 | R12 Surreal disposable slice | D1/D2 complete; D3 target/credential and D4 schema/adapter authority both required and not granted | Blocked, do not touch |

Each held item is a bet that currently pays nothing; converting three of them is worth more than any new subsystem.[^2_1]

### Tier 3 — Unbuilt design layers

**G-13 · Horizon predicate is inert live.** `working.horizon_visible` still filters on `row_knowledge_time <= p_horizon`, which is the superseded predicate; ADR-0059 requires a source-class predicate (first-party availability = occurrence, acquired-third-party = acquisition, realization stays plural).

**G-14 · ADR-0045 §B / ADR-0059 derivation contracts unbuilt live.** No active plural-realization derivation, no dedicated acquired-third-party projection, no durable healthy checkpoint/resume path, no terminal seal/linked-rewalk path.

**G-15 · ADR-0053 schema built but empty.** `chat_conversation`/`chat_message`/`chat_chunk` plus lane/embedding/projection exist at 0 rows, while `working.context_record` holds 1,741 rows of legacy chat-lane data still to migrate.

**G-16 · Promotion → evidence writer does not exist.** Reviewers ruled nothing else in the schema sequence moves until it does; `evidence.raw_*` currently lands pre-promotion inside the evidence schema, which is a D-069 violation ruled to move to context. Custody backfill through the promotion path is the one irreversible step and must precede retiring the ingest-time write.

**G-17 · Eval lane has no citation-grounding or retrieval-quality cases.** `evals/cases.py` is 145 lines with 8 populated cases — the old "CASES=()" claim was already stale when written and was inherited verbatim by two independent gap analyses on 2026-08-23, neither of which opened the file. The real narrower gap is that none of the 8 exercise grounding or retrieval quality.

**G-18 · No recurring backup lane.** `scripts/backup_ovhdata_hot.sh` is a one-time host-retirement snapshot covering Postgres/SurrealDB/Weaviate and explicitly skipping Neo4j/Milvus — not the recurring pg_dump + neo4j dump → R2 lane this row tracks.

**G-19 · CDC worker, classifier quality, OCR/VLM selection, multimodal embedding, timeline extraction, horizon walks** — all six ADR-0053 follow-ups remain at "manual drains / deterministic keyword baseline / not benchmarked / schema-only".

**G-20 · Custody-event digest writer unversioned.** The trigger hashes a session-timezone-rendered timestamp with no construction/timezone version; the readiness endpoint compensates by testing 105 offset candidates per event, which is acceptable for an operator read but must not become a high-volume primitive.

**G-21 · Baseline bootstrap still drifts on current image.** The dump creates `pg_duckdb` before `pg_stat_statements` and PostGIS, causing extension-script GRANTs to be rejected as MotherDuck-table operations; and the captured file lacks `ops.audit_ledger` despite `sql/README.md` claiming otherwise. Needs deterministic extension ordering, an explicit included-migration manifest, and an empty-database regression test.

**G-22 · pg_duckdb barely used** relative to the custom image maintained for it.[^2_1]

**G-23 · No status single-source (H-08).** `DEBT.md` had to correct its own stale banner because status truth lived in both the register and the SQL file headers and drifted.[^2_1]
*Fix:* one machine-readable source (`docs/STATUS.yaml` or an `ops` table), with DEBT rows and SQL banners generated from it, plus a CI check that fails when any `AGENTS.md`/`AGENT_MEMORY.md` contradicts it on a tracked key.[^2_1]

**G-24 · Documentation mass exceeds code mass.** 131,489 Markdown lines against 102,707 first-party Python and 32,403 engine Go; `docs/` at 46 MB and 842 files, `docs/wiki` alone 580 files and 25 MB. See Part 4.[^2_1]

**G-25 · Evidence bundling / exhibit assembly has never been scoped.** No ADR, no roadmap phase, no debt row. The only committed artifact is `analysis.vw_court_export`, a read-only readiness view producing no document; the larger `court_export_draft`/`human_review_packet` vision exists only in an explicitly-disclaimed 729KB draft that canon and ADRs 0057/0058/0059 never adopted.
*Fix:* an owner decision on whether this becomes an ADR now or is formally deferred — right now it is neither built nor deferred, which is the worst of both.

## Part 3 — Agent split, parallelization, and lane budget

The lane structure from the dispatch plan still holds: three concurrent lanes, Sonnet subagents for mid-tier build/ops plus verification, GPT-5.6 Luna (free, high effort) for docs and hygiene, GLM-5.2 via Ollama Cloud/OpenCode as build-tier overflow and open-weight fallback. Kimi K3 is barred from H-01 and H-05. Frontier judgment calls stay in the main loop with execution delegated down.

### Wave 0 — Owner-only, unblocks everything (serial, ~30 min)

| Task | Gap | Who |
| :-- | :-- | :-- |
| Add `SUBMODULE_TOKEN` repo secret | G-01 | Owner |
| Add the seven GAP-021 integration secrets | G-02 | Owner |
| Rule on `sql/0045`: restore or renumber | G-04 | Owner |
| Rule on the 75 `awaiting-verification` dispositions | Part 4 | Owner |
| Rule on evidence-bundling scope: ADR now or formal deferral | G-25 | Owner |
| `agno_app` cutover in Coolify + redeploy | G-06 | Owner |

Nothing else should start until G-01 lands, because a red Go job masks every subsequent build signal.

### Wave 1 — Fully parallel, three lanes, no shared files

| Lane | Task | Gaps | Model tier |
| :-- | :-- | :-- | :-- |
| A | H-08 status single-source: build `docs/STATUS.yaml`, generate DEBT rows and SQL banners from it, add the contradiction CI check | G-23 | Sonnet |
| B | Documentation consolidation pass 1 (deletions and archive moves from Part 4 — mechanical, no judgment) | G-24 | Luna free |
| C | Triage the 27 pre-existing pytest failures into stale-expectation vs real-regression buckets | G-03 | GLM-5.2 |

These three touch disjoint file sets — YAML/register, `docs/`, and `tests/` — so they parallelize cleanly.

### Wave 2 — Parallel, three lanes

| Lane | Task | Gaps | Model tier |
| :-- | :-- | :-- | :-- |
| A | H-02 CI harness expansion + `modules/contracts/` created with the first real schema files (owner already ruled the location) | — | Sonnet/GLM |
| B | H-06 Semantica activation: DB write, worker deploy, credentials, projection, live corpus run | Tier 2 \#3 | Sonnet |
| C | H-10 residual: vendored excludes, `.gitattributes` sweep, doc-prose repair from the rename damage | — | Luna free |

### Wave 3 — Parallel pair, higher risk

| Lane | Task | Gaps | Model tier |
| :-- | :-- | :-- | :-- |
| A | H-01 custody unification across the 30 Python parsers — declare Go authoritative, demote Python to extractors behind the activity seam | G-07, G-08, G-10, G-11, G-12 | Opus if available, else GLM-5.2 with mandatory Sonnet review; **K3 barred** |
| B | H-04 native evidence-vector cutover — includes fixing `enqueue_evidence_vector_projection` | Tier 2 \#2, G-05 | Sonnet |

Split H-01 further if you want more parallelism: the capability-split guard (G-11), the rejection writer (G-12), and the SMS-XML streaming rewrite (G-10) are each independently testable and can go to three separate cheap subagents, with the custody-authority declaration itself held in the main loop.

### Wave 4 — Parallel pair

| Lane | Task | Gaps | Model tier |
| :-- | :-- | :-- | :-- |
| A | H-05 retrieval seam + horizon predicate replacement per ADR-0059 source classes | G-13, G-14 | Opus else GLM + review; **K3 barred** |
| B | H-07 pg_duckdb rationalization + baseline extension-ordering fix with an empty-DB regression test | G-21, G-22 | Sonnet |

### Wave 5 — Serial, irreversible

The promotion → evidence writer (G-16) must be built live-but-unwired first; then `evidence.raw_*` moves to context; then custody backfill for already-ingested rows through the promotion path — **this is the one irreversible step, and it must happen before retiring the ingest-time write, never after**. Only then do the message-layer changes and, last of all, the `normalized_record` trim, one column family per migration. Keep this entirely in the main loop with Sonnet executing individual migrations.

### Wave 6 — Deferrable, parallel

Backup lane (G-18), eval grounding cases (G-17), custody digest versioning (G-20), hash-tag disambiguation (G-09), ADR-0053 follow-ups (G-19), ADR-0053 data migration of the 1,741 context rows (G-15). All independent; assign to whatever cheap capacity is free.

### Completion gate

Unchanged and non-negotiable: a handoff is accepted back only when its own "Done when" block is verified by a **separate** Sonnet check — builds and tests actually run, live `information_schema` actually probed, no dropped-table or `content_hash` references remaining. No self-reported completion counts.

## Part 4 — Documentation disposition, file by file

Governing principle already in AGENTS.md: current truth is indexed by `docs/INDEX.md`, and completed or superseded documents move under `docs/archive/` **in the same change**; ADRs and the append-only `DECISION_LOG.md` stay in place. That rule is currently not being followed — `docs/archive/` contains nothing but a README.

### 4a. Delete now — zero judgment required

| File | Why |
| :-- | :-- |
| `docs/URGENT-TODO.md.bak-20260824b` | Manual pre-edit snapshot; git already has it |
| `docs/URGENT-TODO.md.bak-20260824c` | Same |
| `docs/URGENT-TODO.md.bak-20260824d` | Same |
| `docs/n8n-model-and-node-notes.md.bak-20260824` | Same |
| `docs/wiki/_TO_BE_DELETED/repair-2026-03-31/` | A to-be-deleted folder inside the canonical docs tree |
| `docs/wiki.xxh3` (99 KB) | A hash manifest of a wiki tree that is itself being restructured |

The `.bak-*` convention is a heavy-handed manual versioning layer on top of git and should be retired outright, not just cleaned this once.

### 4b. Archive — verified or explicitly historical, move to `docs/archive/`

The awaiting-verification inventory already did the corroboration work: 13 files are verified→archive, cross-checked against D-001–D-121 and the ADR index, with a document's own PASS/DONE claim never trusted. Move these thirteen: the two Surreal phase-0 evaluations, the four S-series handoffs (SBV/chatminer parser gap review, S1 docs-registers true-up, S10 compose consolidation, S4 ADR package), the five Surreal plans (contracts, goals, pending-owner-decisions, D2 physical proposal, blueprint), and the two compact summaries from 08-12 and 08-14.

Also archive:


| Path | Why |
| :-- | :-- |
| `docs/DOC_CLEANUP_MANIFEST-2026-08-15.md` | Its own status is "QUARANTINE STILL PROPOSED — no files moved"; superseded by the 2026-09-01 inventory |
| `docs/ADR_RECONCILIATION.md` | June proposal sweep ending at ADR-0022; already bannered historical, and there are now 62 ADRs |
| `docs/blueprint/` (4 files) | Older duplicate blueprint carrying a supersession banner; `.agents/blueprint/` is the generated output |
| `docs/RULINGS-SHEET-2026-08-09.md` | 1.3 KB sheet whose rulings are in DECISION_LOG |
| `docs/Codex Goal — Horizon Swift MVP.md` | Space in filename, superseded goal document |
| `docs/reviews/2026-08-23-cross-repo-evidence-audit/` (29 files, ~450 KB) | Findings folded into DEBT/DECISION_LOG; keep `ISSUES-AND-TODO.md` live until its ISS-/TODO- numbers are drained |
| `docs/reviews/2026-08-25-schema-audit/GAP-019-live-receipt-2026-08-26.json` (41 KB) | Receipt artifact, not documentation |
| `docs/recovered/GRAPHRAG-RECOVERED-FROM-BYTECODE.txt` | Recovery succeeded and landed in 0055; the artifact is history now |
| `docs/plans/WAVE1-*.md` (6 files, ~98 KB) | Wave-1 premises falsified per DEBT CH-15/16; archive with correction banners |
| `docs/plans/R10-*`, `R11-*`, `R12-*` pre-mortems (7 files) | R12 execution denied; D1/D2 only |
| `docs/plans/WEAVIATE-NATIVE-EVIDENCE-CUTOVER-RUNBOOK-2026-08-18.md` | Keep **live** until H-04 executes, then archive same-change |

### 4c. Quarantine — stale, superseded, owner-ruled

Roughly 37 files in `docs/awaiting-verification/` are falsified or superseded by the 08-23→08-31 reversals: AgentOS retired (D-101/D-107), Graphiti retired (D-070/D-095), evidence-at-ingest reversed to context-first (D-069), Next.js Workbench retired (D-108), and the schema reckoning (D-108–D-121, 58 tables deleted). Any document assuming AG2/OrchestrationPort, AgentOS Knowledge bases, Graphiti belief graphs, the R0–R8/S1–S9 wave structure, or `visible_from = COALESCE(realized_at, occurred_at)` is stale by definition.

Six of these are pure junk from a tooling defect: `COMPACT-SUMMARY-2026-08-13`, `-15`, `-16`, `-17`, `-18` contain **zero content** — just repeated "Summary field not found in hook payload" JSON from a broken PostCompact hook on Codex gpt-5.6-sol sessions. About 45% of that quarantine lane was exhaust from one hook bug. Delete these outright; there is nothing to preserve. And fix the hook, or it will keep producing them.

### 4d. Keep but consolidate — the real efficiency wins

**Merge the two schema directories.** `docs/schema/` and `docs/schemas/` both exist. The former holds three generated artifacts totalling ~1.9 MB — `ai-schema-reckoning.html` (1.03 MB), `catalog.json` (759 KB), `three-message-shapes.html` (144 KB). The latter holds live contracts: the intake OpenAPI, `document-markdown-v1.json`, the Case Bible compatibility map. Keep `docs/schemas/` for contracts, move the generated HTML/JSON out of `docs/` entirely (they are build output), and delete the singular directory. Note also that `modules/contracts/` is the owner-ruled future home for cross-language schemas — machine-consumed artifacts must not live in `docs/`, precisely because they drift as docs.

**Collapse the TODO/register sprawl.** There are currently at least seven overlapping status surfaces: `DEBT.md` (33 KB), `DOC_DEBT.md`, `URGENT-TODO.md` (25 KB), `MASTER-TODO-2026-08-18.md` (17 KB), `OWNER-REVIEW-2026-08-18-verified-todo-audit.md` (17 KB), `CHANGE-ORDER.md` (54 KB), and `COORDINATION.md` (45 KB). `URGENT-TODO.md` is a **pure infra punch list** — all 13 open items are Docker/Tailscale/Traefik/OVH topology, and none relate to ingest, evidence, retrieval, or bundling. Rename it `INFRA-PUNCHLIST.md` so nobody reads it looking for product debt. Then fold `MASTER-TODO` and `OWNER-REVIEW` into the H-08 single status source and archive both.

**Retire `DOC_DEBT.md` as designed.** Its own reconciliation note admits the `# DOC:` marker convention it was built around was never adopted and the grep returns zero hits, so the register is source-of-truth on its own and must be hand-maintained. A hand-maintained register that contradicts its own stated mechanism is the exact drift pattern H-08 exists to kill — fold its six open items into the single status source and delete the file.

**Split the two giant handoffs.** `HANDOFF-2026-08-29-derived-document-ingest-wiring.md` is **127 KB** in a single file covering WP-1..WP-11. `docs/planning/Claude - chat pipeline for PostgreSQL - Claude.md` is **137 KB** of raw chat transcript with a space-laden filename. The first should be split per work-package; the second should be mined for unique facts and then archived — raw dictation and transcript dumps in the canonical docs tree is exactly the pattern H-09 removed `FUCKED.MD` for.

**Retire `docs/wiki/INDEX.md` and most of `docs/wiki/`.** The wiki index documents an entirely different system — "dial-stack," AI DIAL Core, DuckDB-as-master-analytics, LanceDB, Keycloak, WunderGraph Cosmo, DIAL Chat, CopilotKit — and is stamped "Last updated: 2026-03-12". None of that is the current stack, which is PostgreSQL 18 canonical, Weaviate projection, Neo4j Semantica graph, SurrealDB analytical, Temporal + n8n, Portkey. This is 580 files and 25 MB of documentation for a superseded architecture. Archive the tree wholesale; salvage only the parser pages under `skills/utility/parsers/` if they still describe live parsers, and reconcile them against the authoritative `docs/reference/parsers.md` (48 KB, verified 1:1 against the live registry at 23 tools with no gaps). The nested `docs/wiki/archive/` — which contains `.annotative`, `.audit`, `.full-review`, `.planning`, `.redline`, plus `memory/`, `plans/`, `project-docs/`, `project-root/`, `user-root/`, and a second `wiki/` — is an archive inside an archive and should be flattened or dropped entirely.[^2_1]

**Reconcile `docs/planning/` (34 entries, ~3.9 MB).** It mixes live specs with a SQLite binary (`forensic_staging_test.sqlite`, 274 KB), raw HTML reports, and a 45 KB facade-collapse plan. The `forensic-db-architecture/` tree is the source of the only exhibit/bundle design in the repo — explicitly disclaimed as unratified draft, dated 2026-06-30, never promoted to an ADR. Extract the unique court-safety rationale, then quarantine per the existing manifest recommendation. Move `forensic-staging-schema.sql` to `sql/drafts/` where SQL belongs, and delete the SQLite binary.

**Fix the broken index links.** `docs/INDEX.md` points to `awaiting-verification/handoffs/` for the R0–R14 packets — most of which the 2026-09-01 inventory ruled stale. It also still describes the worktree as DIRTY as of 2026-08-18 and carries seven stacked amendment bylines before any content appears. Rewrite it against the post-restructure tree in one pass rather than appending an eighth byline.

**Cap the byline chains.** README, `AGENTS.md`, `DEBT.md`, and `INDEX.md` all open with multi-model dated amendment stacks — Sonnet 5, Kimi K3, GPT-5, Opus 5, glm-5.2, Fable 5 — that push actual content below the fold and structurally encourage agents to append rather than revise. Keep the most recent entry plus a link to history.[^2_1]

**Reconcile agent-context duplication.** 26 `AGENT_MEMORY.md` files and 13 `AGENTS.md` files exist; distributed context is a reasonable pattern, but at that count the probability two disagree is high and nothing enforces reconciliation. The H-08 CI check should cover this.[^2_1]

### 4e. Correct in place — factual drift found this pass

| Doc | Drift |
| :-- | :-- |
| `README.md` | Says "The current backend runs through an Agno 2.8.7 / AgentOS adapter" and calls AG2 a bounded coordination candidate — but AgentOS is retired (D-101/D-107) and D-101 ruled provider-switching "not needed" |
| `README.md` | Says "Go work under `vendored/sbv` requires the `fts5` build tag" — that path no longer exists; it is `modules/forks/sbv`, a submodule whose own CI is authoritative |
| `README.md` | Lists Neo4j + Graphiti as current infrastructure; Graphiti is retired (D-070) |
| `README.md` | "Root `compose.yaml` is mirrored to the VPS" — compose files now live under `deploy/` |
| `AGENTS.md` | Commands table still shows "Go build/test (`modules/forks/sbv`)" while the ⚠ note below it says `vendored/sbv` and points at `vendored/sbv/Makefile` |
| `AGENTS.md` | "Its export remains at `../_stale/surreal-export-20260804`" — `_stale/` was relocated during the 2026-09-01 reorganization |
| `AGENTS.md` | Project line still reads "platform on Agno AgentOS" |
| `docs/DEBT.md` | Known-debt table still says evals are "still `CASES: tuple[Case, ...] = ()`" in one row while a correction elsewhere in the same file documents 8 populated cases |
| `docs/DEBT.md` | `agno==2.8.7` vs `2.8.0` cited in AGENTS.md, CONVENTIONS.md, and canon §8 — flagged for follow-up sync and never chased |
| `docs/INDEX.md` | Worktree-DIRTY claim and stale packet links, above |
| `sql/README.md` | Claimed the baseline contains `ops.audit_ledger`; it does not |
| ADR-0044 §evidence/context boundary and `sql/0009` header | Both need a dated strike-through pointing at D-069 |
| ADR-0050 | Marked "superseded in part by ADR-0053"; confirm `scripts/ingest_knowledge.py` still targets the right `knowledge/` structure |

### 4f. Move out of `docs/` entirely

Generated and binary artifacts do not belong in a documentation tree: `docs/schema/*.html` and `catalog.json` (~1.9 MB), `docs/planning/forensic_staging_test.sqlite`, `docs/planning/gui-build-plan.html` and `restructure-report.html`, `docs/reviews/2026-08-29-production-workbench-intake-final.png` (102 KB), and `docs/reviews/.../GAP-019-live-receipt-2026-08-26.json`. Also resolve the two symlinks `docs/semantica` and `docs/semantica-benchmarks`, which point outside the tree and will break for any agent or CI runner working from a fresh clone.

### Expected reduction

Deleting 4a, archiving 4b, quarantining 4c, and archiving the superseded `docs/wiki/` tree removes on the order of 700+ files and roughly 30 MB from the active documentation surface — the bulk of it the 580-file, 25 MB dial-stack wiki that documents a system this repo no longer is. That takes documentation mass back below code mass, which is the actual test of whether the consolidation worked.[^2_1]

<span style="display:none">[^2_10][^2_11][^2_2][^2_3][^2_4][^2_5][^2_6][^2_7][^2_8][^2_9]</span>

<div align="center">⁂</div>

[^2_1]: MCP-Platform-Repo-Review-Tweaks-and-Consolidation-Opportunities.md

[^2_2]: SCHEMA-SYSTEMS-ANALYSIS-2026-08-31.html

[^2_3]: SYSTEMS-ANALYSIS-2026-08-31.html

[^2_4]: TABLE-ACCOUNTING-2026-08-31.html

[^2_5]: uncommitted-2026-08-31-NEW-MIGRATIONS.sql

[^2_6]: TARGET-SCHEMA-BLUEPRINT.html

[^2_7]: VERIFICATION-2026-08-31-postmortem-audit.html

[^2_8]: UNCOMMITTED-WORK-2026-08-31.html

[^2_9]: 00-INDEX.md

[^2_10]: Platform-Post-Mortem-and-Recovery-Plan-1.md

[^2_11]: Uncommitted-Work-Report.html


---

# Verdict on Your Three Assertions

Two of your three assertions are already satisfied in the current code; one is only *partially* satisfied and the remaining leak is real, concrete, and in the SBV adapter layer — not in the parser contract itself.

## Assertion 1: Parsers Must Have Nothing To Do With Hashing

**Status: satisfied at the contract layer, violated at the adapter layer.**

- The `parser` package doc comment is explicit and correct: "It deliberately has no Temporal, database, hash, normalization, or custody dependency: adapters stream raw source-native records to a caller-owned BundleWriter and return only compact results".
- `RawRecordEnvelope` is documented as having "no hash, database, normalized, custody, workflow, or generated-id field," and the struct definition confirms this — `RecordOrdinal`, `RecordStatus`, `StatusReason`, `Locator`, `StoredBytes`, `FormatID`, `NativeFields`, `NativeMetadata`, `Attachments` and nothing else.
- `Registry.Select` and `SelectCapability` are documented as never receiving source byte length or hash data, and the selection path confirms it — only declared format coverage plus quality tier plus a lexical tie-break on parser ID/version/language.
- `ParserActivities.SelectParser` carries the same guarantee in its own doc comment: "Registry accepts no input size, source bytes, or hash data, so selection is strictly capability coverage and quality as required by the v1 contract".
- **But** `ObjectRef` in the parser contract does carry a `ContentHash` field, validated as "64 lowercase SHA-256 hexadecimal characters". That is a hash *value* traveling through the parse-only boundary. It is defensible as a passive immutable coordinate (the contract says ObjectRef/Locator "do not open bytes, calculate hashes, or assert custody"), but it is the seam through which the actual violation below flows.
- **The real violation:** `modules/engine/adapters/sbv/artifact_sink.go` imports `crypto/sha256` and `encoding/hex` and contains a `digestFile` function that streams a SHA-256 over artifact bytes, plus a `sha256Text` helper and a `verifyExact` function that compares computed digests. The `Store` method calls `digestFile`, compares the result to `artifact.ByteCount`, and then passes `DigestSHA256: digest` into `registrar.RegisterArtifact`, and finally rejects the registrar's response if `locator.ContentHash != digest`.
- The file's own header comment claims it "does not create its configured root, calculate custody H1/H2/H3, or persist canonical platform records". That is a narrow, lawyerly truth — it is not computing the *custody* hashes — but it is unambiguously computing SHA-256 digests inside the parse path, which is exactly what you said should be done atomically via Temporal and nowhere else.
- The digest is additionally load-bearing for storage decisions: `publish` uses `verifyExact` to decide whether an existing logical identity "already contains different bytes," and `Store` quarantines content-deduplicated objects based on digest-driven locator comparison. So hashing here is not incidental logging — it is a control-flow authority inside the parser adapter.
- The adapter body `sbv.go` is clean by contrast: its package doc says "It owns no persistence, hashing, normalization, or custody," and the file contains no crypto import. It only *propagates* hashes it receives — copying `record.RawLocator.ContentHash` and `attachment.Locator.ContentHash` into parser locators, and marshaling `attachment.DigestSHA256` into attachment native metadata.
- **Net:** the propagation in `sbv.go` is arguably acceptable (it is carrying an upstream coordinate). The *computation* in `artifact_sink.go` is the actual breach and should be lifted into a Temporal activity that owns the digest and hands back a locator, with the sink reduced to a byte-mover that accepts a pre-established digest.


## Assertion 2: Hashing Is Done Atomically Through Temporal In The Workflow

**Status: satisfied, and cleanly versioned.**

- All hashing lives in `modules/engine/activities/hashing.go` (22,222 bytes) with its own test file, entirely separate from `parser_runtime.go`.
- `NewHashActivities` binds production Temporal heartbeats via `activity.RecordHeartbeat` and the attempt number via `activity.GetInfo(ctx).Attempt`, with storage as an injected `HashRepository`.
- `RegisterHashActivities` registers each atomic body under its exact `StageID`, and the comment states the rationale correctly: "Registering methods individually avoids Go method names silently becoming a second naming scheme".
- The vocabulary correction you previously demanded has landed. Context-integrity work now registers as `FingerprintSource`, `FingerprintRawRecords`, and `FingerprintRawGeneration`, while custody hashes are explicitly deferred: "Custody hashes (R04) are registered separately when R04 is implemented".
- Replay safety is handled properly rather than by breaking history. Three legacy aliases — `hash_source_activity`, `hash_raw_records_activity`, `hash_raw_generation_activity` — remain registered with an explicit warning: "Do not use these names for new schedules".
- Genuinely normalized hashes retain the `Hash` verb where that is semantically correct: `HashNormalizedRecords` and `HashNormalizedGeneration`.
- The worker treats `Hash` as its own bounded registration group alongside `Lifecycle`, three separate observation groups, `N8N`, `Raw`, `Normalized`, `Repair`, and `Preview`. Filesystem and embedded observation are deliberately separate values "so extractor provenance cannot cross activity boundaries".


## Assertion 3: Python Parsers Under Go Engine Orchestration, Exportable

**Status: architecturally provisioned, but zero Python parsers exist and the export path is HTTP-only.**

- The language-neutrality contract is in place. `Language` is a first-class validated type with `LanguageGo`, `LanguagePython`, `LanguageJavaScript`, `LanguageTypeScript`, and `LanguageOther`, and the doc note says "A non-Go implementation can be represented by a process/RPC adapter behind the same Adapter interface".
- The `Adapter` interface itself is explicitly designed for this: "Adapter is intentionally language-neutral. A Go parser, an RPC proxy for a Python parser, or a future external-language bridge all receive the same cancellable input and stream through the same sink".
- `Language` participates in deterministic selection as the final tie-break after quality, parser ID, and parser version, so a Python adapter registered alongside a Go one would sort predictably rather than nondeterministically.
- The Go engine unambiguously owns orchestration. `Registry.Execute` "owns streaming bundle lifecycle around one adapter invocation. Adapters can emit records but cannot finalize/commit the bundle". `BundleSink` "intentionally has no finalize method, so an adapter cannot commit an incomplete bundle or mint its result registry. Registry owns finalization after it validates accounting".
- The `validatingSink` enforces contiguous record ordinals, per-record format/status validation, non-zero record count, and exact accounting equality between what the adapter claims and what the sink observed — any mismatch aborts the caller-owned writer. A Python adapter therefore cannot lie about its own output.
- **The export surface exists but is HTTP, not a Go-callable library boundary.** `cmd/parser-activity-runtime` exists specifically to "expose the platform's atomic parser Activities to n8n Activity bodies while keeping source bytes and raw records out of HTTP responses and Temporal history". It builds the registry from SBV adapters, wraps `ParserActivities`, and serves via `runtimeapi.NewParserActivityHandler` behind a bearer token, with a 31-minute write timeout and a startup schema probe requiring all five `context.*` relations.
- **The gap:** `modules/engine/adapters` contains exactly one subdirectory — `sbv` — and `sbv.go` declares `Language: parser.LanguageGo` for every adapter it produces. There is no process adapter, no gRPC adapter, no subprocess bridge, and no Python parser directory anywhere in `modules/engine`. The `LanguagePython` enum value is currently dead code.
- `ExecuteSelected` gives you the correct foundation for exportable-but-pinned execution: it looks up the exact parser ID/version from a persisted receipt, refuses to reselect after registry drift, and rejects a persisted parser that does not declare the requested format. `ExecuteParser` reinforces this — "a missing, stale, or wrong selection is a hard error rather than an opportunity to choose a newer parser". This matters enormously for a Python adapter, whose version churn would otherwise silently change results across retries.


## What Actually Needs To Change

| Item | Current state | Required action |
| :-- | :-- | :-- |
| SHA-256 in `artifact_sink.go` | `digestFile`, `sha256Text`, `verifyExact` compute digests inside the parse path | Lift digest computation into a Temporal activity; pass the digest *into* the sink |
| Digest as storage control flow | `publish`/`Store` branch on digest comparison and quarantine on locator mismatch | Move the identity-conflict decision to the activity that owns the hash |
| `ObjectRef.ContentHash` | Validated 64-hex field on the parse-only contract | Acceptable as a passive coordinate, but document it as *never adapter-computed* |
| `LanguagePython` | Declared and validated, but unused — only SBV/Go adapters exist | Build the process/RPC `Adapter` bridge the contract already anticipates |
| Export surface | HTTP-only via `parser-activity-runtime` for n8n | Confirm whether "exportable" means this HTTP boundary or a Go module boundary |
| Legacy hash aliases | Three replay aliases registered with do-not-reuse warning | Keep until all pre-correction workflows drain, then delete with the const block |

## The Honest Summary

Your instinct that parsers were touching hashing was correct, but the location is narrower than your framing suggested. The parser *contract* is genuinely clean and its doc comments accurately describe its own constraints. The `sbv.go` adapter body is genuinely clean. The single real offender is `artifact_sink.go`, where SHA-256 computation is not merely present but is the deciding authority for whether bytes get published, deduplicated, or quarantined. Fixing that one file closes the assertion completely.

The Python-under-Go orchestration claim is the opposite situation: the abstractions are correct and complete, but nothing has been built on top of them. `LanguagePython` is a promise, not an implementation.

---
