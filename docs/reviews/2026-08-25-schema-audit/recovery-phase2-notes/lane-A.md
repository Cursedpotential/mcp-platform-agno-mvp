# Records recovery — Phase 2, Lane A

> _Byline: Claude Code · Sonnet (recovery lane A) · 2026-09-02_

Scope: reconstruct the 10 `reconciliation-domains/` files listed in
[`../RECOVERY-NOTE.md`](../RECOVERY-NOTE.md) §5 as owned by Lane A —
`README.md`, `DOMAIN-GUIDE-TEMPLATE.md`, `R00`–`R07`. Lane B (concurrent, same
scratchpad root) owns `R08`–`R14`; see its own
[`lane-B.md`](lane-B.md) — not touched by this note.

## Pre-check (per task instructions)

- `git log --all -- docs/reviews/2026-08-25-schema-audit/reconciliation-domains/<file>` —
  **empty for every one of the 10 target files** (confirmed with an unscoped
  `git log --all --diff-filter=A --name-only` grep for `reconciliation-domains` across
  the whole history too — zero hits).
- Live-tree filename search (`find . -iname reconciliation-domains`) — directory did not
  exist before this recovery.
- Conclusion: none of the 10 files have ever been committed. All 10 needed reconstruction.

## Method (mechanical re-derivation of the RECOVERY-NOTE.md method, this pass)

1. Globbed every `rollout-*.jsonl` under `C:\Users\matts\.codex\sessions\2026\08\{25,26,27,28}\`
   (206 files found; 08-28 included per the task's "check 28 too" instruction, but no
   qualifying hits landed there for these 10 targets — last real touch was 2026-08-26).
2. Pass 1 (cheap pre-filter + parse): for every line containing the literal `Begin Patch`
   plus one of the 10 files' distinguishing basename/path fragment, parsed the JSON,
   kept `response_item` entries where `payload.type == "custom_tool_call"` and
   `payload.name == "exec"`. **First filter attempt matched bare `README` and produced
   dozens of false positives** (any unrelated `README.md` patch anywhere in the repo,
   through 2026-08-30) — corrected to match the qualified fragment
   `reconciliation-domains/README.md` before proceeding. 39 real candidates after the fix
   (down from 85 before).
3. Pass 2: for each candidate's `call_id`, located its `custom_tool_call_output` in the
   same rollout file and classified success/failure from the output text (`"Script
   completed"` vs `"Script failed"` / `"...verification failed"`). Rejected-attempt
   candidates were dropped (4 of the 39 were rejected retries, correctly excluded).
4. Decoded each accepted call's `input` (a JS snippet `const patch = "...*** Begin
   Patch...*** End Patch";  text(await tools.apply_patch(patch))`) via JSON-string
   unescaping of the quoted literal, then split the decoded V4A patch into per-file
   `Add File` / `Update File` sections by `*** (Add|Update|Delete) File: <path>` markers.
   **Paths inside the patches are absolute** (`E:/AI_Workspace/Projects/the-platform-
   workspace/Agno-MCP-Platform/docs/reviews/...`), not repo-relative — matched by suffix
   against the 10 target paths after normalizing backslashes.
