# GAP-031 Implementation Status — strict item-level HITL adjudication

> _Byline: Claude Code · Sonnet 5 · 2026-08-26_
> Owning packet (isolated): `server/temporal/classification_workflow.py`, classification-workflow
> tests under `tests/`, this status document. No other files were touched.

## Source finding

`docs/reviews/2026-08-25-schema-audit/AUDIT-GAP-REGISTER.md` row 41 (GAP-031, High,
R07/R13/R14):

> The registered Temporal classification workflow accepts arbitrary signal text; only exact
> `abort` stops it. Any other value releases the gate and appends every `needs_review` item to
> the persistence payload without item-level adjudication
> (`server/temporal/classification_workflow.py:81-84,131-164`; registration
> `server/temporal/worker.py:61-69`). The staged persistence workflow rejects non-accepted gate
> outcomes (`docs/research/integration-audit-2026-08-24/composed/wf-persist-results.json:71-74`),
> so the composed path is fail-open at the signal boundary and cannot express valid partial
> adjudication.

Acceptance gate: "Signal contract is an exact normalized enum allowlist; each item records
decision ID, actor, decision, reason and source; only individually approved/corrected items
become accepted while untouched items remain pending; invalid, mixed, partial and
replayed-signal tests prove no unintended write and deterministic resume."

## What changed

### `server/temporal/classification_workflow.py` — full rewrite of the gate mechanism

- **Removed** the old free-text `gate_decision(self, decision: str)` signal entirely (not kept
  alongside the new one — leaving it reachable would have kept the fail-open hole live).
- **Added** an exact normalized enum allowlist at two levels:
  - Gate-level `action`: `_VALID_GATE_ACTIONS = {"abort", "submit_decisions", "close_batch"}`.
    Anything else is logged and dropped; nothing outside this exact set can release the gate.
  - Item-level `decision`: `_VALID_ITEM_DECISIONS = {"approve", "correct", "reject"}`; only
    `{"approve", "correct"}` (`_ACCEPTING_DECISIONS`) can ever place an item in the persist
    payload.
- **Added** `submit_review_decisions(self, submission: ReviewGateSubmission)` — the sole signal
  on the workflow now. `ReviewGateSubmission.decisions: list[ItemAdjudication]` carries, per
  item: `decision_id` (idempotency key), `item_key`, `actor`, `decision`, `reason`, `source`, and
  optional `corrected_fields`. Every field is validated; the handler never raises (a raising
  signal handler fails the whole workflow task per the existing `ChatTranscriptIngest` gate-test
  doctrine already in the repo) — invalid input is logged via `workflow.logger.warning` and
  dropped.
- **Added** `_apply_item_decision`: rejects (logged, no state change) an unknown `decision`
  enum value, any decision missing `decision_id`/`actor`/`reason`/`source`, and any `item_key`
  not present in the *current* gate's `needs_review` set. A decision whose `decision_id` matches
  an already-recorded decision for the same item is treated as an idempotent replay (no-op); a
  *different* `decision_id` for an already-decided item is rejected as a conflicting
  resubmission — the first applied decision always wins, it is never silently overwritten.
- **Added** `_resolve_gate()` — a pure function (no `temporalio.workflow` calls) that turns the
  accumulated per-item decisions into the persist payload: items with `approve`/`correct` are
  included (with `corrected_fields` merged in for `correct`, plus a `gate_outcome: "accepted"`
  marker and an `adjudication` block carrying the full decision record); `reject` and
  **untouched (still-pending)** items are excluded — never appended. This directly replaces the
  old `accepted = accepted + review` line that appended every `needs_review` item unconditionally.
- **Auto-close / explicit close:** the gate auto-closes once every item in the current
  `needs_review` set has a recorded decision (deterministic — a pure function of the applied
  signal history, no wall-clock). An explicit `close_batch` action lets a reviewer end the wait
  with items still pending (e.g. deferring the rest to a later review pass); those items are
  excluded from persistence and reported in `ClassificationBatchOutput.still_pending`.
  `abort` behavior (end the run at the gate) is preserved, now routed through the enum instead
  of ad-hoc string matching.
