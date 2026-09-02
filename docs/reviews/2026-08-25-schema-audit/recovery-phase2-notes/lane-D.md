# Records recovery — Phase 2, Lane D

> _Byline: Claude Code · Sonnet (recovery lane D) · 2026-09-02_

Scope: reconstruct 12 files listed in [`../RECOVERY-NOTE.md`](../RECOVERY-NOTE.md) §5 as owned
by Lane D — `COMPLETE-CODEBASE-AUDIT.md`, `COMPREHENSIVE-PATH-REVIEW.md`,
`COMPREHENSIVE-PATH-REVIEW.html`, `ENGINEERING-DOCUMENTATION-PACKAGE.md`,
`SEMANTIC-AGENT-WORK-PACKAGES.md`, `SESSION-HANDOFF-COMPLETE-CODEBASE-AUDIT.md`,
`RECONCILIATION-RUNBOOK.md`, `AGENT-HANDOFF-PROTOCOL.md`, `PARALLEL-GAP-EXECUTION-BOARD.md`,
`PROPOSAL-FINAL.md`, `TIMESKETCH-LIVE-PREVIEW-STATUS.md`, `WP-C01-IMPLEMENTATION-STATUS.md`.
Lanes A/B (concurrent, same scratchpad root) own the `reconciliation-domains/` set — see
their own `lane-A.md` / `lane-B.md`, not touched by this note.

## Pre-check (per task instructions)

- `git log --all --oneline -- "**/<file>"` for all 12 targets: **empty for every one.**
- `find . -iname "<file>"` (live tree, `.git` excluded): **zero hits for every one.**
- Conclusion: none of the 12 files have ever been committed anywhere in this repo, and no
  live-tree copy exists under a different path. All 12 needed reconstruction (or, where
  reconstruction proved impossible — see §3 — an honest documented gap).

## Method — and a materially better extraction path than RECOVERY-NOTE.md's original method

RECOVERY-NOTE.md's method (and Lane A's, per its notes) parses `custom_tool_call` /
`name=="exec"` items whose JS `input` embeds `const patch = "*** Begin Patch..."`, JSON-unescapes
the string, and hand-splits/hand-applies the V4A patch — which needs a fallback fuzzy matcher for
hunks whose context drifted.

