# Records recovery, Phase 2, Lane C — notes

> _Byline: Claude Code · Sonnet (recovery lane C) · 2026-09-02_

## Scope

Reconstruct 8 named files under `docs/reviews/2026-08-25-schema-audit/` authored in Codex CLI
sessions 2026-08-25..27 but never committed, per `RECOVERY-NOTE.md`'s method and §5 gap table:

- `PLATFORM-NAMING-CENSUS-AND-HANDOFF.md` (cited authoritative by D-086)
- `PLATFORM-NAMING-MIGRATION-PROPOSAL.md`
- `UNIFIED-PHYSICAL-MODEL.md`
- `PROVISIONAL-PHYSICAL-MODEL.md`
- `AUDIT-GAP-REGISTER.md`
- `CROSS-DOMAIN-CONTRACT-MATRIX.md`
- `OWNER-BACKBONE.md`
- `SYSTEM-ARCHITECTURE.md`

## Pre-check (git + filesystem)

`git log --all --oneline -- "**/<filename>"` returned empty for all 8 files, and a filesystem
`Glob` for each also returned nothing prior to this recovery. **None of the 8 files were previously
committed or present on disk anywhere in the repo.** All 8 required reconstruction; none were
skipped.

## Method (scripted, mirrors `RECOVERY-NOTE.md`'s own method)

Wrote three Python scripts to the session scratchpad (not committed; listed here for
reproducibility):

1. **`scan_candidates.py`** — walked every `rollout-*.jsonl` under
   `C:\Users\matts\.codex\sessions\2026\08\{25,26,27,28}\` (206 files total), line-by-line (JSONL:
   one JSON record per physical line). For each line containing both the substring `apply_patch`
   and at least one of the 8 target filenames, parsed the JSON, and if it was a
   `custom_tool_call` with `name == "exec"` whose `input` contained `apply_patch`, extracted the
   embedded V4A patch text (`const patch = "..."`) via a backslash-aware scanner + JSON-string
   unescape. Cross-referenced each call's `call_id` against the same file's
   `custom_tool_call_output` to classify accepted (`"Script completed"`) vs. rejected
   (`"apply_patch verification failed"` / `"Script failed"`). Found **76 raw candidate calls**
   across only 6 rollout files (all within 08-25/26/27 — none needed from 08-28).
2. **`parse_ops.py`** — a critical correctness step: the raw 76 candidates included false
   positives where a target filename merely appeared as *text* inside an unrelated big patch
   (e.g. a `LIFECYCLE-MANIFEST.md` patch that lists all 8 filenames in a table, and one call at
   2026-08-27T09:32:06Z that superficially "matched" all 8 targets this way). Fixed by parsing each
   patch into its actual `*** Add File: <path>` / `*** Update File: <path>` / `*** Delete File:
   <path>` operations (V4A patch header lines) and keeping only ops whose **path basename** exactly
   equals one of the 8 targets. This dropped the false-positive multi-file matches and produced
   accepted-op counts that match `RECOVERY-NOTE.md §5`'s own table exactly for every file it listed
   (e.g. `AUDIT-GAP-REGISTER.md`: 10 accepted ops vs. the table's "10"; `PROVISIONAL-PHYSICAL-MODEL.md`:
   15 vs. "15"; `UNIFIED-PHYSICAL-MODEL.md`: 6 vs. "6"; `CROSS-DOMAIN-CONTRACT-MATRIX.md`: 2 vs. "2";
   `OWNER-BACKBONE.md`: 1 vs. "1") — independent confirmation the extraction method is sound.
3. **`reconstruct.py`** — sorted each target's accepted ops by real timestamp, replayed them: an
   `Add File` op seeds full content (strip the `+` prefix each Add-File line carries); an `Update
   File` op is split into hunks on `@@` markers and each hunk applied via, in order: (a) exact
   contiguous match of the hunk's context+removed lines starting from a monotonically-advancing
   cursor, (b) exact match anywhere in the file (non-monotonic fallback), (c) whitespace-flexible
   match (normalize runs of whitespace), (d) prefix-anchored match (locate the longest unique
   contiguous sub-run of the hunk from either end). Any hunk that still fails to locate is logged as
   an explicit **GAP** — never guessed/inserted.

## Results — per-file status

| # | File | Status | Bytes | Notes |
|---|---|---:|---:|---|
| 1 | `PLATFORM-NAMING-CENSUS-AND-HANDOFF.md` | **Partial** | 7,216 | No `Add File` located anywhere in scope (2026-08-25..28) — file pre-existed the scan window's earliest hunk. 2 accepted `Update File` hunks recovered verbatim (2026-08-27, the D-091/D-092 addendum + `agno_app` correction + receipt-log entry). |
| 2 | `PLATFORM-NAMING-MIGRATION-PROPOSAL.md` | **Full** | 4,255 | `Add File` (2026-08-26T21:19:35Z) + 2 `Update File` hunks, 0 gaps. |
| 3 | `UNIFIED-PHYSICAL-MODEL.md` | **Partial** | 22,624 | No `Add File` located; file already existed live by 2026-08-26T12:12:44Z per a directory-listing tool output captured in a sibling rollout, well before the earliest located `Update File` hunk (13:05:44Z). 6 accepted hunks recovered verbatim. |
| 4 | `PROVISIONAL-PHYSICAL-MODEL.md` | **Full** | 38,641 | `Add File` (2026-08-25T13:27:48Z) + 14 accepted `Update File` hunks (of 18 attempts; 4 rejected by the original session itself), 0 gaps. |
| 5 | `AUDIT-GAP-REGISTER.md` | **Near-full** | 24,665 | `Add File` (2026-08-26T12:20:17Z) + 9 of 10 accepted hunks applied cleanly. 1 documented gap: a `## Resolution log` section (3 dated entries) existed by 2026-08-26T21:53Z but its own creation is outside scope; the 3 entries' exact text is recovered and quoted verbatim in a gap-note appendix inside the file rather than spliced into the body (structure/position not independently confirmed). |
| 6 | `CROSS-DOMAIN-CONTRACT-MATRIX.md` | **Full** | 11,551 | `Add File` (2026-08-25T14:18:02Z) + 1 `Update File` hunk, 0 gaps. |
| 7 | `OWNER-BACKBONE.md` | **Partial** | 2,708 | No `Add File` located; only 1 accepted `Update File` hunk in scope (part of the same 2026-08-26T13:41:18Z multi-file consolidation call that touched `UNIFIED-PHYSICAL-MODEL.md` and `CROSS-DOMAIN-CONTRACT-MATRIX.md`). |
| 8 | `SYSTEM-ARCHITECTURE.md` | **Full** | 12,668 | Single `Add File` (2026-08-25T14:13:30Z), 0 further hunks, 0 gaps. |

