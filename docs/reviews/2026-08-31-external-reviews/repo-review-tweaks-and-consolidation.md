# MCP Platform Repository Review — Where to Tweak

## Overview

The repository `Cursedpotential/mcp-platform-agno-mvp` is a pro se family-law evidence, analysis, and legal-strategy platform built around a Postgres-authoritative evidence pipeline with Weaviate, Neo4j/Graphiti, Temporal, Portkey, Cloudflare R2, and a custom Next.js/FastAPI Workbench . The working tree contains 4,027 tracked files across 166 MB, with 1,442 Python files, 1,090 Markdown files, 237 Vue files, 173 Go files, and 69 SQL files.

The architecture is unusually disciplined for a solo project. The Go `engine/` implements a 27-stage deterministic `UniversalImportWorkflow` in Temporal with an explicit `stagegraph` dependency DAG, deterministic parser and chunker registries with immutable capability receipts, and a layered custody hash model (H1 whole-source, H2 per-record, H3 ordered fold). Postgres carries 56 forward migrations from `0001_init_extensions.sql` through `0055_graph_lane_provenance_and_graphrag_recovery.sql`. The retrieval seam in `server/evidence/retrieval.py` enforces a horizon pre-filter with no bypass parameter and fails closed on unaudited reads.

The problems are not architectural quality. They are **surface area, duplication across two runtimes, documentation mass exceeding code mass, and a large backlog of "held" activations that are implemented but not live**.

## What is genuinely strong

Several parts of this codebase should be preserved and protected from refactoring.

- **The stagegraph contract.** `engine/stagegraph/registry.go` declares stages with explicit `DependsOn` edges and documented rationale, so execution order derives from the DAG rather than slice position. This is the correct way to make forensic ingest replayable.
- **Deterministic selection receipts.** Both `engine/parser/registry.go` and `engine/chunk/registry.go` persist an immutable `Selection` snapshot (parser ID, version, format, quality) before execution, and `ExecuteSelected` refuses to silently substitute a different registered adapter after registry drift. Very few RAG systems do this.
- **Custody hash discipline.** H1/H2/H3 naming is documented as a raw-custody concept explicitly distinct from normalized-record digests, preventing the common mistake of comparing incomparable hashes.
- **Fail-closed retrieval.** The horizon gate denies undated documents by default and treats a failed audit write as a failed search — the correct posture for an as-lived-versus-hindsight analysis product.
- **Coverage reconciliation stages.** `reconcile_record_accounting`, `reconcile_byte_coverage`, and `verify_raw_coverage_against_source` mean the pipeline can prove it did not silently drop input bytes.

## Tweak 1 — Collapse the two-runtime parser duplication

The single largest source of ongoing friction is that parsing, chunking, and hashing exist in **both** Go and Python.

| Concern | Go implementation | Python implementation |
|---|---|---|
| Parser adapters | `engine/parser/`, `engine/adapters/sbv/` (5 non-test files) | `server/tools/parsers/` (30 files across `ai_chat/`, `messaging/`, `generic/`) |
| Chunking | `engine/chunk/` (`chunk.document_markdown.offsets`) | `server/tools/repair/chunkers.py` (705 lines: `iter_xml`, `iter_html`, `iter_json`, `iter_ndjson`, `iter_csv`, `iter_pdf`) |
| Hashing | `engine/postgres/hash_repository.go`, SBV fold | `server/timeline/hashing.py`, `server/evidence/custody.py` |
| Ingest orchestration | `engine/uiw/workflow.go` (27 activities) | `server/ingest/service.py` (795 lines with its own receipt journal and stage sequencing) |

Two independent ingest paths means two custody stories, two chunk-ID vocabularies, and two places where a format regression can hide. The Python `server/ingest/service.py` has its own `PostgresReceiptJournal` with `stage_start`/`stage_finish`/`skip_after` semantics that parallel — but do not share — the Temporal stagegraph receipts.

The recommended tweak is not to rewrite either side. It is to declare **one custody-authoritative path** and demote the other to a pre-stage:

- Go `engine/uiw` remains the only writer of custody receipts, raw generations, normalized generations, and lineage.
- Python parsers become **format extractors invoked through `select_parser_activity` / `execute_parser_activity`**, returning `RawRecordEnvelope`-shaped output. The worker already registers those two stages through an N8N-backed seam (`registrations.N8N.SelectParser`), so the hook point exists.
- Python chunkers register as `chunk.Adapter` capabilities behind the same registry contract so `ChunkerID`/`ChunkerVersion` receipts stay uniform.

That single change removes the need to maintain parallel receipt journals and makes the 30 Python parsers assets rather than a competing pipeline.

## Tweak 2 — Retire the "held" backlog before adding features

