> _Byline: Codex · GPT-5 · 2026-08-29._

<task>
Implement the UIW-native preview read plane and Workbench BFF needed by `/evidence/preview`. The current
client incorrectly sends a Temporal/UIW run id into legacy `/v1/records?run_id` and legacy ops-run SSE;
those stores are not correlated, so the preview cannot show real messages or events.

Create one opaque UIW preview handle/workflow-id contract that resolves request/source-version/generation,
selected parser+version/config digest, preview digest, paginated context normalized messages with
participant semantics and attachment refs, typed context fingerprint receipts, decision receipt, and
replayable monotonic events with Last-Event-ID. Use the actual UIW/context PostgreSQL repositories and
activity/receipt history; never fabricate sample data and never query legacy `ops.workflow_run.artifact_id`
as the source of UIW records. Approval identity must come from authenticated Workbench context, never a
browser-supplied `decider: owner` role string. Do not compute custody in the view API.

Exclusive allowlist: engine HTTP API/UIW preview-read modules and tests (not engine/uiw/workflow.go,
activities, hash/raw repositories, adapters/sbv, or SQL 0045/0048); workbench/api UIW client/router/types
and tests excluding `app/runtime/auth.py` and `tests/test_auth.py`; workbench/web `src/lib/sbv-preview.ts`,
`src/components/sbv/**`, `src/app/evidence/preview/**`, and their smoke tests; plus one new bylined receipt.
Do not touch shell/header/sidebar/intake, deploy/auth, SQL, vendored/sbv, docs/HANDOFF, or ADR files.

If an existing table cannot provide a required field without schema work outside this allowlist, fail
loudly with a typed `not_available` field and document the exact missing producer; do not invent or
silently map a legacy identifier. Preserve the existing UIW approve/reject gate but bind the request to
authenticated subject and immutable preview fields available today.
</task>

<verification_loop>
Run and make green before finishing:
  cd engine; go test ./httpapi/... ./uiw/... ./postgres/...
  go vet ./httpapi/...
  cd ../workbench/api; uv run pytest -q tests
  cd ../web; npm run lint; npm run build; node --test smoke/sbv-preview-boundary.contract.test.mjs
  cd ../..; git diff --check
Confirm only allowlisted files changed.
</verification_loop>

<action_safety>
Shared dirty worktree with other implementation agents. Never reset, clean, stash, move, delete,
broad-stage, git add, commit, push, deploy, or modify another lane. Never hard-delete. Read applicable
AGENTS.md/AGENT_MEMORY.md first and adapt to existing uncommitted preview-client files.
</action_safety>

<structured_output_contract>
End with: 1. API/correlation implementation; 2. exact files touched; 3. exact gates/counts; 4. fields
explicitly unavailable and why. Leave edits uncommitted.
</structured_output_contract>