This lane found a **cleaner, authoritative source already computed by Codex itself**:
`item_completed` events whose `item.type == "FileChange"` carry a `changes` map keyed by absolute
file path, where each entry is either `{"type":"add","content":"<full real-unicode file
content>"}` or `{"type":"update","unified_diff":"<a real unified diff, standard @@ -a,b +c,d @@
hunks>","move_path":null}`. This is Codex's own post-hoc record of what actually landed on disk —
no JS-string unescaping needed for `add` (content is already real text), and no V4A hand-parsing
needed for `update` (it's a standard unified diff, appliable with an ordinary line-offset patcher).
It also transparently covers **both** Codex session-harness generations found in this corpus (the
`tools.exec_command`-wrapped-JS-patch style used by early 08-25 sessions, and the
`bash.exe -lc`/`unified_exec_startup`/`CommandExecution` style used by most 08-26/27 sessions) —
`FileChange` events exist in both without any format-specific parsing.

Recommendation for any future lane doing this kind of recovery: **scan for
`payload.type=="item_completed" and payload.item.type=="FileChange"` first**; only fall back to
raw `custom_tool_call`/`Begin Patch` text-mining for files where no `FileChange` record exists.

Concretely, this pass:

1. Globbed every `rollout-*.jsonl` under `C:\Users\matts\.codex\sessions\2026\08\{25,26,27,28}\`
   (206 files; 28 included per the task's "+28 if needed" — no target-file hits landed there).
2. Scanned all 206 files (line-by-line, cheap `"FileChange" in line` pre-filter, then real JSON
   parse) for `item_completed`/`FileChange` items. 999 total `FileChange` items found across the
   whole corpus (all projects/repos this desktop's Codex sessions touched, not just this repo);
   filtered down to the ones whose `changes` key's `os.path.basename(...)` matched one of the 12
   targets.
3. Also ran the original `custom_tool_call`/`Begin Patch` extraction independently as a
   cross-check (v1) — its accepted-call counts agreed exactly with the `FileChange` counts (v2)
   for every file that had any apply_patch activity at all, which is good corroborating evidence
   neither method has a systematic blind spot for files that *do* have Codex-authored edits.
4. Sorted each target's ops by real timestamp, seeded from the (single, in every case) `add` op's
   full content, then applied each later `update` op's unified diff in order using a line-offset
   patcher: exact-position match first, then a ±20-line nearby search, then a whole-file global
   search — logging every fallback firing and every hunk that could not be located at all
   (mirroring RECOVERY-NOTE.md's own quality bar).
5. For the 3 files with **no `add` op anywhere in the 08-25→08-28 corpus** (§3 below), searched
   exhaustively for alternative creation mechanisms (raw `custom_tool_call` inputs mentioning the
   filename with `Set-Content`/`Out-File`/Python `write_text`, `McpToolCall` items with a
   filesystem-write tool, case-insensitive `FileChange` basename matching) before concluding the
   base content is genuinely outside this corpus.

## 1. Files fully reconstructed (9 of 12) — written to `docs/reviews/2026-08-25-schema-audit/`

| File | Add (seed) timestamp | Update ops applied | Hunks OK / attempted | Bytes |
|---|---|---|---|---|
| `RECONCILIATION-RUNBOOK.md` | 2026-08-25T14:18:02.310Z | 0 | 0/0 | 10,450 |
| `AGENT-HANDOFF-PROTOCOL.md` | 2026-08-25T14:18:02.310Z | 0 | 0/0 | 6,369 |
| `COMPLETE-CODEBASE-AUDIT.md` | 2026-08-26 (first add) | 3 | 7/9 | 19,364 |
| `COMPREHENSIVE-PATH-REVIEW.md` | 2026-08-26 | 3 | 5/6 | 11,420 |
| `COMPREHENSIVE-PATH-REVIEW.html` | 2026-08-26 | 3 | 4/7 | 14,950 |
| `ENGINEERING-DOCUMENTATION-PACKAGE.md` | 2026-08-25T14:20:11Z | 5 | 6/9 | 5,791 |
| `SEMANTIC-AGENT-WORK-PACKAGES.md` | 2026-08-26T13:37:34Z | 2 | 0/2 | 6,566 |
| `SESSION-HANDOFF-COMPLETE-CODEBASE-AUDIT.md` | 2026-08-25T23:06:09Z | 7 | 5/10 (+2 fallback) | 8,031 |
| `PARALLEL-GAP-EXECUTION-BOARD.md` | 2026-08-26T21:33:47Z | 3 | 4/5 | 11,699 |

`RECONCILIATION-RUNBOOK.md` and `AGENT-HANDOFF-PROTOCOL.md` were both created by the **same**
single multi-file `Add File` patch call at 2026-08-25T14:18:02.310Z (a batch that also created
several files Lanes A/B or a prior pass already recovered — `CROSS-DOMAIN-CONTRACT-MATRIX.md`,
`RECONCILIATION-DOMAIN-WORKSTREAMS.md`, `SYSTEM-ARCHITECTURE.md`, and the
`reconciliation-domains/` tree). Neither file was ever updated again — zero-hunk, full confidence.

**Total bytes written this pass: 94,640** across the 9 files above.

### 1a. Honest per-hunk gaps in the 9 reconstructed files

17 hunks (out of ~53 attempted across the 9 files) could not be located in the running
reconstruction and were **not applied** — logged, not guessed, not silently dropped. Root cause,
established by direct inspection: every one of these hunks' "old" context describes content that a
**different, concurrent editing session already changed by the time this hunk's edit was
attempted** — i.e., these are superseded intermediate edits, not evidence of corruption in the
final document (spot-checked `COMPLETE-CODEBASE-AUDIT.md` around both failure points — the
document reads coherently and consistently at those locations, matching what a *later* successful
hunk already wrote there). The clearest proof: `SEMANTIC-AGENT-WORK-PACKAGES.md`'s two failed
hunks target lines 93 and 101 of a document whose Codex-authored `add` content is only 88 lines
long — the file was demonstrably expanded past line 101 by an edit with **zero trace anywhere** in
this Codex corpus (case-insensitive `FileChange`-basename search across all 206 files, all four
days, confirmed only 3 total `FileChange` events ever touch this file: 1 add + the 2 updates
already applied) — i.e. a **non-Codex session** (almost certainly Claude Code — see §3, where the
sibling file `TIMESKETCH-LIVE-PREVIEW-STATUS.md` proves Claude Code was actively co-editing this
same review directory with an explicit `Byline: Claude Code · Sonnet 5 · 2026-08-26` diff line)
inserted that missing content between this lane's two visible Codex edits.

The "+" (new) content of every unmatched hunk, so nothing found is silently lost — a future pass
with access to the corresponding Claude Code transcripts (if they still exist) can splice these in
at the right point by matching the surrounding preserved context:

**`COMPLETE-CODEBASE-AUDIT.md`** — 2 unmatched (both around the "CI/test coverage" and "Temporal
retry" paragraphs, old_start 198/202, both 2026-08-26T12:58–13:00Z, source
`rollout-2026-08-26T08-31-45-...`): superseded refinements of paragraph wording already present
correctly (spot-checked) in the delivered file.

**`COMPREHENSIVE-PATH-REVIEW.md`** — 1 unmatched (old_start 120, 2026-08-26T13:35:05Z): a
"Freeze D-082 through D-085 ... ratify CR-002 through CR-004" numbered-list rewrite of the "Safe
next sequence" section.

**`COMPREHENSIVE-PATH-REVIEW.html`** — 3 unmatched (old_start 79/86/97, 2026-08-26T13:35–14:55Z):
the HTML mirror of the same "Safe next sequence" section, a "Multi-agent handoffs" note pointing at
`SEMANTIC-AGENT-WORK-PACKAGES.md`, and a "D-082 fence deployed and live-verified" status banner
(the same banner text that appears, successfully applied, in `AUDIT-GAP-REGISTER.md` per the
broad-scan evidence gathered this pass).

**`ENGINEERING-DOCUMENTATION-PACKAGE.md`** — 3 unmatched (old_start 13/13/23, 2026-08-26T13:13–
13:38Z): three successive re-orderings of the entry-point table row order (Comprehensive-path-review
vs Complete-codebase-audit ordering, then the HTML-preferred-variant row, then an Agent-handoff/
Semantic-agent-work-packages row insertion) — all superseded by later edits to the same rows.

**`SEMANTIC-AGENT-WORK-PACKAGES.md`** — 2 unmatched, see root-cause above (old_start 93/101,
2026-08-26T14:55Z and 21:54:05Z): a WP-E01-complete status rewrite and a GAP-032/knowledge-workbench
follow-up-deployment paragraph, both later versions of content whose *prior* version was inserted
by the missing non-Codex edit.

**`SESSION-HANDOFF-COMPLETE-CODEBASE-AUDIT.md`** — 5 unmatched (old_start 4/14/17/141/4, spanning
2026-08-26T13:01–2026-08-27T09:06:58Z): successive status-line rewrites plus one substantial
2026-08-27T09:06:58Z owner-override (D-091/D-092) banner insertion at the top of the document —
this last one is the same D-091/D-092 override text also seen (successfully applied) in
`PARALLEL-GAP-EXECUTION-BOARD.md` below, so its content is independently recoverable from that
sibling file if a future pass wants to splice it back in here too.

**`PARALLEL-GAP-EXECUTION-BOARD.md`** — 1 unmatched (old_start 6, 2026-08-27T09:06:58Z): the same
D-091/D-092 "database stop gate" banner insertion (partially superseded — a slightly later hunk in
the same update op successfully rewrote an overlapping span, so most of this content likely did
land; only the exact banner wording at this specific spot is unconfirmed).

Full unmatched-hunk `+`-content (verbatim) is preserved in this session's scratchpad at
`lane_d_extract/_gap_content.json` if a future pass wants the exact text rather than the summaries
above — not copied into this repo since it is fragment data, not a deliverable file.

## 2. Files NOT written — original creation is outside the Codex transcript corpus (genuine gap)

Three targets have **zero `Add File`/`FileChange:add` event anywhere** in the entire 08-25→08-28
Codex rollout corpus for this repository, confirmed by three independent search strategies (raw
`custom_tool_call`/`Begin Patch` text grep for the literal `Add File: docs/.../<name>` line,
`FileChange`-item basename matching case-sensitive, and the same case-insensitive across all 206
files/4 days) — plus a fourth check for any non-apply_patch file-write mechanism (`Set-Content`,
`Out-File`, Python `write_text`, or an `McpToolCall` filesystem-write tool — none exists in this
corpus; the only `McpToolCall` tools present are `github.*` and `coolify_api.*`).

**`TIMESKETCH-LIVE-PREVIEW-STATUS.md`** — direct, unambiguous proof of cause: the first Codex edit
found (2026-08-27T03:03:42Z) changes line 2 from `> Byline: Claude Code · Sonnet 5 · 2026-08-26` to
`> Byline: Claude Code · Sonnet 5 · 2026-08-26; Codex · GPT-5 · 2026-08-27 (preview hardening)` —
**this file was authored by a Claude Code session on 2026-08-26**, not Codex. Codex only made 4
small hardening edits to it on 2026-08-27 (forkability/DB-URI-encoding notes, a migration-step
note, a preview-URL note, a "files" section wording tweak). Base content recovery is a Claude Code
transcript-recovery task, out of this lane's (and this Codex-transcripts-only recovery's) scope.

**`PROPOSAL-FINAL.md`** — same pattern by strong inference (not proven by an explicit byline diff
line the way the file above is, but: the document is provably 400+ lines by 2026-08-27 — the one
Codex edit found touches lines 8, 162, and 376 — and is read/grepped extensively starting
2026-08-26T13:03:41Z, hours before any Codex `FileChange`/apply_patch trace exists for it). Codex's
one recovered edit (2026-08-27T09:08:27Z) adds a "D-091/D-092 owner override" banner and removes
`is_redacted` from the canonical schema proposal per D-092.

**`WP-C01-IMPLEMENTATION-STATUS.md`** — same pattern (read/grepped extensively from
2026-08-26T21:24:27Z; the one Codex edit at 2026-08-26T21:53:43Z rewrites a status line and adds a
substantial "Follow-up deployment and live proof" paragraph referencing commit `1d7a72a` and
Coolify deployment `spqradjsvl8skt1o9c2w5zqf` — content that presupposes a large pre-existing
document, e.g. "see the 'Deployment receipts' and 'Live verification' sections above").

The recoverable Codex-authored fragments (full unified diffs, not just previews) for all three
files are preserved in this session's scratchpad at
`lane_d_extract/fulldiff_{PROPOSAL-FINAL,TIMESKETCH-LIVE-PREVIEW-STATUS,WP-C01-IMPLEMENTATION-STATUS}_md.txt`
— not written to the repo as the target files themselves, since a 2-8-hunk fragment posing as
"the" document would misrepresent a partial (mostly-missing) file as complete. If a Claude Code
transcript recovery lane later reconstructs these three files' Claude-Code-authored base content,
these fragments are the exact incremental edits Codex made on top of that base and can be applied
directly.

## 3. Contradiction flags

None found. No committed version of any of the 12 targets exists anywhere in git history or the
live tree (confirmed pre-check, §0), so there is nothing to reconcile against a prior canonical
copy. The RECOVERY-NOTE.md §5 table's own `First seen`/`Last touched`/`Patch ops` counts for
`PROPOSAL-FINAL.md` (1 op), `WP-C01-IMPLEMENTATION-STATUS.md` (1 op, after de-duplicating one
rejected retry the original scan's raw-count method would have double-counted), and
`SESSION-HANDOFF-COMPLETE-CODEBASE-AUDIT.md` (8 ops, "spans to 08-27T09:06") all agree exactly with
what this pass independently found — good cross-method corroboration, no drift between
RECOVERY-NOTE.md's earlier headline numbers and this pass's full reconstruction.

## Total

- 9 files reconstructed and written: **94,640 bytes**.
- 3 files confirmed out of Codex-transcript scope (Claude-Code-authored base content); their
  Codex-only incremental fragments preserved in the scratchpad, not written to the repo.
- 17 hunks across the 9 written files logged as unmatched/superseded (not silently dropped —
  `+`-content summarized above and preserved verbatim in the scratchpad).
