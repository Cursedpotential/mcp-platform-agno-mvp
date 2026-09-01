# Handoffs-v2 — Validation Report & Dispatch Plan

> _Byline: Claude Code · Fable 5 · 2026-09-01_
> Source package: `C:\Users\matts\Downloads\handoffs-v2 (1).zip` (14 files, compiled 2026-08-31).
> Every load-bearing claim below was verified against the live repo and the live
> `platform` database at 100.91.190.107:5432 on 2026-09-01.

## Validation results (live-probed, not taken on faith)

| Handoff | Claim | Verdict |
|---|---|---|
| H-00 | 0057-0062 untracked, DECISION_LOG uncommitted | **OBSOLETE — already done.** 0057-0064 committed (`15a1d87`, `cc0f91c`); D-108–D-121 in `docs/DECISION_LOG.md`; both baselines committed; ledger `ddl_sha256` values match the committed files. Residual: the `baseline` ledger row still names superseded `sql/bootstrap/schema_baseline.sql` → folded into H-08. |
| H-02a | Tree does not compile, `undefined: reference` | **VALID, OPEN.** `go build ./...` in `engine/` fails at `parser/registry.go:31:13: undefined: reference`, exactly as described. |
| H-08a | 0062 written+swept but never applied; no `registry` schema | **VALID, OPEN — and worse.** Live schemas: `ai, analysis, archive, canon, context, duckdb, evidence, ext, ops, public, raw, reference, timeline, working` — no `registry`. Ledger has 0057-0061, 0063, 0064 — **0063/0064 were applied 2026-09-01 on top of the skipped 0062.** Code still references `registry.*`. |
| H-09/H-10 | Parking lots + timesketch-fork in tree | **PARTIALLY EXECUTED by owner, uncommitted.** 1,097 unstaged deletions (`timesketch-fork/` 1,011, `llm_probe*/`, `_stale/`, `to_be_deleted/`, `.full-review/`, `tool-skills/`). ⚠ The move also deleted **`.gitattributes` (repo root)** and **`.github/workflows/validate.yml`** (the only CI), and left `workbench/timesketch-fork/` + two stray `.html` files untracked — timesketch-fork moved *into* `workbench/` is still inside the repo. |
| H-11 | `sink` CHECK includes `surrealdb`, `opensearch`, `sat_temporal` | Consistent with applied 0058 (in ledger). Design-doc gap stands. |
| Index | 268 live tables | Now **289** (post-0063/0064 evolution). Cosmetic drift only. |
| H-01/H-04/H-05/H-06/H-07 retargets | `raw` schema, `content_chunk`, `content_sha256`, canon spine | Consistent with applied 0058-0061 (all in ledger). Accepted. |

**Bottom line: the package is sound.** One handoff is already done (H-00), two
are partially in flight (H-09/H-10), and the two urgent ones (H-02a, H-08a) are
confirmed real against live.

## New task discovered (not in the package)

**T-0 — Commit the owner's directory moves.** The 1,101-entry dirty tree
poisons every diff any agent produces after it. Must land before anything else:

1. `git rm` (by explicit path) the moved directories the owner confirms.
2. **Restore `.gitattributes` to repo root** (H-10 explicitly wants it for
   line-ending churn) and **`.github/workflows/validate.yml`** (H-02 builds on
   it) unless the owner deleted them deliberately.
3. Decide `workbench/timesketch-fork/` — still inside the repo; H-10 wants it
   *out* of the tree entirely. Delete the stray `workbench/*.html` files.

## Revised execution order

| Step | Task | Executor lane | Status |
|---|---|---|---|
| T-0 | Commit owner's moves, restore .gitattributes + validate.yml | Cheap (Luna free / Haiku) — after owner answers | **blocked on owner** |
| 1 | H-02a restore compilation (20 Go breaks + 16 prose files) | Sonnet or GLM-5.2 | ready after T-0 |
| 2 | H-08a apply 0062 + fix `registry.detection_pattern`→`reference`, rule `matter_knowledge_partition`, regenerate baseline, full-tree requalification grep | Fable main loop decides; Sonnet executes | ready after 1 |
| 3 (parallel) | H-08 status single-source (absorbs H-00 residual: baseline ledger row) · H-11 Surreal design doc · H-09 residual prose fixes | Sonnet · Kimi-K3-or-Sonnet · Luna free | Wave 1 |
| 4 (parallel) | H-02 CI harness · H-06 Semantica activation · H-10 residual (vendored excludes, gitattributes pass) | Sonnet/GLM · Sonnet · Luna free | Wave 2 |
| 5 | H-01 custody unification (30 parsers) · H-04 vector cutover | Opus-if-available else GLM-5.2 + Sonnet review — **Kimi K3 barred** · Sonnet | Wave 3 |
| 6 | H-05 retrieval seam · H-07 pg_duckdb | Opus-else-GLM+review — **K3 barred** · Sonnet | Wave 4 |
| 7 | H-03 production write-protection | Sonnet | **production cutover only** |

## Budget-mapped lanes (3 concurrent, per owner constraint)

- **Lane A — Claude Sonnet subagents** (plenty of usage): all mid-tier build/ops
  work; also the verifier that re-checks every returned handoff against its
  "Done when" list.
- **Lane B — GPT-5.6 Luna, high effort** (free): docs/hygiene tier — T-0, H-09,
  H-10 residual, prose repair.
- **Lane C — GLM-5.2 via Ollama Cloud / OpenCode**: parallel overflow for
  build-tier work (H-02a, H-02, H-04, H-07) and the open-weight fallback for
  H-01/H-05 when Opus budget is unavailable.
- **Sol/Terra (OpenAI paid)**: not used — minimal credits. Terra's few dollars
  held in reserve for a second opinion on H-08a's two mismatch rulings if wanted.
- **Frontier judgment calls** (H-08a decision, H-01/H-05 oversight): stay in the
  Fable main loop; execution delegated down.

## Completion gate (applies to every dispatch)

A handoff is accepted back only when its own "Done when" block is verified by a
separate Sonnet check — build/tests actually run, live `information_schema`
actually probed, no dropped-table or `content_hash` references remaining. No
self-reported completion counts.

## Open questions for the owner

1. Which directories did you move, and to where? Is `workbench/timesketch-fork/`
   the intended destination (it is still inside the repo tree)?
2. Were the deletions of root `.gitattributes` and
   `.github/workflows/validate.yml` intentional, or swept up in the move?
3. Green light to dispatch T-0 → H-02a → H-08a and Wave 1?
