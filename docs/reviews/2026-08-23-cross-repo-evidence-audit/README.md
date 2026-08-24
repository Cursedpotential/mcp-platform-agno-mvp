# Cross-repo evidence audit — 2026-08-23

> _Byline: Claude Code · Opus 5 · 2026-08-23_
>
> Moved here from the throwaway worktree `claude/funny-benz-34106c` (`.full-review/`) so it
> survives worktree cleanup. Nothing here is authoritative — `PROJECT_CANON.md` and the ADRs win
> on any conflict. This is evidence gathered, not decisions made.

## What this was

Owner supplied two externally-produced gap analyses plus a reference corpus, and asked for a deep
audit of **document handling, search, and evidence bundling** across `Agno-MCP-Platform`,
`Legal-Workspace`, and `vendored/sbv`. Every claim in both documents was then verified against code
on disk.

## The four findings that mattered

1. **Doc drift is the primary defect generator here.** `docs/DEBT.md` carried a stale claim that
   `evals/cases.py` was empty (it has 145 lines, 8 cases). **Both** independent gap analyses
   inherited that error without opening the file. Separately, all five of `sql/0026`–`sql/0030`
   said `NOT APPLIED` when four of them were already live — which caused three sessions to treat
   finished work as a pending decision.
2. **A live correctness defect: MCL 722.23 factors (j) and (k) had transposed names** in
   `server/analysis/config/behavioral_patterns.json` — domestic violence and
   relationship-facilitation printed backwards wherever the label was rendered. Fixed, with a
   contract test (`tests/test_mcl_factor_taxonomy.py`) because `patterns.py` validates letters
   only and structurally cannot catch a name/description swap.
3. **Evidence bundling does not exist** in any of the three repos — no EDRM load files, no exhibit
   assembly, no production set. `analysis.evidence_item.exhibit_number` is a live column with zero
   readers or writers.
4. **Message evidence can land with no custody hash** on the default path, by two independent
   routes. Owner ruled 2026-08-23: mandatory at capture, with hashing extracted into a callable
   process first.

## Reading order

| File | What it is |
|---|---|
| `ISSUES-AND-TODO.md` | **Start here.** 55 verified issues + sequenced remediation plan |
| `CONSOLIDATED-CLAIM-VERIFICATION.md` | Every claim in both supplied documents, with a verdict |
| `00-scope.md` | What was reviewed and how |

### Repo analysis (what the code actually does)

| File | Subject |
|---|---|
| `lane-1a-agno-ingest-trace.md` | Ingest paths — three parallel, only the flattest is HTTP-reachable |
| `lane-1b-agno-evidence-custody.md` | Custody, hashing, search surfaces, bundling |
| `lane-1c-agno-docs-adr-deadweight.md` | Docs, ADRs, dead weight |
| `lane-1d-agno-sql-schema-audit.md` | All 30 migrations, table by table |
| `lane-2-legal-workspace.md` | Legal-Workspace — no document upload pipeline exists |
| `lane-3-sbv.md` | Vendored SBV fork |
| `lane-4-reference-corpus.md` | The supplied reference documents, normalised into requirements |
| `lane-5-cross-cutting-search.md` | Why cross-corpus search is impossible by construction |

### Claim verification (the fact-checking pass)

`verify-1` … `verify-13` each answer one question. Highlights:

- `verify-2-mcl-factor-inversion.md` — the (j)/(k) defect, confirmed against statute
- `verify-3-absence-claims.md` — proving things are genuinely *absent*, with search terms recorded
- `verify-6-sibling-findings.md` — parser precedence and the custody gating
- `verify-8-existing-rulings.md` — where decisions had already been made
- `verify-9-matter-mvp-decisions.md` — the Matter packet, mostly answered by code already

### Inputs

- `claims-src-gaps.md`, `claims-src-edisc-gap-analysis.md` — the two supplied documents, verbatim
- `sibling-session-59068f99/` — a parallel session's independent output, preserved for cross-check

## Caveats

- **Static audit.** No running service was probed; the live database was queried only at the end,
  read-only, to establish migration state.
- **Two different copies of SBV were examined** across the two sessions — a shallow clone of the
  standalone repo, and the vendored subtree. Divergence is the first hypothesis for any SBV
  disagreement between them.
- **Identifiers like `ISS-xxx` / `TODO-xxx` are local to these documents only.** They are not
  project-wide identifiers and should not be used to address the owner.