5. Grouped the resulting per-file sections (53 total across the 10 files — see the
   per-file table below; every count matches RECOVERY-NOTE.md's independently-derived
   §5 tally exactly), sorted by real ISO timestamp, and de-duplicated by exact body-text
   match (protects against the same edit landing twice from concurrent/forked sessions —
   RECOVERY-NOTE.md's known hazard). **Zero duplicate bodies found** — all 53 ops were
   distinct edits, so no dedup collapsing was actually needed for these 10 files.
6. Replayed in order: `Add File` seeds the file (each body line's leading `+` stripped);
   `Update File` bodies split into `@@`-delimited hunks, each hunk's context/`-`/`+`
   lines split into a search block (context+removed) and replacement block
   (context+added), located as an exact contiguous match in the running reconstruction.
   Exact match first; on failure, a whitespace-flexible match (compare `rstrip()`ed
   lines); on failure, a prefix-anchor match (unique single non-blank line from the
   search block located and used as the splice point) — matching RECOVERY-NOTE.md's
   documented fallback ladder, with every fallback firing logged.

## Result: 53/53 hunks applied, 1 flagged fallback (manually corrected)

Of 53 total ops (10 `Add File` + 43 `Update File` hunks), only **one** required a
fallback match, and it produced a real defect that needed manual correction (not just a
confidence flag):

- **R01-pg-backbone-cdc-receipts.md**, hunk from the `2026-08-26T13:42:12.885Z` Update
  (`rollout-2026-08-26T08-31-45-...:1138`): its stored search block (two lines ending
  "...Weaviate, Neo4j, and Surreal are" / "rebuildable consumers under D-080; none may
  become an alternate authority.") no longer matched exactly, because two *earlier*
  Update ops on the same file (`12:20:38.474Z` and `12:58:57.625Z`) had already touched
  neighboring text in that paragraph by the time this hunk replayed. The engine fell
  back to a prefix-anchor match on one line only, which spliced the replacement in
  without removing the now-stale first line of the old search block — producing a
  duplicated/interleaved sentence and a missing blank line before `## Scope`.
  **Manually corrected** by reading the hunk's own removed/added text directly from
  `target_ops.json` and rejoining the paragraph to the version the hunk's own `+` lines
  specify (ends "...Weaviate, Neo4j, Surreal, and the maintained Timesketch fork/
  OpenSearch are rebuildable consumers under D-080/D-084; none may become an alternate
  authority.") plus restoring the blank line before `## Scope`. Verified by rereading
  the full file afterward — no other duplication artifacts found (confirmed with an
  automated consecutive-line-common-prefix scan across all 10 reconstructed files; the
  only other hits were legitimate similar-looking Markdown table rows, not corruption).

No other gaps of any kind: zero "could not locate hunk" misses, zero "empty search
(pure add w/ no context)" misses, zero "Update File before any Add File" ordering
errors. This is a full, high-confidence recovery for all 10 files.

## Per-file status

| File | Status | Ops (Add+Update) | Bytes | Source rollouts | Gaps |
|---|---|---|---|---|---|
| `README.md` | recovered full | 2 (1+1) | 3,277 | `...08-52-26-01a038fa...` (Add), `...08-57-06-01a03e25...` (Update) | none |
| `DOMAIN-GUIDE-TEMPLATE.md` | recovered full | 1 (1+0) | 2,414 | `...08-52-26-01a038fa...` (Add) | none |
| `R00-canon-contract-freeze.md` | recovered full | 8 (1+7) | 19,261 | `...09-08-50-01a03909...`, `...07-45-09-01a03de3...`, `...08-56-59-01a03e25...` (×2), `...08-31-45-01a03e0e...` (×2) | none |
| `R01-pg-backbone-cdc-receipts.md` | **recovered full + 1 manual fix** | 6 (1+5) | 16,669 | `...09-08-50-01a03909...`, `...07-45-09-01a03de3...`, `...08-56-59-01a03e25...`, `...08-31-45-01a03e0e...` (×3) | 1 fallback-collision hunk, manually corrected (see above) |
| `R02-context-ingest-parser-boundary.md` | recovered full | 6 (1+5) | 21,832 | `...09-08-50-01a03909...`, `...07-45-09-01a03de3...`, `...08-56-59-01a03e25...`, `...09-35-51-01a03e48...`, `...08-31-45-01a03e0e...` (×2) | none |
| `R03-normalization-messages-clocks.md` | recovered full | 6 (1+5) | 18,345 | `...09-08-50-01a03909...`, `...07-45-09-01a03de3...` (×2), `...08-56-59-01a03e25...`, `...08-31-45-01a03e0e...` (×2) | none |
| `R04-hashing-custody-promotion.md` | recovered full | 5 (1+4) | 21,144 | `...09-08-50-01a03909...`, `...07-45-09-01a03de3...` (×2), `...08-56-59-01a03e25...`, `...08-31-45-01a03e0e...` | none |
| `R05-weaviate-search.md` | recovered full | 6 (1+5) | 16,441 | `...09-09-34-01a0390a...` (×2), `...07-45-13-01a03de3...` (×3), `...08-56-59-01a03e25...` | none |
| `R06-semantica-neo4j.md` | recovered full | 6 (1+5) | 16,632 | `...09-09-34-01a0390a...` (×2), `...07-45-13-01a03de3...` (×3), `...08-56-59-01a03e25...` | none |
| `R07-governed-facts-realizations.md` | recovered full | 7 (1+6) | 23,085 | `...09-09-34-01a0390a...`, `...07-45-13-01a03de3...` (×2), `...08-56-59-01a03e25...`, `...08-31-45-01a03e0e...` (×2), `...09-35-51-01a03e48...` | none |

**Total: 159,100 bytes across 10 files, all 10 recovered full.**

Every op count above matches RECOVERY-NOTE.md's independently-produced §5 table
(`README.md`: 2, `DOMAIN-GUIDE-TEMPLATE.md`: 1, `R00`: 8, `R01`: 6, `R02`: 6, `R03`: 6,
`R04`: 5, `R05`: 6, `R06`: 6, `R07`: 7) exactly — cross-validating both this pass's
extraction and the original note's survey.

## Contradictions against committed decisions

None found. Content read (D-069 through D-085 references, the H1/H2/H3 hash-chain
description, the Weaviate/Neo4j/Surreal projection split, the Timesketch fork curation
model) is internally consistent with the currently committed `docs/DECISION_LOG.md` and
`AGENTS.md` canon as of 2026-09-02 — no flags to raise.

## What was not touched

- `RECOVERY-NOTE.md` — read only, not edited.
- Lane B's files (`R08`–`R14`) and `lane-B.md` — not read in detail, not edited.
- No `git add` / `git commit` / `git push` performed, per task instructions.