**Total: 124,428 bytes across 8 files.** 4 files (2, 4, 6, 8) are full, high-confidence recoveries
with zero unresolved hunks. 1 file (5) is near-full with one explicitly documented and
verbatim-quoted gap. 3 files (1, 3, 7) are honest partial recoveries: every accepted `apply_patch`
hunk that touched them was located and is reproduced verbatim as labeled diff fragments, but each
file's base content (created before this task's scan window, via a mechanism other than a captured
`apply_patch` call) could not be reconstructed. This mirrors the exact gap pattern
`RECOVERY-NOTE.md` already documented for `SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html` — content that
demonstrably existed (later hunks treat it as pre-existing context) but whose creation left no
`apply_patch` trace in the 2026-08-25/26/27 (and, checked, 2026-08-28) session transcripts.

## Contradiction flags against committed canon

Checked every recovered passage against `docs/DECISION_LOG.md` (through D-092, live-committed) and
`AGENTS.md`'s current-truth summary. **No contradictions found.** Specifically:

- All 8 recovered files are internally consistent with D-069 through D-081 (SurrealDB as the
  governed final derived temporal graph, PostgreSQL canonical, Weaviate/Neo4j as rebuildable
  projections) — this matches `AGENTS.md`'s current stack description exactly.
- `PLATFORM-NAMING-CENSUS-AND-HANDOFF.md`'s fragments and `PLATFORM-NAMING-MIGRATION-PROPOSAL.md`
  reference **D-086** (naming scheme) and **D-091/D-092** (fresh `platform` database, `platform_admin`,
  `platform_runtime`, `agno_app`/`ai` preserved-not-renamed) — these decision numbers are inside the
  already-committed D-072..D-081 recovery range extended by the live `docs/DECISION_LOG.md`; nothing
  in the recovered text asserts anything the current log disputes.
- `AUDIT-GAP-REGISTER.md`'s recovered content already carries its own internal
  "Current-target override — 2026-08-27 (D-091/D-092)" caveat superseding its dated `ai`/`agno_app`
  observations — i.e. the document itself, as recovered, already self-corrects toward the
  now-committed canon. No further correction was needed or applied.
- `UNIFIED-PHYSICAL-MODEL.md`'s recovered fragments are themselves **mid-course corrections** away
  from an earlier "SurrealDB owns everything, PG has nothing past R9" position toward "PostgreSQL
  retains canonical control/ledger families; Surreal executes the final derived walk/analysis" —
  this is the same direction D-073/D-078/D-080 (committed) ultimately took. No conflict.
- `OWNER-BACKBONE.md`'s one recovered hunk (AI-chat permanently barred from evidence promotion,
  Timesketch fork as governed bulk-curation service) is consistent with D-082 (permanent AI-chat
  evidence exclusion, already committed) and D-084/D-085/ADR-0060 (Timesketch fork), referenced
  elsewhere in the corpus (`AUDIT-GAP-REGISTER.md` GAP-032/GAP-034).

## What was NOT touched

Per task scope, only the 8 named files plus this notes file were created/edited. No git write
commands were run. The `docs/reviews/2026-08-25-schema-audit/reconciliation-domains/` directory
(R00–R14 domain guides + `README.md` + `DOMAIN-GUIDE-TEMPLATE.md`) was found **already fully
reconstructed and present on disk** at the start of this task — a separate, concurrently-running
recovery lane (its own scratchpad artifacts, `_report.json`, were visible in this session's shared
scratchpad directory) had already completed that scope. Nothing in that directory was read, edited,
or duplicated by this lane.

## Scripts (scratchpad, not committed)

`scan_candidates.py`, `parse_ops.py`, `reconstruct.py`, `finalize.py`, `finalize_partials.py` — all
under this session's scratchpad
(`...\da5b5108-5039-4a47-b029-4d0337b6eab6\scratchpad\`). Intermediate artifacts
(`candidates.pkl`, `events.pkl`, `events_summary.txt`, `reconstruct_log.txt`, `all_fragments.txt`)
are in the same directory for anyone who wants to re-verify or extend this recovery (e.g. to chase
the 3 partial files' missing base content in later/other Codex sessions outside 2026-08-25..28).
