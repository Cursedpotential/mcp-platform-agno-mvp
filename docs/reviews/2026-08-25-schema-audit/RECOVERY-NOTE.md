# Recovery note — 2026-08-25 schema-audit documents

> _Byline: Claude Code · Sonnet (recovery subagent) · 2026-09-01_

## What happened

Several owner-ruling documents and `docs/DECISION_LOG.md` entries were written during Codex CLI
sessions between 2026-08-25 and 2026-08-27, in this directory and elsewhere, but were never
committed to git. The working copies were later lost/overwritten, leaving `docs/DECISION_LOG.md`
jumping from D-071 straight to D-082 and this review directory missing most of the documents its
own patch history shows were created here.

The full content survives inside Codex session rollout JSONL transcripts under
`C:\Users\matts\.codex\sessions\2026\08\{25,26,27}\`. This note documents what was recovered
2026-09-01 from those transcripts, how, and what could not be fully reconstructed.

## Method

1. Scanned all 185 rollout `.jsonl` files under the three date directories for `apply_patch` tool
   calls (Codex's `custom_tool_call` / `exec` mechanism, which issues `*** Begin Patch ... *** End
   Patch` V4A-format patches) whose patch text referenced the target filenames, the
   `2026-08-25-schema-audit` directory, or `docs/DECISION_LOG.md`.
2. Extracted every matching patch's raw text (JS-string-unescaped from the tool call's `input`
   field), together with its real ISO timestamp, source rollout file, and line number.
3. Cross-referenced each `apply_patch` call against its own `custom_tool_call_output` in the same
   rollout to confirm whether the *original* Codex session actually accepted the patch
   ("Script failed... apply_patch verification failed" = rejected). Only calls the original session
   itself accepted were replayed; rejected attempts were discarded, matching what really happened.
4. Sorted all accepted patches globally by real timestamp (not by rollout file — several rollout
   files represent concurrent/forked sessions editing the same files, so file-local order alone is
   not reliable) and replayed them in that order: `Add File` sections seed a file's content, `Update
   File` sections apply as context-diff hunks against the running reconstruction.
5. For hunks that didn't match verbatim (usually because an intermediate paragraph had been
   re-wrapped by a later edit, or a short numeric/label token drifted), a whitespace-flexible /
   prefix-anchored fallback matcher was used, always logging that it fired. Hunks that could not be
   located under any of these strategies are called out below as explicit gaps rather than guessed.
6. For `docs/DECISION_LOG.md`, rather than reconstructing the whole file (it already exists, correct,
   apart from the missing row range), only the `+`-side text of every hunk touching a `| D-0NN |` row
   was extracted, keeping the chronologically last version of each row number.

## Per-target results

### 1. `TEMPORAL-N8N-WORKFLOW-AND-GAPS.md` — **recovered full**

- Source: `rollout-2026-08-25T08-52-26-01a038fa-a77a-79e1-b66a-99bdb0af6771.jsonl`
- 7 accepted patch calls, 2026-08-25T13:51:47Z (Add File) through 2026-08-25T14:07:30Z (last Update).
- One hunk (the final paragraph rewrite in "Workflow E — final paired walk and delta analysis",
  ending "...remain in Weaviate; semantic graph details remain in Neo4j.") needed the
  whitespace-flexible fallback matcher because an earlier hunk in the same document had already
  reflowed that paragraph's line wrapping differently than the later hunk's stored context assumed.
  The fallback located the one candidate paragraph unambiguously and applied cleanly — confidence is
  high, but flagged per the quality bar.
- Written to: `docs/reviews/2026-08-25-schema-audit/TEMPORAL-N8N-WORKFLOW-AND-GAPS.md` (21 KB).

### 2. `SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html` — **recovered partial + gaps**

- Source: `rollout-2026-08-26T08-31-45-01a03e0e-13ba-7430-86b6-3e53ec175d38.jsonl` (a single long-lived
  session spanning 2026-08-26 into 2026-08-27, itself ~120 MB).
- 9 accepted patch calls, 2026-08-27T00:05:01Z (Add File) through 2026-08-27T02:55:08Z (last Update).
- Two hunks needed a prefix-anchored fallback (a "Go tests pass" counter in the §9 progress table,
  and the "Go atomic stage graph" row) because an intervening edit had already changed the exact
  trailing wording the hunk expected; the anchor (row label) was unique, so the swap is high
  confidence.
- **Three hunks from the 2026-08-27T02:23:49Z patch call could not be located and were skipped —
  genuine gap, not guessed:**
  1. Row 11 of the §2 atomic-stage table (`<tr><td>11</td>...`) was supposed to be renamed from
     `reconcile_record_accounting_activity` to `hash_raw_generation_activity` (adding a fifth,
     explicit H3-raw-generation hash stage). The row **still reads `reconcile_record_accounting_activity`**
     in the recovered file.
  2. The `<p>Per <code>vendored/sbv/CUSTODY.md</code> (authoritative)...</p>` paragraph rewrite
     (replacing it with the "H1, H2, and H3 name only the raw-custody hashes..." wording that
     introduces the `h3-chain-platform-rawall-genesisempty-v1` tag) was **not applied**; that
     paragraph does not appear in the recovered file at all.
  3. The §2 "Four hash computations" table's `H2` row was supposed to be renamed/reworded to
     `Normalized record digest` (and `H3` to a similarly renamed row), moving the section toward a
     "five hash computations" model matching decisions D-087/D-088. **The table still reads as the
     original "Four hash computations" (H1 / Raw-record digest set / H2 / H3) shown in §2's heading
     and rows.**
  - Root cause: verified against every other accepted `SBV-GO-...` patch call in the 08-25/26/27
    window (all 9 of them, `failed=False` per their own tool output) — none of them ever writes the
    intermediate content these three hunks expected to find. The hunks themselves *did* succeed in
    the real 2026-08-26/27 session (their own tool output shows success), so the document state they
    depended on was produced by some other mechanism (very possibly a later continuation session on
    2026-08-28 or after, outside this task's 08-25–08-27 scope, or a full-file rewrite outside
    `apply_patch`). **Last verified-good patch for this specific area: 2026-08-27T02:10:36Z; the
    2026-08-27T02:23:49Z patch's other five sub-edits in the same call (the `hash_raw_generation_activity`
    Go-comment update, the JSON schema description changes, the "Go atomic stage graph" and "Five Go
    hashing Activity bodies" row rewordings, and the closing `<div class="warning">` status paragraph)
    WERE all recovered — only the three items above are missing.**
- Practical effect: the recovered file is internally slightly inconsistent — its own §9 progress
  table and closing status banner say "five distinct hash computations" / "twelve Activity bodies",
  while §2 still shows only 22 numbered activities and a "Four hash computations" sub-table. A future
  session with access to the 2026-08-28+ Codex sessions (or the owner's memory of the change) should
  reconcile these three specific spots.
- Written to: `docs/reviews/2026-08-25-schema-audit/SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html` (~23 KB).

### 3. Whole-system conceptual model — **recovered full**

- Filename: `WHOLE-SYSTEM-CONCEPTUAL-MODEL.md` (this is the file `docs/INDEX.md` edits referenced as
  "Whole-system conceptual model | reviews/2026-08-25-schema-audit/WHOLE...").
- Source: `rollout-2026-08-25T08-52-26-01a038fa-a77a-79e1-b66a-99bdb0af6771.jsonl` (Add File +
  most updates) and `rollout-2026-08-26T08-31-45-01a03e0e-13ba-7430-86b6-3e53ec175d38.jsonl` (three
  later updates the next day).
- 14 accepted patch calls, 2026-08-25T13:20:41Z (Add File) through 2026-08-26T13:33:40Z (last Update).
- Zero unresolved hunks; every context anchor matched exactly on the first try. High confidence.
- Written to: `docs/reviews/2026-08-25-schema-audit/WHOLE-SYSTEM-CONCEPTUAL-MODEL.md` (29 KB).

### 4. `docs/DECISION_LOG.md` D-072 through D-080 — **recovered full**

- All nine rows recovered verbatim from `rollout-2026-08-25T08-52-26-01a038fa-a77a-79e1-b66a-99bdb0af6771.jsonl`,
  written once each in sequence between 2026-08-25T13:34:09Z and 2026-08-25T14:03:59Z, and never
  revised again anywhere in the 08-25–08-27 window (checked against every later
  `docs/DECISION_LOG.md`-touching patch call in that range).
- D-081 was also recovered incidentally (same session, last write 2026-08-25T14:07:04Z) — outside
  the requested D-072–D-080 range but reproduced anyway since it was already in hand.
- Delivered to `docs/pending-review/D-072-D-080-backfill.md` for owner review/append, per the task
  instructions — `docs/DECISION_LOG.md` itself was **not** touched by this recovery (another session
  has it active).

### 5. Other `docs/reviews/2026-08-25-schema-audit/**` files in the rollouts but not in the live repo

The rollout transcripts show **44 distinct files** created/edited under this review directory across
2026-08-25 through 2026-08-27. As of 2026-09-01 (before this recovery's three writes above), only 7
of those 44 existed live in the repo:

- `GAP-004-IMPLEMENTATION-STATUS.md`, `GAP-031-IMPLEMENTATION-STATUS.md`,
  `TIMESKETCH-FORK-CURATION-HANDOFF.md`, `TIMESKETCH-FORK-WP-E01-HANDOFF.md` — present already
  (evidently re-created or preserved by a later session).
- `SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html`, `TEMPORAL-N8N-WORKFLOW-AND-GAPS.md`,
  `WHOLE-SYSTEM-CONCEPTUAL-MODEL.md` — the three this recovery just restored.

**The following 38 files exist in the rollout patch history but are still missing from the live
repo** (name, first-seen, last-touched timestamp; not reconstructed in this pass — this is a listing
only, per the task's "note... list names; extract if small" framing, since fully recovering 38 more
documents was out of scope for this task):

| File | First seen | Last touched | Patch ops |
|---|---|---|---|
| `AGENT-HANDOFF-PROTOCOL.md` | 2026-08-25T14:18:02Z | 2026-08-25T14:18:02Z | 1 |
| `AUDIT-GAP-REGISTER.md` | 2026-08-26T12:20:17Z | 2026-08-27T09:06:57Z | 10 |
| `COMPLETE-CODEBASE-AUDIT.md` | 2026-08-26T12:18:44Z | 2026-08-26T13:00:40Z | 4 |
| `COMPREHENSIVE-PATH-REVIEW.html` | 2026-08-26T13:15:03Z | 2026-08-26T14:55:17Z | 4 |
| `COMPREHENSIVE-PATH-REVIEW.md` | 2026-08-26T13:13:30Z | 2026-08-26T13:40:26Z | 4 |
| `CROSS-DOMAIN-CONTRACT-MATRIX.md` | 2026-08-25T14:18:02Z | 2026-08-26T13:41:18Z | 2 |
| `ENGINEERING-DOCUMENTATION-PACKAGE.md` | 2026-08-25T14:20:11Z | 2026-08-26T13:38:22Z | 6 |
| `OWNER-BACKBONE.md` | 2026-08-26T13:41:18Z | 2026-08-26T13:41:18Z | 1 |
| `PARALLEL-GAP-EXECUTION-BOARD.md` | 2026-08-26T21:33:47Z | 2026-08-27T09:06:57Z | 4 |
| `PLATFORM-NAMING-CENSUS-AND-HANDOFF.md` | 2026-08-27T09:05:43Z | 2026-08-27T09:12:40Z | 2 |
| `PLATFORM-NAMING-MIGRATION-PROPOSAL.md` | 2026-08-26T21:19:35Z | 2026-08-27T09:05:43Z | 3 |
| `PROPOSAL-FINAL.md` | 2026-08-27T09:08:27Z | 2026-08-27T09:08:27Z | 1 |
| `PROVISIONAL-PHYSICAL-MODEL.md` | 2026-08-25T13:27:48Z | 2026-08-26T13:34:35Z | 15 |
| `RECONCILIATION-DOMAIN-WORKSTREAMS.md` | 2026-08-25T14:07:04Z | 2026-08-26T13:39:18Z | 2 |
| `RECONCILIATION-RUNBOOK.md` | 2026-08-25T14:18:02Z | 2026-08-25T14:18:02Z | 1 |
| `SEMANTIC-AGENT-WORK-PACKAGES.md` | 2026-08-26T13:37:34Z | 2026-08-26T21:54:05Z | 3 |
| `SESSION-HANDOFF-COMPLETE-CODEBASE-AUDIT.md` | 2026-08-25T23:06:09Z | 2026-08-27T09:06:57Z | 8 |
| `SYSTEM-ARCHITECTURE.md` | 2026-08-25T14:13:30Z | 2026-08-25T14:13:30Z | 1 |
| `TIMESKETCH-LIVE-PREVIEW-STATUS.md` | 2026-08-27T03:03:42Z | 2026-08-27T03:05:07Z | 4 |
| `UNIFIED-PHYSICAL-MODEL.md` | 2026-08-26T13:05:44Z | 2026-08-26T13:41:18Z | 6 |
| `WP-C01-IMPLEMENTATION-STATUS.md` | 2026-08-26T21:53:43Z | 2026-08-26T21:53:43Z | 1 |
| `reconciliation-domains/DOMAIN-GUIDE-TEMPLATE.md` | 2026-08-25T14:13:30Z | 2026-08-25T14:13:30Z | 1 |
| `reconciliation-domains/R00-canon-contract-freeze.md` | 2026-08-25T14:14:58Z | 2026-08-26T13:40:16Z | 8 |
| `reconciliation-domains/R01-pg-backbone-cdc-receipts.md` | 2026-08-25T14:16:41Z | 2026-08-26T13:43:13Z | 6 |
| `reconciliation-domains/R02-context-ingest-parser-boundary.md` | 2026-08-25T14:18:08Z | 2026-08-26T13:43:49Z | 6 |
| `reconciliation-domains/R03-normalization-messages-clocks.md` | 2026-08-25T14:19:37Z | 2026-08-26T13:43:13Z | 6 |
| `reconciliation-domains/R04-hashing-custody-promotion.md` | 2026-08-25T14:21:25Z | 2026-08-26T13:44:11Z | 5 |
| `reconciliation-domains/R05-weaviate-search.md` | 2026-08-25T14:14:25Z | 2026-08-26T13:00:01Z | 6 |
| `reconciliation-domains/R06-semantica-neo4j.md` | 2026-08-25T14:15:36Z | 2026-08-26T13:00:01Z | 6 |
| `reconciliation-domains/R07-governed-facts-realizations.md` | 2026-08-25T14:17:05Z | 2026-08-26T13:43:49Z | 7 |
| `reconciliation-domains/R08-postgis-modalities.md` | 2026-08-25T14:18:22Z | 2026-08-26T13:00:01Z | 4 |
| `reconciliation-domains/R09-cross-store-reconciliation.md` | 2026-08-25T14:19:58Z | 2026-08-26T13:43:49Z | 11 |
| `reconciliation-domains/R10-surreal-aggregation.md` | 2026-08-25T14:13:53Z | 2026-08-26T12:59:13Z | 6 |
| `reconciliation-domains/R11-walks-paired-delta.md` | 2026-08-25T14:14:50Z | 2026-08-26T13:01:13Z | 8 |
| `reconciliation-domains/R12-legal-workbench.md` | 2026-08-25T14:15:46Z | 2026-08-26T13:43:49Z | 11 |
| `reconciliation-domains/R13-temporal-n8n-execution.md` | 2026-08-25T14:16:58Z | 2026-08-26T13:43:13Z | 9 |
| `reconciliation-domains/R14-migration-cutover-integration.md` | 2026-08-25T14:18:13Z | 2026-08-26T13:43:49Z | 13 |
| `reconciliation-domains/README.md` | 2026-08-25T14:13:30Z | 2026-08-26T12:59:13Z | 2 |

These are the R00–R14 "reconciliation domain" workstream guides referenced by D-081 (see the
backfill doc) plus the wider schema-audit deliverable set (physical model docs, the codebase audit,
handoffs, the platform-naming migration package, the Timesketch-fork proposal chain, etc.). They
follow the same recoverable `apply_patch` pattern as the three files restored above and could be
reconstructed the same way in a follow-up pass if the owner wants them back — this pass stopped at
listing them, per the task's stated priority order (items 1–4 first).

## Honest gaps summary

- `SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html`: three specific pieces of content (table row 11's activity
  name/description, the CUSTODY.md-sourced hash-naming paragraph, and the "Normalized record digest"
  renaming of the §2 hash-summary table) could not be reconstructed from the 08-25–08-27 rollouts —
  see the detailed root-cause note above. Everything else in that 9-edit, ~23 KB document recovered
  cleanly.
- The 38-file list in §5 is a listing only, not a reconstruction — flagged for a follow-up pass if
  wanted.
- Verification was against the *rollout transcripts' own record of tool-call success/failure*, not
  against a second independent copy of the files, since no such copy exists. Confidence is high
  (every non-flagged hunk matched byte-for-byte against the running reconstruction) but this is a
  best-evidence reconstruction, not a checksum-verified restore.
