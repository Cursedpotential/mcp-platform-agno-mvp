# R11 Phase-0 Owner-Ruling Synchronization — Pre-Mortem and Validation

> _Byline: Codex · GPT-5 · 2026-08-16_
>
> **Scope:** Documentation and framework-neutral contract tests only. No database, service,
> corpus, migration, deployment, or production-agent change is authorized or performed.

## Pre-mortem

Assume the accepted S1–S6 package failed six months later.

| Failure mode | Why it matters | Prevention in this task | Required proof |
|---|---|---|---|
| “Shared Context” is interpreted as shared unscoped agent state | Ignorant and hindsight beliefs bleed together silently | Separate shared promoted knowledge from walk-bound experiential beliefs; require Matter/walk/horizon/revision predicates on every stateful surface | Two walks in one Context retrieve only their own beliefs; cache/profile/consolidation paths pass the same gate |
| A sealed historical snapshot becomes fallback memory | A known-contaminated experience influences the clean rewalk | Snapshot is immutable, read-only, non-resumable, and active-retrieval-ineligible; repair creates a new `rewalk_of` identity | Reconstruct the old state exactly while proving zero old-state results in the new walk |
| Reconciliation overwrites the earlier experience | The evolution-of-experience deliverable disappears | Preserve manifest/state/trace hashes and append a linked rewalk rather than resume or mutate | Before/after diff attributes input, policy, and reasoning changes separately |
| A midpoint estimate is treated as realized fact | Knowledge appears earlier than a person can be shown to have learned it | Preserve interval and proposal separately; require reviewer, evidence/rationale, and append-only decision before visibility | Unreviewed proposal appears in zero as-lived candidate pools; later approval is attributable and replayable |
| Duplicate exports inflate corroboration | One assertion looks independently confirmed five times | Count custody/content source families and report raw hit count separately | Five derivative hits yield independent count one until provenance review establishes a second origin |
| Documentation status accidentally authorizes infrastructure | The parked deployment or real corpus is touched before live gates | Repeat implementation-authority prohibition and every R9 hold in contracts, canon, goals, packet, and handoff | Drift scan finds no activation claim; git diff contains no migration/deploy/schema/service edits |

## Validation evidence

- Focused framework-neutral suite: **18 passed**.
- Focused Ruff check and format check: **PASS**.
- Full repository unit suite: **768 passed / 24 skipped**.
- Full Ruff, format, and mypy gates: **PASS**.
- Markdown links across 14 task docs, JSON parse, decision/status drift, activation-hold anchors,
  and task-scoped `git diff --check`: **PASS**.
- Live adapter proof: **NOT ATTEMPTED / remains blocked**.
- R9 holds: **PRESERVED**.
- Workspace note: an unrelated concurrent edit disabled Workbench API authentication in
  `workbench/api/main.py`; it is excluded from this task and preserved untouched for the owner.

## Residual risks

- Spectron-compatible cache/profile/consolidation behavior needs a live disposable shared-Context
  isolation test; the logical contract alone cannot prove it.
- Exact physical snapshot, walk, and realization-review schemas remain intentionally unresolved.
- HITL guidance and reviewer agreement require labeled cases before midpoint use can be calibrated.
