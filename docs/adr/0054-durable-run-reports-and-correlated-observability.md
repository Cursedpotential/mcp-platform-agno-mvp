# ADR-0054 — Durable run reports and correlated observability

> _Byline: Codex · GPT-5 · 2026-08-13_

- **Status:** Accepted (owner ruling 2026-08-13)
- **Decision:** D-059
- **Relates:** ADR-0047 (audit everything), ADR-0053 (AI-chat ingestion)

## Context

Aggregate output such as `654 passed, 25 skipped` does not answer which 25,
why each was skipped, what ran, what was produced, or what can be approved,
overridden, or retried. Logs are not durable enough, and a hosted observability
product cannot be the only copy of a court-facing operational record.

Agno 2.8.7 already provides OpenTelemetry tracing for agents, teams, workflows,
model calls, and tools. The platform also has `ops.workflow_run`,
`ops.workflow_run_stage`, Workbench run controls, and ADR-0047's append-only
hash-chained `ops.audit_ledger`. The missing design was how they relate.

## Decision

1. **Every workflow and automated test run emits a versioned post-run report.**
   It itemizes every unit/stage with status, explicit reason code/detail,
   duration, output summary, errors, warnings, and remediation. Aggregate counts
   are indexes, never substitutes for the itemized list.
2. **Postgres is authoritative.** Terminal workflow stages require a structured
   reason. `ops.workflow_run_review_action` is append-only and stores
   acknowledgements, approvals, overrides, gate actions, aborts, and retries.
   Original outcomes are never rewritten.
3. **ADR-0047 binds review actions into the global chain.** Detail stays in its
   home table; `ops.audit_ledger` stores its reference and payload hash, not raw
   case content.
4. **Langfuse is the preferred optional diagnostic UI, not the authority.** Agno
   OpenTelemetry spans are mirrored only when explicitly enabled. The same trace
   ID is stored on the durable run and exposed as a Workbench deep link. A
   Langfuse outage cannot prevent the run or report.
5. **HITL happens in Workbench.** The report supplies drill-down and
   reason-required Acknowledge, Approve, and Record Override actions. Continue,
   Abort, and Retry remain explicit execution controls and are also recorded.
6. **Case-content safety is fail-closed.** Langfuse export defaults off and
   requires `LANGFUSE_ENABLED=true` plus credentials. Self-hosting is preferred
   for case-bearing traces. No trace backend is evidence custody or audit truth.
7. **Pytest uses the same reporting shape.** Every invocation writes ignored
   JSON and self-contained interactive HTML under `build/test-reports/`, with
   named pass/skip/fail rows, reasons, remediation, and source links.

## Report contract (v1.0)

Top-level keys are `_comment`, `schema_version`, `pass`, `metadata`, `input`,
`output`, `errors`, `warnings`, `handoff`, and `data`. Report status is one of
`COMPLETE`, `PARTIAL`, or `BLOCKED`; per-stage status keeps native vocabulary.

## Consequences

- Migration `0025` must land before the report/review endpoints are used.
- Existing terminal rows receive honest `legacy_*` reasons; provenance is not
  invented.
- Langfuse retention, backup, access, and masking need deployment policy before
  enabling case-bearing production traffic.
- Evidence ingestion and pytest are the first adopters. Other workflows must
  adopt the same contract; bespoke summary-only logging is no longer acceptable.

## Alternatives rejected

- **Langfuse only:** telemetry can be unavailable, externally retained, or
  deleted and is not platform audit authority.
- **Post-run log file only:** not centrally queryable or interactive and cannot
  support append-only decisions.
- **Mutating an outcome after override:** destroys the original fact; corrections
  must be new action rows.
- **Counts without itemization:** rejected explicitly by the owner requirement.