- **Extended `ClassificationBatchOutput`** with `rejected: int`, `still_pending: int`, and
  `adjudications: list[dict]` (the full per-item audit trail: `item_key`, `decision_id`,
  `actor`, `decision`, `reason`, `source` for every DECIDED item in the run). Existing fields
  (`status`, `batches_processed`, `accepted`, `needs_review`, `persisted`, `step_log`) are
  unchanged in name and position; the new fields were inserted before `step_log`, but the only
  constructor call in the codebase is the workflow's own no-arg `ClassificationBatchOutput()`,
  so this is not a positional-argument break for any known caller (grepped repo-wide).
- **`ClassificationBatchInput` is unchanged** (`batches`, `classifier_version`, `run_key`,
  `supervised`) — `scripts/run_classification_batch.py` constructs it by keyword and is
  unaffected.
- Added `pending_items()` query (item_keys in the current gate with no recorded decision) and
  kept the existing `status()` query returning the stage string, unchanged.
- The n8n-facing accepted-item payload now carries `gate_outcome: "accepted"` and an
  `adjudication` object per adjudicated item. The composed persist body
  (`docs/research/integration-audit-2026-08-24/composed/wf-persist-results.json`) already
  tolerates and ignores unknown JSON keys (its `Normalize + Validate Accepted Rows` Code node
  only reads named fields), so this is additive and non-breaking against the current n8n body
  as written — see Limitations for what that body does *not* yet do with the new fields.

### `tests/test_classification_workflow.py` — new file

Contract + state-machine tests, following the existing no-server, no-worker, direct-instantiation
pattern already used by `tests/test_temporal_skeleton.py` for `ChatTranscriptIngest` (the only
established convention for testing these Temporal workflow classes in this repo). Coverage:

1. **Registration contract**: `ClassificationBatchPipeline` is a real `@workflow.defn` named
   `"ClassificationBatchPipeline"`; `submit_review_decisions` is a registered signal;
   `status`/`pending_items` are registered queries; the old `gate_decision` signal is confirmed
   **gone** (not merely unused).
2. **Exact enum allowlist — gate action**: wrong-case, empty, and unknown action strings are
   rejected and never set `_gate_abort`/`_gate_closed`; `abort` and `close_batch` are exercised
   individually.
3. **Exact enum allowlist — item decision**: invalid decision value rejected; each of
   `decision_id`/`actor`/`reason`/`source` missing individually rejected (parametrized); unknown
   `item_key` rejected. All via direct state inspection (`wf._decisions == {}`), no exceptions
   raised.
4. **Provenance recording**: a valid `approve` records `decision_id`/`actor`/`decision`/`reason`/
   `source`; a valid `correct` additionally stores `corrected_fields` and the resolved payload
   reflects the correction.
5. **Only approved/corrected accepted**: `_resolve_gate()` on a batch with one of each outcome
   (approve, correct, reject, untouched) — asserts accepted set is exactly
   `{approve-item, correct-item}`, rejected count is 1, pending count is 1, and the untouched
   item never appears in the accepted payload. A second test confirms an entirely-undecided
   gate resolves to zero accepted / zero rejected / all pending.
6. **Replay determinism**: resubmitting the identical `(item_key, decision_id)` is a no-op
   (state unchanged, no duplicate application); a different `decision_id` for an already-decided
   item is rejected and the original decision is preserved.
7. **Mixed/partial submissions**: one signal call mixing valid, invalid-enum, unknown-item-key,
   and missing-field entries applies only the valid one; partial decisions do not auto-close the
   gate (`pending_items()` reflects the remainder); a fully-decided gate auto-closes.
8. **`_item_key` precedence**: `chunk_id` > `record_id` > `record_ref` > deterministic
   positional fallback.
9. **Payload round-trip**: every new/changed dataclass (`ClassificationBatchInput`,
   `ClassificationBatchOutput`, `ItemAdjudication`, `ReviewGateSubmission`,
   `ItemDecisionRecord`) round-trips through `temporalio`'s default `DataConverter`, mirroring
   the existing round-trip test in `test_temporal_skeleton.py`. This is the first place in the
   repo a `list[<custom dataclass>]` field (`ReviewGateSubmission.decisions`) is round-tripped —
   flagged explicitly below since it has no prior local precedent to lean on.
10. **Determinism import guard**: mirrors the existing `test_workflow_module_does_not_import_env_reading_modules`
    check from `test_temporal_skeleton.py`, applied to `classification_workflow`.

## Static reasoning for correctness (no tests were executed — see Verification required)

