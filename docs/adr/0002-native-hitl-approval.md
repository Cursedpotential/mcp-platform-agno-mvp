# ADR-0002: Native Agno HITL (requires_confirmation + continue_run); approval_request is the audit record
- Status: **Superseded in part (2026-06-12)** — the principle (native HITL, no bespoke
  state machine) stands and is now FULLY native: agno 2.6.13's `@approval` decorator
  persists the pending record itself (`agno.run.approval`), the auto-mounted
  `/approvals` router records decisions, and run-continue is gated by
  `require_approval_resolved`. The custom `approval_request` table + `/v1/approval-requests`
  routes this ADR described as the audit record are REMOVED (legacy tables kept in
  `sql/0002_schema.sql` for provenance only). See docs/DEBT.md "Agno-native audit".
- Date: 2026-06-01

## Context
Human approval is a first-class state: any write to ingestion, normalization, evidence, config, or DB
must pause for an explicit, recorded decision. The v1 repo implemented this as a bespoke REST approval
state machine. Agno provides a native confirmation mechanism, and the reference `agents_factory.py`
already uses it (`apply_db_modification`, `trash_cloud_file` are `@tool(requires_confirmation=True)`).

## Decision
Use Agno's **native confirmation pause** as the primary HITL mechanism: a sensitive tool marked
`requires_confirmation=True` pauses the run; `continue_run(run_id, updated_tools=...)` approves (or
rejects with a `confirmation_note`). The `approval_request` table is the **audit/display record**, not
a parallel approval path — it is keyed by **`run_id`** so a decision (API or Review Panel) resumes the
*same* paused run.

## Consequences
- `agent_run`/`approval_request` schema must carry `run_id` + paused-tool refs.
- The Review Panel (Phase 13) must resolve via `continue_run`, never a second mechanism.
- The Review Gatekeeper writes only approval/audit tables.

## Alternatives considered
- Bespoke REST state machine (v1) — rejected: duplicates a native feature and risks "recorded but never
  resumed" approvals.
