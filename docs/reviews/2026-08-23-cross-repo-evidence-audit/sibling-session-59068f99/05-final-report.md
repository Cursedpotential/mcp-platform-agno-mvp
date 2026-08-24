# Consolidated Report — Document Handling, Search, Evidence Bundling

> _Byline: Claude Code · Opus 5 · 2026-08-23_
>
> Published artifact: https://claude.ai/code/artifact/0d1cd14a-b9ce-4e26-b51c-698fe1e3b3d3
> Phase 0 inputs: `phase0-requirements-register.md` (R01–R68), `phase0-map-agno.md`,
> `phase0-map-legal-workspace.md`, `phase0-map-sbv-forensic.md`.

## Executive summary

All three repos generate forensic hashes with real care. Almost nothing in the system ever
checks them. The architecture is sound and the boundary between the evidence platform and the
legal workspace is clean and deliberately enforced — the deficits are in verification,
bundling/export, and one unconnected seam, not in structure.

## Critical

| ID | Finding | Evidence | Violates |
|---|---|---|---|
| F-01 | H2/H3 never independently recomputed anywhere. Agno re-derives H1 only; on match it records SBV's H2 list + chain verbatim (`computed_by="sbv:internal.custody.HashRecordH2"`). Agno holds the raw bytes and could re-derive. | `server/evidence/custody.py:489,512-525`; sbv `internal/handlers.go:103-127` | R20 R35 R43 |
| F-02 | Custody-hashing parser demoted PRIMARY→SHADOW; non-hashing `sms_xml.py` is primary. Records ingested while SBV is down get no custody hash. MMS media dropped if SBV down. | archive-triage lineage doc; register Contradiction 3 | R14 R15 R20 |
| F-03 | ContextForge JWT secret on ovh-app is the literal string `set CF_JWT_SECRET_KEY` while `AUTH_REQUIRED=true`. Known as B1; gates the seam work. | `Legal-Workspace/docs/URGENT-TODO.md` B1 | — |

## High

| ID | Finding | Evidence | Violates |
|---|---|---|---|
| F-04 | H3 chain never spans batches — sole production call passes `prevChain=""`. Batch deletion/reorder undetectable. Fix needs a NEW canon tag (bare `h3-chain-v1` is already ambiguous). | `internal/parser.go:994`; `custody.go:91`; Agno `custody.py:374-380` | R20 R60 |
| F-05 | Multi-attachment MMS stores only the first part. Raw XML retained + H2 covers whole element, so recoverable — but DB and all exports carry one attachment, unsignalled. | `internal/parser.go:310-330` | R15 R58 |
| F-06 | No evidence bundle anywhere. SBV export excludes media bytes; no bundle hash. Agno has no export function at all. No EDRM (.opt/.dat) and no chronology matrix. | `internal/models.go:16`; phase0-map-agno §5 | R56 R59 R60 R65 |
| F-07 | Agno↔Legal seam has no producer and no UI caller. `:import` and `events:apply` unreferenced in `web/src`; Agno emits no `LegalSourcePackage`. Boundary itself is correct and enforced (`api/main.py:152`). | phase0 maps | R07 R47 |
| F-08 | Graph is write-only — `graphiti_case_client.py` (165 lines) has no query method. | phase0-map-agno §4 | R30 R31 R64 |
| F-09 | `verify_chain()` only non-test caller is a manual script; no startup/scheduled run despite docstring intent. Well tested incl. tamper cases. | `scripts/audit_dump.py:199`; `tests/test_audit_ledger.py:396-426` | R24 R42 |
| F-10 | `evidence.source`/`file_node`/`custody_event` in no numbered migration (only `sql/_manual/`). `0030` HELD-not-applied yet case-management code references its tables. | `sql/_manual/20260802_reconcile_evidence_ddl.sql:46-165`; `sql/0030:5-7` | R23 R68 |
| F-11 | Legal-Workspace PG tables never created — `store.py:69` passes non-null `store_dir`, `engine.py:27` forces SQLite. `sql/0001`/`0002` HOLD, never applied, diverge from ORM. | URGENT-TODO B2, confirmed | R18 R23 R68 |

## Medium

F-12 no scope report anywhere (primitives exist: `IngestReceipt.rejections[]`, search `denied`) · R34 R49 R53 —
F-13 single-granularity embedding, no dual isolated/context embedding, no retrieval-time filtering · R26 R27 R28 —
F-14 real pikepdf redaction + pypdf Bates, both orphaned from `web/` —
F-15 `extractGroupNameFromTrID` live no-op returning `""` (`parser.go:393-433`) · R15 —
F-16 SBV dedup unique index excludes `content_hash` → dedup on normalized equality not raw bytes —
F-17 `calendar_routes.py:166` `UUID` NameError; `/v1/automations/analysis-queue` has 2 dead callers, never registered —
F-18 `InsertCallLogBatch` (`database.go:408-446`) zero callers, omits `content_hash` —
F-19 FTS indexes `body` only; call logs unsearchable —
F-20 doc drift: `UPSTREAM.md` omits 4 Phase-5a files, `SPEC.md` omits 5 routes + phantom date params —
F-21 two parsers for one format with different custody properties; non-hashing one is primary · R13.
**Constraint:** Agno has an active Surreal phase-1 migration in flight + dirty tree — defer structural consolidation.

## Genuinely strong (do not refactor away)

- Hash-before-normalize ordering, proven by `custody_test.go:94-112` (identical normalization → different H2).
- Single sanctioned evidence read path: no bypass param, deny-undated-by-default, failed audit write fails the search, sole-writer enforced by a read-only engine.
- Real mandatory review gate: hash-gated release + `validate_factual_citations` closed-world constraint (R43).
- `EvidenceCitation.epistemic_class` — claim vs verified-statement separation (R45), rarely modelled at all.

## Owner decisions required

1. **Statistical elusion gate vs per-instance controls** — which is authoritative on disagreement (R40–R44 vs R32–R38).
2. **One system of record vs four coordinated stores** — reality already chose the former; recommend formally retiring the four-store design doc.
3. **Custody hashing mandatory at capture or best-effort** — current silent degradation is the one indefensible option.

## Sequenced plan

1. Rule on the three decisions. 2. Recompute H2/H3 independently in Agno (closes F-01).
3. Settle custody-lane policy in code (F-02). 4. Chain batches under a new canon tag (F-04).
5. Build `LegalSourcePackage` exporter + wire import (F-07 — highest capability per line).
6. Store all MMS attachments, include bytes in export (F-05, half F-06). 7. Schedule `verify_chain`, surface scope report (F-09, F-12).
8. Decide graph: build read or retire (F-08). 9. Bring custody DDL into numbered sequence — after Surreal lands (F-10).

## Limits

No Go toolchain — sbv findings are static reading + grep-verified call graphs, not `go build`/`go test`.
Nothing checked against a running database; migration/deploy state read from file headers and code.
`sbv-forensic` had no local clone; shallow-cloned read-only, history is one squashed commit.