`docs/DEBT.md` records at least twelve distinct hold states, and the pattern is consistent: the contract is implemented and tested locally, but the live cutover is gated. Notable examples include Semantica extraction (contract-tested, no database write, no worker deployment, no live corpus execution), native evidence vectors (`EvidenceChunkV1` accepted, but collection creation, PG-chunk backfill, canary receipt, alias switch, and reader rebinding still held), the MCP registry consolidation via ContextForge, and the `agno_app` role cutover.

The `agno_app` item is the sharpest and cheapest win. A non-superuser role was created live with scoped grants across `working`, `evidence`, `ops`, `analysis`, `reference`, `ai`, `public`, and `duckdb`, and verified non-superuser — but the application still connects as the superuser `ai`, which bypasses every GRANT and renders `sql/0029`'s role scoping inert. For a forensic evidence platform where append-only guards (`0017_append_only_guards.sql`) are part of the integrity story, running as a `rolbypassrls` superuser undermines the guarantee the migrations were written to provide.

Suggested sequencing:

1. `agno_app` role cutover (removes a live integrity gap, config-only change).
2. Native evidence vector cutover (unblocks the retrieval quality path, has a defined receipt procedure).
3. Semantica activation (unblocks candidate entity/event extraction, which the claim/assertion layer in `0052_claim_and_assertion_candidates.sql` depends on).
4. ContextForge/Portkey MCP consolidation (largest, most infrastructural).

Each held item is a bet that currently pays nothing. Converting three of them is worth more than any new subsystem.

## Tweak 3 — Documentation mass is now a liability

Markdown totals 131,489 lines against 102,707 lines of first-party Python and 32,403 lines of engine Go. `docs/` is 46 MB with 842 Markdown files, of which `docs/wiki` alone holds 580 files and 25 MB, plus `docs/research` at 9 MB and `docs/planning` at 3.9 MB.

More documentation than code is not automatically wrong for a governance-heavy forensic project, but the current structure has specific failure signatures:

- **Byline stacking.** README, `docs/DEBT.md`, and `server/evidence/retrieval.py` all carry chains of dated amendment bylines from multiple models (Sonnet 5, Kimi K3, GPT-5, Opus 5, glm-5.2, Fable 5). These are useful provenance but they push the actual content below the fold and encourage agents to append rather than revise.
- **Self-contradicting status.** `docs/DEBT.md` explicitly corrects a prior stale banner, noting migrations 0026–0029 were live despite "HELD/NOT APPLIED" markers in the SQL files. Status truth was distributed across two places and drifted.
- **Parking lots.** `_stale/` (248 KB), `to_be_deleted/` (80 KB), `docs/awaiting-verification/` (1.6 MB), `docs/pending-review/` (44 KB), and `docs/wiki/_TO_BE_DELETED` are all still tracked. `docs/wiki/FUCKED.MD` is a raw dictation transcript about reorganizing the wiki, checked into the canonical docs tree.
- **26 `AGENT_MEMORY.md` files and 13 `AGENTS.md` files.** Distributed agent context is a reasonable pattern, but at this count the probability that two of them disagree is high, and nothing enforces reconciliation.

The tweak here is mechanical and fast:

- Make **status live in exactly one machine-readable place** — a `docs/STATUS.yaml` or a Postgres `ops` table — with `DEBT.md` and SQL banners generated from it rather than hand-maintained.
- Delete or move `_stale/`, `to_be_deleted/`, and `docs/wiki/_TO_BE_DELETED` out of the working tree; git history preserves them.
- Cap byline chains at the most recent entry plus a link to history.
- Add a CI check that fails if any `AGENTS.md` or `AGENT_MEMORY.md` contradicts the single status source on a tracked key.

## Tweak 4 — pg_duckdb is barely used

Despite `pg_duckdb` being a headline element of the stack , the only first-party usage in `server/` and `engine/` is R2 secret provisioning: `ensure_duckdb_r2_secret()` appears in `server/api/runtime_support.py` and `server/core/session.py`, calling `duckdb.create_simple_secret(type := 'S3', ...)`, with failures treated as non-fatal. The `.duckdb/` directory at repo root contains only `AGENTS.md` and `CLAUDE.md` — no queries, no ELT definitions.

Meanwhile `server/tools/repair/chunkers.py` implements imperative Python iteration over XML, HTML, JSON, NDJSON, CSV, and PDF — exactly the class of set-based work DuckDB was added for.

The high-value tweak is narrow, not sweeping. Do not try to route XML and PDF through DuckDB; those genuinely need format-specific extractors. Do route the structured cases:

- CSV and NDJSON/JSONL record extraction → `read_csv_auto` / `read_json_auto` inside an `execute_parser_activity`, producing raw record rows directly.
- Bulk normalization joins and coverage reconciliation counts → DuckDB set operations rather than row-at-a-time Python.
- R2 projection/filter pushdown for large structured sources so the block-scratch stage is skipped when only a subset is needed.