- **Fail-closed by construction**: every branch in `submit_review_decisions` /
  `_apply_item_decision` that doesn't match an exact allowlist member or passes a required-field
  check returns without mutating state. There is no `else: accept` branch anywhere in the
  decision path — the old bug was exactly that (anything not `"abort"` fell through to release
  the gate and blanket-append `review`).
- **No unintended persistence payload**: `_resolve_gate()` only ever builds `accepted_items` from
  `self._decisions[key]` entries whose `decision` is in `_ACCEPTING_DECISIONS`; an item with no
  entry in `self._decisions` (never decided) is skipped by the `if record is None: continue`
  guard — it cannot reach the persist call by any code path in `run()`, because `accepted` is
  reassigned to `accepted + adjudicated_accept` and `adjudicated_accept` is exactly
  `_resolve_gate()`'s first return value.
- **Deterministic resume**: the workflow holds all gate state in plain instance attributes
  (`_gate_items`, `_decisions`, `_corrections`) mutated only inside the signal handler; Temporal
  replays a workflow by re-delivering its exact recorded signal history in order, so replay
  reconstructs identical state. The idempotent-replay-by-`decision_id` and
  reject-on-conflicting-`decision_id` rules make the *application-level* semantics deterministic
  too, independent of whether a caller's signal call is retried at the transport layer.
- **Signal handlers never raise**: confirmed by inspection — every validation failure path ends
  in `workflow.logger.warning(...); return`, matching the documented constraint already noted in
  this repo's `ChatTranscriptIngest` gate tests ("A signal handler that raises fails the whole
  workflow task").
- **Determinism preserved**: no `datetime.now()`/`random`/env reads were introduced; the module
  still only imports `temporalio` + stdlib + the `n8n_activities` dataclasses inside
  `workflow.unsafe.imports_passed_through()`, matching the existing import-rule docstring.

## Breaking change — flagged, not silently absorbed

The old `gate_decision(str)` signal is **removed**, not kept as a compatibility shim. A shim
that accepted both the old free-text form and the new structured form was considered and
rejected: the register's own vulnerability is specifically that a broad string-accepting signal
routes to "release the gate," so any surviving free-text entry point reintroduces exactly the
fail-open hole GAP-031 requires closing. This is a genuine breaking change to the workflow's
public Signal API. Repo-wide grep found these references to the **old** contract that a
follow-up doc pass will need to update (none are in this packet's ownership, so they were not
touched):

- `docs/runbooks/N8N-PIPELINE-GOLIVE-RUNBOOK.md:111-112` — tells an operator to send
  `gate_decision` = `approve` from the Temporal UI. Needs updating to describe
  `submit_review_decisions` with a `ReviewGateSubmission` payload (action +
  per-item `ItemAdjudication`s).
- `docs/HANDOFF-2026-08-24-n8n-pipeline-golive.md`, `docs/CHANGE-ORDER.md`,
  `docs/plans/TEMPORAL-INTEGRATION-PLAN-2026-08-23.md`,
  `docs/reviews/2026-08-25-schema-audit/reconciliation-domains/R13-temporal-n8n-execution.md` —
  reference the classification workflow generally; none define the signal contract themselves
  but should be checked for stale assumptions.
- `docs/research/integration-audit-2026-08-24/composed/wf-persist-results.json` — this composed
  n8n body is **not** in this packet's ownership. It already tolerates the new `gate_outcome`/
  `adjudication` fields (extra JSON keys are ignored by its validator), so no immediate
  compatibility break there — but see Limitations: it does not yet *persist*
  `decision_id`/`actor`/`reason`/`source` anywhere, so today those fields reach n8n but are
  dropped before the SQL insert.
- No code caller besides the workflow itself and the new tests constructs
  `ReviewGateSubmission`/`ItemAdjudication` yet — no live signal-sending client exists to update
  in this pass (confirmed by repo-wide grep of `gate_decision`/`ClassificationBatchPipeline`
  usages; `scripts/run_classification_batch.py` only starts the workflow, it never signals it).

## Limitations / explicitly out of scope for this packet

