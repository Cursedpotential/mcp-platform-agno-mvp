> _Byline: Codex · GPT-5 · 2026-08-29._

<task>
Implement the complete remediation of the local 0048 context-fingerprint/UIW repair lane after an
independent REQUEST CHANGES review. Work only in this allowlist: contracts/import/v1 hash-receipt
schema/example/self_validate; sql/0045_context_fingerprint_semantics.sql;
sql/0048_context_fingerprint_uiw_repair.sql; tests/test_0048_context_fingerprint_uiw_repair.py;
engine/activities hashing/raw_pipeline/register and tests; engine/postgres hash_repository and
raw_pipeline_repository plus tests; engine/stagegraph/graph_test.go; engine/temporal/n8n_client_test.go;
engine/uiw options/workflow/tests; engine/uiwworker/worker_test.go; tests/test_temporal_skeleton.py; and
docs/reviews/2026-08-29-context-fingerprint-uiw-repair.md. Do not touch migration 0047, Workbench,
auth, SBV adapter/vendored code, or unrelated files.

Fix every blocker, not just tests: make the numbered 0036->0045->0048 chain schema-correct; make 0048
transactional, platform-targeted, prerequisite/role guarded, fail-closed, and pin every function
search_path; preserve historical activity_execution and hash_receipt provenance/idempotency across
legacy command aliases; version the JSON receipt contract compatibly instead of breaking 1.0.0; implement
real same-workflow reject/resume semantics or honestly change the status/contract if impossible within
the allowlist; and replace external-byte self-attestation with an independently recomputed/attested
external-byte verification boundary. Never call UIW context fingerprints evidence H1/H2/H3.

Add executable PostgreSQL 18 behavior coverage for apply/rollback/permissions/translation/legacy retry
where the repo pattern permits; a missing disposable service may skip the live harness but static-only
substring assertions are insufficient. Update the receipt truthfully.
</task>

<verification_loop>
Run and make green before finishing:
  uv run pytest -q tests/test_0048_context_fingerprint_uiw_repair.py tests/test_temporal_skeleton.py
  uv run python contracts/import/v1/self_validate.py
  cd engine; go test ./activities ./postgres ./stagegraph ./temporal ./uiw ./uiwworker; go vet ./...
  cd ..; uv run ruff check tests/test_0048_context_fingerprint_uiw_repair.py tests/test_temporal_skeleton.py
  git diff --check
Confirm only allowlisted files changed. Do not claim PostgreSQL/live proof if skipped.
</verification_loop>

<action_safety>
Shared dirty worktree. Other agents are editing different files. Never reset, clean, stash, move, delete,
broad-stage, git add, commit, push, deploy, or alter another lane. Never hard-delete; quarantine only with
explicit proof, though no quarantine is expected here. Read applicable AGENTS.md first.
</action_safety>

<structured_output_contract>
End with: 1. defects fixed and architecture decisions; 2. exact files touched; 3. exact gate counts;
4. skipped live gates and remaining blockers. Leave all edits uncommitted.
</structured_output_contract>