This is worth doing because it removes the two heaviest Python iterators (`iter_csv`, `iter_ndjson`) from the custody path while leaving the genuinely hard formats where they belong.

## Tweak 5 — Retrieval is single-lane where the design calls for three

`server/evidence/retrieval.py` is 216 lines and is explicitly the only sanctioned read path. It performs a Weaviate-backed search with over-fetch (`_OVERFETCH = 5`, `_MAX_FETCH = 100`) and a post-hoc horizon filter. The module's own docstring flags the weakness: the current Weaviate adapter can prefilter exact dict fields but stores metadata as JSON text, so range prefiltering is unavailable and over-fetch is a mitigation rather than a guarantee.

The gap between this and the three-store design is significant:

| Design intent | Current state |
|---|---|
| Postgres anchors query with hard constraints and canonical IDs | Not part of the sanctioned seam; retrieval starts at the vector store |
| Weaviate provides hybrid recall | Implemented, but with post-filter horizon enforcement rather than pushdown |
| Neo4j/Graphiti expands temporal and entity adjacency | `server/analysis/graphiti_case_client.py` exists; reads/writes documented as incomplete  |
| Verification back to canonical record before synthesis | Audit is enforced; canonical re-verification of returned chunks is not evident in the seam |

The concrete tweaks, in order of payoff:

1. **Add a Postgres anchor step inside the seam.** Resolve entities, date windows, matter/case scope, and source class in SQL first, then pass an ID allowlist into the vector query. This converts the horizon gate from a post-filter into a pre-filter and eliminates the over-fetch recall risk the docstring warns about.
2. **Land the native `EvidenceChunkV1` cutover** so typed, range-indexed source clocks exist in Weaviate and range prefiltering becomes possible. This is already a held item; it directly fixes the retrieval weakness.
3. **Return an evidence packet, not documents.** `EvidenceSearchResult` currently exposes `documents`, `kept`, `denied`, `audit_id`. Extend it with canonical record references, parent-document context, graph neighbors, conflicting records, and explicit gap flags so downstream synthesis cannot quietly summarize away the record.
4. **Make graph expansion a first-class third step** rather than an incomplete side channel, keyed on the same canonical IDs.

## Tweak 6 — Repository hygiene items

Smaller issues worth batching into one cleanup pass:

- **`timesketch-fork/` is 39 MB in-tree** — 23 percent of the repository. Unless the fork is actively diverging, it belongs in a submodule or separate repo referenced by ADR-0060.
- **`server/vendored/` holds 558 Python files** (Semantica), and `vendored/sbv` is 11 MB of Go. Both are vendored for good reasons, but they distort every repo-wide search, lint scope, and file count. Consider pinned dependencies or submodules with a documented vendoring policy.
- **Only three TODO/FIXME markers exist across first-party `server/` and `engine/` code.** This is not a virtue signal — it means unfinished work is tracked in prose documents instead of at the code site. Inline `# HELD:` markers linked to the status source would put the backlog where the developer actually is.
- **`deploy/` contains 20+ compose files**, including `compose.data-surreal.yaml` and `compose.surreal-phase1.yaml` for a SurrealDB path that `DEBT.md` records as parked and denied. Move denied-path compose files out of `deploy/` so nothing can accidentally reference them.
- **A single commit is visible at clone depth 1** (`feat(db): re-baseline - schema builds from one file in 11s`, 2026-08-31) against 658 total commits — worth confirming the 56 migration files and the re-baseline single-file build have not diverged, since both now claim to define schema.
- **CI runs one workflow** (`validate.yml`) with lint, format, mypy, pytest, and an integration gate that fails if every collected integration test skipped. That gate is a good pattern. Extend the same "prove it actually ran" logic to the Go engine tests, which currently have no visible workflow.

## Priority ordering

If the goal is maximum improvement per unit of effort:

1. **Cut over `agno_app`** — config change, closes a live integrity gap where superuser access nullifies the append-only and grant model.
2. **Delete the parking-lot directories and centralize status** — hours of work, removes the drift class that already produced one documented false status.
3. **Land the native evidence vector cutover** — unblocks range prefiltering and fixes the retrieval seam's acknowledged weakness.
4. **Add the Postgres anchor step to `evidence_search`** — converts post-filtering to pre-filtering, improving both correctness and recall.
5. **Route Python parsers through the Go stagegraph seam** — ends the dual-custody-path problem permanently.
6. **Move `timesketch-fork/` and vendored trees out of the main tree** — restores sane repo ergonomics for both humans and agents.

## What not to change

Resist refactoring the stagegraph DAG, the parser/chunker selection receipt contract, the H1/H2/H3 custody naming, the append-only guards, or the no-bypass horizon gate. These are the parts that make the platform defensible, and they are the parts most likely to be "simplified" by an agent optimizing for readability. Every one of them exists because a forensic pipeline must be able to prove what it did, not merely produce a good answer.