- **Downstream persistence of adjudication provenance is not yet wired.** The Temporal workflow
  now sends `decision_id`/`actor`/`decision`/`reason`/`source` per accepted item to the
  `persist-results` n8n webhook inside `item["adjudication"]`, but the composed n8n body's SQL
  `INSERT INTO analysis.chunk_classification` (which this packet does not own — it lives in
  `docs/research/integration-audit-2026-08-24/composed/wf-persist-results.json` and whatever DDL
  eventually lands under `sql/`) has no columns for those fields today. The audit trail exists
  durably inside the Temporal workflow history and in `ClassificationBatchOutput.adjudications`
  for the run's lifetime, but is **not yet durable in Postgres**. Flagging this as a real
  dependency for whoever owns the persist n8n body / `analysis.chunk_classification` DDL —
  extending the table with `decision_id, actor, decision, reason, source, adjudicated_at` columns
  and passing them through the Code node is a natural follow-up, not done here since it is
  outside this packet's file ownership (composed n8n JSON, SQL migrations).
- **No client exists yet to actually send `submit_review_decisions` in production** (e.g. a
  Workbench review UI or a CLI). The runbook currently documents sending signals via the Temporal
  UI; a UI/CLI for constructing a `ReviewGateSubmission` with correctly-keyed `item_key`s (which
  requires reading `pending_items()` or the batch's `needs_review` items first) is not part of
  this packet.
- Per task instructions, **no lint, mypy, ruff format, tests, builds, or live/integration
  verification were run.** The reasoning above is static (code inspection only). In particular,
  the `list[ItemAdjudication]` field on `ReviewGateSubmission` is, by repo-wide grep, the first
  case in this codebase of a Temporal payload dataclass containing a `list[<custom dataclass>]`
  field round-tripped through `temporalio`'s default `DataConverter` — existing precedent here
  only covers `list[dict]` and scalar/`X | None` fields. This is expected to work (Temporal's SDK
  documents nested-dataclass support), but it has no local precedent and should be the first
  thing confirmed live.

## Required live verification handoff (for root / whoever runs tests+deploy)

1. `uv run pytest -q tests/test_classification_workflow.py` — confirm every case above actually
   passes, especially the payload round-trip parametrization (the `list[ItemAdjudication]` case
   flagged above is the highest-risk item).
2. `uv run ruff check server/temporal/classification_workflow.py tests/test_classification_workflow.py`,
   `uv run ruff format --check` (same paths), `uv run mypy server/temporal/classification_workflow.py`.
3. A live Temporal run (mirroring `scripts/run_classification_batch.py --supervised`) that
   actually reaches a `needs_review` batch, then exercises the acceptance gate's four required
   signal shapes against the running workflow via `temporal workflow signal`:
   - **invalid** — an action or decision value outside the allowlist; confirm the gate does not
     release and `status()`/`pending_items()` are unchanged.
   - **mixed** — one `submit_decisions` call with a valid decision alongside an invalid one;
     confirm only the valid one lands and the batch's persisted rows match exactly.
   - **partial** — decide some but not all `needs_review` items, then `close_batch`; confirm the
     persisted payload contains only the decided approve/correct items, and that the run's
     `still_pending` count and the undecided item_keys are visible in the output/history for
     follow-up.
   - **replayed** — resend an identical `submit_decisions` signal (same `decision_id`s) after the
     gate has already applied it; confirm no duplicate rows land in
     `analysis.chunk_classification` and the workflow's resolved state is unchanged (deterministic
     resume, including across a worker restart / workflow replay if feasible to force one).
4. Confirm, against the live `analysis.chunk_classification` table (or its eventual replacement),
   that no row exists for any item left pending or explicitly rejected in step 3 — the concrete
   "no unintended persistence payload" proof the register asks for.
5. Update `docs/reviews/2026-08-25-schema-audit/AUDIT-GAP-REGISTER.md`'s Resolution log for
   GAP-031 (not done here — outside this packet's ownership) once live verification in steps 1–4
   passes, and update `docs/runbooks/N8N-PIPELINE-GOLIVE-RUNBOOK.md:111-112` to describe the new
   signal contract.

## Files changed

- `server/temporal/classification_workflow.py` — rewritten (gate signal, enum allowlists, item
  adjudication, `_resolve_gate`, extended output).
- `tests/test_classification_workflow.py` — new.
- `docs/reviews/2026-08-25-schema-audit/GAP-031-IMPLEMENTATION-STATUS.md` — new (this file).

No other files were modified. `server/temporal/worker.py` needed no change: it registers
`ClassificationBatchPipeline` by class reference, and the workflow name and activity list are
unchanged.
